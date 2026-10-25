__version__ = "0.1.0"


def __getattr__(name):
	"""Resolve a submodule on attribute access.

	ERPNext's Supplier Scorecard resolves a variable's dotted ``path`` with
	``__import__(root)`` followed by a plain ``getattr`` chain
	(``supplier_scorecard_period.import_string_path``). That finds a submodule
	only if some other code happened to import it first, so
	``food_manufacturing.quality.supplier_quality.get_fm_received_qty`` would
	resolve or fail depending on what else the worker had touched.

	PEP 562 module ``__getattr__`` closes that without importing anything at
	boot: the submodule is loaded the first time the chain actually asks for it.
	Importing these eagerly here instead would pull half the app, and its frappe
	imports, into every process that merely reads ``__version__``.
	"""
	import importlib

	try:
		return importlib.import_module(f"{__name__}.{name}")
	except ModuleNotFoundError:
		# A genuinely missing attribute must still look missing.
		raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
