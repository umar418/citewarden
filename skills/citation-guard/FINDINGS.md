# Citation Guard — adversarial test findings

Two passes, as requested: first as a tester trying to break the extraction
and plumbing, then as an experienced law professional asking where this
could mislead someone who actually relies on it in practice. A third pass
below is a live-API follow-up once a real CourtListener token became
available.

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

## Pass 3 — Live API follow-up (real CourtListener token)

Once a real free API token was available, ran the exact scenarios above
against the live v4 endpoint instead of simulated response shapes.

**Confirmed response schema:** `[{"citation": "576 U.S. 644", "status": 200,
"error_message": "", "clusters": [{"case_name": "Obergefell v. Hodges",
...}]}]` for a match; `"status": 404, "error_message": "Citation not
found: '...'", "clusters": []` for no match. The name-matching logic
written against guessed field names (`case_name` inside `clusters[]`)
turned out to be correct on the first try.

**Found a second real bug in the process, independent of the guessed-schema
caveat:** the `"text"` field used to populate each citation's record used
`str(c)`, which is eyecite's verbose debug repr -
`"FullCaseCitation('576 U.S. 644', groups={...}, metadata=...)"` - not the
clean citation string. CourtListener's API returns the clean form
("576 U.S. 644") in its `"citation"` field. Matching one against the other
would have silently returned zero matches every single time, regardless of
whether the schema-guessing was right - the whole name cross-check would
have quietly done nothing on every real document. **Fixed:** use eyecite's
`corrected_citation()` method, which returns the clean, comparable string.
This is the kind of bug that's especially dangerous for a hallucination
checker specifically because it fails *silent and green* - `performed:
true, checked: 0, possible_mismatches: []` looks identical to "ran cleanly,
found nothing wrong," not to "broken."

**Live results, both directions:**
- `"Smith v. Winterbourne, 576 U.S. 644 (2015) established a right to
  privacy in orbit."` → citation matched (it's real), name cross-check
  correctly flagged it HIGH severity: cited as "Smith v. Winterbourne,"
  CourtListener resolves it to "Obergefell v. Hodges."
- The same citation cited correctly (`"Obergefell v. Hodges, 576 U.S. 644
  (2015)..."`) → matched, zero mismatches. No false alarm on the real thing.
- A fully fabricated citation (`"Flibbertigibbet v. Nonexistent Corp., 999
  F.4th 123 (9th Cir. 2024)"`) → `status: 404`, `clusters: []`, exactly the
  "doesn't exist" signal expected.

This closes open item #1 from Pass 2. `attempt_name_cross_check()` and its
docstring have been updated to state this is live-confirmed rather than
best-effort.

## Pass 4 — Hard multidimensional pass before public release

Requested explicitly as a pre-release check, treating this as a reputation
question, not just a code check. Widened scope beyond citation-matching
correctness to security, crash safety, and real-world document shape.

**1. Command injection / reliability break via how the script is invoked -
the most severe finding of this pass.** `SKILL.md` told Claude to "run the
bundled script, passing the text on stdin" without specifying the mechanism.
Proved concretely (harmless `touch` payload, not run against anything real)
that the natural-looking approach - inlining the pasted document into an
`echo "<text>" | python3 ...` shell command - lets a crafted citation-like
string execute arbitrary shell commands via unquoted `$(...)`. Separately,
and just as importantly for a legal tool: **ordinary legal text containing
a quotation mark** (quoting a contract, a statute, a deposition - extremely
common) breaks a naively-quoted inline command even with no malicious
intent at all, so this was also a plain reliability bug, not only a
security one. **Fixed:** `SKILL.md` now mandates writing the pasted text to
a file with the Write tool first and redirecting the script's input from
that file's path (`< /path/to/file.txt`), never interpolating document
content into a command string. Severity: **critical** - this is an
actual-code-execution-on-the-user's-machine class of bug, from a tool whose
entire premise is trustworthiness.

**2. The most common real-world name-matching false positive imaginable.**
Live-tested `"U.S. v. Nixon, 418 U.S. 683 (1974)"` - a real, correctly
cited case. CourtListener resolves it to "United States v. Nixon." The
strict substring check from Pass 3 flagged this as a **HIGH severity
hallucination** - on one of the single most common citation patterns in
all of American law (the U.S. government as a party). Shipping this would
mean the tool cries wolf on completely routine citations from the first
real brief anyone ran through it. **Fixed:** replaced strict substring
matching with `_names_plausibly_match()` - a small, conservative
abbreviation table (U.S./government/dept/assn/corp/inc/co/bros/mfg/&) plus
a fuzzy fallback (`difflib.SequenceMatcher`, threshold 0.6) against each
side of the resolved case name. Deliberately biased toward **not**
flagging, since a false accusation on a real case does more reputational
damage than quietly missing a borderline one (which the standing
disclaimers already tell the user to verify manually regardless).
Re-verified both directions: "U.S. v. Nixon" no longer flags; "Smith v.
Winterbourne" (the real Pass-3 hallucination test, actually *Obergefell v.
Hodges*) still correctly flags. Also unit-tested that genuinely different
names ("Smith", "Winterbourne" against "Obergefell v. Hodges") are still
caught - the fuzzy threshold was chosen to be forgiving of near-miss
spelling only, not of a different case entirely.

**3. Ambiguous citations only checked their first candidate match.** A
citation that resolves to more than one real case (CourtListener can return
multiple `clusters` for one citation) was only compared against
`clusters[0]`. Fixed to check the cited name against *all* returned
clusters and only flag a mismatch if none of them match.

**4. No safety net for genuinely unexpected failures.** A non-technical
lawyer is the target user; a raw Python traceback is exactly the kind of
output that destroys trust in a "trustworthy citations" tool on sight.
Added a top-level `try/except` around `main()` that converts anything
unexpected into the same clean `{"error": ...}` JSON shape the script
already uses elsewhere, never a stack trace. **Verified with a real
failure, not a hypothetical one:** feeding the script 200 bytes of raw
`/dev/urandom` (simulating, e.g., someone accidentally piping in a binary
file) hit a `UnicodeEncodeError` deep inside output serialization - the
safety net caught it and printed a clean one-line JSON error instead of a
traceback.

**5. CourtListener's API silently caps input at 64,000 characters.**
Discovered by testing an intentionally long document (~480,000 characters,
simulating a long brief with exhibits): the API rejected it with a raw
validation error (`"Ensure this field has no more than 64000 characters"`).
A real, lengthy federal appellate brief can realistically exceed this.
**Fixed:** a pre-flight length check now gives a clear, actionable message
("split the document into sections") instead of surfacing the raw API
error text.

**6. Scope wasn't stated plainly enough.** Neither `eyecite` nor
CourtListener's database covers non-U.S. case law. Added an explicit "U.S.
case law only" line near the top of the README so a non-U.S. user doesn't
get confusing silent-failure behavior and conclude the tool is broken.

**Confirmed NOT reputational risks, checked and ruled out this pass:**
- The API token is never printed, logged, or written to any file in the
  repo at any point - re-confirmed by reading every `fail()` call site.
- Mixed/garbled Unicode (emoji, right-to-left Arabic script, Japanese) next
  to a real citation does not corrupt extraction or trigger a false
  mismatch - tested directly, extracted and matched cleanly.
- `plugin.json`'s `repository` field is still a placeholder
  (`github.com/omarai/citation-guard`) - not a bug, but **flagged as a
  release blocker**: this needs Umar's real GitHub handle before this goes
  out publicly, or the link in the published plugin will point nowhere.

## Severity-ranked summary

| Finding | Type of false result | Status |
|---|---|---|
| Real citation # + fake party names passes a naive check | False **positive** (verified a hallucination) | Fixed (name cross-check), live-confirmed against the real API |
| `text` field used debug repr, not clean citation string | Would have made the name cross-check silently match nothing, ever (fails green) | Fixed (`corrected_citation()`), live-confirmed |
| PDF line-wrap makes a real citation invisible | False **negative** (silent, not even flagged) | Fixed (newline normalization) |
| "Matched" read as "still good law" | Misleading omission | Fixed (standing disclaimer) |
| Real cite, fabricated holding | Undetectable by design | Documented, not fixable by this approach |
| Coverage gaps read as "fake" | False **negative** in effect (unwarranted suspicion) | Mitigated (disclaimer language), not eliminated |
| Smart-quote-corrupted empty name | Would have fed finding #1 as a false mismatch | Fixed (empty name = skip, not mismatch) |
| Statute/Id./supra cites implied as "checked" | Misleading scope | Fixed (separate buckets) |
| Parallel citations double-counted | User confusion | Open, not fixed this pass |
| >250 citations in one document | Hard failure (loud, not silent) | Acceptable as-is; no auto-chunking |
| Inlined document text in a shell command → injection + breaks on quotes | Security (code execution) + reliability | **Fixed** (SKILL.md mandates file-redirect, never inline) |
| "U.S. v. X" flagged as mismatch against "United States v. X" | False **positive**, on the most common case-name pattern in U.S. law | **Fixed** (abbreviation table + fuzzy match) |
| Ambiguous citation only checked against first of several possible matches | Potential false positive | **Fixed** (checks all clusters) |
| Unexpected exception → raw traceback shown to a non-technical user | Trust/professionalism | **Fixed** (top-level safety net, verified with real binary-input crash) |
| Document over 64,000 characters → raw API validation error | Confusing failure on long real briefs | **Fixed** (clear pre-flight message) |
| No "U.S. only" scope statement | Confusing silent failure for non-U.S. users | **Fixed** (stated in README) |
| `plugin.json` repository URL is still a placeholder | Broken link if published as-is | **Open - release blocker, needs Umar's real GitHub handle** |

## Open items for a human to close out

1. ~~Get a free CourtListener API token and run this against real cases~~
   — **done.** Live-confirmed in Pass 3 above.
2. **Replace the placeholder GitHub URL in `plugin.json` and `README.md`**
   with the real repository location before publishing - currently a
   non-functional placeholder.
3. **Decide if parallel-citation de-duplication is worth building** — low
   severity, but it's the kind of thing that erodes trust in the tool's
   output through sheer visual noise.
4. **Decide if >250-citation documents are common enough in practice to
   justify auto-chunking** — currently it fails loudly instead, which is
   honest but not graceful. Same question now applies to the 64,000
   character cap.
