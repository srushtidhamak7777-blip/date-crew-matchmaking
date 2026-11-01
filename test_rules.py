"""Edge-case tests. Run with:  python test_rules.py   (or pytest)"""
from rules import analyse, check, shortlist, summarise, tag_keywords, CLIENTS, PROFILES, REJECTIONS
from tagger import parse_reply


def test_negation_is_not_a_complaint():
    cats, _ = tag_keywords("He doesn't smoke, but he is too far away.")
    assert "smoking" not in cats and "location" in cats


def test_negation_can_be_the_complaint():
    assert tag_keywords("He is not tall enough.")[0] == ["height"]
    assert tag_keywords("I didn't like his photos.")[0] == ["looks"]


def test_blank_and_none_text():
    assert tag_keywords("   ") == (["unclear"], 0.0)
    assert tag_keywords(None) == (["unclear"], 0.0)
    assert analyse("c2", "P10", "   ")["status"] == "review"


def test_multiple_reasons():
    cats, conf = tag_keywords("He smokes and is also too short.")
    assert cats == ["smoking", "height"] and conf < 0.9


def test_missing_data_is_unknown_not_a_fail():
    p = next(x for x in PROFILES if x["id"] == "P11")
    hard, soft, unknown = check(CLIENTS["c1"], p)
    assert hard == [] and len(unknown) >= 3   # " pune " still matches Pune


def test_messy_city_text_matches():
    p = {"id": "x", "age": 30, "city": "  MUMBAI ", "smoker": False, "kids": "yes", "height": 175}
    assert check(CLIENTS["c1"], p)[0] == []


def test_stale_form_detected():
    # Aman's form says age 26-31, profile is 29, he still said "too old"
    assert analyse("c2", "P5", "he is too old for me")["status"] == "stale"


def test_hidden_avoidable_behind_vague_reply():
    r = analyse("c2", "P6", "Not sure. Just not feeling it.")
    assert r["status"] == "review" and r["caught"]   # kids mismatch the form would have caught


def test_already_sent_profiles_excluded():
    passed, out = shortlist("c1")
    assert "P1" not in [p["id"] for p, *_ in passed]
    assert any(p["id"] == "P1" and why == ["already sent to this client"] for p, why in out)


def test_empty_shortlist_is_handled():
    passed, out = shortlist("c3")
    assert passed == [] and len(out) == len(PROFILES)


def test_unknown_data_ranks_lower_but_stays():
    passed, _ = shortlist("c1")
    ids = [p["id"] for p, *_ in passed]
    assert "P11" in ids and ids[-1] == "P11"


def test_bad_ids_raise_clear_errors():
    for args in (("zz", "P1", "x"), ("c1", "P99", "x")):
        try:
            analyse(*args)
        except ValueError as e:
            assert "Unknown" in str(e)
        else:
            raise AssertionError("expected ValueError")


def test_llm_reply_parsing():
    good = '```json\n{"category":"smoking","confidence":0.8,"summary":"smokes"}\n```'
    assert parse_reply(good)["category"] == "smoking"
    assert parse_reply("not json at all")["category"] == "unclear"
    assert parse_reply('{"category":"made_up","confidence":1}')["category"] == "unclear"
    assert parse_reply('{"category":"age","confidence":7}')["confidence"] == 1.0
    assert parse_reply(None)["category"] == "unclear"


def test_summary_by_matchmaker():
    results = [analyse(c, p, x) for c, p, x in REJECTIONS]
    overall, by = summarise(results)
    assert overall["rejections"] == len(REJECTIONS)
    assert sum(v["rejections"] for v in by.values()) == overall["rejections"]
    assert summarise([]) == ({"rejections": 0, "avoidable": 0, "rate": 0}, {})


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("ok  ", t.__name__)
    print(f"{len(tests)} passed")
