"""MCP server entry point for cyberstrikeai integration."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("cyberstrike-firefox")
