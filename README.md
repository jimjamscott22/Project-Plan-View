# Project-Plan-View

A simple, local-first webpage that displays all my project ideas in one place. Browse, search, filter, and track the status of every plan without leaving the browser — no server required.

## What's inside

| File | Purpose |
|---|---|
| `index.html`        | The viewer app — open it directly in any browser. |
| `projects.js`       | Auto-generated data file (`window.PROJECTS_DATA = {...}`). The HTML loads this on page load. |
| `projects.json`     | Same data in plain JSON form, kept in sync for any future tooling or scripts. |
| `build_manifest.py` | Regenerator script. Reads the markdown plans and rewrites both data files. |

## How to use it

1. Double-click `index.html`. That's it.
2. Search across titles, summaries, tags, and full content using the bar at the top.
3. Click a tag chip or status chip to narrow the list.
4. Click any card to expand it — markdown renders inline with full syntax highlighting.
5. Click a status badge to change a project's status (Idea / In Progress / Done / Reference / Inspiration). Your changes are saved to the browser's local storage, so the JSON stays clean.
6. Toggle dark / light mode with the button in the header.

The viewer works straight from `file://` (no local server needed) because `projects.js` assigns the data to `window` instead of relying on `fetch`.

## Adding a new project plan

1. Drop the new `.md` file into the source folder (currently `C:\Users\jimja\OneDrive - Cayuga Community College\Documents\Code\Project Plan Files`).
2. Open `build_manifest.py` and add a one-liner to the `PROJECTS` list:

   ```python
   ("My-New-Plan.md", "Display Title For The Card", "Idea", ["Python", "Web"]),
   ```

   - The fourth field is optional — pass `None` and the script auto-detects tags from the file's content.
3. Run the script:

   ```bash
   python build_manifest.py
   ```

4. Refresh `index.html` in the browser.

## Tech stack

- Plain HTML, CSS, and vanilla JavaScript — no build step.
- [`marked`](https://github.com/markedjs/marked) for markdown rendering (CDN).
- [`DOMPurify`](https://github.com/cure53/DOMPurify) to sanitize the rendered HTML (CDN).
- [`highlight.js`](https://highlightjs.org/) for code-block syntax highlighting (CDN).
- Python 3 + `python-docx` for the regenerator (only needed when adding new plans).

## Roadmap ideas

- Replace the hardcoded `PROJECTS` list in `build_manifest.py` with a folder scan, so new plans need zero code changes.
- Add a `regenerate.bat` so refreshing the manifest is a double-click.
- Optional per-project "last touched" timestamp from file mtime.
- Export filtered view as a printable PDF.
- Sync status changes to a small JSON file (instead of localStorage) so multiple devices share state.
