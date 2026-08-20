"""Session management — cookies, storage, tokens, login state."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

from playwright.sync_api import BrowserContext, Cookie, Page

logger = logging.getLogger(__name__)


class SessionOps:
    """Cookie and browser storage manipulation for session hijacking / replay testing."""

    def __init__(self, context: BrowserContext, page: Page, **kwargs: Any) -> None:
        self.context = context
        self.page = page

    # -- cookies -------------------------------------------------------------

    def get_cookies(self, domains: Optional[list[str]] = None) -> list[dict]:
        """Return all cookies, optionally filtered by domain patterns."""
        raw = self.context.cookies()
        out: list[dict] = []
        for c in raw:
            if domains and not any(d in c.get("domain", "") for d in domains):
                continue
            out.append({
                "name": c["name"],
                "value": c["value"][:50] + ("..." if len(c["value"]) > 50 else ""),
                "domain": c.get("domain", ""),
                "path": c.get("path", "/"),
                "secure": c.get("secure", False),
                "httpOnly": c.get("httpOnly", False),
                "sameSite": c.get("sameSite", "None"),
                "expires": c.get("expires", "session"),
            })
        return out

    def set_cookie(self, name: str, value: str, domain: str = ".localhost",
                   path: str = "/", secure: bool = False,
                   http_only: bool = False, same_site: str = "Lax") -> dict:
        """Inject a single cookie. Useful for session token replays."""
        self.context.add_cookies([{
            "name": name,
            "value": value,
            "domain": domain,
            "path": path,
            "secure": secure,
            "httpOnly": http_only,
            "sameSite": same_site,
        }])
        return {"set": name, "domain": domain}

    def set_cookies(self, cookies: list[dict]) -> dict:
        """Bulk inject cookies (e.g. from Burp suite export)."""
        cleaned: list[dict] = []
        for c in cookies:
            entry: dict = {
                "name": c.get("name", ""),
                "value": c.get("value", ""),
                "domain": c.get("domain", ".localhost"),
                "path": c.get("path", "/"),
            }
            if "secure" in c:
                entry["secure"] = c["secure"]
            if "httpOnly" in c:
                entry["httpOnly"] = c["httpOnly"]
            if "sameSite" in c:
                entry["sameSite"] = c["sameSite"]
            cleaned.append(entry)
        self.context.add_cookies(cleaned)
        return {"cookies_set": len(cleaned)}

    def delete_cookie(self, name: str, domain: str = ".localhost",
                      path: str = "/") -> dict:
        """Remove a specific cookie."""
        self.context.clear_cookies()  # Playwright doesn't support single-delete; clear + re-add others
        all_cookies = [c for c in self.context.cookies() if c["name"] != name]
        self.context.add_cookies(all_cookies)
        return {"deleted": name}

    def clear_cookies(self) -> dict:
        self.context.clear_cookies()
        return {"cleared": True}

    # -- storage -------------------------------------------------------------

    def get_storage_data(self) -> dict:
        """Dump localStorage and sessionStorage contents."""
        data = self.page.evaluate("""
            JSON.stringify({
                localStorage: Object.fromEntries(Object.entries(localStorage)),
                sessionStorage: Object.fromEntries(Object.entries(sessionStorage))
            })
        """)
        return json.loads(data) if isinstance(data, str) else data

    def set_storage_item(self, key: str, value: str,
                         store: str = "localStorage") -> dict:
        """Write a key-value pair to localStorage or sessionStorage."""
        if store == "localStorage":
            self.page.evaluate(f"localStorage.setItem({json.dumps(key)}, {json.dumps(value)})")
        elif store == "sessionStorage":
            self.page.evaluate(f"sessionStorage.setItem({json.dumps(key)}, {json.dumps(value)})")
        else:
            raise ValueError(f"Unknown storage type: {store}")
        return {"stored": key, "store": store}

    # -- export / import -----------------------------------------------------

    def export_state(self, path: str) -> dict:
        """Save full browser state (cookies, localStorage) to a file for reuse."""
        state_path = Path(path)
        self.context.storage_state(path=str(state_path))
        return {"saved": str(state_path), "size_bytes": state_path.stat().st_size}

    def import_state(self, path: str) -> dict:
        """Restore browser state from a previously saved file."""
        self.context.add_cookies([
            {"name": c["name"], "value": c["value"], "domain": c.get("domain", ".localhost"), "path": c.get("path", "/")}
            for c in json.loads(Path(path).read_text())["cookies"]
        ])
        return {"loaded": str(path)}

    # -- info ----------------------------------------------------------------

    def get_session_info(self) -> dict:
        """Comprehensive session snapshot: cookies, tokens, storage."""
        cookies = self.get_cookies()
        storage = self.get_storage_data()
        tokens = self._extract_tokens(storage, cookies)
        return {
            "url": self.page.url,
            "cookie_count": len(cookies),
            "cookies": cookies[:20],  # don't dump everything
            "storage": storage,
            "detected_tokens": tokens,
        }

    @staticmethod
    def _extract_tokens(storage: dict, cookies: list[dict]) -> list[dict]:
        """Heuristic: find JWT, session IDs, API keys in storage and cookies."""
        token_patterns = ["token", "jwt", "sid", "session", "auth", "access_token", "refresh_token"]
        found: list[dict] = []
        for prefix, source in [
            ("local", storage.get("localStorage", {})),
            ("session", storage.get("sessionStorage", {})),
            ("cookie", {c["name"]: c["value"] for c in cookies}),
        ]:
            if isinstance(source, dict):
                for k, v in source.items():
                    if any(p in k.lower() for p in token_patterns):
                        found.append({"key": k, "prefix": prefix, "value_truncated": str(v)[:100]})
        return found
