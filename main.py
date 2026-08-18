"""
main.py

SignalDrop: a real, end-to-end three-agent pipeline.

1. Analyst Agent  -> queries the REAL ClickHouse Cloud service via the
   official mcp-clickhouse server (stdio) to find the top statistically
   anomalous (title, region, device, hour) combination.
2. Diagnosis Agent -> feeds that REAL result into Gemini (via
   google-genai on Vertex AI / Gemini Enterprise Agent Platform) to
   propose a probable root cause.
3. Action Agent    -> files a REAL GitHub Issue in a dedicated repo,
   containing the real anomaly data and the real diagnosis.

No hardcoded intermediate values -- each agent's real output becomes the
next agent's real input.
"""

import os
import json
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
import requests
from google import genai
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()

app = FastAPI()

# --- Config -----------------------------------------------------------
CLICKHOUSE_ENV = {
    "CLICKHOUSE_HOST": os.environ["CLICKHOUSE_HOST"],
    "CLICKHOUSE_PORT": os.environ["CLICKHOUSE_PORT"],
    "CLICKHOUSE_USER": os.environ["CLICKHOUSE_USER"],
    "CLICKHOUSE_PASSWORD": os.environ["CLICKHOUSE_PASSWORD"],
    "CLICKHOUSE_SECURE": os.environ.get("CLICKHOUSE_SECURE", "true"),
    "CLICKHOUSE_MCP_SERVER_TRANSPORT": "stdio",
    "CLICKHOUSE_ALLOW_WRITE_ACCESS": "false",  # read-only for the live pipeline
}
CLICKHOUSE_SERVER_PARAMS = StdioServerParameters(command="mcp-clickhouse", args=[], env=CLICKHOUSE_ENV)

GEMINI_PROJECT = os.environ["GOOGLE_CLOUD_PROJECT"]
GEMINI_LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")
gemini_client = genai.Client(vertexai=True, project=GEMINI_PROJECT, location=GEMINI_LOCATION)

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
GITHUB_REPO = os.environ.get("GITHUB_REPO", "ekpenyongasuquo/signaldrop-content-ops")

ANOMALY_QUERY = """
WITH hourly AS (
    SELECT
        content_title, region, device_type,
        toStartOfHour(event_time) AS hour,
        countIf(event_type = 'buffer_stall') AS stall_count,
        count() AS total_events
    FROM viewing_events
    GROUP BY content_title, region, device_type, hour
),
baseline AS (
    SELECT content_title, region, device_type,
        avg(stall_count) AS avg_stalls, stddevPop(stall_count) AS stddev_stalls
    FROM hourly GROUP BY content_title, region, device_type
)
SELECT h.content_title, h.region, h.device_type, h.hour, h.stall_count,
    b.avg_stalls, (h.stall_count - b.avg_stalls) / nullif(b.stddev_stalls, 0) AS z_score
FROM hourly h JOIN baseline b USING (content_title, region, device_type)
WHERE h.stall_count > 0 AND b.stddev_stalls > 0
ORDER BY z_score DESC LIMIT 1
"""


# --- Agent 1: Analyst ---------------------------------------------------
async def run_analyst_agent() -> dict:
    async with stdio_client(CLICKHOUSE_SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("run_query", {"query": ANOMALY_QUERY})
            raw_text = result.content[0].text if result.content else "{}"
            parsed = json.loads(raw_text)
            if not parsed.get("rows"):
                raise HTTPException(404, "No anomaly found in current data.")
            cols = parsed["columns"]
            row = parsed["rows"][0]
            return dict(zip(cols, row))


# --- Agent 2: Diagnosis --------------------------------------------------
DIAGNOSIS_PROMPT_TEMPLATE = """You are a streaming platform content-operations diagnosis agent.
An anomaly detection query found the following statistically significant
spike in an engagement telemetry table:

{anomaly}

This spike is in buffer_stall events specifically, isolated to one title,
one region, and one device type, clustered in a single hour.

Propose the single most likely root cause category from this list, and
explain your reasoning in 2-3 sentences:
- regional_cdn_or_technical_failure
- content_pacing_issue
- localization_gap
- device_specific_bug
- unknown_needs_investigation

Respond in this exact format:
CATEGORY: <one of the categories above>
REASONING: <your 2-3 sentence explanation>
"""


def run_diagnosis_agent(anomaly: dict) -> dict:
    prompt = DIAGNOSIS_PROMPT_TEMPLATE.format(anomaly=json.dumps(anomaly, indent=2))
    response = gemini_client.models.generate_content(model="gemini-3.5-flash", contents=prompt)
    text = response.text.strip()

    category, reasoning = "unknown_needs_investigation", text
    for line in text.splitlines():
        if line.upper().startswith("CATEGORY:"):
            category = line.split(":", 1)[1].strip()
        elif line.upper().startswith("REASONING:"):
            reasoning = line.split(":", 1)[1].strip()
    return {"category": category, "reasoning": reasoning, "raw": text}


# --- Agent 3: Action -----------------------------------------------------
def run_action_agent(anomaly: dict, diagnosis: dict) -> dict:
    title = (
        f"[SignalDrop] Anomaly detected: {anomaly['content_title']} "
        f"({anomaly['region']}/{anomaly['device_type']}) at {anomaly['hour']}"
    )
    body = f"""## Detected anomaly (via ClickHouse Analyst Agent)

| Field | Value |
|---|---|
| Title | {anomaly['content_title']} |
| Region | {anomaly['region']} |
| Device | {anomaly['device_type']} |
| Hour | {anomaly['hour']} |
| Buffer stalls | {anomaly['stall_count']} (baseline avg: {anomaly['avg_stalls']}) |
| Z-score | {anomaly['z_score']} |

## Diagnosis (via Gemini Diagnosis Agent)

**Category:** `{diagnosis['category']}`

**Reasoning:** {diagnosis['reasoning']}

---
*Filed automatically by SignalDrop's Action Agent as part of a real,
end-to-end pipeline run -- not a manually written report.*
"""
    resp = requests.post(
        f"https://api.github.com/repos/{GITHUB_REPO}/issues",
        headers={"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"},
        json={"title": title, "body": body, "labels": ["signaldrop-auto", "content-ops"]},
    )
    resp.raise_for_status()
    issue = resp.json()
    return {"issue_url": issue["html_url"], "issue_number": issue["number"]}


# --- Orchestration ---------------------------------------------------------
@app.post("/run-detection")
async def run_detection():
    anomaly = await run_analyst_agent()
    diagnosis = run_diagnosis_agent(anomaly)
    action = run_action_agent(anomaly, diagnosis)
    return {"anomaly": anomaly, "diagnosis": diagnosis, "action": action}


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return """
<!DOCTYPE html>
<html>
<head>
<title>SignalDrop</title>
<style>
body { font-family: -apple-system, sans-serif; max-width: 700px; margin: 60px auto; padding: 0 20px; }
h1 { font-size: 1.5em; }
button { background: #111; color: white; border: none; padding: 12px 24px; font-size: 1em; border-radius: 6px; cursor: pointer; }
button:disabled { background: #999; }
#result { margin-top: 30px; white-space: pre-wrap; background: #f5f5f5; padding: 20px; border-radius: 6px; display: none; }
.step { margin: 10px 0; padding: 10px; border-left: 3px solid #ddd; }
.step.done { border-left-color: #22c55e; }
a { color: #2563eb; }
</style>
</head>
<body>
<h1>SignalDrop</h1>
<p>Real-time content QC anomaly detection for streaming platforms.</p>
<button onclick="run()" id="btn">Run Detection Pipeline</button>
<div id="result"></div>
<script>
async function run() {
    const btn = document.getElementById('btn');
    const result = document.getElementById('result');
    btn.disabled = true;
    btn.textContent = 'Running (Analyst -> Diagnosis -> Action)...';
    result.style.display = 'block';
    result.textContent = 'Querying ClickHouse for anomalies...';
    try {
        const resp = await fetch('/run-detection', { method: 'POST' });
        const data = await resp.json();
        result.innerHTML =
            '<div class="step done"><b>1. Analyst Agent (ClickHouse)</b><br>' +
            JSON.stringify(data.anomaly, null, 2) + '</div>' +
            '<div class="step done"><b>2. Diagnosis Agent (Gemini)</b><br>Category: ' +
            data.diagnosis.category + '<br>' + data.diagnosis.reasoning + '</div>' +
            '<div class="step done"><b>3. Action Agent (GitHub)</b><br>Issue filed: ' +
            '<a href="' + data.action.issue_url + '" target="_blank">' + data.action.issue_url + '</a></div>';
    } catch (e) {
        result.textContent = 'Error: ' + e;
    }
    btn.disabled = false;
    btn.textContent = 'Run Detection Pipeline';
}
</script>
</body>
</html>
"""