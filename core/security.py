"""Security testing tools — XSS detection, payload injection analysis."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

from playwright.sync_api import Page

from .page import _is_internal

logger = logging.getLogger(__name__)

# --- common xss payloads for quick probing -------------------------------

_XSS_PAYLOADS: list[str] = [
    '<svg onload="alert(1)">',
    '<img src=x onerror="alert(1)">',
    '"><script>alert(1)</script>',
    "';alert(1);//",
    '<details/open/ontoggle=alert(1)>',
    '<marquee/onstart=alert(1)>',
    "<iframe src='javascript:alert(1)'>",
]


def _check_reflection(page: Page, injected_text: str) -> dict:
    """Check if *injected_text* is reflected back in the DOM or source."""
    # 1. Check innerText
    reflected_text = page.evaluate(f"document.body.innerText.includes('{injected_text[:30]}')")
    # 2. Check outerHTML of body (for stored XSS in HTML context)
    # We can't inline large strings safely in JS; use a simpler check.
    dom_snippet = page.evaluate("""
        () => {
            const h = document.body.innerHTML;
            return { hasHtml: h.includes('<'), len: h.length };
        }
    """)
    # 3. Check console messages for alert() triggers
    console_messages = page.evaluate("""
        () => window.__cyber_console_log || []
    """)

    return {
        "reflected_in_text": bool(reflected_text),
        "dom_has_script_tags": dom_snippet.get("hasHtml", False) if isinstance(dom_snippet, dict) else False,
        "dom_length": dom_snippet.get("len", 0) if isinstance(dom_snippet, dict) else 0,
        "console_messages": console_messages if isinstance(console_messages, list) else [],
    }


class SecurityOps:
    """Vulnerability discovery operations on a live page."""

    def __init__(self, page: Page, **kwargs: Any) -> None:  # accept engine param compat
        self.page = page

    # -- payload injection & XSS detection -----------------------------------

    def inject_xss_payload(self, selector: str, payloads: Optional[list[str]] = None,
                           clear_first: bool = True) -> dict:
        """Inject XSS payloads into a target input/textarea and check for reflection.

        Returns a summary per payload with indication of potential vulnerability.
        """
        results: list[dict] = []
        probes = payloads or _XSS_PAYLOADS

        logger.info("Injecting %d XSS probes into %s", len(probes), selector)
        for idx, payload in enumerate(probes):
            try:
                el = self.page.locator(selector).first
                el.wait_for(state="visible", timeout=5000)
                if clear_first:
                    el.fill(payload)
                else:
                    el.press_sequentially(payload)

                # Fire events
                self.page.evaluate(
                    "(sel) => { const e = document.querySelector(sel); "
                    "if(!e) return; e.dispatchEvent(new Event('input',{bubbles:true})); "
                    "e.dispatchEvent(new Event('change',{bubbles:true})); }",
                    selector,
                )

                # Quick pause for any reactive rendering
                self.page.wait_for_timeout(500)

                reflection = _check_reflection(self.page, payload)
                status = "POSSIBLE_XSS" if (reflection["reflected_in_text"] or reflection["dom_has_script_tags"]) else "no_reflection"

                results.append({
                    "index": idx,
                    "payload_preview": payload[:80],
                    "status": status,
                    "reflection": reflection,
                })

                if status == "POSSIBLE_XSS":
                    logger.warning("Possible XSS detected with payload: %s", payload[:60])

                # Restore original value to not break the form for next probe
                el.fill("")

            except Exception as exc:
                results.append({
                    "index": idx,
                    "payload_preview": payload[:80],
                    "error": str(exc),
                    "status": "failed",
                })

        vulnerable_count = sum(1 for r in results if r.get("status") == "POSSIBLE_XSS")
        return {
            "total_probes": len(results),
            "possible_vulns": vulnerable_count,
            "results": results,
        }

    def inject_xss_reflective(self, text_to_check: str) -> dict:
        """After manual input, check whether the text was reflected in the page."""
        reflection = _check_reflection(self.page, text_to_check)
        reflection["text_checked"] = text_to_check[:100]
        reflection["potential_vuln"] = reflection["reflected_in_text"] or reflection["dom_has_script_tags"]
        return reflection

    # -- parameter fuzzing helpers -------------------------------------------

    def get_url_params(self) -> dict:
        """Extract URL query parameters from current page."""
        url = self.page.url
        params: dict = {}
        if "?" in url:
            qs = url.split("?", 1)[1]
            for part in qs.split("&"):
                if "=" in part:
                    k, v = part.split("=", 1)
                    params[k] = v
        return {"url": url, "params": params, "param_count": len(params)}
