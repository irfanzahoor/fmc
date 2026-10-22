# Implementation handoff for Claude

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

Use the screenshots and HTML listed in this directory's README. Implement with
the existing Vue 3, frappe-ui, Tailwind and lucide-vue-next stack. Adapt the
reference markup into Vue components instead of embedding exported HTML or
copying CDN scripts into the application.

Desktop: compact left sidebar with Overview, Production, Quality, Receiving,
Dispatch and Recall; topbar with active company selector and page context.
Light neutral background, white cards, restrained blue actions, navy text,
tabular quantities, subtle borders and compact readable tables. Reuse common
components and tokens in `frontend/src/components/` and `frontend/src/index.css`.

Mobile: compact navigation, stacked forms/cards and at least 44px touch targets.
Use the overview yield table instead of squeezing a chart. Make all six pages
responsive even though only three explicit mobile references are included.

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
- Recall currently returns affected batches and deliveries, not the intermediate
  graph edges shown by Stitch. Do not fabricate genealogy connections. Render
  available data honestly; any API expansion requires a separate justified,
  permission-checked implementation.
- The generated design-system text sometimes contradicts these requirements
  (mixed-unit bars, telemetry, small touch targets). This handoff and the actual
  application rules take precedence.
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

All nine screenshots and HTML exports are stored in this repository so the work
can proceed without reconnecting Stitch. No API credentials belong in these files.
