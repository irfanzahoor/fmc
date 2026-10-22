# Compatibility

**Active target: v16 only.** On 2026-10-22 the project was scoped to v16 at the user's
direction. v15 is no longer a delivery target, so no v15 claim is made anywhere in this
repository.

The compat layer in `food_manufacturing/compat/` is **kept**: it costs nothing, it already
isolates the differences found, and it is what makes a later v15 or v17 target cheap. Its
v15 branches are written but unexercised.

The app supports **matched majors only**: Frappe and ERPNext must share a major version.
`tests/test_compat.py::test_majors_are_matched` asserts this on every run.

## Matrix

| Target | Frappe | ERPNext | Bench | Site | Install | Migrate | Build | Tests |
|---|---|---|---|---|---|---|---|---|
| **v16 (active)** | 16.52.0 (`4515014c87ece6cb20ee91d2cfb121c5cbd1ff4a`) | 16.27.0 (`9d5c7605b8eae7fb5aaf9efd00a778adae2daeb1`) | `/home/codeboy/bench-16` | `steps_erp.local` | PASS | PASS | PASS | PASS 64/64 |
| v15 (out of scope) | 15.118.0 (`9b8d265b27a1dfb11c7aef21a533a127e14a0a5a`) | 15.119.0 (`866688931ba51b20c8ecb77d7594c641339590ee`) | `/home/codeboy/bench-15` | — | **NOT RUN** | **NOT RUN** | **NOT RUN** | **NOT RUN** |

Both benches run Python 3.14.0. Verified 2026-10-22 against the commits above.

> v15 is **out of scope** as of 2026-10-22. The row above is kept to record what was
> measured, not as a pending promise. Nothing in this repository claims v15 support.

## Cross-version risk register

Confirmed by reading the actual schemas in both benches, not from release notes.

### 1. BOM by-product table renamed — CONFIRMED BREAK

| | v15 | v16 |
|---|---|---|
| BOM field | `scrap_items` | `secondary_items` |
| Child DocType | `BOM Scrap Item` | `BOM Secondary Item` |
| Cost fields | `scrap_material_cost`, `base_scrap_material_cost` | `secondary_items_cost`, `base_secondary_items_cost` |
| Work Order field | *absent* | `secondary_items` |

Handled by `compat/bom.py`. Resolution is by schema capability (`meta_has_field`) with the
newest name tried first, so a site that backports either name still resolves correctly, and
the child DocType is read from the field's own `options` rather than a hardcoded table.
`supports_work_order_byproducts()` reports whether Work Order carries the table at all, so
v15 code paths can degrade rather than crash.

**Impact on this app:** recoverable by-products (e.g. reclaimed over-size grind) must be
read and written only through `compat/bom.py`. Direct `bom.scrap_items` access anywhere in
the app is a defect.

### 2. Process loss — NO SHIM NEEDED

`process_loss_percentage` and `process_loss_qty` exist on BOM in both majors, and
`process_loss_qty` on Work Order in both. Non-recoverable loss (moisture, dust, spillage)
is therefore expressed identically. This matters because the acceptance scenario's 3 kg
loss is process loss, **not** a by-product — so the main production path is version-neutral
and only the optional by-product path needs the shim.

### 3. Batch schema — EFFECTIVELY IDENTICAL

Field-by-field diff of `batch.json` shows only a layout change (v15's `sb_disabled` section
break is gone in v16). Every field this app relies on is present in both:
`batch_id`, `item`, `expiry_date`, `manufacturing_date`, `supplier`, `parent_batch`,
`reference_doctype`, `reference_name`, `use_batchwise_valuation`, `batch_qty`,
`produced_qty`, `qty_to_produce`, `disabled`.

`parent_batch` in both majors is what makes split-batch genealogy possible without a
custom graph table.

### 4. Serial and Batch Bundle — PRESENT IN BOTH

`Serial and Batch Bundle` exists in both majors. Behavioural parity (bundle creation on
Stock Entry, on Work Order completion, and on cancellation) is **not yet verified** and is
scheduled for M2/M4 where the app first depends on it. Asserted today only at the level of
"the DocType exists".

### 5. Test base class renamed — CONFIRMED BREAK

| v15 | v16 |
|---|---|
| `frappe.tests.utils.FrappeTestCase` | `frappe.tests.IntegrationTestCase` |

Handled by `compat/testing.py`, which exports `FMTestCase`. Every test subclasses it. v16
still ships a deprecated `FrappeTestCase`, so the shim prefers the current name and falls
back, rather than the reverse.

### 6. Known risks not yet exercised

Listed so they are not forgotten; none are touched by M1 code.

| Risk | Plan |
|---|---|
| Query ordering | Always pass explicit `order_by`. Default sort differs between majors and across MariaDB versions. |
| Workspace / navigation format | v16 changed Workspace internals (and adds Docks). Build the workspace in M7 and verify on both, or ship per-version fixtures. |
| `frappe.clear_document_cache` location | Defined in `frappe/__init__.py` on v15, moved to `frappe.model.document` on v16 but re-exported. `frappe.clear_document_cache(...)` is safe on both; `frappe.clear_cached_doc` does **not** exist on v15 and must not be used. |
| `non_negative` DocField property | Unverified on v15, so **not** used in DocType JSON. Non-negativity is enforced in the controller instead. |
| Python version | Both benches run 3.14, so `pyproject.toml` targets `>=3.10` rather than pinning 3.14, to keep the app installable on an older v15 bench. |
| Populated v15 → v16 upgrade | Rehearsal still owed (see `docs/tasks.md`). |

## Rules for contributors

1. Inspect the real schema before using a field: `frappe.get_meta(dt).has_field(f)`.
2. No version checks in controllers, reports or JS. Add to `compat/` instead.
3. Prefer capability detection over `frappe_major()`. Version numbers are the last resort.
4. Never claim a version works until its row in the matrix above is filled from a real run.
