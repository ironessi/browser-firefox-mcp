"""Firefox browser engine — lifecycle management via Playwright."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from playwright.sync_api import (
    Browser,
    BrowserContext,
    BrowserType,
    Page,
    Playwright,
    sync_playwright,
)

logger = logging.getLogger(__name__)


class Engine:
    """Manages a headless Firefox instance powered by Playwright.

    Singletons per process: one ``Playwright`` runner, one ``Browser``,
    multiple ``BrowserContext`` objects (each with its own isolated cookies, storage).
    Pages live inside contexts.
    """

    def __init__(self, headless: bool = True, viewport_width: int = 1280,
                 viewport_height: int = 720, proxy: Optional[dict] = None,
                 user_agent: Optional[str] = None) -> None:
        self._pw: Optional[Playwright] = None
        self._browser_type: Optional[BrowserType] = None
        self._browser: Optional[Browser] = None
        self._headless = headless
        self._viewport = {"width": viewport_width, "height": viewport_height}
        self._proxy = proxy
        self._user_agent = user_agent
        self._contexts: list[BrowserContext] = []

    # ---- public lifecycle ------------------------------------------------

    @property
    def is_alive(self) -> bool:
        return self._browser is not None and self._browser.is_connected()

    def start(self) -> None:
        """Launch headless Firefox. Safe to call repeatedly (no-op if already alive)."""
        if self.is_alive:
            return
        logger.info("Launching Firefox (headless=%s)", self._headless)
        self._pw = sync_playwright().start()  # type: ignore[assignment]
        self._browser_type = self._pw.firefox

        launch_kwargs: dict = {
            "headless": self._headless,
            "args": [
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--no-sandbox",          # Kali root-friendly
            ],
        }
        if self._proxy:
            launch_kwargs["proxy"] = self._proxy
        if self._user_agent:
            launch_kwargs["user_agent"] = self._user_agent

        self._browser = self._browser_type.launch(**launch_kwargs)
        logger.info("Firefox launched — pid=%s", self._browser.contexts[0].pages[0].context.browser.pid if self._browser.contexts else "N/A")

    def stop(self) -> None:
        """Close all contexts and shut down the browser."""
        for ctx in self._contexts:
            try:
                ctx.close()
            except Exception:
                pass
        self._contexts.clear()
        if self._browser:
            try:
                self._browser.close()
            except Exception:
                pass
            self._browser = None
        if self._pw:
            try:
                self._pw.stop()
            except Exception:
                pass
            self._pw = None
        logger.info("Browser stopped")

    def restart(self) -> None:
        self.stop()
        self.start()

    # ---- context management ----------------------------------------------

    def new_context(self, proxy: Optional[dict] = None,
                    storage_state: Optional[dict | Path] = None,
                    viewport_size: Optional[dict] = None) -> BrowserContext:
        """Create an isolated Firefox context (separate cookie jar, storage)."""
        kwargs: dict = {
            "viewport": viewport_size or self._viewport,
            "ignore_https_errors": True,
            "java_script_enabled": True,
        }
        if proxy:
            kwargs["proxy"] = proxy
        if storage_state:
            kwargs["storage_state"] = storage_state
        if self._user_agent and not kwargs.get("user_agent"):
            kwargs["user_agent"] = self._user_agent

        ctx = self._browser.new_context(**kwargs)  # type: ignore[union-attr]
        self._contexts.append(ctx)
        return ctx

    def current_context(self) -> BrowserContext:
        """Return the most recently created context (default working context)."""
        if not self._contexts:
            return self.new_context()
        return self._contexts[-1]

    def set_default_user_agent(self, ua: str) -> None:
        self._user_agent = ua
        # Apply to existing contexts
        for ctx in self._contexts:
            ctx.set_extra_http_headers({"User-Agent": ua})

    def detach_event_listener(self) -> None:
        """No-op stub — kept for API compat with event-based patterns."""
        pass
