# Implementation handoff for Claude

## Current visual direction

The user requested a stronger, presentation-ready edition with multiple color
themes, premium fonts and proper dashboards. The current local reference is
`premium/index.html`: five selectable palettes, two font pairings, six operational
pages and three dashboards (Overview plus Production/Quality Insights).
Read `premium/README.md` and `premium/DESIGN.md` for use and design rules.

`premium/preview.js` now renders the shared shell, page templates, sample data and
interactive demo behavior. HTML files are entry points, so inspect the runtime
and browser views as well as screenshots. `premium/preview.css` contains layout
and theme tokens. Fonts and licenses are local in `premium/fonts/`.

This presentation edition supersedes the previous forest-only static exports.
Midnight Blue is the default; Forest, Amethyst, Graphite and Copper are selectable.
Preserve the business rules below, and validate application chart colors before
adopting the new palette. Figures and client-side checks remain illustrative.

## Request

Implement the Stitch UI designs in the existing FMC Vue application. The user
asked to save the designs first and plans to resume implementation with Claude.
No frontend implementation was made during design preparation.

## Read first

Read repository `CLAUDE.md` and load the required `frappe-code-standards` skill
before code changes. Its pinned source is recorded there; the historical local
path may not exist on this machine. The source repository was accessible during
preparation at https://github.com/NexTash/frappe-code-standards, commit
`099cbe788c69ed6f27b6b196d3b2671766c56a05`.

Read `docs/workflows.md`, `docs/operator-improvements.md`, the existing Vue pages,
`frontend/src/data/api.js`, and the corresponding `food_manufacturing/api/`
endpoints. Actual API fields and server policy take precedence over generated
mockups. Do not change stock, permission, accounting or manufacturing rules to
fit a screenshot.

## Design direction

Use the screenshots and interactive views listed in `premium/README.md`. Implement with
the existing Vue 3, frappe-ui, Tailwind and lucide-vue-next stack. Adapt the
reference markup into Vue components instead of embedding exported HTML or
copying CDN scripts into the application.

Desktop: dark left sidebar with Overview, Production, Quality, Receiving,
Dispatch and Recall plus Production/Quality Insights; topbar with company,
appearance controls and context. Use the selected theme's tinted canvas, white
surfaces, tabular quantities, clear hierarchy and readable tables. Reuse common
components and tokens in `frontend/src/components/` and `frontend/src/index.css`.

Use Plus Jakarta Sans / Inter (or the alternate pairing) with font licenses intact.
Implement theme selection as a user preference with safe storage fallback and
consistent application across routes. Use the existing Lucide icon library.
Do not copy the prototype's demo datasets or demo-only review handlers as live
business logic. Build analytics from actual permitted API data; omit unavailable
fields rather than fabricating numbers.

Mobile: compact navigation, stacked forms/cards and at least 44px touch targets.
Use the overview yield list instead of squeezing a chart. All six pages have
phone references; preserve their labeled cards and complete navigation.

## Preserve existing behavior

- Keep company scoping, API bindings, loading/error/empty states, and server
  validation errors. No hardcoded demo metrics in production.
- Keep the existing safe retry request IDs, scanner Enter behavior, and guards
  against repeated posting after success.
- Production retains Work Order detail, released lot visibility, completion,
  process loss and output batch fields. Never expose protected formula data.
- Quality retains matching batch inspections, history, required reasons,
  pagination and audited Release/Hold/Reject actions. Respect server permissions.
- Receiving keeps Purchase Order lines, outstanding quantities, supplier lots,
  manufacturing dates and policy-controlled quarantine routing.
- Dispatch preserves stock-UOM allocations and sales-UOM conversion. Suggestions
  do not reserve stock. Shelf-life, FEFO and quality blocks remain authoritative.
- Recall stays read-only, preserves negative return quantities and incomplete
  trace warnings, and links to Quality for audited Hold decisions.

## Correct the generated concepts during implementation

The exports are design drafts, not a final product specification. Some still
contain invented labels, dates, totals and controls. In particular:

- Omit unsupported machine telemetry, line/shift controls, emergency stop,
  downtime logging, printing/export controls, live status and policy overrides.
- Do not add quantities across different units or compare kg and packs on one
  scale. Keep output charts grouped by UOM and quality mix as batch counts.
- Do not invent trend comparisons, fixed yield targets or totals absent from
  API responses. Missing measurements display as an em dash, not zero.
- Recall currently returns affected batches and deliveries, not intermediate
  manufacturing graph edges. Do not fabricate genealogy connections. Render
  available data honestly; any API expansion requires a separate justified,
  permission-checked implementation.
- Preserve the validated chart palette and white chart surface. Repository
  instructions require rerunning the data-viz validator before changing chart
  colors. Status meaning must remain visible in words/icons as well as color.

## Suggested implementation sequence

1. App shell, sidebar/mobile navigation and shared visual tokens.
2. Overview KPI hierarchy and charts, using existing data and chart components.
3. Production and Quality master/detail layouts with their existing actions.
4. Receiving and Dispatch forms, explicit quantities and scanner interactions.
5. Recall layout based on the actual returned data.
6. Verify all pages on desktop and phone, including keyboard use, errors and
   posting states. Update the existing design harness if needed.

## Validation and delivery

Run the frontend build from `frontend/` with `yarn build` after installing locked
dependencies as needed. Run browser checks against real Vue screens with mocked
API responses when a Frappe session is unavailable; report that limitation.
Check company switching, mobile overflow, scanner focus and Enter prevention,
UOM conversion, quality pagination, successful posting and safe retries.

Do not seed test fixtures into the populated shared site. Do not add schema or
backend changes solely for visual parity. Follow `CLAUDE.md` for bench deployment
commands and explain any checks that could not be run locally.

All sixteen workspace/dashboard desktop/phone entries and screenshots are local.
The presentation hub and its fonts/icons work offline; no Stitch reconnection is
required for implementation. No API credentials belong in these files.


---

## Implementation status (2026-10-23)

**Done:** app shell (240px dark sidebar, topbar, six-item phone navigation), the five
themes and two font pairings as a stored preference with a safe-storage fallback,
self-hosted fonts with their OFL licences, shared tokens and components
(`PageHeader`, `KpiCard`, `StatusChip`, `StateBlock`), the Plant overview rebuilt to the
reference, both Insights dashboards, and all six operational pages restyled onto the
token system. `yarn build` is clean and each page is a lazy chunk.

**Corrections made against the drafts, as the handoff asked:**

- The prototype's `--line` (`#c1d2ff`) was **rejected for chart use**: the data-viz
  validator fails it on every theme hero surface (lightness 0.866, chroma 0.065 — it reads
  gray). The hero chart uses `#3987e5` with `#d03b3b` for flagged runs, which passes every
  check on all five hero surfaces. It is kept as a chrome token only.
- Chart colours do **not** re-tint with the theme. Quality status keeps one fixed meaning
  across all five palettes and always ships an icon and a word.
- Insights are built from `api.dashboard.get_dashboard` only. No endpoint, schema or field
  was added for visual parity, and no trend comparison or target was invented.
- Missing measurements render as an em dash, never zero.
- Output bars stay grouped by UOM; kg and packs are never put on one scale.
- On a phone the overview yield plot is replaced by its run table rather than squeezed.

### Second pass (2026-10-23)

The first pass restyled the operational pages without ever rendering them, and the result
was worse than the prototype: Quality was a plain table with a modal, Dispatch was two
cards and a modal, Recall was a search box on an empty page.

`preview/pages.html` now mounts the **real** shell, router and pages, with only
`@/data/api` and `@/data/session` aliased to mocks. Every page can therefore be opened and
screenshotted without a Frappe session, and all of them were rebuilt against the prototype
with that feedback:

- **Quality** — KPI row, status filter chips, a page filter, inline master/detail with the
  selected row marked, batch facts, a shelf-life meter, matching inspection, decision
  history and the decision form. The modal is gone.
- **Dispatch** — context bar, sales-to-stock UOM conversion cards, the scan card (Enter
  focuses a quantity field and never posts), and a FEFO allocation table per line with
  shelf-life meters, blocked rows named in words, and a running allocated-of-required total.
- **Receiving** — context bar with the quarantine destination, a lines table with
  quantity, supplier lot and manufacturing date, and a result panel listing the batches
  created with their quality status.
- **Recall** — a pre-search panel explaining what a trace returns, then affected batches as
  cards and deliveries as a table with returns named, not just signed.
- **Production** — a pending yield no longer shows a green tick, and the Available/Expiry
  columns carry the earliest eligible lot with a "+N more" count instead of being empty.

**Still not verified:** the live screens against a Frappe session. Scanner focus, QC
pagination, UOM conversion and safe-retry were preserved and are visible in the harness,
but have not been exercised end to end against the server.
