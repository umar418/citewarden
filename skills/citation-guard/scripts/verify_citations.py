#!/usr/bin/env python3
"""Extract case citations from text (via eyecite) and verify them against
CourtListener's free Citation Lookup & Verification API.

Usage:
    python3 verify_citations.py < brief.txt
    COURTLISTENER_API_TOKEN=xxx python3 verify_citations.py < brief.txt

Reads the full document text from stdin, prints one JSON object to stdout:
    {
      "citations_found_locally": [...],   # what eyecite extracted, for transparency
      "courtlistener_status": 200,
      "courtlistener_result": [...]       # raw API response - shape may vary; the
                                           # caller (Claude) interprets it, this
                                           # script does not guess at its fields
    }
On any setup error (missing deps, missing token, network failure) prints a
JSON object with an "error" key and exits 1 instead of guessing.
"""
import json
import os
import sys

API_URL = "https://www.courtlistener.com/api/rest/v4/citation-lookup/"
TOKEN_HELP = (
    "Set COURTLISTENER_API_TOKEN to a free token from "
    "https://www.courtlistener.com/profile/api/ (free account, not a paid API)."
)


def fail(message: str) -> None:
    print(json.dumps({"error": message}))
    sys.exit(1)


def main() -> None:
    try:
        import requests
    except ImportError:
        fail("Missing dependency 'requests'. Install with: pip install requests")
        return

    try:
        from eyecite import get_citations
    except ImportError:
        fail("Missing dependency 'eyecite'. Install with: pip install eyecite")
        return

    text = sys.stdin.read()
    if not text.strip():
        fail("No input text received on stdin.")
        return

    try:
        local_citations = [str(c) for c in get_citations(text)]
    except Exception as exc:  # eyecite failed to parse - still try the API directly
        local_citations = []
        local_extraction_error = str(exc)
    else:
        local_extraction_error = None

    token = os.environ.get("COURTLISTENER_API_TOKEN")
    if not token:
        fail(f"No COURTLISTENER_API_TOKEN set. {TOKEN_HELP}")
        return

    try:
        response = requests.post(
            API_URL,
            headers={"Authorization": f"Token {token}"},
            data={"text": text},
            timeout=30,
        )
    except requests.RequestException as exc:
        fail(f"Request to CourtListener failed: {exc}")
        return

    if response.status_code == 401:
        fail(f"CourtListener rejected the token (401 unauthorized). {TOKEN_HELP}")
        return
    if response.status_code == 429:
        fail(
            "CourtListener rate limit hit (429). This endpoint will not process "
            "more than 250 citations in one request, and also applies a rate "
            "limit over time - wait and retry with a shorter document."
        )
        return
    if response.status_code != 200:
        fail(f"CourtListener returned HTTP {response.status_code}: {response.text[:500]}")
        return

    try:
        result = response.json()
    except ValueError:
        fail("CourtListener returned a non-JSON response.")
        return

    print(json.dumps({
        "citations_found_locally": local_citations,
        "local_extraction_error": local_extraction_error,
        "courtlistener_status": response.status_code,
        "courtlistener_result": result,
    }))


if __name__ == "__main__":
    main()
