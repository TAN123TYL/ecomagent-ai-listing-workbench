from app.modules.listing_generator.batch import (
    generate_batch,
    generate_batch_from_csv,
    parse_product_csv,
    validate_listing,
)
from app.modules.listing_generator.models import GeneratedListing


async def generate_listing(*args, **kwargs):
    from app.modules.listing_generator.generator import generate_listing as _generate_listing

    return await _generate_listing(*args, **kwargs)


async def optimize_listing_from_asin(*args, **kwargs):
    from app.modules.listing_generator.generator import (
        optimize_listing_from_asin as _optimize_listing_from_asin,
    )

    return await _optimize_listing_from_asin(*args, **kwargs)


__all__ = [
    "generate_batch",
    "generate_batch_from_csv",
    "generate_listing",
    "optimize_listing_from_asin",
    "parse_product_csv",
    "validate_listing",
    "GeneratedListing",
]
