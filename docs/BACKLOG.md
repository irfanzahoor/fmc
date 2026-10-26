# Batchwell — open points

Everything known to be unfinished, in one place, so nothing lives only in a
commit message. Each point says what it is, why it matters and what "done"
means. Updated 2026-10-24.

Ordered by what would hurt most if it stayed unfixed.

---

## P1 — Blocks a pilot

### 1. `ruff` has never run on this code
- **What:** `.pre-commit-config.yaml` declares `ruff`, but it is not installed
  in this bench. Every phase has shipped with lint **unverified**.
- **Why it matters:** the repository's own standards assume it runs. Unused
  imports, shadowed names and unreachable branches would all pass unnoticed.
- **Done when:** `ruff check` and `ruff format --check` run clean across the
  app, and are part of the pre-push routine.
- **Blocker:** needs `pip install ruff` in the bench environment.

### 2. Fresh-install verification has never run
- **What:** every migration has been applied to one long-lived site. A brand
  new site has never been installed from scratch.
- **Why it matters:** the install path is the one every customer takes.
  Module-def ordering, custom-field creation and workspace sync have all
  needed fixes before; nothing proves they work in sequence on an empty DB.
- **Done when:** `bench new-site` → `install-app food_manufacturing` →
  `migrate` → full test suite, all green, on a throwaway site.
- **Blocker:** no database root credentials on this machine.

### 3. CI runs 15 of the 347 tests

- **What:** `bench run-tests --app food_manufacturing` discovers only
  `tests/test_operator_guards_unit.py` — 15 tests. It reports "Running 15
  unspecified-category tests for food_manufacturing" and exits OK. Every other
  module passes when named directly with `--module`, so the tests are fine; the
  discovery is not. `.github/workflows/ci-v16.yml` line 135 uses exactly that
  `--app` form.
- **Why it matters:** CI has been reporting green while exercising 4% of the
  suite. Any regression outside operator guards would merge unnoticed. The 347
  figure quoted in the README, `PROJECT_STATUS.md` and the capability document
  has only ever been true of a module-by-module run.
- **Verified on:** 2026-10-24, site `steps_erp.local`, Frappe 16.52.0. Looping
  over the 30 `test_*.py` files with `--module` gives 347 tests, 30 modules OK.
- **Likely cause:** v16 discovers app tests through the module folders listed in
  `modules.txt`; `food_manufacturing/tests/` is not one of them, so only
  whatever the runner picks up incidentally runs.
- **Done when:** a single command runs all 347, and CI uses it. Either move the
  tests under the declared modules, or replace the CI step with the module loop
  and assert the expected count so a silently-shrinking suite fails the build.

### 4. The suite is order-dependent and flakes
- **What:** two tests have been seen to fail in a full run and pass in
  isolation — `test_a_deactivated_bom_cannot_be_costed` (fixed: it now restores
  `is_active` in a `finally`) and
  `test_cancel_chain_restores_the_actual_previous_decision` (**still flaky**,
  seen once on 2026-10-24, passed on re-run).
- **Why it matters:** a flaky suite trains people to re-run instead of read, and
  the next real regression gets re-run away with it.
- **One leak found and closed (2026-10-24):** `fixtures.cleanup()` deleted the
  test Items but not their child rows. Re-creating an Item of the same name left
  it with two `Item Default` rows, and ERPNext's `get_bom_items_as_dict` joins
  that table without de-duplicating, so every Work Order requirement read double
  — then triple on the next run. Measured: the same recipe needing 60 kg, then
  120 kg, then 180 kg on three consecutive runs. `cleanup()` now deletes the
  child rows of every Item it removes. Whether this was *the* cause of the
  cancel-chain flake is unproven; it was certainly **a** cause of
  order-dependence, and the figures it corrupted are the ones several tests
  assert on.
- **Done when:** the full suite passes ten consecutive runs, or the remaining
  leak is found and the fixture isolated.

### 5. Two-process concurrency is untested
- **What:** acceptance 4.7. The retry keys, the `for_update` row locks and the
  idempotency fingerprints are all written for contention that has never been
  reproduced — the suite is single-process.
- **Why it matters:** two operators posting the same receipt, or two planners
  requesting the same shortfall, is the exact case the locks exist for.
- **Done when:** a test spawns two processes that race the same operation and
  asserts exactly one posting.

---

## P2 — Visible to users

### 6. The period selector does not filter
- **What:** "Last 30 days" on the Overview and Insights pages is a static pill.
  The role dashboard's selector *does* work.
- **Why it matters:** a control that looks interactive and is not is worse than
  no control.
- **Done when:** it changes `days` and reloads, or it stops looking like a
  control.

### 7. Stores and Quality dashboard panels show counts without rows
- **What:** only the owner's "short of material" panel renders row detail.
  `panel.kind` exists for exactly this and is unused by the others.
- **Why it matters:** a count tells you there is a problem; the rows tell you
  which one.
- **Done when:** near-expiry and pending-inspection panels render their rows.

### 8. The Desk workspace is not reachable from the console
- **What:** `FM Recall Investigation` is a Desk report with no link from `/fm`.
- **Done when:** the Recall screen links to it for the full trace.

### 9. The HTML prototype's remaining details
- Fullscreen button in the topbar.
- Circular progress ring on the production detail card.
- **Receiving, Dispatch and Recall were never compared screen-by-screen**
  against the prototype; only Overview, Production, Insights and Quality were.

---

## P3 — Correctness worth hardening

### 10. The release gate ignores the inspection's stage
- **What:** releasing a batch matches an accepted Quality Inspection by item and
  batch, but does not require its stage to suit the decision — an *Incoming*
  check can release a finished pack.
- **Why it matters:** it is a food-safety control that is weaker than it looks.
- **Done when:** decided deliberately — either the stage is enforced, or the
  docs say plainly that it is not.

### 11. "Ready to start" relies on a flag, not the planner
- **What:** the production dashboard counts runs without a shortage flag rather
  than re-running the packaging planner per work order.
- **Done when:** either it runs the planner, or the metric is renamed to what it
  actually measures.

### 12. The cost simulator's `docstatus` guard has no test
- **What:** this bench submits a BOM on insert and cancelling is blocked while
  the recipe links to it, so the fixture cannot reach a draft or cancelled BOM.
  Deactivation *is* covered.
- **Done when:** a fixture can produce one, or the guard is proven another way.

### 13. No HTTP round-trip tests for the newer endpoints
- **What:** permissions are exercised in-process with `frappe.set_user`, which
  is the same `has_permission` path, but argument parsing over HTTP is only
  covered for the cost simulator.
- **Why it matters:** this is how the CSRF bug and the `Company` permission bug
  both reached a running app.
- **Done when:** one smoke test per endpoint group hits it over HTTP.

---

## P4 — Deliberately not built

These are decisions, not oversights. Listed so nobody re-litigates them by
accident.

| Point | Why |
|---|---|
| A dark theme | Every surface is light; a real dark mode needs a dark chrome palette **and** chart steps re-validated against it. Half of that is worse than neither. |
| FM roles reading standard ERPNext documents | The app deliberately does not widen access to Sales Orders, Purchase Orders or Work Orders through its own roles. Screens name the missing ERPNext role instead. |
| Customer notification on recall | Telling customers has legal and commercial weight. The report says who to call; the calling is a human decision. |
| Submitting the Material Request | A planner proposes, a buyer decides. Submitting on an operator's behalf would put purchasing authority behind a shop-floor button. |
| A packing-loss default | A plant's own measurement, not something this app should invent. Defaults to zero. |

---

## Closed by the server audit (2026-10-24)

Eight findings — five rules that could be stepped around, three wrong numbers —
are fixed, each with a test that fails without the fix. The table of what each
one was and what closed it is in
[PROJECT_STATUS.md](PROJECT_STATUS.md#server-audit--eight-findings-all-fixed-2026-10-24).
One carries an upgrade note: `quarantine_production_output` defaults to on, so a
manufactured blend or pack now needs a quality decision before it can be
consumed or dispatched.

## Closed by the code review (2026-10-26)

Seven findings from a review of the 2026-10-24 server-audit commit, each with a
test that fails without the fix.

| Finding | What closed it |
|---|---|
| The withheld formula was readable through `/api/resource/BOM Item?parent=BOM` and in BOM list queries | `overrides/bom.py` — a `permission_query_conditions` hook on `BOM` (which v16 also applies to its child rows) and a `has_permission` hook refusing print/email/export |
| `api/exceptions.py` quoted the same per-ingredient quantities with no recipe check | `_withhold_formulas`, the same field set `api/production.py` withholds; rows keep the shortage and stock on hand |
| **The material-shortage panel was empty for every non-Administrator** — `frappe.has_permission` on a child DocType without `parent_doctype` always returns False | `parent_doctype="Work Order"`; the old tests passed because they ran as Administrator |
| A UOM factor lookup per pack row inside `simulate()` | `conversion.get_conversions` resolves a whole set in three queries; the single-pair functions delegate to it |
| Cancelling a run left its batch in Quarantine for stock that no longer existed | `overrides/stock_entry.before_cancel` — before, because ERPNext clears `batch_no` as it cancels |
| A mistyped supplier manufacturing date shortened a batch's life irreversibly | `validate_supplier_dates` refuses a date whose shelf life had already ended before the material arrived |
| `fm_supplier_lot_no` was guarded, so a lot number mistyped on a submitted receipt could not be corrected anywhere | Removed from `overrides/batch.PROTECTED_FIELDS`; it gates nothing |
| `_output_rows` inferred the produced row from the shape of its warehouses, so it quarantined scrap | `is_finished_item`, with the old shape kept only for the case ERPNext leaves the flag unset |

Two reported findings were **withdrawn on inspection**, not fixed:

- Changing the Batch guard to raise `PermissionError` was wrong. Nobody may write those
  fields down that path — a System Manager is refused exactly as an operator is — so the
  refusal is a rule about the write, not a statement about the caller. It stays
  `ValidationError`, which is also the contract its tests already documented.
- Refusing a supplier date *after* the receipt was unnecessary: the dates only ever move
  earlier, so such a date is already ignored, and `test_a_supplier_date_never_makes_a_batch_look_fresher`
  documents that as deliberate.

### Open decision

Hiding recipe-generated BOMs from list and link queries means a Desk user without
recipe access cannot pick one when planning a Work Order. That is defensible —
planning a run of a confidential recipe is a recipe-level act — but it is a
site-policy call, and it is reversible by removing the `BOM` entry from
`permission_query_conditions` in `hooks.py`. Reading the BOM document and
`Work Order Item.required_qty` stay open either way; `docs/workflows.md` §2 says
why neither `permlevel` nor v16's `mask` can close them without breaking ERPNext.

## Verification standing

| Check | State |
|---|---|
| Test suite (399) | **PASS** — 2026-10-26, `--app` form, 384 + 15. |
| Live-session render, desktop and phone | **PASS** for Overview, Production, Quality, Costing, Workspace |
| Brand contrast | **PASS** — measured, all AA |
| Chart palette | **PASS** — validator run, all surfaces |
| `ruff` | **NOT RUN** (point 1) |
| Fresh install | **NOT RUN** (point 2) |
| Concurrency | **NOT TESTED** (point 5) |
| Capability document, page and PDF | **PASS** — 2026-10-24, three PDF pages and the page at 1100px and 390px all rendered and read |
| Handbook, 3 guides, pages and PDFs | **PASS** — 2026-10-24, all four routes rendered at 1280px and 620px, three PDFs rendered and read, unknown slug 404s |
| Keyboard-only walkthrough | **NOT RUN** — focus order read and photographed, not driven |
