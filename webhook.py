# webhook.py - Webhook Dispatcher for Discord, Slack, and Generic Endpoints
import requests
import json
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def send_webhook(webhook_url: str, title: str, content: str | list | dict) -> dict:
    """
    Send formatted payload to Discord, Slack, or custom webhook endpoints.
    """
    if not webhook_url or not webhook_url.startswith("http"):
        raise ValueError("Invalid webhook URL provided.")

    headers = {"Content-Type": "application/json"}

    # Discord Webhook formatting
    if "discord.com/api/webhooks" in webhook_url:
        description_text = content if isinstance(content, str) else json.dumps(content, indent=2)[:1800]
        payload = {
            "embeds": [
                {
                    "title": f"🕷️ {title}",
                    "description": f"```json\n{description_text}\n```" if isinstance(content, (list, dict)) else description_text,
                    "color": 3866870  # Blue
                }
            ]
        }

    # Slack Webhook formatting
    elif "hooks.slack.com" in webhook_url:
        formatted_text = content if isinstance(content, str) else json.dumps(content, indent=2)
        payload = {
            "text": f"*{title}*\n```{formatted_text[:2500]}```"
        }

    # Generic JSON Webhook
    else:
        payload = {
            "title": title,
            "data": content
        }

    response = requests.post(webhook_url, json=payload, headers=headers, timeout=15)
    response.raise_for_status()
    return {"status": "success", "status_code": response.status_code}
