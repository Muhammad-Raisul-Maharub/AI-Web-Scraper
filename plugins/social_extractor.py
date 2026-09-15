# plugins/social_extractor.py - Example Custom Tool Plugin
import re
from typing import Dict, Any
from omniscrape.copilot.tools import register_tool


@register_tool(
    name="extract_social_links",
    description="Scan scraped webpage content or DOM text for social media profile links (Twitter/X, LinkedIn, GitHub, YouTube, Instagram).",
    parameters={
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "Webpage text or HTML to scan for social profiles."}
        },
        "required": ["content"]
    }
)
def tool_extract_social_links(content: str) -> Dict[str, Any]:
    """Extract social media profile URLs from text content."""
    patterns = {
        "twitter": r"(?:https?://)?(?:www\.)?(?:twitter\.com|x\.com)/[a-zA-Z0-9_]+",
        "linkedin": r"(?:https?://)?(?:www\.)?linkedin\.com/(?:in|company)/[a-zA-Z0-9_-]+",
        "github": r"(?:https?://)?(?:www\.)?github\.com/[a-zA-Z0-9_-]+",
        "youtube": r"(?:https?://)?(?:www\.)?youtube\.com/(?:c/|channel/|user/|@)[a-zA-Z0-9_-]+",
        "instagram": r"(?:https?://)?(?:www\.)?instagram\.com/[a-zA-Z0-9_.]+"
    }
    found = {}
    for platform, pattern in patterns.items():
        matches = list(set(re.findall(pattern, content)))
        if matches:
            found[platform] = matches
    return {
        "found_profiles": found,
        "total_profiles_found": sum(len(v) for v in found.values())
    }
