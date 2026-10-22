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

## Status

All seven milestones implemented and verified on v16: **178 tests passing**. The
representative acceptance scenario runs end to end against real ERPNext stock. See
`docs/tasks.md` for what is still owed before a pilot.

## Documentation

- `docs/PRD.md` — scope and assumptions
- `docs/data-model.md` — standard-feature reuse map and custom DocTypes
- `docs/workflows.md` — operational flows
- `docs/compatibility.md` — version matrix and cross-version risks
- `docs/acceptance.md` — acceptance criteria per milestone
- `docs/tasks.md` — milestone status
- `CLAUDE.md` — development standards for this repository

## License

MIT
# fmc
