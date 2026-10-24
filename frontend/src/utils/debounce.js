/**
 * Call `fn` once the caller stops for `wait` ms.
 *
 * A search box that fires per keystroke sends five requests to answer one
 * question, and the answers can arrive out of order.
 */
export function debounce(fn, wait = 300) {
	let timer = null
	const wrapped = (...args) => {
		clearTimeout(timer)
		timer = setTimeout(() => fn(...args), wait)
	}
	wrapped.cancel = () => clearTimeout(timer)
	return wrapped
}
