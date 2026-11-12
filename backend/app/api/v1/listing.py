from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from typing import Optional
import dataclasses

from app.modules.listing_generator.batch import (
    BatchInputError,
    generate_batch_from_csv,
    results_to_csv,
    summarize_results,
)
from app.modules.listing_generator import generate_listing, optimize_listing_from_asin

router = APIRouter(prefix="/listing", tags=["Listing Generator"])


class GenerateRequest(BaseModel):
    keyword: str
    product_details: Optional[dict] = None
    marketplace: str = "amazon.com"
    language: str = "en"


class OptimizeRequest(BaseModel):
    asin: str
    platform: str = "amazon"
    language: str = "en"


@router.post("/generate")
async def generate(req: GenerateRequest):
    try:
        listing = await generate_listing(
            keyword=req.keyword,
            product_details=req.product_details,
            marketplace=req.marketplace,
            language=req.language,
        )
        return dataclasses.asdict(listing)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/optimize")
async def optimize(req: OptimizeRequest):
    try:
        listing = await optimize_listing_from_asin(
            asin=req.asin,
            platform=req.platform,
            language=req.language,
        )
        return dataclasses.asdict(listing)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/languages")
async def supported_languages():
    from app.modules.listing_generator.constants import SUPPORTED_LANGUAGES
    return {"languages": SUPPORTED_LANGUAGES}


@router.post("/batch")
async def generate_batch_csv(
    file: UploadFile = File(...),
    marketplace: str = Query("amazon.com"),
    language: str = Query("en"),
    max_concurrency: int = Query(3, ge=1, le=5),
):
    try:
        raw = await file.read()
        csv_text = raw.decode("utf-8-sig")
        results = await generate_batch_from_csv(
            csv_text,
            default_marketplace=marketplace,
            default_language=language,
            max_concurrency=max_concurrency,
        )
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=422, detail="CSV 必须使用 UTF-8 编码") from exc
    except BatchInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "summary": summarize_results(results),
        "rows": [
            {
                "source_row": result.source_row,
                "keyword": result.keyword,
                "status": result.status,
                "issues": result.issues,
                "listing": dataclasses.asdict(result.listing) if result.listing else None,
            }
            for result in results
        ],
        "review_csv": results_to_csv(results),
    }
