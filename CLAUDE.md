# Project instructions

This is a Frappe/ERPNext app for spice and masala manufacturers.

- For ALL code work in this repository, load and follow the `frappe-code-standards` skill before
  writing code. Its placement rules, error-handling rules and review checklist are mandatory.
  Standards source: https://github.com/NexTash/frappe-code-standards
  Standards commit in use: `099cbe788c69ed6f27b6b196d3b2671766c56a05` (2026-10-19, "Frappe Code Standards plugin")
  Local checkout: `/home/codeboy/fmc/frappe-code-standards`
- Do not use other skills for code in this repository unless asked.

## Project facts (detected 2026-10-22)

| Fact | Value |
|---|---|
| Our app | `food_manufacturing` — DocTypes here are "ours" |
| App repo path | `/home/codeboy/bench-16/apps/food_manufacturing` |
| Module(s) | `Food Manufacturing Setup`, `Food Manufacturing Quality` |
| Custom field prefix (other apps' DocTypes) | `fm_` |
| Our DocType prefix | `FM ` (e.g. `FM Manufacturing Policy`) |
| Primary bench | `/home/codeboy/bench-16` |
| Primary site | `steps_erp.local` |
| v16 versions | frappe 16.52.0 (`4515014c87`), erpnext 16.27.0 (`9d5c7605b8`) |
| v15 | **out of scope** (2026-10-22). Do not add v15 claims or v15-only code paths. |
| Python | 3.14.0 |
| Other apps on the primary site | `erpnext`, `realestate` — extend only via hooks/fixtures |

`steps_erp.local` is a **populated, shared site** holding unrelated work (6 companies,
11 warehouses, the `realestate` app). Never write test fixtures that create Companies or
Warehouses there; discover existing records instead. See `food_manufacturing/tests/`.

## Frontend

Planned Stitch redesign: read `docs/ui-design/README.md` and
`docs/ui-design/IMPLEMENTATION.md` for the saved screenshots, HTML references and
implementation handoff. The redesign is not implemented yet; preserve the
existing API behavior and use actual server data over generated mockup content.
The original visual direction was rejected. The approved replacement direction
is in `docs/ui-design/premium/`, with all six workflows on desktop and phone.
Start with its `index.html` gallery and README.

Vue 3 + frappe-ui + Tailwind + lucide-vue-next, in `frontend/`, served at `/fm`. Matches the
`marley_frontend` convention in this bench. Note `frappe-ui` 0.1.278 exposes its Tailwind
preset at `frappe-ui/tailwind` — the older `frappe-ui/src/tailwind/preset` subpath is gone
from its exports map.

**frappe-ui's Tailwind preset replaces the font-size scale and stops at `text-2xl`** —
`text-4xl` and `text-5xl` generate no CSS at all, so a hero number written with them
silently renders at base size. The dashboard's hero uses a `text-fm-hero` token added in
`tailwind.config.js`.

Charts are hand-rolled inline SVG rather than a chart library: the mark specs (2px lines,
≥8px markers with a surface ring, 2px gaps between stacked fills, selective direct labels)
are easier to meet directly than to configure, and it avoids a dependency. Before changing
any chart colour, re-run the data-viz validator against the white card surface.

Client code is UX only. Every rule is enforced in `food_manufacturing/api/` (permission
checks, POST-only mutations) and in the `doc_events` handlers beneath it.

## Commands

```bash
cd /home/codeboy/bench-16
bench --site steps_erp.local migrate                 # after DocType JSON, patch or fixture changes
bench build --app food_manufacturing                 # after public JS/CSS changes
bench --site steps_erp.local clear-cache             # after hooks.py changes
bench --site steps_erp.local run-tests --app food_manufacturing

cd apps/food_manufacturing/frontend && yarn build   # after frontend changes
```

## Project-specific rules

- Never modify Frappe or ERPNext core. Extend standard DocTypes via `doc_events`,
  `overrides/` modules and scoped fixtures only.
- Reuse standard ERPNext for stock, valuation, invoicing and payments. Do not create a
  parallel stock ledger, accounting engine, invoice or payment doctype. Justify every new
  DocType in `docs/data-model.md` before creating it.
- All version differences live in `food_manufacturing/compat/`. Controllers must not test
  versions. Prefer schema capability checks (`meta_has_field`) over version numbers.
- Confidential recipe data is protected with `permlevel`, not hidden in JS. Protection must
  hold on forms, APIs, reports and exports.
- Business rules and permission checks are enforced on the server. Client JS is UX only.
- Whitelisted methods check permissions explicitly; mutations use POST.
- No `ignore_permissions` without an inline comment stating why (install-time bootstrap only).
- Patches are idempotent and tracked in `patches.txt`.
- Explicit `fields` in every query; explicit `order_by` where order matters across versions.
- No DB queries inside loops; no `frappe.db.commit()` in controllers or request handlers.
