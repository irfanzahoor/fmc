# FMC UI design handoff

Design references generated in Google Stitch on 23 October 2026. Implementation is
pending; application code has not been changed for this redesign.

[Stitch project](https://stitch.withgoogle.com/projects/14703154858659368589)

These are the selected refined desktop screens and mobile concepts. Earlier
iterations remain in Stitch; use the files below as the starting reference.

| Screen | Screenshot | HTML reference | Existing Vue page |
| --- | --- | --- | --- |
| Plant overview | [Preview](overview.png) | [HTML](overview.html) | `frontend/src/pages/Dashboard.vue` |
| Production | [Preview](production.png) | [HTML](production.html) | `frontend/src/pages/ProductionConsole.vue` |
| Quality queue | [Preview](quality.png) | [HTML](quality.html) | `frontend/src/pages/QualityQueue.vue` |
| Goods in | [Preview](receiving.png) | [HTML](receiving.html) | `frontend/src/pages/Receiving.vue` |
| Dispatch | [Preview](dispatch.png) | [HTML](dispatch.html) | `frontend/src/pages/Dispatch.vue` |
| Recall | [Preview](recall.png) | [HTML](recall.html) | `frontend/src/pages/Recall.vue` |
| Overview mobile | [Preview](overview-mobile.png) | [HTML](overview-mobile.html) | `Dashboard.vue` responsive layout |
| Production mobile | [Preview](production-mobile.png) | [HTML](production-mobile.html) | `ProductionConsole.vue` responsive layout |
| Dispatch mobile | [Preview](dispatch-mobile.png) | [HTML](dispatch-mobile.html) | `Dispatch.vue` responsive layout |

[Implementation instructions for Claude](IMPLEMENTATION.md) ·
[Generated design system](design-system.md) · [Stitch screen IDs](manifest.json)

HTML exports are visual references, not working application code. They may use
external fonts, icons, images and CDN scripts, so they are not fully offline
previews. Screenshots are available without those dependencies.
