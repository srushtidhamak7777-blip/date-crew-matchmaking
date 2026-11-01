# The Date Crew: matchmaking prototype

Take-home assignment by Srushti Dhamak.

## The problem I picked

Matchmakers send profiles that clients reject for reasons the client already gave us (about 35% of rejections), and the reasons sit in free-text emails where nobody can learn from them.

## What's here

- `app.py`: Streamlit prototype with mocked data (3 clients, 14 profiles, 10 rejections).
  - **Rejection tagger tab**: tags each rejection and checks it against the client's stated preferences. It flags what was avoidable, what hit a soft preference, what suggests the client's form is out of date, and what needs a matchmaker to review.
  - It also shows avoidable rejections by matchmaker, the weekly view for the ops lead. The matchmaker mapping is invented.
  - **Shortlist tab**: applies a client's hard filters to the profile pool and ranks what's left.
- `rules.py`: the core logic (preference checker, keyword tagger, shortlist ranking), kept separate from the UI so it can be tested.
- `tagger.py`: the LLM tagger. Sends the rejection text to the Claude API and gets back JSON. The app has a toggle for it; without an API key it uses the keyword rules in `rules.py`.
- `test_rules.py`: tests for the edge cases below.
- `eval_tagger.py`: scores the tagger against 14 hand-labelled rejections. The keyword rules get 10/14. The misses ("his mother sounded controlling", "lives in another country", "wanted someone more religious", "drinks a lot") are the cases that need an LLM. Set `ANTHROPIC_API_KEY` to score the Claude tagger the same way.
- `index.html`: an earlier, simpler web version of the prototype that opens in any browser. It does not have the edge-case handling.

## Edge cases handled

- Missing profile data is "unknown", ranks lower, and is never treated as a deal breaker.
- Messy text (" pune ") still matches.
- Negation: "he doesn't smoke, but too far" is not a smoking complaint, while "not tall enough" still counts as a height complaint. (The eval caught my first version getting this wrong.)
- One reply with several reasons gets several tags.
- Blank or vague replies go to the matchmaker, and the tool still says if the profile broke a stated preference.
- Profile meets the stated preference but was rejected anyway: flagged as "form may be out of date".
- Profiles already sent to a client are never shown again.
- Empty shortlist tells the matchmaker to widen the search.
- Unknown client or profile ids raise a clear error.
- API errors, bad JSON, unknown categories and out-of-range confidence from the LLM all fall back to "unclear" for human review.

## Run it

```
pip install -r requirements.txt
streamlit run app.py
python test_rules.py
python eval_tagger.py
```

For the LLM tagger, set `ANTHROPIC_API_KEY` and turn on the toggle in the app, or run `python tagger.py`.

## Limits

The data is mocked, and the keyword tagger is simple on purpose. The first real step would be hand-labelling 50 real rejections and testing the tagger against them.
