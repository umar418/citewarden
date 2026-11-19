#!/usr/bin/env python3
"""Extract case citations from text (via eyecite) and verify them against
CourtListener's free Citation Lookup & Verification API.

Usage:
    python3 verify_citations.py < brief.txt
    COURTLISTENER_API_TOKEN=xxx python3 verify_citations.py < brief.txt

Reads the full document text from stdin, prints one JSON object to stdout
(see OUTPUT SCHEMA below). On any setup error (missing deps, missing token,
network failure) prints a JSON object with an "error" key and exits 1
instead of guessing.

--- Hardening notes (from adversarial testing, see FINDINGS.md) ---

1. Single line-break normalization: text copy-pasted from a PDF very often
   has a hard newline in the middle of a citation (e.g. "576 U.S.\n644
   (2015)"). eyecite silently finds NOTHING in that case - a true false
   negative where a real citation just vanishes instead of being flagged.
   We collapse single newlines (not blank-line paragraph breaks) to spaces
   before extraction, specifically to catch this.

2. Citations are bucketed by what they actually are, instead of lumping
   everything into one flat list:
   - full case citations (the only kind this tool can ask CourtListener to
     verify)
   - short-form / Id. / supra citations (eyecite can find these, but they
     reference an earlier citation rather than standing alone - we do NOT
     attempt automatic antecedent resolution; eyecite's own resolver emits
     "Unknown overlap case" warnings on ambiguous short cites and its
     antecedent guesses can be wrong, so guessing here would just add a new
     source of false results instead of removing one)
   - statute/law citations and anything else eyecite finds that isn't a
     case citation - these are NOT covered by CourtListener's citation-
     lookup endpoint at all and must never be reported as "checked"

3. A full case citation missing a volume or page number (e.g. "22 U.S.
   ___") is marked unverifiable_format locally, instead of silently relying
   on the API to ignore it - so the final report can honestly say "N
   citations were never evaluated" rather than mixing them into "unmatched"
   where a reader would reasonably read that as "likely fake."

4. Name cross-check is the most important check this script attempts, and
   the one most likely to matter: a hallucinated citation can reuse a REAL
   reporter/volume/page (which will "match") while inventing the party
   names and holding. Matching the citation number alone does NOT catch
   this. We extract eyecite's own plaintiff/defendant metadata for each
   full citation and compare it, case-insensitively, against whatever case
   name CourtListener's response resolves that citation to.
   LIVE-CONFIRMED (see FINDINGS.md): tested against the real v4 endpoint
   with a real API token. Response shape is `[{"citation", "status",
   "clusters": [{"case_name", ...}]}]`; an unmatched citation has
   `status != 200` and `clusters: []`. Confirmed catching the exact attack
   this exists for: "Smith v. Winterbourne, 576 U.S. 644 (2015)" - a real
   citation (actually *Obergefell v. Hodges*) reused with invented party
   names - is correctly flagged HIGH severity, while the same citation
   cited correctly produces no false alarm.
   Also: eyecite can return an empty string for plaintiff/defendant on
   otherwise-correct citations (observed when a Unicode smart quote sits
   right before the case name). An empty/missing name is treated as
   "unknown - skip the check," never as an automatic mismatch, specifically
   to avoid a false "mismatch" flag on a perfectly real citation.
   A SEPARATE bug this live testing caught: the "text" field used to be
   eyecite's verbose debug repr (str(c)), not the clean citation string
   ("576 U.S. 644") CourtListener's API actually returns - which would have
   made every text match in this function silently fail. Fixed by using
   corrected_citation() instead.
"""
import difflib
import json
import os
import re
import sys

API_URL = "https://www.courtlistener.com/api/rest/v4/citation-lookup/"
TOKEN_HELP = (
    "Set COURTLISTENER_API_TOKEN to a free token from "
    "https://www.courtlistener.com/profile/api/ (free account, not a paid API)."
)

# Collapse a single newline (likely a PDF/line-wrap artifact) to a space,
# but leave blank lines (paragraph breaks, "\n\n") alone.
_SINGLE_NEWLINE = re.compile(r"(?<!\n)\n(?!\n)")


def normalize_text(text: str) -> str:
    return _SINGLE_NEWLINE.sub(" ", text)


def fail(message: str) -> None:
    print(json.dumps({"error": message}))
    sys.exit(1)


def categorize_citations(citations):
    full_case, short_or_id, other = [], [], []
    for c in citations:
        kind = type(c).__name__
        if kind == "FullCaseCitation":
            # IMPORTANT: str(c) is eyecite's verbose debug repr
            # (e.g. "FullCaseCitation('576 U.S. 644', groups={...}, metadata=...)"),
            # NOT the clean citation string. CourtListener's API returns the clean
            # form ("576 U.S. 644") in its "citation" field - using str(c) here would
            # make every text-based match against the API response silently fail.
            # corrected_citation() gives the clean, comparable string. Found and
            # fixed during live testing - see FINDINGS.md.
            text = c.corrected_citation()
            meta = c.metadata
            volume = c.groups.get("volume")
            page = c.groups.get("page")
            plaintiff = (meta.plaintiff or "").strip()
            defendant = (meta.defendant or "").strip()
            full_case.append({
                "text": text,
                "plaintiff": plaintiff or None,
                "defendant": defendant or None,
                "year": meta.year,
                "volume": volume,
                "reporter": c.groups.get("reporter"),
                "page": page,
                "verifiable_format": bool(volume and page),
            })
        elif kind in ("ShortCaseCitation", "IdCitation", "SupraCitation"):
            short_or_id.append({"text": str(c), "type": kind})
        else:
            other.append({"text": str(c), "type": kind})
    return full_case, short_or_id, other


# Common, unambiguous legal-name abbreviations. Kept deliberately small and
# conservative - every entry here is safe to expand in both directions with
# no realistic ambiguity. "U.S." is the single most important one: it is
# probably the most frequent party name in all of American case law (every
# federal criminal/civil case brought by the government), and a strict
# substring check flags it as a mismatch against CourtListener's
# "United States v. ..." every single time - a false "HIGH severity
# hallucination" on completely ordinary, correct citations. Found live - see
# FINDINGS.md, Pass 4.
_ABBREV_EXPANSIONS = {
    "u.s.": "united states", "u.s": "united states", "us": "united states",
    "gov't": "government", "govt": "government",
    "dep't": "department", "dept": "department",
    "ass'n": "association", "assn": "association",
    "corp.": "corporation", "corp": "corporation",
    "inc.": "incorporated", "inc": "incorporated",
    "co.": "company",
    "bros.": "brothers", "bros": "brothers",
    "mfg.": "manufacturing", "mfg": "manufacturing",
    "&": "and",
}
_ET_AL = re.compile(r"\bet\s+al\.?\b")
_PUNCT = re.compile(r"[.,'’]")
_WS = re.compile(r"\s+")


def _normalize_name(name: str) -> str:
    name = name.lower()
    name = _ET_AL.sub("", name)
    for abbr, full in _ABBREV_EXPANSIONS.items():
        name = re.sub(r"(?<!\w)" + re.escape(abbr) + r"(?!\w)", full, name)
    name = _PUNCT.sub("", name)
    return _WS.sub(" ", name).strip()


def _names_plausibly_match(party: str, resolved_name: str) -> bool:
    """Deliberately conservative: biased toward NOT flagging a mismatch,
    because a false "this looks like a hallucination" accusation on a real,
    correctly-cited case is worse for trust in this tool than occasionally
    staying quiet on a genuine mismatch (which still shows up as a citation
    the user can see and the disclaimers already tell them to verify names
    manually)."""
    p = _normalize_name(party)
    r = _normalize_name(resolved_name)
    if not p:
        return True  # unknown name (e.g. smart-quote artifact) - don't accuse
    if p in r:
        return True
    for side in re.split(r"\bv\b", r):
        side = side.strip()
        if side and difflib.SequenceMatcher(None, p, side).ratio() > 0.6:
            return True
    return False


def attempt_name_cross_check(full_case_citations, api_result):
    """Best-effort comparison of eyecite's extracted party names against
    whatever case name(s) CourtListener's response resolves each citation to.
    Response shape is live-confirmed - see FINDINGS.md, Pass 3 and 4."""
    if not isinstance(api_result, list):
        return {"performed": False, "note": "API result was not a list - unexpected shape, skipped."}

    mismatches = []
    checked = 0
    for item in api_result:
        if not isinstance(item, dict):
            continue
        clusters = [cl for cl in (item.get("clusters") or []) if isinstance(cl, dict)]
        # Collect every candidate case name CourtListener returned for this
        # citation - an ambiguous citation can resolve to more than one real
        # case. Only flag a mismatch if the cited party matches NONE of them.
        resolved_names = [cl.get("case_name") for cl in clusters if cl.get("case_name")]
        resolved_names += [item.get("case_name"), item.get("caseName")]  # legacy/alt shapes, defensive
        resolved_names = [n for n in resolved_names if n]
        cite_text = item.get("citation") or item.get("normalized_citation") or ""
        if not resolved_names or not cite_text:
            continue
        match = next((fc for fc in full_case_citations if fc["text"] == cite_text), None)
        if not match:
            continue
        checked += 1
        for party in (match["plaintiff"], match["defendant"]):
            if not party:  # unknown name (e.g. smart-quote artifact) - skip, don't accuse
                continue
            if not any(_names_plausibly_match(party, rn) for rn in resolved_names):
                mismatches.append({
                    "citation": cite_text,
                    "cited_as": f'{match["plaintiff"]} v. {match["defendant"]}',
                    "courtlistener_case_name": resolved_names[0],
                    "severity": "HIGH - real citation number, party names do not match the real case",
                })
                break

    if checked == 0:
        return {
            "performed": False,
            "note": (
                "Could not match any API result item back to an extracted citation "
                "using the known response shape (citation/clusters[].case_name, "
                "live-confirmed - see FINDINGS.md). Either there were no full case "
                "citations to check, or CourtListener changed its response shape. "
                "Manually confirm party names against the citation yourself."
            ),
        }
    return {"performed": True, "checked": checked, "possible_mismatches": mismatches}


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

    raw_text = sys.stdin.read()
    if not raw_text.strip():
        fail("No input text received on stdin.")
        return

    text = normalize_text(raw_text)

    try:
        citations = get_citations(text)
        extraction_error = None
    except Exception as exc:
        citations = []
        extraction_error = str(exc)

    full_case, short_or_id, other = categorize_citations(citations)
    unverifiable_format = [fc for fc in full_case if not fc["verifiable_format"]]

    token = os.environ.get("COURTLISTENER_API_TOKEN")
    if not token:
        fail(f"No COURTLISTENER_API_TOKEN set. {TOKEN_HELP}")
        return

    # CourtListener's citation-lookup endpoint rejects any text over 64,000
    # characters outright (confirmed live - see FINDINGS.md, Pass 4). A real
    # brief or motion can easily run longer than that. Catch it here with a
    # clear, actionable message instead of letting the user hit a raw
    # "Ensure this field has no more than 64000 characters" API error.
    if len(text) > 64000:
        fail(
            f"Document is {len(text)} characters - CourtListener's citation-lookup "
            "API accepts at most 64,000 characters per request. Split the document "
            "into sections of roughly that size or smaller and check each separately."
        )
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
            "limit over time - split the document into smaller sections and "
            "retry each one; this script does not auto-chunk yet."
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
        "normalization_applied": text != raw_text,
        "local_extraction_error": extraction_error,
        "full_case_citations": full_case,
        "unverifiable_format_count": len(unverifiable_format),
        "short_form_or_id_citations": short_or_id,
        "other_non_case_citations": other,
        "courtlistener_status": response.status_code,
        "courtlistener_result": result,
        "name_cross_check": attempt_name_cross_check(full_case, result),
        "disclaimers": [
            "A 'matched' result means the citation number corresponds to a real case. "
            "It does NOT mean that case is still good law - this tool does not check "
            "whether a matched case was later overruled, reversed, or vacated.",
            "A real case can still be cited for a holding or quote it does not "
            "actually contain. This tool cannot detect that - it only confirms the "
            "citation exists.",
            "'Unmatched' can mean the citation is fabricated, OR that it's real but "
            "not indexed in CourtListener's free database (common for state trial "
            "court orders, very recent decisions, or unpublished/Westlaw-only "
            "opinions). Always say 'could not verify,' never 'this is fake.'",
        ],
    }))


if __name__ == "__main__":
    # Top-level safety net: an end user here is often a non-technical lawyer,
    # not a developer. A raw Python traceback is unprofessional at best and,
    # for a tool whose entire pitch is "trustworthy," actively undermines it.
    # Anything truly unexpected becomes a clean JSON error instead of a dump.
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 - intentional catch-all, see above
        fail(f"Unexpected error: {type(exc).__name__}: {exc}")
