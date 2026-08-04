"""
generate_synthetic_data.py

Generates clearly-labeled SYNTHETIC streaming engagement data for
SignalDrop, with two deliberate, documented anomalies:

1. PRIMARY anomaly: a sharp buffer_stall spike -- title "Nova Horizon",
   region DE, device smart_tv, clustered around 2026-08-01 20:32 UTC.
   Story: a regional CDN/technical failure. Obvious, single-query
   detectable -- the demo's main narrative beat.

2. SECONDARY anomaly: a subtler drop_off spike -- title "Coastal Static",
   region BR, subtitle_language mismatched (pt-PT instead of pt-BR),
   spread across a wider time window with a smaller effect size.
   Story: a localization gap. Requires correlating event_type with
   subtitle_language, not just counting one column -- proves the
   Analyst Agent does real correlation, not a single hardcoded check.

This is NOT real user data. No real streaming platform, title, or user
was involved. All values are fabricated for demo purposes only.
"""

import asyncio
import os
import random
import uuid
from datetime import datetime, timedelta
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()

env = {
    "CLICKHOUSE_HOST": os.environ["CLICKHOUSE_HOST"],
    "CLICKHOUSE_PORT": os.environ["CLICKHOUSE_PORT"],
    "CLICKHOUSE_USER": os.environ["CLICKHOUSE_USER"],
    "CLICKHOUSE_PASSWORD": os.environ["CLICKHOUSE_PASSWORD"],
    "CLICKHOUSE_SECURE": os.environ.get("CLICKHOUSE_SECURE", "true"),
    "CLICKHOUSE_MCP_SERVER_TRANSPORT": "stdio",
    "CLICKHOUSE_ALLOW_WRITE_ACCESS": "true",
}
server_params = StdioServerParameters(command="mcp-clickhouse", args=[], env=env)

TITLES = ["Nova Horizon", "Coastal Static", "Midnight Freight", "Glasshouse", "The Long Dusk"]
REGIONS = ["US", "DE", "BR", "JP"]
DEVICES = ["smart_tv", "mobile", "web", "console"]
BASE_TIME = datetime(2026, 8, 1, 18, 0, 0)


def esc(s: str) -> str:
    return s.replace("'", "''")


def make_row(event_time, content_id, content_title, region, device_type,
             subtitle_language, position, event_type, session_id):
    return (
        f"('{event_time.strftime('%Y-%m-%d %H:%M:%S')}', "
        f"'{esc(content_id)}', '{esc(content_title)}', '{region}', '{device_type}', "
        f"'{subtitle_language}', {position}, '{event_type}', '{session_id}')"
    )


def generate_baseline(n_sessions=800):
    rows = []
    for _ in range(n_sessions):
        title = random.choice(TITLES)
        region = random.choice(REGIONS)
        device = random.choice(DEVICES)
        subtitle = {"US": "en-US", "DE": "de-DE", "BR": "pt-BR", "JP": "ja-JP"}[region]
        session_id = str(uuid.uuid4())[:8]
        start = BASE_TIME + timedelta(minutes=random.randint(0, 4320))  # spread over 3 days

        # Normal funnel: play -> a few pauses/rewinds -> most finish, some drop off naturally
        rows.append(make_row(start, title, title, region, device, subtitle, 0, "play", session_id))
        watched = random.randint(300, 2700)  # 5-45 min watched
        if random.random() < 0.15:
            rows.append(make_row(start + timedelta(seconds=watched // 2), title, title, region,
                                  device, subtitle, watched // 2, "pause", session_id))
        if random.random() < 0.20:
            rows.append(make_row(start + timedelta(seconds=watched), title, title, region,
                                  device, subtitle, watched, "drop_off", session_id))
    return rows


def generate_primary_anomaly(n_sessions=180):
    """Sharp buffer_stall spike: Nova Horizon, DE, smart_tv, clustered at one timestamp."""
    rows = []
    spike_time = BASE_TIME + timedelta(days=1, hours=2, minutes=32)  # 2026-08-02 20:32
    for _ in range(n_sessions):
        session_id = str(uuid.uuid4())[:8]
        jitter = timedelta(seconds=random.randint(-90, 90))  # tight cluster around spike_time
        t = spike_time + jitter
        rows.append(make_row(t, "Nova Horizon", "Nova Horizon", "DE", "smart_tv",
                              "de-DE", random.randint(600, 900), "play", session_id))
        rows.append(make_row(t + timedelta(seconds=5), "Nova Horizon", "Nova Horizon", "DE",
                              "smart_tv", "de-DE", random.randint(605, 905), "buffer_stall", session_id))
        rows.append(make_row(t + timedelta(seconds=20), "Nova Horizon", "Nova Horizon", "DE",
                              "smart_tv", "de-DE", random.randint(610, 910), "drop_off", session_id))
    return rows


def generate_secondary_anomaly(n_sessions=25):
    """Subtler drop_off spike tied to mismatched subtitle language: Coastal Static, BR."""
    rows = []
    for _ in range(n_sessions):
        session_id = str(uuid.uuid4())[:8]
        t = BASE_TIME + timedelta(hours=random.randint(0, 60))  # spread wider, less obvious
        rows.append(make_row(t, "Coastal Static", "Coastal Static", "BR", "mobile",
                              "pt-PT", 0, "play", session_id))  # note: pt-PT, not pt-BR -- the bug
        if random.random() < 0.55:  # elevated but not as dramatic as the primary spike
            rows.append(make_row(t + timedelta(seconds=random.randint(60, 300)), "Coastal Static",
                                  "Coastal Static", "BR", "mobile", "pt-PT",
                                  random.randint(60, 300), "drop_off", session_id))
    return rows


async def insert_rows(session, rows, label):
    if not rows:
        return
    batch_size = 200
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        sql = (
            "INSERT INTO viewing_events "
            "(event_time, content_id, content_title, region, device_type, "
            "subtitle_language, playback_position_seconds, event_type, session_id) VALUES "
            + ", ".join(batch)
        )
        result = await session.call_tool("run_query", {"query": sql})
        print(f"[{label}] inserted batch {i // batch_size + 1} ({len(batch)} rows)")


async def main():
    random.seed(42)  # reproducible synthetic data
    baseline = generate_baseline()
    primary = generate_primary_anomaly()
    secondary = generate_secondary_anomaly()

    print(f"Generated: {len(baseline)} baseline, {len(primary)} primary-anomaly, "
          f"{len(secondary)} secondary-anomaly rows (all synthetic).")

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            await insert_rows(session, baseline, "baseline")
            await insert_rows(session, primary, "primary-anomaly")
            await insert_rows(session, secondary, "secondary-anomaly")

            print("\n=== Verifying total row count ===")
            result = await session.call_tool("run_query", {"query": "SELECT count() FROM viewing_events"})
            for item in result.content:
                print(item.text if hasattr(item, "text") else item)


if __name__ == "__main__":
    asyncio.run(main())