# parse.py - Multi-Provider AI Content Extraction Engine with Pydantic Schemas
import os
import re
import json
import logging
from typing import Type, List, Dict, Any
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

PROMPT_MARKDOWN = """
You are an expert web data extractor. You are provided with the text content scraped from a webpage.
Webpage Content:
\"\"\"{dom_content}\"\"\"

Task:
Extract ONLY the information matching this request:
\"{parse_description}\"

Instructions:
1. Extract only data directly relevant to the request.
2. Format the output cleanly using Markdown (lists, headers, or bullet points).
3. Do not include conversational filler (e.g. "Sure, here is the information").
4. If no information matches the request, output: "No matching information found."
"""

PROMPT_JSON = """
You are a precise data extraction engine. You are provided with the text content scraped from a webpage.
Webpage Content:
\"\"\"{dom_content}\"\"\"

Task:
Extract the following information:
\"{parse_description}\"

Instructions:
1. Output strictly a valid JSON array of objects (e.g. [ {{"field1": "value1", "field2": "value2"}} ]).
2. Do not wrap in backticks or markdown, do not include any explanatory text before or after the JSON.
3. If no matching information is found, return an empty array: []
"""

PROMPT_SCHEMA = """
You are a precise data extraction engine. You are provided with the text content scraped from a webpage.
Webpage Content:
\"\"\"{dom_content}\"\"\"

Task:
Extract records matching this user request:
\"{parse_description}\"

The extracted items MUST strictly conform to the following JSON Schema:
{schema_json}

Instructions:
1. Output strictly a valid JSON array of objects where each object adheres to the schema above.
2. Do NOT wrap in backticks or markdown fences. Return ONLY the raw JSON string.
3. If no matching information is found, return an empty array: []
"""


def _clean_json_response(raw_text: str) -> list | dict:
    """Strip markdown fences and parse JSON safely."""
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned.strip())
    except json.JSONDecodeError:
        match = re.search(r"(\[.*\]|\{.*\})", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        return {"raw_output": raw_text}


def parse_with_gemini(
    dom_content: str,
    parse_description: str,
    api_key: str = None,
    model_name: str = "gemini-2.5-flash",
    output_format: str = "markdown",
    schema_class: Type[BaseModel] = None
) -> str | list | dict:
    """Extract information using Google Gemini API."""
    key = api_key or os.getenv("GEMINI_API_KEY")
    if not key:
        raise ValueError("Google Gemini API Key is missing. Please provide it in the UI or in your .env file.")

    from google import genai
    client = genai.Client(api_key=key)

    if schema_class:
        schema_json = json.dumps(schema_class.model_json_schema(), indent=2)
        prompt = PROMPT_SCHEMA.format(
            dom_content=dom_content,
            parse_description=parse_description,
            schema_json=schema_json
        )
        response = client.models.generate_content(
            model=model_name or "gemini-2.5-flash",
            contents=prompt,
        )
        parsed = _clean_json_response(response.text or "[]")
        return _validate_with_pydantic(parsed, schema_class)

    prompt_template = PROMPT_JSON if output_format == "json" else PROMPT_MARKDOWN
    prompt = prompt_template.format(dom_content=dom_content, parse_description=parse_description)

    response = client.models.generate_content(
        model=model_name or "gemini-2.5-flash",
        contents=prompt
    )
    result_text = response.text or ""

    if output_format == "json":
        return _clean_json_response(result_text)
    return result_text.strip()


def parse_with_openai(
    dom_content: str,
    parse_description: str,
    api_key: str = None,
    model_name: str = "gpt-4o-mini",
    output_format: str = "markdown",
    schema_class: Type[BaseModel] = None
) -> str | list | dict:
    """Extract information using OpenAI API."""
    key = api_key or os.getenv("OPENAI_API_KEY")
    if not key:
        raise ValueError("OpenAI API Key is missing. Please provide it in the UI or in your .env file.")

    from openai import OpenAI
    client = OpenAI(api_key=key)

    if schema_class:
        schema_json = json.dumps(schema_class.model_json_schema(), indent=2)
        prompt = PROMPT_SCHEMA.format(
            dom_content=dom_content,
            parse_description=parse_description,
            schema_json=schema_json
        )
    else:
        prompt_template = PROMPT_JSON if output_format == "json" else PROMPT_MARKDOWN
        prompt = prompt_template.format(dom_content=dom_content, parse_description=parse_description)

    completion = client.chat.completions.create(
        model=model_name or "gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a precise web data extraction specialist."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.1
    )
    result_text = completion.choices[0].message.content or ""

    if schema_class:
        parsed = _clean_json_response(result_text)
        return _validate_with_pydantic(parsed, schema_class)

    if output_format == "json":
        return _clean_json_response(result_text)
    return result_text.strip()


def parse_with_ollama(
    dom_chunks: list[str],
    parse_description: str,
    model_name: str = "llama3.1",
    base_url: str = None,
    output_format: str = "markdown",
    schema_class: Type[BaseModel] = None,
    progress_callback=None,
    stop_check=None
) -> str | list:
    """Extract information across DOM chunks using local Ollama model."""
    import requests

    ollama_url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")
    api_endpoint = f"{ollama_url}/api/generate"

    results = []
    schema_json = json.dumps(schema_class.model_json_schema(), indent=2) if schema_class else ""

    for i, chunk in enumerate(dom_chunks, start=1):
        if stop_check and stop_check():
            logging.info("Parsing stopped by user.")
            break

        if progress_callback:
            progress_callback(i, len(dom_chunks))

        if schema_class:
            prompt = PROMPT_SCHEMA.format(
                dom_content=chunk,
                parse_description=parse_description,
                schema_json=schema_json
            )
        else:
            prompt_template = PROMPT_JSON if output_format == "json" else PROMPT_MARKDOWN
            prompt = prompt_template.format(dom_content=chunk, parse_description=parse_description)

        try:
            res = requests.post(
                api_endpoint,
                json={
                    "model": model_name or "llama3.1",
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1}
                },
                timeout=120
            )
            res.raise_for_status()
            data = res.json()
            response_text = data.get("response", "").strip()

            if schema_class or output_format == "json":
                parsed = _clean_json_response(response_text)
                if isinstance(parsed, list):
                    results.extend(parsed)
                elif isinstance(parsed, dict) and "raw_output" not in parsed:
                    results.append(parsed)
            else:
                if response_text and "no matching information found" not in response_text.lower():
                    results.append(response_text)

        except requests.exceptions.ConnectionError:
            raise ConnectionError(
                f"Cannot connect to Ollama at {ollama_url}. Ensure the Ollama service is running (`ollama serve`)."
            )
        except Exception as e:
            logging.error(f"Error parsing chunk {i}: {e}")
            if not schema_class and output_format != "json":
                results.append(f"Error in batch {i}: {e}")

    if schema_class:
        return _validate_with_pydantic(results, schema_class)

    if output_format == "json":
        return results
    return "\n\n---\n\n".join(results) if results else "No matching information found."


def _validate_with_pydantic(raw_data: Any, schema_class: Type[BaseModel]) -> List[Dict[str, Any]]:
    """Validate and normalize raw JSON items through the Pydantic schema."""
    if not isinstance(raw_data, list):
        if isinstance(raw_data, dict) and "raw_output" not in raw_data:
            raw_data = [raw_data]
        else:
            return []

    validated_items = []
    for item in raw_data:
        if isinstance(item, dict):
            try:
                # Validate with model and convert to clean dict
                model_obj = schema_class.model_validate(item)
                validated_items.append(model_obj.model_dump())
            except Exception as e:
                # If strict validation fails on a single field, pass through non-empty keys
                logging.debug(f"Pydantic validation warning: {e}")
                validated_items.append(item)

    return validated_items


def extract_with_ai(
    dom_content: str,
    parse_description: str,
    provider: str = "ollama",
    model_name: str = "llama3.1",
    api_key: str = None,
    output_format: str = "markdown",
    schema_class: Type[BaseModel] = None,
    progress_callback=None,
    stop_check=None
):
    """
    Unified extraction dispatcher across all supported AI providers and schemas.
    """
    provider = provider.lower()

    if provider == "gemini":
        return parse_with_gemini(
            dom_content=dom_content,
            parse_description=parse_description,
            api_key=api_key,
            model_name=model_name or "gemini-2.5-flash",
            output_format=output_format,
            schema_class=schema_class
        )

    elif provider == "openai":
        return parse_with_openai(
            dom_content=dom_content,
            parse_description=parse_description,
            api_key=api_key,
            model_name=model_name or "gpt-4o-mini",
            output_format=output_format,
            schema_class=schema_class
        )

    elif provider == "ollama":
        from scrape import split_dom_content
        chunks = split_dom_content(dom_content, max_length=5000)
        return parse_with_ollama(
            dom_chunks=chunks,
            parse_description=parse_description,
            model_name=model_name or "llama3.1",
            output_format=output_format,
            schema_class=schema_class,
            progress_callback=progress_callback,
            stop_check=stop_check
        )

    else:
        raise ValueError(f"Unsupported provider: {provider}")


def extract_with_vision(
    image_path: str,
    parse_description: str,
    api_key: str = None,
    model_name: str = "gemini-2.5-flash",
    schema_class: Type[BaseModel] = None
) -> str | list | dict:
    """
    Extract structured or markdown content visually from a webpage screenshot using Gemini Vision.
    """
    key = api_key or os.getenv("GEMINI_API_KEY")
    if not key:
        raise ValueError("Google Gemini API Key is required for Multimodal Vision extraction.")

    from google import genai
    from PIL import Image

    client = genai.Client(api_key=key)
    image = Image.open(image_path)

    if schema_class:
        schema_json = json.dumps(schema_class.model_json_schema(), indent=2)
        prompt = (
            f"You are a visual web scraper analyzing a full-page website screenshot.\n"
            f"Task: {parse_description}\n\n"
            f"Extract all relevant items in the screenshot matching the following JSON Schema:\n{schema_json}\n\n"
            f"Return strictly a raw JSON array of objects without markdown formatting or code blocks."
        )
        response = client.models.generate_content(
            model=model_name or "gemini-2.5-flash",
            contents=[image, prompt]
        )
        parsed = _clean_json_response(response.text or "[]")
        return _validate_with_pydantic(parsed, schema_class)

    prompt = (
        f"You are a visual web scraper analyzing a full-page website screenshot.\n"
        f"Task: {parse_description}\n\n"
        f"Extract the requested data accurately based on what is visible in the rendered screenshot."
    )
    response = client.models.generate_content(
        model=model_name or "gemini-2.5-flash",
        contents=[image, prompt]
    )
    return response.text or ""

