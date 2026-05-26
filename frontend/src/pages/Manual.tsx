import ReactMarkdown from "react-markdown";

const MD = `
# Media Monitor — User Manual

Welcome. Media Monitor watches a curated list of news outlets for mentions of a
search term you choose, and lets you review and export the hits.

---

## 1. First-time setup

### 1.1 Change your password
Your account was created with a temporary password. The first time you sign in,
you must choose a new one. After that, you can change it again any time from
**Settings**.

### 1.2 Get Google Custom Search credentials
The service uses Google Custom Search behind the scenes — you supply your own
**API key** and **Search Engine ID** (so the daily 100-query free quota is
yours). Both are stored encrypted on the server and never shown again after
saving.

1. Visit https://programmablesearchengine.google.com/ and sign in.
2. Click **Add** to create a new search engine.
3. Under **What to search**, choose **Search the entire web**. Name it
   "Media Monitor" and click **Create**.
4. Open the engine, go to **Setup → Basics**, and copy the **Search Engine ID**
   (it looks like \`a12b3c4d5e6f7g\`).
5. Visit https://console.cloud.google.com/apis/credentials and pick or create a
   Cloud project.
6. Click **+ Create credentials → API key**, then copy the key (starts with \`AIza\`).
7. In the API Library, search for **Custom Search API** and click **Enable**.
8. Open Media Monitor → **Settings → Google Custom Search credentials**, paste
   both values, and click **Save**.

> **Quota:** Google gives you 100 free queries per day per project. If you
> need more, enable billing in the same Cloud project (pay-as-you-go).

---

## 2. Languages

Go to **Languages** and define the university name in each language you need.
Each entry has an ISO code (e.g. \`EN\`, \`JA\`) and the university name in that
language. A language must be defined here before it can be used in the
University Name option of a search.

A default English entry ("Kobe University") is seeded for every new account.

### 2.1 Bulk import / export

Click **Template** to download a starter CSV. Columns: \`iso_code\` (uppercase)
and \`university_name\`. Upload with **Import — Add** to merge new rows into
your list, or **Import — Replace all** to wipe your list first. Use **Download
CSV** to export your current language list in the same import-compatible shape.

If a row uses an ISO code not in the supported list, you'll be prompted to pick
a valid language for each affected row. If a row duplicates a language you've
already defined, you choose per-row whether to keep the existing entry or
replace it with the one from the file.

Select rows in the table and use **Delete selected** to remove several at once.

---

## 3. Configuring searches

A **Search** is a named bundle of terms, options, and outlets. Open **Searches**,
create a new one, then fill in the five sections:

### 3.1 Search from (search window)
Three modes:

- **Last successful run** (default) — looks back to the start of the most recent
  successful run of this search. The "fallback hours" value below kicks in on the
  very first run.
- **Previous hours** — fixed lookback in hours.
- **Date range** — restrict results to a publication-date window. Enter a
  **From** date; **To** is optional (blank = up to today). For a single day,
  enter the same date in both fields. Maps to Google CSE's
  \`sort=date:r:YYYYMMDD:YYYYMMDD\` parameter.

### 3.2 Search terms
Add one or more free-text terms. Each row has the term text and a logical
operator (**AND / OR / NOT**) applied between this term and the previous one;
the first term has no operator. All terms are concatenated into **one** combined
Google query, so the **Pages** picker at the bottom of the section applies once
to that combined query (1–10; 10 results per page = one API call).

### 3.3 DOI
Optional. Paste a DOI string here to search for a specific paper. It is **always
a standalone query**, unaffected by the term operators above, and has its own
page count.

### 3.4 University name (toggle, off by default)
When enabled, expands to a checklist of your defined languages, plus a **Pages
per language** picker. The university-name option behaves as an **AND constraint**
on the combined search-terms query, issued as a **separate Google query per
selected language**:

\`\`\`
(combined terms) AND "<university name in language N>"
\`\`\`

With three active languages, three queries are issued, each fetching the
configured number of pages. If the terms section is empty, the queries are simply
\`"<university name in language N>"\` — useful for a wide "anything mentioning the
university in any language" net.

### 3.5 Outlets (toggle, off by default)
When enabled, shows your outlet library grouped by category. Each category has
a "Select all" checkbox. Searches are then restricted to \`site:{domain}\` for
each selected outlet.

When the University Name option is also active, outlets that have no language
set are included in all queries; outlets with language codes are only included
when at least one code matches the university-name language.

### 3.6 Validation
A search can only be run if at least one of the following is true:
- At least one non-empty search term.
- A non-empty DOI.
- University Name is enabled with at least one language selected.

---

## 4. Running a search and reviewing results

From the **Dashboard**, the **Searches** page, or **Run History**, trigger a run.
You land on the **Run Detail** page; results appear as Google returns them.

Next to each Run button is a **Deduplicate results** checkbox, on by default.
With it on, a *Last successful run* search will skip URLs that already
appeared in previous runs of the same search within the last couple of days
— so a run a few hours after the previous one won't re-list the same hits.
Uncheck it to see everything in the window, including repeats. The checkbox
only affects *Last successful run* mode; the *Previous hours* and *Date range*
modes already let you choose the window deliberately and are never deduped
across runs.

### 4.1 Review and export
Each hit shows the title, snippet, the **source host** (e.g. \`bbc.com\`, derived
from the result URL with any \`www.\` prefix stripped), the detected language,
and a **Published** date — the article's publication date, parsed best-effort
from the Google result snippet. The Published date can be approximate or
missing depending on how the source page exposes it. Don't confuse it with
the run's **Started** timestamp shown at the top of the Run Detail page and
in the Run History "Started" column — that's when *you* ran the search.

Tick the rows you want and click **Export CSV**.

CSV format: \`Date, Media, Language, Headline, URL\` — UTF-8 with BOM, ready for
Excel.

---

## 4a. Dashboard widgets

The **Dashboard** shows a short feed of recent runs plus two summary widgets:
**Top sources** (the most frequent hostnames across runs in the chosen window)
and **Hits by detected language**. Both widgets cover the same time window — a
small **Window (days)** input next to *Top sources* sets it (default 7 days).
Source labels are derived from each result's URL, so they correctly attribute
hits that come from outlets outside your library (e.g. a university-name
search will surface news sites you never added).

---

## 5. Run history — bulk actions

In **Run History**, tick rows to select them. A toolbar appears offering:

- **Delete selected** — permanently removes the selected runs and their results.
- **Merge & open** — combines the result sets (deduplicated by URL) and opens
  them in the same review-and-export view as a single run, with checkboxes,
  language grouping, and CSV export. Toggling a row updates the selection on
  the underlying run. The merged view itself is not saved as a new run.

The **Select all** checkbox selects only the currently visible rows (filtered
by the active search/status filter).

---

## 6. Outlets

The **Outlets** page is your personal library of media outlets. Each outlet has:

- **Name** — display label.
- **Domain** — the host Google should search inside (e.g. \`bbc.com\`).
- **Category** — free text for grouping.
- **Languages** — which of your defined languages apply to this outlet.
  Leave empty and the outlet is included in all language queries.
- **Active** — toggle off temporarily without deleting.

### 6.1 Bulk import / export
Click **Template** to download a CSV template. Upload a CSV with **Import — Add**
(merges) or **Import — Replace all** (wipes first). Click **Download CSV** to
export your current outlet library in the same import-compatible shape — useful
for sharing a definition with a coworker.

CSV columns: \`name\`, \`domain\`, \`category\`, \`keyword_langs\` (comma-separated ISO
codes), \`notes\` (ignored on import).

On upload, you'll see a preview showing which rows will be added and which
duplicate an existing outlet. For each duplicate, you choose whether to keep
the existing entry or replace it with the value from the file. Commit when
ready.

### 6.2 Bulk delete
Tick the rows you want to remove and click **Delete selected**. Confirm in the
dialog. Deletion is permanent.

---

## 6a. Automatic (scheduled) runs

Open a search and find the **Perform** section. Two choices:

- **Manually** (default) — the search only runs when you click *Run now*,
  hit the Dashboard's *Run default search*, or call the webhook.
- **Automatically** — the server fires the search on a cadence. You pick:
  - an **interval** (every 6 hours, daily, weekly, or a custom number of
    hours);
  - a **start time** (HH:MM) that anchors the cadence;
  - a **timezone** (IANA name, default **Asia/Tokyo**) the start time is
    interpreted in.

A daily-or-longer cadence fires at the start time each day/week. A sub-daily
cadence ("every N hours") anchors to the start time and then fires every N
hours from there — so *Every 6 hours at 08:00* fires at 08:00, 14:00, 20:00,
02:00 in the chosen zone.

Scheduled runs use the search's own *Search window* setting and are listed
with the **Scheduled** trigger label in Run History. Combine them with
*Last successful run* (and leave the *Deduplicate results* checkbox on,
which is the default for automatic runs) so each cycle returns only what's
new since the last fire.

**Date range** windows cannot be combined with automatic runs — the form
warns and the API rejects this combination, because a fixed calendar range
would return the same results on every fire.

**When a scheduled run can't proceed** (e.g. you removed your Google
credentials, the search has no terms, or your Google quota is exhausted),
the run shows up in Run History as **Skipped** with the reason — so a
forgotten recurring search never produces silence.

---

## 7. Webhook automation

1. Go to **Settings → Webhook API key** and click **Generate**.
2. **Copy the key now** — it is shown only once.
3. POST to the webhook endpoint:

\`\`\`
curl -X POST https://mm.schenz.eu/api/v1/webhook/run \\
     -H "X-API-Key: <your-key>" \\
     -H "Content-Type: application/json" \\
     -d '{"search_id": "<uuid-of-your-search>"}'
\`\`\`

The response is \`{"run_id": "…", "status": "pending"}\`.

If a key leaks, **Revoke** it immediately.

---

## 8. University affiliation (multi-user pools)

Admins can group accounts into a **university**. Affiliated members:

- **Share** the Languages list, the Outlets library, and the run history. Any
  member can view *and edit* the shared definitions (last-write-wins). Any
  member can also toggle result selections on any visible run, but only the
  run's performer can delete it.
- **Do not share** login credentials, the Google Custom Search API key + CX,
  or the webhook key. Those stay strictly per-user.
- See a coloured banner at the top of Languages, Outlets, and Run History
  while operating in shared mode, plus a chip with the university name in the
  top-right of every page.

Admin actions (Admin tab):

- Create, rename, and delete universities. Deleting one un-affiliates every
  member; their shared rows revert to personal ownership (no data is lost).
- Per-user **Affiliation** dialog assigns / moves / un-affiliates a member.
  On assignment, the user's non-conflicting personal Languages and Outlets
  are adopted into the new shared pool. Conflicting personal rows stay
  user-private (and become invisible to the user while affiliated — they
  reappear if you un-affiliate).
- Optionally, on assignment, **duplicate the user's personal run history**
  into the new university's pool. Originals stay where they were; this is
  primarily useful when a previously-private user is first migrated into a
  new affiliation.

The performing user's affiliation is **snapshotted** onto every run at
creation time. Runs do not migrate on reassignment — they stay in the
university they were performed under.

---

## 9. FAQ

**Why might a Spanish article show up under "English"?**
Language detection is statistical (\`langdetect\`). Short or mixed-language snippets
can be miscategorised — the detected language is best-effort, not authoritative.

**Why is the date sometimes missing?**
Dates are extracted from the Google snippet by regex. Some snippets do not include
a publication date.

**Can I export hits from multiple runs in one CSV?**
Yes — use **Merge & open** in Run History, then export from the merged view.
`;

export default function Manual() {
  return (
    <div className="card manual-content p-8">
      <ReactMarkdown>{MD}</ReactMarkdown>
    </div>
  );
}
