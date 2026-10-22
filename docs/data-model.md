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
| `FM Production Run` | `Work Order` does not record which supplier lots were actually allocated, nor planned-vs-actual yield with a loss/by-product split. Wraps, does not replace, the Work Order. | planned (M4) |
| `FM Packaging Run` | No standard record links one bulk batch to the several SKU batches packed from it, nor tracks packaging variance. | planned (M5) |

Deliberately **not** created: any invoice, payment, stock ledger, valuation or accounting
DocType. Those remain pure ERPNext.

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
