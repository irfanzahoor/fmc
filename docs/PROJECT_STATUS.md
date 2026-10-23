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

Status: **not started.**
