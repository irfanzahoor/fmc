"""Entry points for ERPNext's Supplier Scorecard, kept one level deep.

The measurement lives in :mod:`food_manufacturing.quality.supplier_quality`.
This module exists only to be *resolvable*: ERPNext walks a variable's dotted
``path`` with ``__import__(root)`` and a plain ``getattr`` chain, so every
component after the root has to already be an attribute of the one before it.
A single level below the package needs only the lazy ``__getattr__`` in
``food_manufacturing/__init__.py``; a deeper path would need one in every
package along the way.

So the registered paths are ``food_manufacturing.scorecard_variables.<fn>``,
and the logic stays where it belongs.
"""

from food_manufacturing.quality.supplier_quality import (
	get_fm_lots_received,
	get_fm_qc_rejected_qty,
	get_fm_received_qty,
	get_fm_usable_qty,
)

__all__ = [
	"get_fm_lots_received",
	"get_fm_qc_rejected_qty",
	"get_fm_received_qty",
	"get_fm_usable_qty",
]
