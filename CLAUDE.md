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

## Commands

```bash
cd /home/codeboy/bench-16
bench --site steps_erp.local migrate                 # after DocType JSON, patch or fixture changes
bench build --app food_manufacturing                 # after public JS/CSS changes
bench --site steps_erp.local clear-cache             # after hooks.py changes
bench --site steps_erp.local run-tests --app food_manufacturing
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
