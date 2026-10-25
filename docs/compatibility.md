# Compatibility

**Active targets: v15 and v16.** On 2026-10-25 v15 was brought back in scope at the user's
direction and the port was completed on the `version-15` branch. Both majors are now
delivery targets and both are verified by a real run (see the matrix).

All version-dependent behaviour lives in `food_manufacturing/compat/`. Controllers,
reports and JS never test versions themselves, so a new major is absorbed by changing that
layer only.

The app supports **matched majors only**: Frappe and ERPNext must share a major version.
`tests/test_compat.py::test_majors_are_matched` asserts this on every run.

## Matrix

| Target | Frappe | ERPNext | Bench | Site | Install | Migrate | Build | Tests |
|---|---|---|---|---|---|---|---|---|
| **v16** | 16.52.0 (`4515014c87ece6cb20ee91d2cfb121c5cbd1ff4a`) | 16.27.0 (`9d5c7605b8eae7fb5aaf9efd00a778adae2daeb1`) | `/home/codeboy/bench-16` | `steps_erp.local` | PASS | PASS | PASS | PASS 376/376 |
| **v15** | 15.118.0 (`9b8d265b27a1dfb11c7aef21a533a127e14a0a5a`) | 15.119.0 (`866688931ba51b20c8ecb77d7594c641339590ee`) | `/home/codeboy/bench-15` | `fmc.local` | PASS | PASS | PASS | PASS 376/376 |

Both benches run Python 3.14.0. Verified 2026-10-25 against the commits above.

On v16 the 376 are reported by the newer runner as 361 integration + 15 unit tests; on v15
the older runner reports one flat count. Zero skips on either, which required giving the
test site the fixtures described under "Test sites" below — before that, 325 of the 376
skipped on v15 and the port was effectively unverified.

## Test sites

`tests/fixtures.py` never creates a Company or a Warehouse: building a Company builds a
full chart of accounts and is effectively irreversible, which is unsafe on a shared or
populated site. It discovers what the site already has and skips when the site cannot
supply it. It needs **two companies**, one with at least three enabled leaf warehouses.

Items, Batches, Customers and Suppliers *are* created, because they are cheap and
removable.

`tests/ci_setup.prepare()` creates the fixture companies and parties. It refuses to run
unless the site carries `fm_isolated_test_site` in its site config — an explicit, deliberate
opt-in, because this is the one piece of test setup that cannot be undone. The gate is that
flag and nothing else; it used to be a hardcoded `ci.localhost`, which meant no other
disposable site could ever be prepared.

To prepare a disposable site:

```bash
bench --site <site> set-config allow_tests true
bench --site <site> set-config fm_isolated_test_site true
bench --site <site> execute food_manufacturing.tests.ci_setup.prepare
```

`fmc.local` is prepared this way. Its fixture records are `FM CI Primary` / `FM CI
Secondary` (companies, four leaf warehouses each) and `FM CI Customer` / `FM CI Supplier`.
`FM CI Primary` sorts before the site's own `FMC` company, so the suite runs inside the CI
companies and leaves `FMC` untouched.

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
v15 code paths degrade rather than crash.

**Impact on this app:** recoverable by-products (e.g. reclaimed over-size grind) must be
read and written only through `compat/bom.py`. Direct `bom.scrap_items` access anywhere in
the app is a defect. On v15 a Work Order cannot carry by-products at all, so
`fm_byproduct_qty` is necessarily 0 there and `compute_yield` reports process loss on its
own — `tests/test_yield.py` asserts whichever contract the running version has.

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

### 4. Serial and Batch Entry columns denormalised in v16 — CONFIRMED BREAK

`Serial and Batch Bundle` exists in both majors and the **parent** carries `is_cancelled`,
`item_code`, `voucher_no`, `voucher_type`, `type_of_transaction` and `posting_datetime` in
both. v16 additionally copied several of those onto the **child** `Serial and Batch Entry`
row; v15's child table has none of them.

| Column on the child row | v15 | v16 |
|---|---|---|
| `batch_no`, `warehouse`, `qty`, `is_outward`, `stock_value_difference` | yes | yes |
| `is_cancelled` | **no** | yes |
| `item_code` | **no** | yes |
| `voucher_no`, `voucher_type`, `type_of_transaction`, `posting_datetime` | **no** | yes |

This was the single largest break in the v15 port: 55 test errors from
`Unknown column 'tabSerial and Batch Entry.is_cancelled'` and `Unknown column 'item_code'`.

Handled by `compat/bundle.py`:

* `get_entries(filters, fields, order_by, pluck)` — a `frappe.get_all` over
  `Serial and Batch Entry` whose `fields`, `pluck` and `filters` may name any
  parent-backed column. Where the child row has the column the call passes straight
  through as one query; otherwise the rows are matched to their parents in a second,
  **bounded** query. Never one query per row. Only equality is supported on a
  parent-backed filter, and anything else throws rather than silently returning wrong rows.
* `restrict_to_live(query, entry)` — for query-builder queries, restricts to rows of
  non-cancelled bundles, joining the parent where the child has no `is_cancelled`.

A bundle holds one item and is cancelled as a whole, so parent and child say the same
thing; reading it from the parent is correct on both majors rather than a v15 fallback.

**Impact on this app:** `Serial and Batch Entry` must be read only through
`compat/bundle.py` whenever a parent-backed column is involved. Note that
`Stock Ledger Entry.is_cancelled` is unaffected and exists in both majors — only the
bundle's child table moved.

### 5. Test base class renamed — CONFIRMED BREAK

| v15 | v16 |
|---|---|
| `frappe.tests.utils.FrappeTestCase` | `frappe.tests.IntegrationTestCase` |

Handled by `compat/testing.py`, which exports `FMTestCase`. Every test subclasses it. v16
still ships a deprecated `FrappeTestCase`, so the shim prefers the current name and falls
back, rather than the reverse.

### 6. Site-wide lot switch is v16-only — CONFIRMED BREAK

v16 added `Stock Settings.enable_serial_and_batch_no_for_item` ("Activate Serial / Batch No
for Item") and ships `erpnext/patches/v16_0/enable_serial_batch_setting.py` to turn it on
for upgraded sites. While it is off, v16 refuses to build a Serial and Batch Bundle, so no
batched stock can move. **v15 has no such field** — lot handling is unconditionally
available — and writing to it there fails with
`Field enable_serial_and_batch_no_for_item does not exist on Stock Settings`.

This produced 107 test errors in the v15 port, from test setup turning the switch on.

Handled by `compat/stock.py`: `get_lot_feature()` reports the value or `None` where the
version has no switch, and `set_lot_feature(value)` is a no-op there. Save/restore pairs
stay symmetrical on both majors, so callers set it unconditionally. `demo/seed.py` skips
the switch entirely on a version without one, so teardown has nothing to restore.

### 7. ERPNext stock exceptions moved in v16 — CONFIRMED BREAK

| | v15 | v16 |
|---|---|---|
| `BatchExpiredError` | `erpnext.controllers.stock_controller` | `erpnext.exceptions` |

v16 moved `BatchExpiredError` and the `QualityInspection*Error` classes into
`erpnext.exceptions`. `erpnext.exceptions` exists on v15 but holds only the accounts
exceptions, so `from erpnext.exceptions import BatchExpiredError` is an `ImportError` there.

Handled by `compat/exceptions.py`, which tries the canonical v16 home first and falls back
to v15's. v16 also imports the class into `stock_controller` for its own use, so
`tests/test_compat.py` asserts the shim resolves to the *same class object* the stock
controller raises — identity matters, because `assertRaises` against a look-alike class
would never match.

### 8. Data Import exporter ignores `permlevel` on v15 — CONFIRMED SECURITY BREAK

v16's `Exporter` runs every requested field through `frappe.model.get_permitted_fields`, so
a `permlevel` 1 field never reaches a CSV for a user holding permlevel 0 access only.
**v15's `Exporter` filters on fieldtype alone** and will export a permlevel 1 field to
anyone allowed to read the DocType at all.

This app protects the confidential recipe formula with `permlevel`, and that protection has
to hold on exports as much as on forms, APIs and reports — so on v15 the framework alone
does not deliver the guarantee this app makes. It showed up as
`test_exporter_strips_the_formula_for_a_permitted_exporter` leaking `total_percentage`,
`item_code`, `percentage`, `qty` and `stock_qty`.

Handled in two places:

* `compat/exporter.py` — an `Exporter` subclass that drops any field above the user's
  permlevel access. The filtering is **idempotent**, so it is applied unconditionally on
  both majors and there is no version branch to keep in step.
* `overrides/data_import.py` + `override_whitelisted_methods` in `hooks.py` — reroutes
  `frappe.core.doctype.data_import.data_import.download_template`, the endpoint the Desk
  export dialog and `/api/method` use, so a real export is covered and not just the test.
  **Only this app's own DocTypes are rerouted**; every other app on the site keeps the
  framework's behaviour exactly, because silently changing how their exports treat
  permlevel is not this app's call to make.

### 9. `frappe.get_doc(dict)` does not apply DocType defaults

Not a version difference, but it only bites on v15. `frappe.get_doc({...})` leaves
`is_return` as `None`, where `frappe.new_doc(...)` sets it to `0`; defaults are applied by
`insert()` / `save()`, not by construction. ERPNext v15's `selling_controller.set_incoming_rate`
computes `is_standalone = self.is_return and not self.return_against`, which is `None`
rather than `False`, and v15's typed `get_incoming_rate(raise_error_if_no_rate: bool = True)`
rejects it with `FrappeTypeError`.

So a document that is validated **without ever being inserted** must be built with
`frappe.new_doc`. `tests/test_batch_eligibility.py` does, and says why.

### 10. Known risks not yet exercised

| Risk | Plan |
|---|---|
| Query ordering | Always pass explicit `order_by`. Default sort differs between majors and across MariaDB versions. |
| Workspace / navigation format | The four workspaces, five script reports and one print format install and migrate cleanly on both majors (verified 2026-10-25). v16's Docks remain v16-only. |
| `frappe.clear_document_cache` location | Defined in `frappe/__init__.py` on v15, moved to `frappe.model.document` on v16 but re-exported. `frappe.clear_document_cache(...)` is safe on both; `frappe.clear_cached_doc` does **not** exist on v15 and must not be used. |
| `non_negative` DocField property | Unverified on v15, so **not** used in DocType JSON. Non-negativity is enforced in the controller instead. |
| Python version | Both benches run 3.14, so `pyproject.toml` targets `>=3.10` rather than pinning 3.14, to keep the app installable on an older v15 bench. |
| Populated v15 → v16 upgrade | Rehearsal still owed (see `docs/tasks.md`). |
| v16 test runner categories | v16 splits the suite into integration and unit categories; v15 reports one flat count. Any new test should run under both runners, not just the one on the bench in front of you. |

## Rules for contributors

1. Inspect the real schema before using a field: `frappe.get_meta(dt).has_field(f)`.
2. No version checks in controllers, reports or JS. Add to `compat/` instead.
3. Prefer capability detection over `frappe_major()`. Version numbers are the last resort.
4. Never claim a version works until its row in the matrix above is filled from a real run.
5. Prefer a shim that is correct on **both** majors over one that branches. `compat/exporter.py`
   and `compat/bundle.py` are idempotent and parent-backed respectively for this reason —
   an unbranched shim cannot rot on the version you are not currently running.
6. Run the suite on both benches before finishing. A change that is green on one major and
   untested on the other is not done.
