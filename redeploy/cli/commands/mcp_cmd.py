"""redeploy mcp command — start the MCP server."""
from __future__ import annotations

import click


@click.command("mcp")
@click.option(
    "--transport", "-t",
    type=click.Choice(["stdio", "sse", "http"], case_sensitive=False),
    default="stdio",
    show_default=True,
    help="Transport: stdio (for IDE/Claude Desktop), sse or http (remote HTTP).",
)
@click.option(
    "--host",
    default="0.0.0.0",
    show_default=True,
    help="Bind host for sse/http transports.",
)
@click.option(
    "--port", "-p",
    default=8811,
    show_default=True,
    help="Bind port for sse/http transports.",
)
def mcp_cmd(transport: str, host: str, port: int) -> None:
    """Start the redeploy MCP server.

    \b
    Transports:
      stdio  -- for Claude Desktop / VS Code MCP integration (default)
      sse    -- HTTP Server-Sent Events on http://HOST:PORT/sse
      http   -- Streamable HTTP on http://HOST:PORT/mcp

    \b
    Examples:
        redeploy mcp                          # stdio, for MCP clients
        redeploy mcp --transport sse          # SSE on :8811
        redeploy mcp --transport sse --port 9000

    \b
    Claude Desktop config (~/.config/claude/claude_desktop_config.json):
        {
          "mcpServers": {
            "redeploy": {
              "command": "redeploy",
              "args": ["mcp"]
            }
          }
        }
    """
    from redeploy.mcp_server import serve
    serve(transport=transport, host=host, port=port)
