"""Scores the tagger against hand-labelled rejections.

Run:  python eval_tagger.py              (keyword tagger only)
      ANTHROPIC_API_KEY=... python eval_tagger.py   (also scores the Claude tagger)

The labels are my own. 14 examples is a smoke test, not a benchmark. The real
version of this would use 50 real rejections labelled by a matchmaker.
"""
import os

from rules import tag_keywords

LABELLED = [
    ("He smokes heavily, I can't deal with that.", "smoking"),
    ("Too old for me.", "age"),
    ("He is not tall enough.", "height"),
    ("I didn't like his photos.", "looks"),
    ("His salary seems low for what I want.", "career"),
    ("Too far from my office, I can't do that commute.", "location"),
    ("He wants kids right away and I don't.", "kids"),
    ("Just not feeling it, no real reason.", "unclear"),
    ("He wants to live with his parents after marriage.", "family"),
    ("His mother sounded very controlling on the call.", "family"),
    ("He lives in another country and I won't move.", "location"),
    ("I wanted someone more religious.", "religion"),
    ("He drinks a lot at parties.", "other"),
    ("He doesn't smoke which is great, but he looks much older than his age.", "age"),
]


def keyword(text):
    return tag_keywords(text)[0][0]


def score(name, fn):
    right, misses = 0, []
    for text, label in LABELLED:
        got = fn(text)
        if got == label:
            right += 1
        else:
            misses.append((text, label, got))
    print(f"{name}: {right}/{len(LABELLED)} correct ({round(100 * right / len(LABELLED))}%)")
    for text, label, got in misses:
        print(f"   missed: {text!r}  expected {label}, got {got}")


if __name__ == "__main__":
    score("keyword rules", keyword)
    if os.getenv("ANTHROPIC_API_KEY"):
        from tagger import tag_rejection
        score("claude tagger", lambda t: tag_rejection(t, {})["category"])
    else:
        print("claude tagger: skipped (set ANTHROPIC_API_KEY to score it)")
