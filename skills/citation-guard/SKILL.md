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
4. The script prints JSON: a list of citations found, each marked `matched` (with the
   real case name/court/date CourtListener returned) or `unmatched`.

## How to present the results

- Show a short table: citation text → status → (if matched) the real case name/court/year CourtListener confirmed.
- For anything `unmatched`, say it **could not be verified — confirm manually** before
  relying on it. Do NOT say "this is fake" outright: a citation can fail to match for
  benign reasons — it's missing a volume/page number (the API won't even attempt those),
  it's a very recent case not yet indexed, or it's in a format eyecite didn't parse
  cleanly. Name the likely reason if you can tell from the citation's shape.
- Always close with: this is not legal advice, and a clean result does not replace a
  human's own professional review of the document.
