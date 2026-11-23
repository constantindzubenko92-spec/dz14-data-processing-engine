"""Ліниве читання, перевірка та перетворення продажів."""

from __future__ import annotations

import csv
from collections.abc import Generator, Iterable, Iterator, Mapping
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from heapq import nsmallest
from itertools import count
from math import isfinite
from pathlib import Path
from typing import NamedTuple, TypeAlias, TypeVar

DEFAULT_CSV: Path = Path(__file__).resolve().parents[1] / "data" / "sales.csv"
CSV_FIELDS: tuple[str, ...] = ("id", "product", "category", "quantity", "price", "status")

Item = TypeVar("Item")
Scalar: TypeAlias = str | int | float | bool | None
NestedValue: TypeAlias = (
    Scalar | list["NestedValue"] | tuple["NestedValue", ...] | dict[str, "NestedValue"]
)


class SalesDataError(ValueError):
    """Дані CSV не відповідають формату продажів."""


@dataclass(frozen=True)
class Sale:
    """Один рядок CSV після перевірки та перетворення полів."""

    id: int
    product: str
    category: str
    quantity: int
    price: float
    status: str


@dataclass(frozen=True)
class PricedSale:
    """Продаж і виручка за ним у копійках."""

    sale: Sale
    revenue_cents: int


class CsvRow(NamedTuple):
    """Необроблений рядок і його номер у вихідному файлі."""

    line_number: int
    values: dict[str, str]


def read_csv_rows(path: str | Path) -> Generator[CsvRow, None, None]:
    """Читає заголовок і поступово повертає рядки як словники."""
    with Path(path).open(encoding="utf-8-sig", newline="") as source:
        reader = csv.reader(source, strict=True)
        try:
            header = next(reader, None)
            if header is None or len(header) != len(CSV_FIELDS) or set(header) != set(CSV_FIELDS):
                raise SalesDataError("CSV має містити поля " + ", ".join(CSV_FIELDS))

            for values in reader:
                if not values:
                    continue
                if len(values) != len(header):
                    raise SalesDataError(f"Рядок {reader.line_num}: неправильна кількість полів.")
                yield CsvRow(reader.line_num, dict(zip(header, values)))
        except csv.Error as error:
            raise SalesDataError(f"Рядок {reader.line_num}: {error}") from error


def validate_sales(rows: Iterable[CsvRow]) -> Iterator[Sale]:
    """Перевіряє записи та перетворює поля на типи моделі Sale."""
    for line_number, row in rows:
        try:
            sale_id = int(row["id"])
            quantity = int(row["quantity"])
            price = float(row["price"])
        except ValueError as error:
            raise SalesDataError(f"Рядок {line_number}: неправильний формат числа.") from error

        product = row["product"].strip()
        category = row["category"].strip()
        status = row["status"].strip().casefold()
        if sale_id <= 0 or quantity <= 0 or not isfinite(price) or price < 0:
            raise SalesDataError(f"Рядок {line_number}: неприпустиме ID, кількість або ціна.")
        if not (product and category and status):
            raise SalesDataError(f"Рядок {line_number}: назва, категорія та статус обов'язкові.")
        yield Sale(sale_id, product, category, quantity, price, status)


def read_sales(path: str | Path = DEFAULT_CSV) -> Generator[Sale, None, None]:
    """Повертає перевірені записи без завантаження всього CSV."""
    rows = read_csv_rows(path)
    try:
        yield from validate_sales(rows)
    finally:
        rows.close()


def filter_sales(sales: Iterable[Sale], status: str = "completed") -> Iterator[Sale]:
    """Залишає записи з указаним статусом."""
    wanted = status.strip().casefold()
    for sale in sales:
        if sale.status.casefold() == wanted:
            yield sale


def transform_sales(sales: Iterable[Sale]) -> Iterator[PricedSale]:
    """Обчислює виручку кожного продажу та округлює її до копійок."""
    for sale in sales:
        amount = Decimal(str(sale.price)) * sale.quantity
        cents = int((amount * 100).to_integral_value(rounding=ROUND_HALF_UP))
        yield PricedSale(sale, cents)


def calculate_revenue(sales: Iterable[Sale]) -> Iterator[Decimal]:
    """Повертає накопичену виручку після кожного переданого продажу."""
    total_cents = 0
    for priced_sale in transform_sales(sales):
        total_cents += priced_sale.revenue_cents
        yield Decimal(total_cents) / 100


def generate_batches(items: Iterable[Item], size: int) -> Iterator[list[Item]]:
    """Формує пакети розміру size, включно з останнім неповним пакетом."""
    if size <= 0:
        raise ValueError("Розмір пакета має бути додатним.")

    batch: list[Item] = []
    for item in items:
        batch.append(item)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch


def generate_top_products(
    product_revenues: Mapping[str, int], limit: int = 5
) -> Iterator[tuple[str, int]]:
    """Повертає товари за спаданням виручки й за назвою при нічиїй."""
    if limit < 0:
        raise ValueError("Ліміт товарів не може бути від'ємним.")
    yield from nsmallest(
        limit, product_revenues.items(), key=lambda item: (-item[1], item[0])
    )


def sales_ids(start: int = 1) -> Iterator[int]:
    """Нескінченно генерує унікальні для одного обходу цілі ID."""
    if start <= 0:
        raise ValueError("Початковий ID має бути додатним.")
    yield from count(start)


def fibonacci(n: int) -> Iterator[int]:
    """Повертає перші n чисел Фібоначчі, починаючи з нуля."""
    if n < 0:
        raise ValueError("Кількість значень не може бути від'ємною.")
    current, following = 0, 1
    for _ in range(n):
        yield current
        current, following = following, current + following


def flatten_nested(value: NestedValue) -> Iterator[Scalar]:
    """Рекурсивно обходить списки, кортежі та значення словників."""
    if isinstance(value, dict):
        for child in value.values():
            yield from flatten_nested(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from flatten_nested(child)
    else:
        yield value
