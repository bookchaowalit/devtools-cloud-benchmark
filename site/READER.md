# Reader shell

The shared calm, Apple-like look for content sites: blogs, notes, archives, course and path pages.
Started 2026-11-19 with `content-techblog-web` as the pilot (source of truth) and `education-learn-web`
as the second site. It is the fifth shell after the Workbench (devtools), the sales page, the App shell
(list apps) and the Dashboard shell (data pages). Each site is its own repo, so the shell is copied in,
not installed. Copy these four files **byte for byte** (check with `sha256sum`):

| File | What it holds |
|---|---|
| `app/reader-shell.css` (`src/app/` in a `src/` repo) | Tokens `--rs-*` (light + dark, same palette as the App and Dashboard shells), top bar, page head, buttons, search, chips, entry rows and cards, tags, empty state, article head, prose, code block with copy button, pager, footer, phone and forced-colors rules |
| `components/reader-shell.tsx` (`src/components/`) | `Reader`, `ReaderTop`, `ReaderFoot`, `ReaderHead`, `EntryList`, `Tags`, `TagFilter`, `SearchForm`, `ResultCount`, `EmptyState`, `ArticleHeader`, `Prose`, `TableScroll`, `Pager`, and the helpers `formatDate`, `matchesQuery`, `neighbours`, `plural`. No hooks, no `"use client"`: every piece renders from a Server Component |
| `tests/reader-shell.test.tsx` | Tests for the shell itself (pieces, helpers and the stylesheet floor), so a site that uses only part of it still covers all of it. Imports `@/components/reader-shell`, so `@` must point at the folder that holds `components/` |
| `READER.md` | This file |

## Rules

- **One h1 per page**, from `ReaderHead` (index pages) or `ArticleHeader` (articles). The lede says what
  the page holds in one sentence; no invented counts, readers or dates.
- **Index pages** list entries with `EntryList`: title, a meta line (date first, then reading time or scope),
  a one-line summary and tags. Rows by default; `layout="cards"` for short collections. The title link
  covers the whole entry, so each entry is one large target. Under a section `h2`, pass `headingLevel={3}`.
- **Tags are labels** (`Tags`); filtering is done with `TagFilter` chips (links, `?tag=…`, current one has
  `aria-current="page"`) or, on a client page, buttons with `aria-pressed` and the `rs-chip` class.
- **Search where it helps** (more than a handful of entries): `SearchForm`. On a server page it is a GET
  form with a Search button and a Clear link, and the page reads `searchParams`. On a client page pass
  `value`, `onValueChange` and `onClear`; it then filters live and is not a form (a `role="search"` box, no
  field name, Enter cancelled), so the query never reaches the server, even before JavaScript loads. Clear
  puts focus back in the field; do the same for any other "clear" button that removes itself.
- **Filter counts follow the search**: a chip's number is what clicking it shows, so count within the
  entries that match the current query.
- **Chips stay on screen**: a chip never grows past its row and its label wraps. Build chips only from
  values the content really has, never straight from a URL parameter.
- **Always say how many show** with `ResultCount` (a `role="status"` line), and show an `EmptyState`
  that says what to do next, different for "nothing yet" and "nothing matches" (with a way back).
- **Articles**: `ArticleHeader` (back link, tags, title, lede, meta with a machine-readable date), the body
  in `Prose`, then `Pager` (previous / next in the index order). If the content starts with the same
  `# Title` as the page h1, drop that line before rendering so there is one h1.
- **Prose** styles raw Markdown/MDX HTML: headings, lists, links, quotes, inline code, code blocks, images,
  figures, tables and rules. Wrap every table in `TableScroll` (a labelled, focusable scroll region) so a wide
  one scrolls inside itself; never set `display` on `table`, `tr` or `td`, which drops the table semantics in
  Safari/VoiceOver. In MDX, map `table` to `TableScroll` and `h1` to `h2` so the page keeps one h1, and
  compile with `remark-gfm`, or Markdown `| … |` tables never become tables. A code block that scrolls sideways gets
  `tabIndex={0}`; a copy button is a `button.rs-copy` inside `div.rs-code` with a `role="status"` message.
- **Reading measure 68ch** for heads, summaries and prose. Line height 1.65 for Latin text and 1.8 under
  `:lang(th)` (Thai stacks marks above and below the line); put `lang="th"` on Thai content or pages. The
  Thai rules match the element's own language, so `<Prose lang="th">` works inside an English page.
- **Top bar**: brand (links home), a few plain links, the hub link is added for you. Sticky on wider
  screens; on phones it wraps and scrolls away, so links are never hidden behind a menu.
- **Footer**: `ReaderFoot` always links back to https://bookchaowalit.com/ ("More projects"), plus Source,
  Privacy and Status, optional extra links and one honest note about where the content comes from.
- **Floor:** text ≥ 12px, controls ≥ 44px, 3px focus ring never clipped (no `overflow: hidden` around
  focusable things; on phones nothing pulls left by more than 8px into the 16px gutter), 4.5:1 text contrast and 3:1 control edges in light and dark (values in the CSS
  header), forced-colors support, no horizontal scroll at 320px.

## Site conventions that go with the shell

- Geist via `next/font` with the variable on `<html>` (not `<body>`): the tokens live on `:root`.
  The shell falls back to system fonts (and Thai system fonts) when a variable is missing, so a site
  does not need Geist Mono unless it shows code.
- `globals.css`: `@import "tailwindcss"; @import "./reader-shell.css";` and
  `html, body { margin: 0; background: var(--rs-bg); }`. Drop the old theme.
- `next.config.ts` redirects `/more-projects` permanently (308) to https://bookchaowalit.com/.
- No Vercel Analytics or Speed Insights.
- Inside a Next app, link internal routes with `next/link` and the shell classes (`rs-button`,
  `rs-plain`); the shell's own links are plain `<a>` so it stays framework-free.

## Moving a site onto the shell

1. Copy the four files; import the CSS from `globals.css`; put the font variable on `<html>`.
2. Keep the site's content, routes and loaders. Keep page files thin and put the views in a
   component that takes plain data, so tests can render it with no entries, a query or a tag.
3. Rebuild each page as `Reader` → `ReaderTop` → `<main id="main" className="rs-main">` (head, toolbar,
   list or empty state, or the article) → `ReaderFoot`.
4. Add `components/**/*.tsx` to the coverage `include`, keep the repo's coverage gate, and write mounted
   tests for search, filters, empty states and previous/next.
5. Screenshot the home page, one list page and one article page at 320 / 375 / 768 / 1440 in light and
   dark (and once with forced colors); check there is no horizontal scroll and nothing overlaps.
