"""Page operations — navigate, click, fill, read DOM, capture screenshots."""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from typing import Any, Optional

from playwright.sync_api import ElementHandle, Page

from .engine import Engine

logger = logging.getLogger(__name__)

# Internal URL schemes we should NOT navigate to
_INTERNAL_SCHEMES = ("about:", "chrome://", "moz-extension://")


def _is_internal(url: str) -> bool:
    return any(url.startswith(s) for s in _INTERNAL_SCHEMES)


# ------------------------------------------------------------------ helpers


def _expect_loaded(page: Page, timeout_ms: int = 30_000) -> None:
    """Wait for page to reach a stable state after navigation."""
    page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
    page.wait_for_load_state("networkidle", timeout=min(timeout_ms, 10_000))


# ----------------------------------------------------------------─ public API


class PageOps:
    """High-level page interaction layer. Receives a Playwright ``Page``
    from ``Engine.new_context().new_page()`` at construction time."""

    def __init__(self, page: Page, engine: Engine) -> None:
        self.page = page
        self.engine = engine

    # -- navigation --------------------------------------------------------

    def navigate(self, url: str, timeout_ms: int = 30_000) -> dict:
        """Navigate to *url*. Returns status info and final URL."""
        if _is_internal(url):
            raise ValueError(f"Internal URL scheme blocked: {url}")
        logger.info("Navigating to %s", url)
        self.page.goto(url, wait_until="commit", timeout=timeout_ms)
        _expect_loaded(self.page, timeout_ms)
        title = self.page.title()
        return {
            "url": self.page.url,
            "title": title,
            "status": self.page.evaluate("async () => { const r = await fetch(location.href, {method:'HEAD'}); return r.status; }").get("status", 0),
        }

    def go_back(self) -> dict:
        self.page.go_back(wait_until="domcontentloaded")
        return {"url": self.page.url, "title": self.page.title()}

    def go_forward(self) -> dict:
        self.page.go_forward(wait_until="domcontentloaded")
        return {"url": self.page.url, "title": self.page.title()}

    def reload(self) -> dict:
        self.page.reload(wait_until="domcontentloaded")
        return {"url": self.page.url, "title": self.page.title()}

    # -- element interaction -----------------------------------------------

    def click(self, selector: str, timeout: int = 5000) -> dict:
        """Click the first element matching *selector*."""
        el = self.page.locator(selector).first
        el.wait_for(state="visible", timeout=timeout)
        el.click()
        # Brief pause for post-click effects
        self.page.wait_for_timeout(300)
        return {"url": self.page.url, "title": self.page.title(), "clicked": selector}

    def click_text(self, text: str, timeout: int = 5000) -> dict:
        """Click a node whose visible text contains *text*."""
        self.page.get_by_text(text, exact=False).first.click(timeout=timeout)
        self.page.wait_for_timeout(300)
        return {"url": self.page.url, "clicked_text": text}

    def fill_input(self, selector: str, value: str, clear_first: bool = True,
                   timeout: int = 5000) -> dict:
        """Fill an input field, firing framework-compatible events."""
        el = self.page.locator(selector).first
        el.wait_for(state="visible", timeout=timeout)
        if clear_first:
            el.fill(value)
        else:
            el.press_sequentially(value)
        # Fire change/input events for SPA frameworks
        self.page.evaluate(
            "(sel) => { const e = document.querySelector(sel); "
            "if(!e) return; e.dispatchEvent(new Event('input',{bubbles:true})); "
            "e.dispatchEvent(new Event('change',{bubbles:true})); }",
            selector,
        )
        return {"filled": selector, "value_masked": "*" * min(len(value), 8)}

    def press_key(self, key: str) -> dict:
        """Press a keyboard key (e.g. 'Enter', 'Tab', 'Control+a')."""
        self.page.keyboard.press(key)
        self.page.wait_for_timeout(200)
        return {"key_pressed": key, "url": self.page.url}

    def upload_file(self, selector: str, file_paths: list[str]) -> dict:
        """Set file(s) on a file input."""
        el = self.page.locator(selector).first
        el.wait_for(state="visible")
        el.set_input_files(file_paths)
        return {"uploaded": selector, "files": file_paths}

    # -- content extraction ------------------------------------------------

    def get_content(self) -> str:
        """Return raw HTML of the current page."""
        return self.page.content()

    def get_text(self, selector: str = "body") -> str:
        """Extract visible text under *selector*."""
        return self.page.inner_text(selector, timeout=5000)

    def get_attribute(self, selector: str, name: str) -> Optional[str]:
        return self.page.get_attribute(selector, name, timeout=5000)

    def js_evaluate(self, expression: str, await_promise: bool = False) -> Any:
        """Execute JavaScript and return the result. Use with caution."""
        return self.page.evaluate(expression, force=True, timeout=10_000)

    def page_info(self) -> dict:
        """Return summary: url, title, dimensions, scroll position."""
        info = self.page.evaluate("""
            JSON.stringify({
                url: location.href,
                title: document.title,
                w: innerWidth, h: innerHeight,
                sx: scrollX, sy: scrollY,
                pw: document.documentElement.scrollWidth,
                ph: document.documentElement.scrollHeight,
            })
        """)
        return json.loads(info) if isinstance(info, str) else info

    # -- screenshot --------------------------------------------------------

    def screenshot(self, full_page: bool = False, path: Optional[str] = None) -> Optional[str]:
        """Capture screenshot. Returns base64 string unless *path* is given."""
        kwargs: dict = {"type": "jpeg", "quality": 70}
        if full_page:
            kwargs["full_page"] = True
        data = self.page.screenshot(**kwargs)
        if path:
            Path(path).write_bytes(data)
            return path
        return base64.b64encode(data).decode("ascii")

    # -- waiting -----------------------------------------------------------

    def wait_for_selector(self, selector: str, timeout_ms: int = 10_000) -> bool:
        try:
            self.page.locator(selector).wait_for(state="attached", timeout=timeout_ms)
            return True
        except Exception:
            return False

    def wait_for_url(self, pattern: str, timeout_ms: int = 10_000) -> bool:
        try:
            self.page.wait_for_url(pattern, timeout=timeout_ms)
            return True
        except Exception:
            return False
