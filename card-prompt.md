You are producing ONE read-only status card for the project item `{{SLUG}}`.

Your current directory IS `{{SLUG}}`. Read (do not write or modify anything):

- `context.md` (if present)
- `README.md` (if present)
- any other obviously relevant status or notes file in this directory (e.g.
  `STATUS.md`, `NOTES.md`, `CHANGELOG.md`), if present
- `git log` history for this directory, if it is inside a git repository
  (read-only — you may only run `git log`)

Output EXACTLY this compact card, nothing else:

  ┌─ {{SLUG}}
  │ Status:          <one line>
  │ Next milestone:  <date/description, or "none found">
  │ Top risk:        <most notable risk or blocker, or "none found">
  │ Last activity:   <most recent dated entry or commit>
  │ Needs attention: <the single most important open item, or "nothing pending">
  └─

Rules:

- Be brief and direct. No preamble, no restating the question, no markdown
  fences around the card.
- Do not invent facts. If a file listed above is absent, say so in your own
  reasoning — do not guess at its contents or pretend you read it.
- If a date, name, or fact is genuinely unclear from what you read, mark that
  field "[uncertain]" rather than stating it as settled.
- Never fabricate dates, deadlines, or risks that are not grounded in
  something you actually read in this directory.
