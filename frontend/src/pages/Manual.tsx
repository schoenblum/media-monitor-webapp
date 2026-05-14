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
Each entry has an ISO code (e.g. \`en\`, \`ja\`), a human label, and the
university name in that language. A language must be defined here before it can
be used in the University Name option of a search.

A default English entry ("Kobe University") is seeded for every new account.

---

## 3. Configuring searches

A **Search** is a named bundle of terms, options, and outlets. Open **Searches**,
create a new one, then fill in the five sections:

### 3.1 Search from (search window)
Choose whether each run looks back to the **last successful run** of this search
(default) or a fixed number of **previous hours**. When "From last search" is
active but no prior run exists, the "Previous hours" value is used as a fallback.

### 3.2 Search terms
Add one or more free-text terms. Each row has:

- The term text.
- A logical operator (**AND / OR / NOT**) applied between this term and the
  previous one. The first term has no operator.
- A **Number** of result pages to fetch (1–10; 10 results per page = one API call).

### 3.3 DOI
Optional. Paste a DOI string here to search for a specific paper. It behaves as
an additional OR-linked term with its own page count.

### 3.4 University name (toggle, off by default)
When enabled, expands to a checklist of your defined languages. Each selected
language generates one query using the university name in that language.

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

### 4.1 Review and export
Each hit shows the title, snippet, outlet, detected language, and an extracted
date. Tick the rows you want and click **Export CSV**.

CSV format: \`Date, Media, Language, Headline, URL\` — UTF-8 with BOM, ready for
Excel.

---

## 5. Run history — bulk actions

In **Run History**, tick rows to select them. A toolbar appears offering:

- **Delete selected** — permanently removes the selected runs and their results.
- **Merge & open** — combines the result sets (deduplicated by URL) and opens
  them in a temporary view with the same checklist and CSV export as a single run.
  The merged view is not saved as a new run.

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
(merges) or **Import — Replace all** (wipes first). Export your library as CSV
with **Export**.

CSV columns: \`name\`, \`domain\`, \`category\`, \`keyword_langs\` (comma-separated ISO
codes), \`notes\` (ignored on import).

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

## 8. FAQ

**Why might a Spanish article show up under "English"?**
Language detection is statistical (\`langdetect\`). Short or mixed-language snippets
can be miscategorised — the detected language is best-effort, not authoritative.

**Why is the date sometimes missing?**
Dates are extracted from the Google snippet by regex. Some snippets do not include
a publication date.

**Can I export hits from multiple runs in one CSV?**
Yes — use **Merge & open** in Run History, then export from the merged view.

**Where can I see the raw API documentation?**
Visit \`/docs\` on the server (FastAPI's auto-generated OpenAPI explorer).
`;

export default function Manual() {
  return (
    <div className="card prose max-w-none p-6 prose-headings:text-brand prose-h1:mt-0 prose-h2:mt-8 prose-h2:border-b prose-h2:border-slate-200 prose-h2:pb-1 prose-pre:bg-slate-900 prose-pre:text-emerald-200 prose-a:text-brand">
      <ReactMarkdown>{MD}</ReactMarkdown>
    </div>
  );
}
