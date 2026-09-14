# 🕷️ AI Web Scraper Pro

An intelligent, multi-provider web scraping and structured data extraction platform built with **Python**, **Streamlit**, **FastAPI**, **Selenium**, and **Generative AI** (Google Gemini, OpenAI, and local Ollama), featuring an **Autonomous AI Copilot** and an official **Model Context Protocol (MCP) Server**.

---

## 🌟 Complete Feature Matrix

| Feature | Description |
| :--- | :--- |
| **🕒 Automated Scheduler & Monitor** | Background daemon thread powered by SQLite that executes recurring scrapes (15m, 1h, 6h, 12h, 24h, custom), detects price/content diffs, and fires webhook alerts. |
| **🎬 Animation & Motion Asset Extraction** | Detects, extracts, and bundles Lottie JSON, Rive (`.riv`), animated SVGs, GIF/WebM loops, animation JS libraries (GSAP, Three.js), and CSS `@keyframes` with one-click ZIP download. |
| **🎯 Scraping Target Type Selector** | Switch between Cleaned Text / DOM (for AI analysis) and Animation Assets in the UI or programmatically. |
| **💬 Autonomous AI Copilot** | Interactive conversational agent in Streamlit with multi-turn memory and autonomous tool calling across Gemini, OpenAI, and Ollama. |
| **🔌 Model Context Protocol (MCP) Server** | Run `mcp_server.py` to expose all scraping tools over stdio to Claude Desktop, Cursor, Antigravity, and other MCP clients. |
| **🧩 Extensible Tool & Plugin System** | Drop any Python file with `@register_tool` into `plugins/` for instant auto-discovery, plus `mcp_config.json` for external MCP servers. |
| **⚡ Hybrid Scraping Engine** | Fast HTTP (static sites), Headless Chrome (dynamic JavaScript), or Bright Data Proxy (anti-bot bypass). |
| **📐 Pydantic Schema Templates** | Built-in templates for E-Commerce, Jobs, Real Estate, News, and Quotes, plus a Dynamic Schema Builder. |
| **👁️ Multimodal Vision Extraction** | Captures full-page screenshots via Selenium and extracts data visually with Google Gemini Vision. |
| **📜 Smart Pagination & Infinite Scroll** | Automatically scrolls dynamic feeds or clicks through pagination buttons (`Next >`). |
| **🚀 Headless FastAPI REST API** | Full programmatic backend (`api.py`) for integration into external pipelines and services. |
| **💻 CLI Automation Tool** | Command-line interface (`cli.py`) for terminal workflows and batch scripts. |
| **📈 Price Tracking & Change Detection** | Persistent SQLite database (`db.py`) that logs scrape history and flags price drops or increases. |
| **🔔 Webhook Dispatcher** | Automatically dispatches structured results to Discord, Slack, Zapier, or custom webhook URLs. |
| **🧪 Automated Unit & Integration Tests** | Test suite in `tests/test_scraper.py` testing DOM cleaners, animation extraction, ZIP bundlers, and API endpoints. |
| **📓 Interactive Jupyter Lab** | `demo_and_evaluation.ipynb` laboratory for benchmarking DOM compression and testing prompts. |

---

## 🛠️ Technology Stack

- **Frontend**: Streamlit
- **AI Agent & Copilot**: Google GenAI SDK (Function Calling), OpenAI Tool Calling, Ollama ReAct
- **Protocol & Extensibility**: Model Context Protocol (MCP SDK 2.x), Custom Tool Registry
- **Browser Automation**: Selenium, WebDriver Manager
- **API Backend**: FastAPI, Uvicorn
- **DOM Parsing & Cleaning**: BeautifulSoup4, lxml
- **Data & Storage**: Pydantic v2, Pandas, SQLite3, Matplotlib, Pillow

---

## 🚀 Quick Start Guide

### 1. Clone & Setup Virtual Environment
```bash
git clone https://github.com/Muhammad-Raisul-Maharub/AI-Web-Scraper.git
cd AI-Web-Scraper

# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Environment Configuration (Optional)
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
| Variable | Description |
| :--- | :--- |
| `GEMINI_API_KEY` | Google Gemini API key (optional, can also be entered in the UI) |
| `OPENAI_API_KEY` | OpenAI API key (optional, can also be entered in the UI) |
| `OLLAMA_BASE_URL` | Local Ollama host (default: `http://localhost:11434`) |
| `SBR_WEBDRIVER` | Optional Bright Data Scraping Browser remote proxy URL |

---

## 🐳 Running with Docker (Recommended)

If you have Docker installed, launch both the **Streamlit Web Dashboard** and the **FastAPI Backend** with a single command:

```bash
docker compose up --build
```

* 🌐 **Streamlit Web Dashboard:** [http://localhost:8501](http://localhost:8501)
* 🚀 **FastAPI Interactive Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🖥️ Running Locally (Without Docker)

### 1. Interactive Streamlit Dashboard (With AI Copilot)
```powershell
streamlit run main.py
```
* **Tab 1 (💬 AI Assistant Copilot):** Converse naturally with the AI Copilot. It plans and executes scraping tools autonomously to answer questions, extract tables, or capture screenshots.
* **Tab 2 (🔍 Scrape & Extract):** Single-page scraping, animation extraction, screenshot capture, Pydantic schema templates, Multimodal Vision mode, and CSV/JSON/ZIP downloads.
* **Tab 3 (🌐 Crawl & Pagination):** Domain-restricted crawling, infinite scroll feeding, and multi-page pagination.
* **Tab 4 (⚡ Keyword Search):** Instant zero-LLM keyword filter.
* **Tab 5 (📊 History & Price Tracker):** Database history and detected price change alerts.
* **Tab 6 (🕒 Automated Scheduler & Monitor):** Configure background recurring scrape jobs, custom minute/preset intervals, price diff detection, and webhook alerts.

---

### 2. Model Context Protocol (MCP) Server

Connect your external AI assistant (Claude Desktop, Cursor, Antigravity) to use AI-Web-Scraper tools natively:

```powershell
python mcp_server.py
```

#### Claude Desktop Configuration (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "ai-web-scraper": {
      "command": "python",
      "args": ["mcp_server.py"],
      "cwd": "C:\\path\\to\\AI-Web-Scraper"
    }
  }
}
```

**Exposed MCP Tools:**
- `scrape_page`: Fetches and cleans any URL.
- `extract_structured_data`: Extracts Pydantic records into JSON.
- `extract_web_animations`: Extracts Lottie, Rive, SVGs, GIFs, JS libs, and CSS keyframes.
- `schedule_scrape_job`: Schedules recurring background scraping tasks with interval & alerts.
- `list_scrape_jobs`: Lists all active/paused monitor jobs and next execution timestamps.
- `take_screenshot`: Captures high-res full-page screenshots.
- `query_scrape_history`: Retrieves previous scrape logs.
- `send_webhook_alert`: Dispatches alerts to Discord or Slack.

---

### 3. Adding Custom Tools & Plugins

Create any Python file in the `plugins/` directory and use the `@register_tool` decorator:

```python
# plugins/my_custom_tool.py
from tools import register_tool

@register_tool(
    name="my_custom_tool",
    description="Explain what this tool does.",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search term."}
        },
        "required": ["query"]
    }
)
def my_custom_tool(query: str) -> dict:
    return {"result": f"Processed {query}"}
```
The AI Copilot and MCP Server will automatically discover and load it!

---

### 4. Headless FastAPI REST API
```powershell
uvicorn api:app --reload --port 8000
```
Interactive API Docs: [http://localhost:8000/docs](http://localhost:8000/docs)

---

### 5. CLI Automation Tool
```powershell
# Extract e-commerce products into JSON
python cli.py --url "https://books.toscrape.com" --template ecommerce --output books.json

# Extract animation assets and bundle into a ZIP archive
python cli.py --url "https://example.com" --animations --download-zip animations.zip

# Capture screenshot and extract with custom prompt
python cli.py --url "https://quotes.toscrape.com" --screenshot quote.png --prompt "Extract all quotes and authors" --format json
```

---

## 📁 Repository Structure

```
├── .gitignore                   # Standard ignore rules (venv, secrets, caches)
├── .env.example                 # Configuration template
├── api.py                       # FastAPI REST API
├── assistant.py                 # Autonomous AI Copilot engine with tool calling
├── cli.py                       # Command-line interface automation tool
├── db.py                        # SQLite storage, history & price change tracking
├── demo_and_evaluation.ipynb    # Interactive evaluation & visualization notebook
├── main.py                      # Modern Streamlit UI dashboard with Copilot tab
├── mcp_config.json              # MCP server and external tool configurations
├── mcp_server.py                # Official Model Context Protocol (MCP) Server
├── parse.py                     # Multi-provider AI extraction engine (Gemini, Ollama, OpenAI, Vision)
├── plugins/                     # Extensible custom tools directory
│   └── social_extractor.py      # Example plugin: social media link extractor
├── requirements.txt             # Pinned project dependencies
├── scheduler.py                # Background scraping daemon & autonomous monitor
├── schemas.py                   # Pydantic extraction models & dynamic schema generator
├── scrape.py                    # Hybrid scraping engine, screenshot capture & pagination
├── tests/                       # Automated test suite (unittest compatible)
│   └── test_scraper.py          # Unit & integration tests for scraping, animations, scheduler
├── tools.py                     # Extensible Tool Registry & schema generators
├── webhook.py                   # Discord, Slack & generic webhook dispatcher
└── README.md                    # Project documentation
```

---

## 👤 Author
**Muhammad Raisul Maharub**
- GitHub: [@Muhammad-Raisul-Maharub](https://github.com/Muhammad-Raisul-Maharub)
