from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.modules.listing_generator.batch import (
    generate_batch_from_csv,
    results_to_csv,
    summarize_results,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Batch-generate Amazon listings from an Excel-friendly CSV."
    )
    parser.add_argument("--input", required=True, type=Path, help="Input CSV path")
    parser.add_argument("--output", required=True, type=Path, help="Output CSV path")
    parser.add_argument("--marketplace", default="amazon.com")
    parser.add_argument("--language", default="en", choices=["en", "de", "fr", "es", "it", "jp"])
    parser.add_argument("--concurrency", type=int, default=3, choices=range(1, 6))
    return parser


async def run(args: argparse.Namespace) -> None:
    csv_text = args.input.read_text(encoding="utf-8-sig")
    results = await generate_batch_from_csv(
        csv_text,
        default_marketplace=args.marketplace,
        default_language=args.language,
        max_concurrency=args.concurrency,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(results_to_csv(results), encoding="utf-8-sig")
    print(json.dumps(summarize_results(results), ensure_ascii=False))
    print(f"Review file: {args.output}")


def main() -> None:
    asyncio.run(run(build_parser().parse_args()))


if __name__ == "__main__":
    main()
