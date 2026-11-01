"""Core logic: mock data, the preference checker, a keyword tagger and the shortlist.

Kept separate from the UI so it can be tested. Edge cases handled here:
  - missing profile data (unknown, not a fail)       - messy text like " pune "
  - blank or vague rejections                         - negation ("doesn't smoke")
  - several reasons in one rejection                  - form out of date (stale)
  - profiles already sent to a client                 - empty shortlist
  - unknown client or profile ids
"""
import re

LOW_CONFIDENCE = 0.6
UNKNOWN_PENALTY = 10   # unknown data ranks a profile lower, it does not exclude it
SOFT_PENALTY = 20

# "soft" = a preference the client states but has not enforced in the past.
CLIENTS = {
    "c1": {"name": "Riya", "age": (28, 34), "cities": ["Pune", "Mumbai"],
           "smoker": False, "kids": "yes", "soft": {"height": 170},
           "note": "Height is marked soft: she accepted shorter profiles twice after rejecting on height."},
    "c2": {"name": "Aman", "age": (26, 31), "cities": ["Mumbai", "Navi Mumbai", "Thane"],
           "smoker": False, "kids": "yes", "soft": {}, "note": ""},
    "c3": {"name": "Neha", "age": (30, 36), "cities": ["Bengaluru"],
           "smoker": False, "kids": "open", "soft": {}, "note": ""},
}

# Mock mapping of clients to matchmakers (invented, to show the by-matchmaker view).
MATCHMAKERS = {"c1": "B", "c2": "A", "c3": "A"}

PROFILES = [
    {"id": "P1", "name": "Karan", "age": 31, "city": "Pune", "smoker": False, "kids": "yes", "height": 178},
    {"id": "P2", "name": "Vikram", "age": 35, "city": "Pune", "smoker": False, "kids": "yes", "height": 175},
    {"id": "P3", "name": "Sameer", "age": 30, "city": "Mumbai", "smoker": False, "kids": "open", "height": 168},
    {"id": "P4", "name": "Arjun", "age": 33, "city": "Pune", "smoker": True, "kids": "yes", "height": 180},
    {"id": "P5", "name": "Rohit", "age": 29, "city": "Navi Mumbai", "smoker": False, "kids": "yes", "height": 172},
    {"id": "P6", "name": "Dev", "age": 30, "city": "Mumbai", "smoker": False, "kids": "no", "height": 176},
    {"id": "P7", "name": "Nikhil", "age": 27, "city": "Thane", "smoker": False, "kids": "yes", "height": 170},
    {"id": "P8", "name": "Abhay", "age": 34, "city": "Bengaluru", "smoker": False, "kids": "open", "height": 174},
    {"id": "P9", "name": "Tarun", "age": 31, "city": "Bengaluru", "smoker": True, "kids": "yes", "height": 177},
    {"id": "P10", "name": "Mihir", "age": 30, "city": "Mumbai", "smoker": False, "kids": "yes", "height": 165},
    # Messy record: city has stray spaces and lowercase, age/smoking/kids are missing.
    {"id": "P11", "name": "Yash", "age": None, "city": " pune ", "smoker": None, "kids": None, "height": None},
    {"id": "P12", "name": "Kabir", "age": 32, "city": "Mumbai", "smoker": False, "kids": "yes", "height": 175},
    {"id": "P13", "name": "Ishan", "age": 28, "city": "Pune", "smoker": False, "kids": "yes", "height": 171},
    {"id": "P14", "name": "Rahul", "age": 28, "city": "Thane", "smoker": False, "kids": "open", "height": 173},
]

# (client, profile, what the client wrote back)
REJECTIONS = [
    ("c1", "P4", "He smokes, I did mention this in my form. Please be careful."),
    ("c1", "P2", "Too much older than me, I wanted someone closer to my age."),
    ("c2", "P7", "Didn't feel a connection from the photos, not my type."),
    ("c3", "P9", "He is a smoker and I can't be with that. Also seems a bit short."),
    ("c1", "P3", "Honestly he seems short for me, I need someone taller."),
    ("c2", "P6", "Not sure. Just not feeling it right now."),
    ("c3", "P8", "His family is a joint family and I prefer a nuclear setup."),
    ("c2", "P5", "Seems nice but he is too old for me honestly."),
    ("c1", "P1", "He doesn't smoke which is good, but he is too far from where I work."),
    ("c2", "P10", "   "),
]

# First match wins per category. Production uses an LLM (see tagger.py); this runs offline.
KEYWORDS = [
    ("smoking", r"smok|cigarette"),
    ("kids", r"kids|children|child"),
    ("age", r"older|younger|too old|\bage\b"),
    ("location", r"city|\bfar\b|relocat|distance|commute"),
    ("height", r"tall|short|height"),
    ("family", r"family|parents"),
    ("career", r"\bjob\b|salary|career|earn"),
    ("looks", r"photo|looks|attractive|\btype\b|appearance"),
]
NEGATION = re.compile(r"\b(not|no|never)\b|n't")
# Negation only cancels categories where "not X" means the trait is absent ("doesn't smoke").
# For others it is the complaint itself ("not tall enough", "didn't like his photos").
NEGATABLE = {"smoking"}


def tag_keywords(text):
    """Return (list_of_categories, confidence).

    Handles blank text, negation ("doesn't smoke" is not a complaint about smoking, but
    "not tall enough" is a complaint about height) and several reasons in one message.
    """
    text = (text or "").strip().lower()
    if not text:
        return ["unclear"], 0.0
    found = []
    for category, pattern in KEYWORDS:
        for m in re.finditer(pattern, text):
            negated = category in NEGATABLE and NEGATION.search(text[max(0, m.start() - 15):m.start()])
            if not negated:
                found.append(category)
                break
    if not found:
        return ["unclear"], 0.3
    return found, 0.9 if len(found) == 1 else 0.7


def _norm(s):
    return (s or "").strip().lower()


def check(client, profile):
    """Return (hard_fails, soft_misses, unknowns), each a list of (category, message).

    Missing data goes in unknowns. It never counts as a fail, because a missing
    field is not the same as a deal breaker.
    """
    hard, soft, unknown = [], [], []
    lo, hi = client["age"]
    if profile.get("age") is None:
        unknown.append(("age", "age not recorded"))
    elif not lo <= profile["age"] <= hi:
        hard.append(("age", f"age {profile['age']} is outside {lo}-{hi}"))

    if not _norm(profile.get("city")):
        unknown.append(("location", "city not recorded"))
    elif _norm(profile["city"]) not in [_norm(c) for c in client["cities"]]:
        hard.append(("location", f"{profile['city'].strip()} is not in {'/'.join(client['cities'])}"))

    if not client["smoker"]:
        if profile.get("smoker") is None:
            unknown.append(("smoking", "smoking not recorded"))
        elif profile["smoker"]:
            hard.append(("smoking", "he smokes, client said no smoking"))

    if client["kids"] == "yes":
        if profile.get("kids") in (None, "unsure"):
            unknown.append(("kids", "kids preference not recorded"))
        elif profile["kids"] == "no":
            hard.append(("kids", "he does not want kids, client does"))

    h = client["soft"].get("height")
    if h and profile.get("height") is not None and profile["height"] < h:
        soft.append(("height", f"{profile['height']} cm is under {h} cm"))
    return hard, soft, unknown


def describe_prefs(client):
    """Plain-language prefs, used as context for the LLM tagger."""
    return {"age": f"{client['age'][0]}-{client['age'][1]}", "cities": client["cities"],
            "smoking": "smoker" if client["smoker"] else "no smoking",
            "kids": client["kids"], "soft_preferences": client["soft"]}


def _get(client_id, profile_id):
    if client_id not in CLIENTS:
        raise ValueError(f"Unknown client id: {client_id!r}")
    profile = next((p for p in PROFILES if p["id"] == profile_id), None)
    if profile is None:
        raise ValueError(f"Unknown profile id: {profile_id!r}")
    return CLIENTS[client_id], profile


def analyse(client_id, profile_id, text, tagger=None):
    """Tag one rejection and say what it tells us.

    tagger: optional function(text, prefs) -> {"category", "confidence"}.
    status: avoidable | soft | stale | review | new
      avoidable = broke a stated hard preference, the pre-send check would have caught it
      soft      = broke a preference this client has not enforced before
      stale     = profile meets the stated preference, so the form may be out of date
      review    = reason unclear or low confidence, matchmaker confirms
      new       = a reason that is not in the form at all, worth learning from
    """
    client, profile = _get(client_id, profile_id)
    if tagger and (text or "").strip():
        r = tagger(text, describe_prefs(client))
        cats, conf = [r["category"]], r["confidence"]
    else:
        cats, conf = tag_keywords(text)

    hard, soft, unknown = check(client, profile)
    hard_k, soft_k, unk_k = {k for k, _ in hard}, {k for k, _ in soft}, {k for k, _ in unknown}
    stated = {"age", "location", "smoking", "kids"} | set(client["soft"])

    hard_hits = [m for k, m in hard if k in cats]
    soft_hits = [m for k, m in soft if k in cats]
    stale = [k for k in cats if k in stated and k not in hard_k | soft_k | unk_k]
    new = [k for k in cats if k not in stated and k != "unclear"]

    extras = [f"{k}: the profile meets the stated preference, so the form may be out of date" for k in stale]
    extras += [f"{k}: not in the form, a new signal" for k in new]

    if hard_hits:
        status = "avoidable"
        msg = f"Avoidable: {'; '.join(hard_hits)}. The pre-send check would have blocked this."
    elif soft_hits:
        status = "soft"
        msg = f"Soft preference ({'; '.join(soft_hits)}). {client['note']}".strip()
    elif stale:
        status = "stale"
        msg = (f"The profile meets the stated {', '.join(stale)} preference, so the form may be "
               "out of date. Ask the client what their real limit is.")
        extras = [e for e in extras if not e.split(":")[0] in stale]
    elif cats == ["unclear"] or conf < LOW_CONFIDENCE:
        status = "review"
        msg = "Blank or unclear reply, so the matchmaker confirms the reason." if cats == ["unclear"] \
            else "Low confidence, so the matchmaker confirms the reason."
    else:
        status, msg = "new", "Not in stated preferences. This is a new signal to learn from."
        extras = [e for e in extras if "new signal" not in e]

    caught = bool(hard)  # would the pre-send check have stopped this profile for any reason?
    if status == "review" and caught:
        msg += " The pre-send check would still have caught: " + "; ".join(m for _, m in hard) + "."
    if status in ("avoidable", "soft") and extras:
        msg += " Also: " + "; ".join(extras) + "."
    return {"client": client["name"], "client_id": client_id, "matchmaker": MATCHMAKERS.get(client_id, "?"),
            "profile": profile, "text": (text or "").strip(),
            "categories": cats, "confidence": conf, "status": status, "message": msg,
            "caught": caught}


def shortlist(client_id):
    """Rank profiles that pass every hard filter.

    Returns (passed, out). passed rows are (profile, score, soft_notes, unknown_notes).
    Profiles already sent to this client are left out so they are never repeated.
    """
    if client_id not in CLIENTS:
        raise ValueError(f"Unknown client id: {client_id!r}")
    client = CLIENTS[client_id]
    sent = {p for c, p, _ in REJECTIONS if c == client_id}
    mid = sum(client["age"]) / 2
    passed, out = [], []
    for p in PROFILES:
        if p["id"] in sent:
            out.append((p, ["already sent to this client"]))
            continue
        hard, soft, unknown = check(client, p)
        if hard:
            out.append((p, [m for _, m in hard]))
            continue
        score = 100 - SOFT_PENALTY * len(soft) - UNKNOWN_PENALTY * len(unknown)
        if p.get("age") is not None:
            score -= 2 * abs(p["age"] - mid)
        passed.append((p, round(score), [m for _, m in soft], [m for _, m in unknown]))
    passed.sort(key=lambda x: -x[1])
    return passed, out


def is_avoidable(result):
    """Counts as avoidable if the pre-send check would have stopped the profile for a
    stated reason, or if the reply was unclear but the profile broke a stated preference."""
    return result["status"] == "avoidable" or (result["status"] == "review" and result["caught"])


def summarise(results):
    """Overall and per-matchmaker avoidable rate. Empty input returns zeros, not an error."""
    def block(rs):
        n = len(rs)
        a = sum(is_avoidable(r) for r in rs)
        return {"rejections": n, "avoidable": a, "rate": round(100 * a / n) if n else 0}
    by = {}
    for m in sorted({r["matchmaker"] for r in results}):
        by[m] = block([r for r in results if r["matchmaker"] == m])
    return block(results), by
