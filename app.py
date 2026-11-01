"""Streamlit prototype. Run with:  streamlit run app.py"""
import os

import streamlit as st

from rules import CLIENTS, PROFILES, REJECTIONS, analyse, shortlist, summarise

st.set_page_config(page_title="Date Crew prototype", page_icon="💌")
st.title("Date Crew prototype")
st.caption("Mock data only. One rule engine powers both tabs: it reads a client's "
           "stated preferences and checks them against a profile.")

tab_tag, tab_list = st.tabs(["Rejection tagger", "Shortlist builder"])

with tab_tag:
    use_ai = st.toggle("Use Claude API for tagging (needs ANTHROPIC_API_KEY)")
    tagger = None
    if use_ai:
        if os.getenv("ANTHROPIC_API_KEY"):
            from tagger import tag_rejection
            tagger = tag_rejection
        else:
            st.warning("No ANTHROPIC_API_KEY set, using keyword rules instead.")

    results = [analyse(c, p, t, tagger) for c, p, t in REJECTIONS]
    n = len(results)
    overall, by_mm = summarise(results)
    avoidable = overall["avoidable"]
    stale = sum(r["status"] == "stale" for r in results)
    review = sum(r["status"] == "review" for r in results)
    cols = st.columns(5)
    cols[0].metric("Rejections", n)
    cols[1].metric("Avoidable", avoidable)
    cols[2].metric("Avoidable rate", f"{round(100 * avoidable / n)}%")
    cols[3].metric("Form out of date", stale)
    cols[4].metric("Need review", review)
    st.caption("Avoidable = the pre-send check would have stopped the profile. "
               "Form out of date = the profile met the stated preference but was still rejected. "
               "All data here is invented, so these numbers show how the tool works, "
               "not Date Crew's real rates.")
    st.markdown("**Avoidable rejections by matchmaker** (the weekly view for the ops lead)")
    st.table([{"Matchmaker": m, "Rejections": v["rejections"], "Avoidable": v["avoidable"],
               "Avoidable rate": f"{v['rate']}%"} for m, v in by_mm.items()])

    show = {"avoidable": st.error, "soft": st.warning, "stale": st.info,
            "review": st.warning, "new": st.success}
    for r in results:
        p = r["profile"]
        with st.container(border=True):
            st.caption(f"{r['client']} on {p['name']} ({p['age'] or '?'}, {(p['city'] or '?').strip()})")
            st.markdown(f"*“{r['text'] or '(blank reply)'}”*")
            st.markdown(" ".join(f"`{c}`" for c in r["categories"]) + f"  `confidence {r['confidence']}`")
            show[r["status"]](r["message"])

with tab_list:
    cid = st.selectbox("Client", list(CLIENTS), format_func=lambda k: CLIENTS[k]["name"])
    c = CLIENTS[cid]
    st.caption(f"Hard filters: age {c['age'][0]}-{c['age'][1]}, {'/'.join(c['cities'])}, "
               f"no smoking{', wants kids' if c['kids'] == 'yes' else ''}. {c['note']}")
    passed, out = shortlist(cid)
    st.subheader(f"Shortlist ({len(passed)} of {len(PROFILES)})")
    if not passed:
        st.warning("No profiles pass every hard filter. The matchmaker should widen the search "
                   "or ask the client which preference can flex.")
    for p, score, soft, unknown in passed:
        with st.container(border=True):
            st.markdown(f"**{p['name']}**, {p['age'] or '?'}, {p['city'].strip().title()}  ·  score {score}")
            if soft:
                st.warning("Soft miss: " + "; ".join(soft))
            if unknown:
                st.info("Check before sending: " + "; ".join(unknown))
    st.subheader(f"Filtered out ({len(out)})")
    for p, why in out:
        st.markdown(f"**{p['name']}**: :red[{'; '.join(why)}]")
