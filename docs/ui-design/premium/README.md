# FMC — Premium v2

The user approved the new Overview/Production visual direction. All six workflows
now have matching desktop and phone design previews. These are static design
references; the Vue application has not been changed.

**[Open the complete design gallery](index.html)**

| Screen | Desktop HTML | Phone HTML | Desktop PNG | Phone PNG |
| --- | --- | --- | --- | --- |
| Plant overview | [Open](overview.html) | [Open](overview-mobile.html) | [View](overview.png) | [View](overview-mobile.png) |
| Production | [Open](production.html) | [Open](production-mobile.html) | [View](production.png) | [View](production-mobile.png) |
| Quality | [Open](quality.html) | [Open](quality-mobile.html) | [View](quality.png) | [View](quality-mobile.png) |
| Goods in | [Open](receiving.html) | [Open](receiving-mobile.html) | [View](receiving.png) | [View](receiving-mobile.png) |
| Dispatch | [Open](dispatch.html) | [Open](dispatch-mobile.html) | [View](dispatch.png) | [View](dispatch-mobile.png) |
| Recall & traceability | [Open](recall.html) | [Open](recall-mobile.html) | [View](recall.png) | [View](recall-mobile.png) |

[Premium Stitch project](https://stitch.withgoogle.com/projects/3395685398154969203)
· [Design direction](DESIGN.md) · [Source screen IDs](manifest.json)
· [Browser layout checks](preview-checks.json)

## How these previews work

The six desktop screens were generated in Stitch and refined locally. Shared
`preview.css` and a consistent navigation shell connect the local previews.
The phone files are local responsive adaptations of those same desktop designs,
not separate Stitch generations. Desktop HTML also adapts when its viewport narrows.

All six navigation links work between preview files, with a full six-item phone
navigation bar. Phone tables become labeled cards, and Overview's chart becomes
a readable run list. Overview and Production retain the approved layout direction.
Quality's table was simplified to avoid clipped columns; Dispatch includes stock
quantity inputs and disabled held-batch inputs.

Screenshots were rendered from the local HTML at 1440px desktop and 390px phone.
All six pages passed layout checks at both widths with no horizontal page overflow;
no desktop table was clipped, and all six phone navigation links were visible.
This is visual/layout verification, not testing of ERPNext transactions.

The gallery and PNGs can be viewed offline. The generated HTML depends on external
CDN styles and fonts, so it needs internet for its full appearance. Controls use
illustrative data and are not connected to ERPNext; a responsive phone preview
should be viewed in a phone-width browser viewport.

## Implementation handoff

Use [`../IMPLEMENTATION.md`](../IMPLEMENTATION.md) and repository `CLAUDE.md` before
implementing. Previous design drafts have been removed.
Use real API fields and permissions rather than copying placeholder data or
unavailable actions. The example green charts do not replace the application's
validated visualization palette without the required validation.
