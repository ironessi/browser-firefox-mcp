"""Network traffic capture — request/response interception via Playwright."""

from __future__ import annotations

import logging
from typing import Any, Optional

from playwright.sync_api import Page, Request, Response, Route

logger = logging.getLogger(__name__)


class NetworkOps:
    """Capture and inspect HTTP(S) traffic during browsing."""

    def __init__(self, page: Page, **kwargs: Any) -> None:
        self.page = page
        self._captured_requests: list[dict] = []
        self._captured_responses: list[dict] = []
        self._request_handler = self._build_request_handler()
        self._response_handler = self._build_response_handler()
        self._intercepted = False

    # -- internal handler factories ------------------------------------------

    def _build_request_handler(self):
        """Factory that captures request details into self._captured_requests."""
        captured = self._captured_requests  # closure capture

        def handler(request: Request) -> None:
            entry: dict = {
                "method": request.method,
                "url": request.url,
                "headers": {k: v for k, v in request.headers.items()},
                "post_data": request.post_data,
                "resource_type": request.resource_type,
            }
            captured.append(entry)

        return handler

    def _build_response_handler(self):
        """Factory that captures response details into self._captured_responses."""
        captured = self._captured_responses  # closure capture

        def handler(response: Response) -> None:
            try:
                body_str = response.text()
            except Exception:
                body_str = "<binary>"
            entry: dict = {
                "status": response.status,
                "url": response.url,
                "headers": {k: v for k, v in response.headers.items()},
                "body_preview": body_str[:2000] if isinstance(body_str, str) else "<binary>",
                "resource_type": response.request.resource_type,
            }
            captured.append(entry)

        return handler

    # -- capture controls ----------------------------------------------------

    def start_capture(self) -> dict:
        """Begin capturing all requests/responses on the page."""
        if self._intercepted:
            return {"status": "already_capturing", "requests": len(self._captured_requests)}

        self._clear_capture()
        self.page.on("request", self._request_handler)
        self.page.on("response", self._response_handler)
        self._intercepted = True
        logger.info("Network capture started")
        return {"status": "started"}

    def stop_capture(self) -> dict:
        """Stop capturing and detach listeners."""
        if not self._intercepted:
            return {"status": "not_capturing"}
        self.page.remove_listener("request", self._request_handler)
        self.page.remove_listener("response", self._response_handler)
        self._intercepted = False
        return {
            "status": "stopped",
            "total_requests": len(self._captured_requests),
            "total_responses": len(self._captured_responses),
        }

    def _clear_capture(self) -> None:
        self._captured_requests.clear()
        self._captured_responses.clear()

    # -- query ----------------------------------------------------------------

    def get_capture_summary(
        self,
        resource_types: Optional[list[str]] = None,
        status_filter: Optional[int] = None,
    ) -> dict:
        """Get a filtered summary of captured traffic."""
        reqs = list(self._captured_requests)
        resps = list(self._captured_responses)

        if resource_types:
            reqs = [r for r in reqs if r.get("resource_type") in resource_types]
            resps = [r for r in resps if r.get("resource_type") in resource_types]

        if status_filter is not None:
            resps = [r for r in resps if r.get("status") == status_filter]

        methods: dict = {}
        for r in reqs:
            m = r.get("method", "GET")
            methods[m] = methods.get(m, 0) + 1

        return {
            "requests": len(reqs),
            "responses": len(resps),
            "methods": methods,
            "sample_requests": reqs[:20],
            "sample_responses": resps[:20],
        }

    # -- blocking / routing --------------------------------------------------

    def block_urls(self, patterns: list[str]) -> dict:
        """Block navigations matching glob-style URL patterns.

        Uses Playwright's route API — matched requests are aborted immediately.
        """
        blocked: list[str] = []
        for pattern in patterns:
            self.page.route(pattern, lambda route: route.abort())
            blocked.append(pattern)
        return {"blocked": blocked}
