# FMC — Presentation edition

A connected, interactive design prototype with five selectable themes, two
premium font pairings, six operational pages and three dashboard experiences.
The Vue application is still unchanged; this bundle uses illustrative data.

**[Open FMC Studio](index.html)**

## Present it

1. Open `index.html` in a browser. No server or internet connection is needed.
2. Select **Midnight Blue**, **Forest**, **Amethyst**, **Graphite** or **Copper**.
3. Choose **Studio** typography (Plus Jakarta Sans headings / Inter body) or
   **Humanist** (Inter headings / Plus Jakarta Sans body).
4. Switch the live preview between pages, dashboards and phone/desktop widths.
5. Click **Launch presentation** for a full browser tab. Use the fullscreen
   button and Left/Right arrow keys to move through the presentation views.

Theme and typography choices follow navigation, persist when storage is available,
and remain in page URLs. Appearance controls inside the live frame and in the
presentation hub stay synchronized. Open the phone HTML in a phone-width window;
its layout is responsive rather than forcibly fixed to a phone-sized canvas.

## Pages and dashboards

| View | Desktop | Phone | Screenshot |
| --- | --- | --- | --- |
| Plant overview dashboard | [Open](overview.html) | [Open](overview-mobile.html) | [PNG](overview.png) |
| Production workspace | [Open](production.html) | [Open](production-mobile.html) | [PNG](production.png) |
| Production insights dashboard | [Open](production-insights.html) | [Open](production-insights-mobile.html) | [PNG](production-insights.png) |
| Quality workspace | [Open](quality.html) | [Open](quality-mobile.html) | [PNG](quality.png) |
| Quality overview dashboard | [Open](quality-insights.html) | [Open](quality-insights-mobile.html) | [PNG](quality-insights.png) |
| Goods in | [Open](receiving.html) | [Open](receiving-mobile.html) | [PNG](receiving.png) |
| Dispatch | [Open](dispatch.html) | [Open](dispatch-mobile.html) | [PNG](dispatch.png) |
| Recall & traceability | [Open](recall.html) | [Open](recall-mobile.html) | [PNG](recall.png) |

Theme examples: [Midnight](overview-midnight.png), [Forest](overview-forest.png),
[Amethyst](overview-amethyst.png), [Graphite](overview-graphite.png),
[Copper](overview-copper.png).

## Interactive behavior

- Production: select a Work Order, inspect its materials, edit output/loss and
  review a completion summary. Packaging shows bulk and packaging items.
- Quality: filter/search batches, open detail, select inspection, choose a
  decision, require a Hold/Reject reason and review the decision.
- Goods in: switch Purchase Orders, edit quantities/lots/dates, see updated totals
  and review the receipt. Scanner Enter in a lot field does not submit.
- Dispatch: scan an exact batch ID to focus its quantity, adjust picked packs,
  see updated totals and review the dispatch. Held stock remains disabled.
- Recall: search the sample batch IDs, inspect affected batches/deliveries,
  distinguish negative returns, and see a readable unknown-batch state.
- Review dialogs explicitly state that no ERPNext record is posted. UI validation
  in this design demo is illustrative, not a substitute for server rules.

## Files and verification

`preview.js` owns the shared shell, templates, example datasets and interactions;
`preview.css` owns layout and tokenized palettes. HTML files are small entry points.
Icons are inline SVG. Font files and OFL licenses are local in `fonts/`.
The former static Stitch briefs remain provenance references, not current specs.
This locally refined edition supersedes the earlier Stitch exports.

[Layout checks](preview-checks.json) and [interaction checks](interaction-checks.json)
record Chromium checks: all eight views at 390, 768 and 1440px, local font loading,
five themes, key review/scanner flows, theme persistence, live-frame synchronization,
no horizontal page/table overflow, and no external requests or JavaScript errors
in offline mode. This is prototype verification, not ERPNext integration testing.

[Design system](DESIGN.md) · [Manifest](manifest.json) ·
[Claude implementation handoff](../IMPLEMENTATION.md)
