# Data model and standard-feature reuse map

The rule for this app: **ERPNext owns stock, valuation, costing and money.** We add the
food-manufacturing rules ERPNext does not model, and we link to standard records rather
than copying them.

## Reuse map

| Need | Standard ERPNext feature we reuse | What we add (prefix `fm_` / `FM `) |
|---|---|---|
| Raw material, packaging, bulk blend, finished SKU | `Item`, `Item Group`, `UOM`, `UOM Conversion Detail` | `fm_material_nature` to classify an Item as Raw / Packaging / Bulk Blend / Finished; pack size fields on finished SKUs |
| Multiple pack sizes | One `Item` per pack size + `UOM Conversion Detail` | `fm_pack_size`, `fm_pack_uom`, `fm_bulk_item` linking a SKU to its bulk blend |
| Warehouses, quarantine, rejected | `Warehouse` | `FM Manufacturing Policy` names the quarantine / rejected / bulk / packaging / FG warehouses per company |
| Supplier, customer | `Supplier`, `Customer` | — |
| Purchasing | `Purchase Order`, `Purchase Receipt`, `Purchase Invoice` | `fm_supplier_lot_no`, `fm_supplier_mfg_date` on receipt items; receipt routes to quarantine |
| Internal lot identity | `Batch` (`batch_id`, `expiry_date`, `manufacturing_date`, `supplier`, `parent_batch`) | `fm_quality_status` (Quarantine / Released / Hold / Rejected), `fm_supplier_lot_no`, `fm_released_by`, `fm_released_on` |
| Batch/serial movement | `Serial and Batch Bundle`, `Serial and Batch Entry` | validation hooks only — never a parallel ledger |
| Recipe | `BOM`, `BOM Item`, `BOM Operation`, `Routing` | `FM Recipe` holding percentage-based entry + approval state, which **generates** a BOM; the submitted BOM remains the record of truth for costing |
| Recipe revision history | `BOM` is immutable once submitted; `Work Order.bom_no` pins the revision used | `FM Recipe` revision no. + link to the generated BOM |
| Process loss (non-recoverable) | `BOM.process_loss_percentage` / `process_loss_qty`, `Work Order.process_loss_qty` | — identical on v15 and v16, no shim needed |
| Recoverable by-product | v15 `BOM.scrap_items` (`BOM Scrap Item`) / v16 `BOM.secondary_items` (`BOM Secondary Item`) | accessed only through `compat/bom.py` |
| Production | `Work Order`, `Job Card`, `Stock Entry` (Material Transfer for Manufacture, Manufacture) | `FM Production Run` as an operational wrapper recording actual lot allocations and planned-vs-actual yield; stock moves stay standard `Stock Entry` |
| Packaging | `Work Order` + `Stock Entry` consuming bulk + packaging, producing SKU batches | `FM Packaging Run` recording bulk-to-packed genealogy and packaging variance |
| Quality | `Quality Inspection`, `Quality Inspection Template`, `Quality Inspection Parameter`, `Quality Inspection Reading` | `FM Batch Release` recording the authorised hold/release/reject decision with audit trail |
| Selling and dispatch | `Sales Order`, `Delivery Note`, `Sales Invoice`, `Payment Entry` | dispatch-time validation of expiry, remaining shelf life and batch release status |
| Traceability | `Stock Ledger Entry`, `Serial and Batch Bundle`, `Batch.parent_batch` | report-only genealogy derived from submitted transactions — no stored duplicate graph |
| Costing | `Stock Ledger Entry` valuation, `BOM` cost, `Landed Cost Voucher` | reports that present ledger valuation per batch and per pack, clearly separated from BOM planned cost |

## Why each custom DocType is justified

A custom DocType is only created where standard configuration cannot express the rule.

| DocType | Why standard configuration is insufficient | Status |
|---|---|---|
| `FM Manufacturing Policy` | ERPNext has no per-company place to declare quarantine/rejected warehouses, shelf-life floors, FEFO mode or yield tolerance. `Stock Settings` is a Single and cannot vary by company. | **implemented (M1)** |
| `FM Recipe` | A BOM cannot be entered as percentages, has no approval state distinct from submit, and has no confidential-formula permlevel. Generates a standard BOM rather than replacing it. | planned (M3) |
| `FM Batch Release` | `Quality Inspection` records *measurements*; it does not record an authorised release decision, who made it, or a later hold/reject with history. Batch status alone has no audit trail. | planned (M2) |
| ~~`FM Production Run`~~ | **Not created — design revised in M4 after reading the real schema.** `Work Order` already maintains `required_items[].required_qty` / `consumed_qty`, `produced_qty`, `process_loss_qty`, and (v16) by-products in `secondary_items`; ERPNext updates them itself when a manufacturing Stock Entry is submitted or cancelled. A wrapper DocType would have duplicated all of that. The genuine gaps — a **yield** figure and a variance flag against the company tolerance — are `fm_` fields on Work Order, and lot allocation is *derived* from the ledger rather than stored. | **replaced by an extension** |
| ~~`FM Packaging Run`~~ | **Not created — design revised in M5.** A packaging run is a standard Work Order whose BOM consumes the bulk blend plus packaging materials. The bulk→packed link is already in the ledger, so genealogy is derived rather than stored, and packaging variance comes from `Work Order Item.required_qty` / `consumed_qty`. What ERPNext cannot express is the *shape* a packaging BOM must have, which is enforced in `packaging/validation.py`. | **replaced by validation + derivation** |

Deliberately **not** created: any invoice, payment, stock ledger, valuation or accounting
DocType. Those remain pure ERPNext.

## Production yield (M4)

No custom DocType. `fm_` fields on `Work Order`, computed by
`production/yield_tracking.py` and refreshed by a `doc_events` hook on Stock Entry
submit/cancel — exactly when ERPNext updates `produced_qty` and `consumed_qty`.

| Field | Purpose |
|---|---|
| `fm_planned_input_qty`, `fm_actual_input_qty` | Input totals, in the output's stock UOM |
| `fm_planned_yield_percent`, `fm_actual_yield_percent` | Output over input |
| `fm_yield_variance_percent`, `fm_yield_flagged` | Deviation, flagged against `yield_variance_tolerance_percent` |
| `fm_byproduct_qty` | Recoverable by-products, read only through `compat/bom.py` |
| `fm_process_loss_qty_snapshot` | Non-recoverable loss, copied from the standard field |
| `fm_yield_basis` | The UOM the yield was computed in, **or why it could not be** |

Two deliberate honesty constraints:

- `required_qty` and `consumed_qty` are each in their own item's stock UOM. Summing them is
  only meaningful when every ingredient shares the output's UOM, so when they differ the
  yield is left blank and `fm_yield_basis` explains why, rather than reporting a number
  derived by adding kilograms to grams.
- The output UOM comes from the production **Item**, not `Work Order.stock_uom`: ERPNext
  defaults that field to `Nos` and does not reliably set it from the item. Trusting it
  produced a false "mixed UOMs" result for a blend whose every quantity was in kg.

### Genealogy (`production/genealogy.py`)

Derived, never stored, so it cannot drift from the ledger. Batches are read from
`Stock Ledger Entry.batch_no` **and** from the `Serial and Batch Entry` rows of the SLE's
bundle — ERPNext uses the bundle when it allocates batches itself, and leaves the SLE's own
`batch_no` empty. Reading only one of the two silently loses rows. An SLE that has a bundle
is read from the bundle alone, so nothing is double counted. Cancelled entries are excluded,
which is what makes cancellations and returns behave without special handling.

## Packaging (M5)

A packaging run is a standard Work Order per pack size. `packaging/validation.py` enforces
the two rules ERPNext cannot:

- A BOM producing a `Finished Good` may consume only `Bulk Blend` and `Packaging Material`
  items. Consuming a `Raw Material` is rejected. Since the blending Work Order is the only
  thing that consumes ingredients, **there is no path by which an ingredient is consumed
  twice** — 5.5 is structural, not a procedure anyone has to remember.
- The bulk item the BOM consumes must be the one the SKU declares in `fm_bulk_item`, so a
  SKU cannot silently be packed from the wrong blend.

Packaging variance (`get_packaging_variance`) is derived from `Work Order Item.required_qty`
versus `consumed_qty`. Nothing is stored, so it cannot fall out of step with the ledger.

### Tracing

`trace_backward(item_code, batch_no)` walks a packed SKU batch back through the Work Orders
that produced it to the batches they consumed, recursively, ending at purchased lots with
their `fm_supplier_lot_no` and supplier. Packed SKU → bulk blend → ingredient lots falls out
of the same recursion, so packaging needs no genealogy code of its own. `trace_forward`
and `get_consuming_work_orders` give the dispatch direction for recall. A depth limit stops
bad data causing infinite recursion.

## Costing (M7)

`costing/batch_cost.py`. Two figures, deliberately never mixed:

| Figure | Source | Meaning |
|---|---|---|
| **Actual** | `stock_value_difference` over the batch's inward ledger entries | The stock ledger's own valuation — the same number ERPNext posted to the GL |
| **Planned** | `BOM.total_cost` scaled to the quantity made | An estimate made before the run |

The actual figure reconciles with the standard Stock Ledger and Stock Balance reports *by
construction*, because it is read from the same rows rather than recomputed. Planned cost is
blank for a purchased batch: there is no BOM estimate for bought material, and inventing one
would blur the very line this module exists to keep.

### Labour, overhead and wastage

These follow ERPNext's own treatment; this app adds no costing engine.

- **Labour and overhead** come from BOM operations and the Work Order's operating cost.
  ERPNext includes them in the valuation of the output, so they are already inside the
  actual figure. `planned_operating_cost` is reported separately for comparison.
- **Non-recoverable process loss** is not written off. The same value is spread over fewer
  surviving units, so the unit cost rises — which is the correct accounting and needs no
  adjustment from us. Asserted in
  `test_process_loss_raises_the_unit_cost_of_what_survives`: 3 kg lost from 100 kg worth
  10,000 leaves 97 kg at 103.09, with the total still 10,000.
- **Recoverable by-products** are stocked items in their own right and take valuation at the
  rate ERPNext assigns them, which reduces the cost carried by the main output.

Per-pack cost needs no arithmetic: a finished SKU's stock UOM *is* the pack, so the unit
rate is the cost per pack. It is stated as its own column because that is the number a
pricing conversation needs.

## Implemented schema (M1)

### FM Manufacturing Policy
Named after its company (`autoname: field:company`), so exactly one policy per company.

| Field | Type | Purpose |
|---|---|---|
| `company` | Link Company (unique, reqd) | scope |
| `enabled` | Check | disable without deleting |
| `quarantine_warehouse` | Link Warehouse (reqd) | receipt destination pending inspection |
| `rejected_warehouse` | Link Warehouse (reqd) | rejected material, blocked from production |
| `bulk_warehouse`, `packaging_warehouse`, `finished_goods_warehouse` | Link Warehouse | defaults for production and packaging |
| `require_incoming_inspection` | Check (default 1) | QI required before release |
| `block_unreleased_consumption` | Check (default 1) | block consuming un-released batches |
| `block_rejected_consumption` | Check (default 1) | block consuming rejected/held batches |
| `min_remaining_shelf_life_percent` | Percent (default 25) | dispatch floor |
| `near_expiry_alert_days` | Int (default 30) | alert horizon, 0 disables |
| `block_expired_dispatch` | Check (default 1) | hard stop on expired stock |
| `enforce_fefo` | Select Off/Warn/Block (default Warn) | FEFO mode |
| `yield_variance_tolerance_percent` | Percent (default 2) | yield flagging threshold |

Server-enforced rules (`fm_manufacturing_policy.py`): every warehouse must belong to the
policy's company; quarantine / rejected / bulk / finished must be distinct; percentages in
0–100; alert days non-negative. Defaults are deliberately **restrictive** — an
unconfigured policy blocks rather than permits.

Accessors: `get_policy(company)` throws when missing (safe default for consumption
validation); `get_policy_if_any(company)` returns `None`, and also returns `None` for a
disabled policy.
