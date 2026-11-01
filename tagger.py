"""Rejection tagger: turns free-text client rejections into structured tags.

The prototype uses keyword rules by default so it runs offline (see rules.py).
This is the LLM version: Claude reads the text and returns JSON.

Setup:  pip install anthropic   and set ANTHROPIC_API_KEY
Run:    python tagger.py
"""
import json
import os
import re

CATEGORIES = ["smoking", "kids", "age", "location", "height", "family",
              "career", "looks", "religion", "other", "unclear"]
MODEL = os.getenv("TAGGER_MODEL", "claude-sonnet-5-5")

SYSTEM = f"""You tag a client's rejection of a matchmaking profile.
Return ONLY a JSON object, no other text, with these keys:
  category: the main reason, one of {CATEGORIES}
  confidence: number from 0 to 1
  summary: the reason in under 12 words
If the client gives no real reason, use "unclear" with low confidence.
If the text is not a rejection or is empty, use "unclear" with confidence 0."""

FALLBACK = {"category": "unclear", "confidence": 0.0, "summary": "could not tag"}


def parse_reply(raw):
    """Parse the model's reply safely. Never raises; bad output becomes 'unclear'.

    Handles code fences around the JSON, extra text, invalid JSON, unknown
    categories and out-of-range confidence.
    """
    if not raw:
        return dict(FALLBACK)
    raw = re.sub(r"```(?:json)?", "", raw).strip()
    m = re.search(r"\{.*\}", raw, re.S)
    try:
        data = json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        return dict(FALLBACK)
    category = data.get("category")
    if category not in CATEGORIES:
        return dict(FALLBACK)
    try:
        conf = min(1.0, max(0.0, float(data.get("confidence", 0))))
    except (TypeError, ValueError):
        conf = 0.0
    return {"category": category, "confidence": conf, "summary": str(data.get("summary", ""))[:80]}


def tag_rejection(text, client_prefs):
    """Tag one rejection with Claude. On any API error, returns the 'unclear' fallback
    so the matchmaker reviews it by hand instead of the tool crashing."""
    if not (text or "").strip():
        return dict(FALLBACK)
    try:
        from anthropic import Anthropic
        msg = Anthropic().messages.create(
            model=MODEL, max_tokens=300, system=SYSTEM,
            messages=[{"role": "user", "content": json.dumps(
                {"stated_preferences": client_prefs, "rejection": text})}])
        return parse_reply(msg.content[0].text)
    except Exception as e:  # network, auth, rate limit
        out = dict(FALLBACK)
        out["summary"] = f"API error: {type(e).__name__}"
        return out


if __name__ == "__main__":
    prefs = {"age": "28-34", "cities": ["Pune", "Mumbai"], "smoking": "no smoking", "kids": "yes"}
    print(json.dumps(tag_rejection("He smokes, I did mention this in my form.", prefs), indent=2))
