# OPPA | Operational Pain Point Assessment
### Make the gap between perception and floor reality visible.

An interactive assessment app that compares client self-assessments with auditor observations across 12 operational categories, turning interviews and field evidence into a shared view of operational friction.

## The business problem
Leaders and frontline auditors can see the same operation very differently. Scores alone lose context; photos and voice notes alone are difficult to compare. OPPA brings them into one assessment workflow.

## What I built
- Client and auditor scoring across labor, process flow, inventory, safety, quality, and other operational categories.
- Gap analysis, risk indicators, and a radar chart comparing the two perspectives.
- Photo and voice-note capture alongside assessment notes.
- Baseline, 30-day check-in, and final-review phases.
- CSV export and optional Supabase authentication, records, and media storage.

**Stack:** Python · Streamlit · Plotly · pandas · Supabase

## Try locally
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Choose Demo Mode to explore without Supabase. Saving to the database is disabled in that mode.

## Optional persistence
The module documentation at the top of [app.py](app.py) contains the expected SQL schema and storage bucket names. Configure `SUPABASE_URL` and `SUPABASE_KEY` through environment variables or `.streamlit/secrets.toml`. Keep credentials out of Git. Use an appropriately restricted client key and row-level access policies before a shared deployment.

## Walkthrough
1. Create an assessment and enter its metadata.
2. Score the client and auditor perspectives.
3. Add supporting notes, photos, or voice recordings.
4. Review gaps and critical disconnects.
5. Export the assessment or save it to a configured Supabase project.

## Scope
An assessment MVP. Gap and risk rules are application heuristics; they support discussion and prioritization rather than replacing an operational audit.

---
Built by [Vishwa Mehta](https://www.linkedin.com/in/vishwa10/) · Forward Deployed Engineer
