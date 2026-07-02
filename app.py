"""
app.py — hosted sandbox demo for the Redrob hackathon submission.

Deployable to Streamlit Cloud / HuggingFace Spaces (Streamlit SDK).
Accepts a small candidate sample (<=100 candidates.jsonl-format rows),
runs the exact same scoring logic as rank.py, and displays/downloads a
ranked CSV — satisfying Section 10.5 of the submission spec.

Run locally:
    streamlit run app.py
"""

import csv
import io
import json

import streamlit as st

from rank import score_candidate, build_reasoning

st.set_page_config(page_title="Redrob Ranker Sandbox", layout="wide")
st.title("Redrob Candidate Ranker — Sandbox")
st.caption(
    "Upload a small candidates.jsonl sample (<=100 candidates) and run the "
    "same rule-based ranker used to produce the full submission. CPU-only, "
    "no network calls, completes in seconds."
)

uploaded = st.file_uploader("candidates.jsonl (or sample_candidates.json)", type=["jsonl", "json"])

if uploaded is not None:
    raw = uploaded.read().decode("utf-8")
    candidates = []
    if uploaded.name.endswith(".json"):
        candidates = json.loads(raw)
    else:
        for line in raw.splitlines():
            line = line.strip()
            if line:
                candidates.append(json.loads(line))

    st.write(f"Loaded {len(candidates)} candidates.")

    if st.button("Rank candidates"):
        scored = []
        dropped = 0
        for c in candidates:
            r = score_candidate(c)
            if r is None:
                dropped += 1
                continue
            scored.append(r)

        if scored:
            max_score = max(r["score"] for r in scored)
            if max_score > 0:
                for r in scored:
                    r["score"] = round(r["score"] / max_score * 0.999, 4)

        scored.sort(key=lambda r: (-r["score"], r["candidate_id"]))

        st.write(f"Dropped {dropped} suspected honeypots.")

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["candidate_id", "rank", "score", "reasoning"])
        for i, r in enumerate(scored, start=1):
            writer.writerow([r["candidate_id"], i, f'{r["score"]:.4f}', build_reasoning(i, r)])

        st.download_button(
            "Download ranked CSV",
            data=buf.getvalue(),
            file_name="ranked_sample.csv",
            mime="text/csv",
        )
        st.dataframe(
            [
                {
                    "rank": i,
                    "candidate_id": r["candidate_id"],
                    "score": r["score"],
                    "title": r["current_title"],
                    "company": r["current_company"],
                }
                for i, r in enumerate(scored, start=1)
            ]
        )
else:
    st.info("Upload sample_candidates.json from the hackathon bundle to try it out.")
