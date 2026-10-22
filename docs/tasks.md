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

## Open blockers

| # | Blocker | Impact | Needs |
|---|---|---|---|
| B1 | No DB root and no passwordless `sudo`; MariaDB root uses `unix_socket` auth | Cannot create dedicated `fm15.local` / `fm16.local` sites, so verification runs on the populated shared site `steps_erp.local` | MariaDB root password, or the user runs `bench new-site` |
| B2 | ~~v15 not verified~~ | **Closed**: v15 is out of scope as of 2026-10-22 (v16 only) | — |
| B3 | ~~v15→v16 upgrade rehearsal~~ | **Closed**: not applicable to a v16-only target | — |
| B4 | Host site has `Stock Settings.enable_serial_and_batch_no_for_item` **off** | Batched receiving is impossible on this site without it. Receiving tests enable it and restore it; a real pilot site must have it on | Turn it on in Stock Settings before pilot |
| B5 | Tests run against the user's live site | Test fixtures must never create Companies/Warehouses there | Already mitigated: fixtures discover existing records and skip if absent |

## Next — Milestone 4

Production runs: actual consumption, lot allocation, yield and loss. Acceptance criteria
4.1–4.7 are already written in `docs/acceptance.md`.

1. `FM Production Run` wrapping a standard Work Order, recording which supplier lots were
   actually allocated against the planned BOM quantities
2. Bulk output batch with correct quantity and expiry
3. Planned vs actual yield, flagged against `yield_variance_tolerance_percent`
4. Process loss (`process_loss_qty`) reported separately from recoverable by-products,
   which are reached only through `compat/bom.py`
5. Partial completion, cancellation and amendment leaving consistent stock
6. Concurrency: the same batch cannot be oversold by two simultaneous consumptions
