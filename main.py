# main.py - OmniScrape AI Dashboard (With AI Copilot, MCP Tools & Runs Explorer)
import os
import sys
import json
import time
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

# Ensure src/ is on sys.path
_src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from omniscrape.engine.scrape import (
    scrape_website,
    extract_body_content,
    clean_body_content,
    dive_deep,
    keyword_based_extraction,
    capture_page_screenshot,
    scrape_with_infinite_scroll,
    scrape_with_pagination,
    extract_animation_assets,
    bundle_animations_zip
)
from omniscrape.engine.parse import extract_with_ai, extract_with_vision
from omniscrape.models.schemas import EXTRACTION_TEMPLATES, create_dynamic_model
from omniscrape.storage.db import (
    save_scrape,
    save_extraction,
    get_recent_scrapes,
    get_recent_extractions,
    detect_price_changes
)
from omniscrape.storage.outputs import default_output_manager
from omniscrape.automation.webhook import send_webhook
from omniscrape.copilot.tools import get_all_tools
from omniscrape.copilot.assistant import run_copilot_turn
from omniscrape.automation import scheduler

load_dotenv()

# Start Background Scheduler Daemon
scheduler_daemon = scheduler.get_scheduler()

# Page Setup
st.set_page_config(
    page_title="OmniScrape AI",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom UI Styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.3rem;
        font-weight: 800;
        background: linear-gradient(90deg, #4f46e5, #06b6d4, #10b981);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0px;
    }
    .sub-header {
        color: #94a3b8;
        font-size: 1.05rem;
        margin-bottom: 25px;
    }
    .metric-card {
        background-color: #1e293b;
        border-radius: 10px;
        padding: 15px;
        border: 1px solid #334155;
        text-align: center;
    }
    .tool-badge {
        background-color: #312e81;
        color: #c7d2fe;
        padding: 3px 8px;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 600;
        margin-right: 5px;
    }
</style>
""", unsafe_allow_html=True)

# Initialize Session State
if "scraped_dom" not in st.session_state:
    st.session_state.scraped_dom = None
if "scraped_raw_html" not in st.session_state:
    st.session_state.scraped_raw_html = None
if "scraped_url" not in st.session_state:
    st.session_state.scraped_url = ""
if "current_screenshot" not in st.session_state:
    st.session_state.current_screenshot = None
if "crawled_results" not in st.session_state:
    st.session_state.crawled_results = []
if "extracted_data" not in st.session_state:
    st.session_state.extracted_data = None
if "detected_price_changes" not in st.session_state:
    st.session_state.detected_price_changes = []
if "scraped_animations" not in st.session_state:
    st.session_state.scraped_animations = None
if "animation_zip_bytes" not in st.session_state:
    st.session_state.animation_zip_bytes = None
if "current_run_info" not in st.session_state:
    st.session_state.current_run_info = None
if "copilot_messages" not in st.session_state:
    st.session_state.copilot_messages = [
        {
            "role": "assistant",
            "content": "👋 Hello! I am your **AI Scraping Copilot**. Ask me to scrape any webpage, extract structured data into tables, take full-page screenshots, or inspect past execution runs!"
        }
    ]

# Sidebar Configuration
with st.sidebar:
    st.title("⚙️ Engine Settings")
    st.markdown("---")

    # AI Provider Setup
    st.subheader("1. AI Provider")
    ai_provider = st.selectbox(
        "Select Provider",
        options=["Google Gemini", "Local Ollama", "OpenAI"],
        index=0
    )

    api_key = None
    model_name = ""

    if ai_provider == "Google Gemini":
        model_name = st.selectbox(
            "Gemini Model",
            options=["gemini-2.5-flash", "gemini-1.5-flash", "gemini-1.5-pro"],
            index=0
        )
        api_key = st.text_input(
            "Gemini API Key",
            type="password",
            value=os.getenv("GEMINI_API_KEY", ""),
            help="Defaults to GEMINI_API_KEY from .env if left blank"
        )
    elif ai_provider == "Local Ollama":
        model_name = st.text_input("Ollama Model", value="llama3.1", help="e.g., llama3.1, llama3.2, mistral, gemma2")
        ollama_url = st.text_input("Ollama Base URL", value="http://localhost:11434")
    elif ai_provider == "OpenAI":
        model_name = st.selectbox(
            "OpenAI Model",
            options=["gpt-4o-mini", "gpt-4o"],
            index=0
        )
        api_key = st.text_input(
            "OpenAI API Key",
            type="password",
            value=os.getenv("OPENAI_API_KEY", ""),
            help="Defaults to OPENAI_API_KEY from .env if left blank"
        )

    st.markdown("---")

    # Scraper Engine Setup
    st.subheader("2. Scraping Engine")
    scraper_mode = st.radio(
        "Engine Mode",
        options=[
            ("fast", "Fast HTTP (Static Sites)"),
            ("local", "Local Headless Chrome (Dynamic JS)"),
            ("bright_data", "Bright Data Proxy (Anti-bot/CAPTCHA)")
        ],
        format_func=lambda x: x[1],
        index=0
    )[0]

    timeout = st.slider("Request Timeout (seconds)", min_value=10, max_value=60, value=25)

    st.markdown("---")
    st.subheader("3. Webhook Dispatcher")
    webhook_url = st.text_input("Discord / Slack / Generic Webhook URL", placeholder="https://discord.com/api/webhooks/...")

    st.markdown("---")
    st.subheader("4. 🔌 MCP Server")
    st.caption("External AI clients (Cursor, Claude Desktop, Antigravity) can connect to this project via MCP.")
    with st.expander("View MCP Connection Config"):
        st.code("""{
  "mcpServers": {
    "omniscrape-ai": {
      "command": "python",
      "args": ["mcp_server.py"]
    }
  }
}""", language="json")

# Main App Header
st.markdown('<div class="main-header">🌐 OmniScrape AI</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-header">Autonomous multi-modal web scraping, animation extraction, Pydantic schemas, isolated run outputs & background monitoring.</div>',
    unsafe_allow_html=True
)

tab_copilot, tab1, tab2, tab3, tab4, tab_runs, tab_scheduler = st.tabs([
    "💬 AI Assistant Copilot",
    "🔍 Scrape & Extract",
    "🌐 Crawl & Pagination",
    "⚡ Quick Keyword Search",
    "📊 History & Price Tracker",
    "📁 Outputs & Runs Explorer",
    "🕒 Automated Scheduler & Monitor"
])

# ==========================================
# TAB COPILOT: Interactive Conversational Agent
# ==========================================
with tab_copilot:
    st.subheader("💬 AI Web Scraping Copilot")
    st.write("An autonomous agent that reasons, plans, and executes scraping tools to answer your queries.")

    # Show active tools
    active_tools = get_all_tools()
    tools_badges = " ".join([f'<span class="tool-badge">⚡ {t}</span>' for t in active_tools.keys()])
    st.markdown(f"**Loaded Tools ({len(active_tools)}):** {tools_badges}", unsafe_allow_html=True)

    # Render Chat History
    for msg in st.session_state.copilot_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if "tool_executions" in msg and msg["tool_executions"]:
                with st.expander(f"🛠️ Tool Invocations ({len(msg['tool_executions'])})"):
                    for te in msg["tool_executions"]:
                        if isinstance(te, dict):
                            st.markdown(f"**Called:** `{te.get('tool', 'tool')}`")
                            st.caption(f"Arguments: `{json.dumps(te.get('args', {}))}`")
                            st.json(te.get("output", {}))

    # User Input Field
    user_prompt = st.chat_input("Ask Copilot (e.g. 'Scrape quotes.toscrape.com and list authors', 'Take a screenshot of news.ycombinator.com')")

    if user_prompt:
        st.session_state.copilot_messages.append({"role": "user", "content": user_prompt})
        with st.chat_message("user"):
            st.markdown(user_prompt)

        with st.chat_message("assistant"):
            status_placeholder = st.status("Thinking and planning tools...", expanded=True)

            def handle_tool_call(name, args):
                status_placeholder.write(f"⚙️ Running tool **{name}** with `{json.dumps(args)}`...")

            try:
                provider_key = {
                    "Google Gemini": "gemini",
                    "Local Ollama": "ollama",
                    "OpenAI": "openai"
                }[ai_provider]

                formatted_history = [
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state.copilot_messages
                ]

                reply = run_copilot_turn(
                    messages=formatted_history,
                    provider=provider_key,
                    model_name=model_name,
                    api_key=api_key,
                    on_tool_call=handle_tool_call
                )

                status_placeholder.update(label="Response generated!", state="complete")
                st.markdown(reply["content"])

                # Store assistant response with execution details
                st.session_state.copilot_messages.append({
                    "role": "assistant",
                    "content": reply["content"],
                    "tool_executions": reply.get("tool_executions", [])
                })

            except Exception as e:
                status_placeholder.update(label=f"Error: {e}", state="error")
                st.error(f"Copilot error: {e}")


# ==========================================
# TAB 1: Single Page Scrape & AI Extraction
# ==========================================
with tab1:
    scrape_target_type = st.radio(
        "🎯 Scraping Target Type",
        options=[
            "📄 Cleaned Text / DOM (AI Extraction)",
            "🎬 Animations & Motion Assets (Lottie, Rive, SVGs, Media, JS Libs)"
        ],
        horizontal=True
    )

    col_url, col_btn, col_shot = st.columns([3, 1, 1])
    with col_url:
        target_url = st.text_input("Target Website URL", placeholder="https://quotes.toscrape.com", label_visibility="collapsed")
    with col_btn:
        scrape_clicked = st.button("🚀 Scrape Page", use_container_width=True)
    with col_shot:
        screenshot_clicked = st.button("📸 Screenshot", use_container_width=True)

    # Screenshot Action
    if screenshot_clicked:
        if not target_url:
            st.warning("Please enter a valid website URL.")
        else:
            with st.spinner("Capturing high-resolution page screenshot..."):
                try:
                    img_path = capture_page_screenshot(target_url, timeout=timeout)
                    current_run = st.session_state.get("current_run_info")
                    if isinstance(current_run, dict) and "run_dir" in current_run:
                        default_output_manager.save_image(current_run["run_dir"], "screenshot.png", img_path, category="image")
                    st.success(f"Screenshot captured and recorded!")
                except Exception as e:
                    st.error(f"Screenshot error: {e}")

    if st.session_state.current_screenshot:
        with st.expander("🖼️ View Captured Page Screenshot", expanded=False):
            st.image(st.session_state.current_screenshot, caption="Rendered Page View", use_container_width=True)

    # Scrape Action
    if scrape_clicked:
        if not target_url:
            st.warning("Please enter a valid website URL.")
        else:
            start_scrape_time = time.time()
            with st.status(f"Fetching content from {target_url}...", expanded=True) as status:
                try:
                    st.write(f"Connecting using **{scraper_mode}** engine...")
                    raw_html = scrape_website(target_url, mode=scraper_mode, timeout=timeout)

                    # Initialize dedicated isolated run folder
                    is_anim = "Animations" in scrape_target_type
                    run_info = default_output_manager.create_run(
                        url=target_url,
                        task_type="animations" if is_anim else "scrape",
                        mode=scraper_mode
                    )
                    st.session_state.current_run_info = run_info
                    run_dir = run_info["run_dir"]
                    default_output_manager.save_text(run_dir, "raw_page.html", raw_html, category="html")

                    if is_anim:
                        st.write("Inspecting and extracting animation & motion assets...")
                        anim_assets = extract_animation_assets(raw_html, base_url=target_url)
                        default_output_manager.save_json(run_dir, "animation_assets.json", anim_assets, category="json")

                        st.write("Packaging discovered assets into ZIP archive...")
                        zip_bytes = bundle_animations_zip(anim_assets, base_url=target_url)
                        default_output_manager.save_zip(run_dir, "animations.zip", zip_bytes, category="archive")
                        default_output_manager.finalize_run(run_dir, status="success", duration_seconds=time.time() - start_scrape_time)

                        st.session_state.scraped_animations = anim_assets
                        st.session_state.animation_zip_bytes = zip_bytes
                        st.session_state.scraped_dom = None
                        st.session_state.scraped_url = target_url
                        status.update(label=f"Extracted {anim_assets['total_assets_count']} animation assets! (Saved in run `{run_info['run_id']}`)", state="complete")
                    else:
                        st.write("Extracting and cleaning DOM...")
                        body = extract_body_content(raw_html)
                        cleaned = clean_body_content(body)
                        default_output_manager.save_text(run_dir, "cleaned_dom.txt", cleaned, category="text")
                        default_output_manager.finalize_run(run_dir, status="success", duration_seconds=time.time() - start_scrape_time)

                        # Save to SQLite database
                        scrape_id = save_scrape(target_url, scraper_mode, raw_html, cleaned)

                        st.session_state.scraped_dom = cleaned
                        st.session_state.scraped_raw_html = raw_html
                        st.session_state.scraped_url = target_url
                        st.session_state.scraped_animations = None
                        st.session_state.animation_zip_bytes = None
                        st.session_state.extracted_data = None
                        st.session_state.detected_price_changes = []
                        status.update(label=f"Scraping completed & saved in run `{run_info['run_id']}` (DB ID: #{scrape_id})!", state="complete")
                except Exception as e:
                    status.update(label=f"Failed to scrape: {e}", state="error")
                    st.error(f"Error scraping website: {e}")

    # Display Animation Asset Breakdown if scraped
    if st.session_state.scraped_animations:
        anim_data = st.session_state.scraped_animations
        st.markdown(f"### 🎬 Discovered Motion & Animation Assets ({anim_data['total_assets_count']} Total)")

        col_a1, col_a2, col_a3, col_a4, col_a5 = st.columns(5)
        col_a1.metric("Lottie JSON", len(anim_data["lottie_files"]))
        col_a2.metric("Rive (.riv)", len(anim_data["rive_files"]))
        col_a3.metric("SVGs (SMIL/Keyframes)", len(anim_data["svg_animations"]))
        col_a4.metric("Motion Media (GIF/MP4)", len(anim_data["motion_media"]))
        col_a5.metric("CSS Keyframes", len(anim_data["css_keyframes"]))

        # Download ZIP button
        if st.session_state.animation_zip_bytes:
            col_z1, col_z2 = st.columns([1, 3])
            with col_z1:
                st.download_button(
                    "📦 Download All Assets (.ZIP)",
                    data=st.session_state.animation_zip_bytes,
                    file_name="animation_assets.zip",
                    mime="application/zip",
                    use_container_width=True
                )
            with col_z2:
                st.caption("Includes manifest.json, downloaded Lottie JSONs, Rive binaries, animated SVGs, looping media, and keyframes.css.")

        anim_tab1, anim_tab2, anim_tab3, anim_tab4, anim_tab5, anim_tab6 = st.tabs([
            f"✨ Lottie ({len(anim_data['lottie_files'])})",
            f"🎯 Rive ({len(anim_data['rive_files'])})",
            f"🎨 Animated SVGs ({len(anim_data['svg_animations'])})",
            f"🎥 Media Loops ({len(anim_data['motion_media'])})",
            f"📜 CSS Keyframes ({len(anim_data['css_keyframes'])})",
            f"📚 JS Libs ({len(anim_data['animation_libraries'])})"
        ])

        with anim_tab1:
            if not anim_data["lottie_files"]:
                st.info("No Lottie files detected.")
            else:
                for idx, lf in enumerate(anim_data["lottie_files"], 1):
                    with st.expander(f"Lottie #{idx} - Type: {lf['type']}"):
                        if lf.get("url") and lf["url"] != "inline_data":
                            st.write(f"**Asset URL:** [{lf['url']}]({lf['url']})")
                        if "preview" in lf:
                            st.code(lf["preview"], language="json")

        with anim_tab2:
            if not anim_data["rive_files"]:
                st.info("No Rive (.riv) animations detected.")
            else:
                for idx, rf in enumerate(anim_data["rive_files"], 1):
                    st.write(f"- [{rf['type']}] [{rf['url']}]({rf['url']})")

        with anim_tab3:
            if not anim_data["svg_animations"]:
                st.info("No animated SVGs detected.")
            else:
                for idx, svg_item in enumerate(anim_data["svg_animations"], 1):
                    with st.expander(f"SVG #{idx} ({svg_item['type']})"):
                        if "html" in svg_item:
                            st.code(svg_item["html"], language="html")
                        if "url" in svg_item:
                            st.write(f"URL: [{svg_item['url']}]({svg_item['url']})")

        with anim_tab4:
            if not anim_data["motion_media"]:
                st.info("No motion GIF or video loops detected.")
            else:
                for idx, mm in enumerate(anim_data["motion_media"], 1):
                    st.write(f"- **{mm['type'].upper()}**: [{mm['url']}]({mm['url']})")

        with anim_tab5:
            if not anim_data["css_keyframes"]:
                st.info("No CSS @keyframes rules detected.")
            else:
                for kf in anim_data["css_keyframes"]:
                    with st.expander(f"@keyframes {kf['name']}"):
                        st.code(kf["css"], language="css")

        with anim_tab6:
            if not anim_data["animation_libraries"]:
                st.info("No known animation JS libraries (GSAP, Three.js, etc.) found in scripts.")
            else:
                for lib in anim_data["animation_libraries"]:
                    st.write(f"- **{lib['library'].upper()}**: [{lib['url']}]({lib['url']})")

    # Display Cleaned Text DOM View if text mode was scraped
    if st.session_state.scraped_dom:
        with st.expander("📄 View Scraped & Cleaned Page Text", expanded=False):
            st.text_area("DOM Content", st.session_state.scraped_dom, height=250)

        # AI Extraction Setup Card
        st.markdown("---")
        st.markdown("### 🤖 Structured AI Data Extraction")

        col_schema_type, col_template = st.columns([1, 2])
        with col_schema_type:
            schema_choice = st.radio(
                "Extraction Schema Mode",
                ["Pre-configured Template", "Custom Fields", "Free-form Prompt"],
                index=0
            )

        selected_template = None
        custom_field_list = []
        schema_class = None
        default_prompt = ""

        with col_template:
            if schema_choice == "Pre-configured Template":
                template_name = st.selectbox("Select Domain Template", list(EXTRACTION_TEMPLATES.keys()))
                t_info = EXTRACTION_TEMPLATES[template_name]
                st.caption(f"ℹ️ {t_info['description']}")
                selected_template = template_name
                schema_class = t_info["model"]
                default_prompt = t_info["default_prompt"]

            elif schema_choice == "Custom Fields":
                fields_str = st.text_input("Enter comma-separated field names", placeholder="e.g. title, price, in_stock, rating")
                if fields_str:
                    custom_field_list = [f.strip() for f in fields_str.split(",") if f.strip()]
                    schema_class = create_dynamic_model(custom_field_list)
                    default_prompt = f"Extract all items with: {', '.join(custom_field_list)}"

        parse_prompt = st.text_area("Extraction Prompt / Refinements", value=default_prompt, height=80)

        col_fmt, col_vis, col_extract = st.columns([1, 1, 1])
        with col_fmt:
            out_fmt = st.selectbox("Output Format", ["Structured JSON (Table)", "Clean Markdown"], index=0)
            fmt_code = "json" if "JSON" in out_fmt else "markdown"
        with col_vis:
            use_vision_mode = st.checkbox(
                "👁️ Multimodal Vision Mode",
                help="Extract directly from the rendered page screenshot instead of raw text (Requires Gemini)."
            )
        with col_extract:
            st.write("")
            st.write("")
            extract_clicked = st.button("✨ Run AI Extraction", type="primary", use_container_width=True)

        if extract_clicked:
            start_extract_time = time.time()
            dom_text = st.session_state.scraped_dom
            if not dom_text and not use_vision_mode:
                st.warning("Please scrape a website first.")
            else:
                provider_key = {
                    "Google Gemini": "gemini",
                    "Local Ollama": "ollama",
                    "OpenAI": "openai"
                }[ai_provider]

                with st.spinner("Extracting data..."):
                    try:
                        # Multimodal Vision Mode
                        if use_vision_mode:
                            if not st.session_state.current_screenshot:
                                img_path = capture_page_screenshot(st.session_state.scraped_url, timeout=timeout)
                                st.session_state.current_screenshot = img_path

                            result = extract_with_vision(
                                image_path=st.session_state.current_screenshot,
                                parse_description=parse_prompt,
                                api_key=str(api_key or ""),
                                model_name=str(model_name or "gemini-2.5-flash"),
                                schema_class=schema_class
                            )
                        # Text DOM Extraction Mode
                        else:
                            result = extract_with_ai(
                                dom_content=dom_text,
                                parse_description=parse_prompt,
                                provider=provider_key,
                                model_name=str(model_name or ""),
                                api_key=str(api_key or ""),
                                output_format=fmt_code,
                                schema_class=schema_class
                            )

                        # Save extraction to database
                        save_extraction(None, st.session_state.scraped_url, selected_template or "custom", parse_prompt, result)

                        # Save extraction to dedicated run folder
                        current_run = st.session_state.get("current_run_info")
                        if isinstance(current_run, dict) and "run_dir" in current_run:
                            cur_run_dir = str(current_run["run_dir"])
                            default_output_manager.save_json(cur_run_dir, "extracted_data.json", result, category="json")
                            if isinstance(result, list) and result:
                                try:
                                    default_output_manager.save_csv(cur_run_dir, "extracted_data.csv", result, category="tabular")
                                except Exception:
                                    pass
                            default_output_manager.finalize_run(
                                cur_run_dir,
                                status="success",
                                duration_seconds=time.time() - start_extract_time,
                                metrics={"extracted_records": len(result) if isinstance(result, list) else 1}
                            )

                        # Price change detection
                        if isinstance(result, list):
                            changes = detect_price_changes(st.session_state.scraped_url, result)
                            st.session_state.detected_price_changes = changes

                        # Webhook dispatch if configured
                        if webhook_url:
                            send_webhook(webhook_url, f"Scrape Extract: {st.session_state.scraped_url}", result)
                            st.toast("✅ Webhook dispatched successfully!")

                        st.session_state.extracted_data = {
                            "format": fmt_code,
                            "content": result,
                            "schema": selected_template
                        }

                    except Exception as e:
                        st.error(f"Extraction error: {e}")

        # Price Alert Banner if changes detected
        if st.session_state.detected_price_changes:
            st.warning(f"🔔 Detected {len(st.session_state.detected_price_changes)} price shift(s) since last scrape!")
            for c in st.session_state.detected_price_changes:
                dir_badge = "🔺 INCREASE" if c["direction"] == "increase" else "🔻 DISCOUNT"
                st.write(f"- **{c['item']}**: {c['old_price']} ➔ **{c['new_price']}** ({dir_badge} of {c['change_amount']:+})")

        # Display Extraction Results
        if st.session_state.extracted_data:
            st.markdown("### 📊 Extracted Results")
            ext = st.session_state.extracted_data

            if ext["format"] == "json":
                data = ext["content"]
                if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
                    df = pd.DataFrame(data)
                    st.dataframe(df, use_container_width=True)

                    # Export Buttons
                    col_d1, col_d2 = st.columns(2)
                    with col_d1:
                        csv_data = df.to_csv(index=False).encode("utf-8")
                        st.download_button("📥 Download as CSV", csv_data, "extracted_data.csv", "text/csv")
                    with col_d2:
                        json_data = json.dumps(data, indent=2).encode("utf-8")
                        st.download_button("📥 Download as JSON", json_data, "extracted_data.json", "application/json")
                else:
                    st.json(data)
                    json_data = json.dumps(data, indent=2).encode("utf-8")
                    st.download_button("📥 Download as JSON", json_data, "extracted_data.json", "application/json")
            else:
                st.markdown(ext["content"])
                st.download_button("📥 Download Markdown", ext["content"].encode("utf-8"), "extracted_data.md", "text/markdown")


# ==========================================
# TAB 2: Domain Crawl & Smart Pagination
# ==========================================
with tab2:
    st.subheader("🌐 Automated Crawling & Smart Pagination")

    crawl_type = st.radio(
        "Automation Method",
        options=["Polite Domain Crawler", "Infinite Scroll Feeder", "Next-Button Paginator"],
        horizontal=True
    )

    if crawl_type == "Polite Domain Crawler":
        st.info("Recursively follows links on the exact same root domain without wandering onto external sites.")
        col_c1, col_c2 = st.columns([3, 1])
        with col_c1:
            crawl_url = st.text_input("Start Crawl URL", placeholder="https://books.toscrape.com")
        with col_c2:
            max_pages = st.slider("Max Pages", min_value=2, max_value=10, value=3)

        if st.button("🕷️ Start Domain Crawl"):
            if not crawl_url:
                st.warning("Please enter a starting URL.")
            else:
                p_bar = st.progress(0)
                status_text = st.empty()
                def crawl_progress(curr, total, url):
                    p_bar.progress(curr / total)
                    status_text.text(f"Scraping ({curr}/{total}): {url}")

                start_c_time = time.time()
                with st.spinner("Crawling pages..."):
                    results = dive_deep(crawl_url, max_pages=max_pages, mode=scraper_mode, progress_callback=crawl_progress)
                    st.session_state.crawled_results = results

                    # Save to dedicated run
                    run_info = default_output_manager.create_run(url=crawl_url, task_type="domain_crawl", mode=scraper_mode)
                    default_output_manager.save_json(run_info["run_dir"], "crawled_pages.json", results, category="json")
                    default_output_manager.finalize_run(run_info["run_dir"], status="success", duration_seconds=time.time() - start_c_time, metrics={"pages_crawled": len(results)})

                    p_bar.empty()
                    status_text.empty()
                    st.success(f"Crawl completed! Recorded in run `{run_info['run_id']}`")

    elif crawl_type == "Infinite Scroll Feeder":
        st.info("Automatically scrolls down dynamic feeds (like product lists or social catalogs) to trigger infinite loading.")
        col_s1, col_s2 = st.columns([3, 1])
        with col_s1:
            scroll_url = st.text_input("Feed URL to Scroll", placeholder="https://example.com/infinite-catalog")
        with col_s2:
            max_scrolls = st.slider("Number of Scrolls", min_value=1, max_value=15, value=4)

        if st.button("📜 Scroll & Scrape Feed"):
            if not scroll_url:
                st.warning("Please enter a URL.")
            else:
                start_s_time = time.time()
                with st.spinner("Auto-scrolling page..."):
                    html = scrape_with_infinite_scroll(scroll_url, max_scrolls=max_scrolls, timeout=timeout)
                    cleaned = clean_body_content(extract_body_content(html))
                    st.session_state.scraped_dom = cleaned
                    st.session_state.scraped_url = scroll_url

                    # Save to dedicated run
                    run_info = default_output_manager.create_run(url=scroll_url, task_type="infinite_scroll", mode="local")
                    default_output_manager.save_text(run_info["run_dir"], "raw_feed.html", html, category="html")
                    default_output_manager.save_text(run_info["run_dir"], "cleaned_dom.txt", cleaned, category="text")
                    default_output_manager.finalize_run(run_info["run_dir"], status="success", duration_seconds=time.time() - start_s_time)

                    st.success(f"Scroll finished! Extracted {len(cleaned):,} characters and saved in run `{run_info['run_id']}`.")

    elif crawl_type == "Next-Button Paginator":
        st.info("Finds and clicks 'Next >' pagination buttons automatically across multiple catalog pages.")
        col_p1, col_p2, col_p3 = st.columns([2, 2, 1])
        with col_p1:
            pag_url = st.text_input("Starting Catalog URL", placeholder="https://books.toscrape.com")
        with col_p2:
            next_css = st.text_input("Next Button CSS Selector", value="li.next a, a.next, a[rel='next']")
        with col_p3:
            pag_limit = st.slider("Page Limit", min_value=2, max_value=8, value=3)

        if st.button("⏩ Run Pagination Scraping"):
            if not pag_url:
                st.warning("Please enter a starting catalog URL.")
            else:
                start_p_time = time.time()
                with st.spinner("Navigating across pages..."):
                    pages = scrape_with_pagination(pag_url, next_button_css=next_css, max_pages=pag_limit, timeout=timeout)
                    st.session_state.crawled_results = pages

                    # Save to dedicated run
                    run_info = default_output_manager.create_run(url=pag_url, task_type="pagination_scrape", mode="local")
                    default_output_manager.save_json(run_info["run_dir"], "paginated_pages.json", pages, category="json")
                    default_output_manager.finalize_run(run_info["run_dir"], status="success", duration_seconds=time.time() - start_p_time, metrics={"pages_scraped": len(pages)})

                    st.success(f"Successfully scraped {len(pages)} paginated pages! Recorded in run `{run_info['run_id']}`.")

    # Display Crawled Pages Table if available
    if st.session_state.crawled_results:
        st.markdown("### 📑 Crawled Pages Summary")
        summary_rows = [
            {
                "Page #": item.get("page", i + 1),
                "URL": item["url"],
                "Characters": len(item["cleaned"]),
                "Lines": len(item["cleaned"].splitlines())
            }
            for i, item in enumerate(st.session_state.crawled_results)
        ]
        st.dataframe(pd.DataFrame(summary_rows), use_container_width=True)


# ==========================================
# TAB 3: Instant Keyword Search
# ==========================================
with tab3:
    st.subheader("⚡ Zero-LLM Fast Keyword Search")
    st.write("Search the currently scraped content for specific keywords instantly without calling an LLM.")

    if not st.session_state.scraped_dom:
        st.info("No scraped content available. Please scrape a website in Tab 1 first.")
    else:
        kw_input = st.text_input("Enter comma-separated keywords", placeholder="e.g. price, author, rating, stock")
        if st.button("Search Keywords"):
            keywords = [k.strip() for k in kw_input.split(",") if k.strip()]
            if keywords:
                matches = keyword_based_extraction(st.session_state.scraped_dom, keywords)
                if matches:
                    st.success(f"Found matches for: {', '.join(keywords)}")
                    st.code(matches, language="text")
                else:
                    st.warning("No matching lines found containing any of those keywords.")


# ==========================================
# TAB 4: History & Price Change Tracker
# ==========================================
with tab4:
    st.subheader("📊 Scrape History & Price Change Tracker")
    st.write("Persistent SQLite database logs of previous scrapes and detected price shifts.")

    col_h1, col_h2 = st.columns(2)
    with col_h1:
        st.markdown("#### 🕒 Recent Scrapes")
        scrapes_list = get_recent_scrapes(limit=10)
        if scrapes_list:
            st.dataframe(pd.DataFrame(scrapes_list), use_container_width=True)
        else:
            st.info("No scrape records logged yet.")

    with col_h2:
        st.markdown("#### 🤖 Recent AI Extractions")
        extractions_list = get_recent_extractions(limit=10)
        if extractions_list:
            display_ext = [
                {
                    "ID": r["id"],
                    "URL": r["url"][:30] + "...",
                    "Template": r["template"],
                    "Time": r["timestamp"]
                }
                for r in extractions_list
            ]
            st.dataframe(pd.DataFrame(display_ext), use_container_width=True)
        else:
            st.info("No extraction records logged yet.")


# ==========================================
# TAB 5: Outputs & Runs Explorer
# ==========================================
with tab_runs:
    st.subheader("📁 Outputs & Runs Explorer")
    st.write("Browse, inspect, preview, and download individual execution runs and generated artifacts.")

    all_runs = default_output_manager.list_runs(limit=100)

    col_r1, col_r2, col_r3 = st.columns(3)
    col_r1.metric("Total Runs", len(all_runs))
    col_r2.metric("Storage Folder", "outputs/runs/")
    if all_runs:
        col_r3.metric("Latest Run", all_runs[0].get("created_at", "N/A"))
    else:
        col_r3.metric("Latest Run", "None")

    if not all_runs:
        st.info("No execution runs recorded yet. Run a scrape, extraction, or animation extraction to view run outputs here!")
    else:
        # Selector for run
        run_options = {
            f"[{r.get('status', 'unknown').upper()}] {r.get('created_at', 'unknown')} ➔ {r.get('url', 'N/A')[:40]} ({r.get('run_id')})": r.get("run_id")
            for r in all_runs
        }
        selected_run_label = st.selectbox("Select Run to Inspect", list(run_options.keys()))
        selected_run_id = str(run_options.get(selected_run_label) or "")
        run_details = default_output_manager.get_run(selected_run_id) if selected_run_id else None

        if run_details:
            # Metadata Summary Card
            with st.container():
                col_m1, col_m2, col_m3 = st.columns(3)
                with col_m1:
                    st.write(f"**URL:** [{run_details.get('url', 'N/A')}]({run_details.get('url', '#')})")
                    st.write(f"**Task Type:** `{run_details.get('task_type', 'N/A')}`")
                    st.write(f"**Mode:** `{run_details.get('mode', 'N/A')}`")
                with col_m2:
                    status_val = run_details.get('status', 'unknown')
                    badge = "🟢 SUCCESS" if status_val == "success" else "🔴 FAILED"
                    st.write(f"**Status:** {badge}")
                    st.write(f"**Created At:** `{run_details.get('created_at', 'N/A')}`")
                    st.write(f"**Duration:** `{run_details.get('duration_seconds', 'N/A')}s`")
                with col_m3:
                    st.write(f"**Directory:** `{run_details.get('run_dir', 'N/A')}`")
                    files_map = run_details.get("available_files", {})
                    st.write(f"**Files Count:** `{len(files_map)} file(s)`")

            st.markdown("---")

            # Sub-tabs for run assets
            sub_tab_data, sub_tab_text, sub_tab_ss, sub_tab_anim, sub_tab_files = st.tabs([
                "📊 Structured Data",
                "📄 Content & DOM",
                "🖼️ Screenshot",
                "🎬 Animations",
                "📦 All Files & ZIP"
            ])

            # 1. Structured Data Sub-tab
            with sub_tab_data:
                if "extracted_data.json" in files_map:
                    json_path = files_map["extracted_data.json"]["path"]
                    try:
                        with open(json_path, "r", encoding="utf-8") as f:
                            ext_json = json.load(f)

                        if isinstance(ext_json, list) and ext_json and isinstance(ext_json[0], dict):
                            st.markdown(f"**Structured Records ({len(ext_json)} items):**")
                            df_ext = pd.DataFrame(ext_json)
                            st.dataframe(df_ext, use_container_width=True)

                            col_dl1, col_dl2 = st.columns(2)
                            with col_dl1:
                                st.download_button(
                                    "📥 Download CSV",
                                    df_ext.to_csv(index=False).encode("utf-8"),
                                    f"{selected_run_id}_extracted.csv",
                                    "text/csv"
                                )
                            with col_dl2:
                                st.download_button(
                                    "📥 Download JSON",
                                    json.dumps(ext_json, indent=2).encode("utf-8"),
                                    f"{selected_run_id}_extracted.json",
                                    "application/json"
                                )
                        else:
                            st.json(ext_json)
                    except Exception as e:
                        st.error(f"Could not load extracted data: {e}")
                else:
                    st.info("No structured data was extracted during this run.")

            # 2. Content & DOM Sub-tab
            with sub_tab_text:
                if "cleaned_dom.txt" in files_map:
                    dom_path = files_map["cleaned_dom.txt"]["path"]
                    with open(dom_path, "r", encoding="utf-8", errors="replace") as f:
                        dom_content = f.read()

                    st.markdown(f"**Cleaned DOM Text ({len(dom_content):,} chars, {len(dom_content.splitlines()):,} lines):**")
                    st.text_area("Content Preview", dom_content, height=300)
                    st.download_button(
                        "📥 Download Cleaned DOM",
                        dom_content.encode("utf-8"),
                        f"{selected_run_id}_cleaned.txt",
                        "text/plain"
                    )
                elif "raw_page.html" in files_map:
                    html_path = files_map["raw_page.html"]["path"]
                    with open(html_path, "r", encoding="utf-8", errors="replace") as f:
                        html_content = f.read()
                    st.markdown(f"**Raw Page HTML ({len(html_content):,} chars):**")
                    st.text_area("HTML Preview", html_content[:5000], height=300)
                else:
                    st.info("No DOM text files in this run.")

            # 3. Screenshot Sub-tab
            with sub_tab_ss:
                if "screenshot.png" in files_map:
                    ss_file_path = files_map["screenshot.png"]["path"]
                    st.image(ss_file_path, caption=f"Screenshot: {selected_run_id}", use_container_width=True)
                    with open(ss_file_path, "rb") as f:
                        st.download_button(
                            "📥 Download Screenshot",
                            f.read(),
                            f"{selected_run_id}_screenshot.png",
                            "image/png"
                        )
                else:
                    st.info("No screenshot captured during this run.")

            # 4. Animations Sub-tab
            with sub_tab_anim:
                if "animation_assets.json" in files_map:
                    anim_path = files_map["animation_assets.json"]["path"]
                    with open(anim_path, "r", encoding="utf-8") as f:
                        anim_json = json.load(f)
                    st.markdown(f"**Discovered Motion Assets ({anim_json.get('total_assets_count', 0)} Total):**")
                    st.json(anim_json)

                    if "animations.zip" in files_map:
                        zip_file_path = files_map["animations.zip"]["path"]
                        with open(zip_file_path, "rb") as f:
                            st.download_button(
                                "📦 Download Animation Assets (.ZIP)",
                                f.read(),
                                f"{selected_run_id}_animations.zip",
                                "application/zip"
                            )
                else:
                    st.info("No animation assets recorded for this run.")

            # 5. All Files & Master ZIP
            with sub_tab_files:
                st.markdown("#### 📁 File Inventory")
                file_rows = [
                    {
                        "Filename": fname,
                        "Size (KB)": round(finfo["size_bytes"] / 1024, 2),
                        "Modified": finfo["modified"]
                    }
                    for fname, finfo in files_map.items()
                ]
                st.dataframe(pd.DataFrame(file_rows), use_container_width=True)

                col_zip_btn, col_del_btn = st.columns(2)
                with col_zip_btn:
                    zip_buffer = default_output_manager.export_run_zip(selected_run_id)
                    if zip_buffer:
                        st.download_button(
                            "📦 Download Entire Run as ZIP",
                            data=zip_buffer.getvalue(),
                            file_name=f"{selected_run_id}_complete.zip",
                            mime="application/zip",
                            type="primary",
                            use_container_width=True
                        )

                with col_del_btn:
                    if st.button("🗑️ Delete This Run", key=f"delete_run_{selected_run_id}"):
                        default_output_manager.delete_run(selected_run_id)
                        st.success(f"Run {selected_run_id} deleted!")
                        st.rerun()


# ==========================================
# TAB 6: Automated Scheduler & Background Monitor
# ==========================================
with tab_scheduler:
    st.subheader("🕒 Automated Recurring Scrapes & Autonomous Monitor")
    st.write("Configure background schedules to monitor target websites periodically, track price/content shifts, and send alerts.")

    jobs = scheduler.list_jobs()
    active_jobs = [j for j in jobs if j["is_active"]]

    col_sm1, col_sm2, col_sm3 = st.columns(3)
    col_sm1.metric("Total Jobs", len(jobs))
    col_sm2.metric("Active Monitors", len(active_jobs))
    col_sm3.metric("Background Daemon", "🟢 Running" if scheduler_daemon.is_running() else "🔴 Stopped")

    # Expander to schedule a new job
    with st.expander("➕ Create New Scheduled Scrape Monitor", expanded=len(jobs) == 0):
        with st.form("new_schedule_form"):
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                sched_name = st.text_input("Job Name", placeholder="e.g. Daily Books Price Monitor")
                sched_url = st.text_input("Target Webpage URL", placeholder="https://books.toscrape.com")
            with col_f2:
                sched_mode = st.selectbox("Scraping Engine", ["fast", "local", "bright_data"], index=0)
                sched_type = st.selectbox("Scrape Target", ["text", "animations"], format_func=lambda x: "📄 Structured Text / DOM" if x == "text" else "🎬 Animations & Motion Assets")

            # Extraction config if text
            col_e1, col_e2 = st.columns(2)
            with col_e1:
                template_opts = ["None (Clean DOM Only)"] + list(EXTRACTION_TEMPLATES.keys())
                sched_template = st.selectbox("Extraction Template", template_opts)
            with col_e2:
                sched_prompt = st.text_input("Custom Extraction Prompt", placeholder="e.g. Extract book titles and prices into structured JSON")

            # Frequency & Alerts
            col_freq, col_int = st.columns(2)
            with col_freq:
                freq_preset = st.selectbox(
                    "Frequency Preset",
                    ["Every 15 Minutes", "Every 1 Hour", "Every 6 Hours", "Every 12 Hours", "Every 24 Hours", "Custom Interval (Mins)"]
                )
            with col_int:
                preset_map = {
                    "Every 15 Minutes": 15,
                    "Every 1 Hour": 60,
                    "Every 6 Hours": 360,
                    "Every 12 Hours": 720,
                    "Every 24 Hours": 1440
                }
                if freq_preset == "Custom Interval (Mins)":
                    sched_interval = st.number_input("Interval (Minutes)", min_value=1, max_value=10080, value=30)
                else:
                    sched_interval = preset_map[freq_preset]
                    st.caption(f"Will trigger every **{sched_interval} minutes**.")

            col_wb1, col_wb2 = st.columns([3, 1])
            with col_wb1:
                sched_webhook = st.text_input("Alert Webhook URL (Discord / Slack / Generic)", placeholder="https://discord.com/api/webhooks/...")
            with col_wb2:
                sched_alert_change = st.checkbox("Alert on change only", value=True, help="Only fire webhook when content diff or price shift occurs.")

            submit_job = st.form_submit_button("🚀 Schedule Background Job", type="primary")

            if submit_job:
                if not sched_name.strip() or not sched_url.strip():
                    st.error("Please provide both a Job Name and a valid Target URL.")
                else:
                    template_val = sched_template if sched_template != "None (Clean DOM Only)" else None
                    job_id = scheduler.create_job(
                        name=sched_name.strip(),
                        url=sched_url.strip(),
                        mode=sched_mode,
                        scrape_type=sched_type,
                        template=template_val,
                        prompt=sched_prompt.strip() if sched_prompt else None,
                        interval_minutes=int(sched_interval),
                        webhook_url=sched_webhook.strip() if sched_webhook else None,
                        alert_on_change_only=sched_alert_change
                    )
                    st.success(f"Job #{job_id} ('{sched_name}') scheduled successfully!")
                    st.rerun()

    # Active and Configured Jobs List
    st.markdown("### 📋 Configured Monitor Jobs")
    if not jobs:
        st.info("No scheduled jobs found. Create one above to begin autonomous monitoring!")
    else:
        for j in jobs:
            status_icon = "🟢 ACTIVE" if j["is_active"] else "⏸️ PAUSED"
            expander_title = f"{status_icon} | #{j['id']} - {j['name']} (Every {j['interval_minutes']}m) ➔ {j['url'][:40]}..."

            with st.expander(expander_title, expanded=False):
                col_det1, col_det2, col_det3 = st.columns(3)
                col_det1.write(f"**URL:** [{j['url']}]({j['url']})")
                col_det1.write(f"**Engine:** `{j['mode']}` | **Type:** `{j['scrape_type']}`")
                col_det2.write(f"**Next Run:** `{j['next_run_at'] or 'Paused'}`")
                col_det2.write(f"**Last Run:** `{j['last_run_at'] or 'Never'}` ({j['last_status']})")
                col_det3.write(f"**Alerts:** `{'Change only' if j['alert_on_change_only'] else 'Every run'}`")
                if j["webhook_url"]:
                    col_det3.write(f"**Webhook:** `{j['webhook_url'][:35]}...`")

                # Action buttons
                col_act1, col_act2, col_act3 = st.columns([1, 1, 1])
                with col_act1:
                    if st.button("▶️ Run Now", key=f"run_{j['id']}"):
                        with st.spinner(f"Running job #{j['id']}..."):
                            res = scheduler.trigger_job_now(j["id"])
                            st.write(f"**Result:** {res['summary']}")
                            st.rerun()
                with col_act2:
                    toggle_label = "⏸️ Pause" if j["is_active"] else "▶️ Resume"
                    if st.button(toggle_label, key=f"toggle_{j['id']}"):
                        scheduler.toggle_job(j["id"])
                        st.rerun()
                with col_act3:
                    if st.button("🗑️ Delete", key=f"del_{j['id']}", type="secondary"):
                        scheduler.delete_job(j["id"])
                        st.rerun()

                # Execution History for this Job
                logs = scheduler.get_job_logs(j["id"], limit=5)
                if logs:
                    st.caption("Recent Execution Logs:")
                    log_df = pd.DataFrame([
                        {
                            "Run Time": l["run_at"],
                            "Status": l["status"],
                            "Summary": l["summary"],
                            "Diff Detected": "🔔 Yes" if l["diff_detected"] else "No"
                        }
                        for l in logs
                    ])
                    st.dataframe(log_df, use_container_width=True)
                else:
                    st.caption("No run logs yet for this job.")