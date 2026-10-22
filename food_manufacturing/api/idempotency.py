"""Transaction-scoped retry protection for operator stock postings.

The source document row lock lasts until the request commits. A retry waits for
that commit, then returns the original result rather than posting stock again.
"""

import hashlib
import inspect
import json
from functools import wraps

import frappe
from frappe import _


def retry_safe(source_type, source_arg, target_type, result_key):
	def decorate(function):
		@wraps(function)
		def wrapped(*args, **kwargs):
			bound = inspect.signature(function).bind(*args, **kwargs)
			bound.apply_defaults()
			values = dict(bound.arguments)
			request_id = values.pop("request_id", None)
			if not request_id:
				return function(*args, **kwargs)
			if not isinstance(request_id, str) or len(request_id) > 128:
				frappe.throw(_("Invalid operation request ID."))
			source = values[source_arg]
			frappe.has_permission(
				source_type, "write" if source_type == "Work Order" else "read", doc=source, throw=True
			)
			frappe.has_permission(target_type, "create", throw=True)
			frappe.db.get_value(source_type, source, "name", for_update=True)
			key = hashlib.sha256(
				f"{frappe.session.user}:{function.__name__}:{request_id}".encode()
			).hexdigest()
			payload = hashlib.sha256(json.dumps(values, sort_keys=True, default=str).encode()).hexdigest()
			previous = frappe.db.get_value(
				target_type,
				{"fm_operation_key": key},
				["name", "docstatus", "fm_operation_hash", "fm_operation_result"],
				as_dict=True,
				for_update=True,
			)
			if previous:
				frappe.has_permission(target_type, "read", doc=previous.name, throw=True)
				if previous.fm_operation_hash != payload:
					frappe.throw(_("This request ID was already used with different values."))
				if previous.docstatus != 1:
					frappe.throw(_("The original posting was cancelled. Start a new operation."))
				return json.loads(previous.fm_operation_result)
			result = function(*args, **kwargs)
			frappe.db.set_value(
				target_type,
				result[result_key],
				{
					"fm_operation_key": key,
					"fm_operation_hash": payload,
					"fm_operation_result": json.dumps(result, default=str),
				},
				update_modified=False,
			)
			return result

		return wrapped

	return decorate
