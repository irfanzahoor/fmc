# Tasks

Status as of 2026-10-22.

## Milestone 1 — foundation — DONE on v16

- [x] Inspect workspace: apps, versions, sites, Git state
- [x] Read standards repo; record commit `099cbe78`
- [x] Standard-feature reuse map (`docs/data-model.md`)
- [x] Cross-version risk register from real schemas (`docs/compatibility.md`)
- [x] Merge implementation into the existing `bench new-app` scaffold
- [x] Compat layer: `compat/__init__.py`, `compat/bom.py`, `compat/testing.py`
- [x] 6 roles, created idempotently in `before_install` + `pre_model_sync` patch
- [x] `FM Manufacturing Policy` per company, server-enforced
- [x] Tests: 25, all passing on v16
- [x] Verify install, migrate, build, cache clear on `steps_erp.local`
- [x] CI workflows for both majors
- [ ] **v15 verification — deferred by request**

## Milestone 2 — items, batches, supplier lots, incoming QC — DONE on v16

- [x] `setup/custom_fields.py`: 15 custom fields on Item, Purchase Receipt Item and Batch
- [x] `FM Batch Release` submittable DocType with transitions, audit trail and cancellation
- [x] Quarantine routing and supplier lot capture on Purchase Receipt
- [x] Batch eligibility enforcement via `doc_events` on Stock Entry and Delivery Note
- [x] Role authorisation and cross-company isolation tests
- [x] Fixed: Module Def ordering so one `bench migrate` is enough for a new module
- [x] Fixed: batches reached through a Serial and Batch Bundle were invisible to hooks
      because ERPNext writes the bundle link with `frappe.db.set_value` during submit
- [x] 73 tests passing

## Milestone 3 — approved recipes and BOM integration — DONE on v16

- [x] `FM Recipe` + `FM Recipe Ingredient`: percentage entry totalling 100%, explicit and
      stored UOM conversion factors, derived quantities
- [x] Confidential formula at `permlevel` 1, proven on document read, list/report query and
      export, with real users rather than by inspecting the schema
- [x] Approval generates a submitted standard BOM (`BOM.fm_recipe` links back)
- [x] Revisions: auto-increment, supersede the previous recipe, never mutate its BOM;
      cancellation restores the previous revision
- [x] `Work Order` guard: a superseded or unapproved recipe cannot be produced, while BOMs
      with no recipe are left alone
- [x] Fixed: a parent DocType referencing a child table that sorts after it alphabetically
      was silently skipped by `bench migrate` (`FM Recipe` vs `FM Recipe Ingredient`).
      Child tables are now imported before the main sync pass.
- [x] 108 tests passing

## Milestone 4 — production, yield and loss — DONE on v16

- [x] **Design revised**: no `FM Production Run`. Work Order already maintains planned vs
      actual quantities, process loss and v16 by-products, so a wrapper would have
      duplicated standard features. Justified in `docs/data-model.md`.
- [x] `production/yield_tracking.py`: yield, variance and policy flagging as `fm_` fields on
      Work Order, refreshed on Stock Entry submit and cancel
- [x] `production/genealogy.py`: consumed and produced batches derived from the ledger,
      reading both `SLE.batch_no` and Serial and Batch Bundle entries
- [x] End-to-end blending run: receive to quarantine, release, approved recipe, Work Order,
      manufacture, then assert yield and lot genealogy against real stock
- [x] Fixed: ERPNext defaults `Work Order.stock_uom` to `Nos`, so the yield wrongly reported
      "mixed UOMs" for an all-kg blend. The output UOM now comes from the Item.
- [x] Fixed: batches allocated through a Serial and Batch Bundle were missing from the
      genealogy, because the SLE's own `batch_no` is empty in that case.
- [x] 124 tests passing

## Open blockers

| # | Blocker | Impact | Needs |
|---|---|---|---|
| B1 | No DB root and no passwordless `sudo`; MariaDB root uses `unix_socket` auth | Cannot create dedicated `fm15.local` / `fm16.local` sites, so verification runs on the populated shared site `steps_erp.local` | MariaDB root password, or the user runs `bench new-site` |
| B2 | ~~v15 not verified~~ | **Closed**: v15 is out of scope as of 2026-10-22 (v16 only) | — |
| B3 | ~~v15→v16 upgrade rehearsal~~ | **Closed**: not applicable to a v16-only target | — |
| B4 | Host site has `Stock Settings.enable_serial_and_batch_no_for_item` **off** | Batched receiving is impossible on this site without it. Receiving tests enable it and restore it; a real pilot site must have it on | Turn it on in Stock Settings before pilot |
| B5 | Tests run against the user's live site | Test fixtures must never create Companies/Warehouses there | Already mitigated: fixtures discover existing records and skip if absent |
| B6 | Frappe rolls the test transaction back **per class**, not per test | Tests that post real stock saw each other's ledger entries (a 120 kg requirement against 60 kg of stock) | Mitigated: production-flow tests derive item and batch names from the test name |
| B7 | True concurrency (two processes consuming one batch) not tested | Acceptance 4.7 only partially met — the release row-lock is tested, stock oversell relies on ERPNext's own guard | Needs a two-process test harness |

## Next — Milestone 5

Packaging and bulk-to-finished traceability. Acceptance criteria 5.1–5.5 are already
written in `docs/acceptance.md`.

1. A packaging BOM that consumes the bulk item plus pouches and cartons — never the raw
   ingredients, which is what structurally prevents double consumption
2. A separate Work Order per pack size, producing finished SKU batches
3. Bulk-to-packed genealogy, extending `production/genealogy.py`
4. Packaging variance: pouches and cartons consumed versus theoretical
5. The full acceptance scenario: 97 kg blend, 1,000 x 50 g, 400 x 100 g, 7 kg bulk left
