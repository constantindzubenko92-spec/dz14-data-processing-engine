"""Ітератор продажів з необов'язковим фільтром категорії."""

from collections.abc import Iterable, Iterator

from generators.sales_generator import Sale


class SalesIterator(Iterator[Sale]):
    """Послідовно повертає продажі з будь-якого ітерованого джерела."""

    def __init__(self, sales: Iterable[Sale], category: str | None = None) -> None:
        """Створює ітератор над вхідними записами без їх копіювання."""
        self._sales: Iterator[Sale] = iter(sales)
        self._category: str | None = category

    def __iter__(self) -> "SalesIterator":
        """Повертає поточний об'єкт ітератора."""
        return self

    def __next__(self) -> Sale:
        """Повертає наступний відповідний продаж або піднімає StopIteration."""
        for sale in self._sales:
            if self._category is None or sale.category == self._category:
                return sale
        raise StopIteration
