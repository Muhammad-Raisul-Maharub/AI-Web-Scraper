# Project Architecture & Run Output Standards

## Directory Hygiene
1. **No Root Clutter**: Do not leave one-off test scripts, static HTML/CSS prototypes, or temporary output dumps in the project root.
2. **Package Separation**: Core library modules reside under `src/omniscrape/`. Root scripts (`main.py`, `api.py`, `cli.py`, `mcp_server.py`) act as entrypoints and maintain re-export shims for backwards compatibility.
3. **Database Storage**: SQLite database files must reside in `data/` (e.g. `data/scraper.db`), with automatic creation and fallback.

## Run Outputs Management
1. **Isolated Run Folders**: Every execution from the Streamlit UI, CLI, API, or background scheduler must register with `RunOutputManager` to create an isolated run folder under `outputs/runs/YYYYMMDD_HHMMSS_<slug>/`.
2. **Standard Manifest**: Each run folder must include `metadata.json` with execution timestamp, target URL, duration, status, task type, and a manifest of generated files.
3. **Inspection Support**: Any new scraping or extraction feature must integrate with the **Outputs & Runs Explorer** in Streamlit and the CLI run viewer.
