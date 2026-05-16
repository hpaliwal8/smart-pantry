"""Bedrock service. Wraps Claude Sonnet 4.6 calls for Chef Charlie, recipe
generation, and recipe import.

The Chef Charlie response format is a structured block protocol. The system
prompt instructs the model to emit a JSON array of blocks; the parser falls
back to a single text block if the model deviates.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

import boto3
from botocore.exceptions import ClientError

from .. import config

log = logging.getLogger(__name__)

_client = boto3.client("bedrock-runtime", region_name=config.AWS_REGION)


class BedrockUnavailable(RuntimeError):
    """Raised when Bedrock is reachable but the model isn't usable (access/use-case form)."""


def invoke(
    messages: list[dict],
    *,
    system: str | None = None,
    max_tokens: int = 2048,
    temperature: float = 0.6,
) -> str:
    """Invoke Claude via Bedrock and return the assistant text.

    Raises BedrockUnavailable when the call fails for access/setup reasons —
    routes translate this into a 503 so the UI can show a friendly message.
    """
    body: dict[str, Any] = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": messages,
    }
    if system:
        body["system"] = system
    try:
        resp = _client.invoke_model(modelId=config.BEDROCK_MODEL_ID, body=json.dumps(body))
    except ClientError as e:
        msg = str(e)
        if "use case details" in msg or "ResourceNotFoundException" in msg or "AccessDenied" in msg:
            raise BedrockUnavailable(
                "Bedrock model not available yet. Submit the Anthropic use-case "
                "form at AWS Bedrock → Model access, then retry."
            ) from e
        raise
    payload = json.loads(resp["body"].read())
    parts = payload.get("content", [])
    return "".join(p.get("text", "") for p in parts if p.get("type") == "text")


# ---------- Chef Charlie ----------

CHEF_SYSTEM = """You are Chef Charlie, an AI sous-chef inside the PantryAI app.
You can see the user's pantry, grocery list, weekly meal plan, and recipe library
(provided in the user message as JSON context). Be concise and practical.

RESPONSE FORMAT — strict:
Respond with a JSON array of blocks inside <response>...</response> tags. Each
block is one of:

  {"type":"text","content":"<markdown text>"}
  {"type":"recipe_card","title":"...","ingredients":["..."],"instructions":["..."],"recipe_id":"<optional>"}
  {"type":"grocery_suggestion","items":[{"name":"...","quantity":"..."}]}
  {"type":"meal_plan","slots":[{"day":0-6,"meal":"breakfast|lunch|dinner","title":"..."}]}
  {"type":"action","label":"...","action":"add_to_grocery|add_to_meal_plan|add_recipe","payload":{...}}

Keep blocks small and composable. Use multiple blocks rather than one mega-block.
If unsure, return only a text block. Never include prose outside the tags.
"""


_BLOCK_RE = re.compile(r"<response>(.*?)</response>", re.DOTALL)


def parse_chef_response(raw: str) -> list[dict]:
    """Extract structured blocks. Falls back to a single text block."""
    m = _BLOCK_RE.search(raw)
    if not m:
        return [{"type": "text", "content": raw.strip()}]
    inner = m.group(1).strip()
    try:
        parsed = json.loads(inner)
        if isinstance(parsed, list):
            return [b for b in parsed if isinstance(b, dict) and "type" in b]
    except json.JSONDecodeError:
        log.warning("Chef Charlie returned non-JSON inside tags; falling back")
    return [{"type": "text", "content": raw.strip()}]


def chef_chat(user_message: str, context: dict, history: list[dict] | None = None) -> list[dict]:
    msg = (
        "CONTEXT (current app state):\n```json\n"
        + json.dumps(context, default=str)
        + "\n```\n\nUSER:\n"
        + user_message
    )
    messages = list(history or []) + [{"role": "user", "content": msg}]
    raw = invoke(messages, system=CHEF_SYSTEM, max_tokens=3000, temperature=0.5)
    return parse_chef_response(raw)


# ---------- Recipe generation / import ----------

RECIPE_GEN_SYSTEM = """You generate a single recipe as strict JSON. Output ONLY
a JSON object with this shape (no prose, no code fences):

{
  "title": "string",
  "ingredients": ["1 cup flour", "..."],
  "instructions": ["Step 1...", "..."],
  "tags": ["dinner","quick"],
  "servings": 4
}
"""


def generate_recipe(prompt: str) -> dict:
    raw = invoke(
        [{"role": "user", "content": prompt}],
        system=RECIPE_GEN_SYSTEM,
        max_tokens=1500,
        temperature=0.7,
    )
    return _extract_json_object(raw)


RECIPE_IMPORT_SYSTEM = """Extract a recipe from this raw HTML / text. Output ONLY
a JSON object (no prose, no code fences):

{
  "title": "string",
  "ingredients": ["..."],
  "instructions": ["..."],
  "image_url": "string or empty",
  "servings": 4
}
"""


def import_recipe(html_or_text: str) -> dict:
    # Hard cap input so we don't blow the context window
    snippet = html_or_text[:60000]
    raw = invoke(
        [{"role": "user", "content": snippet}],
        system=RECIPE_IMPORT_SYSTEM,
        max_tokens=2500,
        temperature=0.2,
    )
    return _extract_json_object(raw)


def _extract_json_object(raw: str) -> dict:
    """Tolerate code fences or stray prose; return first JSON object found."""
    s = raw.strip()
    if s.startswith("```"):
        s = s.strip("`")
        # ```json\n...\n``` shape
        nl = s.find("\n")
        if nl != -1:
            s = s[nl + 1 :]
        if s.endswith("```"):
            s = s[:-3]
    # Find first { ... } balanced
    start = s.find("{")
    if start == -1:
        return {}
    depth = 0
    for i in range(start, len(s)):
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(s[start : i + 1])
                except json.JSONDecodeError:
                    return {}
    return {}
