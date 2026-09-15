# src/omniscrape/copilot/__init__.py
from .tools import (
    register_tool,
    get_all_tools,
    execute_tool,
    get_openai_tool_definitions,
    get_gemini_tool_declarations,
    load_plugins,
    REGISTERED_TOOLS
)
from .assistant import run_copilot_turn, COPILOT_SYSTEM_PROMPT

__all__ = [
    "register_tool",
    "get_all_tools",
    "execute_tool",
    "get_openai_tool_definitions",
    "get_gemini_tool_declarations",
    "load_plugins",
    "REGISTERED_TOOLS",
    "run_copilot_turn",
    "COPILOT_SYSTEM_PROMPT"
]
