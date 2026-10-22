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
