# Citation Guard

A free Claude Code / Claude plugin that catches hallucinated legal citations
**before you file them.**

AI-drafted legal text has a well-documented failure mode: fabricated or
mismatched case citations. Public trackers have logged over 1,400 court
incidents where filings cited fake or inaccurate AI-generated cases, and a
2025 Stanford study found even paid, commercial legal-AI tools still
hallucinate citations in 17-33% of hard queries. This plugin gives you a fast,
free, last-line check: paste a brief or memo, and it tells you which
citations are confirmed real and which it couldn't verify.

## What it does

1. Extracts every case citation from the text you paste, using
   [`eyecite`](https://github.com/freelawproject/eyecite) — Free Law
   Project's open-source citation-parsing library (the same one that powers
   CourtListener itself).
2. Checks each one against
   [CourtListener's Citation Lookup & Verification API](https://www.courtlistener.com/help/api/rest/v4/citation-lookup) —
   a free, official API built by the same nonprofit specifically "to validate
   that a citation is not hallucinated."
3. Reports which citations matched a real case (with the confirmed case
   name/court/year) and which didn't, so you can check those manually before
   relying on them.

**This is not legal advice**, and a clean result doesn't replace your own
professional review of the document.

## Why this, and not just asking an AI chatbot

Confirming whether a case citation is real requires checking it against an
actual case-law database — something a plain chat with an AI assistant can't
do on its own, since it has no live access to court records. This plugin
wires that access up for you, for free.

## Example

Input: a short paragraph citing `Obergefell v. Hodges, 576 U.S. 644 (2015)`
(real) alongside a fabricated case name with a plausible-looking citation.
Output: the real case is matched and confirmed; the fabricated one comes back
unmatched, flagged for manual review.

## Install

1. Clone this repo.
2. Add it to Claude Code as a plugin (via a local plugin marketplace entry
   pointing at this folder, or by adding the repo directly as a plugin
   source) — see Claude Code's plugin documentation for the current install
   command.
3. Get a **free** CourtListener API token at
   https://www.courtlistener.com/profile/api/ (a free account with Free Law
   Project, a nonprofit — not a paid API) and set it as an environment
   variable:
   ```bash
   export COURTLISTENER_API_TOKEN=your_free_token_here
   ```
4. Install the two small Python dependencies the skill's script needs:
   ```bash
   pip install eyecite requests
   ```
5. In Claude Code, paste a brief or memo and ask: *"can you check if these
   citations are real?"*

## Credits

Built on two free, open projects from [Free Law Project](https://free.law/):
[`eyecite`](https://github.com/freelawproject/eyecite) (BSD license) for
citation extraction, and the
[CourtListener API](https://www.courtlistener.com/help/api/rest/) for
verification. This repository's own code is MIT licensed — see `LICENSE`.

Made by [Omar AI](https://omarai.org).
