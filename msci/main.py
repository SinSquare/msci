"""msci main app"""

from typing import Annotated

import numpy as np
from fastapi import FastAPI, Depends, HTTPException, Query

from msci import models
from msci.state import lifespan, get_wiki
from msci.wiki_word_frequency import WikiWordFrequency


app = FastAPI(title="msci", lifespan=lifespan)  # pylint: disable=unused-argument


def get_wiki_word_freq():
    """Get wiki"""
    return get_wiki()


# pylint: disable=dangerous-default-value
async def handle_work(
    wiki, key, ignore_list: list[str] = [], percentile: int | None = None
):
    """Handle work retrieval"""
    while (result := wiki.get_result(key)) is None:
        pass
    wiki.cleanup(key)
    if not result.get("success", False):
        raise HTTPException(
            status_code=500,
            detail={"message": result.get("error", "An unknown error happened")},
        )
    words = result["words"]
    for word in ignore_list:
        words.pop(word, None)

    if percentile is not None:
        counts = np.array(list(words.values()))
        threshold = np.percentile(counts, percentile)
        return {word: count for word, count in words.items() if count < threshold}
    return words


@app.get(
    "/word-frequency",
    response_model=models.WordFrequencyResult,
    response_model_exclude_unset=True,
    status_code=200,
)
async def get_word_freq(
    data: Annotated[models.WordFrequencyGet, Query()],
    wiki: WikiWordFrequency = Depends(get_wiki_word_freq),
):
    """GET WordFrequency"""
    key = wiki.add_job(data.article, data.depth)
    return await handle_work(wiki, key)


@app.post(
    "/keywords",
    response_model=models.WordFrequencyResult,
    response_model_exclude_unset=True,
    status_code=200,
)
async def post_word_freq(
    data: models.WordFrequencyPost,
    wiki: WikiWordFrequency = Depends(get_wiki_word_freq),
):
    """POST Keywords"""

    key = wiki.add_job(data.article, data.depth)
    return await handle_work(wiki, key, data.ignore_list, data.percentile)
