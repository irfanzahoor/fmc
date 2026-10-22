import { call } from 'frappe-ui'

/** Thin named wrappers, so a page never contains a dotted method path. */
const mutations = new Set(['production.finish_production_run', 'receiving.receive_purchase_order', 'dispatch.create_delivery_note'])
const pending = new Map()
const method = (name) => async (args = {}) => {
	if (!mutations.has(name)) return call(`food_manufacturing.api.${name}`, args)
	const storageKey = `fm:retry:${name}:${JSON.stringify(args)}`
	let requestId = pending.get(storageKey)
	try { requestId ||= sessionStorage.getItem(storageKey) } catch { /* Storage may be disabled. */ }
	requestId ||= crypto.randomUUID()
	pending.set(storageKey, requestId)
	try { sessionStorage.setItem(storageKey, requestId) } catch { /* In-memory retries remain available. */ }
	const result = await call(`food_manufacturing.api.${name}`, { ...args, request_id: requestId })
	// Only a confirmed response ends the operation. A lost response keeps its ID for retry.
	pending.delete(storageKey)
	try { sessionStorage.removeItem(storageKey) } catch { /* Storage may be disabled. */ }
	return result
}

export const production = {
	queue: method('production.get_production_queue'),
	detail: method('production.get_work_order_detail'),
	finishRun: method('production.finish_production_run'),
}

export const quality = {
	queue: method('quality.get_release_queue'),
	counts: method('quality.get_queue_counts'),
	batchContext: method('quality.get_batch_context'),
	recordDecision: method('quality.record_decision'),
}

export const receiving = {
	openOrders: method('receiving.get_open_purchase_orders'),
	orderLines: method('receiving.get_purchase_order_lines'),
	receive: method('receiving.receive_purchase_order'),
}

export const dispatch = {
	openOrders: method('dispatch.get_open_sales_orders'),
	picklist: method('dispatch.get_picklist'),
	createDeliveryNote: method('dispatch.create_delivery_note'),
}

/** Pull a readable message out of a Frappe error response. */
export function errorMessage(error) {
	if (!error) return null
	const messages = error.messages || error._server_messages
	if (Array.isArray(messages) && messages.length) {
		return messages
			.map((m) => {
				try {
					return JSON.parse(m).message || m
				} catch {
					return m
				}
			})
			.join('\n')
	}
	return error.message || String(error)
}
