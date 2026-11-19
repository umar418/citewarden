---
name: citation-guard
description: Verify every case-law citation in a legal brief, memo, or AI-drafted document against the real court record before filing. Use this whenever the user pastes legal text containing citations, asks to "check citations," "cite-check," "verify case cites," or is worried an AI assistant may have hallucinated a case.
---

# Citation Guard

AI-drafted legal text has a documented, costly failure mode: fabricated or
mismatched case citations. Even paid commercial legal-AI tools still
hallucinate citations in a meaningful share of hard queries, and courts have
sanctioned lawyers hundreds of times for filing briefs containing fake cases.
This skill catches that before filing, by checking citations against the
real court record instead of asking the model to "remember" whether a case
is real.

## When to use this

Trigger whenever the user:
- Pastes a brief, memo, or any text containing case citations and asks you to check, verify, or cite-check it.
- Mentions they used AI (this assistant, ChatGPT, or any legal-AI tool) to draft something with citations and wants it double-checked before filing.
- Asks something like "is this a real case?" or "can you confirm these citations?"

## How to run the check

1. Take the full text the user gave you (don't retype or summarize it first — pass the original text through).
2. Run the bundled script, passing the text on stdin:

   ```bash
   python3 scripts/verify_citations.py
   ```

   The script needs `eyecite` and `requests` — if missing, install them first with
   `pip install eyecite requests` (or `pip3`, matching whatever Python the user has).

3. The script needs a free CourtListener API token in the `COURTLISTENER_API_TOKEN`
   environment variable. If it's not set, the script will say so — tell the user to
   get one free at https://www.courtlistener.com/profile/api/ (CourtListener/Free Law
   Project is a nonprofit; this is a free account, not a paid API) and either export it
   in their shell or pass it as `COURTLISTENER_API_TOKEN=... python3 scripts/verify_citations.py`.
4. The script prints one JSON object, already bucketed for you:
   - `full_case_citations` — case citations with a volume+page, the only kind actually
     sent for verification.
   - `unverifiable_format_count` — full citations missing a volume or page number
     (e.g. `22 U.S. ___`); these were never evaluated, not "unmatched."
   - `short_form_or_id_citations` — `Id.`, `supra`, and short-form cites. These are
     NOT independently verified — they point back to an earlier full citation. Tell
     the user which full citation they most likely belong to, don't claim they were checked.
   - `other_non_case_citations` — statutes and anything else that isn't case law.
     CourtListener's citation-lookup does not cover these at all; never report them
     as checked.
   - `courtlistener_result` — the raw API response for the full case citations.
   - `name_cross_check` — see below. Check its `performed` field before trusting it.
   - `disclaimers` — three fixed strings. Always relay all three, verbatim in substance, every time you report results.

## How to present the results

- Show a short table of the `full_case_citations` only: citation → status → (if
  matched) the real case name/court/year CourtListener confirmed.
- For anything unmatched, say it **could not be verified — confirm manually**. Do NOT
  say "this is fake" outright — see the disclaimers.
- **Read `name_cross_check` carefully.** If `performed: true` and `possible_mismatches`
  is non-empty, that is the single most important thing to surface, above everything
  else, in bold, first: it means a citation number is real but the party names cited
  don't match the real case — a strong signal of a hallucination that reused a real
  reporter/volume/page. If `performed: false`, say plainly that the name cross-check
  could not run on this response and party names need manual confirmation.
- Report `unverifiable_format_count` and the `short_form_or_id_citations` list
  separately from the matched/unmatched table — they were not evaluated, full stop.
- Mention `other_non_case_citations` only to say they exist and weren't covered by this tool (e.g., statutes).
- Always relay all three `disclaimers` from the script output, in substance:
  1. a match confirms the case exists, not that it's still good law (not overruled/vacated — this tool does not Shepardize/KeyCite);
  2. a real case can still be cited for a holding or quote it doesn't contain — this tool cannot check that;
  3. "unmatched" can mean fabricated OR just not indexed (state trial courts, very recent, unpublished/Westlaw-only decisions) — always say "could not verify," never "fake."
