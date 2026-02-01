"""Process pages"""

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import partial
from threading import Lock
import logging
import re
import time
import uuid

import requests

log = logging.getLogger(__name__)
word_re = re.compile(r"[^\w\-/']", re.UNICODE)


class WikiError(Exception):
    """Exception raised for custom error scenarios."""

    def __init__(self, message):
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class WikiResult:
    success: bool
    words: dict[str, int] | None = None
    error: str | None = None


class WikiWordFrequency:
    """WikiWordFrequency"""

    # pylint: disable=too-many-instance-attributes
    # pylint: disable=too-many-arguments
    # pylint: disable=too-many-positional-arguments
    def __init__(
        self,
        max_workers: int,
        api_url: str,
        user_agent: str,
        access_token: str | None = None,
        batch_size: int = 5,
    ):
        """Init WikiWordFrequency.

        Args:
            max_workers: number of workers in ThreadPoolExecutor
            api_url: wikipedia API url
            user_agent: user agent for the API calls
            access_token (optional): access token to extend rate limits
        """

        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._futures = {}
        self._links = {}
        self._results = {}
        self._words = {}
        self._lock = Lock()

        self.batch_size = batch_size
        self.api_url = api_url
        self.headers = {"User-Agent": user_agent}
        if access_token:
            self.headers["Authorization"] = f"Bearer {access_token}"

    def _get_response(self, params):
        """Get response from wikipedia API

        Will retry up to 5 times in case of timeout/HTTP 429
        """
        try_cnt = 0
        while try_cnt < 5:
            try_cnt += 1
            try:
                response = requests.get(
                    self.api_url, headers=self.headers, params=params, timeout=3
                )
                if response.status_code == 200:
                    return response.json()
                if response.status_code == 429:
                    try:
                        retry_after = int(response.headers.get("Retry-After"))
                        log.warning(
                            "HTTP 429 - sleeping for %ds (retry-after)", retry_after + 1
                        )
                        time.sleep(retry_after + 1)
                    except (ValueError, TypeError):
                        log.warning(
                            "HTTP 429 - sleeping for %ds (fallback)", 2 * 3**try_cnt
                        )
                        time.sleep(2 * 3**try_cnt)
                    continue
                log.warning("HTTP %d", response.status_code)
                raise WikiError(
                    (
                        "Could not get response from wikipedia because of"
                        f" HTTP {response.status_code}"
                    )
                )
            except requests.exceptions.Timeout:
                log.warning("Timeout")
                time.sleep(2 * 3**try_cnt)
                continue
        log.warning("Retries exhausted")
        raise WikiError("Could not get response from wikipedia (timeout)")

    def _get_words(self, articles: list[str]):
        """Get word count for articles"""
        log.info("Getting words for %s", ",".join(articles))

        def calculate_words(text):
            words = Counter()
            words.update([word_re.sub("", w) for w in text.split()])
            words.pop("", None)
            return words

        params = {
            "action": "query",
            "format": "json",
            "prop": "extracts",
            "explaintext": True,
            "exlimit": "max",
            "titles": "|".join(articles),
        }
        all_words = Counter()
        while True:
            response = self._get_response(params)
            pages = response.get("query", {}).get("pages", {})
            for _, content in pages.items():
                all_words += calculate_words(content.get("extract", ""))
            if "continue" in response:
                params.update(response["continue"])
            else:
                break
        log.info("Done getting words for %s", ",".join(articles))
        return all_words

    def _get_links(self, articles: list[str]):
        """Get links for articles"""
        log.info("Getting links for %s", ",".join(articles))
        params = {
            "action": "query",
            "format": "json",
            "prop": "links",
            "pllimit": "max",
            "plnamespace": 0,
            "titles": "|".join(articles),
        }
        all_links = set()
        while True:
            response = self._get_response(params)
            pages = response.get("query", {}).get("pages", {})
            for _, content in pages.items():
                all_links.update(
                    [link.get("title") for link in content.get("links", [])]
                )
            if "continue" in response:
                params.update(response["continue"])
            else:
                break
        log.info("Done getting links for %s", ",".join(articles))
        return all_links

    def _error(self, key, message):
        if key in self._results:
            return
        res = WikiResult(success=False, error=message)
        self._results.update({key: res})
        self._words.pop(key, None)
        self._links.pop(key, None)
        self._futures.pop(key, None)

    def _finished(self, key):
        if key in self._results:
            return
        if key not in self._futures:
            return
        if len(self._futures[key]) > 0:
            return
        words = self._words.pop(key, {})
        res = WikiResult(success=True, words=words)
        self._results.update({key: res})
        self._links.pop(key, None)
        self._futures.pop(key, None)

    def _merge_words(self, key, future):
        """Merge words with existing data"""
        log.info("Merge words for %s", key)
        with self._lock:
            if key not in self._futures:
                return
            self._futures[key].discard(future)
            try:
                result = future.result()
                self._words[key] += result
            except WikiError as e:
                self._error(key, e.message)
            except Exception:  # pylint: disable=broad-exception-caught
                self._error(key, "An unknown error happened")
                log.error("Task failed", exc_info=True)
            finally:
                self._finished(key)

    def _merge_links(self, key, depth, max_depth, future):
        """Merge links with existing data"""
        log.info("Merge links for %s", key)
        with self._lock:
            if key not in self._futures:
                return
            self._futures[key].discard(future)
            try:
                result = future.result()
                links = []
                for link in result:
                    if link in self._links[key]:
                        continue
                    self._links[key].add(link)
                    links.append(link)
                for i in range(0, len(links), self.batch_size):
                    articles = links[i : i + self.batch_size]
                    future = self._executor.submit(self._get_words, articles)
                    future.add_done_callback(partial(self._merge_words, key))
                    self._futures[key].add(future)
                    if depth < max_depth:
                        future = self._executor.submit(self._get_links, articles)
                        future.add_done_callback(
                            partial(self._merge_links, key, depth + 1, max_depth)
                        )
                        self._futures[key].add(future)
            except WikiError as e:
                self._error(key, e.message)
            except Exception:  # pylint: disable=broad-exception-caught
                self._error(key, "An unknown error happened")
                log.error("Task failed", exc_info=True)
            finally:
                self._finished(key)

    def add_job(
        self,
        article: str,
        depth: int,
    ):
        """Add job

        Args:
            article: article name
            depth: depth to traverse
        """
        key = uuid.uuid4()

        self._words.update({key: Counter()})
        self._links.update({key: set()})

        futures = [self._executor.submit(self._get_words, [article])]
        futures[0].add_done_callback(partial(self._merge_words, key))
        if depth > 0:
            futures.append(self._executor.submit(self._get_links, [article]))
            futures[-1].add_done_callback(partial(self._merge_links, key, 1, depth))

        self._futures.update({key: set(futures)})
        return key

    def get_result(self, key):
        """Get job result

        Args:
            key: id return from add_job

        Returns:
            None: the job is not yet finished
            dict: data
        """
        with self._lock:
            if key not in self._results:
                return None
            return self._results[key]

    def cleanup(self, key):
        """Clean job result

        Args:
            key: id return from add_job
        """
        with self._lock:
            self._results.pop(key, None)
            self._words.pop(key, None)
            self._links.pop(key, None)
            self._futures.pop(key, None)
