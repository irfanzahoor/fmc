# PRD — Food Manufacturing

## Who this is for

Small and medium spice/masala manufacturers: buy whole and ground spices, blend to a
recipe, pack into several retail sizes, and sell to distributors and retailers. Typically
one plant, a handful of operators, one QC person, and a regulatory need to trace any sold
pack back to the supplier lots it came from.

## Problem

Standard ERPNext handles the money and the stock correctly but leaves the plant's actual
rules unmodelled:

- Recipes are kept as percentages, not quantities, and are confidential.
- Incoming material must sit in quarantine until QC releases it; nothing stops an operator
  consuming unreleased or rejected material.
- A blend is made once in bulk, then packed into several SKUs over days. Nothing links the
  bulk batch to the packed batches.
- Expiry and remaining shelf life gate dispatch, and customers demand FEFO.
- A recall means tracing a sold pack back to supplier lots within minutes.

## Approach

Reuse ERPNext for purchasing, stock, manufacturing, selling and accounting. Add only the
rules above, enforced on the server. No parallel stock ledger, accounting engine, invoice or
payment system. Every custom DocType is justified in `docs/data-model.md`.

## Core flow

```
Purchase Order → Purchase Receipt (→ quarantine, supplier lot captured, internal Batch created)
  → Quality Inspection → FM Batch Release (released | hold | rejected)
  → FM Recipe (approved revision) → BOM
  → Work Order → FM Production Run (actual lot allocations, yield, process loss, by-products)
  → bulk blend Batch
  → Work Order → FM Packaging Run (consume bulk + pouches/cartons) → finished SKU Batches
  → Quality Inspection → FM Batch Release
  → Sales Order → Delivery Note (expiry / shelf-life / release / FEFO validated)
  → Sales Invoice → Payment Entry
```

## Scope

**In scope:** setup and pack sizes; approved percentage recipes with confidential-formula
access control; supplier-lot receiving with incoming QC and hold/release/reject; production
with actual consumption, yield variance, process loss and recoverable by-products;
packaging with bulk-to-packed genealogy and packaging variance; expiry and FEFO dispatch
control; full forward and backward traceability including splits, returns and cancellations;
costing reports that separate planned estimates from ledger valuation; operator-focused
role-based screens.

**Out of scope:** payroll and HR; maintenance management; transport/fleet; e-commerce;
anything that duplicates standard ERPNext accounting or stock valuation; label artwork
design (we print from data, we do not design labels).

## Documented assumptions

Taken to avoid blocking; each is cheap to change and should be confirmed during pilot.

| # | Assumption | Why | Change cost |
|---|---|---|---|
| 1 | One `Item` per pack size (e.g. "Garam Masala 50g"), with `UOM Conversion Detail` for pack↔kg | How ERPNext models sellable SKUs; keeps standard costing and selling intact | low |
| 2 | Bulk blend is a stocked `Item` with its own `Batch`, not a virtual intermediate | Bulk genuinely sits in stock between blending and packing (7 kg remainder in the acceptance scenario) | high if changed |
| 3 | Blending and packing are **separate Work Orders** | They happen on different days with different outputs; one WO cannot produce several SKUs with correct batch genealogy | high if changed |
| 4 | Quarantine and rejected are **warehouses**, not just batch statuses | Keeps unreleased stock out of available quantity in standard reports; status alone leaves it sellable | medium |
| 5 | Batch quality state lives in a `fm_quality_status` custom field on `Batch`, with the decision audit in `FM Batch Release` | Status must be queryable in standard stock validations; audit needs its own submittable record | low |
| 6 | Process loss is non-recoverable; by-products are separately stocked items | Matches ERPNext's own split, and the two have different costing treatment | low |
| 7 | Recipe confidentiality is enforced with `permlevel` on formula fields | The framework-supported mechanism that also covers API, report and export paths | low |
| 8 | Shelf life is a percentage of total shelf life, not fixed days | Spice SKUs have very different shelf lives; a fixed day count misbehaves across them | low |
| 9 | FEFO is **recommended and optionally enforced** (Off/Warn/Block), default Warn | Plants need overrides for genuine reasons; hard enforcement from day one blocks dispatch | low |
| 10 | Labour and overhead come from standard BOM operations and ERPNext work-order costing, not a custom engine | Keeps actual cost reconcilable with the ledger | medium |
| 11 | Company scoping uses the standard `company` field plus `permission_query_conditions` | Standard mechanism; avoids a bespoke access layer | low |

## Non-goals and honesty constraints

- No regulatory certification claims (FSSAI, HACCP, ISO, FDA). The app records data an
  auditor may ask for; it does not certify anything, and documentation must not imply it.
- No compatibility claim for a version until it has actually been verified — see
  `docs/compatibility.md`.
