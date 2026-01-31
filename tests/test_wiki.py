"""test wiki"""
from unittest.mock import call
import copy

from msci.wiki_word_frequency import WikiWordFrequency

EXTRACT_RESPONSE = {
    "query": {"pages": {"1": {"title": "title", "extract": "Some words here."}}}
}
LINKS_RESPONSE = {
    "query": {"pages": {"1": {"links": [{"title": "title1"}, {"title": "title2"}]}}}
}


def test_wiki_extract(http_testserver):
    def callback():
        return EXTRACT_RESPONSE

    http_testserver.add_callback("/", callback)
    wiki = WikiWordFrequency(10, http_testserver.url, "test")
    key = wiki.add_job("test", 0)
    while (result := wiki.get_result(key)) is None:
        pass
    assert result["success"]
    assert result["words"] == {"here": 1, "words": 1, "Some": 1}
    assert http_testserver.request_log == ["GET /"]
    request = http_testserver.pop_first()
    assert request["params"] == {
        "action": "query",
        "format": "json",
        "prop": "extracts",
        "explaintext": "True",
        "exlimit": "max",
        "titles": "test",
    }
    assert key in wiki._results

    wiki.cleanup(key)

    assert key not in wiki._results
    assert key not in wiki._words
    assert key not in wiki._links
    assert key not in wiki._futures


def test_wiki_links(http_testserver):
    def callback():
        req = http_testserver.request
        titles = req.args.get("titles").split("|")
        prop = req.args.get("prop")
        if prop == "links":
            return LINKS_RESPONSE
        resp = {}
        for i, t in enumerate(titles):
            resp[i] = {"title": t, "extract": t}
        return {"query": {"pages": resp}}

    http_testserver.add_callback("/", callback)
    wiki = WikiWordFrequency(10, http_testserver.url, "test")
    key = wiki.add_job("test", 1)
    while (result := wiki.get_result(key)) is None:
        pass
    assert result["success"]
    assert result["words"] == {"test": 1, "title2": 1, "title1": 1}


def test_wiki_continue(http_testserver):
    def callback():
        req = http_testserver.request
        titles = req.args.get("titles").split("|")
        prop = req.args.get("prop")
        if prop == "links":
            resp = copy.deepcopy(LINKS_RESPONSE)
            if req.args.get("continue"):
                resp["query"]["pages"]["1"]["links"] = [{"title": "title2"}]
                return resp
            resp["query"]["pages"]["1"]["links"] = [{"title": "title1"}]
            resp["continue"] = {"continue": "value"}
            return resp

        resp = copy.deepcopy(EXTRACT_RESPONSE)
        if len(titles) == 1:
            resp["query"]["pages"]["1"] = {"title": titles[0], "extract": titles[0]}
            return resp
        if req.args.get("continue"):
            resp["query"]["pages"]["1"] = {"title": titles[-1], "extract": titles[-1]}
            return resp
        resp["query"]["pages"]["1"] = {"title": titles[0], "extract": titles[0]}
        resp["continue"] = {"continue": "value"}
        return resp

    http_testserver.add_callback("/", callback)
    wiki = WikiWordFrequency(10, http_testserver.url, "test")
    key = wiki.add_job("test", 1)
    while (result := wiki.get_result(key)) is None:
        pass
    assert result["success"]
    assert result["words"] == {"test": 1, "title2": 1, "title1": 1}


def test_wiki_links_duplicated(http_testserver):
    def callback():
        req = http_testserver.request
        titles = req.args.get("titles").split("|")
        prop = req.args.get("prop")
        if prop == "links":
            resp = copy.deepcopy(LINKS_RESPONSE)
            resp["query"]["pages"]["1"]["links"] = [{"title": "title1"}]
            if req.args.get("continue"):
                return resp
            resp["continue"] = {"continue": "value"}
            return resp
        resp = {}
        for i, t in enumerate(titles):
            resp[i] = {"title": t, "extract": t}
        return {"query": {"pages": resp}}

    http_testserver.add_callback("/", callback)
    wiki = WikiWordFrequency(10, http_testserver.url, "test")
    key = wiki.add_job("test", 1)
    while (result := wiki.get_result(key)) is None:
        pass
    assert result["success"]
    assert result["words"] == {"test": 1, "title1": 1}
    assert len(http_testserver.request_log) == 4


def test_wiki_error(http_testserver):
    def callback():
        return EXTRACT_RESPONSE, 500

    http_testserver.add_callback("/", callback)
    wiki = WikiWordFrequency(1, http_testserver.url, "test")
    key = wiki.add_job("test", 1)
    while (result := wiki.get_result(key)) is None:
        pass
    assert result == {
        "success": False,
        "error": "Could not get response from wikipedia because of HTTP 500",
    }


def test_wiki_retry(http_testserver, mocker):
    resp = [({}, 429, {"Retry-After": "2"}), ({}, 429), (EXTRACT_RESPONSE)]
    resp_gen = (r for r in resp)
    sleep_mock = mocker.patch("time.sleep")

    def callback():
        return next(resp_gen)

    http_testserver.add_callback("/", callback)
    wiki = WikiWordFrequency(1, http_testserver.url, "test")
    key = wiki.add_job("test", 0)
    while (result := wiki.get_result(key)) is None:
        pass
    assert result == {"success": True, "words": {"Some": 1, "words": 1, "here": 1}}
    assert sleep_mock.call_args_list == [call(3), call(18)]
