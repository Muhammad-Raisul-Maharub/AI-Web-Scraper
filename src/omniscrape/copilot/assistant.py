# src/omniscrape/copilot/assistant.py - Conversational AI Web Scraping Copilot with Autonomous Tool Calling
import os
import json
import logging
from typing import List, Dict, Any, Optional, Callable
from dotenv import load_dotenv

try:
    from .tools import (
        get_all_tools,
        execute_tool,
        get_openai_tool_definitions,
        get_gemini_tool_declarations
    )
except (ImportError, ValueError):
    from tools import (
        get_all_tools,
        execute_tool,
        get_openai_tool_definitions,
        get_gemini_tool_declarations
    )

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

COPILOT_SYSTEM_PROMPT = """You are the OmniScrape AI Copilot, an autonomous web intelligence and scraping assistant.
You help users scrape web pages, extract structured information, inspect animation assets, capture screenshots, analyze HTML, schedule background monitors, inspect past execution runs, and track price changes.

You have access to tools that you can call when you need to interact with websites or check database/run logs:
- `scrape_page(url, mode)`: Scrapes and cleans web pages.
- `extract_structured_data(url, prompt, template)`: Extracts structured data into tables/JSON.
- `extract_web_animations(url)`: Inspects and extracts Lottie, Rive, SVGs, loops, and CSS keyframes.
- `schedule_scrape_job(name, url, interval_minutes, ...)`: Schedules autonomous background recurring scrape monitors.
- `list_scrape_jobs()`: Lists all scheduled jobs and next run timestamps.
- `take_screenshot(url)`: Captures full-page screenshots.
- `query_scrape_history(limit)`: Checks previous scrape logs.
- `list_runs(limit)`: Lists previous runs and artifacts in outputs folder.
- `get_run_output(run_id)`: Fetches full details and files for a specific run.
- `send_webhook_alert(webhook_url, title, content)`: Dispatches alerts to Discord/Slack.

Guidelines:
1. When asked to inspect, scrape, or extract data from a URL, ALWAYS invoke the appropriate tool instead of guessing.
2. Present extracted data clearly using Markdown formatting, bullet points, or tables.
3. Be helpful, concise, and professional.
"""


def _run_with_gemini(
    messages: List[Dict[str, str]],
    api_key: str,
    model_name: str = "gemini-2.5-flash",
    on_tool_call: Optional[Callable[[str, Dict[str, Any]], None]] = None
) -> Dict[str, Any]:
    """Execute conversational turn using Google Gemini with function calling."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    # Convert tools to Gemini format
    tool_declarations = []
    for t_name, t_meta in get_all_tools().items():
        tool_declarations.append(
            types.FunctionDeclaration(
                name=t_name,
                description=t_meta["description"],
                parameters=t_meta["parameters"]
            )
        )
    gemini_tools = [types.Tool(function_declarations=tool_declarations)]

    # Format chat history for Gemini
    contents = []
    for msg in messages:
        role = "user" if msg["role"] == "user" else "model"
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=msg["content"])]))

    tool_executions = []

    # Agent Loop (up to 4 tool calling iterations)
    for _ in range(4):
        response = client.models.generate_content(
            model=model_name or "gemini-2.5-flash",
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=COPILOT_SYSTEM_PROMPT,
                tools=gemini_tools,
                temperature=0.2
            )
        )

        candidate = response.candidates[0]
        model_part = candidate.content.parts[0] if candidate.content.parts else None

        # Check for function call
        if model_part and hasattr(model_part, "function_call") and model_part.function_call:
            fc = model_part.function_call
            tool_name = fc.name
            tool_args = dict(fc.args)

            if on_tool_call:
                on_tool_call(tool_name, tool_args)

            logging.info(f"Gemini calling tool '{tool_name}' with args: {tool_args}")
            try:
                tool_output = execute_tool(tool_name, tool_args)
            except Exception as e:
                tool_output = {"error": str(e)}

            tool_executions.append({"tool": tool_name, "args": tool_args, "output": tool_output})

            # Append model turn and tool response turn
            contents.append(candidate.content)
            contents.append(
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_function_response(
                            name=tool_name,
                            response={"result": tool_output}
                        )
                    ]
                )
            )
        else:
            final_text = response.text or ""
            return {
                "role": "assistant",
                "content": final_text,
                "tool_executions": tool_executions
            }

    return {
        "role": "assistant",
        "content": response.text or "Completed tool actions.",
        "tool_executions": tool_executions
    }


def _run_with_openai(
    messages: List[Dict[str, str]],
    api_key: str,
    model_name: str = "gpt-4o-mini",
    on_tool_call: Optional[Callable[[str, Dict[str, Any]], None]] = None
) -> Dict[str, Any]:
    """Execute conversational turn using OpenAI with tool calling."""
    from openai import OpenAI
    client = OpenAI(api_key=api_key)

    tools = get_openai_tool_definitions()
    formatted_msgs = [{"role": "system", "content": COPILOT_SYSTEM_PROMPT}] + messages
    tool_executions = []

    for _ in range(4):
        completion = client.chat.completions.create(
            model=model_name or "gpt-4o-mini",
            messages=formatted_msgs,
            tools=tools,
            temperature=0.2
        )

        response_msg = completion.choices[0].message

        if response_msg.tool_calls:
            formatted_msgs.append(response_msg)

            for tc in response_msg.tool_calls:
                t_name = tc.function.name
                t_args = json.loads(tc.function.arguments)

                if on_tool_call:
                    on_tool_call(t_name, t_args)

                logging.info(f"OpenAI calling tool '{t_name}' with args: {t_args}")
                try:
                    t_output = execute_tool(t_name, t_args)
                except Exception as e:
                    t_output = {"error": str(e)}

                tool_executions.append({"tool": t_name, "args": t_args, "output": t_output})

                formatted_msgs.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(t_output, default=str)
                })
        else:
            return {
                "role": "assistant",
                "content": response_msg.content or "",
                "tool_executions": tool_executions
            }

    return {
        "role": "assistant",
        "content": response_msg.content or "Completed tool actions.",
        "tool_executions": tool_executions
    }


def _run_with_ollama(
    messages: List[Dict[str, str]],
    model_name: str = "llama3.1",
    base_url: str = None,
    on_tool_call: Optional[Callable[[str, Dict[str, Any]], None]] = None
) -> Dict[str, Any]:
    """Execute conversational turn with local Ollama using ReAct pattern."""
    import requests

    ollama_url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")
    api_endpoint = f"{ollama_url}/api/chat"

    # Convert tools descriptions
    tools_desc = "\n".join([
        f"- {name}: {meta['description']} (Parameters: {list(meta['parameters']['properties'].keys())})"
        for name, meta in get_all_tools().items()
    ])

    react_prompt = f"""{COPILOT_SYSTEM_PROMPT}

AVAILABLE TOOLS:
{tools_desc}

To use a tool, respond strictly in this format:
ACTION: <tool_name>
ACTION_INPUT: <valid_json_arguments>

If no tool is needed, provide your direct response.
"""

    formatted_msgs = [{"role": "system", "content": react_prompt}] + messages
    tool_executions = []

    for _ in range(3):
        res = requests.post(
            api_endpoint,
            json={
                "model": model_name or "llama3.1",
                "messages": formatted_msgs,
                "stream": False,
                "options": {"temperature": 0.2}
            },
            timeout=120
        )
        res.raise_for_status()
        reply = res.json().get("message", {}).get("content", "").strip()

        # Check for ReAct action
        if "ACTION:" in reply and "ACTION_INPUT:" in reply:
            try:
                lines = reply.splitlines()
                action_name = ""
                action_input_str = ""

                for line in lines:
                    if line.startswith("ACTION:"):
                        action_name = line.replace("ACTION:", "").strip()
                    elif line.startswith("ACTION_INPUT:"):
                        action_input_str = line.replace("ACTION_INPUT:", "").strip()

                action_args = json.loads(action_input_str)

                if on_tool_call:
                    on_tool_call(action_name, action_args)

                tool_output = execute_tool(action_name, action_args)
                tool_executions.append({"tool": action_name, "args": action_args, "output": tool_output})

                formatted_msgs.append({"role": "assistant", "content": reply})
                formatted_msgs.append({
                    "role": "user",
                    "content": f"OBSERVATION:\n{json.dumps(tool_output, default=str)}"
                })
            except Exception as e:
                logging.error(f"Error parsing Ollama ReAct action: {e}")
                return {"role": "assistant", "content": reply, "tool_executions": tool_executions}
        else:
            return {"role": "assistant", "content": reply, "tool_executions": tool_executions}

    return {"role": "assistant", "content": reply, "tool_executions": tool_executions}


def run_copilot_turn(
    messages: List[Dict[str, str]],
    provider: str = "gemini",
    model_name: Optional[str] = None,
    api_key: Optional[str] = None,
    on_tool_call: Optional[Callable[[str, Dict[str, Any]], None]] = None
) -> Dict[str, Any]:
    """
    Unified entry point for the OmniScrape AI Copilot.
    """
    provider = provider.lower()

    if provider == "gemini":
        key = api_key or os.getenv("GEMINI_API_KEY")
        if not key:
            raise ValueError("Google Gemini API Key is required for Copilot mode.")
        return _run_with_gemini(
            messages=messages,
            api_key=key,
            model_name=model_name or "gemini-2.5-flash",
            on_tool_call=on_tool_call
        )

    elif provider == "openai":
        key = api_key or os.getenv("OPENAI_API_KEY")
        if not key:
            raise ValueError("OpenAI API Key is required for Copilot mode.")
        return _run_with_openai(
            messages=messages,
            api_key=key,
            model_name=model_name or "gpt-4o-mini",
            on_tool_call=on_tool_call
        )

    elif provider == "ollama":
        return _run_with_ollama(
            messages=messages,
            model_name=model_name or "llama3.1",
            on_tool_call=on_tool_call
        )

    else:
        raise ValueError(f"Unsupported provider: {provider}")
