"""
test_diagnosis_agent.py

Verifies the real Gemini call via google-genai (Vertex AI / Gemini
Enterprise Agent Platform) before wiring it into the full pipeline.
Feeds it the actual anomaly row found by the Analyst Agent's ClickHouse
query, and asks it to propose a probable cause -- a real correlation
task, not a canned response.

Requires: pip install google-genai
Requires: gcloud auth application-default login already completed
          (confirmed working earlier in this project).
"""

import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

PROJECT_ID = os.environ["GOOGLE_CLOUD_PROJECT"]
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")

client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)

# This is the REAL row returned by test_anomaly_detection.py -- not
# invented. Feeding the actual detected anomaly to Gemini, not a
# hypothetical, so this test proves real correlation reasoning.
ANOMALY_ROW = {
    "content_title": "Nova Horizon",
    "region": "DE",
    "device_type": "smart_tv",
    "hour": "2026-08-02 20:00:00",
    "stall_count": 180,
    "avg_stalls": 18.0,
    "z_score": 3.0,
}

PROMPT = f"""You are a streaming platform content-operations diagnosis agent.
An anomaly detection query found the following statistically significant
spike in an engagement telemetry table:

{ANOMALY_ROW}

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


def main():
    response = client.models.generate_content(
        model="gemini-3.5-flash",
        contents=PROMPT,
    )
    print("=== Gemini Diagnosis ===")
    print(response.text)


if __name__ == "__main__":
    main()