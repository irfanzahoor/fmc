# FMC premium design direction

## Foundation

Warm ivory canvas `#F7F8F5`, white surfaces, pine text `#172E28`, forest actions
`#24634D`, sage selection `#EAF1E8`, secondary text `#738078`. Use amber/red only
for meaningful attention and blocked states, alongside readable words/icons.
Manrope/Inter typography; roughly 34px desktop headings, 28px phone headings,
38px main metrics, 14–15px readable data, and tabular quantities.

## Shared shell

216px white desktop sidebar, 72px company/context topbar, generous 24–32px
workspace spacing, light borders and 14px card corners. Phone uses compact brand
and company header plus six visible navigation destinations, stacked workspaces,
44px input/touch targets and labeled data cards. Shared rules live in `preview.css`.

## Workflows

Overview prioritizes three metrics, then production yield and stock status;
units remain separate. Production places work order selection beside the selected
run, available ingredient lots and completion form. Quality puts batch review
beside the queue and offers a matching inspection, notes and audited decision flow.
Goods in groups quantities, supplier lots and manufacturing dates per item.
Dispatch shows sales-to-stock conversion, FEFO eligibility and stock quantities.
Recall is a read-only batch-and-delivery investigation with negative returns and
an incomplete-result notice, using data the current API actually returns.

## Functional boundaries

References are visual concepts with example data. Keep actual server permissions,
company scoping, retries and batch policies. Scanner Enter must not post receipts;
dispatch scanning focuses the matching quantity. Suggestions do not reserve stock.
Do not add fake telemetry, unsupported overrides, recipe percentages, print/export
features or fabricated genealogy. Intermediate statuses and placeholder supplier
or scheduling metadata must be mapped to real API fields or omitted.

Static previews use English copy; production implementation must follow the
repository's translation standards. Preserve or revalidate the existing chart
palette before changing application chart colors. No schema migration is needed
for these documentation artifacts.
