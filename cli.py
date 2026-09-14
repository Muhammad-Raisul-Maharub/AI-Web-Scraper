# cli.py - Command Line Interface for AI Web Scraper
import argparse
import json
import sys
import os
import pandas as pd
from dotenv import load_dotenv

from scrape import scrape_website, extract_body_content, clean_body_content, capture_page_screenshot
from parse import extract_with_ai
from schemas import EXTRACTION_TEMPLATES, create_dynamic_model
from db import save_scrape, save_extraction, detect_price_changes
from webhook import send_webhook

load_dotenv()


def main():
    parser = argparse.ArgumentParser(
        description="AI Web Scraper CLI - Intelligent web scraping and AI-powered structured extraction."
    )
    parser.add_argument("--url", "-u", required=True, help="Target URL to scrape")
    parser.add_argument(
        "--mode", "-m", choices=["fast", "local", "bright_data"], default="fast",
        help="Scraping mode (default: fast)"
    )
    parser.add_argument(
        "--template", "-t",
        choices=["ecommerce", "jobs", "realestate", "articles", "quotes"],
        help="Pre-configured extraction template"
    )
    parser.add_argument("--prompt", "-p", help="Custom extraction instructions")
    parser.add_argument("--fields", help="Comma-separated custom field names (e.g. 'title,price,stock')")
    parser.add_argument(
        "--provider", choices=["gemini", "ollama", "openai"], default="gemini",
        help="AI Provider for extraction (default: gemini)"
    )
    parser.add_argument("--model", help="AI model name override")
    parser.add_argument("--api-key", help="API key override (defaults to environment variable)")
    parser.add_argument(
        "--format", "-f", choices=["json", "markdown"], default="json",
        help="Extraction output format (default: json)"
    )
    parser.add_argument("--output", "-o", help="Path to save output file (.json, .csv, or .md)")
    parser.add_argument("--screenshot", help="Capture and save screenshot to specified PNG file path")
    parser.add_argument("--webhook", help="Webhook URL to POST extraction results to")

    args = parser.parse_args()

    # Optional Screenshot capture
    if args.screenshot:
        print(f"📸 Capturing page screenshot of {args.url}...")
        try:
            saved_img = capture_page_screenshot(args.url, args.screenshot)
            print(f"✅ Screenshot saved to {saved_img}")
        except Exception as e:
            print(f"⚠️ Screenshot capture failed: {e}", file=sys.stderr)

    # 1. Scrape
    print(f"🕷️ Scraping {args.url} [mode={args.mode}]...")
    try:
        raw_html = scrape_website(args.url, mode=args.mode)
        body = extract_body_content(raw_html)
        cleaned = clean_body_content(body)
        scrape_id = save_scrape(args.url, args.mode, raw_html, cleaned)
        print(f"✅ Scraped {len(raw_html):,} raw chars -> {len(cleaned):,} cleaned chars (~{(1 - len(cleaned)/len(raw_html))*100:.1f}% reduction)")
    except Exception as e:
        print(f"❌ Scraping error: {e}", file=sys.stderr)
        sys.exit(1)

    # If no prompt or template is provided, print preview and exit
    if not args.prompt and not args.template and not args.fields:
        print("\n--- Cleaned DOM Preview ---")
        print(cleaned[:600] + ("..." if len(cleaned) > 600 else ""))
        sys.exit(0)

    # 2. Schema resolution
    schema_class = None
    instruction = args.prompt or ""

    template_mapping = {
        "ecommerce": "🛍️ E-Commerce Products",
        "jobs": "💼 Job Postings",
        "realestate": "🏡 Real Estate Listings",
        "articles": "📰 Article & News Summaries",
        "quotes": "💬 Quotes & Testimonials"
    }

    if args.template and args.template in template_mapping:
        t_key = template_mapping[args.template]
        t_data = EXTRACTION_TEMPLATES[t_key]
        schema_class = t_data["model"]
        instruction = instruction or t_data["default_prompt"]
    elif args.fields:
        field_list = [f.strip() for f in args.fields.split(",") if f.strip()]
        schema_class = create_dynamic_model(field_list)
        instruction = instruction or f"Extract items matching: {', '.join(field_list)}"

    # 3. AI Extraction
    print(f"🤖 Extracting with {args.provider.upper()}...")
    try:
        result = extract_with_ai(
            dom_content=cleaned,
            parse_description=instruction,
            provider=args.provider,
            model_name=args.model,
            api_key=args.api_key,
            output_format=args.format,
            schema_class=schema_class
        )
        save_extraction(scrape_id, args.url, args.template or "custom", instruction, result)

        if isinstance(result, list):
            changes = detect_price_changes(args.url, result)
            if changes:
                print(f"🔔 Detected {len(changes)} price shift(s)!")
                for c in changes:
                    print(f"   - {c['item']}: {c['old_price']} -> {c['new_price']} ({c['change_amount']:+})")

        # 4. Output handling
        if args.output:
            out_path = args.output.lower()
            if out_path.endswith(".csv") and isinstance(result, list):
                pd.DataFrame(result).to_csv(args.output, index=False)
            elif out_path.endswith(".json"):
                with open(args.output, "w", encoding="utf-8") as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)
            else:
                with open(args.output, "w", encoding="utf-8") as f:
                    f.write(result if isinstance(result, str) else json.dumps(result, indent=2))
            print(f"💾 Results saved to {args.output}")
        else:
            print("\n=== Extracted Results ===")
            if isinstance(result, (list, dict)):
                print(json.dumps(result, indent=2, ensure_ascii=False))
            else:
                print(result)

        # 5. Webhook dispatch
        if args.webhook:
            print(f"🚀 Dispatching webhook to {args.webhook}...")
            send_webhook(args.webhook, f"CLI Scrape: {args.url}", result)
            print("✅ Webhook sent successfully.")

    except Exception as e:
        print(f"❌ Extraction error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
