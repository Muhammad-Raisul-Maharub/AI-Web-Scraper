# Project Architecture & Run Output Standards

## Directory Hygiene & Structure
1. **Clean Root Invariant**: The project root contains strictly the primary entrypoints (`main.py`, `api.py`, `cli.py`, `mcp_server.py`), project configuration files (`pyproject.toml`, `requirements.txt`, `pyrightconfig.json`), and top-level directory roots. No intermediate shims, temporary audit scripts, or clutter are allowed in the root.
2. **Package Separation**: All core library modules, subpackages, engines, copilot logic, and storage implementations reside cleanly inside `src/omniscrape/`.
3. **IDE & Type Checking**: Always maintain `.vscode/settings.json` and `pyrightconfig.json` pointing to the workspace `venv/` and configuring `extraPaths: ["src"]` to ensure 0-error IDE diagnostics across all packages.
4. **Database Storage**: SQLite database files reside in `data/` (e.g. `data/scrapes.db`), with automatic path creation and graceful fallback.

## Run Outputs Management
1. **Isolated Run Folders**: Every execution from the Streamlit UI, CLI, API, or background scheduler must register with `RunOutputManager` to create an isolated run folder under `outputs/<run_id>/`.
2. **Standard Manifest**: Each run folder must include `run_meta.json` with execution timestamp, target URL, duration, status, task type, and a manifest of generated files.
3. **Inspection Support**: Any new scraping, animation extraction, or AI parsing feature must integrate with the **Outputs & Runs Explorer** in Streamlit and the CLI `--list-runs` viewer.
