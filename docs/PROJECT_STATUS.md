# Batchwell — project status

Product brand **Batchwell**; technical app name stays `food_manufacturing`.

Target: **Frappe v16 / ERPNext v16 only.** Verified against Frappe 16.52.0 and
ERPNext 16.27.0. No v15 compatibility layer, branch or test is maintained.

---

## Audit, 2026-10-23

### Implemented and working

| Area | Where | State |
|---|---|---|
| Company policy | `FM Manufacturing Policy` | Per-company warehouses, QC gates, shelf-life floor, FEFO mode, yield tolerance |
| Confidential recipes | `FM Recipe` + `FM Recipe Ingredient` | Percentages at `permlevel` 1; stripped from read, `get_list`, export template and exporter |
| Quality decisions | `FM Batch Release` | Submittable, audited; release/hold/reject |
| Quality gate | `quality/batch_eligibility.py` | Blocks unreleased/rejected consumption and dispatch via `doc_events` |
| Shelf life + FEFO | `dispatch/shelf_life.py`, `dispatch/fefo.py` | Minimum remaining shelf life, expiry block, FEFO warn/block |
| Yield | `production/yield_tracking.py` | Actual vs planned, process loss, variance flag |
| Packaging rules | `packaging/validation.py` | A packaging run must consume its declared bulk item and no raw ingredients |
| Traceability | `production/genealogy.py`, `api/recall.py` | Forward and backward trace from submitted stock transactions |
| Batch cost | `costing/batch_cost.py` | Actual inward value per batch, and planned cost |
| Operator console | `frontend/`, `www/fm.py` | Vue 3 + frappe-ui SPA at `/fm`: 6 screens + 3 dashboards |
| Near-expiry alerts | `tasks/near_expiry.py` | Daily scheduler job |

**241 tests pass** on v16 (227 integration + 14 unit).

### Partial

- **Dashboards are not role-scoped.** One Plant Overview plus Production and
  Quality insights, built from `api/dashboard.py`. There is no Owner, Stores or
  per-role view, and no cost-variance metric.
- **Quality Inspection is read, never written.** `api/quality.py` requires a
  matching accepted inspection before release, but the app does not create
  inspections, carry templates, or distinguish incoming / in-process / finished
  checks.
- **Costing is batch-level and after the fact.** `costing/batch_cost.py` answers
  "what did this batch cost", not "what would this recipe cost".

### Missing

- Recipe cost simulator — **this phase**
- Packaging material planning and Material Requests
- Quality Inspection lifecycle (templates, evidence, disposition history)
- Role-based dashboards

### Known gaps carried forward

- Fresh-install verification has not been run (no DB root on this machine).
- True two-process concurrency (acceptance 4.7) is **PARTIAL** — single-process
  only.
- `ruff` is in `.pre-commit-config.yaml` but is not installed in this bench, so
  lint is **NOT RUN**.

---

## Phase 1 — Recipe cost simulator

Status: **implemented**. 17 tests, all passing. Full suite **257 passing**
(243 integration + 14 unit), no regressions.

### What it does

| Requirement | Where |
|---|---|
| Select an approved BOM, batch size, pack sizes | `api/costing.get_costable_boms`, `simulate_recipe_cost` |
| Ingredient, packaging and operating cost | `costing/simulator._cost`, `_lines` |
| Cost per batch, per unit, per pack | `total_cost`, `cost_per_unit`, `packs[].cost_per_pack` |
| Baseline vs changed prices, quantities, yield | `baseline` / `scenario` / `delta` in one response |
| Price sources, UOM conversions, assumptions | `rate_source` per line, `conversion_factor`, `assumptions[]` |
| Must not modify BOMs or ledgers | No write path exists; asserted by two tests |
| Estimated cost ≠ ledger valuation | `basis: "estimate"`, stated in `assumptions[0]` |

### Design decisions

**No new DocType.** A simulation is a calculation, not a record. The strongest
guarantee that nothing is modified is to have no write path at all, so
`costing/simulator.py` only reads.

**Rates are ERPNext's, not ours.** `costing/pricing.py` uses the rate already
costed onto the BOM, and falls back to `erpnext...bom.get_bom_item_rate` for a
row that has none. A second opinion on what an ingredient costs is exactly the
duplication that drifts from the ledger. What this app adds is *provenance*:
every rate comes back with the source that produced it, and a reason when it
could not be priced.

**Yield spreads cost over good output.** 8,000 of material at 97% yield is
82.47/kg, not 80.00 — the three kilograms that did not survive still cost money.

**Costing does not leak the formula.** A BOM generated from an `FM Recipe`
carries the formula in the clear: the quantities *are* the percentages. A caller
without permlevel-1 read on `FM Recipe` gets `shows_ingredient_detail: false`,
the totals, and no lines. Asserted both ways.

**Pack cost is blend only.** A pack's own pouch, label and carton belong to the
packaging run and its BOM; folding them in here would double-count them against
that run. Phase 2 covers them.

### Worked example (the acceptance case)

100 kg blend, 60% chilli at 100/kg + 40% cumin at 50/kg:

| | |
|---|---|
| Material | 6,000 + 2,000 = **8,000** |
| Per kg at 100% yield | **80.00** |
| Per kg at 97% yield | **82.47** |
| Per 50 g pack (100% yield) | **4.00** |
| Chilli to 120/kg | 9,200 — **+1,200 (+15%)** |

### Not covered

- The `docstatus != 1` guard has **no test**. ERPNext submits a BOM on insert in
  this bench, and cancelling is blocked while the `FM Recipe` links to it, so
  the fixture cannot reach a draft or cancelled BOM. The guard is in the code;
  no test is claimed for it. Deactivation (`is_active = 0`) *is* covered.
- **NOT RUN:** HTTP round-trip against a live session. The permission paths are
  exercised in-process with `frappe.set_user`, which is the same
  `has_permission` code path, and JSON-string arguments (how HTTP delivers
  `packs` and `overrides`) have their own test.
- **NOT RUN:** `ruff` — in `.pre-commit-config.yaml`, not installed in this bench.
- No console UI yet. The endpoints are ready; the screen is not built.

### Handoff for review

- `food_manufacturing/costing/simulator.py` — the calculation, read-only
- `food_manufacturing/costing/pricing.py` — rate resolution and provenance
- `food_manufacturing/api/costing.py` — two whitelisted reads
- `food_manufacturing/tests/test_cost_simulator.py` — 17 acceptance tests

Worth a second pair of eyes on: whether `_may_see_formula` should also gate the
*packaging* lines (currently it gates both, which may be stricter than needed —
packaging is not confidential), and whether operating cost should come from the
BOM alone or also from a per-company overhead rate on `FM Manufacturing Policy`.

---

## Phase 2 — Packaging material planning

Status: **implemented**. 17 tests, all passing. Full suite **275 passing**
(261 integration + 14 unit), no regressions.

### What it does

| Requirement | Where |
|---|---|
| Blend, pouches, labels, cartons for planned packs | `packaging/planning._requirements` |
| Explicit UOM conversions | `packaging/conversion.to_stock_qty` |
| Configurable packing-loss allowance | `FM Manufacturing Policy.packing_loss_percent`, overridable per request |
| Availability, commitments, expected receipts, net shortage | `packaging/planning._stock_position` |
| Reviewable Material Requests, no duplicates | `packaging/requests.create_material_request` |

### Design decisions

**The stock position is four numbers, not one.** "Do we have enough" collapses
an answer the planner needs to see:

| | Bin field | Meaning |
|---|---|---|
| On hand | `actual_qty` | physically there |
| Committed | `reserved_qty` + `reserved_qty_for_production` | promised to a sales order or an open run |
| Already requested | `indented_qty` | a Material Request is open |
| Expected | `ordered_qty` | a purchase order is due |

Shortage nets all four.

**Duplicates are prevented twice, because one way is not enough.** By
*arithmetic*: `indented_qty` is netted off, so a shortage already requested is
no longer a shortage and re-planning the same run produces nothing — the
behaviour a planner expects without knowing about keys. By *key*: arithmetic
loses a race between two people clicking at once, so the plan carries an
idempotency fingerprint and a repeat returns the first request.

**The request is a draft, and stays one.** A planner proposes; a buyer decides.
Submitting on the operator's behalf would put purchasing authority behind a
shop-floor button.

**ERPNext's `get_conversion_factor` is deliberately not used.** It returns
**1.0** when it finds nothing, which is indistinguishable from a genuine 1:1
conversion — and planning 50 g of blend as 50 kg is exactly the failure this
module exists to prevent. `packaging/conversion.py` reads the item's UOM table
and the global table directly, so "unknown" comes back as zero and is reported
as a note rather than guessed. A test asserts the blend line is *dropped* and a
note raised when the conversion is missing.

**The blend is counted once.** It is implied by the pack's fill quantity *and*
listed in the packaging BOM; the BOM row for the declared bulk item is skipped.

**The loss allowance defaults to zero.** A packing-loss figure is a plant's own
measurement, not something this app should invent.

### Worked example (the brief's acceptance case)

1,000 packs of 50 g, one pouch and one label each:

| | |
|---|---|
| Blend | 1,000 × 50 g = **50 kg** (factor 0.001, reported) |
| Pouches / labels | **1,000** each |
| With 2% allowance | 51 kg, 1,020 each |
| 400 pouches on hand | shortage **600** |
| After the request is submitted | `requested_qty` 1,000, shortage **0** |

### Not covered

- **NOT RUN:** HTTP round-trip. Permissions are exercised in-process via
  `frappe.set_user`, the same `has_permission` path.
- **NOT RUN:** `ruff` — absent from this bench.
- Concurrency is guarded by a `for_update` row lock on the key lookup, but
  **two-process contention is NOT TESTED** — the suite is single-process.
- No console UI yet.

### Handoff for review

- `food_manufacturing/packaging/planning.py` — requirements and stock position
- `food_manufacturing/packaging/conversion.py` — UOM factors, stated not assumed
- `food_manufacturing/packaging/requests.py` — the draft Material Request
- `food_manufacturing/tests/test_packaging_planning.py` — 17 acceptance tests

Worth a second look at: whether a shortage should be requested into the
*quarantine* warehouse rather than stores when the policy requires incoming
inspection (currently the caller names the warehouse), and whether the plan
should also consider stock in transit.

---

## Phase 3 — Quality hold and release

Status: **implemented**. 16 tests, all passing. Full suite **291 passing**
(277 integration + 14 unit), no regressions.

### What was already there

The hold/release/reject rules, the audited `FM Batch Release` record and the
server-side blocks on consumption and dispatch predate this phase, and are
enforced through `doc_events`, so they hold for the Desk form, `/api/resource`,
`/api/method` and Data Import alike. Explicitly approved quarantine and QC
movements were already permitted (`_is_permitted_quarantine_movement`), with
moving stock *out* of the rejected warehouse restricted to one role.

### What this phase added

| Gap | Now |
|---|---|
| The app never *created* a Quality Inspection | `quality/inspection.create_inspection` |
| No incoming / in-process / finished distinction | `STAGES`, mapped to ERPNext's own `inspection_type` |
| Templates were never carried | ERPNext fills `readings` from the item's template; only values are applied here |
| History showed accepted inspections only | `get_inspections` returns every verdict |

### Design decisions

**No limit is written in this app.** Parameters, minimum and maximum values and
acceptance formulas live in a Quality Inspection Template the plant configures.
An item without one cannot be inspected and says so; a reading for a parameter
the template does not define is **refused**, not appended, because appending it
would let an inspection assert a limit nobody configured. Inventing a moisture
ceiling or a plate count would be a food safety claim this app has no standing
to make.

**ERPNext fills the readings.** `doc.insert()` triggers ERPNext's own template
copy; this module only writes measured values onto the rows it produced.
Reimplementing that copy is how the two drift apart.

**v16 forced a better design.** `reference_type`, `reference_name` and
`sample_size` are mandatory on a Quality Inspection. That is the right
constraint — an inspection is always *of* something — so they are required
arguments rather than optional ones, and `STAGE_REFERENCES` keeps a
finished-product check from being filed against a purchase receipt.

**The history is not a record of good news.** `get_batch_context` filtered
inspections to `status = "Accepted"`, which hid the single most relevant fact
before a decision. It now returns every inspection with its verdict and
docstatus.

**Evidence reuses the framework.** `FM Batch Release.evidence` is an `Attach`
field and Quality Inspection carries `remarks` plus standard Frappe
attachments. No parallel evidence table was added.

### Not covered

- **NOT RUN:** HTTP round-trip; permissions are exercised in-process through
  the same `has_permission` path.
- **NOT RUN:** `ruff` — absent from this bench.
- The release gate still matches an accepted inspection by item and batch only;
  it does not yet require the inspection's *stage* to suit the decision. Worth
  deciding deliberately rather than inferring.
- No console UI for raising an inspection yet.

### Handoff for review

- `food_manufacturing/quality/inspection.py` — raise, read and list
- `food_manufacturing/api/quality.py` — `raise_inspection`,
  `get_inspection_readings`, and the widened `get_batch_context`
- `food_manufacturing/tests/test_quality_inspection.py` — 16 acceptance tests

Worth a second look at: whether `STAGE_REFERENCES` should allow `Job Card` for
a finished-product check on a packing line, and whether release should require
an inspection whose stage matches the batch's position in the process.

---

## Phase 4 — Batch traceability

Status: **implemented**. 10 new tests. Full suite **301 passing**
(287 integration + 14 unit), no regressions.

### What was already there

The trace engine predates this phase and already does most of what the brief
asks. `production/genealogy.py` and `api/recall.py` walk forward and backward
from a lot through consumed ingredients, blends, pack batches and deliveries,
and they already:

- read **both** v16 batch allocation structures — the `Serial and Batch Bundle`
  *and* the legacy `batch_no` on the ledger entry;
- filter `is_cancelled = 0` and `docstatus = 1`, so a cancelled movement never
  appears and the evidence is submitted transactions, never BOM theory;
- keep returns **negative** rather than netting them away, so recovered stock is
  distinguishable from shipped stock;
- bound the walk and report `truncated` rather than quietly stopping;
- re-check permission on every batch, item and delivery, refusing the whole
  trace rather than silently returning a partial one.

### What this phase added

| Gap | Now |
|---|---|
| The trace named the batches but not **where they are** | `recall._on_hand`, per batch and warehouse |
| No investigation artifact | `FM Recall Investigation`, a Script Report |

**Where the stock is** is read from the ledger via `get_batch_balances`, not
from `Batch.batch_qty`, so a split or part-consumed lot reports what is actually
in each warehouse. A warehouse holding none of it is dropped — an empty
warehouse is not a place to go and look.

**The report is a Desk artifact**, because an investigation gets filtered,
printed, exported and attached to a file an auditor reads months later. It is
built from the same permission-scoped trace the console uses, so it cannot show
a batch, delivery or company the reader could not open directly. It can be
narrowed to affected batches, stock on hand, or deliveries.

**Nothing is notified.** The report's own message says so: telling customers is
a decision with legal and commercial weight, and this says who to contact.

### Not covered

- **NOT RUN:** HTTP round-trip; **NOT RUN:** `ruff`.
- The report is not yet surfaced in the `/fm` console — it is a Desk report.
- Mixed-lot and split coverage is split across this file and
  `test_operator_guards_unit.py`; it is not consolidated.

### Handoff for review

- `food_manufacturing/api/recall.py` — `_on_hand`
- `food_manufacturing/food_manufacturing_quality/report/fm_recall_investigation/`
- `food_manufacturing/tests/test_recall_investigation.py` — 10 tests

Worth a second look at: whether the depth limit of 6 is right for a plant that
blends a blend, and whether `on_hand` should include stock in transit.

---

## Phase 5 — Role-based dashboards

Status: **not started.**
