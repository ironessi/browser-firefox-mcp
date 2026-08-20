"""Server entry point — registers all MCP tools and runs over stdio.

This is the ONLY file needed at the package root level.
All business logic lives in the ``core/`` subdirectory.
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("firefx-server")

# --- singleton runtime ------------------------------------------------------


class _Runtime:
    """Holds Engine + all ops modules for the current session."""

    def __init__(self) -> None:
        from core.engine import Engine
        from core.page import PageOps
        from core.security import SecurityOps
        from core.session import SessionOps
        from core.network import NetworkOps
        from core.recon import ReconOps

        self.engine = Engine()
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
    global _rt
    if _rt is None or not _rt.engine.is_alive:
        _rt = _Runtime()
        _rt.engine.start()
    return _rt


def _boot_page() -> _Runtime:
    rt = _ensure()
    if rt.page_ops is None:
        rt._init_for_page()
    return rt


# =================================================================== tools


# -- navigation --------------------------------------------------------------

TOOL_NAVIGATE = {
    "name": "navigate",
    "description": "Navigate to a URL. Returns final url, title, and HTTP status.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "The URL to navigate to"},
            "timeout_ms": {"type": "integer", "default": 30000, "description": "Timeout in milliseconds"},
        },
        "required": ["url"],
    },
}

def fn_navigate(url: str, timeout_ms: int = 30_000) -> dict:
    rt = _boot_page()
    return rt.page_ops.navigate(url, timeout_ms=timeout_ms)

TOOL_NAVIGATE["fn"] = fn_navigate


TOOL_GO_BACK = {
    "name": "go_back",
    "description": "Navigate back in history.",
    "inputSchema": {"type": "object", "properties": {}, "required": []},
}
def fn_go_back() -> dict:
    rt = _boot_page()
    return rt.page_ops.go_back()
TOOL_GO_BACK["fn"] = fn_go_back


TOOL_GO_FORWARD = {
    "name": "go_forward",
    "description": "Navigate forward in history.",
    "inputSchema": {"type": "object", "properties": {}, "required": []},
}
def fn_go_forward() -> dict:
    rt = _boot_page()
    return rt.page_ops.go_forward()
TOOL_GO_FORWARD["fn"] = fn_go_forward


TOOL_RELOAD = {
    "name": "reload_page",
    "description": "Reload the current page.",
    "inputSchema": {"type": "object", "properties": {}, "required": []},
}
def fn_reload() -> dict:
    rt = _boot_page()
    return rt.page_ops.reload()
TOOL_RELOAD["fn"] = fn_reload


# -- element interaction -----------------------------------------------------

TOOL_CLICK = {
    "name": "click",
    "description": "Click an element identified by CSS selector.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "selector": {"type": "string"},
            "timeout": {"type": "integer", "default": 5000},
        },
        "required": ["selector"],
    },
}
def fn_click(selector: str, timeout: int = 5000) -> dict:
    rt = _boot_page()
    return rt.page_ops.click(selector, timeout=timeout)
TOOL_CLICK["fn"] = fn_click


TOOL_CLICK_TEXT = {
    "name": "click_text",
    "description": "Click the first node whose visible text contains the given text.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "timeout": {"type": "integer", "default": 5000},
        },
        "required": ["text"],
    },
}
def fn_click_text(text: str, timeout: int = 5000) -> dict:
    rt = _boot_page()
    return rt.page_ops.click_text(text, timeout=timeout)
TOOL_CLICK_TEXT["fn"] = fn_click_text


TOOL_FILL = {
    "name": "fill_input",
    "description": "Fill a form field. Fires framework-compatible input/change events.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "selector": {"type": "string"},
            "value": {"type": "string"},
            "clear_first": {"type": "boolean", "default": True},
            "timeout": {"type": "integer", "default": 5000},
        },
        "required": ["selector", "value"],
    },
}
def fn_fill_input(selector: str, value: str, clear_first: bool = True, timeout: int = 5000) -> dict:
    rt = _boot_page()
    return rt.page_ops.fill_input(selector, value, clear_first=clear_first, timeout=timeout)
TOOL_FILL["fn"] = fn_fill_input


TOOL_KEY = {
    "name": "press_key",
    "description": "Press a keyboard key or combination (e.g. 'Enter', 'Control+a').",
    "inputSchema": {
        "type": "object",
        "properties": {"key": {"type": "string"}},
        "required": ["key"],
    },
}
def fn_press_key(key: str) -> dict:
    rt = _boot_page()
    return rt.page_ops.press_key(key)
TOOL_KEY["fn"] = fn_press_key


TOOL_UPLOAD = {
    "name": "upload_file",
    "description": "Upload file(s) to a file input element.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "selector": {"type": "string"},
            "file_paths": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["selector", "file_paths"],
    },
}
def fn_upload_file(selector: str, file_paths: list[str]) -> dict:
    rt = _boot_page()
    return rt.page_ops.upload_file(selector, file_paths)
TOOL_UPLOAD["fn"] = fn_upload_file


# -- content reads -----------------------------------------------------------

TOOL_READ_PAGE = {
    "name": "read_page",
    "description": "Read the full page: DOM HTML length + title + metadata summary.",
    "inputSchema": {"type": "object", "properties": {}, "required": []},
}
def fn_read_page() -> dict:
    rt = _boot_page()
    po = rt.page_ops
    return {
        "url": po.page.url,
        "title": po.page.title(),
        "html_length": len(po.get_content()),
        "text_preview": po.get_text()[:2000],
        "page_info": po.page_info(),
    }
TOOL_READ_PAGE["fn"] = fn_read_page


TOOL_GET_TEXT = {
    "name": "get_text",
    "description": "Extract visible text under the given CSS selector.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "selector": {"type": "string", "default": "body"},
        },
        "required": [],
    },
}
def fn_get_text(selector: str = "body") -> str:
    rt = _boot_page()
    return rt.page_ops.get_text(selector)
TOOL_GET_TEXT["fn"] = fn_get_text


TOOL_JS_EVAL = {
    "name": "js_eval",
    "description": "Execute JavaScript expression and return result.",
    "inputSchema": {
        "type": "object",
        "properties": {"expression": {"type": "string"}},
        "required": ["expression"],
    },
}
def fn_js_eval(expression: str) -> Any:
    rt = _boot_page()
    return rt.page_ops.js_evaluate(expression)
TOOL_JS_EVAL["fn"] = fn_js_eval


TOOL_SCREENSHOT = {
    "name": "screenshot",
    "description": "Take a screenshot. Returns base64 string, or saves to path.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "full_page": {"type": "boolean", "default": False},
            "path": {"type": "string", "description": "File path to save image (optional)"},
        },
        "required": [],
    },
}
def fn_screenshot(full_page: bool = False, path: Optional[str] = None) -> Optional[str]:
    rt = _boot_page()
    return rt.page_ops.screenshot(full_page=full_page, path=path)
TOOL_SCREENSHOT["fn"] = fn_screenshot


TOOL_WAIT = {
    "name": "wait_for_selector",
    "description": "Wait for an element to appear. Returns True when found.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "selector": {"type": "string"},
            "timeout_ms": {"type": "integer", "default": 10000},
        },
        "required": ["selector"],
    },
}
def fn_wait_for_selector(selector: str, timeout_ms: int = 10_000) -> bool:
    rt = _boot_page()
    return rt.page_ops.wait_for_selector(selector, timeout_ms=timeout_ms)
TOOL_WAIT["fn"] = fn_wait_for_selector


# -- security ----------------------------------------------------------------

TOOL_XSS = {
    "name": "inject_xss_payload",
    "description": "Inject XSS probes into a target input/textarea and check for reflection.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "selector": {"type": "string"},
            "payloads": {"type": "array", "items": {"type": "string"}, "description": "Optional custom payloads"},
            "clear_first": {"type": "boolean", "default": True},
        },
        "required": ["selector"],
    },
}
def fn_inject_xss(selector: str, payloads: Optional[list[str]] = None, clear_first: bool = True) -> dict:
    rt = _boot_page()
    assert rt.security_ops is not None
    return rt.security_ops.inject_xss_payload(selector, payloads=payloads, clear_first=clear_first)
TOOL_XSS["fn"] = fn_inject_xss


TOOL_INJECT = {
    "name": "inject_payload",
    "description": "Inject a single custom payload into a target element and verify reflection.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "selector": {"type": "string"},
            "payload": {"type": "string"},
        },
        "required": ["selector", "payload"],
    },
}
def fn_inject_payload(selector: str, payload: str) -> dict:
    rt = _boot_page()
    assert rt.security_ops is not None
    rt.security_ops.inject_xss_payload(selector, payloads=[payload], clear_first=True)
    return rt.security_ops.inject_xss_reflective(payload)
TOOL_INJECT["fn"] = fn_inject_payload


TOOL_REFLECT = {
    "name": "find_reflection",
    "description": "Check whether text was reflected in the current page DOM.",
    "inputSchema": {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    },
}
def fn_find_reflection(text: str) -> dict:
    rt = _boot_page()
    assert rt.security_ops is not None
    return rt.security_ops.inject_xss_reflective(text)
TOOL_REFLECT["fn"] = fn_find_reflection


TOOL_URL_PARAMS = {
    "name": "get_url_params",
    "description": "Extract and list all URL query parameters.",
    "inputSchema": {"type": "object", "properties": {}, "required": []},
}
def fn_get_url_params() -> dict:
    rt = _boot_page()
    assert rt.security_ops is not None
    return rt.security_ops.get_url_params()
TOOL_URL_PARAMS["fn"] = fn_get_url_params


# -- session -----------------------------------------------------------------

TOOL_GET_COOKIES = {
    "name": "get_cookies",
    "description": "List all cookies, optionally filtered by domain patterns.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "domains": {"type": "array", "items": {"type": "string"}, "description": "Filter by domain patterns"},
        },
        "required": [],
    },
}
def fn_get_cookies(domains: Optional[list[str]] = None) -> list[dict]:
    rt = _boot_page()
    assert rt.session_ops is not None
    return rt.session_ops.get_cookies(domains=domains)
TOOL_GET_COOKIES["fn"] = fn_get_cookies


TOOL_SET_COOKIE = {
    "name": "set_cookie",
    "description": "Set a single cookie. Useful for session token replay.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "value": {"type": "string"},
            "domain": {"type": "string", "default": ".localhost"},
            "path": {"type": "string", "default": "/"},
            "secure": {"type": "boolean", "default": False},
            "http_only": {"type": "boolean", "default": False},
            "same_site": {"type": "string", "default": "Lax"},
        },
        "required": ["name", "value"],
    },
}
def fn_set_cookie(name: str, value: str, domain: str = ".localhost", path: str = "/",
                  secure: bool = False, http_only: bool = False, same_site: str = "Lax") -> dict:
    rt = _boot_page()
    assert rt.session_ops is not None
    return rt.session_ops.set_cookie(name, value, domain=domain, path=path,
                                     secure=secure, http_only=http_only, same_site=same_site)
TOOL_SET_COOKIE["fn"] = fn_set_cookie


TOOL_SET_COOKIES = {
    "name": "set_cookies",
    "description": "Bulk-inject cookies (e.g., from Burp export).",
    "inputSchema": {
        "type": "object",
        "properties": {"cookies": {"type": "array", "items": {"type": "object"}}},
        "required": ["cookies"],
    },
}
def fn_set_cookies(cookies: list[dict]) -> dict:
    rt = _boot_page()
    assert rt.session_ops is not None
    return rt.session_ops.set_cookies(cookies)
TOOL_SET_COOKIES["fn"] = fn_set_cookies


TOOL_CLEAR_COOKIES = {
    "name": "clear_cookies",
    "description": "Clear all cookies for the current context.",
    "inputSchema": {"type": "object", "properties": {}, "required": []},
}
def fn_clear_cookies() -> dict:
    rt = _boot_page()
    assert rt.session_ops is not None
    return rt.session_ops.clear_cookies()
TOOL_CLEAR_COOKIES["fn"] = fn_clear_cookies


TOOL_SESSION_INFO = {
    "name": "get_session_info",
    "description": "Full session snapshot: cookies + storage + detected tokens.",
    "inputSchema": {"type": "object", "properties": {}, "required": []},
}
def fn_session_info() -> dict:
    rt = _boot_page()
    assert rt.session_ops is not None
    return rt.session_ops.get_session_info()
TOOL_SESSION_INFO["fn"] = fn_session_info


TOOL_STORAGE = {
    "name": "get_storage_data",
    "description": "Dump localStorage and sessionStorage contents.",
    "inputSchema": {"type": "object", "properties": {}, "required": []},
}
def fn_get_storage_data() -> dict:
    rt = _boot_page()
    assert rt.session_ops is not None
    return rt.session_ops.get_storage_data()
TOOL_STORAGE["fn"] = fn_get_storage_data


TOOL_STORE_ITEM = {
    "name": "set_storage_item",
    "description": "Write a key-value pair to localStorage or sessionStorage.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "key": {"type": "string"},
            "value": {"type": "string"},
            "store": {"type": "string", "default": "localStorage"},
        },
        "required": ["key", "value"],
    },
}
def fn_set_storage_item(key: str, value: str, store: str = "localStorage") -> dict:
    rt = _boot_page()
    assert rt.session_ops is not None
    return rt.session_ops.set_storage_item(key, value, store=store)
TOOL_STORE_ITEM["fn"] = fn_set_storage_item


TOOL_EXPORT_STATE = {
    "name": "export_state",
    "description": "Save full browser state (cookies + storage) to a file.",
    "inputSchema": {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    },
}
def fn_export_state(path: str) -> dict:
    rt = _boot_page()
    assert rt.session_ops is not None
    return rt.session_ops.export_state(path)
TOOL_EXPORT_STATE["fn"] = fn_export_state


TOOL_IMPORT_STATE = {
    "name": "import_state",
    "description": "Restore browser state from a previously saved file.",
    "inputSchema": {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    },
}
def fn_import_state(path: str) -> dict:
    rt = _boot_page()
    assert rt.session_ops is not None
    return rt.session_ops.import_state(path)
TOOL_IMPORT_STATE["fn"] = fn_import_state


# -- network -----------------------------------------------------------------

TOOL_NET_START = {
    "name": "start_network_capture",
    "description": "Begin capturing all HTTP(S) requests/responses on the current page.",
    "inputSchema": {"type": "object", "properties": {}, "required": []},
}
def fn_net_start() -> dict:
    rt = _boot_page()
    assert rt.network_ops is not None
    return rt.network_ops.start_capture()
TOOL_NET_START["fn"] = fn_net_start


TOOL_NET_STOP = {
    "name": "stop_network_capture",
    "description": "Stop capturing and report totals.",
    "inputSchema": {"type": "object", "properties": {}, "required": []},
}
def fn_net_stop() -> dict:
    rt = _boot_page()
    assert rt.network_ops is not None
    return rt.network_ops.stop_capture()
TOOL_NET_STOP["fn"] = fn_net_stop


TOOL_NET_SUMMARY = {
    "name": "get_network_summary",
    "description": "Get a filtered summary of captured network traffic.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "resource_types": {"type": "array", "items": {"type": "string"}},
            "status_filter": {"type": "integer"},
        },
        "required": [],
    },
}
def fn_net_summary(resource_types: Optional[list[str]] = None, status_filter: Optional[int] = None) -> dict:
    rt = _boot_page()
    assert rt.network_ops is not None
    return rt.network_ops.get_capture_summary(resource_types=resource_types, status_filter=status_filter)
TOOL_NET_SUMMARY["fn"] = fn_net_summary


TOOL_BLOCK_URLS = {
    "name": "block_urls",
    "description": "Block navigations matching glob-style URL patterns.",
    "inputSchema": {
        "type": "object",
        "properties": {"patterns": {"type": "array", "items": {"type": "string"}}},
        "required": ["patterns"],
    },
}
def fn_block_urls(patterns: list[str]) -> dict:
    rt = _boot_page()
    assert rt.network_ops is not None
    return rt.network_ops.block_urls(patterns)
TOOL_BLOCK_URLS["fn"] = fn_block_urls


# -- recon -------------------------------------------------------------------

TOOL_TECH_STACK = {
    "name": "recon_technology_stack",
    "description": "Detect technologies/frameworks/CMS used on the current page.",
    "inputSchema": {"type": "object", "properties": {}, "required": []},
}
def fn_tech_stack() -> dict:
    rt = _boot_page()
    assert rt.recon_ops is not None
    return rt.recon_ops.tech_stack()
TOOL_TECH_STACK["fn"] = fn_tech_stack


TOOL_SENSITIVE = {
    "name": "find_sensitive_data",
    "description": "Scan page HTML and text for leaked secrets, keys, tokens.",
    "inputSchema": {"type": "object", "properties": {}, "required": []},
}
def fn_find_sensitive() -> dict:
    rt = _boot_page()
    assert rt.recon_ops is not None
    return rt.recon_ops.find_sensitive_data()
TOOL_SENSITIVE["fn"] = fn_find_sensitive


TOOL_DOM = {
    "name": "dom_analysis",
    "description": "Extract structural summary of the DOM tree.",
    "inputSchema": {"type": "object", "properties": {}, "required": []},
}
def fn_dom() -> dict:
    rt = _boot_page()
    assert rt.recon_ops is not None
    return rt.recon_ops.dom_analysis()
TOOL_DOM["fn"] = fn_dom


TOOL_FORMS = {
    "name": "enumerate_forms",
    "description": "List all forms with actions, methods, and field details.",
    "inputSchema": {"type": "object", "properties": {}, "required": []},
}
def fn_forms() -> dict:
    rt = _boot_page()
    assert rt.recon_ops is not None
    return rt.recon_ops.enumerate_forms()
TOOL_FORMS["fn"] = fn_forms


TOOL_LINKS = {
    "name": "enumerate_links",
    "description": "List all hyperlinks on the page.",
    "inputSchema": {
        "type": "object",
        "properties": {"relative_only": {"type": "boolean", "default": True}},
        "required": [],
    },
}
def fn_links(relative_only: bool = True) -> dict:
    rt = _boot_page()
    assert rt.recon_ops is not None
    return rt.recon_ops.enumerate_links(relative_only=relative_only)
TOOL_LINKS["fn"] = fn_links


TOOL_HEADERS = {
    "name": "security_headers_check",
    "description": "Check for common security headers and protections.",
    "inputSchema": {"type": "object", "properties": {}, "required": []},
}
def fn_headers() -> dict:
    rt = _boot_page()
    assert rt.recon_ops is not None
    return rt.recon_ops.security_headers_check()
TOOL_HEADERS["fn"] = fn_headers


# -- lifecycle ---------------------------------------------------------------

TOOL_CLOSE = {
    "name": "close_browser",
    "description": "Close the browser and release resources.",
    "inputSchema": {"type": "object", "properties": {}, "required": []},
}
def fn_close() -> dict:
    global _rt
    if _rt:
        _rt.engine.stop()
    _rt = None
    return {"status": "closed"}
TOOL_CLOSE["fn"] = fn_close


TOOL_NEW_CTX = {
    "name": "new_context",
    "description": "Create a new isolated browser context (separate cookie jar).",
    "inputSchema": {
        "type": "object",
        "properties": {
            "proxy": {"type": "object", "description": "Proxy settings dict"},
        },
        "required": [],
    },
}
def fn_new_ctx(proxy: Optional[dict] = None) -> dict:
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
TOOL_NEW_CTX["fn"] = fn_new_ctx


TOOL_LIST_CTX = {
    "name": "list_contexts",
    "description": "List all active browser contexts.",
    "inputSchema": {"type": "object", "properties": {}, "required": []},
}
def fn_list_ctx() -> dict:
    rt = _ensure()
    return {"context_count": len(rt.engine._contexts)}
TOOL_LIST_CTX["fn"] = fn_list_ctx


# ================================================================ MCP protocol handler

ALL_TOOLS = [
    TOOL_NAVIGATE, TOOL_GO_BACK, TOOL_GO_FORWARD, TOOL_RELOAD,
    TOOL_CLICK, TOOL_CLICK_TEXT, TOOL_FILL, TOOL_KEY, TOOL_UPLOAD,
    TOOL_READ_PAGE, TOOL_GET_TEXT, TOOL_JS_EVAL, TOOL_SCREENSHOT, TOOL_WAIT,
    TOOL_XSS, TOOL_INJECT, TOOL_REFLECT, TOOL_URL_PARAMS,
    TOOL_GET_COOKIES, TOOL_SET_COOKIE, TOOL_SET_COOKIES, TOOL_CLEAR_COOKIES,
    TOOL_SESSION_INFO, TOOL_STORAGE, TOOL_STORE_ITEM,
    TOOL_EXPORT_STATE, TOOL_IMPORT_STATE,
    TOOL_NET_START, TOOL_NET_STOP, TOOL_NET_SUMMARY, TOOL_BLOCK_URLS,
    TOOL_TECH_STACK, TOOL_SENSITIVE, TOOL_DOM,
    TOOL_FORMS, TOOL_LINKS, TOOL_HEADERS,
    TOOL_CLOSE, TOOL_NEW_CTX, TOOL_LIST_CTX,
]

TOOLS_MAP = {t["name"]: t for t in ALL_TOOLS}


def _handle_tools_list() -> dict:
    """List all available tools."""
    return {"tools": [
        {"name": t["name"], "description": t["description"], "inputSchema": t["inputSchema"]}
        for t in ALL_TOOLS
    ]}


def _handle_tools_call(name: str, arguments: dict) -> dict:
    """Call a tool by name with given arguments."""
    if name not in TOOLS_MAP:
        return {"error": f"Unknown tool: {name}", "_tools_available": list(TOOLS_MAP.keys())}
    fn = TOOLS_MAP[name]["fn"]
    try:
        result = fn(**arguments)
        return {"content": [{"type": "text", "text": json.dumps(result, default=str)}]}
    except Exception as e:
        logger.exception("Tool %s failed", name)
        return {"error": str(e), "tool": name}


def _send_response(request_id: int, result: dict) -> None:
    msg = {"jsonrpc": "2.0", "id": request_id, "result": result}
    print(json.dumps(msg))
    sys.stdout.flush()


def _send_error(request_id: Optional[int], code: int, message: str) -> None:
    obj = {"jsonrpc": "2.0", "error": {"code": code, "message": message}}
    if request_id is not None:
        obj["id"] = request_id
    print(json.dumps(obj))
    sys.stdout.flush()


def _handle_initialize() -> dict:
    """Return MCP server capabilities."""
    return {
        "protocolVersion": "2024-11-05",
        "serverInfo": {
            "name": "browser-firefox-mcp",
            "version": "0.1.0",
        },
        "capabilities": {
            "tools": {
                "listChanged": False,
            },
        },
    }


def main() -> None:
    """Run the MCP server over stdio (sync, no asyncio needed)."""
    logger.info("Starting firefx-browser MCP server")

    while True:
        line = sys.stdin.readline()
        if not line:
            break
        try:
            req = json.loads(line.strip())
        except json.JSONDecodeError:
            continue

        method = req.get("method", "")
        rid = req.get("id")

        try:
            if method == "initialize":
                _send_response(rid, _handle_initialize())
            elif method == "notifications/initialized":
                # No response required for notifications
                pass
            elif method == "tools/list":
                _send_response(rid, _handle_tools_list())
            elif method == "tools/call":
                params = req.get("params", {})
                _send_response(rid, _handle_tools_call(params.get("name", ""), params.get("arguments", {})))
            else:
                _send_error(rid, -32601, f"Method not found: {method}")
        except Exception as e:
            logger.exception("Request handler error")
            _send_error(rid, -32603, str(e))


if __name__ == "__main__":
    main()
