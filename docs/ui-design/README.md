# FMC UI design handoff

The presentation edition covers all six workflows, three dashboards, five
selectable color themes and two premium font pairings on desktop and phone.

**[Open the premium design gallery](premium/index.html)** ·
[Screen previews and screenshots](premium/README.md) ·
[Implementation handoff](IMPLEMENTATION.md)

| Workflow | Existing Vue page |
| --- | --- |
| Plant overview | `frontend/src/pages/Dashboard.vue` |
| Production | `frontend/src/pages/ProductionConsole.vue` |
| Quality | `frontend/src/pages/QualityQueue.vue` |
| Goods in | `frontend/src/pages/Receiving.vue` |
| Dispatch | `frontend/src/pages/Dispatch.vue` |
| Recall | `frontend/src/pages/Recall.vue` |

[Design direction](premium/DESIGN.md) · [Stitch screen IDs](premium/manifest.json)

The current edition enhances the earlier premium direction for presentations.
Previous design drafts have been removed. Application implementation is pending;
the local HTML/JS prototype uses illustrative data and never posts ERPNext records.
Fonts, icons and assets are local, so the presentation works offline.
