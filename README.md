# Redrob Hackathon Submission — Intelligent Candidate Discovery & Ranking

A rule-based, explainable ranker that scores all 100,000 candidates against
the Redrob AI "Intelligence Layer Engineer" job description and outputs the
top 100, with a monotonically non-increasing score and a fact-grounded
reasoning string per candidate.

## Reproduce the submission

```bash
pip install -r requirements.txt   # no third-party deps; stdlib only
python rank.py --candidates ./candidates.jsonl --out ./submission.csv
python validate_submission.py ./submission.csv
```

Runs in ~40 seconds on a single CPU core with <200MB RAM on the full 100K
candidate pool — well inside the 5-minute / 16GB / CPU-only / no-network
budget. No pre-computation step is required.

## Why rule-based, not embeddings/LLM re-ranking

The compute budget (CPU-only, 5 minutes, no network, no GPU) rules out
per-candidate LLM calls and makes dense embedding search for 100K
candidates unnecessarily heavy for a single ranking pass. A transparent,
inspectable rule engine also directly serves the JD's own stated concern:
*"the right answer is not keyword matching, it's reasoning about the gap
between what the JD says and what it means."* A rule engine lets us encode
that reasoning explicitly and defend every score component.

## Methodology

### 1. Honeypot screen (runs first, removes candidates from the pool)

The dataset is described as containing ~80 candidates with internally
*inconsistent* profiles. Rather than guessing at an ID list, we detect
self-contradiction directly:

- Free-text summary states a different years-of-experience than the
  structured `years_of_experience` field (e.g. field says 2.8, prose says
  "7.4 years of experience").
- Total `career_history` duration is wildly inconsistent with
  `years_of_experience` (too long or too short).
- A single role's duration exceeds the candidate's entire claimed career.
- Overlapping full-time roles (>6 months of overlap between two jobs).
- `expert` proficiency claimed on 2+ skills with `duration_months == 0`.
- Education `end_year` before `start_year`.

A candidate tripping enough of these checks is dropped before scoring.
This is defense-in-depth: even candidates that don't trip the hard
screen still score low from the trust-weighting and evidence checks below
(e.g. an "expert in 10 skills, 0 months used" candidate gets almost no
skills-score credit).

### 2. Base fit score (weighted sum of 7 components)

| Component | Weight | What it captures |
|---|---|---|
| Title relevance | 0.28 | Is the *current title* an ML/AI/search/ranking IC role, vs. a non-technical title (HR Manager, Content Writer, Operations Manager, etc.) with AI keywords bolted onto the skills list? This is the primary defense against the keyword-stuffer trap the JD calls out explicitly. |
| Production evidence | 0.27 | Regex/keyword evidence of embeddings, vector DBs/hybrid search, ranking/recommendation systems, retrieval, and eval-framework work *inside career-history prose*, not just the skills list. This is how a Tier-5 candidate who never writes "RAG" but clearly built a recommender system at a product company gets credit. |
| Trust-weighted skills | 0.15 | A skill only counts if it has endorsements, `duration_months > 0`, or is corroborated by career-history text — bare listed skills with none of these are the stuffing signature. |
| Experience fit | 0.10 | Smooth Gaussian peak at 7 years (center of the JD's "6-8 ideal" band), tapering across the 5-9 acceptable band and beyond — never a hard cutoff, matching the JD's "we'll consider candidates outside the band if other signals are strong." |
| Location fit | 0.10 | Pune/Noida (JD-preferred hub) scores highest; other welcomed Tier-1 India cities next; elsewhere in India scaled by `willing_to_relocate`; outside India scored low (JD: no visa sponsorship, case-by-case). |
| Education tier | 0.05 | Minor weight — the JD doesn't emphasize pedigree. |
| Tenure/stability | 0.05 | Smooth reward for longer average tenure in recent roles. |

All saturating sub-scores (evidence, skills, tenure) use smooth
asymptotic curves (`1 - e^(-x/k)`) rather than hard caps, so strong
candidates keep differentiating from each other instead of collapsing to
identical maxima — this matters for `score` monotonicity and for
NDCG@10, where getting the *order* of the top candidates right matters
most.

### 3. Disqualifier-style penalties (multiplicative, stacking)

Directly encodes the JD's "things we explicitly do NOT want" and
disqualifier sections:

- Pure research/academia background with no production evidence → ×0.15
- Entire career at consulting/services firms (TCS, Infosys, Wipro,
  Accenture, Cognizant, Capgemini, etc.) with no product-company
  experience → ×0.25
- CV/speech/robotics background with no NLP/IR exposure → ×0.3
- AI experience limited to recent LangChain/LLM-API work, no pre-LLM
  production ML (ranking, retrieval, XGBoost-era work) → ×0.4
- Senior/management title with no recent hands-on IC role (last two
  roles' titles carry no engineer/scientist/developer hint) → ×0.5
- Rapid escalation through senior titles across short (<18mo avg) stints
  → ×0.6 (title-chaser pattern)
- No GitHub activity and no certifications at 5+ years experience → ×0.9
  (mild — "external validation" proxy)
- 4+ AI/ML skills listed with zero endorsements/usage/corroboration and
  low overall evidence → ×0.35 (the sharpest keyword-stuffing signature)

These are intentionally *soft* (multiplicative, not exclusionary) because
the JD explicitly says it will "seriously consider candidates outside the
band if other signals are strong" — a candidate can still rank if enough
other components are strong.

### 4. Behavioral signal multiplier (Redrob signals)

Applied last, as a bounded multiplier (0.5–1.2) on the fit score, per the
signals doc's own guidance ("incorporate them as a multiplier ... on top
of skill-match scoring"): `open_to_work_flag`, recency of
`last_active_date`, `recruiter_response_rate`, `interview_completion_rate`,
`notice_period_days`, verification flags, and `profile_completeness_score`.
A perfect-on-paper candidate who hasn't logged in for 6 months is
down-weighted, not excluded — matching the JD's own example.

### 5. Reasoning generation

Every reasoning string is built from facts actually extracted for that
candidate (title, company, years, the strongest evidence category found,
up to 4 corroborated skills, location note, response rate, notice period,
and the top penalty/behavioral concern if any) — never a fixed template
with the name swapped in, and never a claim not present in the source
profile.

## Files

- `rank.py` — the ranker (single command, no dependencies beyond stdlib)
- `validate_submission.py` — organizer-provided format validator (copied
  in unmodified)
- `requirements.txt` — empty; stdlib only, listed for completeness
- `submission_metadata.yaml` — fill in team/contact/repo/sandbox details
  before submitting
- `app.py` — minimal sandbox app (Streamlit) satisfying the Section 10.5
  hosted-sandbox requirement; runs the same `score_candidate` logic on an
  uploaded small candidate sample

## Known limitations / what we'd improve with more time

- The keyword lexicons (title/evidence terms, consulting-firm list) are
  hand-curated from the JD and sample data; a larger pass over the full
  100K pool's vocabulary would likely surface more edge terms.
- Honeypot detection is self-consistency-based, not tuned against the
  true ~80-candidate honeypot list (which we don't have) — we verified by
  hand that our top 100 contains zero candidates tripping any of our
  internal-consistency checks, but there could be honeypot patterns
  outside what we check for (e.g. contradictions we didn't think to
  encode).
- No offline eval against ground truth is possible (no live leaderboard),
  so component weights are reasoned from the JD text rather than tuned.
