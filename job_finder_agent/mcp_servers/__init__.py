"""
mcp_servers package — thin clients for external MCP servers.

Transport is configured via config.JOBSPY_TRANSPORT (or env JOBSPY_TRANSPORT):
  "sse"   → HTTP POST to JOBSPY_SSE_URL/api (default)
  "stdio" → spawn MCP server subprocess via Python MCP client
"""
