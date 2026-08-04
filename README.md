# SignalDrop

Real-time content QC anomaly detection for streaming platforms — built for
the **Agentic Cinema: The Blockbuster Hackathon** (Google Cloud), ClickHouse
partner track.

## The problem

Streaming platforms lose viewers to specific, detectable causes — a bad
edit, a subtitle desync, a localized CDN failure — but today, someone has
to notice a chart looks wrong before anyone investigates. That's slow and
human-bottlenecked.

## What it does

A real, three-agent pipeline that finds an engagement anomaly, diagnoses
its probable cause, and files an actionable report — with no human in the
loop until the resulting GitHub Issue is triaged.

1. **Analyst Agent** — queries real streaming engagement telemetry in
   **ClickHouse Cloud**, via the official `mcp-clickhouse` MCP server, to
   find statistically significant anomalies (z-score based) in
   `buffer_stall` events by title/region/device/hour.
2. **Diagnosis Agent** — feeds the real anomaly into **Gemini** (via
   `google-genai` on Google Cloud's Gemini Enterprise Agent Platform) to
   propose the most likely root cause category, with reasoning.
3. **Action Agent** — files a real **GitHub Issue** with the anomaly data
   and diagnosis in a dedicated content-ops repo:
   [`signaldrop-content-ops`](https://github.com/ekpenyongasuquo/signaldrop-content-ops).

Each agent's real output feeds the next agent's real input — this is not
three scripts stitched together with hardcoded intermediate values.

## Data

The `viewing_events` ClickHouse table contains **synthetic** engagement
telemetry (`generate_synthetic_data.py`) with two deliberately engineered,
clearly labeled anomalies:
- A sharp, obvious `buffer_stall` spike (regional/device-specific — the
  primary demo scenario)
- A subtler `drop_off` pattern tied to a mismatched subtitle language (a
  localization-gap scenario, requiring real column correlation, not a
  single hardcoded check)

No real user or platform data is used anywhere in this project.

## Stack

- **ClickHouse Cloud** + official `mcp-clickhouse` MCP server (stdio
  transport)
- **Google Cloud** — Gemini (`gemini-3.5-flash`) via `google-genai`,
  Gemini Enterprise Agent Platform (formerly Vertex AI)
- **FastAPI** backend + a minimal single-page frontend
- **GitHub REST API** for the real Action Agent write

## Running it

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in your real ClickHouse, Google Cloud, and GitHub values
uvicorn main:app --reload --port 8000
```

Open `http://127.0.0.1:8000`, click **"Run Detection Pipeline"** — this
triggers a real, live run of all three agents.

### Setup scripts (run once, in order, before the app)

```bash
python create_table.py            # creates the viewing_events table
python generate_synthetic_data.py # seeds synthetic telemetry with 2 labeled anomalies
```

## Known limitations

- Anomaly detection uses a single z-score query over one metric
  (`buffer_stall`); a production system would monitor multiple engagement
  signals and correlate across them.
- The Diagnosis Agent's category list is fixed and prompt-defined, not
  learned from historical incident outcomes.
- The Action Agent files one Issue per run with no deduplication against
  already-open Issues for the same anomaly — a production version would
  need that.
- `CLICKHOUSE_ALLOW_WRITE_ACCESS` is only needed for the one-time setup
  scripts; the live app itself runs fully read-only against ClickHouse.

## License

MIT — see [LICENSE](./LICENSE).