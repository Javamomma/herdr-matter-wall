You are producing ONE read-only status card for the project item `{{SLUG}}`.

Your current directory IS `{{SLUG}}`. Read (do not write or modify anything):

- `context.md` (if present)
- `README.md` (if present)
- any other obviously relevant status or notes file in this directory (e.g.
  `STATUS.md`, `NOTES.md`, `CHANGELOG.md`), if present
- `git log` history for this directory, if it is inside a git repository
  (read-only — you may only run `git log`)

Output ONLY this block, nothing before or after it:

<<<CARD
STATUS: <short phrase: where this item stands now>
PHASE: <one word describing its stage>
DEADLINE: <YYYY-MM-DD> | <short label>
RISK: <short text> | <HIGH|MED|LOW>
NEXT: <the single most important open item>
CARD>>>

Rules:

- Emit the deadline as the DATE you actually read — do NOT compute day-counts
  yourself (the tool that renders this card does that). Use `DEADLINE: NONE`
  if there is no dated deadline.
- Use `RISK: none | NONE` and `NEXT: none` when there is nothing to report.
- Keep each value to one short line.
- Do not invent facts. If a file listed above is absent, treat the
  corresponding field as NONE rather than guessing at its contents or
  pretending you read it.
- No preamble, no restating the question, no markdown fences, no text
  outside the block.
