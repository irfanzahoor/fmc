"""Test base-class compatibility.

===============  ==================================================
Version          Base class
===============  ==================================================
v15              ``frappe.tests.utils.FrappeTestCase``
v16              ``frappe.tests.IntegrationTestCase``
===============  ==================================================

Tests import :data:`FMTestCase` and stay version-neutral. v16 still ships a
deprecated ``FrappeTestCase`` alias, so the import order below prefers the
current name and only falls back to the old one.
"""

try:  # v16+
	from frappe.tests import IntegrationTestCase as _BaseTestCase
except ImportError:  # v15
	from frappe.tests.utils import FrappeTestCase as _BaseTestCase


class FMTestCase(_BaseTestCase):
	"""Base class for every Food Manufacturing test."""


__all__ = ["FMTestCase"]
