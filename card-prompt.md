You are producing ONE read-only "full status brief" card for the project
item `{{SLUG}}`, focused on the LAST 5–10 DAYS of activity.

Your current directory IS `{{SLUG}}`. Read (do not write or modify anything):

- `context.md` (if present)
- `README.md` (if present)
- any other obviously relevant status or notes file in this directory (e.g.
  `STATUS.md`, `NOTES.md`, `CHANGELOG.md`), if present
- `git log --since="10 days ago" --date=short --pretty="%ad %s" -- .` for
  dated recent-activity bullets (newest first), if this directory is inside
  a git repository (read-only — you may only run `git log`)
- recently-modified files in this directory, e.g. via
  `find . -maxdepth 2 -type f -mtime -10`, as a signal of what's been touched

Output ONLY this block, nothing before or after it:

<<<CARD
STATUS: <1-2 line current-state phrase>
PHASE: <1-3 words only, e.g. "planning", "in review", "stable" — NOT a description>
DEADLINE: <YYYY-MM-DD>|<label>          (or  DEADLINE: NONE)
RISK: <short text>|<HIGH|MED|LOW>       (or  RISK: NONE)
RECENT:
- <YYYY-MM-DD> <concrete thing that happened>
- ... (newest first)
AWAITING:
- <thing this item is waiting on / owed>
- ...
NEXT: <the single most important open item>
CARD>>>

Rules:
- STATUS/PHASE/DEADLINE/RISK/NEXT are single-line fields. RECENT and
  AWAITING are list headers followed by `- ` bullet lines (as many as
  apply) until the next KEY: header or the end of the block.
- Emit the deadline as the DATE you actually read — do NOT compute
  day-counts yourself (the tool that renders this card does that). Use
  `DEADLINE: NONE` if there is no dated deadline.
- Use `RISK: none | NONE` if there is nothing material to report.
- RECENT: give up to 4–6 dated bullets, newest first, each a concrete dated
  action/event, roughly one line long, prefixed with the date (YYYY-MM-DD).
  Ground every bullet in a file or `git log` entry you actually read — do
  not fabricate dates or events.
- AWAITING: 1–3 items this item is genuinely waiting on (e.g. a review, a
  reply, an external dependency). Omit the header entirely if there is
  nothing outstanding.
- NEXT: the single next action. Use `NEXT: none` if nothing is pending.
- Do not invent facts. If a file listed above is absent, treat the
  corresponding field as NONE rather than guessing at its contents or
  pretending you read it.
- No preamble, no restating the question, no markdown fences, no text
  outside the block.
