from __future__ import annotations

import csv
import io

import pytest

from app.modules.listing_generator.batch import (
    BatchInputError,
    generate_batch_from_csv,
    parse_product_csv,
    results_to_csv,
    summarize_results,
    validate_listing,
)
from app.modules.listing_generator.models import GeneratedListing


def make_listing(keyword: str, *, short: bool = False) -> GeneratedListing:
    return GeneratedListing(
        asin_reference="B0TEST00001",
        marketplace="amazon.com",
        language="en",
        title=f"Premium {keyword} for Daily Use",
        bullet_points=(
            ["DURABLE: built to last"]
            if short
            else [f"BENEFIT {index}: useful detail" for index in range(1, 6)]
        ),
        description="A product description that explains the main customer benefits.",
        search_terms=["insulated bottle", "travel bottle"],
        subject_matter=["quality", "portability", "design", "use cases", "care"],
        a_plus_draft="A concise brand story for the product.",
        seo_score=8.2,
        character_counts={"title": 20, "description": 65, "search_terms": 29},
    )


def test_parse_excel_csv_with_bom_and_feature_list():
    csv_text = (
        "\ufeffKeyword,Product Name,Brand,Features,Language\n"
        "insulated bottle,Premium Bottle,Acme,Leakproof|BPA free,en\n"
    )
    products = parse_product_csv(csv_text)

    assert len(products) == 1
    assert products[0].row_number == 2
    assert products[0].keyword == "insulated bottle"
    assert products[0].product_details["brand"] == "Acme"
    assert products[0].product_details["features"] == ["Leakproof", "BPA free"]


def test_parse_invalid_language_is_kept_for_row_level_review():
    products = parse_product_csv("keyword,language\nbottle,xx\n")

    assert products[0].issues
    assert "不支持的语言" in products[0].issues[0]


def test_empty_csv_is_rejected():
    with pytest.raises(BatchInputError, match="为空"):
        parse_product_csv("")


@pytest.mark.asyncio
async def test_batch_marks_valid_and_invalid_generation_results():
    calls: list[str] = []

    async def fake_generator(keyword, product_details, marketplace, language):
        calls.append(keyword)
        return make_listing(keyword, short=keyword == "short-listing")

    csv_text = (
        "keyword\n"
        "water-bottle\n"
        "short-listing\n"
        ",missing-keyword\n"
    )
    results = await generate_batch_from_csv(csv_text, generator=fake_generator)
    summary = summarize_results(results)

    assert calls == ["water-bottle", "short-listing"]
    assert summary == {"total": 3, "success": 1, "needs_review": 1, "failed": 1}
    assert results[0].status == "success"
    assert results[1].status == "needs_review"
    assert results[2].status == "failed"


def test_validate_listing_reports_amazon_constraint_violations():
    issues = validate_listing(make_listing("bottle", short=True))

    assert any("卖点数量" in issue for issue in issues)


def test_export_escapes_spreadsheet_formula_injection():
    csv_text = "keyword\n=unsafe\n"

    async def fake_generator(keyword, product_details, marketplace, language):
        return make_listing(keyword)

    import asyncio

    results = asyncio.run(
        generate_batch_from_csv(csv_text, generator=fake_generator)
    )
    output = results_to_csv(results)
    row = next(csv.DictReader(io.StringIO(output)))

    assert row["keyword"].startswith("'=")
