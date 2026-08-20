"""MCP server — FastMCP-wrapped tool registry for cyberstrikeai.

Start via:  python -m mcp.server
Or:        browser-firefox-mcp
All tools communicate via JSON-RPC over stdio (MCP spec).
"""

from __future__ import annotations

import logging
import sys
from typing import Any, Optional

# ---------------------------------------------------------------- logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("cyberstrike-firefox")

# --- singleton runtime ------------------------------------------------------


class _Runtime:
    """Holds Engine + all ops modules for the current MCP session.

    Created lazily on first tool call; shut down by ``close_browser()``.
    """

    def __init__(self) -> None:
        # Deferred imports to avoid circular deps during module load
        from core.engine import Engine
        from core.page import PageOps
        from core.security import SecurityOps
        from core.session import SessionOps
        from core.network import NetworkOps
        from core.recon import ReconOps

        self.engine = Engine()
        # Will be set on first page creation
        self.page_ops: Optional[PageOps] = None
        self.security_ops: Optional[SecurityOps] = None
        self.session_ops: Optional[SessionOps] = None
        self.network_ops: Optional[NetworkOps] = None
        self.recon_ops: Optional[ReconOps] = None

    def _init_for_page(self) -> None:
        """Attach all ops wrappers to the current page."""
        from core.page import PageOps
        from core.security import SecurityOps
        from core.session import SessionOps
        from core.network import NetworkOps
        from core.recon import ReconOps

        ctx = self.engine.current_context()
        page = ctx.new_page()
        self.page_ops = PageOps(page, self.engine)
        self.security_ops = SecurityOps(page)
        self.session_ops = SessionOps(ctx, page)
        self.network_ops = NetworkOps(page)
        self.recon_ops = ReconOps(page)


_rt: Optional[_Runtime] = None


def _ensure() -> _Runtime:
    """Return the global runtime, creating + booting the browser if needed."""
    global _rt
    if _rt is None or not _rt.engine.is_alive:
        _rt = _Runtime()
        _rt.engine.start()
    return _rt


def _boot_page() -> _Runtime:
    """Ensure runtime exists AND has a ready page (ops initialized)."""
    rt = _ensure()
    if rt.page_ops is None:
        rt._init_for_page()
    return rt


# ================================================================ MCP setup
# Must come AFTER _Runtime class definition

from mcp.server.fastmcp import FastMCP

mcp_server = FastMCP("cyberstrike-firefox")


# ============================================================= navigation


@mcp_server.tool()
def navigate(url: str, timeout_ms: int = 30_000) -> dict:
    """Navigate to a URL. Returns final url, title, and HTTP status."""
    rt = _boot_page()
    return rt.page_ops.navigate(url, timeout_ms=timeout_ms)


@mcp_server.tool()
def go_back() -> dict:
    """Navigate back in history."""
    rt = _boot_page()
    return rt.page_ops.go_back()


@mcp_server.tool()
def go_forward() -> dict:
    """Navigate forward in history."""
    rt = _boot_page()
    return rt.page_ops.go_forward()


@mcp_server.tool()
def reload_page() -> dict:
    """Reload the current page."""
    rt = _boot_page()
    return rt.page_ops.reload()


# =========================================================== element ops


@mcp_server.tool()
def click(selector: str, timeout: int = 5000) -> dict:
    """Click an element identified by CSS selector."""
    rt = _boot_page()
    return rt.page_ops.click(selector, timeout=timeout)


@mcp_server.tool()
def click_text(text: str, timeout: int = 5000) -> dict:
    """Click the first node whose visible text contains *text*."""
    rt = _boot_page()
    return rt.page_ops.click_text(text, timeout=timeout)


@mcp_server.tool()
def fill_input(selector: str, value: str, clear_first: bool = True,
               timeout: int = 5000) -> dict:
    """Fill a form field with the given value. Fires framework-compatible events."""
    rt = _boot_page()
    return rt.page_ops.fill_input(selector, value, clear_first=clear_first,
                                  timeout=timeout)


@mcp_server.tool()
def press_key(key: str) -> dict:
    """Press a keyboard key or key combination (e.g. 'Enter', 'Control+a')."""
    rt = _boot_page()
    return rt.page_ops.press_key(key)


@mcp_server.tool()
def upload_file(selector: str, file_paths: list[str]) -> dict:
    """Upload file(s) to a file input element."""
    rt = _boot_page()
    return rt.page_ops.upload_file(selector, file_paths)


# ============================================================ content reads


@mcp_server.tool()
def read_page() -> dict:
    """Read the full page: DOM HTML + metadata summary."""
    rt = _boot_page()
    po = rt.page_ops
    return {
        "url": po.page.url,
        "title": po.page.title(),
        "html_length": len(po.get_content()),
        "text_preview": po.get_text()[:2000],
        "page_info": po.page_info(),
    }


@mcp_server.tool()
def get_text(selector: str = "body") -> str:
    """Extract visible text under the given CSS selector."""
    rt = _boot_page()
    return rt.page_ops.get_text(selector)


@mcp_server.tool()
def get_attribute(selector: str, name: str) -> Optional[str]:
    """Get an attribute value from an element."""
    rt = _boot_page()
    return rt.page_ops.get_attribute(selector, name)


@mcp_server.tool()
def js_eval(expression: str) -> Any:
    """Execute JavaScript expression and return result. Use with caution."""
    rt = _boot_page()
    return rt.page_ops.js_evaluate(expression)


@mcp_server.tool()
def wait_for_selector(selector: str, timeout_ms: int = 10_000) -> bool:
    """Wait for an element to appear. Returns True when found."""
    rt = _boot_page()
    return rt.page_ops.wait_for_selector(selector, timeout_ms=timeout_ms)


@mcp_server.tool()
def screenshot(full_page: bool = False, path: Optional[str] = None) -> Optional[str]:
    """Take a screenshot. Returns base64 string, or saves to *path*."""
    rt = _boot_page()
    return rt.page_ops.screenshot(full_page=full_page, path=path)


# ========================================================== security tools


@mcp_server.tool()
def inject_xss_payload(selector: str, payloads: Optional[list[str]] = None,
                       clear_first: bool = True) -> dict:
    """Inject XSS probes into a target input/textarea and check for reflection.

    Tests common payload vectors (SVG onload, img onerror, script tags, etc.)
    against the specified form field and reports which ones were reflected.
    """
    rt = _boot_page()
    assert rt.security_ops is not None
    return rt.security_ops.inject_xss_payload(
        selector, payloads=payloads, clear_first=clear_first,
    )


@mcp_server.tool()
def inject_payload(selector: str, payload: str) -> dict:
    """Inject a single custom payload into a target element and verify reflection.

    Use for targeted fuzzing after manual discovery. Returns reflection analysis.
    """
    rt = _boot_page()
    assert rt.security_ops is not None
    rt.security_ops.inject_xss_payload(selector, payloads=[payload], clear_first=True)
    return rt.security_ops.inject_xss_reflective(payload)


@mcp_server.tool()
def find_reflection(text: str) -> dict:
    """Check whether *text* was reflected in the current page DOM."""
    rt = _boot_page()
    assert rt.security_ops is not None
    return rt.security_ops.inject_xss_reflective(text)


@mcp_server.tool()
def get_url_params() -> dict:
    """Extract and list all URL query parameters."""
    rt = _boot_page()
    assert rt.security_ops is not None
    return rt.security_ops.get_url_params()


# ========================================================= session management


@mcp_server.tool()
def get_cookies(domains: Optional[list[str]] = None) -> list[dict]:
    """List all cookies, optionally filtered by domain patterns."""
    rt = _boot_page()
    assert rt.session_ops is not None
    return rt.session_ops.get_cookies(domains=domains)


@mcp_server.tool()
def set_cookie(name: str, value: str, domain: str = ".localhost",
               path: str = "/", secure: bool = False,
               http_only: bool = False, same_site: str = "Lax") -> dict:
    """Set a single cookie. Useful for session token replay attacks."""
    rt = _boot_page()
    assert rt.session_ops is not None
    return rt.session_ops.set_cookie(
        name, value, domain=domain, path=path,
        secure=secure, http_only=http_only, same_site=same_site,
    )


@mcp_server.tool()
def set_cookies(cookies: list[dict]) -> dict:
    """Bulk-inject cookies from external sources (e.g., Burp export)."""
    rt = _boot_page()
    assert rt.session_ops is not None
    return rt.session_ops.set_cookies(cookies)


@mcp_server.tool()
def delete_cookie(name: str, domain: str = ".localhost",
                  path: str = "/") -> dict:
    """Remove a specific cookie by name."""
    rt = _boot_page()
    assert rt.session_ops is not None
    return rt.session_ops.delete_cookie(name, domain=domain, path=path)


@mcp_server.tool()
def clear_cookies() -> dict:
    """Clear all cookies for the current context."""
    rt = _boot_page()
    assert rt.session_ops is not None
    return rt.session_ops.clear_cookies()


@mcp_server.tool()
def get_session_info() -> dict:
    """Full session snapshot: cookies + storage + detected tokens."""
    rt = _boot_page()
    assert rt.session_ops is not None
    return rt.session_ops.get_session_info()


@mcp_server.tool()
def get_storage_data() -> dict:
    """Dump localStorage and sessionStorage contents."""
    rt = _boot_page()
    assert rt.session_ops is not None
    return rt.session_ops.get_storage_data()


@mcp_server.tool()
def set_storage_item(key: str, value: str, store: str = "localStorage") -> dict:
    """Write a key-value pair to localStorage or sessionStorage."""
    rt = _boot_page()
    assert rt.session_ops is not None
    return rt.session_ops.set_storage_item(key, value, store=store)


@mcp_server.tool()
def export_state(path: str) -> dict:
    """Save full browser state (cookies + storage) to a file for later reuse."""
    rt = _boot_page()
    assert rt.session_ops is not None
    return rt.session_ops.export_state(path)


@mcp_server.tool()
def import_state(path: str) -> dict:
    """Restore browser state from a previously saved file."""
    rt = _boot_page()
    assert rt.session_ops is not None
    return rt.session_ops.import_state(path)


# ========================================================== network capture


@mcp_server.tool()
def start_network_capture() -> dict:
    """Begin capturing all HTTP(S) requests/responses on the current page."""
    rt = _boot_page()
    assert rt.network_ops is not None
    return rt.network_ops.start_capture()


@mcp_server.tool()
def stop_network_capture() -> dict:
    """Stop capturing and report totals."""
    rt = _boot_page()
    assert rt.network_ops is not None
    return rt.network_ops.stop_capture()


@mcp_server.tool()
def get_network_summary(resource_types: Optional[list[str]] = None,
                        status_filter: Optional[int] = None) -> dict:
    """Get a filtered summary of captured network traffic."""
    rt = _boot_page()
    assert rt.network_ops is not None
    return rt.network_ops.get_capture_summary(
        resource_types=resource_types, status_filter=status_filter,
    )


@mcp_server.tool()
def block_urls(patterns: list[str]) -> dict:
    """Block navigations matching glob-style URL patterns."""
    rt = _boot_page()
    assert rt.network_ops is not None
    return rt.network_ops.block_urls(patterns)


# =========================================================== recon tools


@mcp_server.tool()
def recon_technology_stack() -> dict:
    """Detect technologies/frameworks/CMS used on the current page."""
    rt = _boot_page()
    assert rt.recon_ops is not None
    return rt.recon_ops.tech_stack()


@mcp_server.tool()
def find_sensitive_data() -> dict:
    """Scan page HTML and text for leaked secrets, keys, tokens, credentials."""
    rt = _boot_page()
    assert rt.recon_ops is not None
    return rt.recon_ops.find_sensitive_data()


@mcp_server.tool()
def dom_analysis() -> dict:
    """Extract structural summary of the DOM tree (tag counts, forms, links, etc.)."""
    rt = _boot_page()
    assert rt.recon_ops is not None
    return rt.recon_ops.dom_analysis()


@mcp_server.tool()
def enumerate_forms() -> dict:
    """List all forms with actions, methods, and field details."""
    rt = _boot_page()
    assert rt.recon_ops is not None
    return rt.recon_ops.enumerate_forms()


@mcp_server.tool()
def enumerate_links(relative_only: bool = True) -> dict:
    """List all hyperlinks on the page."""
    rt = _boot_page()
    assert rt.recon_ops is not None
    return rt.recon_ops.enumerate_links(relative_only=relative_only)


@mcp_server.tool()
def security_headers_check() -> dict:
    """Check for common security headers and meta-based protections."""
    rt = _boot_page()
    assert rt.recon_ops is not None
    return rt.recon_ops.security_headers_check()


# =========================================================== lifecycle


@mcp_server.tool()
def close_browser() -> dict:
    """Close the browser and release resources. Next tool call reboots."""
    global _rt
    if _rt:
        _rt.engine.stop()
    _rt = None
    return {"status": "closed"}


@mcp_server.tool()
def new_context(proxy: Optional[dict] = None) -> dict:
    """Create a new isolated browser context (separate cookie jar).

    Switches working context to the new one. Previous contexts remain alive
    until closed by ``close_browser()``.
    """
    rt = _ensure()
    ctx = rt.engine.new_context(proxy=proxy)
    page = ctx.new_page()
    from core.page import PageOps
    from core.security import SecurityOps
    from core.session import SessionOps
    from core.network import NetworkOps
    from core.recon import ReconOps

    rt.page_ops = PageOps(page, rt.engine)
    rt.security_ops = SecurityOps(page)
    rt.session_ops = SessionOps(ctx, page)
    rt.network_ops = NetworkOps(page)
    rt.recon_ops = ReconOps(page)
    return {"status": "new_context", "url": page.url}


@mcp_server.tool()
def list_contexts() -> dict:
    """List all active browser contexts."""
    rt = _ensure()
    return {"context_count": len(rt.engine._contexts)}


# =============================================================== main


def main() -> None:
    """Entry point — runs the MCP server over stdio."""
    logger.info("Starting cyberstrike-firefox MCP server")
    mcp_server.run(transport="stdio")


if __name__ == "__main__":
    main()
