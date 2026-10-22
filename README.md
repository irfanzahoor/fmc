# Food Manufacturing

Spice and masala manufacturing on ERPNext: supplier lots, approved recipes, bulk
blending, packaging into multiple pack sizes, and batch traceability from
supplier lot to customer.

Built on standard ERPNext purchasing, inventory, manufacturing, sales and
accounting. This app adds the food-manufacturing rules that ERPNext does not
model; it does not duplicate stock ledgers, valuation, invoices or payments.

## Compatibility

Matched majors only — Frappe and ERPNext must be on the same major version.

| Target | Frappe | ERPNext | Status |
|---|---|---|---|
| v16 | 16.52.0 | 16.27.0 | **active target, verified** |
| v15 | 15.118.0 | 15.119.0 | out of scope — no support claimed |

Version differences are isolated in `food_manufacturing/compat/`.

## Operator UI

A Vue 3 + frappe-ui SPA at `/fm`: a plant-overview dashboard plus four operator screens —
production console, quality release queue, goods in, and dispatch with FEFO picking. See `docs/workflows.md` for the routes, the
security model and the build steps.

## Demo data

```bash
bench --site <site> execute food_manufacturing.demo.seed.create_demo_data
```

Seeds the acceptance scenario as real documents — supplier lots, QC decisions, an approved
recipe, three blends, two pack sizes and a dispatch. Namespaced `FM Demo`, idempotent, and
removable with `remove_demo_data`. See `docs/workflows.md` for the caveats.

## Status

All seven milestones plus the operator UI implemented and verified on v16: **204 tests
passing**, and the dashboard has been rendered and reviewed at desktop and phone widths. The
representative acceptance scenario runs end to end against real ERPNext stock. See
`docs/tasks.md` for what is still owed before a pilot.

The newer [operator reliability changes](docs/operator-improvements.md) have passed
local unit/build/browser checks; their v16 database integration and concurrency
checks are wired into CI and still need a CI run.

## Documentation

- [UI designs and Claude handoff](docs/ui-design/README.md) — Stitch references for the planned redesign (6 desktop and 3 mobile screens)
- `docs/PRD.md` — scope and assumptions
- `docs/data-model.md` — standard-feature reuse map and custom DocTypes
- `docs/workflows.md` — operational flows
- `docs/operator-improvements.md` — QC guards, stock UOM picking, safe retries, scanners and recall
- `docs/compatibility.md` — version matrix and cross-version risks
- `docs/acceptance.md` — acceptance criteria per milestone
- `docs/tasks.md` — milestone status
- `CLAUDE.md` — development standards for this repository

## License

MIT
# fmc
