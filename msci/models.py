"""Request and response models."""

from pydantic import BaseModel, RootModel, Field


class WordFrequencyGet(BaseModel):
    """GET WordFrequency"""

    article: str = Field(min_length=1)
    depth: int = Field(ge=0)


class WordFrequencyPost(WordFrequencyGet):
    """POST WordFrequency"""

    ignore_list: list[str] | None = None
    percentile: int | None = Field(ge=0, le=100, default=None)


class WordFrequencyResult(RootModel):
    """Sort Output model"""

    root: dict[str, int]

    def __iter__(self):  # pragma: no cover
        return iter(self.root)

    def __getitem__(self, item):  # pragma: no cover
        return self.root[item]
