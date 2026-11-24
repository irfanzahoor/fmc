# Changelog

All notable changes to Food Manufacturing for ERPNext (fmc) are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.0] - 2026-11-03

First public release. Built for Frappe v16 / ERPNext v16 (`version-16` branch).
A `version-15` branch is maintained for ERPNext v15.

### Added

- **Batch traceability** — trace supplier lots through production to customers, with a full batch trail and quality log.
- **Quality control** — Quarantine, Released, Hold and Rejected batches; Quality Inspections raised from the app with every verdict shown.
- **FEFO (First Expiry, First Out)** — stock prioritised by earliest expiry; dispatch of expired or ineligible stock prevented.
- **Shelf-life management** — expiry handling with recall support: where recalled stock is, and an investigation report.
- **Recipe management** — approved recipes, recipe-based blending, recipe cost simulator, and confidential ingredient percentages protected.
- **Production** — production batches with stage-aware actions, search, UOM conversion, production yield and process-loss tracking.
- **Packaging** — bulk blends converted into multiple finished pack sizes, with packaging material planning.
- **Operator console** — role-based dashboards leading with exceptions, cost variance, live charts, ProgressRing and responsive UI; boot data so the console can post requests.
- **Dashboards & reports** — company-restricted dashboard APIs, role-based dashboards, supplier scorecard quality metrics, permlevel-aware data import templates.
- **Documentation** — built-in Batchwell handbook (`/handbook`): operating, administrator and developer guides as PDFs; vendor-facing capability document (`/proposal`).
- **Branding** — forest-green brand, Batchwell icon and Desk rail.

### Testing

- CI runs 15 of the app's 347 tests (see `CI v16` workflow).

## Install

```bash
bench get-app https://github.com/irfanzahoor/fmc
bench --site <your-site> install-app food_manufacturing
```

Requires Frappe v16 and ERPNext v16.
