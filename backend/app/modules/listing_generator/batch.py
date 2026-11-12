from __future__ import annotations

import asyncio
import csv
import io
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Iterable, Mapping

from app.modules.listing_generator.constants import SUPPORTED_LANGUAGES
from app.modules.listing_generator.models import GeneratedListing


ListingGenerator = Callable[..., Awaitable[GeneratedListing]]

MAX_BATCH_ROWS = 200
MAX_CONCURRENCY = 5

FIELD_ALIASES = {
    "keyword": ("keyword", "primary_keyword", "product_name", "title"),
    "asin": ("asin",),
    "brand": ("brand",),
    "features": ("features", "feature", "selling_points"),
    "marketplace": ("marketplace", "market"),
    "language": ("language", "lang"),
}
CONTROL_FIELDS = {
    alias
    for aliases in FIELD_ALIASES.values()
    for alias in aliases
}


class BatchInputError(ValueError):
    """Raised when the uploaded CSV cannot be parsed safely."""


@dataclass
class BatchProduct:
    row_number: int
    keyword: str
    product_details: dict
    marketplace: str
    language: str
    issues: list[str] = field(default_factory=list)


@dataclass
class BatchListingResult:
    source_row: int
    keyword: str
    status: str
    listing: GeneratedListing | None = None
    issues: list[str] = field(default_factory=list)


def _first_value(record: Mapping[str, str], field_name: str) -> str:
    for alias in FIELD_ALIASES[field_name]:
        value = record.get(alias, "").strip()
        if value:
            return value
    return ""


def _normalize_record(record: Mapping[str, str]) -> dict[str, str]:
    return {
        str(key or "").strip().lower().replace(" ", "_").replace("-", "_"): str(value or "").strip()
        for key, value in record.items()
    }


def _parse_features(raw: str) -> list[str]:
    return [
        item.strip()
        for item in raw.replace("\r", "\n").replace("|", "\n").split("\n")
        if item.strip()
    ]


def parse_product_csv(
    csv_text: str,
    *,
    default_marketplace: str = "amazon.com",
    default_language: str = "en",
) -> list[BatchProduct]:
    """Parse Excel-friendly CSV text into validated listing inputs."""
    text = csv_text.lstrip("\ufeff")
    if not text.strip():
        raise BatchInputError("CSV 文件为空")

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise BatchInputError("CSV 缺少表头")

    products: list[BatchProduct] = []
    for row_number, raw_record in enumerate(reader, start=2):
        record = _normalize_record(raw_record)
        if not any(record.values()):
            continue
        if len(products) >= MAX_BATCH_ROWS:
            raise BatchInputError(f"单次最多处理 {MAX_BATCH_ROWS} 行")

        issues: list[str] = []
        keyword = _first_value(record, "keyword")
        if not keyword:
            issues.append("缺少 keyword、primary_keyword、product_name 或 title")

        marketplace = record.get("marketplace", "").strip() or default_marketplace
        language = record.get("language", "").strip().lower() or default_language
        if language not in SUPPORTED_LANGUAGES:
            issues.append(
                f"不支持的语言 {language!r}，可选值：{', '.join(SUPPORTED_LANGUAGES)}"
            )

        product_details = {
            key: value
            for key, value in record.items()
            if key and key not in CONTROL_FIELDS and value
        }
        features = _parse_features(record.get("features", ""))
        if features:
            product_details["features"] = features
        if record.get("asin"):
            product_details["asin"] = record["asin"]
        if record.get("brand"):
            product_details["brand"] = record["brand"]

        products.append(
            BatchProduct(
                row_number=row_number,
                keyword=keyword,
                product_details=product_details,
                marketplace=marketplace,
                language=language,
                issues=issues,
            )
        )

    if not products:
        raise BatchInputError("CSV 中没有可处理的数据行")
    return products


def validate_listing(listing: GeneratedListing) -> list[str]:
    """Return Amazon-facing rule violations that require human review."""
    issues: list[str] = []
    if not listing.title.strip():
        issues.append("标题为空")
    elif len(listing.title) > 200:
        issues.append(f"标题 {len(listing.title)} 字符，超过 200")

    if len(listing.bullet_points) != 5:
        issues.append(f"卖点数量为 {len(listing.bullet_points)}，要求 5 条")
    for index, bullet in enumerate(listing.bullet_points, start=1):
        if not bullet.strip():
            issues.append(f"第 {index} 条卖点为空")
        elif len(bullet) > 500:
            issues.append(f"第 {index} 条卖点 {len(bullet)} 字符，超过 500")

    if not listing.description.strip():
        issues.append("描述为空")
    elif len(listing.description) > 2000:
        issues.append(f"描述 {len(listing.description)} 字符，超过 2000")

    search_terms = " ".join(listing.search_terms)
    if len(search_terms) > 250:
        issues.append(f"搜索词 {len(search_terms)} 字符，超过 250")

    if len(listing.subject_matter) != 5:
        issues.append(f"A+ 主题数量为 {len(listing.subject_matter)}，要求 5 条")
    if not 0 <= listing.seo_score <= 10:
        issues.append("SEO 分数不在 0-10 范围内")
    return issues


async def generate_batch(
    products: Iterable[BatchProduct],
    generator: ListingGenerator,
    *,
    max_concurrency: int = 3,
) -> list[BatchListingResult]:
    """Generate listings with bounded concurrency and row-level error handling."""
    if not 1 <= max_concurrency <= MAX_CONCURRENCY:
        raise ValueError(f"max_concurrency 必须在 1-{MAX_CONCURRENCY} 之间")

    semaphore = asyncio.Semaphore(max_concurrency)

    async def generate_one(product: BatchProduct) -> BatchListingResult:
        if product.issues:
            return BatchListingResult(
                source_row=product.row_number,
                keyword=product.keyword,
                status="failed",
                issues=product.issues,
            )

        try:
            async with semaphore:
                listing = await generator(
                    keyword=product.keyword,
                    product_details=product.product_details,
                    marketplace=product.marketplace,
                    language=product.language,
                )
        except Exception as exc:
            return BatchListingResult(
                source_row=product.row_number,
                keyword=product.keyword,
                status="failed",
                issues=[f"生成失败：{type(exc).__name__}: {exc}"],
            )

        validation_issues = validate_listing(listing)
        return BatchListingResult(
            source_row=product.row_number,
            keyword=product.keyword,
            status="needs_review" if validation_issues else "success",
            listing=listing,
            issues=validation_issues,
        )

    return await asyncio.gather(*(generate_one(product) for product in products))


async def generate_batch_from_csv(
    csv_text: str,
    *,
    default_marketplace: str = "amazon.com",
    default_language: str = "en",
    max_concurrency: int = 3,
    generator: ListingGenerator | None = None,
) -> list[BatchListingResult]:
    products = parse_product_csv(
        csv_text,
        default_marketplace=default_marketplace,
        default_language=default_language,
    )
    if generator is None:
        from app.modules.listing_generator.generator import generate_listing

        generator = generate_listing
    return await generate_batch(
        products,
        generator,
        max_concurrency=max_concurrency,
    )


def _safe_csv_cell(value: object) -> str:
    text = "" if value is None else str(value)
    if text.startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


def results_to_csv(results: Iterable[BatchListingResult]) -> str:
    """Render reviewable batch output into an Excel-friendly CSV."""
    fieldnames = [
        "source_row",
        "keyword",
        "status",
        "asin_reference",
        "title",
        "bullet_1",
        "bullet_2",
        "bullet_3",
        "bullet_4",
        "bullet_5",
        "description",
        "search_terms",
        "validation_issues",
    ]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()

    for result in results:
        listing = result.listing
        bullets = listing.bullet_points[:5] if listing else []
        row = {
            "source_row": result.source_row,
            "keyword": result.keyword,
            "status": result.status,
            "asin_reference": listing.asin_reference if listing else "",
            "title": listing.title if listing else "",
            "description": listing.description if listing else "",
            "search_terms": " ".join(listing.search_terms) if listing else "",
            "validation_issues": "；".join(result.issues),
        }
        for index in range(5):
            row[f"bullet_{index + 1}"] = bullets[index] if index < len(bullets) else ""
        writer.writerow(
            {
                key: _safe_csv_cell(value)
                for key, value in row.items()
            }
        )
    return output.getvalue()


def summarize_results(results: Iterable[BatchListingResult]) -> dict[str, int]:
    summary = {"total": 0, "success": 0, "needs_review": 0, "failed": 0}
    for result in results:
        summary["total"] += 1
        summary[result.status] = summary.get(result.status, 0) + 1
    return summary
