# Workflows

Standard ERPNext documents are shown in plain text; this app's additions in **bold**.

## 1. Receiving (M2)

1. `Purchase Order` → `Purchase Receipt`, destination = **policy quarantine warehouse**.
2. Receipt item captures **`fm_supplier_lot_no`**, **`fm_supplier_mfg_date`**; an internal
   `Batch` is created with `expiry_date`, `manufacturing_date`, `supplier`, and
   **`fm_quality_status = "Quarantine"`**.
3. `Quality Inspection` (incoming) recorded against the receipt/batch.
4. **`FM Batch Release`** records the decision by an authorised role:
   - *Released* → `fm_quality_status = "Released"`, stock moved out of quarantine.
   - *Hold* → stays in quarantine, consumption blocked.
   - *Rejected* → moved to the **policy rejected warehouse**, consumption blocked.
5. Every decision is an immutable submitted record with actor and timestamp.

**Enforcement:** consumption validation rejects any batch whose status is not *Released*
when `block_unreleased_consumption` / `block_rejected_consumption` are set. Enforced in
`doc_events` on `Stock Entry` and `Delivery Note`, so it also covers API and data-import
paths — not just form buttons.

## 2. Recipe approval (M3)

1. **`FM Recipe`** is entered as percentages that must total 100%.
2. Draft → submitted → **approved** by `FM Recipe Manager`. Formula fields sit at
   `permlevel` 1, so only that role reads them — on forms, APIs, reports and exports.
3. Approval generates a standard submitted `BOM` with explicit quantities and UOMs.
4. Historical production keeps its exact revision: `Work Order.bom_no` pins the submitted
   BOM, which ERPNext will not let you edit. A recipe change creates a **new** revision and
   a new BOM; it never mutates the old one.

## 3. Production — blending (M4)

1. `Work Order` against the approved BOM, qty in kg of bulk blend.
2. `Stock Entry` (Material Transfer for Manufacture) moves **released** ingredient lots to WIP.
3. **`FM Production Run`** records which supplier lots were actually allocated and in what
   quantity, against the planned BOM quantities.
4. `Stock Entry` (Manufacture) produces the **bulk blend batch**.
5. **Yield** is computed: planned vs actual, with `process_loss_qty` (non-recoverable) kept
   separate from recoverable by-products (via `compat/bom.py`). Deviation beyond
   `yield_variance_tolerance_percent` is flagged.
6. Partial completion, cancellation and amendment follow standard Work Order behaviour; the
   production run follows the Work Order's state rather than keeping its own copy.

## 4. Packaging (M5)

1. A **separate** `Work Order` per pack size, consuming the bulk blend item + packaging items.
2. **`FM Packaging Run`** consumes from one bulk batch and produces finished SKU batches,
   recording the bulk→packed link that makes genealogy derivable.
3. Remaining bulk stock stays in the bulk warehouse as normal stock — it is not written off.
4. Packaging variance (pouches/cartons consumed vs theoretical) is recorded.
5. **Double consumption is structurally prevented:** raw ingredients are consumed by the
   blending Work Order only. The packaging Work Order's BOM consumes the *bulk item*, never
   the raw ingredients, so no ingredient can be consumed twice.

## 5. Finished-goods release and dispatch (M6)

1. `Quality Inspection` (finished) on the SKU batch → **`FM Batch Release`**.
2. `Sales Order` → `Delivery Note`. Before submit, validation checks, per batch:
   expiry (`block_expired_dispatch`), remaining shelf life against
   `min_remaining_shelf_life_percent`, release status, warehouse and company match, and
   available quantity.
3. **FEFO** is computed deterministically — ordered by `expiry_date` (never-expiring last),
   then `manufacturing_date`, then `batch_id` as the explicit tie-break. The ordering is
   *total*, so the same stock always produces the same recommendation on any database,
   whatever `Stock Settings.pick_serial_and_batch_based_on` says. Held and rejected batches
   are never recommended.
4. `enforce_fefo` decides whether a non-FEFO pick is silent (Off), warned, or blocked.
5. `Sales Invoice` → `Payment Entry`, entirely standard.

### Permitted quarantine / QC movements

Stock in the quarantine or rejected warehouse may move **only**:

- quarantine → released warehouse (on *Released*)
- quarantine → rejected warehouse (on *Rejected* or later hold-then-reject)
- rejected → supplier, via a standard `Purchase Receipt` return
- rejected → disposal/write-off, via a `Stock Entry` of type Material Issue by an
  authorised role

Any other movement out of quarantine or rejected is blocked. Movement *within* quarantine
(bin to bin) is allowed, since it is not a release.

## 6. Traceability and recall (M6)

- **Backward**, from a sold pack: `Delivery Note` → SKU `Batch` → `FM Packaging Run` →
  bulk `Batch` → `FM Production Run` → ingredient batches → `fm_supplier_lot_no` + `Supplier`.
- **Forward**, from a supplier lot: the same chain reversed, ending at `Delivery Note` and
  customer.
- Genealogy is **derived** from submitted transactions, `Serial and Batch Bundle` entries
  and `Batch.parent_batch` — never from a separately maintained graph that could drift.
- Split batches and multiple ingredient lots produce multiple parents/children and are
  reported as such.
- Cancelled and returned transactions are excluded from, or marked in, the trace rather than
  silently dropped.


## Operator SPA (/fm)

A Vue 3 + frappe-ui app, matching the `marley_frontend` convention in this bench. Served at
`/fm`; `vue-router` owns everything below that prefix.

| Screen | Route | What it does |
|---|---|---|
| Plant overview | `/fm/dashboard` | Hero yield figure, KPI row, yield trend, output by item, quality mix, expiry horizon |
| Production console | `/fm/production` | Open Work Orders, released lots per ingredient in FEFO order, finish a run with good quantity and process loss |
| Quality queue | `/fm/quality` | Batches awaiting a decision, longest-waiting first, with history and genealogy before deciding |
| Goods in | `/fm/receiving` | Receive against a purchase order, capturing supplier lot and manufacturing date |
| Dispatch | `/fm/dispatch` | Pick batches against a sales order with the FEFO suggestion pre-filled and shelf-life blocks shown |

### The security model

The SPA is a **convenience over the same server rules**, never a second route around them.

- The HTML shell carries no data. `www/fm.py` redirects an anonymous visitor to login and
  refuses a Website User, so portal accounts cannot open it.
- Every figure comes from a whitelisted endpoint in `food_manufacturing/api/` that calls
  `frappe.has_permission(..., throw=True)`, and all mutations are `methods=["POST"]`.
- Mutating endpoints build ERPNext's own documents (`make_stock_entry`,
  `make_purchase_receipt`, `make_delivery_note`) and submit them, so the batch quality gate,
  recipe guard, shelf-life floor, FEFO mode and every stock validation run exactly as in the
  Desk. Asserted in `tests/test_api.py`: an inspector cannot release through the API, and
  `finish_production_run` still refuses an unreleased lot.
- The company selector is a browser preference, never a trust boundary; each endpoint
  re-checks permission, so choosing a company you cannot see returns nothing.

### The dashboard

Built against the data-visualization method, with the palette **computed rather than
eyeballed** — the validator was run against this app's own white card surface, not the
reference surface:

| Use | Colour | Validator result |
|---|---|---|
| Yield trend line | series blue `#2a78d6` | all checks pass |
| Expiry horizon bars | ordinal blue ramp, 4 steps | all checks pass |
| Quality status stack | status palette, ordered good → warning → critical → serious | both separation gates pass |

The status order is deliberate. Warning (`#fab219`) beside serious (`#ec835a`) fails the
normal-vision separation floor (ΔE 13.6, needs ≥ 15), so `_quality_mix` emits
**Released, Quarantine, Rejected, Hold** to keep that pair apart — reordering is the
documented fix, and it lifts the worst adjacent pair to ΔE 15.7. Those two hues also sit
below 3:1 on white, which obliges visible relief: every segment carries a direct value
label and the legend repeats each value with an icon and a word, so a status is never
conveyed by colour alone.

Three decisions worth keeping:

- **Bars never scale across units.** Output is grouped by UOM and each group scaled against
  its own maximum. Scaling 1,842 kg against 24,000 packs on one length axis made packs look
  like the entire plant's output.
- **Expiry buckets lead with the most urgent**, darkest step first, so the row needing
  action is not buried under a longer bar for a bucket nobody must act on.
- **On a phone the yield plot is replaced by its table**, not shrunk. Twelve points in
  330px is not a readable chart.

An unknown is never rendered as zero: with no completed runs the average-yield tile shows
`—`, because "we did not measure this" and "this is zero" are different facts.

### Design harness

`frontend/preview/` builds the real chart components against fixture data as a standalone
static page, so the UI can be opened and screenshotted without a Frappe session:

```bash
cd apps/food_manufacturing/frontend
FM_PREVIEW_OUT=/tmp/fm-preview npx vite build --config vite.preview.config.js
```

It is a development tool and is never served by the app.

### Build

```bash
cd apps/food_manufacturing/frontend
yarn install
yarn build          # writes ../food_manufacturing/public/frontend and www/fm.html
cd ../../.. && bench build --app food_manufacturing
```

Build output (`public/frontend/`) and the generated `www/fm.html` are gitignored, so the
repo holds sources only.


## Demo data

`food_manufacturing/demo/seed.py` seeds the acceptance scenario as **real ERPNext
documents**, so the demo exercises the same validations a plant would: quarantine routing,
the quality gate, recipe approval, yield and loss, packaging genealogy and FEFO dispatch.

```bash
bench --site <site> execute food_manufacturing.demo.seed.create_demo_data \
  --kwargs '{"company":"Steps ERP (Demo)"}'

bench --site <site> execute food_manufacturing.demo.seed.remove_demo_data \
  --kwargs '{"company":"Steps ERP (Demo)"}'
```

With no `company` it picks a company whose name contains "Demo", falling back to the first.

### What it creates

Everything is prefixed `FM Demo`. Five supplier lots across three spices — three released,
one left in quarantine so the QC queue is not empty, one rejected for moisture. An approved
percentage recipe (60% chilli / 40% cumin) generating a BOM. Three blending runs, two within
tolerance and one at 91% so the variance flag has something to show. Packaging into 1,000 ×
50 g and 400 × 100 g from one bulk batch, leaving bulk on hand. A delivery note to a
customer, so a sold pack traces forward. Three ageing batches so the expiry horizon is
populated.

### Three properties that make it safe on a shared site

- **Namespaced** — every record carries the `FM Demo` prefix.
- **Idempotent** — re-running produces identical figures and never duplicates. In
  particular a quality decision is never overwritten: an early version re-stamped every lot
  back to Quarantine on the second run, silently undoing the releases.
- **Reversible** — `remove_demo_data` cancels and deletes in dependency order. Two details
  that took fixing: a BOM and the FM Recipe that generated it point at each other, so the
  link is broken before either is deleted; and a warehouse holding stock ledger entries is
  **disabled rather than deleted**, because deleting stock history to tidy up a demo would
  be the wrong trade.

### One site-wide change

The seeder turns on `Stock Settings.enable_serial_and_batch_no_for_item`, without which no
batched stock can move at all. This affects **every company on the site**. Teardown restores
it only if the seeder was the one that changed it.
