"""
test_mcp_connection.py

Verifies the official mcp-clickhouse server using the pattern documented
directly by ClickHouse (stdio transport, not HTTP) -- see
https://clickhouse.com/docs/use-cases/AI/MCP/ai-agent-libraries/streamlit-agent
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
    "CLICKHOUSE_MCP_SERVER_TRANSPORT": "stdio",  # force stdio, not the HTTP default
}

server_params = StdioServerParameters(
    command="mcp-clickhouse",  # the console entry point installed by pip
    args=[],
    env=env,
)


async def main():
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("=== Session initialized ===")

            tools = await session.list_tools()
            print("=== Available tools ===")
            for t in tools.tools:
                print(f"- {t.name}: {t.description}")

            print("\n=== Listing databases (real call, real data) ===")
            result = await session.call_tool("list_databases", {})
            for item in result.content:
                print(item.text if hasattr(item, "text") else item)


if __name__ == "__main__":
    asyncio.run(main())