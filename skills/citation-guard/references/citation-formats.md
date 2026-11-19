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
sections.
