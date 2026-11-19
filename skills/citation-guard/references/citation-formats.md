# Notes on citation matching

## What "unmatched" does and doesn't mean

An unmatched citation is **not proof it's fabricated**. Known benign reasons a
real citation can still come back unmatched:

- **No volume or page number.** CourtListener's citation-lookup API explicitly
  will not attempt to match a citation like `22 U.S. ___` that's missing a
  volume or page number — common in early drafts before a case is published
  with final pagination.
- **Very recent case.** There's a lag between a decision being handed down and
  it being indexed in CourtListener's database.
- **Non-case citations.** This tool is scoped to case-law citations. Statutes,
  regulations, and id./supra short-form references may extract via eyecite but
  aren't verified the same way.
- **Unusual reporter abbreviation.** eyecite's reporter database is extensive
  but not exhaustive for every regional or historical reporter.

Treat "unmatched" as "needs a human to check it directly," not as a verdict.

## Why both eyecite and the CourtListener API

- `eyecite` (https://github.com/freelawproject/eyecite) does local, offline
  extraction — pulling citation-shaped text out of a document. It's the same
  library CourtListener itself uses internally.
- The CourtListener Citation Lookup & Verification API
  (https://www.courtlistener.com/help/api/rest/v4/citation-lookup) does the
  actual verification against real case records — confirmed to require a free
  account token (anonymous requests return HTTP 401).

## Rate limits

Confirmed from CourtListener's docs: a single request won't process more than
250 citations (the 251st+ get a 429). There's also a general account-level
rate limit over time. For a very long brief, consider splitting it into
sections. The script does not auto-chunk large documents yet - it fails
loudly with a clear message rather than guessing, which is intentional
(see FINDINGS.md), but it is a real gap for very long briefs.

## Known limitations, found by adversarial testing (see FINDINGS.md)

- **Does not check whether a matched case is still good law.** A citation
  can be 100% real and still be overruled, reversed, or vacated. This tool
  only confirms existence - it is not a Shepard's/KeyCite replacement.
- **Cannot catch a real citation attached to a fabricated holding.** If an
  AI drafts "`Obergefell v. Hodges, 576 U.S. 644 (2015)` held that the earth
  is flat," every part of that citation is real and will match. Catching
  that the *holding* is fabricated requires reading the actual opinion
  against the quote/paraphrase - out of scope for a citation-lookup tool.
- **Coverage gaps produce false "unmatched."** Many state trial-court
  orders, administrative decisions, and unpublished/Westlaw-only opinions
  (`2024 WL 1234567`-style citations) aren't indexed in CourtListener's free
  database. "Unmatched" there reflects a coverage gap, not fabrication.
- **Short-form, `Id.`, and `supra` citations are not independently verified.**
  eyecite's own antecedent-resolution logic can misattribute which earlier
  citation a short cite refers to (observed "Unknown overlap case" warnings
  and a wrong antecedent guess during testing) - this tool deliberately does
  not attempt automatic resolution, to avoid adding a new source of false
  results on top of removing one.
- **The `name_cross_check` result's reliability depends on a live-confirmed
  API schema.** It was built and unit-tested against several plausible
  response shapes, but has not yet been run against a real CourtListener
  response (no API token was available during development). Treat
  `performed: false` as "not yet verified working," not as "no mismatch
  found."
