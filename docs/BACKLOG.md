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

### 3. The suite is order-dependent and flakes
- **What:** two tests have been seen to fail in a full run and pass in
  isolation — `test_a_deactivated_bom_cannot_be_costed` (fixed: it now restores
  `is_active` in a `finally`) and
  `test_cancel_chain_restores_the_actual_previous_decision` (**still flaky**,
  seen once on 2026-10-24, passed on re-run).
- **Why it matters:** a flaky suite trains people to re-run instead of read, and
  the next real regression gets re-run away with it.
- **Likely cause:** tests share one long-lived site, so a fixture that mutates a
  record another test later selects leaks between them.
- **Done when:** the full suite passes ten consecutive runs, or the leak is
  found and the fixture isolated.

### 4. Two-process concurrency is untested
- **What:** acceptance 4.7. The retry keys, the `for_update` row locks and the
  idempotency fingerprints are all written for contention that has never been
  reproduced — the suite is single-process.
- **Why it matters:** two operators posting the same receipt, or two planners
  requesting the same shortfall, is the exact case the locks exist for.
- **Done when:** a test spawns two processes that race the same operation and
  asserts exactly one posting.

---

## P2 — Visible to users

### 5. The period selector does not filter
- **What:** "Last 30 days" on the Overview and Insights pages is a static pill.
  The role dashboard's selector *does* work.
- **Why it matters:** a control that looks interactive and is not is worse than
  no control.
- **Done when:** it changes `days` and reloads, or it stops looking like a
  control.

### 6. Stores and Quality dashboard panels show counts without rows
- **What:** only the owner's "short of material" panel renders row detail.
  `panel.kind` exists for exactly this and is unused by the others.
- **Why it matters:** a count tells you there is a problem; the rows tell you
  which one.
- **Done when:** near-expiry and pending-inspection panels render their rows.

### 7. The Desk workspace is not reachable from the console
- **What:** `FM Recall Investigation` is a Desk report with no link from `/fm`.
- **Done when:** the Recall screen links to it for the full trace.

### 8. The HTML prototype's remaining details
- Fullscreen button in the topbar.
- Circular progress ring on the production detail card.
- **Receiving, Dispatch and Recall were never compared screen-by-screen**
  against the prototype; only Overview, Production, Insights and Quality were.

---

## P3 — Correctness worth hardening

### 9. The release gate ignores the inspection's stage
- **What:** releasing a batch matches an accepted Quality Inspection by item and
  batch, but does not require its stage to suit the decision — an *Incoming*
  check can release a finished pack.
- **Why it matters:** it is a food-safety control that is weaker than it looks.
- **Done when:** decided deliberately — either the stage is enforced, or the
  docs say plainly that it is not.

### 10. "Ready to start" relies on a flag, not the planner
- **What:** the production dashboard counts runs without a shortage flag rather
  than re-running the packaging planner per work order.
- **Done when:** either it runs the planner, or the metric is renamed to what it
  actually measures.

### 11. The cost simulator's `docstatus` guard has no test
- **What:** this bench submits a BOM on insert and cancelling is blocked while
  the recipe links to it, so the fixture cannot reach a draft or cancelled BOM.
  Deactivation *is* covered.
- **Done when:** a fixture can produce one, or the guard is proven another way.

### 12. No HTTP round-trip tests for the newer endpoints
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

## Verification standing

| Check | State |
|---|---|
| Test suite (347) | **PASS** |
| Live-session render, desktop and phone | **PASS** for Overview, Production, Quality, Costing, Workspace |
| Brand contrast | **PASS** — measured, all AA |
| Chart palette | **PASS** — validator run, all surfaces |
| `ruff` | **NOT RUN** (point 1) |
| Fresh install | **NOT RUN** (point 2) |
| Concurrency | **NOT TESTED** (point 4) |
| Keyboard-only walkthrough | **NOT RUN** — focus order read and photographed, not driven |
