# CiteWarden

**CiteWarden is a free, open-source legal citation checker that catches AI-hallucinated case citations before you file.** It's a plugin for Claude Code and Claude that verifies every case-law citation in a brief, memo, or AI-drafted legal document against the real U.S. court record — so a fabricated or mismatched citation never makes it into a filing.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

## Why CiteWarden exists

AI-drafted legal text has a well-documented, costly failure mode: fabricated or mismatched case citations. Public trackers have logged over 1,400 court incidents where filings cited fake or inaccurate AI-generated cases, and a 2025 Stanford study found that even paid, commercial legal-AI research tools still hallucinate citations in 17–33% of hard queries. Courts have sanctioned lawyers, and law firms have had to refund client fees, over citations an AI assistant made up.

CiteWarden is a fast, free, last-line check: paste a brief or memo, and it tells you which citations are confirmed real and which it couldn't verify — including the one hallucination pattern most citation tools miss entirely (see below).

## What CiteWarden does

1. **Extracts** every case citation from the text you paste, using [`eyecite`](https://github.com/freelawproject/eyecite) — Free Law Project's open-source citation-parsing library (the same engine that powers CourtListener itself).
2. **Verifies** each one against [CourtListener's Citation Lookup & Verification API](https://www.courtlistener.com/help/api/rest/v4/citation-lookup) — a free, official API built by the same nonprofit specifically "to validate that a citation is not hallucinated."
3. **Cross-checks party names**, not just the citation number. A citation can reuse a *real* reporter/volume/page while the AI invents the case name and holding — the single most realistic hallucination pattern, and the one a naive "does this citation exist" check completely misses. CiteWarden flags this as a high-severity mismatch, using abbreviation-aware, fuzzy name matching so it doesn't cry wolf on routine citations like "U.S. v. Nixon" (a real case, correctly abbreviated — not a hallucination).
4. **Reports clearly**, bucketing results into verified, unverifiable (never evaluated), and genuinely unmatched, with plain-language disclaimers every time — never "this is fake," always "this could not be verified."

**This is not legal advice**, and a clean result doesn't replace your own professional review of the document.

## Scope: U.S. case law only

Both `eyecite` and CourtListener's database are built around U.S. federal and state court citations. CiteWarden will not recognize or verify citations from other countries' courts (UK neutral citations, Canadian, Australian, etc.).

## Why a plugin, not another AI chatbot prompt

Confirming whether a case citation is real requires checking it against an actual case-law database — something a plain chat with an AI assistant cannot do on its own, since it has no live access to court records. Asking ChatGPT or Claude "is this citation real?" with no tools wired up just produces another guess. CiteWarden wires up that access for free, using only free, official data sources — no paid API, no subscription, no hosting cost to anyone.

## Example

**Input:** `"Smith v. Winterbourne, 576 U.S. 644 (2015) established a right to privacy in orbit."`

**CiteWarden's result:** the citation number (576 U.S. 644) is real — but it's actually *Obergefell v. Hodges*, not "Smith v. Winterbourne." CiteWarden flags this as a high-severity name mismatch: a strong signal of a hallucination that reused a genuine citation with an invented case name.

Cited correctly — `"Obergefell v. Hodges, 576 U.S. 644 (2015)..."` — the same citation produces a clean match with no false alarm.

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/umar418/citewarden.git
   ```
2. Add it to Claude Code as a plugin (via a local plugin marketplace entry pointing at this folder, or by adding the repository directly as a plugin source — see Claude Code's plugin documentation for the current install command).
3. Get a **free** CourtListener API token at [courtlistener.com/profile/api](https://www.courtlistener.com/profile/api/) (a free Free Law Project account — not a paid API) and export it:
   ```bash
   export COURTLISTENER_API_TOKEN=your_free_token_here
   ```
4. Install the two small Python dependencies:
   ```bash
   pip install eyecite requests
   ```
5. In Claude Code, paste a brief or memo and ask: *"Can you check if these citations are real?"*

## Limitations (read before relying on this)

CiteWarden confirms a citation **exists**. It does not confirm:

- that the case is still **good law** — not overruled, reversed, or vacated. CiteWarden is not a Shepard's/KeyCite replacement.
- that the case actually **says** what it's being cited for. A real citation can still be attached to a fabricated quote or holding.
- anything about state trial-court orders, administrative decisions, or unpublished/Westlaw-only citations not indexed in CourtListener's free database — those can come back "unmatched" for coverage reasons, not because they're fake.

CourtListener's API also caps each request at 64,000 characters — a long brief or motion may need to be split into sections and checked separately.

See [`skills/citewarden/FINDINGS.md`](skills/citewarden/FINDINGS.md) for the full adversarial test report these limitations came from — including every false positive and false negative found while trying to break this tool before release, and how each was fixed.

## FAQ

**What is CiteWarden?**
CiteWarden is a free, open-source tool that checks whether the case-law citations in a legal document are real, catching the kind of AI-hallucinated citations that have gotten lawyers sanctioned in court.

**Is CiteWarden free?**
Yes. It's MIT-licensed and built entirely on free, official data sources (Free Law Project's `eyecite` and CourtListener API) — no paid API, no subscription.

**Does CiteWarden tell me if a case is still good law?**
No — that's a deliberate scope limit, not an oversight. See Limitations above.

**Does CiteWarden work for non-U.S. citations?**
No, it's scoped to U.S. federal and state case law.

## Credits

Built on two free, open projects from [Free Law Project](https://free.law/): [`eyecite`](https://github.com/freelawproject/eyecite) (BSD license) for citation extraction, and the [CourtListener API](https://www.courtlistener.com/help/api/rest/) for verification. This repository's own code is MIT licensed — see `LICENSE`.

Made by [Omar AI](https://omarai.org) — AI automation for professional services.
