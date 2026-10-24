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

Status: **implemented**. 15 tests. Full suite **316 passing**
(302 integration + 14 unit), no regressions.

### What it does

| Role | Panels |
|---|---|
| Owner | Production · **Cost variance** · Stock and quality |
| Production | Work queue · Output |
| Quality | Decisions waiting · Inspections |
| Stores | Goods in · Shortages · Near expiry |

`/fm/workspace` in the console, plus `api/dashboards.get_dashboard` and
`available_views`.

### Design decisions

**Every metric links to its source records.** A number nobody can open is a
number nobody can act on — and, worse, one nobody can check. Each metric
carries `{doctype, filters}` naming exactly the rows behind it, and the console
renders that as a filtered Desk list. The dashboard is an index into the ledger
rather than a claim about it.

**A link this account cannot follow is dropped, not shown.** `_link` returns
`None` when the reader has no read permission on the DocType, so there is no
affordance that refuses on click.

**The production dashboard does not borrow the plant one.** It first reused
`api/dashboard.get_dashboard`, which also counts pending QC and near-expiry
batches — so a line operator's own dashboard refused on documents their job
does not involve. It now computes only production figures. That also made it
**13× faster** (36.7s → 2.8s for the suite).

**Cost variance is the two halves meeting.** `costing/simulator.py` said what a
batch should cost and the ledger said what it did; they never met.
`costing/variance.py` compares the BOM's cost scaled to what was produced
against the Manufacture entry's outgoing value. A run whose BOM carries no cost
has **no estimate** — it reports `None` and is excluded from the totals, and the
panel says how many of the runs could actually be costed. A run with no estimate
is unmeasured, not on plan.

**An unmeasured figure is an em dash, never a zero.** Carried through from the
existing dashboards.

**`available_views` is a landing hint, not a boundary.** It picks the dashboard
that fits the account's roles; the endpoints re-check permission regardless.

### Not covered

- **NOT RUN:** HTTP round-trip; **NOT RUN:** `ruff`.
- Panels carry a `rows` payload the console does not render yet — the metric
  row is built, the supporting tables are not.
- "Material readiness" on the production dashboard counts runs without a
  shortfall flag; it does not yet re-run the packaging planner per work order.
- Verified by rendering the harness at 1440 and 390 with mocked data; **not yet
  rendered against a live session.**

### Handoff for review

- `food_manufacturing/api/dashboards.py` — four dashboards, linked metrics
- `food_manufacturing/costing/variance.py` — estimated vs actual
- `frontend/src/pages/RoleDashboard.vue`, `components/MetricCard.vue`
- `food_manufacturing/tests/test_role_dashboards.py` — 15 tests

Worth a second look at: whether "Ready to start" should call the packaging
planner per run rather than reading a flag, and whether the Owner dashboard
should scope to companies the reader has a User Permission for rather than one
at a time.

---

## All five phases complete

| Phase | Tests | Status |
|---|---|---|
| 1 Recipe cost simulator | 17 | done |
| 2 Packaging material planning | 17 | done |
| 3 Quality hold and release | 16 | done |
| 4 Batch traceability | 10 | done |
| 5 Role-based dashboards | 15 | done |

**316 tests passing** on Frappe 16.52.0 / ERPNext 16.27.0.

Carried forward across all phases: fresh-install verification **NOT RUN** (no DB
root), two-process concurrency **NOT TESTED**, `ruff` **NOT RUN** (absent from
this bench), and no HTTP round-trip test for the new endpoints.


---

## Branding and Desk presence (2026-10-23)

The app had no icon and a single generic workspace. It now presents the way
`realestate` does on this bench, which was the reference.

| Piece | Where |
|---|---|
| App icon | `public/images/batchwell-logo.svg` — a filled batch container, geometry only so it reads at 24px |
| Apps screen tile | `add_to_apps_screen` in `hooks.py`, gated by `api/permission.has_app_permission` |
| Icon rail | `dock/food_manufacturing/` — four panes |
| Pane contents | a `Sidebar` record per module, under each module's `sidebar/` folder |
| Landing pages | four `Workspace` records: Batchwell, Quality, Costing, Setup |

### What the reference taught

**The rail is a `Dock` record pointing at `Sidebar` records, not at Workspaces.**
A Workspace entry gives the pane the *module's* name as its header — so the app
read "Food Manufacturing Setup". A Sidebar entry supplies its own header and
link list.

**The pane header renders the Sidebar's `name`, not its `title`.** Realestate's
are identical, which hid the difference; each Sidebar here is named as a phrase
(`Batchwell Plant`) rather than a bare word, so nothing collides with another
app's and the header still reads well.

**The landing route follows the workspace's module.** `/app/batchwell` opened
the Setup pane until the workspace moved to `Food Manufacturing Production`.

**The workspace rename needed a patch.** A Workspace's record name is its
primary key, so the sync created `Batchwell` and left `Food Manufacturing`
behind — two sidebar entries, one stale. `patches/v0_3/rename_workspace_to_batchwell`
removes the old one, and only once the new one exists, so a half-finished
migrate never leaves the app with no entry at all.

**A fixture is re-imported only when its file is newer than the record.** Every
content change here needed its `modified` stamp moved with it.

`app_title` is now `Batchwell`; `app_name`, the module names and every import
path are unchanged, so existing installs, fixtures and code keep working. The
console's own mark uses the same SVG, so the Desk and `/fm` read as one product.

**NOT RUN:** `ruff`. Verified by rendering against a live session at 1440px with
a temporary user, created and deleted.


---

# Batchwell UI programme (2026-10-24)

## Audit

Stack is already Vue 3 + frappe-ui 0.1.248 + Tailwind 3.4.15 + vue-router 4,
all pinned, served at `/fm`; Desk administration untouched. Frappe 16.52.0 /
ERPNext 16.27.0. No TypeScript, and no migration attempted — the brief allows
TS only where practical without a broad change, and nothing here needed it.

Two defects found during the audit:

1. **A fabricated figure on a live screen.** The owner dashboard's "Ready to
   start" filtered `get_production_queue` on a `shortfall` key that endpoint
   has never returned, so *every* open run counted as ready. Removed and
   replaced with a measured shortage count.
2. **The default theme was Midnight Blue**, not the forest green the product
   is branded on.

## Phase 1 — shell and owner dashboard · **DONE**

### Branding

Forest green with a restrained gold accent. Every value measured, not picked:

| Role | Hex | Contrast |
|---|---|---|
| Primary | `#1f6b51` | 6.40:1 on white; white on it 6.40:1 |
| Soft | `#e8f2ed` | primary on it 5.60:1 |
| Sidebar | `#102a21` | side ink `#c3d8cd` 10.20:1 |
| Hero | `#163a2d` | white on it 12.52:1 |
| Accent | `#a1711a` | 4.29:1 on white — marks and borders, never body text |
| Accent on gold chip | `#8a6016` | 5.04:1 on `#faf3e2` |
| Accent on hero | `#d4a24a` | 5.41:1 (`#a1711a` would be 2.92:1 there) |

Gold is held constant across all five themes, the way the status colours are, so
a Batchwell screen is recognisable in any palette. Chart colours are unchanged
and still the validated set.

### Exceptions, computed from records

`api/exceptions.py` returns three lists, each row carrying what it links to:

- **Material short** — required less transferred less consumed, against
  `Bin.actual_qty` in the run's own source warehouse, scoped to the company's
  warehouses so a shortage is never judged against someone else's stock.
- **Quality holds** — delegated to `get_release_queue`, which already filters to
  batches holding stock in this company; duplicating that rule is how the two
  drift apart.
- **Delayed runs** — open runs past `planned_end_date`, with days late.

The owner dashboard leads with these, and the shortage rows name the ingredient,
how short it is and which warehouse was checked. "This run is short" is not
actionable; "Red Chilli Powder short 246 Kg (54 of 300 in Stores)" is.

A panel now declares the `kind` of rows it carries. Without that the client
rendered cost-variance rows through the shortage template and printed
"and 126354.45999999999 more runs short of material" — caught by rendering it.

### Checks

| Check | Result |
|---|---|
| Full test suite (325) | **PASS** |
| New exception tests (8) | **PASS** |
| Owner dashboard, live session, 1440px | **PASS** — rendered and inspected |
| Owner dashboard, 390px | **PASS** — rendered and inspected |
| Shortage template with data (harness) | **PASS** — rendered and inspected |
| Contrast of every brand token | **PASS** — measured |
| `ruff` | **NOT RUN** — not installed in this bench |
| HTTP round-trip of `get_exceptions` | **NOT RUN** — exercised in-process |

### Gaps carried into later phases

- The period selector is still a static pill; it does not filter.
- `Stores` and `Quality` panels still carry no row detail, only counts.
- No confirmation dialogs on consequential actions yet (Phase 5).


## Phase 2 — Production workspace · **DONE**

| Requirement | Where |
|---|---|
| Searchable list with filters and clear statuses | `get_production_queue(search, status, limit, start)` |
| Material availability | `short_items` / `material_ready` per row; per-ingredient `outstanding_qty`, `available_qty`, `short_qty` in the detail |
| Progress | percent complete on each card |
| Clear primary action for the stage | `next_action` on the detail, decided server-side |
| kg/g and pack conversions explicit | unit shown beside every quantity; detail reads the UOM from the Item |

### Design decisions

**Search and paging happen in the query**, not in the browser. A plant with two
thousand open runs should not ship two thousand rows so the client can hide most
of them. The box is debounced at 300 ms — a request per keystroke answers one
question five times, and the answers can arrive out of order.

**Availability reuses `api/exceptions`** rather than re-deriving it. Two answers
to "is this run short" is one too many.

**The stage action is decided on the server.** A button that disagrees with the
rule behind it is worse than no button, so `next_action` carries the label,
whether it is enabled, and why not. A blocked action stays **visible and
disabled with its reason** rather than hidden — hiding it leaves an operator
hunting for a button that was there yesterday.

**Readiness appears where the run is chosen**, not only after opening it: the
queue card says "Short of 2 ingredients".

**The filter row sits outside the state block**, so an empty result still leaves
you the means to change it.

### Checks

| Check | Result |
|---|---|
| Full suite (335) | **PASS** |
| New production-workspace tests (10) | **PASS** |
| Production screen, harness, 1440px | **PASS** — rendered and inspected |
| `ruff` | **NOT RUN** |
| Live-session render of the new filters | **NOT RUN** — harness only this phase |


## Phase 3 — Recipe costing and packaging · **DONE**

The engines existed from the earlier programme (`costing/simulator.py`,
`costing/pricing.py`, `packaging/planning.py`). What was missing was a screen.
`/fm/costing` is that screen; **no calculation was invented for it**.

| Requirement | Where |
|---|---|
| Estimated vs posted cost, clearly distinguished | A gold banner states it before any figure, and `assumptions[0]` repeats it |
| Ingredient, packaging and operating breakdown | Four cards plus a line table carrying each rate's **source** |
| Packaging requirements and shortages in a table | Material · Required · Free stock · Requested · Expected · Short |
| No invented calculations or availability | Every number comes from an endpoint that already existed |

### Design decisions

**The estimate/actual distinction leads.** It is the thing the brief turns on,
so it is stated above the figures rather than footnoted below them.

**Every rate shows where it came from** — "Moving-average valuation, as costed
on this BOM" — because a cost nobody can trace is a cost nobody can argue with.

**The formula stays gated.** A caller without permlevel-1 read on `FM Recipe`
sees the totals and a plain explanation instead of the ingredient lines; the
screen reflects what the server returned rather than deciding for itself.

**Free stock is named, not implied.** The table separates what is on hand less
commitments, what is already requested and what is expected, with a footnote
saying why: planning the same run twice must not request it twice.

**The pack picker opens on a real pack.** `get_packs_for` reads the
`fm_bulk_item` link the Item already carries — nothing is inferred about which
SKUs a blend fills — and the screen selects the first rather than opening on
"None", which made the planner look broken.

### Checks

| Check | Result |
|---|---|
| Full suite (336) | **PASS** |
| New pack-picker test | **PASS** |
| Costing screen, harness, 1440px | **PASS** — rendered and inspected |
| `ruff` | **NOT RUN** |
| Live-session render | **NOT RUN** — harness only this phase |
| "Propose Material Request" button | **NOT BUILT** — the endpoint exists and is wired into `api.js`; the button is Phase 5, with its confirmation |


## Phase 4 — Quality and traceability · **DONE**

| Requirement | Where |
|---|---|
| Queue with pending, held, approved and rejected | `QUEUE_STATUSES`; chips read Awaiting · Quarantine · Hold · Released · Rejected |
| Prominent hold/release information and authorised actions | Unchanged: status chip, shelf-life meter, matching inspection, decision form; permission is `FM Batch Release` create, enforced by the framework |
| Batch detail showing linked materials, production, quality and dispatch | `get_batch_trail` — "Linked records" |
| Actual transaction links | Every row is a document name with a Desk link |
| Restrictions enforced server-side | Unchanged `doc_events`; this phase added only reads |

### Design decisions

**The queue can be looked back through.** It filtered to Quarantine and Hold
only, so a decision log existed that nobody could read. Pending is still the
default — that is what needs doing — but Released and Rejected are a chip away,
and a decided list sorts newest-first because that is how a log is read, where
a pending list sorts oldest-first because that is who has waited longest.

**The trail reuses the recall engines.** `trace_backward`,
`get_producing_work_orders` and `get_recall` already existed; building a second
query would let the quality screen and the recall report disagree about the
same batch.

**One captioned list, not three headings.** The question is "what else touches
this batch"; the caption answers "in what way" — *produced by this run*,
*consumed · supplier lot SV-261001*, *returned by Apex Retailers · 24 Nos*.

**A trail that cannot be read does not block the decision.** It is fetched
beside the context and swallowed on failure, so a reader without delivery
access can still release a batch.

### Checks

| Check | Result |
|---|---|
| Full suite (344) | **PASS** |
| New trail/queue tests (8) | **PASS** |
| Quality screen, harness, 1440px | **PASS** — rendered and inspected |
| `ruff` | **NOT RUN** |
| Live-session render | **NOT RUN** — harness only this phase |
