# bot/utils/pagination.py
from math import ceil
from typing import TypeVar, Generic, Sequence

T = TypeVar("T")


class Paginator(Generic[T]):
    def __init__(self, items: Sequence[T], page: int = 1, per_page: int = 5):
        self.all_items = items
        self.page = max(1, page)
        self.per_page = per_page
        self.total = len(items)
        self.total_pages = max(1, ceil(self.total / self.per_page))
        if self.page > self.total_pages:
            self.page = self.total_pages

    @property
    def items(self) -> Sequence[T]:
        start = (self.page - 1) * self.per_page
        return self.all_items[start : start + self.per_page]

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    @property
    def info(self) -> str:
        return f"Page {self.page}/{self.total_pages} ({self.total} items)"


class AsyncPaginator:
    def __init__(self, items: list, total: int, page: int = 1, per_page: int = 5):
        self.items = items
        self.total = total
        self.page = max(1, page)
        self.per_page = per_page
        self.total_pages = max(1, ceil(total / per_page))

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    @property
    def info(self) -> str:
        return f"Page {self.page}/{self.total_pages} ({self.total} total)"