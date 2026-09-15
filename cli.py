# cli.py - Command Line Interface for OmniScrape AI
import argparse
import json
import sys
import os
import time
import pandas as pd
from dotenv import load_dotenv

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

# Ensure src/ is on sys.path
_src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from omniscrape.engine.scrape import (
    scrape_website,
    extract_body_content,
    clean_body_content,
    capture_page_screenshot,
    extract_animation_assets,
    bundle_animations_zip
)
from omniscrape.engine.parse import extract_with_ai
from omniscrape.models.schemas import EXTRACTION_TEMPLATES, create_dynamic_model
from omniscrape.storage.db import save_scrape, save_extraction, detect_price_changes
from omniscrape.storage.outputs import default_output_manager
from omniscrape.automation.webhook import send_webhook

load_dotenv()


def handle_list_runs(limit: int = 15):
    """Display summary of recent runs saved in outputs/runs/."""
    runs = default_output_manager.list_runs(limit=limit)
    if not runs:
        print("ℹ️ No runs found in the outputs/runs/ directory.")
        return

    print(f"\n📂 Recent OmniScrape Execution Runs ({len(runs)}):")
    print(f"{'RUN ID':<36} {'STATUS':<10} {'TASK':<18} {'CREATED AT':<20} {'FILES'}")
    print("-" * 105)
    for r in runs:
        run_id = r.get("run_id", "unknown")
        status = r.get("status", "unknown").upper()
        task = r.get("task_type", "scrape")
        created = r.get("created_at", "unknown")
        files_count = len(r.get("files", []))
        print(f"{run_id:<36} {status:<10} {task:<18} {created:<20} {files_count} file(s)")
    print()


def handle_view_run(run_id: str):
    """Display detailed manifest and files for a specific run ID."""
    run = default_output_manager.get_run(run_id)
    if not run:
        print(f"❌ Run '{run_id}' was not found in outputs/runs/.")
        return

    print(f"\n=======================================================")
    print(f"🔍 Run Details: {run.get('run_id')}")
    print(f"=======================================================")
    print(f"• URL:        {run.get('url', 'N/A')}")
    print(f"• Task Type:  {run.get('task_type', 'N/A')}")
    print(f"• Mode:       {run.get('mode', 'N/A')}")
    print(f"• Status:     {run.get('status', 'N/A')}")
    print(f"• Created At: {run.get('created_at', 'N/A')}")
    print(f"• Duration:   {run.get('duration_seconds', 'N/A')}s")
    print(f"• Directory:  {run.get('run_dir', 'N/A')}")

    files = run.get("available_files", {})
    print(f"\n📁 Stored Files ({len(files)}):")
    for fname, fmeta in files.items():
        size_kb = fmeta.get("size_bytes", 0) / 1024
        print(f"  - {fname:<25} ({size_kb:.1f} KB, modified {fmeta.get('modified', '')})")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="OmniScrape AI CLI - Autonomous multi-modal web scraping, structured data extraction, and animation bundling."
    )
    parser.add_argument("--url", "-u", help="Target URL to scrape")
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
    parser.add_argument("--output", "-o", help="Custom path to save output file (.json, .csv, or .md)")
    parser.add_argument("--screenshot", help="Capture and save screenshot to specified PNG file path")
    parser.add_argument("--webhook", help="Webhook URL to POST extraction results to")
    parser.add_argument("--animations", action="store_true", help="Extract animation/motion assets (Lottie, Rive, SVGs, GIFs, CSS Keyframes)")
    parser.add_argument("--download-zip", help="Custom path to download and bundle discovered animation assets as a .ZIP archive")
    parser.add_argument("--list-runs", action="store_true", help="List all saved execution runs in the outputs folder")
    parser.add_argument("--view-run", help="Inspect metadata and files for a specific run ID")

    args = parser.parse_args()

    # Handle run explorer subcommands
    if args.list_runs:
        handle_list_runs()
        sys.exit(0)

    if args.view_run:
        handle_view_run(args.view_run)
        sys.exit(0)

    if not args.url:
        parser.error("--url (-u) is required unless using --list-runs or --view-run.")

    start_time = time.time()

    # Initialize dedicated isolated run directory
    task_type = "animations" if args.animations else ("structured_extract" if (args.prompt or args.template or args.fields) else "scrape")
    run_info = default_output_manager.create_run(
        url=args.url,
        task_type=task_type,
        mode=args.mode,
        template=args.template,
        prompt=args.prompt
    )
    run_dir = run_info["run_dir"]
    run_id = run_info["run_id"]

    # Optional Screenshot capture
    if args.screenshot or args.mode == "local":
        print(f"📸 Capturing page screenshot of {args.url}...")
        try:
            run_ss_path = os.path.join(run_dir, "screenshot.png")
            capture_page_screenshot(args.url, run_ss_path)
            default_output_manager.save_image(run_dir, "screenshot.png", run_ss_path, category="image")
            if args.screenshot:
                import shutil
                shutil.copyfile(run_ss_path, args.screenshot)
                print(f"✅ Screenshot saved to {args.screenshot}")
            print(f"✅ Screenshot recorded in run folder: {run_ss_path}")
        except Exception as e:
            print(f"⚠️ Screenshot capture notice: {e}", file=sys.stderr)

    # 1. Scrape
    print(f"🕷️ Scraping {args.url} [mode={args.mode}]...")
    try:
        raw_html = scrape_website(args.url, mode=args.mode)
        default_output_manager.save_text(run_dir, "raw_page.html", raw_html, category="html")

        body = extract_body_content(raw_html)
        cleaned = clean_body_content(body)
        scrape_id = save_scrape(args.url, args.mode, raw_html, cleaned)
        default_output_manager.save_text(run_dir, "cleaned_dom.txt", cleaned, category="text")

        print(f"✅ Scraped {len(raw_html):,} raw chars -> {len(cleaned):,} cleaned chars (~{(1 - len(cleaned)/len(raw_html))*100:.1f}% reduction)")
    except Exception as e:
        print(f"❌ Scraping error: {e}", file=sys.stderr)
        default_output_manager.finalize_run(run_dir, status="failed", duration_seconds=time.time() - start_time, error=str(e))
        sys.exit(1)

    # Animation extraction mode
    if args.animations:
        print(f"\n🎬 Extracting animation & motion assets from {args.url}...")
        assets = extract_animation_assets(raw_html, base_url=args.url)
        default_output_manager.save_json(run_dir, "animation_assets.json", assets, category="json")

        # Bundle ZIP into run directory
        zip_bytes = bundle_animations_zip(assets, base_url=args.url)
        default_output_manager.save_zip(run_dir, "animations.zip", zip_bytes, category="archive")

        print(f"✨ Found {assets['total_assets_count']} total animation assets:")
        print(f"  • Lottie Files: {len(assets['lottie_files'])}")
        for lf in assets['lottie_files']:
            print(f"    - [{lf['type']}] {lf.get('url', 'inline')}")
        print(f"  • Rive Files: {len(assets['rive_files'])}")
        for rf in assets['rive_files']:
            print(f"    - {rf['url']}")
        print(f"  • SVG Animations: {len(assets['svg_animations'])}")
        print(f"  • Motion Media (GIF/Video): {len(assets['motion_media'])}")
        for mm in assets['motion_media']:
            print(f"    - [{mm['type']}] {mm['url']}")
        print(f"  • Animation JS Libraries: {len(assets['animation_libraries'])}")
        for lib in assets['animation_libraries']:
            print(f"    - {lib['library'].upper()}: {lib['url']}")
        print(f"  • CSS Keyframe Animations: {len(assets['css_keyframes'])}")
        for kf in assets['css_keyframes']:
            print(f"    - @keyframes {kf['name']}")

        # Custom user path if requested
        zip_target = args.download_zip or (args.output if args.output and args.output.endswith(".zip") else None)
        if zip_target:
            os.makedirs(os.path.dirname(os.path.abspath(zip_target)), exist_ok=True)
            with open(zip_target, "wb") as f:
                f.write(zip_bytes)
            print(f"✅ Saved custom animation ZIP archive to {zip_target}")

        if args.output and args.output.endswith(".json"):
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(assets, f, indent=2)
            print(f"✅ Saved animation manifest JSON to {args.output}")

        default_output_manager.finalize_run(run_dir, status="success", duration_seconds=time.time() - start_time)
        print(f"\n📁 Full run output preserved in: {run_dir}")
        sys.exit(0)

    # If no prompt or template is provided, print preview and finish run
    if not args.prompt and not args.template and not args.fields:
        print("\n--- Cleaned DOM Preview ---")
        print(cleaned[:600] + ("..." if len(cleaned) > 600 else ""))
        default_output_manager.finalize_run(run_dir, status="success", duration_seconds=time.time() - start_time)
        print(f"\n📁 Run output saved to: {run_dir}")
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

        # Save to run folder
        default_output_manager.save_json(run_dir, "extracted_data.json", result, category="json")
        if isinstance(result, list) and result:
            try:
                default_output_manager.save_csv(run_dir, "extracted_data.csv", result, category="tabular")
            except Exception:
                pass

        if isinstance(result, list):
            changes = detect_price_changes(args.url, result)
            if changes:
                print(f"🔔 Detected {len(changes)} price shift(s)!")
                for c in changes:
                    print(f"   - {c['item']}: {c['old_price']} -> {c['new_price']} ({c['change_amount']:+})")

        # 4. User-specified output handling
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
            print(f"💾 Results also saved to {args.output}")
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

        default_output_manager.finalize_run(run_dir, status="success", duration_seconds=time.time() - start_time)
        print(f"\n📁 Full run output preserved in: {run_dir}")

    except Exception as e:
        print(f"❌ Extraction error: {e}", file=sys.stderr)
        default_output_manager.finalize_run(run_dir, status="failed", duration_seconds=time.time() - start_time, error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
