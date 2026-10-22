# Acceptance criteria

Criteria are written **before** each milestone is implemented. A milestone is done only when
every criterion has an actually-executed check, or is explicitly marked NOT RUN.

Legend: PASS / FAIL / **NOT RUN** (environment unavailable). v15 columns were removed on
2026-10-22 when the project was scoped to v16 only.

## Milestone 1 — foundation

| # | Criterion | Check | v16 |
|---|---|---|---|
| 1.1 | Workspace inspected; installed apps, versions, sites and Git state recorded | `docs/compatibility.md`, `CLAUDE.md` | PASS |
| 1.2 | Standards commit recorded | `CLAUDE.md` → `099cbe78` | PASS |
| 1.3 | Standard-feature reuse map exists and justifies every custom DocType | `docs/data-model.md` | PASS |
| 1.4 | Cross-version risks identified from real schemas | `docs/compatibility.md` risk register | PASS |
| 1.5 | App installs on a matched-major site | `bench install-app food_manufacturing` | PASS |
| 1.6 | `bench migrate` succeeds and is idempotent | ran post-install and again; patch logged once | PASS |
| 1.7 | `bench build --app` succeeds | exit 0, assets linked | PASS |
| 1.8 | 6 FM roles created, idempotently | `test_setup.py` (4 tests) | PASS |
| 1.9 | Per-company policy with server-enforced rules | `test_manufacturing_policy.py` (14 tests) | PASS |
| 1.10 | Policy defaults are restrictive, not permissive | `test_defaults_are_conservative` | PASS |
| 1.11 | Compat layer resolves to names the live site really has | `test_compat.py` (7 tests) | PASS |
| 1.12 | Frappe and ERPNext majors must match | `test_majors_are_matched` | PASS |
| 1.13 | No Frappe/ERPNext core file modified | `git status` clean in both app repos | PASS |
| 1.14 | Unrelated work on the host site preserved | no stray rows; no test Company/Warehouse created | PASS |
| 1.15 | CI jobs defined for both majors | `.github/workflows/` | PASS (defined) |

Result: **PASS on v16.** v15 out of scope — see `docs/compatibility.md`.

## Milestone 2 — items, batches, supplier lots, incoming QC — DONE on v16

| # | Criterion | Check | v16 |
|---|---|---|---|
| 2.1 | Item classified Raw / Packaging / Bulk Blend / Finished via `fm_material_nature`; fixtures scoped to our module | `setup/custom_fields.py`, 15 fields stamped with our modules | PASS |
| 2.2 | Purchase Receipt captures supplier lot and manufacturing date; internal `Batch` created with expiry | `overrides/purchase_receipt.py::stamp_batches` | PASS |
| 2.3 | Received stock lands in the policy quarantine warehouse | `route_to_quarantine` + `test_receipt_into_quarantine_is_not_blocked` | PASS |
| 2.4 | `fm_quality_status` defaults to Quarantine and is never writable directly by an operator | `test_batch_quality_status_is_read_only_on_the_form` | PASS |
| 2.5 | `FM Batch Release` records release / hold / reject with actor and timestamp, immutably | `test_reject_sets_status_and_records_reason`, `test_decision_records_who_authorised_it` | PASS |
| 2.6 | Only `FM Quality Manager` may release or reject; `FM Quality Inspector` may only record inspections | `test_quality_inspector_cannot_create_a_release`, `test_quality_manager_may_release` | PASS |
| 2.7 | Consuming an unreleased batch is blocked — via form, via `frappe.client` API, and via data import | `test_quarantine_batch_cannot_be_consumed`, `test_rule_holds_on_the_api_path` | PASS |
| 2.8 | Consuming a rejected or held batch is blocked on all three paths | `test_held_batch_cannot_be_consumed`, `test_rejected_batch_cannot_be_consumed` | PASS |
| 2.9 | Permitted quarantine movements (per `docs/workflows.md`) succeed; all others are blocked | `test_quarantine_to_rejected_is_permitted`, `test_quarantine_to_stores_is_blocked` | PASS |
| 2.10 | Policy toggles actually relax the rules when turned off | `test_policy_toggle_relaxes_unreleased_rule`, `..._rejected_rule` | PASS |
| 2.11 | Cross-company access blocked: a user restricted to company A cannot read or release company B's batches | `test_user_restricted_to_another_company_cannot_read_the_release` | PASS |
| 2.12 | Release is idempotent — a retried/duplicate request does not double-move stock | `test_duplicate_release_is_rejected`, `test_cancel_restores_previous_status` | PASS |

## Milestone 3 — recipes — DONE on v16

Confidentiality is enforced with `permlevel` 1 on the `ingredients` table and on every child
field. Frappe applies permlevel in three separate places, so each is tested on its own:
`apply_fieldlevel_read_permissions` (form, `/api/resource`, `frappe.client.get`),
`get_permitted_fields` via `db_query` (list view, report view, `get_list`), and the
data-import `Exporter`. Two findings worth recording: `get_list` **silently drops** a
confidential column rather than raising, and `FM Production Manager` cannot export at all,
so the field-stripping test uses a role that is explicitly granted export at permlevel 0.

| # | Criterion | Check | v16 |
|---|---|---|---|
| 3.1 | Percentages must total 100%; conversion to quantity/UOM is explicit and asserted | `test_percentages_must_total_one_hundred`, `test_uom_conversion_is_explicit`, `test_missing_uom_conversion_is_reported` | PASS |
| 3.2 | Production is impossible against an unapproved recipe | `test_superseded_recipe_cannot_be_produced`, `test_bom_without_a_recipe_is_left_alone` | PASS |
| 3.3 | Approval generates a submitted standard BOM | `test_approval_generates_a_submitted_bom` | PASS |
| 3.4 | A new revision never mutates the BOM used by historical production | `test_new_revision_supersedes_the_old_one_without_touching_its_bom` | PASS |
| 3.5 | Unauthorised recipe access blocked on form **and** `/api/resource`, `/api/method`, report view, and export | `test_get_list_strips_*`, `test_exporter_strips_the_formula_for_a_permitted_exporter`, `test_document_read_hides_*` | PASS |
| 3.6 | A user without `FM Recipe Manager` cannot read formula fields by any of those paths | `test_permitted_fieldnames_exclude_the_formula_for_an_outsider`, `test_level_zero_writer_cannot_change_the_formula` | PASS |

## Milestone 4 — production — DONE on v16

No `FM Production Run` DocType was created: ERPNext's Work Order already tracks planned vs
actual quantities, process loss and v16 by-products. See `docs/data-model.md` for the
revised decision. Yield became `fm_` fields on Work Order, and lot allocation is derived
from the ledger.

| # | Criterion | Check | v16 |
|---|---|---|---|
| 4.1 | Actual ingredient quantities and lot allocations recorded against planned | `test_blend_run_records_yield_and_genealogy`, `test_consumed_lots_carry_supplier_lot_metadata` | PASS |
| 4.2 | Bulk output batch created with correct qty and expiry | `test_blend_run_records_yield_and_genealogy` (produced batch asserted from the ledger) | PASS |
| 4.3 | Planned vs actual yield computed; variance beyond tolerance flagged | `test_variance_beyond_tolerance_is_flagged`, `test_tolerance_comes_from_the_policy` | PASS |
| 4.4 | Process loss and recoverable by-products reported separately | `test_byproducts_are_reported_separately_from_process_loss` | PASS |
| 4.5 | By-products read/written only through `compat/bom.py`; verified on both majors | `test_byproducts_read_through_the_compat_layer` | PASS (v16 only) |
| 4.6 | Partial completion, cancellation and amendment leave consistent stock and no orphan FM records | `test_cancelling_the_manufacture_entry_resets_the_yield`, `test_partial_completion` | PASS |
| 4.7 | Concurrent consumption of the same batch cannot oversell it | `test_duplicate_release_is_rejected` (row lock); stock oversell is ERPNext's own guard | **PARTIAL** — release races are tested; a true two-process concurrent consumption test is **NOT RUN** and is owed |

## Milestone 5 — packaging

| # | Criterion |
|---|---|
| 5.1 | Bulk + packaging consumed, finished SKU batches produced, per pack size |
| 5.2 | Bulk→packed genealogy recorded and queryable |
| 5.3 | Remaining bulk stock stays correct and available |
| 5.4 | Packaging variance recorded |
| 5.5 | Raw ingredients cannot be consumed twice (structural: packaging BOM consumes bulk only) |

## Milestone 6 — expiry, dispatch, recall

| # | Criterion |
|---|---|
| 6.1 | Near-expiry alerts fire per `near_expiry_alert_days` |
| 6.2 | Minimum remaining shelf life enforced at dispatch |
| 6.3 | FEFO deterministic: ordered by expiry, then manufacturing date, then batch id |
| 6.4 | Expired / rejected / held stock blocked per policy, on form and API |
| 6.5 | Warehouse, company, available qty and quality eligibility all validated |
| 6.6 | Backward trace from a sold batch reaches supplier lots; forward trace reaches customers |
| 6.7 | Split batches and multi-lot inputs traced correctly |
| 6.8 | Returns and cancellations correctly reflected in the trace |

## Milestone 7 — costing, dashboards, hardening

| # | Criterion |
|---|---|
| 7.1 | Cost per batch and per pack reported |
| 7.2 | Planned estimate vs actual ledger valuation clearly separated |
| 7.3 | Operational reports reconcile with standard ERPNext stock and GL reports |
| 7.4 | Labour, overhead and wastage treatment documented and consistent |
| 7.5 | Role-based workspace: production queue, pending QC, near-expiry, yield variance |
| 7.6 | Screens responsive; scoped CSS; no global theme override; no fragile DOM manipulation |

## Representative acceptance scenario (M5 gate)

Synthetic demo data, asserted end to end:

| Step | Expected |
|---|---|
| Consume ingredients | 100 kg from identified supplier lots |
| Produce blend | 97 kg usable bulk |
| Process loss | 3 kg, recorded as loss — not as a by-product |
| Pack 50 g | 1,000 packs = 50 kg |
| Pack 100 g | 400 packs = 40 kg |
| Remaining bulk | 7 kg, if no additional packing loss |
| Packaging consumed | pouches and cartons per pack size |
| Trace | both finished batches → actual supplier lots → customers |

Also asserted: quantities and UOM conversions, valuation, batch links, and cancellation
behaviour at every step.

## Standing negative tests (run every milestone from M2)

Unauthorised recipe access · consumption of held/rejected material · dispatch of expired
stock · partial completion · returns · split and mixed lots · duplicate/retried requests ·
cross-company access · migration on both majors.
