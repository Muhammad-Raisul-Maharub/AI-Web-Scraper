# 🌐 OmniScrape AI v2.2

An autonomous, multi-modal web scraping, animation asset extraction, and background monitoring platform built with **Python**, **Streamlit**, **FastAPI**, **Selenium**, and **Generative AI** (Google Gemini, OpenAI, and local Ollama), featuring an **Autonomous AI Copilot**, an official **Model Context Protocol (MCP) Server**, a clean **modular engine (`src/omniscrape`)**, and a dedicated **isolated Run Outputs system (`outputs/runs/`)**.

---

## 🌟 Complete Feature Matrix

| Feature | Description |
| :--- | :--- |
| **📁 Isolated Run Outputs System** | Every execution (UI, CLI, API, background scheduler) saves to an isolated timestamped directory (`outputs/runs/YYYYMMDD_HHMMSS_<slug>/`) with `metadata.json`, cleaned text, structured JSON/CSV, screenshots, and animation bundles. |
| **🗂️ Interactive Outputs & Runs Explorer** | Built-in explorer in Streamlit (Tab 5), CLI (`--list-runs`, `--view-run`), and REST API (`/api/runs`) to inspect, preview, and download run bundles as ZIP archives. |
| **🕒 Automated Scheduler & Monitor** | Background daemon thread powered by SQLite that executes recurring scrapes (15m, 1h, 6h, 12h, 24h, custom), detects price/content diffs, and fires webhook alerts. |
| **🎬 Animation & Motion Asset Extraction** | Detects, extracts, and bundles Lottie JSON, Rive (`.riv`), animated SVGs, GIF/WebM loops, animation JS libraries (GSAP, Three.js), and CSS `@keyframes` with one-click ZIP download. |
| **🎯 Scraping Target Type Selector** | Switch between Cleaned Text / DOM (for AI analysis) and Animation Assets in the UI or programmatically. |
| **💬 Autonomous AI Copilot** | Interactive conversational agent in Streamlit with multi-turn memory and autonomous tool calling across Gemini, OpenAI, and Ollama. |
| **🔌 Model Context Protocol (MCP) Server** | Run `mcp_server.py` to expose all scraping, extraction, scheduling, and run explorer tools over stdio to Claude Desktop, Cursor, Antigravity, and other MCP clients. |
| **🧩 Extensible Tool & Plugin System** | Drop any Python file with `@register_tool` into `plugins/` for instant auto-discovery, plus `mcp_config.json` for external MCP servers. |
| **⚡ Hybrid Scraping Engine** | Fast HTTP (static sites), Headless Chrome (dynamic JavaScript), or Bright Data Proxy (anti-bot bypass). |
| **📐 Pydantic Schema Templates** | Built-in templates for E-Commerce, Jobs, Real Estate, News, and Quotes, plus a Dynamic Schema Builder. |
| **👁️ Multimodal Vision Extraction** | Captures full-page screenshots via Selenium and extracts data visually with Google Gemini Vision. |
| **📜 Smart Pagination & Infinite Scroll** | Automatically scrolls dynamic feeds or clicks through pagination buttons (`Next >`). |
| **🚀 Headless FastAPI REST API** | Full programmatic backend (`api.py`) for integration into external pipelines and services with OpenAPI documentation. |
| **💻 CLI Automation Tool** | Command-line interface (`cli.py` / `omniscrape`) for terminal workflows, automated scripts, and run output inspections. |
| **📈 Price Tracking & Change Detection** | Persistent SQLite database (`data/scraper.db`) that logs scrape history and flags price drops or increases. |
| **🔔 Webhook Dispatcher** | Automatically dispatches structured results to Discord, Slack, Zapier, or custom webhook URLs. |
| **🧪 Automated Unit & Integration Tests** | Test suite in `tests/test_scraper.py` testing DOM cleaners, animation extraction, ZIP bundlers, run outputs, scheduler, and API endpoints. |
| **📓 Interactive Jupyter Lab** | `demo_and_evaluation.ipynb` laboratory for benchmarking DOM compression and testing prompts. |

---

## 🛠️ Technology Stack

- **Architecture**: Modular Python package (`src/omniscrape`) with root backwards-compatibility entrypoints
- **Frontend**: Streamlit
- **AI Agent & Copilot**: Google GenAI SDK (Function Calling), OpenAI Tool Calling, Ollama ReAct
- **Protocol & Extensibility**: Model Context Protocol (MCP SDK 2.x), Custom Tool Registry
- **Browser Automation**: Selenium, WebDriver Manager
- **API Backend**: FastAPI, Uvicorn
- **DOM Parsing & Cleaning**: BeautifulSoup4, lxml
- **Data & Storage**: Pydantic v2, Pandas, SQLite3 (`data/`), Isolated Run Outputs (`outputs/runs/`), Matplotlib, Pillow

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

# Or install in editable development mode
pip install -e .
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
| `OMNISCRAPE_OUTPUTS_DIR` | Custom output directory (default: `outputs`) |
| `OMNISCRAPE_DATA_DIR` | Custom persistent data directory (default: `data`) |

---

## 🐳 Running with Docker (Recommended)

Launch both the **Streamlit Web Dashboard** and the **FastAPI Backend** with volume mounts for `data/`, `outputs/`, and `screenshots/`:

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
* **Tab 5 (📁 Outputs & Runs Explorer):** Interactive run explorer. View previous runs, preview tabular data, read extracted text, view screenshots, inspect files, and download full-run ZIP bundles.
* **Tab 6 (📊 History & Price Tracker):** Database history and detected price change alerts.
* **Tab 7 (🕒 Automated Scheduler & Monitor):** Configure background recurring scrape jobs, custom minute/preset intervals, price diff detection, and webhook alerts.

---

### 2. Model Context Protocol (MCP) Server

Connect your external AI assistant (Claude Desktop, Cursor, Antigravity) to use OmniScrape AI tools natively:

```powershell
python mcp_server.py
```

#### Claude Desktop Configuration (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "omniscrape-ai": {
      "command": "python",
      "args": ["mcp_server.py"],
      "cwd": "C:\\path\\to\\OmniScrape-AI"
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
- `list_runs`: Lists all saved run execution folders, file manifests, and statistics.
- `get_run_output`: Retrieves the detailed metadata and file inventory for a specific run ID.
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

**Key API Endpoints:**
- `POST /api/scrape`: Scrapes and cleans web page content.
- `POST /api/extract`: AI-powered structured extraction using Gemini, OpenAI, or Ollama.
- `POST /api/scrape/animations`: Detects motion assets and returns asset manifest + ZIP.
- `GET /api/jobs`: Lists all recurring monitor jobs.
- `POST /api/jobs`: Schedules a new background recurring monitor job.
- `PATCH /api/jobs/{id}/toggle`: Pauses or resumes a monitor job.
- `DELETE /api/jobs/{id}`: Deletes a monitor job.
- `GET /api/runs`: Lists all previous run execution folders and metadata.
- `GET /api/runs/{run_id}`: Retrieves complete file manifest and details for a run ID.
- `GET /api/runs/{run_id}/download`: Downloads a run directory as a full `.zip` bundle.
- `DELETE /api/runs/{run_id}`: Deletes a run folder and its artifacts.

---

### 5. CLI Automation Tool
```powershell
# Extract e-commerce products into JSON
python cli.py --url "https://books.toscrape.com" --template ecommerce --output books.json

# Extract animation assets and bundle into a ZIP archive
python cli.py --url "https://example.com" --animations --download-zip animations.zip

# Capture screenshot and extract with custom prompt
python cli.py --url "https://quotes.toscrape.com" --screenshot quote.png --prompt "Extract all quotes and authors" --format json

# List recent execution runs
python cli.py --list-runs

# View detailed inventory of a specific run
python cli.py --view-run 20260915_191136_quotes_toscrape_com
```

---

## 📁 Clean Repository Structure

```
├── .agents/                     # Antigravity agent rules and skill definitions
│   ├── rules/
│   │   └── project-standards.md # Project standards & run output invariant rules
│   └── skills/
│       └── web-animation-scraper/
├── .env.example                 # Configuration template
├── .gitignore                   # Standard ignore rules (venv, db, run outputs, caches)
├── Dockerfile                   # Multi-stage production container definition
├── LICENSE                      # MIT License
├── README.md                    # Project documentation
├── api.py                       # FastAPI REST API entrypoint (with /api/runs endpoints)
├── assistant.py                 # Autonomous AI Copilot re-export shim
├── cli.py                       # CLI automation entrypoint & run viewer
├── db.py                        # Database storage re-export shim
├── demo_and_evaluation.ipynb    # Interactive evaluation & visualization notebook
├── docker-compose.yml           # Multi-container service configuration
├── main.py                      # Modern Streamlit UI dashboard with Runs Explorer tab
├── mcp_config.json              # MCP server and external tool configurations
├── mcp_server.py                # Official Model Context Protocol (MCP) Server
├── outputs.py                   # Run output manager re-export shim
├── parse.py                     # Multi-provider AI extraction re-export shim
├── pyproject.toml               # Modern PEP 518/621 project configuration & packaging
├── requirements.txt             # Pinned project dependencies
├── scheduler.py                 # Background scraping daemon re-export shim
├── schemas.py                   # Pydantic extraction models re-export shim
├── scrape.py                    # Hybrid scraping engine re-export shim
├── tools.py                     # Extensible Tool Registry re-export shim
├── webhook.py                   # Webhook dispatcher re-export shim
│
├── data/                        # Persistent storage directory
│   ├── .gitkeep                 # Track directory in Git
│   └── scraper.db               # SQLite database for scrape history & jobs
│
├── outputs/                     # Run outputs directory
│   ├── .gitkeep                 # Track directory in Git
│   └── runs/                    # Dedicated isolated run folders
│       └── YYYYMMDD_HHMMSS_<slug>/
│           ├── metadata.json    # Complete run metadata manifest
│           ├── raw_page.html    # Raw HTML snapshot
│           ├── cleaned_dom.txt  # Cleaned readable text/DOM
│           ├── extracted_data.json # Structured JSON output
│           ├── extracted_data.csv  # Formatted tabular CSV
│           ├── screenshot.png   # Full-page screenshot
│           └── animations.zip   # Bundled motion assets
│
├── plugins/                     # Extensible custom tools directory
│   └── social_extractor.py      # Example plugin: social media link extractor
│
├── src/                         # Modular package root
│   └── omniscrape/
│       ├── __init__.py
│       ├── automation/          # Background scheduler & webhooks
│       │   ├── scheduler.py
│       │   └── webhook.py
│       ├── copilot/             # AI Copilot agent & tool registry
│       │   ├── assistant.py
│       │   └── tools.py
│       ├── engine/              # Core scraping & multi-LLM parsing
│       │   ├── parse.py
│       │   └── scrape.py
│       ├── models/              # Pydantic schemas & dynamic builder
│       │   └── schemas.py
│       └── storage/             # SQLite DB & isolated run output manager
│           ├── db.py
│           └── outputs.py
│
└── tests/                       # Automated test suite (unittest compatible)
    └── test_scraper.py          # Unit & integration tests for scraping, outputs, API
```

---

## 👤 Author
**Muhammad Raisul Maharub**
- GitHub: [@Muhammad-Raisul-Maharub](https://github.com/Muhammad-Raisul-Maharub)
