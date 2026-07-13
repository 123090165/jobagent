# Learning Search MCP Server

This local Streamable HTTP MCP server exposes a `search` tool backed by Tavily.
JobAgent uses it only to retrieve learning links for interview-preparation skill
gaps.

## Configuration

Keep the local values in the repository root `.env.deepseek.local`:

```env
TAVILY_API_KEY=tvly-your-key
JOBAGENT_LEARNING_MCP_URL=http://127.0.0.1:8001/mcp
JOBAGENT_LEARNING_MCP_TOOL=search
JOBAGENT_LEARNING_MCP_QUERY_ARGUMENT=query
JOBAGENT_LEARNING_MCP_HOST=127.0.0.1
JOBAGENT_LEARNING_MCP_PORT=8001
TAVILY_TIMEOUT_SECONDS=15
```

The local environment file is ignored by Git. Never put a real key in
`.env.example`.

## Run

From the repository root, with the project virtual environment activated:

```powershell
python -m mcp_servers.learning_search.server
```

The MCP endpoint is `http://127.0.0.1:8001/mcp`. Start this process separately
from the JobAgent FastAPI backend. If it is unavailable, preparation generation
continues with the small built-in official catalog.

The server requests bounded Tavily results and excludes common social/video
domains. Returned items are normalized to title, URL, snippet, and source; only
HTTP(S) links are accepted.
