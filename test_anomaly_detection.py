"""
test_anomaly_detection.py

Runs the core Analyst Agent query directly through the verified MCP
connection, to confirm it actually finds the primary anomaly before any
agent framework is built around it.
"""

import asyncio
import os
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

# Finds hours where buffer_stall rate for a given (title, region, device)
# combo is far above that combo's own overall average -- a real anomaly
# detection query, not a hardcoded lookup for "Nova Horizon".
ANOMALY_QUERY = """
WITH hourly AS (
    SELECT
        content_title,
        region,
        device_type,
        toStartOfHour(event_time) AS hour,
        countIf(event_type = 'buffer_stall') AS stall_count,
        count() AS total_events
    FROM viewing_events
    GROUP BY content_title, region, device_type, hour
),
baseline AS (
    SELECT
        content_title, region, device_type,
        avg(stall_count) AS avg_stalls,
        stddevPop(stall_count) AS stddev_stalls
    FROM hourly
    GROUP BY content_title, region, device_type
)
SELECT
    h.content_title,
    h.region,
    h.device_type,
    h.hour,
    h.stall_count,
    b.avg_stalls,
    (h.stall_count - b.avg_stalls) / nullif(b.stddev_stalls, 0) AS z_score
FROM hourly h
JOIN baseline b USING (content_title, region, device_type)
WHERE h.stall_count > 0 AND b.stddev_stalls > 0
ORDER BY z_score DESC
LIMIT 5
"""


async def main():
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("=== Running anomaly detection query ===")
            result = await session.call_tool("run_query", {"query": ANOMALY_QUERY})
            for item in result.content:
                print(item.text if hasattr(item, "text") else item)


if __name__ == "__main__":
    asyncio.run(main())