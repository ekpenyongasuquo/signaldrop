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
    "CLICKHOUSE_ALLOW_DROP": "true",
}
server_params = StdioServerParameters(command="mcp-clickhouse", args=[], env=env)


async def main():
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("run_query", {"query": "TRUNCATE TABLE viewing_events"})
            for item in result.content:
                print(item.text if hasattr(item, "text") else item)
            print("Table truncated.")


if __name__ == "__main__":
    asyncio.run(main())