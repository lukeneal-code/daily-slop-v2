#!/usr/bin/env python3
"""One-time LinkedIn OAuth helper.

Walks you through the 3-legged OAuth flow for the company-page poster app,
captures the authorization code on http://localhost:8765/callback, exchanges
it for an access + refresh token, and writes both into Secret Manager
(or prints the values for manual copy in local mode).

Usage:
    LINKEDIN_CLIENT_ID=xxx LINKEDIN_CLIENT_SECRET=yyy \\
        GCP_PROJECT_ID=daily-slop-v2 \\
        uv run python -m scripts.linkedin_oauth

Required scopes for organization posting (the app must be approved for
"Community Management API" / "Marketing Developer Platform"):
    r_organization_social w_organization_social w_member_social

The redirect URI `http://localhost:8765/callback` must be registered in the
LinkedIn developer app settings (auth tab).
"""

from __future__ import annotations

import argparse
import http.server
import os
import secrets
import sys
import threading
import urllib.parse
import webbrowser
from typing import Any

import httpx

REDIRECT_URI = "http://localhost:8765/callback"
AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
DEFAULT_SCOPES = "r_organization_social w_organization_social w_member_social rw_organization_admin"


class _Handler(http.server.BaseHTTPRequestHandler):
    code: str | None = None
    state: str | None = None

    def do_GET(self) -> None:  # noqa: N802 — http.server requires this name
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/callback":
            self.send_response(404)
            self.end_headers()
            return
        params = urllib.parse.parse_qs(parsed.query)
        _Handler.code = (params.get("code") or [None])[0]
        _Handler.state = (params.get("state") or [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        msg = "Authorization captured. You can close this tab."
        self.wfile.write(f"<h1>{msg}</h1>".encode())

    def log_message(self, *args: Any) -> None:  # silence the default access log
        pass


def _capture_code(state: str) -> str:
    server = http.server.HTTPServer(("127.0.0.1", 8765), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        while _Handler.code is None:
            pass
    finally:
        server.shutdown()
    if _Handler.state != state:
        raise RuntimeError("OAuth state mismatch — possible CSRF, aborting")
    assert _Handler.code is not None
    return _Handler.code


def _store_secret(project_id: str | None, secret_id: str, value: str) -> None:
    if not project_id:
        print(f"\n# {secret_id}\nprintf '%s' '{value}' | gcloud secrets versions add {secret_id} --data-file=-")
        return
    from google.cloud import secretmanager

    client = secretmanager.SecretManagerServiceClient()
    parent = f"projects/{project_id}/secrets/{secret_id}"
    client.add_secret_version(
        request={"parent": parent, "payload": {"data": value.encode("utf-8")}}
    )
    print(f"  ✓ wrote new version of {secret_id}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scopes", default=DEFAULT_SCOPES, help="space-separated OAuth scopes"
    )
    parser.add_argument(
        "--project",
        default=os.environ.get("GCP_PROJECT_ID"),
        help="GCP project id (omit to print gcloud commands instead)",
    )
    args = parser.parse_args()

    client_id = os.environ.get("LINKEDIN_CLIENT_ID")
    client_secret = os.environ.get("LINKEDIN_CLIENT_SECRET")
    if not client_id or not client_secret:
        print(
            "set LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET (from your LinkedIn app)",
            file=sys.stderr,
        )
        return 2

    state = secrets.token_urlsafe(16)
    auth_params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "scope": args.scopes,
        "state": state,
    }
    auth_url = f"{AUTH_URL}?{urllib.parse.urlencode(auth_params)}"
    print("\nOpen this URL to authorize (will open in your browser):\n")
    print(auth_url)
    print()
    webbrowser.open(auth_url)

    print("Waiting for redirect to http://localhost:8765/callback ...")
    code = _capture_code(state)
    print("✓ got authorization code")

    response = httpx.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    response.raise_for_status()
    body = response.json()
    access_token = body["access_token"]
    refresh_token = body.get("refresh_token", "")
    if not refresh_token:
        print(
            "WARNING: LinkedIn did not return a refresh_token. "
            "Your app may not be approved for refresh-token issuance — "
            "you'll need to re-run this script every ~60 days."
        )

    print(f"\naccess_token expires in {body.get('expires_in', '?')} seconds")
    print("\nWriting tokens...")
    _store_secret(args.project, "linkedin-client-id", client_id)
    _store_secret(args.project, "linkedin-client-secret", client_secret)
    _store_secret(args.project, "linkedin-access-token", access_token)
    if refresh_token:
        _store_secret(args.project, "linkedin-refresh-token", refresh_token)

    print("\nDone. Find your organization URN with:")
    print(
        f"  curl -H 'Authorization: Bearer {access_token[:8]}…' "
        "-H 'LinkedIn-Version: 202405' -H 'X-Restli-Protocol-Version: 2.0.0' "
        "'https://api.linkedin.com/rest/organizationAcls?q=roleAssignee&role=ADMINISTRATOR'"
    )
    print("Set LINKEDIN_ORG_URN (e.g. urn:li:organization:12345678) in Terraform vars.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
