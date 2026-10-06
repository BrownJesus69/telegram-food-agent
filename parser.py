import json
import logging
import re
from dataclasses import dataclass
from typing import Optional

import httpx

import config

log = logging.getLogger(__name__)

STOP = set("""i am im hungry want wanna need needs give gimme me get find show a an the some any please
pls order eat craving craving for of to and with near nearby around here can you could would like
food something good best cheap tasty hello hi hey now asap quickly fast""".split())

NUM_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}

BUDGET_PATTERNS = [
    r"(?:under|below|within|upto|up to|max|maximum|less than|budget)\s*(?:of\s*)?(?:₹|rs\.?|inr)?\s*(\d+)",
    r"(?:₹|rs\.?|inr)\s*(\d+)",
    r"(\d+)\s*(?:rs|rupees|inr|₹)",
]


@dataclass
class ParsedQuery:
    dish: Optional[str] = None
    budget: Optional[int] = None
    qty: int = 1
    diet: Optional[str] = None


def parse(text):
    t = " " + text.lower().replace(",", " ") + " "
    budget = None
    for pat in BUDGET_PATTERNS:
        m = re.search(pat, t)
        if m:
            budget = int(m.group(1))
            t = t[: m.start()] + " " + t[m.end():]
            break

    diet = None
    if re.search(r"\bnon[\s-]?veg(?:etarian)?\b", t):
        diet = "non_veg"
        t = re.sub(r"\bnon[\s-]?veg(?:etarian)?\b", " ", t)
    elif re.search(r"\b(?:pure\s+)?veg(?:etarian)?\b", t):
        diet = "veg"
        t = re.sub(r"\b(?:pure\s+)?veg(?:etarian)?\b", " ", t)

    qty = 1
    m = re.search(r"\b(\d{1,2})\b", t)
    if m:
        qty = max(1, min(int(m.group(1)), 10))
        t = t[: m.start()] + " " + t[m.end():]
    else:
        for w, n in NUM_WORDS.items():
            if re.search(rf"\b{w}\b", t):
                qty = n
                t = re.sub(rf"\b{w}\b", " ", t)
                break

    tokens = [w for w in re.findall(r"[a-z]+", t) if w not in STOP]
    dish = " ".join(tokens).strip() or None
    return ParsedQuery(dish=dish, budget=budget, qty=qty, diet=diet)


SYSTEM = (
    "Extract a food-search request. Return ONLY JSON: "
    '{"dish": string|null, "budget": integer|null, "quantity": integer, "diet": "veg"|"non_veg"|null}. '
    "Do not suggest restaurants. Do not invent missing values."
)


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


async def groq_extract(text):
    if not config.GROQ_API_KEY:
        return None
    payload = {
        "model": config.GROQ_MODEL,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": text[:500]}],
    }
    try:
        async with httpx.AsyncClient(timeout=8) as c:
            r = await c.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {config.GROQ_API_KEY}"},
                json=payload,
            )
            r.raise_for_status()
            data = json.loads(r.json()["choices"][0]["message"]["content"])
    except Exception as e:
        log.warning("groq_extract failed: %s", type(e).__name__)
        return None
    dish = (data.get("dish") or "").strip().lower() or None
    diet = data.get("diet") if data.get("diet") in ("veg", "non_veg") else None
    qty = _int(data.get("quantity")) or 1
    return ParsedQuery(dish=dish, budget=_int(data.get("budget")), qty=max(1, min(qty, 10)), diet=diet)
