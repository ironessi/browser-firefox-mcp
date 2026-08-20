"""Smoke tests for browser-firefox-mcp MCP server."""

from __future__ import annotations


def test_import_core_modules() -> None:
    """Verify all core modules import without errors."""
    from core.engine import Engine
    from core.page import PageOps, navigate
    from core.security import SecurityOps
    from core.session import SessionOps
    from core.network import NetworkOps
    from core.recon import ReconOps
    print("  ✓ All core modules imported successfully")


def test_mcp_tools_registered() -> None:
    """Verify all expected tools are registered in the MCP server."""
    from mcp.server import mcp_server

    expected_tools = [
        "navigate", "go_back", "go_forward", "reload_page",
        "click", "click_text", "fill_input", "press_key", "upload_file",
        "read_page", "get_text", "js_eval", "screenshot", "wait_for_selector",
        "inject_xss_payload", "inject_payload", "find_reflection", "get_url_params",
        "get_cookies", "set_cookie", "set_cookies", "delete_cookie", "clear_cookies",
        "get_session_info", "get_storage_data", "set_storage_item",
        "export_state", "import_state",
        "start_network_capture", "stop_network_capture", "get_network_summary", "block_urls",
        "recon_technology_stack", "find_sensitive_data", "dom_analysis",
        "enumerate_forms", "enumerate_links", "security_headers_check",
        "close_browser", "new_context", "list_contexts",
    ]

    # Access the internal tool registry
    tools = mcp_server._tool_manager.list_tools() if hasattr(mcp_server, "_tool_manager") else []
    tool_names = [t.name for t in tools] if tools else []

    missing = [name for name in expected_tools if name not in tool_names]
    assert not missing, f"Missing tools: {missing}"
    print(f"  ✓ All {len(expected_tools)} tools registered")


if __name__ == "__main__":
    test_import_core_modules()
    test_mcp_tools_registered()
    print("\n✓ All smoke tests passed!")
