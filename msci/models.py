"""Request and response models."""

from pydantic import BaseModel, RootModel


class WordFrequencyGet(BaseModel):
    """GET WordFrequency"""

    article: str
    depth: int


class WordFrequencyPost(WordFrequencyGet):
    """POST WordFrequency"""

    ignore_list: list[str] = []
    percentile: int | None = None


class WordFrequencyResult(RootModel):
    """Sort Output model"""

    root: dict[str, int]

    def __iter__(self):  # pragma: no cover
        return iter(self.root)

    def __getitem__(self, item):  # pragma: no cover
        return self.root[item]
