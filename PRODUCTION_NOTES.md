# Media Monitor — Production Notes

*Standing procedure for working on this repo. Last updated: 2026-05-22.*

This file captures **how we work**. It is intentionally separate from
`HANDOVER.md`, which owns architecture, secrets, and current status. Keep this
list living — add a rule when a new standing procedure emerges, remove or amend
a rule when it stops applying.

---

## 1. Never publish secrets

No credential, key, password, or `.env` content goes into git, issues, PRs,
logs, screenshots, or any indexable or shareable location.

- `HANDOVER.md` is gitignored and stays gitignored. It is the consolidated
  secrets vault and is delivered out-of-band (encrypted password manager,
  physical handoff, end-to-end-encrypted message).
- `.env`, `.env.local`, and equivalents are gitignored. The repo only contains
  `.env.example` with placeholder values.
- Server-side env files such as `/etc/media-monitor/backup.env` live on the
  host only; only `*.example` versions belong in the repo.
- Before every push, eyeball the diff (`git diff --staged`) for credential-
  looking strings — base64-shaped blobs, things matching `AIza…`, `gh[ps]_…`,
  and anything that looks like a Fernet, JWT, or DB password.

If a secret leaks: rotate immediately (see `HANDOVER.md` §7) and note the
rotation in `HANDOVER.md` §4.

## 2. Push at the end of each development step

When a numbered step from the revision brief is complete, commit and push to
GitHub. This triggers CI (`.github/workflows/test.yml` runs pytest) and gives
the maintainer a visible checkpoint to review.

A "step" can be a single brief item, or a coherent bundle of items that share a
file or schema (the brief's §9 sequencing guides this). Avoid mixing unrelated
changes in one push — small, focused commits are easier to review and revert.

## 3. Keep the work tree clean and flat

- All canonical files live at their proper top-level location in the repo.
  There are no shadow copies in `_old/`, `.archive/`, `versions/`, etc.
- Remove scratch, temp, and dot-prefixed working files before pushing
  (`.pytest_cache/` is gitignored; the `venv/` is gitignored; check anything
  else you wrote during the session).
- If you find a file that looks newer or fresher than its sibling, investigate
  *why* before deleting — it may be the maintainer's in-progress work. Ask.

## 4. Update the handover

After each step, update `HANDOVER.md` to reflect the new status quo:

- **Section 2 ("Current state")**: bump version, list new endpoints / pages /
  migrations, update the "Verified live" subsection if you exercised the
  feature.
- **Section 3 ("Open items")**: cross off anything you closed; add anything
  new you uncovered.
- **Section 4 ("Secrets vault")**: only when a credential changes. Record the
  rotation date inline.
- **Section 11 ("Quick sanity checks")**: keep the expected version / Alembic
  revision in lockstep with reality so the checks remain meaningful.

The handover is the single ground-truth document for the next maintainer; if a
fact lives in two places, the handover wins.

## 5. Update the production notes

This file. If a new standing procedure emerged during a step — a recurring
pitfall you want the next session to avoid, a convention you settled on — add
it here.

**Do not** put architecture, secrets, or current-state facts here. Those belong
in `HANDOVER.md`. Production notes are about *how we work*, not *what we have*.

## 6. Cross-cutting reminders carried over from the revision brief

These are the consistency rules a revision touches most often. They are not
listed in the handover because they apply to the *act of editing*, not the
running system:

- **Search config + types move together.** Any change to `SearchConfig` touches
  `app/schemas/search.py`, `app/models/search.py` (`DEFAULT_SEARCH_CONFIG`),
  `frontend/src/api/types.ts` (`SearchConfig` + `defaultSearchConfig()`), and
  the Searches form (`frontend/src/pages/Searches.tsx`).
- **Language list moves together.** `ALL_LANGUAGES` (TS) and
  `SUPPORTED_LANGUAGES` (Python) must stay in sync — both files carry a
  paired-edit warning header. A future revision may unify them.
- **In-app Manual is part of the deliverable.** Any user-visible change updates
  the `MD` string in `frontend/src/pages/Manual.tsx` in the same commit. Users
  read this; do not let it drift.
- **Tests live with the change.** Backend changes extend `tests/`; CI runs
  pytest on every push and is the gate.
- **Verify before assuming.** When the handover or a brief refers to existing
  behaviour, read the current code first — the handover is a guide, not ground
  truth.
