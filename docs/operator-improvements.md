# Operator reliability and recall improvements

Implemented in October 2026. These changes target Frappe/ERPNext v16.

## Quality decisions

When the company policy requires incoming inspection, a release needs a submitted,
Accepted Quality Inspection with the same `item_code` and `batch_no`. Existing
item-only inspections must be replaced or completed with their actual batch before
release. Both the Desk selector and operator queue show matching inspections.

Only the current quality decision can be cancelled. New decisions store a link to
the actual preceding decision, so cancelling a Release after a Hold restores the
Hold and its decision pointer. Historical decisions without that link use the
existing decision history as a fallback.

## Picking and quantities

The dispatch API's allocation quantities are **stock UOM quantities**. Two cartons
of 24 packs require 48 packs from the available batches. The Delivery Note retains
the Sales Order's sales UOM and conversion factor; its sales quantity becomes 2.

Suggestions exclude batches below the company's remaining-shelf-life floor. FEFO
validation considers the total stock quantity across split rows, so adding a token
quantity from an early batch cannot hide an otherwise late pick. Suggestions across
repeated order lines share the same available balance.

Production and dispatch load item/warehouse batch availability in bulk. Balances
read standard ERPNext stock ledger and bundle entries and account for outstanding
batch reservations and unconsolidated POS postings. ERPNext's own submit-time
stock checks remain authoritative; a suggestion does not reserve stock.

QC pagination happens after company-stock filtering. The queue has Previous/Next
controls; badge and overview totals include every qualifying batch.

## Safe retries

Receiving, production completion and dispatch accept an optional `request_id`.
The operator UI creates one per payload, retaining it in session storage until a
response is confirmed. Retrying an unchanged request returns the original posting.
Reusing an ID with changed values, or after cancellation, is refused.

Source rows are locked for the request transaction. Operation keys, payload hashes
and results are stored on the standard Purchase Receipt, Stock Entry or Delivery
Note using hidden `fm_` custom fields. No parallel stock or payment document is
introduced. Replays recheck source and result-document permissions.

After a timeout, retry the unchanged form before starting a different posting.
Storage-disabled browsers retain retry keys only while the page remains open.

## Scanners and recall

USB/Bluetooth scanners configured as keyboard input can enter supplier lots in Goods
In. Their Enter key does not submit a receipt. Dispatch's Scan Batch field focuses
the matching available batch's quantity input. Recall accepts a scanned batch ID.
Camera scanning and GS1 payload parsing are outside this implementation; encode the
exact existing batch ID or supplier lot text.

`/fm/recall` walks a batch through consuming Work Orders to manufactured output and
customer deliveries. It scopes ledger movements by company and checks read access
to affected batches, stock entries, Work Orders and Delivery Notes. Split bundles
count only each affected batch's quantity; returns are displayed as negative stock
quantities and cancelled movements are excluded. A six-level/200-batch traversal
limit displays an explicit incomplete-result notice. The screen is read-only;
placing affected batches on Hold still uses the audited quality decision flow.

## Installation and verification

From the v16 bench, after pulling these changes:

```sh
bench --site <site> migrate
bench build --app food_manufacturing
cd apps/food_manufacturing/frontend
yarn install --frozen-lockfile
yarn build
```

Migration creates the operation metadata and previous-decision field. Run the app's
integration suite on a dedicated v16 site, not a populated shared site:

```sh
bench --site <test-site> run-tests --app food_manufacturing
```

The CI workflow creates `ci.localhost`, opts in with `fm_isolated_test_site`, and
creates its two company fixtures there. The setup refuses every other site. After
the regular suite, two independent DB processes test identical request retries and
competing Work Orders consuming the same remaining batch stock; a barrier starts the operations together. The harness
commits real stock fixtures and leaves them for inspection; discard the CI site
when finished. Never enable this flag on a shared site.

```sh
bench --site ci.localhost set-config fm_isolated_test_site true
bench --site ci.localhost execute food_manufacturing.tests.ci_setup.prepare
bench --site ci.localhost execute food_manufacturing.tests.concurrency.run
```

Local verification during implementation: 14 database-free regression tests passed
using the available Frappe installation, Python compilation passed, and the operator
frontend built successfully. Browser checks with mocked API responses passed for
scanner focus, stock-UOM suggestions, QC pagination and recall at phone width, with
no JavaScript errors. A v16 bench/database is not available in the local
workspace, so v16 integration and two-process stock results require the CI run.

## Changed-file map

| File | Purpose and placement |
| --- | --- |
| `api/dispatch.py` | Sales-to-stock UOM conversion, eligible suggestions, shared allocation balance and retry hook in the dispatch API. |
| `api/production.py` | Bulk lot lookup, current Work Order row lock and retry hook in the production API. |
| `api/receiving.py` | Retry hook around standard Purchase Receipt creation. |
| `api/quality.py` | Same-batch inspection choices, company-scoped queue pagination and full counts. |
| `api/dashboard.py` | Overview QC count includes the complete queue. |
| `api/idempotency.py` | Shared transactional API retry wrapper. |
| `api/recall.py` | Permission-checked, company-scoped batch traversal and delivery quantities. |
| `dispatch/fefo.py` | Bulk candidates and quantity-aware eligible FEFO enforcement. |
| `stock_levels.py` | Grouped standard-ledger balances and reservation reads shared by callers. |
| `doctype/fm_batch_release/fm_batch_release.py` | Inspection matching and cancellation rules belong on the owned DocType controller. |
| `doctype/fm_batch_release/fm_batch_release.js` | Inspection selector UX extends the owned form's existing handlers. |
| `doctype/fm_batch_release/fm_batch_release.json` | Persistent previous-decision link on the owned DocType. |
| `setup/custom_fields.py` | App-owned metadata extends ERPNext posting documents without editing core. |
| `patches/v0_2/operator_retry_fields.py` | Idempotent metadata creation on existing installations. |
| `patches.txt` | Registers the migration. |
| `tests/test_batch_release.py` | Integration regressions for cancellation order and status restoration. |
| `tests/test_operator_guards_unit.py` | Database-free guard, UOM, pagination, reservation, recall and retry regressions. |
| `tests/ci_setup.py` | Company provisioning restricted to the disposable CI site. |
| `tests/concurrency.py` | Separate-process retry and shared-batch consumption checks on the disposable site. |
| `frontend/src/data/api.js` | Stable client request IDs survive uncertain responses. |
| `frontend/src/pages/Dispatch.vue` | Stock-UOM labels, scanner focus and repeat-submit guard. |
| `frontend/src/pages/Receiving.vue` | Scanner-friendly lot entry and repeat-submit guard. |
| `frontend/src/pages/ProductionConsole.vue` | Prevent repeated submission of a completed operation. |
| `frontend/src/pages/QualityQueue.vue` | Previous/Next company-stock queue controls. |
| `frontend/src/pages/Recall.vue` | Operator recall lookup and delivery/return display. |
| `frontend/src/router.js` | Registers `/fm/recall`. |
| `frontend/src/App.vue` | Adds recall navigation. |
| `.github/workflows/ci-v16.yml` | Python 3.14, frontend build, isolated company setup and two-process checks. |
| `README.md` | Documents the new features and verification status. |
| `docs/tasks.md` | Replaces stale next-milestone text and records pending v16 verification. |
| `docs/operator-improvements.md` | Behavior, installation steps, test limits and this file map. |

Backend paths above are relative to `food_manufacturing/`; the owned batch-release
DocType lives under `food_manufacturing_quality/`.
