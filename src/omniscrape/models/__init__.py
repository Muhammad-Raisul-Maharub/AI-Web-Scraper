# src/omniscrape/models/__init__.py
from .schemas import (
    EcommerceProduct,
    JobPosting,
    RealEstateListing,
    ArticleSummary,
    QuoteItem,
    EXTRACTION_TEMPLATES,
    create_dynamic_model
)

__all__ = [
    "EcommerceProduct",
    "JobPosting",
    "RealEstateListing",
    "ArticleSummary",
    "QuoteItem",
    "EXTRACTION_TEMPLATES",
    "create_dynamic_model"
]
