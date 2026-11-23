"""Командний запуск Data Processing Engine та демонстрація генераторів."""

from __future__ import annotations

from argparse import ArgumentParser
from contextlib import closing
from itertools import islice
from pathlib import Path

from generators.sales_generator import (
    DEFAULT_CSV,
    NestedValue,
    SalesDataError,
    calculate_revenue,
    fibonacci,
    filter_sales,
    flatten_nested,
    read_sales,
    sales_ids,
)
from iterators.sales_iterator import SalesIterator
from services.analytics import SalesReport, analyze_sales, compare_memory


def print_report(report: SalesReport) -> None:
    """Друкує фінансові показники та рейтинг товарів."""
    print("========== SALES ANALYTICS ==========")
    print()
    print(f"Total sales: {report.total_sales}")
    print(f"Completed sales: {report.completed_sales}")
    print(f"Total revenue: {report.total_revenue:.2f}")
    print(f"Average check: {report.average_check:.2f}")
    print("Most popular product:")
    print(report.most_popular_product or "N/A")
    print("Most profitable category:")
    print(report.most_profitable_category or "N/A")
    print("Top 5 products:")
    if not report.top_products:
        print("N/A")
    for position, (name, revenue) in enumerate(report.top_products, start=1):
        print(f"{position}. {name} - {revenue:.2f}")
    print()
    print("=====================================")


def show_generator_examples(path: Path, category: str) -> None:
    """Показує обхід категорії та результати допоміжних генераторів."""
    with closing(read_sales(path)) as records:
        preview = list(islice(SalesIterator(records, category=category), 3))
    print(f"First sale IDs in {category}: {[sale.id for sale in preview]}")

    with closing(read_sales(path)) as records:
        revenue = calculate_revenue(filter_sales(records))
        sample = [f"{amount:.2f}" for amount in islice(revenue, 3)]
        print(f"Running revenue (first three completed sales): {sample}")

    nested: NestedValue = {"shop": ["Laptop", ("Mouse", 3)], "active": True}
    print(f"Generated IDs: {list(islice(sales_ids(), 5))}")
    print(f"Fibonacci: {list(fibonacci(8))}")
    print(f"Nested values: {list(flatten_nested(nested))}")


def main() -> None:
    """Обробляє CSV, друкує звіт і за запитом вимірює пам'ять."""
    parser = ArgumentParser(description="Аналіз продажів інтернет-магазину.")
    parser.add_argument("csv", nargs="?", type=Path, default=DEFAULT_CSV, help="шлях до CSV")
    parser.add_argument("--category", default="Electronics", help="категорія для демонстрації")
    parser.add_argument("--batch-size", type=int, default=64, help="розмір пакета")
    parser.add_argument("--memory", action="store_true", help="виміряти пам'ять списку й генератора")
    args = parser.parse_args()

    if args.batch_size <= 0:
        parser.error("--batch-size має бути додатним")

    path: Path = args.csv
    try:
        with closing(read_sales(path)) as records:
            report = analyze_sales(records, args.batch_size)
        print_report(report)
        print()
        show_generator_examples(path, args.category)
        if args.memory:
            list_peak, stream_peak = compare_memory(path)
            print(f"Peak memory (list): {list_peak:,} bytes")
            print(f"Peak memory (generator): {stream_peak:,} bytes")
    except (SalesDataError, OSError, UnicodeError) as error:
        parser.exit(1, f"Error: {error}\n")


if __name__ == "__main__":
    main()
