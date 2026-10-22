---
name: FMC Operations Core
colors:
  surface: '#f7f9fc'
  surface-dim: '#d8dadd'
  surface-bright: '#f7f9fc'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f4f7'
  surface-container: '#eceef1'
  surface-container-high: '#e6e8eb'
  surface-container-highest: '#e0e3e6'
  on-surface: '#191c1e'
  on-surface-variant: '#414752'
  inverse-surface: '#2d3133'
  inverse-on-surface: '#eff1f4'
  outline: '#727784'
  outline-variant: '#c1c6d4'
  surface-tint: '#005eb4'
  primary: '#005bb0'
  on-primary: '#ffffff'
  primary-container: '#2474d2'
  on-primary-container: '#fefcff'
  inverse-primary: '#a8c8ff'
  secondary: '#545f73'
  on-secondary: '#ffffff'
  secondary-container: '#d5e0f8'
  on-secondary-container: '#586377'
  tertiary: '#4d5d73'
  on-tertiary: '#ffffff'
  tertiary-container: '#66768d'
  on-tertiary-container: '#fdfcff'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#d5e3ff'
  primary-fixed-dim: '#a8c8ff'
  on-primary-fixed: '#001b3c'
  on-primary-fixed-variant: '#00468a'
  secondary-fixed: '#d8e3fb'
  secondary-fixed-dim: '#bcc7de'
  on-secondary-fixed: '#111c2d'
  on-secondary-fixed-variant: '#3c475a'
  tertiary-fixed: '#d3e4fe'
  tertiary-fixed-dim: '#b7c8e1'
  on-tertiary-fixed: '#0b1c30'
  on-tertiary-fixed-variant: '#38485d'
  background: '#f7f9fc'
  on-background: '#191c1e'
  surface-variant: '#e0e3e6'
typography:
  display-lg:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.02em
  display-lg-mobile:
    fontFamily: Inter
    fontSize: 26px
    fontWeight: '700'
    lineHeight: 34px
    letterSpacing: -0.015em
  headline-md:
    fontFamily: Inter
    fontSize: 22px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: -0.005em
  title-md:
    fontFamily: Inter
    fontSize: 15px
    fontWeight: '600'
    lineHeight: 20px
  title-sm:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '600'
    lineHeight: 18px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
  label-md:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.01em
  label-xs:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 14px
    letterSpacing: 0.04em
  data-tabular-lg:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '700'
    lineHeight: 28px
    letterSpacing: -0.02em
  data-tabular-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
  data-tabular-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  gutter: 1rem
  gutter-dense: 0.75rem
  margin: 1.5rem
  margin-mobile: 0.75rem
  space-2xs: 0.125rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.75rem
  space-lg: 1rem
  space-xl: 1.5rem
  space-2xl: 2rem
---

## Brand & Style

This design system targets food manufacturing operations, quality control laboratories, and supply chain management within high-throughput spice and masala processing plants. The operational environment requires operators, plant supervisors, and food technologists to rapidly parse batch statuses, yield discrepancies, tolerance limits, and hygiene parameters under shifting physical and digital conditions.

The visual style is **Refined Industrial Modern**: hyper-functional, data-dense, restrained, and precise. It eschews decorative clutter, aggressive gradients, and non-essential ornamentation in favor of crisp delineation, meticulous spacing cadence, and immediate information legibility. The emotional response must be one of absolute operational control, food safety compliance, and zero-latency decision confidence. Every visual artifact serves to communicate quantitative truth, process deviations, or batch lifecycle milestones.

## Colors

The color palette prioritizes optical balance across high-density tabular views and real-time plant telemetry. Contrast and semantic isolation guide the eye to process excursions without inducing cognitive fatigue during extended operational shifts.

### Canvas & Surfaces
- **Canvas Base:** `#F5F7FA` provides a cool, anti-glare operational foundation across industrial displays.
- **Card / Sheet Surface:** `#FFFFFF` offers maximum clarity and separation from the backdrop.
- **Subtle Surface Borders:** Primary structural dividers use `#E2E8F0`; secondary micro-dividers use `#EDF2F7`.

### Typography & Neutrals
- **Primary Text:** `#0F172A` (900 slate) for top-level headers, primary KPIs, and critical telemetry values.
- **Secondary Text:** `#1E293B` (800 slate) for table records, input values, and structured data labels.
- **Muted / Metadata Text:** `#64748B` (500 slate) for timestamps, secondary units, and static table column headers.

### Primary Brand
- **Interactive Primary:** `#2A78D6` serves as the focused operational anchor for interactive triggers, current-step steppers, and active navigation nodes.

### Operational Semantic Status
Semantic statuses must **never rely on color alone**. Every status indication requires pairing with an explicit text string, a categorical badge, or an unambiguous directional icon:
- **Released / Normal / In Spec:** Foreground `#16A34A`, Tint Background `#DCFCE7`, Border `#BBF7D0`.
- **Quarantine / Warning / Pending Review:** Foreground `#D97706`, Tint Background `#FEF3C7`, Border `#FDE68A`.
- **Hold / Attention / Deviation:** Foreground `#EA580C`, Tint Background `#FFEDD5`, Border `#FED7AA`.
- **Rejected / Out of Spec / Critical Hazard:** Foreground `#DC2626`, Tint Background `#FEE2E2`, Border `#FECACA`.

## Typography

Inter serves as the sole typographic engine, engineered specifically for high-legibility screens and dense quantitative layouts. 

### Font-Feature Settings Rule
All numerical layouts—including inventory yields, weight metrics (kg/g/MT), moisture contents (%), lot identifiers, and batch countdown clocks—**must enforce**:
`font-feature-settings: 'tnum' on, 'cv02' on, 'cv03' on, 'zero' on;`

This ensures:
1. Strict monospaced vertical columnar alignment across fluctuating decimal places.
2. Distinct non-ambiguous representations of digits `1`, `7`, and slashed `0` to prevent formulation input errors during seasoning and blending routines.
3. Optical alignment of currency and mass unit abbreviations against adjacent integers.

## Layout & Spacing

The operational interface uses a **fluid, density-optimized 12-column grid** anchored by a structured left navigation shell (fixed at 240px desktop, collapsible to 64px icon rail on tablets).

### Breakpoints & Layout Adaptations
- **Desktop (1440px and above):** 12-column fluid grid, 24px canvas margins, 16px column gutters. Production line control panels and batch tracking matrices expand into 3- or 4-up analytical cards.
- **Compact Desktop / Tablet Landscape (1024px - 1439px):** 12-column fluid grid, 16px canvas margins, 12px column gutters. Multi-metric tables preserve horizontal continuity; secondary metadata collapses into tooltips or expandable row drawers.
- **Tablet Portrait (768px - 1023px):** 8-column layout, 16px canvas margins. Split KPI horizontal bars stack into dual-row metrics.
- **Rugged Mobile / Handheld Scanner (360px - 767px):** 4-column layout, 12px canvas margins, 8px gutters. Shift views simplify to single-column card flows with persistent primary barcode action bars pinned to the bottom.

### Operational Spacing Rhythm
Component layouts adhere strictly to a compact 4px baseline rhythm (`space-xs` = 4px, `space-sm` = 8px, `space-md` = 12px, `space-lg` = 16px). High-density operational tables employ a strict 36px row height with 8px horizontal cell padding to maximize visible rows per screen viewport without touch-target degradation.

## Elevation & Depth

This design system rejects deep drop shadows and skeuomorphic lighting in favor of **disciplined tonal layering and low-contrast perimeter definition**. Industrial environments require sharp delineation that remains readable under varying ambient lighting conditions.

### Surface Hierarchy
1. **Level 0 (Canvas):** `#F5F7FA` foundational backdrop.
2. **Level 1 (Operational Cards & Workbenches):** Solid `#FFFFFF` background bound by a continuous 1px outline of `#E2E8F0`. No ambient shadow in default state.
3. **Level 2 (Active Focus & Sticky Table Headers):** `#FFFFFF` with a 1px border of `#CBD5E1` and an ultra-subtle, non-diffuse baseline shadow: `0 1px 3px 0 rgba(15, 23, 42, 0.06), 0 1px 2px -1px rgba(15, 23, 42, 0.04)`.
4. **Level 3 (Flyout Drawers, Modals & Lot Inspection Panels):** Solid `#FFFFFF` framed by a 1px border of `#94A3B8`, elevated by a crisp structural shadow: `0 10px 15px -3px rgba(15, 23, 42, 0.08), 0 4px 6px -4px rgba(15, 23, 42, 0.04)`.
5. **Level 4 (Out-of-Spec Warning Overlays):** Persistent `#FFFFFF` surface bordered by a 2px high-visibility stroke of the appropriate semantic color (`#DC2626` for alerts, `#D97706` for quarantine), accompanied by an ambient flash-free border highlight.

## Shapes

The geometric framework enforces strict structural discipline to communicate precision and containment:

- **Containers, Data Workbenches & KPI Cards:** Fixed **10px** corner radius (`rounded-[10px]`). This softens the visual grid slightly while maintaining a tight, industrial perimeter that maximizes usable rectangular screen estate.
- **Buttons, Form Inputs, Dropdowns & Pill Badges:** Strict **6px** corner radius (`rounded-[6px]`). This creates distinct nested harmony inside the 10px outer containment cards.
- **Data Visualizer Markers & Expiry Horizon Blocks:** **4px** corner radius (`rounded-[4px]`) for internal bars, mini tolerance indicators, and tabular milestone tags. Fully circular geometries (`rounded-full`) are restricted strictly to status indicator dots and counter badges.

## Components

### Buttons & Interactive Controls
- **Primary Action:** Solid `#2A78D6` background, `#FFFFFF` text, 6px radius, height: 36px (compact desktop) / 44px (touch scanner), horizontal padding 14px. Hover: `#1E62B3`. Active: `#185296`.
- **Secondary / Outline:** `#FFFFFF` background, 1px border `#CBD5E1`, text `#1E293B`. Hover: `#F8FAFC`, border `#94A3B8`.
- **Destructive / Reject:** `#DC2626` text, `#FEE2E2` background, 1px border `#FECACA`. Hover: `#FCA5A5`.

### High-Density KPI Cards
- Form factor: 10px radius, `#FFFFFF` surface, 1px border `#E2E8F0`, padding 16px.
- Internal layout: Top row holds the metric label (`label-xs` uppercase in `#64748B`) and status pill. Center holds the large tabular number (`data-tabular-lg` in `#0F172A`). Bottom holds the deviation comparator (e.g., "+2.4% vs Recipe Standard" with contextual green/red text and directional micro-arrow).

### Tabular Data Grid
- Header row: 32px height, `#F8FAFC` background, 1px bottom border `#CBD5E1`. Text: `label-xs` uppercase `#475569`.
- Data rows: 36px height, alternating transparent and `#FCFDFE` background for zebra scanability. Bottom border 1px `#EDF2F7`. Hover: `#F1F5F9`.
- Column alignments: Text left-aligned; all numerical weights, dates, and lots right-aligned using `data-tabular-md`.

### SVG Line Charts with Tolerance Bands & Out-of-Spec Markers
- Visualization canvas: Embedded cleanly within standard 10px cards. Background grid lines: 1px dashed `#E2E8F0`.
- Tolerance band: Shaded horizontal zone (`rgba(42, 120, 214, 0.06)`) bounded by upper and lower specification limit lines (`1px dashed #94A3B8`).
- Process run line: 2px solid stroke `#2A78D6`.
- Violation points: 6px circular nodes styled in `#DC2626` with a 2px white halo and outward ping badge indicating step index and timestamp.

### Horizontal Split Ranking Bars (Dual Independent Units)
- Dedicated dual-progress track measuring both mass (`kg`) and discrete packaging (`packs`).
- Container height: 28px, background `#F1F5F9`, 4px radius.
- Split fill: Primary progress bar `#2A78D6` (mass target) with interior right-aligned tabular text in white; secondary complementary fill `#93C5FD` (pack completion) with dark navy slate text.

### Quality Status Breakdown Pill Badges
- Height: 22px, corner radius: 6px, padding: 2px 8px.
- Structure: Always pairs a 6px semantic status circle with explicit uppercase text (`label-xs`).
- Matrix:
  - *Released:* `#DCFCE7` background, `#16A34A` text and dot.
  - *Quarantine:* `#FEF3C7` background, `#D97706` text and dot.
  - *Hold:* `#FFEDD5` background, `#EA580C` text and dot.
  - *Rejected:* `#FEE2E2` background, `#DC2626` text and dot.

### Tiered Expiry Horizon Countdown Blocks
- Visual countdown blocks grouped into time intervals: `< 24h` (Critical), `< 7d` (Urgent), `< 30d` (Nominal), `> 30d` (Stable).
- Unit composition: 4px rounded block containers displaying numerical days remaining in bold tabular figures, backed by corresponding semantic tint borders and progress ribbons indicating lot freshness degradation.

## Brand & Style

This design system targets food manufacturing operations, quality control laboratories, and supply chain management within high-throughput spice and masala processing plants. The operational environment requires operators, plant supervisors, and food technologists to rapidly parse batch statuses, yield discrepancies, tolerance limits, and hygiene parameters under shifting physical and digital conditions.

The visual style is **Refined Industrial Modern**: hyper-functional, data-dense, restrained, and precise. It eschews decorative clutter, aggressive gradients, and non-essential ornamentation in favor of crisp delineation, meticulous spacing cadence, and immediate information legibility. The emotional response must be one of absolute operational control, food safety compliance, and zero-latency decision confidence. Every visual artifact serves to communicate quantitative truth, process deviations, or batch lifecycle milestones.

## Layout & Spacing

The operational interface uses a **fluid, density-optimized 12-column grid** anchored by a structured left navigation shell (fixed at 240px desktop, collapsible to 64px icon rail on tablets).

### Breakpoints & Layout Adaptations
- **Desktop (1440px and above):** 12-column fluid grid, 24px canvas margins, 16px column gutters. Production line control panels and batch tracking matrices expand into 3- or 4-up analytical cards.
- **Compact Desktop / Tablet Landscape (1024px - 1439px):** 12-column fluid grid, 16px canvas margins, 12px column gutters. Multi-metric tables preserve horizontal continuity; secondary metadata collapses into tooltips or expandable row drawers.
- **Tablet Portrait (768px - 1023px):** 8-column layout, 16px canvas margins. Split KPI horizontal bars stack into dual-row metrics.
- **Rugged Mobile / Handheld Scanner (360px - 767px):** 4-column layout, 12px canvas margins, 8px gutters. Shift views simplify to single-column card flows with persistent primary barcode action bars pinned to the bottom.

### Operational Spacing Rhythm
Component layouts adhere strictly to a compact 4px baseline rhythm (`space-xs` = 4px, `space-sm` = 8px, `space-md` = 12px, `space-lg` = 16px). High-density operational tables employ a strict 36px row height with 8px horizontal cell padding to maximize visible rows per screen viewport without touch-target degradation.

## Elevation & Depth

This design system rejects deep drop shadows and skeuomorphic lighting in favor of **disciplined tonal layering and low-contrast perimeter definition**. Industrial environments require sharp delineation that remains readable under varying ambient lighting conditions.

### Surface Hierarchy
1. **Level 0 (Canvas):** `#F5F7FA` foundational backdrop.
2. **Level 1 (Operational Cards & Workbenches):** Solid `#FFFFFF` background bound by a continuous 1px outline of `#E2E8F0`. No ambient shadow in default state.
3. **Level 2 (Active Focus & Sticky Table Headers):** `#FFFFFF` with a 1px border of `#CBD5E1` and an ultra-subtle, non-diffuse baseline shadow: `0 1px 3px 0 rgba(15, 23, 42, 0.06), 0 1px 2px -1px rgba(15, 23, 42, 0.04)`.
4. **Level 3 (Flyout Drawers, Modals & Lot Inspection Panels):** Solid `#FFFFFF` framed by a 1px border of `#94A3B8`, elevated by a crisp structural shadow: `0 10px 15px -3px rgba(15, 23, 42, 0.08), 0 4px 6px -4px rgba(15, 23, 42, 0.04)`.
5. **Level 4 (Out-of-Spec Warning Overlays):** Persistent `#FFFFFF` surface bordered by a 2px high-visibility stroke of the appropriate semantic color (`#DC2626` for alerts, `#D97706` for quarantine), accompanied by an ambient flash-free border highlight.

## Components

### Buttons & Interactive Controls
- **Primary Action:** Solid `#2A78D6` background, `#FFFFFF` text, 6px radius, height: 36px (compact desktop) / 44px (touch scanner), horizontal padding 14px. Hover: `#1E62B3`. Active: `#185296`.
- **Secondary / Outline:** `#FFFFFF` background, 1px border `#CBD5E1`, text `#1E293B`. Hover: `#F8FAFC`, border `#94A3B8`.
- **Destructive / Reject:** `#DC2626` text, `#FEE2E2` background, 1px border `#FECACA`. Hover: `#FCA5A5`.

### High-Density KPI Cards
- Form factor: 10px radius, `#FFFFFF` surface, 1px border `#E2E8F0`, padding 16px.
- Internal layout: Top row holds the metric label (`label-xs` uppercase in `#64748B`) and status pill. Center holds the large tabular number (`data-tabular-lg` in `#0F172A`). Bottom holds the deviation comparator (e.g., "+2.4% vs Recipe Standard" with contextual green/red text and directional micro-arrow).

### Tabular Data Grid
- Header row: 32px height, `#F8FAFC` background, 1px bottom border `#CBD5E1`. Text: `label-xs` uppercase `#475569`.
- Data rows: 36px height, alternating transparent and `#FCFDFE` background for zebra scanability. Bottom border 1px `#EDF2F7`. Hover: `#F1F5F9`.
- Column alignments: Text left-aligned; all numerical weights, dates, and lots right-aligned using `data-tabular-md`.

### SVG Line Charts with Tolerance Bands & Out-of-Spec Markers
- Visualization canvas: Embedded cleanly within standard 10px cards. Background grid lines: 1px dashed `#E2E8F0`.
- Tolerance band: Shaded horizontal zone (`rgba(42, 120, 214, 0.06)`) bounded by upper and lower specification limit lines (`1px dashed #94A3B8`).
- Process run line: 2px solid stroke `#2A78D6`.
- Violation points: 6px circular nodes styled in `#DC2626` with a 2px white halo and outward ping badge indicating step index and timestamp.

### Horizontal Split Ranking Bars (Dual Independent Units)
- Dedicated dual-progress track measuring both mass (`kg`) and discrete packaging (`packs`).
- Container height: 28px, background `#F1F5F9`, 4px radius.
- Split fill: Primary progress bar `#2A78D6` (mass target) with interior right-aligned tabular text in white; secondary complementary fill `#93C5FD` (pack completion) with dark navy slate text.

### Quality Status Breakdown Pill Badges
- Height: 22px, corner radius: 6px, padding: 2px 8px.
- Structure: Always pairs a 6px semantic status circle with explicit uppercase text (`label-xs`).
- Matrix:
  - *Released:* `#DCFCE7` background, `#16A34A` text and dot.
  - *Quarantine:* `#FEF3C7` background, `#D97706` text and dot.
  - *Hold:* `#FFEDD5` background, `#EA580C` text and dot.
  - *Rejected:* `#FEE2E2` background, `#DC2626` text and dot.

### Tiered Expiry Horizon Countdown Blocks
- Visual countdown blocks grouped into time intervals: `< 24h` (Critical), `< 7d` (Urgent), `< 30d` (Nominal), `> 30d` (Stable).
- Unit composition: 4px rounded block containers displaying numerical days remaining in bold tabular figures, backed by corresponding semantic tint borders and progress ribbons indicating lot freshness degradation.