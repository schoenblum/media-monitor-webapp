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

1. Visit <https://programmablesearchengine.google.com/> and sign in.
2. Click **Add** to create a new search engine.
3. Under **What to search**, choose **Search the entire web**. Name it
   "Media Monitor" and click **Create**.
4. Open the engine, go to **Setup → Basics**, and copy the **Search Engine ID**
   (it looks like \`a12b3c4d5e6f7g\`).
5. Now visit <https://console.cloud.google.com/apis/credentials> and either pick
   an existing Cloud project or create one.
6. Click **+ Create credentials → API key**, then copy the key (it starts with
   \`AIza\`).
7. In the API Library, search for **Custom Search API** and click **Enable**.
8. Open Media Monitor → **Settings → Google Custom Search credentials**, paste
   both values, and click **Save**.

> **Quota:** Google gives you 100 free queries per day per project. If you
> need more, enable billing in the same Cloud project (it's pay-as-you-go).

---

## 2. Configuring searches

A **Search** is a named bundle of:

- one or more **search terms**, one per language (English "Kobe University",
  German "Universität Kobe", etc.),
- a list of **outlets** to look in.

Open **Searches**, create a new one, then in the editor:

- Toggle the **on** switch and enter a term for each language you care about.
- Set the **pages** column (1–10). Each page is up to 10 results and costs one
  Google API call.
- Tick the outlets you want this search to cover.
- Click **Save changes**.

You can have many searches (e.g. "Kobe University", "Tokyo University") — flag
one as **Default** to run it from the Dashboard with a single click.

---

## 3. Managing your outlet library

The **Outlets** page is your personal library of media outlets. Each outlet has:

- **Name** — human label (e.g. "BBC News")
- **Domain** — the host Google should search inside (e.g. \`bbc.com\`)
- **Category** — free text, just for organisation
- **Languages** — which language-specific search terms apply to this outlet
- **Active** — turn off temporarily without deleting

You can add, edit, and delete outlets in-line. Newly created accounts come
pre-seeded with the default Kobe University outlet list, which you are free to
modify.

### 3.1 Bulk import
Click **Template** to download an Excel template with the right columns:

| Column         | Required | Notes |
|----------------|----------|-------|
| name           | yes      | The outlet's display name |
| domain         | yes      | Plain hostname; \`http://\` and trailing \`/\` are stripped |
| category       | no       | Any text |
| keyword_langs  | no       | Comma-separated language codes, e.g. \`en,de\`; defaults to \`en\` |
| notes          | no       | Ignored on import |

Choose **Import — Add** to merge new rows (existing domains are skipped), or
**Import — Replace all** to wipe your library first.

---

## 4. Running a search and reviewing the results

From either the **Dashboard** ("Run default search"), the **Searches** page
("Run now"), or **Run History** ("Run default"), trigger a run. You'll land on
the **Run Detail** page; results appear as Google returns them and the page
auto-refreshes until the run is complete.

The 100-query-per-day quota is your hard limit. If you hit it, the run is
marked **Failed**, but any results already collected are kept.

### 4.1 Search window
The first time you run a given search, Media Monitor looks back **7 days**.
For every subsequent run of the same search, the window is automatically set
to the number of days since the previous successful run — so you never miss
anything between runs and never re-fetch the same week twice.

### 4.2 Review and export
Each hit shows the title, snippet, outlet, detected language, and a date
extracted from the snippet (when present). Tick the rows you want and click
**Export CSV**. The modal lets you also fold in selections from previous runs
so you can ship a single weekly/monthly CSV across multiple runs.

CSV format: \`Date, Media, Language, Headline, URL\` — UTF-8 with BOM, RFC 4180
quoting, ready to open in Excel.

---

## 5. Webhook automation

If you want to trigger runs from an external scheduler:

1. Go to **Settings → Webhook API key** and click **Generate**.
2. **Copy the key now** — it is shown only once.
3. POST to the webhook endpoint:

\`\`\`bash
curl -X POST https://mm.schenz.eu/api/v1/webhook/run \\
     -H "X-API-Key: <your-key>" \\
     -H "Content-Type: application/json" \\
     -d '{"search_id": "<uuid-of-your-search>"}'
\`\`\`

The response is \`{"run_id": "…", "status": "pending"}\` — the run executes in
the background just as if you'd clicked it.

If a key leaks, **Revoke** it; this invalidates it immediately.

---

## 6. FAQ

**Why might a Spanish article show up under "English"?**
Language detection is statistical (the \`langdetect\` library). Very short or
mixed-language snippets can be miscategorised — the **detected language** is a
best effort, not authoritative. You can still tick and export the article
normally.

**Why is the date sometimes missing?**
Dates are scraped from the Google snippet using regex. Some snippets simply
don't include a publication date, in which case the **Date** column stays
empty. The CSV export sorts by date descending with empty dates pushed to the
end.

**Can I export hits from multiple runs in one CSV?**
Yes — on a Run Detail page, click **Export CSV**. The dialog lets you tick
other completed runs to include. Only ticked rows (selected articles) across
those runs are exported.

**Where can I see the raw API documentation?**
Visit \`/docs\` on the server (FastAPI's auto-generated OpenAPI explorer).
`;

export default function Manual() {
  return (
    <div className="card prose max-w-none p-6 prose-headings:text-brand prose-h1:mt-0 prose-h2:mt-8 prose-h2:border-b prose-h2:border-slate-200 prose-h2:pb-1 prose-pre:bg-slate-900 prose-pre:text-emerald-200">
      <Markdown text={MD} />
    </div>
  );
}

/**
 * Minimal Markdown renderer — supports headings, paragraphs, lists, code blocks
 * and inline code. Avoids adding a dependency for what's essentially a single
 * static document.
 */
function Markdown({ text }: { text: string }) {
  const out: React.ReactNode[] = [];
  const lines = text.split("\n");
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];

    // Fenced code block
    if (/^```/.test(line)) {
      const buf: string[] = [];
      i++;
      while (i < lines.length && !/^```/.test(lines[i])) {
        buf.push(lines[i]);
        i++;
      }
      out.push(
        <pre key={`p-${i}`} className="overflow-x-auto rounded-md p-3 text-xs">
          <code>{buf.join("\n")}</code>
        </pre>,
      );
      i++;
      continue;
    }

    // Tables — header | --- | rows
    if (line.includes("|") && lines[i + 1]?.match(/^\s*\|?\s*-/)) {
      const headerCells = line
        .split("|")
        .map((c) => c.trim())
        .filter(Boolean);
      i += 2; // skip header + separator
      const rows: string[][] = [];
      while (i < lines.length && lines[i].includes("|")) {
        rows.push(lines[i].split("|").map((c) => c.trim()).filter(Boolean));
        i++;
      }
      out.push(
        <div key={`t-${i}`} className="overflow-x-auto">
          <table className="my-3 w-full border-collapse text-sm">
            <thead>
              <tr>
                {headerCells.map((c, j) => (
                  <th key={j} className="border border-slate-200 bg-slate-50 px-2 py-1 text-left">
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r, ri) => (
                <tr key={ri}>
                  {r.map((c, ci) => (
                    <td key={ci} className="border border-slate-200 px-2 py-1 align-top">
                      {inline(c)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>,
      );
      continue;
    }

    // Headings
    const h = line.match(/^(#{1,6})\s+(.+)/);
    if (h) {
      const level = h[1].length;
      const Tag = (`h${Math.min(level, 4)}` as unknown) as keyof JSX.IntrinsicElements;
      out.push(<Tag key={`h-${i}`}>{inline(h[2])}</Tag>);
      i++;
      continue;
    }
    if (/^---\s*$/.test(line)) {
      out.push(<hr key={`hr-${i}`} className="my-6 border-slate-200" />);
      i++;
      continue;
    }
    if (/^>\s/.test(line)) {
      out.push(
        <blockquote
          key={`q-${i}`}
          className="my-3 border-l-4 border-amber-300 bg-amber-50 px-3 py-2 text-sm"
        >
          {inline(line.replace(/^>\s/, ""))}
        </blockquote>,
      );
      i++;
      continue;
    }
    if (/^\s*-\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*-\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*-\s+/, ""));
        i++;
      }
      out.push(
        <ul key={`ul-${i}`} className="my-3 list-disc pl-6">
          {items.map((it, j) => (
            <li key={j}>{inline(it)}</li>
          ))}
        </ul>,
      );
      continue;
    }
    if (/^\s*\d+\.\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*\d+\.\s+/, ""));
        i++;
      }
      out.push(
        <ol key={`ol-${i}`} className="my-3 list-decimal pl-6">
          {items.map((it, j) => (
            <li key={j}>{inline(it)}</li>
          ))}
        </ol>,
      );
      continue;
    }
    if (line.trim().length > 0) {
      const para: string[] = [];
      while (i < lines.length && lines[i].trim().length > 0 && !/^([#>\-`|]|\d+\.)/.test(lines[i].trim())) {
        para.push(lines[i]);
        i++;
      }
      out.push(<p key={`pp-${i}`}>{inline(para.join(" "))}</p>);
      continue;
    }
    i++;
  }
  return <>{out}</>;
}

function inline(text: string): React.ReactNode {
  // Order matters: code → link → bold → italic.
  const parts: React.ReactNode[] = [];
  let rest = text;
  let key = 0;
  while (rest.length > 0) {
    const codeMatch = rest.match(/`([^`]+)`/);
    const linkMatch = rest.match(/\[([^\]]+)\]\(([^)]+)\)/);
    const angleLink = rest.match(/<((?:https?:\/\/)[^>\s]+)>/);
    const boldMatch = rest.match(/\*\*([^*]+)\*\*/);
    const candidates = [codeMatch, linkMatch, angleLink, boldMatch]
      .map((m, j) => (m && m.index !== undefined ? { m, j, idx: m.index } : null))
      .filter(Boolean) as { m: RegExpMatchArray; j: number; idx: number }[];
    if (candidates.length === 0) {
      parts.push(rest);
      break;
    }
    candidates.sort((a, b) => a.idx - b.idx);
    const first = candidates[0];
    if (first.idx > 0) {
      parts.push(rest.slice(0, first.idx));
    }
    const m = first.m;
    if (first.j === 0) {
      parts.push(
        <code key={key++} className="rounded bg-slate-100 px-1 py-0.5 text-[0.85em]">
          {m[1]}
        </code>,
      );
    } else if (first.j === 1) {
      parts.push(
        <a key={key++} href={m[2]} target="_blank" rel="noreferrer" className="text-brand hover:underline">
          {m[1]}
        </a>,
      );
    } else if (first.j === 2) {
      parts.push(
        <a key={key++} href={m[1]} target="_blank" rel="noreferrer" className="text-brand hover:underline">
          {m[1]}
        </a>,
      );
    } else {
      parts.push(<strong key={key++}>{m[1]}</strong>);
    }
    rest = rest.slice(first.idx + m[0].length);
  }
  return parts;
}
