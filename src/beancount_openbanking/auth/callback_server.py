"""OAuth callback server for Enable Banking authorization flow.

This module provides a simple HTTP server that listens for the OAuth callback
after the user authorizes the application with their bank.
"""

from __future__ import annotations

import logging
import threading
import urllib.parse
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class CallbackResult:
    """Result from an OAuth callback.

    Attributes:
        code: Authorization code on success.
        state: State parameter for CSRF protection.
        error: Error code if authorization failed.
        error_description: Human-readable error description.
    """

    code: str | None = None
    state: str | None = None
    error: str | None = None
    error_description: str | None = None


def wait_for_oauth_callback(
    host: str = "127.0.0.1",
    port: int = 8765,
    timeout: int = 300,
) -> CallbackResult:
    """Start a local HTTP server and wait for OAuth callback.

    This function blocks until the callback is received or the timeout expires.

    Args:
        host: Local host to bind the server to.
        port: Local port to bind the server to.
        timeout: Maximum time to wait for the callback in seconds.

    Returns:
        CallbackResult containing the authorization code or error.

    Raises:
        TimeoutError: If the callback is not received within the timeout.
        RuntimeError: If the callback contains an error.
    """
    result = CallbackResult()
    done = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            nonlocal result
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            result = CallbackResult(
                code=(params.get("code") or [None])[0],
                state=(params.get("state") or [None])[0],
                error=(params.get("error") or [None])[0],
                error_description=(params.get("error_description") or [None])[0],
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                b"<html><body>Authorization received. You can close this tab.</body></html>"
            )
            done.set()

        def log_message(self, format: str, *args: object) -> None:
            return

    server = HTTPServer((host, port), Handler)
    logger.debug("OAuth callback server listening on http://%s:%d", host, port)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        if not done.wait(timeout=timeout):
            logger.warning("OAuth callback timeout after %d seconds", timeout)
            server.shutdown()
            raise TimeoutError("Timeout waiting for Enable Banking callback")
    finally:
        server.shutdown()

    logger.debug(
        "OAuth callback received: state=%s, code=%s",
        result.state,
        "present" if result.code else "none",
    )

    if result.error:
        logger.error("OAuth error: %s - %s", result.error, result.error_description)
        raise RuntimeError(f"{result.error}: {result.error_description}")

    if not result.code:
        logger.error("No authorization code in callback")
        raise RuntimeError("No authorization code received in callback")

    return result
