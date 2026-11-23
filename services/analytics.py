"""Підсумкова аналітика та вимірювання пам'яті."""

from __future__ import annotations

import tracemalloc
from collections import Counter
from collections.abc import Iterable, Iterator, Mapping
from contextlib import closing
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from generators.sales_generator import (
    PricedSale,
    Sale,
    calculate_revenue,
    filter_sales,
    generate_batches,
    generate_top_products,
    read_sales,
    transform_sales,
)
from iterators.sales_iterator import SalesIterator


@dataclass
class SalesTotals:
    """Лічильники та підсумки, що накопичуються під час обходу."""

    total_sales: int = 0
    completed_sales: int = 0
    revenue_cents: int = 0
    product_units: Counter[str] = field(default_factory=Counter)
    product_revenues: Counter[str] = field(default_factory=Counter)
    category_revenues: Counter[str] = field(default_factory=Counter)


@dataclass(frozen=True)
class SalesReport:
    """Готові показники продажів."""

    total_sales: int
    completed_sales: int
    total_revenue: Decimal
    average_check: Decimal
    most_popular_product: str | None
    most_profitable_category: str | None
    top_products: tuple[tuple[str, Decimal], ...]


def count_sales(sales: Iterable[Sale], totals: SalesTotals) -> Iterator[Sale]:
    """Рахує всі записи до фільтрації та передає їх далі."""
    for sale in sales:
        totals.total_sales += 1
        yield sale


def total_revenue(totals: SalesTotals) -> Decimal:
    """Повертає суму виручки завершених продажів."""
    return Decimal(totals.revenue_cents) / 100


def average_check(totals: SalesTotals) -> Decimal:
    """Повертає виручку, поділену на кількість завершених записів."""
    if totals.completed_sales == 0:
        return Decimal("0.00")
    average = total_revenue(totals) / totals.completed_sales
    return average.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _leader(scores: Mapping[str, int]) -> str | None:
    """Вибирає лідера за показником і за назвою при рівності."""
    return min(scores, key=lambda name: (-scores[name], name), default=None)


def most_popular_product(totals: SalesTotals) -> str | None:
    """Повертає назву товару з найбільшою кількістю проданих одиниць."""
    return _leader(totals.product_units)


def most_profitable_category(totals: SalesTotals) -> str | None:
    """Повертає назву категорії з найбільшою виручкою."""
    return _leader(totals.category_revenues)


def top_products(
    totals: SalesTotals, limit: int = 5
) -> tuple[tuple[str, Decimal], ...]:
    """Повертає обмежений список лідерів із грошовими сумами."""
    return tuple(
        (name, Decimal(cents) / 100)
        for name, cents in generate_top_products(totals.product_revenues, limit)
    )


def analyze_batches(
    batches: Iterable[list[PricedSale]], totals: SalesTotals
) -> Iterator[SalesReport]:
    """Споживає пакети та після останнього пакета повертає звіт."""
    for batch in batches:
        for priced in batch:
            sale = priced.sale
            totals.completed_sales += 1
            totals.revenue_cents += priced.revenue_cents
            totals.product_units[sale.product] += sale.quantity
            totals.product_revenues[sale.product] += priced.revenue_cents
            totals.category_revenues[sale.category] += priced.revenue_cents

    yield SalesReport(
        total_sales=totals.total_sales,
        completed_sales=totals.completed_sales,
        total_revenue=total_revenue(totals),
        average_check=average_check(totals),
        most_popular_product=most_popular_product(totals),
        most_profitable_category=most_profitable_category(totals),
        top_products=top_products(totals),
    )


def analyze_sales(sales: Iterable[Sale], batch_size: int = 64) -> SalesReport:
    """З'єднує генератори в один конвеєр аналітики завершених продажів."""
    totals = SalesTotals()
    counted = count_sales(SalesIterator(sales), totals)
    completed = filter_sales(counted)
    priced = transform_sales(completed)
    batches = generate_batches(priced, batch_size)
    return next(analyze_batches(batches, totals))


def _measure_peak(path: Path, materialize: bool) -> tuple[Decimal, int]:
    """Вимірює пік читання й розрахунку виручки одним із двох способів."""
    tracemalloc.start()
    try:
        with closing(read_sales(path)) as records:
            sales: Iterable[Sale] = list(records) if materialize else records
            total = Decimal("0.00")
            for total in calculate_revenue(filter_sales(sales)):
                pass
            _, peak = tracemalloc.get_traced_memory()
            return total, peak
    finally:
        tracemalloc.stop()


def compare_memory(path: Path) -> tuple[int, int]:
    """Повертає піки пам'яті списку й генератора для однакового розрахунку."""
    list_total, list_peak = _measure_peak(path, materialize=True)
    stream_total, stream_peak = _measure_peak(path, materialize=False)
    if list_total != stream_total:
        raise RuntimeError("Способи обробки дали різну виручку.")
    return list_peak, stream_peak
