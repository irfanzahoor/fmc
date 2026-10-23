# FMC presentation design system

## Typography and composition

Primary pairing: Plus Jakarta Sans for headings/figures, Inter for operational
copy. Alternate pairing reverses those roles. Variable WOFF2 fonts are self-hosted
with their OFL licenses. Use tabular quantities, 31px desktop headings, 25px phone
headings, 31px KPI figures, readable 12–14px operational data and compact secondary
metadata. The dark sidebar establishes navigation; white surfaces and a lightly
tinted canvas keep forms readable. Standard cards have 16px corners, subtle
borders and restrained elevation. The overview's dark performance panel creates
one focal point rather than giving every card the same weight.

## Selectable palettes

| Theme | Sidebar | Primary action | Soft accent | Canvas |
| --- | --- | --- | --- | --- |
| Midnight Blue (default) | `#111D33` | `#4263EB` | `#EDF1FF` | `#F4F6FB` |
| Forest | `#142F29` | `#247861` | `#EAF4EE` | `#F4F7F3` |
| Amethyst | `#251D39` | `#7552B5` | `#F1ECFA` | `#F7F5FA` |
| Graphite | `#202831` | `#445366` | `#EDF0F3` | `#F4F5F6` |
| Copper | `#342A23` | `#9C5B35` | `#FAF0E8` | `#F8F5F0` |

`--primary`, `--soft`, `--canvas`, `--ink`, `--muted`, `--border`, `--sidebar`,
`--side-ink`, `--hero` and `--line` vary by theme. Semantic quality meanings keep
stable colors and explicit labels/icons across themes. Do not use theme color
alone to imply that a batch is released or blocked.

## Pages and dashboards

Six operations pages form the main navigation. Production and Quality also have
separate Insights views, accessible by tabs and sidebar links; together with
Plant Overview, they make three dashboards. Work-order/batch selection, quantity
editing, search, filters and review dialogs support a coherent presentation.
The gallery embeds the actual HTML runtime rather than stale screenshot thumbnails.

## Responsive behavior

240px desktop sidebar, a company/context topbar and comfortable card spacing.
Tablet layouts reduce column counts. Phone layouts use six visible navigation
items, horizontal work-order selection, labeled table cards, stacked forms and
a yield run list instead of a squeezed overview graph. Phone input/action targets
are at least 44px, with secondary filter/navigation controls sized for their role.

## Functional boundaries

All figures are illustrative. Sample stock counts reconcile (48 Released +
8 Quarantine + 4 Hold + 3 Rejected = 63 batches); 54 batches in the expiry buckets
match the 90-day near-expiry figure. Recent-run yields and the overall period
average represent different populations. No trend comparison or revenue is invented.

The app's real company scope, permissions, inspections, retry keys and server policy
must govern implementation. Suggestions do not reserve stock. Dispatch scanning
focuses quantity; receiving scanner Enter does not post. Recall remains read-only,
with negative returns and a visibly illustrative incomplete-result state. Do not
introduce machine telemetry, recipe percentages or bypass controls.

These palettes are presentation references. Before changing application chart
colors, run the required visualization validation on each applicable surface;
the prototype does not establish chart-palette certification. Production copy
must follow repository translation requirements.
