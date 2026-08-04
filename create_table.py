"""
create_table.py

Creates the viewing_events table on the real ClickHouse Cloud service,
via the official mcp-clickhouse server's run_query tool -- same verified
stdio connection pattern as test_mcp_connection.py.
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

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS viewing_events (
    event_time DateTime,
    content_id String,
    content_title String,
    region String,
    device_type String,
    subtitle_language String,
    playback_position_seconds UInt32,
    event_type Enum8('play' = 1, 'pause' = 2, 'rewind' = 3, 'drop_off' = 4, 'buffer_stall' = 5),
    session_id String
) ENGINE = MergeTree()
ORDER BY (content_id, event_time)
"""


async def main():
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            print("=== Creating viewing_events table ===")
            result = await session.call_tool("run_query", {"query": CREATE_TABLE_SQL})
            for item in result.content:
                print(item.text if hasattr(item, "text") else item)

            print("\n=== Verifying: listing tables in 'default' ===")
            result = await session.call_tool("list_tables", {"database": "default"})
            for item in result.content:
                print(item.text if hasattr(item, "text") else item)


if __name__ == "__main__":
    asyncio.run(main())