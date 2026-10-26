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

### Third pass (2026-10-23) — first live verification

The console had never been opened against a real Frappe session. Doing so found four
defects that no amount of harness work would have shown.

**The first request failed.** `session.js` opened by asking `frappe.client.get_list` for
`Company`. No FM role can read Company, so an operator holding only FM roles got
`Insufficient Permission for Company` before anything rendered. `api/session.py::get_bootstrap`
now derives the company list from `FM Manufacturing Policy` — readable by every FM role —
and treats Company as a fallback. Catching the `PermissionError` was not enough on its own:
`frappe.throw` queues its message *before* raising, so the swallowed error still shipped a
red popup on a request that had succeeded; the message log is trimmed back for that reason.

**Refusals were unreadable.** Server messages are HTML, rendered as text, so a permission
error read `Insufficient Permission for <strong>Company</strong>`. Tags are now stripped, and
`.fm-app .fm-card` is more specific than `.bg-red-50`, so the error card had been rendering
plain white in every theme — it now uses the theme's own `--fm-bad` tokens.

**A refusal said nothing useful.** The screens read standard ERPNext documents and the FM
roles deliberately do not widen access to them, so a missing role is expected, not a bug.
`StateBlock` now names the roles the screen needs (`frontend/src/data/access.js`, computed
from the `has_permission` gates and this site's DocPerm, not guessed) once the server has
refused. The role table in `docs/workflows.md` was corrected against that same reading —
in particular Quality needs ERPNext's **Quality Manager**, without which a batch's matching
inspection does not load.

**A blend read "500 Nos".** `Work Order.stock_uom` is only fetched by the Desk form, so an
order created through the API or an import keeps the `Nos` default. The production endpoints
now resolve the unit from the Item, in one query per page. Pinned by
`test_queue_reports_the_items_unit_not_the_work_order_default`.

A mistyped path under `/fm` also rendered the shell with an empty pane; there is now a
`NotFound` route, and the breadcrumb falls back to the route title.

**Verified live** over HTTP against `steps_erp.local` with a temporary FM-roles user (created,
used, deleted): the exact `Insufficient Permission for Company` reproduced on the old call and
cleared on the new one, then Overview, Production, Quality, Receiving, Dispatch and Recall
each opened with real server data — 95.2% average yield, a flagged run at 91%, one quarantined
lot awaiting a decision, two open work orders in kilograms, four purchase orders, and a FEFO
allocation that blocks an aged batch in words. 241 tests pass.

**Still not verified:** posting a receipt, a run completion or a delivery note through the live
UI; those paths are covered by tests but have not been clicked end to end.


### Fourth pass (2026-10-23) — the charts themselves

Rendered every chart first, then changed it. What the renders showed:

**The line chart was drawing a 92–97% series inside an 85–105% band.** The axis padded
the data by a fixed amount, snapped to multiples of five, and treated the 100% planned
line as a value to pad *beyond* — so the data used a quarter of the plot and eighteen
runs looked identical. `frontend/src/utils/scale.js` picks the step from the data's own
range and caps the ceiling at the planned line; the same series now spans 90–100%, and
the dips are the first thing you see. A 10% area wash gives the line weight, and the
direct labels are the latest run plus every flagged one — a flagged trough is labelled
*below* its marker, where the text no longer lands on the line coming into it.

**"Process loss by item" named the wrong item.** Ranked in kilograms, the biggest product
is always the worst offender: 56 kg lost on 1,842 kg is 3.0%, while 34 kg on 420 kg is
8.1%. It is now a loss *rate*, which also puts every item on one scale — and it carries
the absolute figures in each row's note. Nothing was added to the API; `production_by_item`
already returns output and loss per item.

**A ranking chart was not ranked**, so `BarRanking` sorts descending — except on an
ordered scale, where `:sorted="false"` keeps expiry buckets in time order. Sorting them by
count had put "31-90 days" first under a subtitle reading "most urgent first".

**A one-row group was a one-bar bar chart**, which says only "this is 100% of itself";
it now renders as a figure. Every row gained its share of the group, a hover/focus wash
on the row rather than on the 10px bar, and the stacked status bar gained a tooltip with
keyboard focus — a 3-of-63 segment is too thin to label, so pointing at it is how its
number is read.

**Colour.** A second validated slot (`--viz-series-2`, light `#eb6834`) so loss and output
are not both blue; it passes every check against this app's white card surface
(CVD ΔE 24.7, normal-vision ΔE 33.6, both clear 3:1). The expiry ordinal ramp and the hero
series/flag pair were re-validated unchanged on all five hero surfaces. Status colours are
untouched and still ship an icon and a word.

**A latent dark-mode break was removed.** The `--viz-*` tokens flipped to their dark steps
under `prefers-color-scheme: dark`, but no theme this app ships has a dark chrome —
`--fm-surface` is `#ffffff` in all five — so on an OS-dark machine chart labels rendered
`#f0efec` on white, 1.07:1. The companion `:root[data-theme='dark']` rule could never match,
since the theme attribute sits on `.fm-app`. Both are gone, with a note on what a real dark
theme would require. **Not verified by rendering:** this headless Chrome would not emulate
the media query, so the break was read off the cascade rather than photographed.

**Type.** The hero figure moved to 44px — above the 31px stat row, so the panel reads as the
one focal point — and both it and the KPI values dropped `tabular-nums`, which gives every
digit the width of a zero and makes a display-size figure look loose. Tabular figures stay
where numbers align vertically: table rows and axis ticks. Headings balance; paragraphs
avoid orphans.

`preview/pages.js` gained `?hover=<selector>`, which drives one pointer event after mount:
headless Chrome never moves a mouse, and a chart's hover layer is part of the chart.


### Fifth pass (2026-10-23) — form variety, themes, widths

**Two forms the data was asking for.** The expiry horizon is now a **column chart**:
these buckets are an ordered *time* scale, and time reads left to right. The yield stat
card carries a **sparkline** — the stat-tile contract's trend slot, built from the same
completed runs the panel plots, so the number has its recent shape beside it. The
dashboards now use five distinct forms (line+area, sparkline, ranked bars, stacked bar,
columns) plus the meters already on Quality and Dispatch, each picked by the data's job.

**A recolor-on-filter bug, caught by rendering it.** The column ramp stepped by row
position, but `expiry_buckets` omits an empty bucket — so on a day with no expired stock,
"Within 7 days" wore the darkest step, and on a day with some it wore the second. The
step is keyed to the bucket now, kept in step with `EXPIRY_BUCKETS` in `api/dashboard.py`.

**The sparkline's end dot was an ellipse.** `preserveAspectRatio="none"` stretches
geometry as well as the box, so the dot was flattened and clipped against the right edge.
It uses a uniform scale with the dot inset by its own radius.

**All five palettes rendered**, via a new `?theme=` / `?font=` stamp in the harness —
the appearance menu is behind a click a screenshot cannot make, and it has to run in a
classic script because the appearance store reads `localStorage` during module
evaluation, before any top-level code in `pages.js`. Chrome tints; charts do not.

**Widths checked at 360, 390, 768, 1024, 1440 and 1920.** No horizontal overflow
anywhere. The two Insights pages stacked their KPI cards one per row on a phone while
Overview and the Quality queue showed two; they match now, which halves the scroll before
the first chart. The column chart holds four labelled columns at 360px without rotating a
label.

**README rewritten** as a guide to using the app rather than a project summary: install,
the company policy field by field, material natures, the recipe's confidentiality, the
daily round as a flow, every console route, the chart-form table, the role matrix and a
troubleshooting section covering each failure earlier passes produced.


### Sixth pass (2026-10-24) — measured against the prototype, screen by screen

The feedback was that the HTML designs were never fully implemented and that the
Vue app should have been *better* than them. Both halves were fair. This pass
served the prototype and the Vue app side by side and compared each screen
rather than reasoning about them.

**What the prototype had and the Vue app had lost:**

| Gap | Fix |
|---|---|
| The yield chart had **no x-axis** — you could not tell which run was which | Run labels along the bottom, thinned to what fits, shortened to their distinctive tail |
| Production Insights had **no "Completed-run review" table** at all | `RunReview.vue`, fed by a new `yield_exceptions` list: the flagged runs with input, good output, loss and yield |
| Output groups read a bare **"KG" / "NOS"** | "Bulk production · Kg", "Finished goods · Nos" — the group says what it groups, falling back to the unit when a group is mixed |
| The **quality queue dropped its unit**: "450" not "450 Kg" | `get_release_queue` returns `stock_uom`; a quantity without its unit is not a quantity |
| **Decision notes** only appeared after choosing Hold or Reject | Always shown. A release is worth annotating, and a field that appears mid-form moves the buttons under the cursor |
| No **"View insights"** link from a summary card | `BarRanking` takes a `to` route |
| The sidebar footer was plain text | The company's initials as a mark, as the reference has |
| Run cards showed a progress bar with **no figure** | "42% complete" beside the status |

**What I had made worse, and undid:** Stock quality and Expiry horizon were split
into two cards, which left a half-empty card beside a full one; they are one card
again, as the reference has them, and the status legend is a vertical list with
right-aligned counts instead of a 2×2 grid that ran its entries together.

**Where the Vue app is deliberately ahead of the prototype:** released-lot
"+N more" counts and a "No released stock" warning on Production; a shelf-life
meter on Quality; blocked dispatch rows named in words; honest em dashes for
unmeasured values; every chart with a table view and keyboard access.

`get_item_uoms` moved to `food_manufacturing/items.py` — three modules had grown
their own copy.

**Still not done**, and not claimed: the prototype's fullscreen button, its
working period selector on the overview (ours is a static pill), the circular
progress ring on the production detail card, and a screen-by-screen comparison
of Receiving, Dispatch and Recall.

317 tests pass. Verified against a live session.


### Seventh pass (2026-10-26) — depth, response, and a phone-width bug

The brief was simply to make the app more attractive. Six passes had already got
the structure, typography and charts right, so this one is about the two things
a flat design is still missing — **depth** and **response to the pointer** — plus
one layout defect the renders exposed.

**Cards had no elevation at all.** `--fm-shadow` was a single 3%-alpha wash at
14px, which on a near-white canvas reads as nothing: every surface was a hairline
rectangle and nothing sat *above* anything. It is now two layers — a 1px contact
shadow for the edge and an 18px ambient one for height — with a `--fm-shadow-lift`
step for hover. Both stay cool and low-alpha, so the page still reads as paper.

**Nothing responded to the pointer.** A `fm-card-interactive` class gives a card
whose whole surface is a control — a work order in the queue, a purchase order to
receive, a dashboard shortcut — a border tint, the lift shadow and a 2px rise, with
a matching `:focus-visible` ring so the keyboard gets the same affordance. It
replaces three ad-hoc `hover:border-…` utilities that each did a little less. The
attention rows gained a chevron that nudges on hover.

**Tables had no row wash.** These are read across — an ingredient to its lot and
its expiry, an allocation to the batch it came from — and a wide row with nothing
tying it together is where the eye slips a line. `fm-table-rows` is opt-in, applied
to the six tables with more than one row; the quality queue takes it too, since its
selected row sets its own inline background and only the other rows take the wash.

**The run detail card had no progress figure**, which was on the previous pass's
"still not done" list. `ProgressRing.vue` draws it from the same `progress()` rule
the queue cards use, so a card and the row it was opened from cannot disagree. It
is chrome, not a chart: it uses `--fm-primary` and re-tints with the theme, exactly
as the queue card's bar does. A run at 0% draws a cap at twelve o'clock, because an
empty ring otherwise reads as a disabled control rather than as a run not started.

**Native date inputs were the one unstyled control.** A browser draws them itself,
so on Receiving they sat shorter than the fields beside them with a full-black
picker button. The box height now matches and the indicator is toned; the date
*format* stays the browser's, which is the user's locale.

**A phone-width bug the renders found, and it was not new.** On Production at
390px the run detail card was wider than the screen, so "Produced" was off-screen
entirely — along with the "3 shown" and yield chips. A grid track is sized by its
content's min-content width unless the item may shrink, and neither column carried
`min-w-0`. Confirmed against a build with this pass's changes stashed, so it was
pre-existing rather than introduced here. The ring and the stats also stack on a
phone instead of competing for one row: `flex-1` sets `flex-basis: 0`, which beats
`w-full`, so wrapping had to be a `flex-col sm:flex-row` rather than a width.

**Rendered, not reasoned about.** Every page at 1440 before and after, Production
and Quality at 390, and the copper palette to confirm the new shadows sit correctly
on a warm canvas. Chart colours are untouched, so the data-viz validator did not
need re-running; `yarn build` is clean.

**Not verified:** hover and focus states against a live Frappe session — headless
Chrome drives one synthetic pointer event, which is not the same as using it.
