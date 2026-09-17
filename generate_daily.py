#!/usr/bin/env python3
"""
Runs unattended (see .github/workflows/daily.yml) — no visitor required.

What it does, once a day:
1. Calls the Anthropic API (with web search on) to find one genuinely
   newsworthy upcoming phone / accessory / car.
2. Asks for a short bilingual (EN + TR) news blurb about it.
3. Appends it to daily_history.json (keeps the last 60 entries).
4. Writes today's entry into daily_today.json, which index.html fetches.

Requires:
  pip install anthropic
  env var ANTHROPIC_API_KEY set (GitHub Actions injects it from a repo secret)
"""

import json
import os
import re
from datetime import date, datetime, timezone
from pathlib import Path

import anthropic

ROOT = Path(__file__).parent
HISTORY_PATH = ROOT / "daily_history.json"
TODAY_PATH = ROOT / "daily_today.json"
MAX_HISTORY = 60

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

PROMPT = """You are the automated editor for Droplist, a tracker of upcoming
phones, accessories and cars (global market, but the audience is in Turkey).

Use web search to find ONE genuinely newsworthy item from the last few days:
a new confirmed launch date, a leak that firmed up, a spec reveal, a price
leak, or similar — for a phone, an accessory (earbuds/wearables/chargers),
or a car (EV or otherwise).

Then write a short news blurb about it (45-70 words), once in English and
once in natural, professional Turkish (not a literal translation).

Respond with ONLY strict JSON, no markdown fences, no commentary, in exactly
this shape:
{"category":"phones|accessories|cars","item_name":"...","maker":"...",
 "headline_en":"...","body_en":"...","headline_tr":"...","body_tr":"...",
 "source_url":"..."}
"""


def generate() -> dict:
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1200,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": PROMPT}],
    )

    # Concatenate all text blocks (search results add tool_use/tool_result
    # blocks in between — we only want the assistant's final text).
    text = "".join(b.text for b in resp.content if b.type == "text").strip()

    # Be tolerant of stray fences or prose around the JSON object.
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise ValueError(f"No JSON object found in model output:\n{text}")
    return json.loads(match.group(0))


def main():
    picked = generate()
    today = date.today().isoformat()

    entry = {
        "date": today,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        **picked,
    }

    # today's entry — what the live page fetches
    TODAY_PATH.write_text(json.dumps(entry, ensure_ascii=False, indent=2))

    # rolling archive
    history = []
    if HISTORY_PATH.exists():
        history = json.loads(HISTORY_PATH.read_text())
    history = [h for h in history if h.get("date") != today]  # replace same-day reruns
    history.insert(0, entry)
    history = history[:MAX_HISTORY]
    HISTORY_PATH.write_text(json.dumps(history, ensure_ascii=False, indent=2))

    print(f"Wrote daily find for {today}: {entry.get('item_name')}")


if __name__ == "__main__":
    main()
