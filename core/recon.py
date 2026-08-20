"""Reconnaissance — technology fingerprinting, sensitive info detection,
DOM structure analysis, framework identification."""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

from playwright.sync_api import Page

logger = logging.getLogger(__name__)


# --- known signatures ------------------------------------------------------

_FRAMEWORK_SIGS: list[tuple[str, list[str]]] = [
    ("React", ["__reactFiber", "__reactEvents", "react-dom"]),
    ("Vue", ["__vue__", "__vuex", "vue-router"]),
    ("Angular", ["ngApplication", "__ngZone__", "angular"], ["angular.js", "zone.js"]),
    ("Svelte", ["__svelte__", "svelte"]),
    ("Next.js", ["__NEXT_DATA__", "next.js"]),
    ("Nuxt", ["__NUXT__", "nuxt"]),
    (" Ember ", ["Ember", "ember-data"]),
    ("jQuery", ["jquery", "$.fn.jquery"]),
    ("Alpine.js", ["$data", "alpine", "x-data"]),
    ("SOLIDITY_WEB3", ["window.ethereum", "web3", "MetaMask"]),
]

_SENSITIVE_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("API_KEY", re.compile(r"(?i)(api[_-]?key|apikey)\s*[=:]\s*['\"]([a-zA-Z0-9]{16,})")),
    ("SECRET", re.compile(r"(?i)(secret|passwd|password|pwd)\s*[=:]\s*['\"](\S{8,})")),
    ("AWS_KEY", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("GCP_KEY", re.compile(r"AIza[0-9A-Za-z_-]{35}")),
    ("PRIVATE_KEY", re.compile(r"-----BEGIN (RSA |EC )?PRIVATE KEY-----")),
    ("JWT", re.compile(r"eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")),
    ("PHONE", re.compile(r"(?<!\d)\b\d{10,}\b(?!@\w)")),
    ("EMAIL_INLINE", re.compile(r"(?<![""])([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})(?![\"\'])")),
    ("IP_ADDRESS", re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")),
    ("SQL_COMMENT", re.compile(r"(?i)(--|#|/\*)\s*(SELECT|DROP|INSERT|UPDATE|DELETE|OR 1))")),
]

_SCRIPT_TAGS_SIGNS: list[tuple[str, re.Pattern]] = [
    ("EXTERNAL_JS", re.compile(r'(?i)src\s*=\s*["\'](?:https?:)?//[^\s"\'><]+')),
    ("INLINE_SCRIPT", re.compile(r"<script[^>]*>(?=.*</script>)", re.DOTALL)),
    ("DATA_ATTR", re.compile(r'data-\w+="[^"]{20,}"')),
    ("CONFIG_OBJECT", re.compile(r"(?i)(config|settings|env|constants)\s*=\s*\{")),
]


class ReconOps:
    """Information gathering operations — technology stack, security posture, metadata."""

    def __init__(self, page: Page, **kwargs: Any) -> None:
        self.page = page

    # -- technology stack ----------------------------------------------------

    def tech_stack(self) -> dict:
        """Detect technologies used on the page (framework, CMS, analytics, etc.)."""
        detected: dict[str, dict] = {}

        # Framework detection via JS evaluation
        for name, sigs_js in _FRAMEWORK_SIGS:
            if len(sigs_js) >= 2 and isinstance(sigs_js[1], list):
                # (name, [js_sigs], [script_src_patterns])
                js_sigs = sigs_js[:2]
                script_sigs = sigs_js[2:] if len(sigs_js) > 2 else []
            else:
                js_sigs = sigs_js
                script_sigs = []

            for sig in js_sigs:
                result = self.page.evaluate(f"typeof {sig} !== 'undefined'", force=True)
                if result:
                    detected[name] = {"detection_method": "js_eval", "signature": sig}
                    break

            if name in detected:
                continue

            # Fall back to script source check
            scripts = self.page.evaluate("""
                () => Array.from(document.querySelectorAll('script[src]')).map(s => s.src)
            """)
            if isinstance(script_sigs, list) and isinstance(scripts, list):
                for pattern in script_sigs:
                    for src in scripts:
                        if pattern.lower() in src.lower():
                            detected[name] = {"detection_method": "script_match", "source": src}

        # Script tags analysis
        script_info = self.page.evaluate("""
            () => ({
                totalScripts: document.querySelectorAll('script').length,
                externalScripts: Array.from(document.querySelectorAll('script[src]')).map(s => s.src),
                inlineScripts: Array.from(document.querySelectorAll(':scope > script:not([src])')).length,
            })
        """)

        # Link tags analysis (CDNs, fonts, trackers)
        link_info = self.page.evaluate("""
            () => Array.from(document.querySelectorAll('link[href]'))
                .filter(l => l.href.startsWith('http'))
                .map(l => ({ href: l.href, rel: l.rel }))
        """)

        return {
            "detected_technologies": detected,
            "tech_count": len(detected),
            "scripts": script_info if isinstance(script_info, dict) else {},
            "external_resources": link_info if isinstance(link_info, list) else [],
        }

    # -- sensitive information detection -------------------------------------

    def find_sensitive_data(self) -> dict:
        """Scan page HTML for potentially sensitive data leaks."""
        html = self.page.content()
        findings: list[dict] = []
        raw_texts: list[dict] = []

        for label, pattern in _SENSITIVE_PATTERNS:
            matches = pattern.findall(html)
            if matches:
                for match in matches[:10]:  # limit per category
                    if isinstance(match, tuple):
                        findings.append({
                            "category": label,
                            "matched": match[0][:80],
                            "value_truncated": match[1][:30] if len(match) > 1 else "",
                        })
                    else:
                        findings.append({
                            "category": label,
                            "matched": match[:80],
                        })

        # Also scan visible text for secrets
        body_text = self.page.inner_text("body")[:50000]
        for label, pattern in _SENSITIVE_PATTERNS:
            matches = pattern.findall(body_text)
            if matches:
                for match in matches[:5]:
                    raw_texts.append({
                        "context": f"...{match[0][-30:]}...",
                        "category": label,
                    })

        return {
            "html_findings": findings,
            "text_findings": raw_texts,
            "total_html_matches": sum(1 for p in _SENSITIVE_PATTERNS if p[1].search(html)),
            "severity": "HIGH" if any(f["category"] in ("JWT", "PRIVATE_KEY", "AWS_KEY") for f in findings) else "MEDIUM" if findings else "LOW",
        }

    # -- DOM structure analysis ----------------------------------------------

    def dom_analysis(self) -> dict:
        """Extract structural summary of the DOM tree."""
        summary = self.page.evaluate("""
            (() => {
                const tags = {};
                document.querySelectorAll('*').forEach(el => {
                    const t = el.tagName.toLowerCase();
                    tags[t] = (tags[t] || 0) + 1;
                });
                const forms = document.forms.length;
                const inputs = document.querySelectorAll('input').length;
                const links = document.querySelectorAll('a[href]').length;
                const images = document.querySelectorAll('img').length;
                const iframes = document.querySelectorAll('iframe').length;
                const buttons = document.querySelectorAll('button').length;
                const attrs = {};
                document.querySelectorAll('[id]').forEach(el => { attrs.id = (attrs.id||0)+1; });
                document.querySelectorAll('[name]').forEach(el => { attrs.name = (attrs.name||0)+1; });
                document.querySelectorAll('[class]').forEach(el => { attrs.class = (attrs.class||0)+1; });
                return { tags, forms, inputs, links, images, iframes, buttons, attributes: attrs };
            })()
        """)
        return summary if isinstance(summary, dict) else {}

    def enumerate_forms(self) -> dict:
        """List all forms with their action, method, and field details."""
        forms = self.page.evaluate("""
            (() => {
                return Array.from(document.forms).map(f => ({
                    action: f.action,
                    method: f.method,
                    id: f.id || null,
                    name: f.name || null,
                    fields: Array.from(f.elements).map(e => ({
                        name: e.name,
                        type: e.type,
                        id: e.id,
                        required: e.required,
                        disabled: e.disabled,
                        value: e.tagName === 'BUTTON' ? null : (e.value || '').substring(0, 50),
                        autocomplete: e.getAttribute('autocomplete'),
                    })).filter(f => f.name)
                }));
            })()
        """)
        return {"forms": forms if isinstance(forms, list) else []}

    def enumerate_links(self, relative_only: bool = True) -> dict:
        """List all hyperlinks, optionally filtering to relative paths only."""
        links = self.page.evaluate(f"""
            (() => {{
                const items = [];
                document.querySelectorAll('a[href]').forEach(a => {{
                    const h = a.href;
                    if ({relative_only} && !h.includes(location.hostname)) return;
                    items.push({{ url: h, text: a.textContent.trim().substring(0, 100), target: a.target }});
                }});
                return items;
            }})()
        """)
        return {"links": links if isinstance(links, list) else [], "count": len(links if isinstance(links, list) else [])}

    # -- security headers ----------------------------------------------------

    def security_headers_check(self) -> dict:
        """Check for common security headers in current page responses."""
        result = self.page.evaluate("""
            (() => {
                const headers = {};
                // Note: this reads navigation timing entries since we can't access response headers directly
                // This is a best-effort pass
                return headers;
            })()
        """)
        # Best effort: analyze meta tags for security hints
        metas = self.page.evaluate("""
            (() => {
                return Array.from(document.querySelectorAll('meta')).map(m => ({
                    name: m.name || m.httpEquiv || m.property,
                    content: m.content,
                }));
            })()
        """)
        csp_meta = [m for m in metas if isinstance(metas, list) and m.get("httpEquiv") == "Content-Security-Policy"] if isinstance(metas, list) else []
        x_frame = [m for m in metas if isinstance(metas, list) and m.get("httpEquiv") == "X-Frame-Options"] if isinstance(metas, list) else []

        return {
            "meta_security_tags": metas if isinstance(metas, list) else [],
            "csp_present": bool(csp_meta),
            "xframe_present": bool(x_frame),
            "recommendation": self._security_recommendation(csp_meta, x_frame, metas),
        }

    @staticmethod
    def _security_recommendation(csp: list, xframe: list, metas: list) -> list[str]:
        recs: list[str] = []
        if not csp:
            recs.append("Missing CSP meta tag — recommend server-side CSP header")
        if not xframe:
            recs.append("Missing X-Frame-Options — site may be vulnerable to clickjacking")
        has_hsts = any("Strict-Transport-Security" in str(m) for m in metas) if isinstance(metas, list) else False
        if not has_hsts:
            recs.append("No HSTS indication — ensure HTTPS enforcement")
        return recs
