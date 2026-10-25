"""ERPNext exception compatibility.

ERPNext moved its stock exceptions into a dedicated module between majors:

===============  =========================================
Version          Home of ``BatchExpiredError``
===============  =========================================
v15              ``erpnext.controllers.stock_controller``
v16              ``erpnext.exceptions``
===============  =========================================

v16 also imports the class into ``stock_controller`` for its own use, but that
is an implementation detail of that module rather than a published location, so
the canonical v16 home is tried first and v15's is the fallback.

Tests and handlers import from here and stay version-neutral.
"""

try:  # v16+
	from erpnext.exceptions import BatchExpiredError
except ImportError:  # v15
	from erpnext.controllers.stock_controller import BatchExpiredError

__all__ = ["BatchExpiredError"]
