# schemas.py - Pydantic Schema Definitions and Extraction Templates
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, create_model


class EcommerceProduct(BaseModel):
    name: str = Field(description="Name or title of the product")
    current_price: str = Field(description="Current sale price or cost (including currency symbol if present)")
    original_price: Optional[str] = Field(None, description="Original or list price before discount")
    rating: Optional[str] = Field(None, description="Product review rating, e.g., '4.5' or '4 out of 5 stars'")
    review_count: Optional[str] = Field(None, description="Number of customer reviews or ratings")
    in_stock: Optional[bool] = Field(None, description="True if the item is in stock or available to buy")
    product_url: Optional[str] = Field(None, description="Direct URL or link to the product details")


class JobPosting(BaseModel):
    title: str = Field(description="Job title or designation")
    company: str = Field(description="Company or hiring organization name")
    location: Optional[str] = Field(None, description="City, state, country, or 'Remote'")
    salary_range: Optional[str] = Field(None, description="Offered salary or compensation range")
    job_type: Optional[str] = Field(None, description="Full-time, Part-time, Contract, Internship, etc.")
    experience_level: Optional[str] = Field(None, description="Entry level, Mid, Senior, Lead, etc.")
    skills: Optional[List[str]] = Field(default_factory=list, description="Key skills or technologies required")


class RealEstateListing(BaseModel):
    property_title: str = Field(description="Title or brief description of the listing")
    price: str = Field(description="Listing price or monthly rental rate")
    address: Optional[str] = Field(None, description="Physical address or neighborhood/city")
    bedrooms: Optional[str] = Field(None, description="Number of bedrooms")
    bathrooms: Optional[str] = Field(None, description="Number of bathrooms")
    area_sqft: Optional[str] = Field(None, description="Square footage or property area")
    property_type: Optional[str] = Field(None, description="Apartment, House, Condo, Villa, etc.")
    agent_contact: Optional[str] = Field(None, description="Agent or contact phone/email")


class ArticleSummary(BaseModel):
    headline: str = Field(description="Title or headline of the article")
    author: Optional[str] = Field(None, description="Author or contributor name")
    publication_date: Optional[str] = Field(None, description="Date the article was published")
    reading_time: Optional[str] = Field(None, description="Estimated reading time in minutes")
    summary_points: List[str] = Field(default_factory=list, description="Bullet points summarizing main points")
    key_takeaways: Optional[List[str]] = Field(default_factory=list, description="Core conclusions or actionable insights")


class QuoteItem(BaseModel):
    quote: str = Field(description="The full text of the quote")
    author: str = Field(description="Author who said or wrote the quote")
    tags: Optional[List[str]] = Field(default_factory=list, description="Associated tags, themes, or categories")


# Template registry
EXTRACTION_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "🛍️ E-Commerce Products": {
        "model": EcommerceProduct,
        "default_prompt": "Extract all products listed on this page with their name, current price, original price, rating, review count, stock availability, and link.",
        "description": "Ideal for Amazon, eBay, Shopify stores, and retail catalogs."
    },
    "💼 Job Postings": {
        "model": JobPosting,
        "default_prompt": "Extract all job vacancies on this page including job title, company, location, salary range, job type, and required skills.",
        "description": "Ideal for LinkedIn, Indeed, Greenhouse, and company career pages."
    },
    "🏡 Real Estate Listings": {
        "model": RealEstateListing,
        "default_prompt": "Extract all property listings including title, price, address, bedrooms, bathrooms, area in sqft, and property type.",
        "description": "Ideal for Zillow, Redfin, Realtor.com, and rental portals."
    },
    "📰 Article & News Summaries": {
        "model": ArticleSummary,
        "default_prompt": "Extract the article headline, author, publication date, reading time, summary bullet points, and key takeaways.",
        "description": "Ideal for blogs, Medium, Substack, TechCrunch, and news sites."
    },
    "💬 Quotes & Testimonials": {
        "model": QuoteItem,
        "default_prompt": "Extract all quotes with the author name and list of associated tags.",
        "description": "Ideal for quotes collections, customer testimonials, and reviews."
    }
}


def create_dynamic_model(field_names: List[str]) -> type[BaseModel]:
    """
    Dynamically create a Pydantic model from a list of user-provided field names.
    All fields default to Optional[str] for maximum extraction flexibility.
    """
    fields = {}
    for name in field_names:
        clean_name = name.strip().lower().replace(" ", "_").replace("-", "_")
        if clean_name:
            fields[clean_name] = (Optional[str], Field(None, description=f"Extracted {name.strip()}"))

    if not fields:
        fields["extracted_text"] = (Optional[str], Field(None, description="Extracted content"))

    return create_model("CustomExtractedItem", **fields)
