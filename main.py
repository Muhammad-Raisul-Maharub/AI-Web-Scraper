# main.py - Comprehensive AI Web Scraper Dashboard (With AI Copilot & MCP Tools)
import os
import json
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from scrape import (
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
from parse import extract_with_ai, extract_with_vision
from schemas import EXTRACTION_TEMPLATES, create_dynamic_model
from db import (
    save_scrape,
    save_extraction,
    get_recent_scrapes,
    get_recent_extractions,
    detect_price_changes
)
from webhook import send_webhook
from tools import get_all_tools
from assistant import run_copilot_turn

load_dotenv()

# Page Setup
st.set_page_config(
    page_title="AI Web Scraper Pro",
    page_icon="🕷️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom UI Styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.3rem;
        font-weight: 700;
        margin-bottom: 0.2rem;
        background: linear-gradient(90deg, #3b82f6, #8b5cf6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .sub-header {
        font-size: 1rem;
        color: #94a3b8;
        margin-bottom: 1.5rem;
    }
    .schema-badge {
        display: inline-block;
        background-color: #1e293b;
        color: #38bdf8;
        border: 1px solid #0284c7;
        border-radius: 4px;
        padding: 2px 8px;
        margin: 2px;
        font-size: 0.85rem;
    }
    .tool-badge {
        display: inline-block;
        background-color: #064e3b;
        color: #34d399;
        border: 1px solid #059669;
        border-radius: 4px;
        padding: 2px 8px;
        margin: 2px;
        font-size: 0.82rem;
    }
</style>
""", unsafe_allow_html=True)

# Initialize Session States
if "scraped_dom" not in st.session_state:
    st.session_state.scraped_dom = None
if "scraped_raw_html" not in st.session_state:
    st.session_state.scraped_raw_html = ""
if "scraped_url" not in st.session_state:
    st.session_state.scraped_url = ""
if "crawled_results" not in st.session_state:
    st.session_state.crawled_results = []
if "extracted_data" not in st.session_state:
    st.session_state.extracted_data = None
if "current_screenshot" not in st.session_state:
    st.session_state.current_screenshot = None
if "detected_price_changes" not in st.session_state:
    st.session_state.detected_price_changes = []
if "scraped_animations" not in st.session_state:
    st.session_state.scraped_animations = None
if "animation_zip_bytes" not in st.session_state:
    st.session_state.animation_zip_bytes = None
if "copilot_messages" not in st.session_state:
    st.session_state.copilot_messages = [
        {
            "role": "assistant",
            "content": "👋 Hello! I am your **AI Scraping Copilot**. Ask me to scrape any webpage, extract structured data into tables, take full-page screenshots, or inspect price tracking history!"
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
    "ai-web-scraper": {
      "command": "python",
      "args": ["mcp_server.py"]
    }
  }
}""", language="json")

# Main App Header
st.markdown('<div class="main-header">🕷️ AI Web Scraper Pro</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-header">Multi-provider web scraping, Pydantic schemas, MCP server tools, and an autonomous AI Copilot.</div>',
    unsafe_allow_html=True
)

tab_copilot, tab1, tab2, tab3, tab4 = st.tabs([
    "💬 AI Assistant Copilot",
    "🔍 Scrape & Extract",
    "🌐 Crawl & Pagination",
    "⚡ Quick Keyword Search",
    "📊 History & Price Tracker"
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
                        st.markdown(f"**Tool:** `{te['tool']}`")
                        st.json(te.get("args", {}))
                        st.caption("Result Summary:")
                        st.code(str(te.get("output", ""))[:400] + "...")

    # Starter prompts if history is minimal
    if len(st.session_state.copilot_messages) <= 1:
        st.markdown("**Try a quick prompt:**")
        col_s1, col_s2, col_s3 = st.columns(3)
        with col_s1:
            if st.button("Quotes Authors & Tags"):
                st.session_state.copilot_input = "Scrape https://quotes.toscrape.com and list the top 3 quotes and their authors."
        with col_s2:
            if st.button("Check Price History"):
                st.session_state.copilot_input = "Query the scrape history and check if any price shifts were recorded."
        with col_s3:
            if st.button("Capture Books Screenshot"):
                st.session_state.copilot_input = "Take a screenshot of https://books.toscrape.com and tell me what the page looks like."

    # Chat Input Box
    user_query = st.chat_input("Ask the copilot to scrape, extract, or analyze...")
    if "copilot_input" in st.session_state and st.session_state.copilot_input:
        user_query = st.session_state.copilot_input
        st.session_state.copilot_input = None

    if user_query:
        # Append User Message
        st.session_state.copilot_messages.append({"role": "user", "content": user_query})
        with st.chat_message("user"):
            st.markdown(user_query)

        # Assistant Execution
        with st.chat_message("assistant"):
            provider_key = {
                "Google Gemini": "gemini",
                "Local Ollama": "ollama",
                "OpenAI": "openai"
            }[ai_provider]

            status_placeholder = st.status("🧠 Copilot reasoning...", expanded=True)
            tool_call_log = []

            def handle_tool_call(tool_name, tool_args):
                status_placeholder.write(f"⚡ **Executing tool:** `{tool_name}`")
                tool_call_log.append({"tool": tool_name, "args": tool_args})

            try:
                # Format messages for assistant
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
                    st.session_state.current_screenshot = img_path
                    st.success("Screenshot captured!")
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
            with st.status(f"Fetching content from {target_url}...", expanded=True) as status:
                try:
                    st.write(f"Connecting using **{scraper_mode}** engine...")
                    raw_html = scrape_website(target_url, mode=scraper_mode, timeout=timeout)

                    if "Animations" in scrape_target_type:
                        st.write("Inspecting and extracting animation & motion assets...")
                        anim_assets = extract_animation_assets(raw_html, base_url=target_url)
                        st.write("Packaging discovered assets into ZIP archive...")
                        zip_bytes = bundle_animations_zip(anim_assets, base_url=target_url)

                        st.session_state.scraped_animations = anim_assets
                        st.session_state.animation_zip_bytes = zip_bytes
                        st.session_state.scraped_dom = None
                        st.session_state.scraped_url = target_url
                        status.update(label=f"Extracted {anim_assets['total_assets_count']} animation assets!", state="complete")
                    else:
                        st.write("Extracting and cleaning DOM...")
                        body = extract_body_content(raw_html)
                        cleaned = clean_body_content(body)

                        # Save to SQLite database
                        scrape_id = save_scrape(target_url, scraper_mode, raw_html, cleaned)

                        st.session_state.scraped_dom = cleaned
                        st.session_state.scraped_raw_html = raw_html
                        st.session_state.scraped_url = target_url
                        st.session_state.scraped_animations = None
                        st.session_state.animation_zip_bytes = None
                        st.session_state.extracted_data = None
                        st.session_state.detected_price_changes = []
                        status.update(label=f"Scraping completed & saved (ID: #{scrape_id})!", state="complete")
                except Exception as e:
                    status.update(label=f"Failed to scrape: {e}", state="error")
                    st.error(f"Error scraping website: {e}")

    # Display Scraped Animation Assets if available
    if st.session_state.scraped_animations:
        anim = st.session_state.scraped_animations
        st.markdown("---")

        col_hdr, col_dl = st.columns([3, 1])
        with col_hdr:
            st.markdown(f"### 🎬 Discovered Animation Assets ({anim['total_assets_count']})")
            st.caption(f"Target: `{st.session_state.scraped_url}`")
        with col_dl:
            if st.session_state.animation_zip_bytes:
                st.download_button(
                    "📥 Download All (.ZIP)",
                    data=st.session_state.animation_zip_bytes,
                    file_name="animation_assets.zip",
                    mime="application/zip",
                    use_container_width=True,
                    type="primary"
                )

        col_a1, col_a2, col_a3, col_a4, col_a5 = st.columns(5)
        col_a1.metric("Lottie & Rive", f"{len(anim['lottie_files']) + len(anim['rive_files'])}")
        col_a2.metric("Animated SVGs", f"{len(anim['svg_animations'])}")
        col_a3.metric("Motion Media", f"{len(anim['motion_media'])}")
        col_a4.metric("JS Libs", f"{len(anim['animation_libraries'])}")
        col_a5.metric("Keyframes", f"{len(anim['css_keyframes'])}")

        anim_tab1, anim_tab2, anim_tab3, anim_tab4, anim_tab5, anim_tab6 = st.tabs([
            f"🎭 Lottie & Rive ({len(anim['lottie_files']) + len(anim['rive_files'])})",
            f"🌀 SVGs ({len(anim['svg_animations'])})",
            f"🎞️ Media ({len(anim['motion_media'])})",
            f"⚡ JS Libraries ({len(anim['animation_libraries'])})",
            f"🎨 Keyframes ({len(anim['css_keyframes'])})",
            "📋 Manifest JSON"
        ])

        with anim_tab1:
            if not anim['lottie_files'] and not anim['rive_files']:
                st.info("No Lottie or Rive files detected on this page.")
            else:
                for idx, lf in enumerate(anim['lottie_files']):
                    with st.expander(f"Lottie #{idx + 1}: [{lf['type']}] {lf.get('url', 'inline')[:60]}", expanded=True):
                        st.write(f"**Type:** `{lf['type']}`")
                        if lf.get('url') and lf['url'].startswith('http'):
                            st.markdown(f"🔗 [Direct URL]({lf['url']})")
                        if "preview" in lf:
                            st.caption("Inline Data Preview:")
                            st.code(lf['preview'], language="json")
                for idx, rf in enumerate(anim['rive_files']):
                    with st.expander(f"Rive #{idx + 1}: {rf['url']}", expanded=True):
                        st.write(f"**Type:** `{rf['type']}`")
                        st.markdown(f"🔗 [Direct Rive Asset]({rf['url']})")

        with anim_tab2:
            if not anim['svg_animations']:
                st.info("No animated SVG elements or standalone SVGs detected.")
            else:
                for idx, svg in enumerate(anim['svg_animations']):
                    if svg.get("type") == "inline-animated-svg":
                        with st.expander(f"Inline SVG #{idx + 1} (SMIL/CSS animated)", expanded=True):
                            st.caption("Live Render:")
                            st.markdown(f"<div style='background:#181824;padding:15px;border-radius:8px;text-align:center;'>{svg['html']}</div>", unsafe_allow_html=True)
                            st.code(svg['html'][:500] + ("..." if len(svg['html']) > 500 else ""), language="xml")
                    else:
                        st.markdown(f"- 📄 **SVG File:** [{svg['url']}]({svg['url']})")

        with anim_tab3:
            if not anim['motion_media']:
                st.info("No GIF or video loops detected.")
            else:
                cols = st.columns(min(3, len(anim['motion_media'])) or 1)
                for idx, m in enumerate(anim['motion_media']):
                    with cols[idx % len(cols)]:
                        st.caption(f"{m['type'].upper()} #{idx + 1}")
                        if m['type'] == 'gif':
                            st.image(m['url'], use_container_width=True)
                        elif m['type'] == 'video-loop':
                            st.video(m['url'])
                        st.caption(m['url'])

        with anim_tab4:
            if not anim['animation_libraries']:
                st.info("No common animation JavaScript libraries detected.")
            else:
                st.write("Identified Animation Scripts & Engines:")
                for lib in anim['animation_libraries']:
                    st.markdown(f"- ⚡ **{lib['library'].upper()}**: `{lib['url']}`")

        with anim_tab5:
            if not anim['css_keyframes']:
                st.info("No CSS @keyframes rules discovered.")
            else:
                for idx, kf in enumerate(anim['css_keyframes']):
                    with st.expander(f"@keyframes {kf['name']}", expanded=False):
                        st.code(kf['css'], language="css")

        with anim_tab6:
            st.json(anim)

    # Display Scraped Content Details if available
    if st.session_state.scraped_dom:
        dom_text = st.session_state.scraped_dom
        est_tokens = len(dom_text) // 4

        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        col_m1.metric("Characters", f"{len(dom_text):,}")
        col_m2.metric("Est. Tokens", f"~{est_tokens:,}")
        col_m3.metric("Lines of Text", f"{len(dom_text.splitlines()):,}")
        col_m4.metric("Active URL", st.session_state.scraped_url[:25] + "...")

        with st.expander("📄 View Cleaned DOM Text"):
            st.text_area("Cleaned DOM", dom_text, height=220, disabled=True)

        st.markdown("---")
        st.subheader("🤖 AI Data Extraction")

        # Vision Mode Toggle
        col_t1, col_t2 = st.columns([2, 1])
        with col_t1:
            template_options = ["✨ Free-Form Prompt (No Schema)"] + list(EXTRACTION_TEMPLATES.keys()) + ["🛠️ Custom Schema Builder"]
            selected_template = st.selectbox("Select Extraction Schema Template", options=template_options, index=0)
        with col_t2:
            use_vision_mode = st.checkbox("👁️ Multimodal Vision Mode", value=False, help="Uses Gemini Vision on the rendered screenshot instead of text DOM.")

        schema_class = None
        default_prompt = ""

        if selected_template in EXTRACTION_TEMPLATES:
            t_info = EXTRACTION_TEMPLATES[selected_template]
            schema_class = t_info["model"]
            default_prompt = t_info["default_prompt"]
            st.caption(f"ℹ️ {t_info['description']}")
            fields_html = " ".join([f'<span class="schema-badge">{f}</span>' for f in schema_class.model_fields.keys()])
            st.markdown(f"**Target Fields:** {fields_html}", unsafe_allow_html=True)

        elif selected_template == "🛠️ Custom Schema Builder":
            custom_fields_input = st.text_input("Enter field names (comma-separated)", placeholder="product_name, price, rating, stock")
            if custom_fields_input.strip():
                fields_list = [f.strip() for f in custom_fields_input.split(",") if f.strip()]
                schema_class = create_dynamic_model(fields_list)
                fields_html = " ".join([f'<span class="schema-badge">{f}</span>' for f in schema_class.model_fields.keys()])
                st.markdown(f"**Dynamic Schema Fields:** {fields_html}", unsafe_allow_html=True)
                default_prompt = f"Extract all items with: {', '.join(fields_list)}."

        col_p1, col_p2 = st.columns([3, 1])
        with col_p1:
            parse_prompt = st.text_area(
                "Extraction Instructions",
                value=default_prompt,
                placeholder="Describe what data to extract...",
                height=90
            )
        with col_p2:
            if schema_class:
                st.info("📌 Enforcing strict schema output.")
                fmt_code = "json"
            else:
                output_format = st.radio("Output Format", ["Structured Table / JSON", "Markdown Summary"])
                fmt_code = "json" if "JSON" in output_format else "markdown"

            extract_clicked = st.button("✨ Extract with AI", use_container_width=True, type="primary")

        if extract_clicked:
            if not parse_prompt.strip():
                st.warning("Please provide a prompt describing what to extract.")
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
                                api_key=api_key,
                                model_name=model_name or "gemini-2.5-flash",
                                schema_class=schema_class
                            )
                        # Text DOM Extraction Mode
                        else:
                            result = extract_with_ai(
                                dom_content=dom_text,
                                parse_description=parse_prompt,
                                provider=provider_key,
                                model_name=model_name,
                                api_key=api_key,
                                output_format=fmt_code,
                                schema_class=schema_class
                            )

                        # Save extraction to database
                        save_extraction(None, st.session_state.scraped_url, selected_template, parse_prompt, result)

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

                with st.spinner("Crawling pages..."):
                    results = dive_deep(crawl_url, max_pages=max_pages, mode=scraper_mode, progress_callback=crawl_progress)
                    st.session_state.crawled_results = results
                    p_bar.empty()
                    status_text.empty()

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
                with st.spinner("Auto-scrolling page..."):
                    html = scrape_with_infinite_scroll(scroll_url, max_scrolls=max_scrolls, timeout=timeout)
                    cleaned = clean_body_content(extract_body_content(html))
                    st.session_state.scraped_dom = cleaned
                    st.session_state.scraped_url = scroll_url
                    st.success(f"Scroll finished! Extracted {len(cleaned):,} characters of feed content.")

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
                with st.spinner("Navigating across pages..."):
                    pages = scrape_with_pagination(pag_url, next_button_css=next_css, max_pages=pag_limit, timeout=timeout)
                    st.session_state.crawled_results = pages
                    st.success(f"Successfully scraped {len(pages)} paginated pages!")

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
    st.write("Persistent database logs of previous scrapes and detected price shifts.")

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