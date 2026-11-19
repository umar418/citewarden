# Citation Guard — adversarial test findings

Two passes, as requested: first as a tester trying to break the extraction
and plumbing, then as an experienced law professional asking where this
could mislead someone who actually relies on it in practice.

**Scope limitation, stated up front:** no CourtListener API token was
available during this pass (creating that account was left for Umar, per
the earlier plan). Everything involving live verification results is
therefore reasoned through and defensively coded, not confirmed against a
real response. That gap is itself the top open item below.

## Pass 1 — Tester: break the extraction

Ran fourteen adversarial inputs through `eyecite` directly. Two produced
real, reproducible false results; the rest were fine or benign.

| # | Input | Result before fix | Severity |
|---|---|---|---|
| 1 | Citation split by a line break (`576 U.S.\n644 (2015)`) — the single most common artifact of copy-pasting from a PDF | **eyecite found zero citations.** Not "unmatched" — silently invisible. A brief with ten real citations, one of them PDF-wrapped, would report nine checked and the tenth would never even appear, with nothing telling the user it was missed. | **Critical — true false negative, total silence** |
| 2 | Case name preceded by a Unicode smart/curly quote (`"Obergefell v. Hodges, 576 U.S. 644 (2015)"` — the quote style every Word/Google Docs paste produces) | eyecite still found the citation, but `plaintiff` came back as an **empty string** instead of `"Obergefell"`. Harmless on its own, but dangerous feeding into a name-mismatch check (see Pass 2, #4) — an empty name could be misread as "doesn't match," flagging a perfectly real citation as suspicious for a typographic reason only. | High (as an input to the name check) |
| 3 | Citation missing a volume/page (`22 U.S. ___`) | Extracted fine locally, but CourtListener's own docs say it won't even attempt to match citations like this. Before the fix, this would have silently fallen into "sent to the API, got no match" — indistinguishable from a real fabrication. | Medium — misleading bucketing, not a crash |
| 4 | Mixed document: a real case citation + a statute (`42 U.S.C. § 1983`) + an `Id.` + a `supra` | All four extracted correctly, but the original script treated them as one flat list. A statute citation sitting next to "unmatched" case citations in one undifferentiated list invites the reader to assume it was checked the same way case citations were — it wasn't; CourtListener's citation-lookup doesn't cover statutes at all. | Medium — scope-creep in reporting, not extraction |
| 5 | `resolve_citations()` (eyecite's own antecedent-resolution helper, tried as a way to link `Id.`/short-form cites back to their full citation) | eyecite itself logged `Unknown overlap case` on an ambiguous short cite and **guessed the wrong antecedent** (attributed `Brown, 347 U.S. at 495` to "Board of Educ." instead of "Brown"). Decided **not** to use this function in the shipped script — it would have added a new, confident-sounding wrong answer on top of the problem this tool exists to prevent. | N/A — deliberately not shipped |
| — | Zero-citation text, pure statute text, a non-citation string that merely contains numbers resembling a reporter (`"$576 million U.S. dollars for 644 new jobs"`) | All handled correctly — no crash, no false-positive extraction. | None |

**Fixes shipped** (in `scripts/verify_citations.py`): single-newline
normalization before extraction (fixes #1); empty-string names are mapped to
"unknown, skip" rather than treated as present (fixes #2's downstream risk);
citations are now bucketed into `full_case_citations` /
`unverifiable_format_count` / `short_form_or_id_citations` /
`other_non_case_citations` instead of one flat list (fixes #3 and #4); #5's
resolver is intentionally not used, and that decision is documented in the
code and in `references/citation-formats.md`.

## Pass 2 — Experienced law professional: where this could actually mislead someone

Putting on the "would I trust this before filing" hat, in order of how much
damage each gap could do:

**1. A real citation number with invented party names is the attack this
tool was built for — and a naive "does this citation exist" check completely
misses it.** Tested directly: `"Smith v. Winterbourne, 576 U.S. 644 (2015)
established a right to privacy in orbit."` The citation `576 U.S. 644` is
real (it's *Obergefell v. Hodges*). A naive check — "is 576 U.S. 644 a real
reporter entry?" — returns yes, and a tool that stops there would report
this fabrication as **verified**. This is arguably the single most important
thing a tool like this has to catch, because it's exactly the pattern AI
models produce when they hallucinate: they don't usually invent an
impossible reporter number, they recombine real building blocks. **Fix
shipped:** `attempt_name_cross_check()` compares eyecite's extracted party
names against whatever case name the API resolves the citation to, and
flags a mismatch as HIGH severity, ranked above the plain matched/unmatched
status in how `SKILL.md` tells Claude to present results. **Caveat, stated
honestly:** this is unit-tested against simulated response shapes, not
against a real CourtListener response — see Open Items below.

**2. "Matched" will be read as "safe to cite" — it isn't.** A matched
citation only proves the case exists. It says nothing about whether that
case is still good law. A real lawyer's mental model of a "citation checker"
is shaped by Shepard's/KeyCite, which do check that. If this tool's output
doesn't scream the difference, someone will treat "matched ✓" as a
Shepardizing substitute, cite a reversed or overruled case with full
confidence, and the tool will have actively made that worse, not better,
because it manufactured false confidence. **Fix shipped:** this is now a
standing disclaimer the script emits with every result and `SKILL.md`
requires Claude to relay every time, not just on request.

**3. A real citation can support a fake proposition, and nothing here (or
in any citation-lookup tool) can catch that.** Tested directly: `"Obergefell
v. Hodges, 576 U.S. 644 (2015) held that the earth is flat."` Every token in
that citation is genuine. The only way to catch the fabricated holding is to
read the actual opinion text against the claim — a fundamentally different
(and much harder) problem than citation verification. This is a hard
limitation, not a bug, and it needs to be stated plainly rather than
implied, because "citation checker" is an easy name to over-trust.
**Fix shipped:** added as its own named disclaimer, separate from the
good-law-status one above, since they're different failure modes.

**4. Coverage gaps will produce false "unmatched" results, and a reader
will reasonably read "unmatched" as "probably fake."** CourtListener is
strong on federal and state appellate case law, weaker on state trial-court
orders, administrative decisions, and unpublished/Westlaw-only citations
(`2024 WL 1234567`-style). A solo practitioner citing a real trial-court
order will very plausibly get "unmatched" through no fault of their own.
**Fix shipped:** the standing disclaimer language is explicit that
"unmatched" must always be presented as "could not verify," never as "this
is fake," with the coverage-gap explanation included every time.

**5. Parallel citations to the same case will look like two separate
citations to check, which could confuse rather than clarify.** `Brown v.
Board of Educ., 347 U.S. 483, 74 S. Ct. 686 (1954)` extracts as two
`FullCaseCitation` objects (one per reporter) sharing the same parties and
year. Not fixed in code this pass — flagged as an open item below, since it
risks only user confusion (e.g., "1 of 2 matched" read as a partial failure
of one real citation), not a false verified/unverified verdict.

## Severity-ranked summary

| Finding | Type of false result | Status |
|---|---|---|
| Real citation # + fake party names passes a naive check | False **positive** (verified a hallucination) | Fixed (name cross-check), unverified against live API |
| PDF line-wrap makes a real citation invisible | False **negative** (silent, not even flagged) | Fixed (newline normalization) |
| "Matched" read as "still good law" | Misleading omission | Fixed (standing disclaimer) |
| Real cite, fabricated holding | Undetectable by design | Documented, not fixable by this approach |
| Coverage gaps read as "fake" | False **negative** in effect (unwarranted suspicion) | Mitigated (disclaimer language), not eliminated |
| Smart-quote-corrupted empty name | Would have fed finding #1 as a false mismatch | Fixed (empty name = skip, not mismatch) |
| Statute/Id./supra cites implied as "checked" | Misleading scope | Fixed (separate buckets) |
| Parallel citations double-counted | User confusion | Open, not fixed this pass |
| >250 citations in one document | Hard failure (loud, not silent) | Acceptable as-is; no auto-chunking |

## Open items for a human to close out

1. **Get a free CourtListener API token and run this against real cases**
   — including a real hallucinated-name test like the one above — to
   confirm `attempt_name_cross_check()`'s field-matching actually works
   against the live v4 response schema, and tell me the real field names so
   the guesswork in that function can be replaced with certainty.
2. **Decide if parallel-citation de-duplication is worth building** — low
   severity, but it's the kind of thing that erodes trust in the tool's
   output through sheer visual noise.
3. **Decide if >250-citation documents are common enough in practice to
   justify auto-chunking** — currently it fails loudly instead, which is
   honest but not graceful.
