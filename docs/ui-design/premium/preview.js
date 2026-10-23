/* Static presentation prototype. No server calls or ERPNext records are written. */
(() => {
  'use strict';
  const themes = {
    midnight: { name: 'Midnight Blue', note: 'Confident & contemporary', colors: ['#111d33', '#4263eb', '#edf1ff', '#f4f6fb'] },
    forest: { name: 'Forest', note: 'Natural & composed', colors: ['#142f29', '#247861', '#eaf4ee', '#f4f7f3'] },
    amethyst: { name: 'Amethyst', note: 'Distinctive & refined', colors: ['#251d39', '#7552b5', '#f1ecfa', '#f7f5fa'] },
    graphite: { name: 'Graphite', note: 'Quiet & architectural', colors: ['#202831', '#445366', '#edf0f3', '#f4f5f6'] },
    copper: { name: 'Copper', note: 'Warm & crafted', colors: ['#342a23', '#9c5b35', '#faf0e8', '#f8f5f0'] },
  };
  const paths = {
    grid: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
    factory: '<path d="M3 21V10l6 3V8l6 4V3h4l2 18H3Z"/><path d="M7 17h1m4 0h1m4 0h1"/>',
    shield: '<path d="M12 3 4 6v6c0 5 8 9 8 9s8-4 8-9V6l-8-3Z"/><path d="m8.5 12 2.5 2.5 4.5-5"/>',
    box: '<path d="m3 7 9-4 9 4v10l-9 4-9-4V7Z"/><path d="m3 7 9 4 9-4M12 11v10M7.5 5l9 4"/>',
    truck: '<path d="M3 5h11v12H3zM14 9h4l3 4v4h-7"/><circle cx="7" cy="18" r="2"/><circle cx="18" cy="18" r="2"/>',
    trace: '<circle cx="6" cy="5" r="2"/><circle cx="18" cy="12" r="2"/><circle cx="6" cy="19" r="2"/><path d="M8 5h4a4 4 0 0 1 4 4v1M6 7v10M8 19h4a4 4 0 0 0 4-4v-1"/>',
    chart: '<path d="M4 3v17h17M8 15l4-5 4 2 5-7"/>',
    arrow: '<path d="M5 12h14m-5-5 5 5-5 5"/>',
    chevron: '<path d="m9 5 7 7-7 7"/>',
    down: '<path d="m6 9 6 6 6-6"/>',
    upRight: '<path d="M6 18 18 6M6 6h12v12"/>',
    check: '<path d="m5 12 4 4L19 6"/>',
    calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4M17 3v4M3 10h18"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    alert: '<path d="m12 3 10 18H2L12 3Z"/><path d="M12 9v5m0 3h.01"/>',
    leaf: '<path d="M20 4c-9-2-17 3-15 10 2 7 14 5 15-10Z"/><path d="M4 21 15 10"/>',
    search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
    palette: '<path d="M12 3a9 9 0 1 0 0 18h1c3 0 4-3 1-5-2-2 0-3 2-3h2c5 0 3-10-6-10Z"/><path d="M7 9h.01M10 6h.01M15 7h.01M6 13h.01"/>',
    building: '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 7h2m4 0h2M8 11h2m4 0h2M10 21v-6h4v6"/>',
    expand: '<path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5"/>',
    close: '<path d="m6 6 12 12M18 6 6 18"/>',
    refresh: '<path d="M20 7v5h-5M4 17v-5h5"/><path d="M6 7a7 7 0 0 1 12-1l2 3M4 15l2 3a7 7 0 0 0 12-1"/>',
    barcode: '<path d="M4 7V3h4m8 0h4v4M4 17v4h4m8 0h4v-4M7 8v8m3-8v8m4-8v8m3-8v8"/>',
    layers: '<path d="m12 3 10 5-10 5L2 8l10-5Zm-10 9 10 5 10-5M2 16l10 5 10-5"/>',
    lock: '<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>',
    pause: '<path d="M8 5v14M16 5v14"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10h.01"/>',
    eye: '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>',
  };
  const icon = name => `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">${paths[name] || paths.grid}</svg>`;
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  const num = value => Number(value).toLocaleString('en-US', { maximumFractionDigits: 2 });
  const storage = { get(key) { try { return localStorage.getItem(key); } catch { return null; } }, set(key, value) { try { localStorage.setItem(key, value); } catch { /* URL links also retain the selection. */ } } };
  const params = new URLSearchParams(location.search);
  let theme = params.get('theme') || storage.get('fmc:preview-theme') || 'midnight';
  if (!themes[theme]) theme = 'midnight';
  let font = params.get('font') || storage.get('fmc:preview-font') || 'studio';
  if (!['studio', 'humanist'].includes(font)) font = 'studio';
  const page = document.body.dataset.page || 'overview';
  const mobileFile = location.pathname.includes('-mobile.html');
  let insights = (params.get('view') === 'insights' || document.body.dataset.view === 'insights') && ['production', 'quality'].includes(page);
  const pages = [ ['overview', 'Plant overview', 'grid'], ['production', 'Production', 'factory'], ['quality', 'Quality', 'shield'], ['receiving', 'Goods in', 'box'], ['dispatch', 'Dispatch', 'truck'], ['recall', 'Recall & traceability', 'trace'] ];
  const navNames = { overview: 'Overview', production: 'Production', quality: 'Quality', receiving: 'Receiving', dispatch: 'Dispatch', recall: 'Recall' };
  const href = (name, view = '') => {
    const q = new URLSearchParams({ theme, font });
    if (view) q.set('view', view);
    if (params.get('present') === '1') q.set('present', '1');
    return `${name}${mobileFile && name !== 'index' ? '-mobile' : ''}.html?${q}`;
  };
  const badge = (text, kind = 'neutral') => `<span class="badge ${kind}"><i class="dot"></i>${escape(text)}</span>`;
  const kind = status => ({ Released: 'good', Quarantine: 'warn', Hold: 'warn', Rejected: 'bad', 'In process': 'neutral', 'Ready to start': 'good' })[status] || 'neutral';
  const field = (label, control, helper = '', extra = '') => `<label class="field ${extra}">${label}${control}${helper ? `<small>${helper}</small>` : ''}</label>`;
  const button = (text, action, primary = false, glyph = '') => `<button class="button ${primary ? 'primary' : ''}" type="button" data-action="${action}">${glyph ? icon(glyph) : ''}${text}</button>`;
  const metric = (label, value, unit, note, glyph, tone = '') => `<article class="card metric"><div class="metric-top"><span class="metric-label">${label}</span><span class="metric-icon">${icon(glyph)}</span></div><div class="metric-value mono">${value}${unit ? `<small>${unit}</small>` : ''}</div><p class="metric-note ${tone}"><i class="dot"></i>${note}</p></article>`;
  const cardHead = (title, subtitle, right = '') => `<div class="card-head"><div><h2>${title}</h2>${subtitle ? `<p>${subtitle}</p>` : ''}</div>${right}</div>`;
  const info = (text, tone = '') => `<div class="info ${tone}">${icon(tone === 'warn' ? 'alert' : 'info')}<span>${text}</span></div>`;
  const td = (label, html, cls = '') => `<td data-label="${label}" class="${cls}">${html}</td>`;
  const table = (headers, rows, caption) => `<div class="table-wrap"><table class="mobile-cards"><caption class="sr-only">${caption}</caption><thead><tr>${headers.map(h => `<th>${h}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table></div>`;
  const footer = () => `<footer class="page-footer"><span><i class="dot"></i>FM Demo Foods · Illustrative workspace</span><a data-route="index" href="${href('index')}">Design &amp; themes ${icon('upRight')}</a></footer>`;
  const swatches = key => `<span class="swatches">${themes[key].colors.map(color => `<i style="background:${color}"></i>`).join('')}</span>`;
  const themePicker = () => `<details class="theme-picker"><summary class="icon-button" aria-label="Choose color theme">${icon('palette')}<span class="tool-label">Appearance</span></summary><div class="theme-panel"><h3>A look that feels like you.</h3><p>Choose a palette for the entire workspace.</p><div class="theme-options">${Object.keys(themes).map(key => `<button type="button" class="theme-option" data-theme-pick="${key}" aria-pressed="${key === theme}">${swatches(key)}<span>${themes[key].name}</span><span class="check">${icon('check')}</span></button>`).join('')}</div><label class="font-option">Typography pairing<select data-font-pick aria-label="Typography pairing"><option value="studio" ${font === 'studio' ? 'selected' : ''}>Studio · Jakarta Sans + Inter</option><option value="humanist" ${font === 'humanist' ? 'selected' : ''}>Humanist · Inter + Jakarta Sans</option></select></label></div></details>`;
  function applyAppearance() {
    document.documentElement.dataset.theme = theme;
    document.documentElement.dataset.font = font;
    storage.set('fmc:preview-theme', theme); storage.set('fmc:preview-font', font);
    document.querySelectorAll('[data-theme-pick]').forEach(el => el.setAttribute('aria-pressed', String(el.dataset.themePick === theme)));
    document.querySelectorAll('[data-font-pick]').forEach(el => { el.value = font; });
    document.querySelectorAll('[data-route]').forEach(el => { const target = href(el.dataset.route, el.dataset.view || ''); el.href = el.dataset.presentation ? target + '&present=1' : target; });
    const q = new URLSearchParams(location.search); q.set('theme', theme); q.set('font', font);
    try { history.replaceState(null, '', `${location.pathname}?${q}`); } catch { /* file previews can restrict History API. */ }
    const frame = document.querySelector('#demo-frame');
    if (frame?.contentWindow) frame.contentWindow.postMessage({ type: 'fmc:appearance', theme, font }, '*');
  }
  function shell() {
    const name = pages.find(p => p[0] === page)?.[1] || 'Overview';
    document.title = `${name}${insights ? ' · Insights' : ''} · FMC`;
    const navigation = pages.map(([key, , glyph]) => `<a data-route="${key}" href="${href(key)}" class="${key === page && !insights ? 'active' : ''}" ${key === page && !insights ? 'aria-current="page"' : ''}>${icon(glyph)}<span>${navNames[key]}</span>${key === 'quality' ? '<span class="nav-count">12</span>' : ''}</a>`).join('');
    document.body.innerHTML = `<a class="skip" href="#main">Skip to content</a><aside class="sidebar"><a class="brand" data-route="overview" href="${href('overview')}"><span class="brand-logo">FMC</span><span><span class="brand-name">FMC</span><small>Food manufacturing, connected.</small></span></a><div class="nav-label">WORKSPACE</div><nav class="nav-group" aria-label="Operations">${navigation}</nav><div class="nav-insights"><div class="nav-label">INSIGHTS</div><nav class="nav-group" aria-label="Analytics"><a data-route="production" data-view="insights" href="${href('production', 'insights')}" class="${page === 'production' && insights ? 'active' : ''}">${icon('chart')}<span>Production insights</span></a><a data-route="quality" data-view="insights" href="${href('quality', 'insights')}" class="${page === 'quality' && insights ? 'active' : ''}">${icon('shield')}<span>Quality overview</span></a></nav></div><div class="sidebar-footer"><div class="workspace-foot"><span class="workspace-avatar">FM</span><span><strong>FM Demo Foods</strong><small>Spice &amp; masala operations</small></span></div><a class="sidebar-gallery" data-route="index" href="${href('index')}">${icon('palette')}Explore design themes ${icon('upRight')}</a></div></aside><header class="topbar"><a class="icon-button mobile-menu" data-route="index" href="${href('index')}" aria-label="Design home">FM</a><div class="breadcrumbs"><span>Workspace</span>${icon('chevron')}<strong>${name}${insights ? ' / Insights' : ''}</strong></div><div class="toolbar"><span class="company-pill"><span>${icon('building')}</span>FM Demo Foods${icon('down')}</span>${themePicker()}<button class="icon-button" type="button" data-action="present" aria-label="Enter presentation fullscreen" title="Presentation fullscreen">${icon('expand')}</button></div></header><nav class="mobile-nav" aria-label="Mobile operations">${navigation}</nav><main class="main" id="main"></main><dialog class="dialog" id="review-dialog" aria-labelledby="dialog-title"></dialog><div id="toast" role="status" hidden></div>`;
    if (params.get('present') === '1') document.body.classList.add('presentation-mode');
    renderPage();
  }
  const pageHead = (eyebrow, title, description, action = '') => `<header class="page-head"><div><div class="eyebrow">${eyebrow}</div><h1>${title}</h1><p>${description}</p></div><div class="page-actions">${action || `<span class="date-chip">${icon('calendar')}23 October 2026</span>${button('Refresh', 'refresh', false, 'refresh')}`}</div></header>`;
  const tabs = () => `<nav class="tabs" aria-label="Page view"><a data-route="${page}" href="${href(page)}" class="${!insights ? 'active' : ''}">${icon(page === 'quality' ? 'layers' : 'factory')}Workspace</a><a data-route="${page}" data-view="insights" href="${href(page, 'insights')}" class="${insights ? 'active' : ''}">${icon('chart')}Insights</a></nav>`;
  const yields = [98.2, 97.6, 91.4, 98, 97.8, 88.5, 97.9, 98.4];
  function yieldChart(dark = false) {
    const points = yields.map((v, i) => `${35 + i * 82},${145 - (v - 85) * 9}`).join(' ');
    const color = dark ? 'var(--line)' : 'var(--primary)';
    return `<svg class="chart-svg" viewBox="0 0 650 185" role="img" aria-label="Actual yield for runs 201 to 208; runs 203 and 206 are flagged">${[0, 1, 2, 3].map(i => `<line x1="30" x2="622" y1="${10 + i * 45}" y2="${10 + i * 45}" stroke="${dark ? '#ffffff18' : 'var(--border)'}" stroke-dasharray="3 5"/><text x="0" y="${14 + i * 45}" style="font-size:9px">${100 - i * 5}%</text>`).join('')}<polyline points="${points}" fill="none" stroke="${color}" stroke-width="2.5" stroke-linejoin="round"/>${yields.map((v, i) => `<circle cx="${35 + i * 82}" cy="${145 - (v - 85) * 9}" r="${i === 2 || i === 5 ? 5 : 3.5}" fill="${i === 2 || i === 5 ? '#eda99f' : color}" stroke="${dark ? 'var(--hero)' : 'white'}" stroke-width="2"/><text x="${35 + i * 82}" y="177" text-anchor="middle">#${201 + i}</text>`).join('')}</svg><div class="chart-caption"><span><i class="dot" style="color:${color}"></i>Actual yield by run</span><span><i class="dot" style="color:#eda99f"></i>Flagged exception</span></div><div class="mobile-run-list">${yields.map((v, i) => `<div class="${i === 2 || i === 5 ? 'flag' : ''}"><span>#${201 + i}${i === 2 || i === 5 ? ' · Flagged' : ''}</span><strong>${v.toFixed(1)}%</strong></div>`).join('')}</div>`;
  }
  function outputBars() {
    return `<div class="sub-label" style="margin-top:0">Bulk production · kg</div><div class="bar-list">${[['Chilli Powder', '1,800 kg', 100], ['Garam Masala Bulk', '1,200 kg', 66]].map(([n, v, w]) => `<div class="bar-row"><div class="row-top"><span>${n}</span><strong>${v}</strong></div><div class="bar-track"><div class="bar-fill" style="width:${w}%"></div></div></div>`).join('')}</div><div class="sub-label">Finished goods · packs</div><div class="bar-list">${[['Garam Masala 50g', '24,000 packs', 100], ['Garam Masala 100g', '12,000 packs', 50]].map(([n, v, w]) => `<div class="bar-row"><div class="row-top"><span>${n}</span><strong>${v}</strong></div><div class="bar-track"><div class="bar-fill" style="width:${w}%;opacity:.6"></div></div></div>`).join('')}</div>`;
  }
  function qualityMix() {
    return `<div class="status-stack" aria-label="48 released, 8 quarantine, 4 hold, 3 rejected batches"><i style="width:76.19%;background:var(--good)"></i><i style="width:12.7%;background:#d7b575"></i><i style="width:6.35%;background:#8190ab"></i><i style="width:4.76%;background:var(--bad)"></i></div><div class="status-list">${[['Released', 'var(--good)', 48], ['Quarantine', '#b68b42', 8], ['Hold', '#8190ab', 4], ['Rejected', 'var(--bad)', 3]].map(([n, c, v]) => `<div class="status-line"><span><i class="dot" style="color:${c}"></i>${n}</span><strong>${v}<small>batches</small></strong></div>`).join('')}</div>`;
  }
  function attention() {
    const rows = [['shield', '', '12 batches need a decision', 'Review quarantined and held batches', 'quality'], ['clock', '', '54 batches approaching expiry', 'Stock expiring within the next 90 days', 'quality'], ['alert', 'red', '2 runs outside tolerance', 'Check yield exceptions before the next run', 'production']];
    return `<article class="card card-pad">${cardHead('Needs your attention', 'A little focus where it matters most.', '<span class="count">3 priorities</span>')}<div class="attention-list">${rows.map(([g, c, n, d, route]) => `<a class="attention-row" data-route="${route}" href="${href(route)}"><span class="attention-icon ${c}">${icon(g)}</span><span><strong>${n}</strong><p>${d}</p></span>${icon('chevron')}</a>`).join('')}</div><p class="mini-note">Company-scoped stock and quality decisions.</p></article>`;
  }
  function overview() {
    return pageHead('OPERATIONS AT A GLANCE', 'Plant overview', 'A considered view of every batch, from ingredients to dispatch.', `<label class="sr-only" for="period">Dashboard period</label><select id="period" data-period><option value="7">Last 7 days</option><option value="30" selected>Last 30 days</option><option value="90">Last 90 days</option></select>${button('Open production', 'open-production', true, 'arrow')}`) + `<section class="metric-grid" aria-label="Key performance indicators">${metric('Average actual yield', '97.4', '%', 'Across completed runs', 'chart', 'positive')}${metric('Awaiting quality', '12', 'batches', 'Ready for a decision', 'shield', 'warning')}${metric('Near expiry', '54', 'batches', 'Within 90 days', 'clock', 'warning')}${metric('Open work orders', '6', 'runs', 'Blending & packaging', 'factory')}</section><section class="split"><article class="hero"><div class="hero-head"><div><div class="eyebrow">PRODUCTION PERFORMANCE</div><h2>Consistency in every run.</h2><p>Actual yield across the eight most recent completed runs.</p></div><span class="hero-chip">28 completed runs</span></div><div class="hero-number">97.4<small>% average yield</small></div>${yieldChart(true)}</article>${attention()}</section><section class="equal section-gap"><article class="card card-pad">${cardHead('Output by item', 'Separate scales for bulk and finished goods.', `<a class="text-link" data-route="production" data-view="insights" href="${href('production', 'insights')}">View insights ${icon('upRight')}</a>`)}${outputBars()}</article><article class="card card-pad">${cardHead('Stock quality', '63 batches currently holding company stock.', badge('Company stock'))}${qualityMix()}<div class="expiry">${cardHead('Expiry horizon', 'Most urgent stock first.')}${[['0–7 days', 3, 9], ['8–30 days', 5, 16], ['31–60 days', 14, 44], ['61–90 days', 32, 100]].map(([n, v, w]) => `<div class="expiry-row"><span>${n}</span><div class="bar-track"><div class="bar-fill" style="width:${w}%;opacity:${n === '0–7 days' ? 1 : .35}"></div></div><strong>${v} batches</strong></div>`).join('')}</div></article></section><section class="workflow section-gap" aria-label="Quick workflows">${[['receiving', 'box', 'Receive ingredients', 'Supplier lots & quantities'], ['quality', 'shield', 'Review quality', 'Release, hold or reject'], ['production', 'factory', 'Complete a run', 'Output & process loss'], ['dispatch', 'truck', 'Prepare a dispatch', 'Eligible batches, FEFO first']].map(([r, g, t, d]) => `<a data-route="${r}" href="${href(r)}">${icon(g)}<span><strong>${t}</strong><small>${d}</small></span>${icon('arrow')}</a>`).join('')}</section>`;
  }
  const workOrders = [
    { id: 'WO-FM-0028', item: 'Garam Masala Bulk', type: 'Blending', status: 'In process', qty: 500, done: 0, uom: 'kg', bom: 'BOM-GM-004', code: 'GM-BULK', output: 487, loss: 13 },
    { id: 'WO-FM-0029', item: 'Garam Masala 50g', type: 'Packaging', status: 'Ready to start', qty: 2400, done: 0, uom: 'packs', bom: 'BOM-GM50-002', code: 'GM-50', output: 2400, loss: 0 },
    { id: 'WO-FM-0030', item: 'Turmeric Powder', type: 'Blending', status: 'In process', qty: 400, done: 100, uom: 'kg', bom: 'BOM-TUR-003', code: 'TUR', output: 294, loss: 6 },
  ];
  let selectedOrder = 0;
  const ingredients = {
    'GM-BULK': [['Chilli Powder', 300, 0, 'CHI-014', 450, '12 Jan 2027', 'kg'], ['Cumin', 125, 0, 'CUM-009', 180, '20 Feb 2027', 'kg'], ['Coriander', 50, 0, 'COR-021', 90, '11 Mar 2027', 'kg'], ['Black Pepper', 25, 0, 'PEP-006', 40, '15 Apr 2027', 'kg']],
    'GM-50': [['Garam Masala Bulk', 120, 0, 'GM-BULK-028', 300, '14 Feb 2027', 'kg'], ['50g Pouch', 2400, 0, 'POUCH-031', 6000, '—', 'units'], ['Printed Label', 2400, 0, 'LABEL-044', 8000, '—', 'units']],
    TUR: [['Turmeric Whole', 400, 100, 'TUR-015', 320, '08 May 2027', 'kg']],
  };
  function production() {
    if (insights) return productionInsights();
    const w = workOrders[selectedOrder];
    return pageHead('PRODUCTION WORKSPACE', 'Production', 'Released ingredients. Clear work orders. Confident completions.') + tabs() + `<section class="workspace"><aside><div class="queue-heading"><strong>Open work orders</strong><span class="count">3 shown</span></div><div class="order-list">${workOrders.map((o, i) => `<button class="order-card ${selectedOrder === i ? 'active' : ''}" data-order="${i}" type="button" aria-pressed="${selectedOrder === i}"><div class="order-line"><span class="order-code">${o.id}</span>${badge(o.type)}</div><h3>${o.item}</h3><p>${o.type} · ${num(o.qty)} ${o.uom} planned</p><div class="order-progress"><i style="width:${o.done / o.qty * 100}%"></i></div><div class="order-sub"><span>${o.status}</span><span>${o.done / o.qty * 100}% completed</span></div></button>`).join('')}</div></aside><div class="run-detail"><article class="card card-pad"><div class="run-title"><div><div class="small muted">${w.id} &nbsp; ${badge(w.status, kind(w.status))}</div><h2>${w.item}</h2><p>${w.type} &nbsp; / &nbsp; ${w.bom}</p></div><div class="ring"><svg viewBox="0 0 64 64" aria-hidden="true"><circle cx="32" cy="32" r="26" fill="none" stroke="var(--soft)" stroke-width="5"/><circle cx="32" cy="32" r="26" fill="none" stroke="var(--primary)" stroke-width="5" stroke-dasharray="${w.done / w.qty * 163} 163" stroke-linecap="round"/></svg><strong>${w.done / w.qty * 100}%</strong></div></div><div class="run-metrics"><div><label>Planned quantity</label><strong>${num(w.qty)} <small>${w.uom}</small></strong></div><div><label>Already produced</label><strong>${num(w.done)} <small>${w.uom}</small></strong></div><div><label>Remaining</label><strong style="color:var(--primary)">${num(w.qty - w.done)} <small>${w.uom}</small></strong></div></div></article><article class="card"><div class="card-pad" style="padding-bottom:0">${cardHead(w.type === 'Packaging' ? 'Bulk & packaging materials' : 'Ingredients & released lots', 'Available stock, earliest expiry first.', badge('Released stock', 'good'))}</div>${table(['Ingredient', 'Required', 'Consumed', 'Released lot', 'Available', 'Expiry'], ingredients[w.code].map(([n, qty, done, b, av, exp, uom]) => `<tr>${td('Ingredient', `<strong>${n}</strong>`)}${td('Required', `${num(qty)} ${uom}`, 'numeric')}${td('Consumed', `${num(done)} ${uom}`, 'numeric muted')}${td('Released lot', b)}${td('Available', `${num(av)} ${uom}`, 'numeric')}${td('Expiry', exp)}</tr>`), 'Required materials and released batch availability')}<div class="card-footer"><span class="muted">${icon('shield')} Only eligible released lots can be consumed.</span></div></article><form class="card card-pad" id="production-form">${cardHead('Finish this run', 'Record actual output and non-recoverable process loss.')}<div class="field-grid">${field('Good output', `<div class="unit-field"><input name="good" type="number" min="0.001" max="${w.qty - w.done}" step="any" value="${w.output}" required><span>${w.uom}</span></div>`)}${field('Process loss', `<div class="unit-field"><input name="loss" type="number" min="0" step="any" value="${w.loss}" required><span>${w.uom}</span></div>`)}${field('Output batch reference <span class="muted">(optional)</span>', '<input name="batch" placeholder="Automatic batch naming" maxlength="140">', 'Leave blank to let ERPNext name the output batch.', 'field-full')}</div><div class="form-footer"><p>Review the quantities before completing this Work Order.</p><div><button class="button primary" type="submit">${icon('check')}Review completion</button></div></div></form></div></section>`;
  }
  function productionInsights() {
    return pageHead('PRODUCTION INTELLIGENCE', 'Production insights', 'The detail behind your output, yield and process loss.') + tabs() + `<div class="metric-grid">${metric('Runs completed', '28', 'runs', 'Selected reporting period', 'factory')}${metric('Average actual yield', '97.4', '%', 'Completed-run measurement', 'chart', 'positive')}${metric('Open work orders', '6', 'runs', 'Current company workload', 'layers')}${metric('Yield exceptions', '2', 'runs', 'Outside policy tolerance', 'alert', 'negative')}</div><div class="equal"><article class="card card-pad">${cardHead('Actual yield by run', 'Recent runs, oldest first.')}${yieldChart()}<div class="mobile-run-list">${yields.map((v, i) => `<div><span>Run ${201 + i}</span><strong>${v}%</strong></div>`).join('')}</div></article><article class="card card-pad">${cardHead('Output composition', 'Quantity comparisons stay within the same unit.')}${outputBars()}</article></div><article class="card section-gap"><div class="card-pad" style="padding-bottom:0">${cardHead('Completed-run review', 'A focused view of flagged production records.', badge('2 exceptions', 'bad'))}</div>${table(['Work order', 'Product', 'Input', 'Good output', 'Process loss', 'Yield'], [['WO-FM-0203', 'Garam Masala Bulk', '500 kg', '457 kg', '43 kg', '91.4%'], ['WO-FM-0206', 'Chilli Powder', '400 kg', '354 kg', '46 kg', '88.5%']].map(r => `<tr>${r.map((v, i) => td(['Work order', 'Product', 'Input', 'Good output', 'Process loss', 'Yield'][i], i === 5 ? badge(v, 'bad') : escape(v))).join('')}</tr>`), 'Flagged production runs')}</article>`;
  }
  const batches = [
    { id: 'CHI-014', item: 'Chilli Powder', qty: 450, uom: 'kg', status: 'Quarantine', lot: 'SV-261001', supplier: 'Spice Valley', expiry: '12 Jan 2027', inspection: 'QI-0021' },
    { id: 'CUM-009', item: 'Cumin Whole', qty: 180, uom: 'kg', status: 'Quarantine', lot: 'RJ-99420', supplier: 'Rajasthan Agro', expiry: '20 Feb 2027', inspection: 'QI-0022' },
    { id: 'COR-021', item: 'Coriander', qty: 90, uom: 'kg', status: 'Hold', lot: 'GUJ-1102', supplier: 'Gujarat Spices', expiry: '11 Mar 2027', inspection: '' },
    { id: 'PEP-006', item: 'Black Pepper', qty: 40, uom: 'kg', status: 'Quarantine', lot: 'KL-8831', supplier: 'Malabar Coast', expiry: '15 Apr 2027', inspection: 'QI-0024' },
    { id: 'TUR-015', item: 'Turmeric Whole', qty: 320, uom: 'kg', status: 'Quarantine', lot: 'TN-4029', supplier: 'Salem Harvest', expiry: '08 May 2027', inspection: 'QI-0025' },
  ];
  let qualityFilter = 'All'; let qualitySearch = ''; let selectedBatch = 'CHI-014';
  const matchingBatches = () => batches.filter(b => (qualityFilter === 'All' || b.status === qualityFilter) && `${b.id} ${b.item} ${b.lot}`.toLowerCase().includes(qualitySearch.toLowerCase()));
  function batchRows() {
    return matchingBatches().map(b => `<tr class="selectable-row ${b.id === selectedBatch ? 'selected' : ''}" data-quality="${b.id}">${td('Batch', `<button class="text-button" data-quality="${b.id}" type="button">${b.id}</button>`)}${td('Item', `<strong>${b.item}</strong><small>${b.lot}</small>`)}${td('Status', badge(b.status, kind(b.status)))}${td('Quantity', `${b.qty} ${b.uom}`, 'numeric')}</tr>`).join('') || '<tr><td colspan="4"><div class="empty"><h3>No matching batches</h3><p>Try a different item, batch or supplier lot.</p></div></td></tr>';
  }
  function batchDetail() {
    const b = batches.find(b => b.id === selectedBatch);
    return `<article class="card card-pad detail-panel"><div class="detail-heading"><span class="item-icon">${icon('box')}</span><div><h2>${b.item}</h2><p>${b.id} &nbsp; ${badge(b.status, kind(b.status))}</p></div></div><div class="detail-facts"><div><span>Stock quantity</span><strong>${b.qty} ${b.uom}</strong></div><div><span>Expiry</span><strong>${b.expiry}</strong></div><div><span>Supplier</span><strong>${b.supplier}</strong></div><div><span>Supplier lot</span><strong>${b.lot}</strong></div></div><div class="mini-divider"></div><div class="section-title">MATCHING INSPECTION</div><label class="sr-only" for="inspection">Matching quality inspection</label><select id="inspection" style="width:100%"><option value="">Choose an inspection</option>${b.inspection ? `<option value="${b.inspection}" selected>${b.inspection} · Accepted</option>` : ''}</select><p class="muted small" style="font-size:9px;margin-top:8px">Release requires the accepted inspection for this exact item and batch when company policy requires it.</p><div class="mini-divider"></div><div class="section-title">DECISION HISTORY</div><div class="timeline"><div><strong>Quarantine recorded</strong><p>23 Oct 2026 · 09:15 · Receiving team</p></div><div><strong>${b.status === 'Hold' ? 'Placed on hold for review' : 'Incoming inspection recorded'}</strong><p>23 Oct 2026 · 11:30 · Quality officer</p></div></div><div class="mini-divider"></div><form id="quality-form">${field('Decision notes', '<textarea name="reason" placeholder="Explain the decision or required follow-up." rows="3"></textarea>', 'A reason is mandatory for Hold or Reject.')}<div class="decision-options">${[['Release', 'check'], ['Hold', 'pause'], ['Reject', 'close']].map(([t, g], i) => `<label><input type="radio" name="decision" value="${t}" ${i === 0 ? 'checked' : ''}>${icon(g)}${t}</label>`).join('')}</div><button class="button primary" style="width:100%;margin-top:17px" type="submit">Review decision ${icon('arrow')}</button></form></article>`;
  }
  function quality() {
    if (insights) return qualityInsights();
    return pageHead('QUALITY WORKSPACE', 'Quality', 'Every batch deserves a clear, considered decision.') + tabs() + `<section class="metric-grid">${metric('Awaiting a decision', '12', 'batches', 'Company-stock queue', 'shield', 'warning')}${metric('In quarantine', '8', 'batches', 'Inspection & review pending', 'box', 'warning')}${metric('Currently on hold', '4', 'batches', 'Follow-up required', 'pause')}${metric('Released in period', '41', 'batches', 'Audited decisions', 'check', 'positive')}</section><div class="filter-shell"><div class="filters">${['All', 'Quarantine', 'Hold'].map(t => `<button class="filter ${qualityFilter === t ? 'active' : ''}" type="button" data-filter="${t}" aria-pressed="${qualityFilter === t}">${t}${t === 'All' ? ' batches' : ''}</button>`).join('')}</div><label class="search">${icon('search')}<input id="quality-search" placeholder="Search batch, item or lot" aria-label="Search quality queue" value="${escape(qualitySearch)}"></label></div><section class="quality-grid"><article class="card"><div class="card-pad" style="padding-bottom:0">${cardHead('Batches awaiting review', 'Longest waiting first. Select a batch to review.', '<span class="count">5 shown</span>')}</div><div id="quality-results">${table(['Batch', 'Item / supplier lot', 'Status', 'Quantity'], [batchRows()], 'Pending quality batches')}</div><div class="card-footer"><span class="muted">Illustrative queue · 5 of 12 batches</span><span class="muted small">Company stock only</span></div></article><div id="batch-detail">${batchDetail()}</div></section>`;
  }
  function qualityInsights() {
    return pageHead('QUALITY INTELLIGENCE', 'Quality overview', 'A calm, complete view of stock disposition and release priorities.') + tabs() + `<section class="metric-grid">${metric('Batches holding stock', '63', 'batches', 'Current company inventory', 'layers')}${metric('Released stock', '48', 'batches', 'Eligible for policy checks', 'check', 'positive')}${metric('Pending quality', '12', 'batches', 'Quarantine & Hold', 'shield', 'warning')}${metric('Rejected stock', '3', 'batches', 'Consumption blocked', 'lock', 'negative')}</section><section class="equal"><article class="card card-pad">${cardHead('Stock disposition', 'Batch counts, never mixed stock quantities.')}${qualityMix()}</article><article class="card card-pad">${cardHead('Expiry exposure', 'Company-stock batches expiring within 90 days.')}<div class="chart-columns">${[['0–7d', 3], ['8–30d', 5], ['31–60d', 14], ['61–90d', 32]].map(([n, v]) => `<div class="chart-column" style="height:${v / 32 * 120 + 18}px"><i style="height:100%;opacity:${n === '0–7d' ? 1 : .5}"></i><strong>${v}</strong><span>${n}</span></div>`).join('')}</div><p class="mini-note">Counts are ordered by urgency, not by size.</p></article></section><section class="equal section-gap">${attention()}<article class="card card-pad">${cardHead('Release with confidence', 'One consistent, audited path for every batch.')}<div class="timeline" style="margin-top:25px"><div><strong>Match the inspection</strong><p>Confirm the exact item and batch.</p></div><div><strong>Review the context</strong><p>Check history, shelf life and supplier lot.</p></div><div><strong>Record the decision</strong><p>Release, hold or reject with actor and timestamp.</p></div></div><a class="button primary" style="margin-top:28px" data-route="quality" href="${href('quality')}">Open quality queue ${icon('arrow')}</a></article></section>`;
  }
  const purchaseOrders = {
    'PO-FM-0042': { supplier: 'Spice Valley Traders', date: '23 Oct 2026', warehouse: 'Raw Material Quarantine', items: [ { name: 'Chilli Powder', code: 'CP-001', ordered: 1000, received: 500, pending: 500, qty: 450, lot: 'SV-261001', mfg: '2026-10-01' }, { name: 'Cumin Whole', code: 'CUM-004', ordered: 500, received: 0, pending: 500, qty: 250, lot: 'SV-261002', mfg: '2026-10-04' }, { name: 'Turmeric Whole', code: 'TUR-002', ordered: 400, received: 100, pending: 300, qty: 0, lot: '', mfg: '' } ] },
    'PO-FM-0046': { supplier: 'Malabar Coast Spices', date: '22 Oct 2026', warehouse: 'Raw Material Quarantine', items: [ { name: 'Black Pepper', code: 'PEP-006', ordered: 100, received: 0, pending: 100, qty: 40, lot: 'KL-8831', mfg: '2026-10-03' } ] },
  };
  let selectedPO = 'PO-FM-0042';
  function receiving() {
    const po = purchaseOrders[selectedPO];
    return pageHead('RECEIVING WORKSPACE', 'Goods in', 'Give every ingredient a traceable beginning.') + `<article class="card card-pad"><div class="order-summary"><div>${field('PURCHASE ORDER', `<select id="purchase-order">${Object.keys(purchaseOrders).map(id => `<option ${id === selectedPO ? 'selected' : ''}>${id}</option>`).join('')}</select>`)}</div><div><label>SUPPLIER</label><strong>${po.supplier}</strong><p>Purchase order supplier</p></div><div><label>ORDER DATE</label><strong>${po.date}</strong><p>Outstanding material</p></div><div><label>DESTINATION</label><strong>${po.warehouse}</strong><p>Controlled quality routing</p></div></div><div style="margin-top:22px">${info('Inspection-required material remains in quarantine until an authorized quality release.', 'warn')}</div></article><form id="receiving-form"><article class="card card-pad section-gap">${cardHead('Purchase order lines', 'Receive quantities, capture supplier lots and record manufacturing dates.', badge(`${po.items.length} items`))}<div class="receipt-lines">${po.items.map((item, i) => `<div class="receipt-item"><div class="receipt-item-head"><div class="item-cell"><span class="item-icon">${icon('leaf')}</span><div><h3>${item.name}</h3><p>${item.code} &nbsp; · &nbsp; Ordered ${num(item.ordered)} kg &nbsp; · &nbsp; Received ${num(item.received)} kg</p></div></div>${badge(`${num(item.pending)} kg outstanding`)}</div><div class="receipt-inputs">${field('Receive quantity', `<div class="unit-field"><input type="number" data-receive-qty="${i}" name="qty-${i}" min="0" max="${item.pending}" step="any" value="${item.qty}" required><span>kg</span></div>`)}${field('Supplier lot', `<input name="lot-${i}" data-supplier-lot placeholder="Scan or enter supplier lot" value="${item.lot}">`)}${field('Manufacturing date', `<input type="date" name="mfg-${i}" value="${item.mfg}" max="2026-10-23">`)}</div></div>`).join('')}</div><div style="margin-top:22px">${info('Keyboard scanners enter lot text. Pressing Enter in a supplier-lot field never posts the receipt.')}</div></article><div class="card bottom-summary section-gap"><div><h3 id="receiving-total">${po.items.filter(i => i.qty > 0).length} lines · ${num(po.items.reduce((s, i) => s + i.qty, 0))} kg to receive</h3><p>Review the supplier lots and quantities before posting.</p></div><div><button class="button primary" type="submit">Review receipt ${icon('arrow')}</button></div></div></form>`;
  }
  const picks = [
    { batch: 'GM50-021', item: 'Garam Masala 50g', status: 'Released', expiry: '14 Feb 2027', shelf: 62, available: 72, qty: 48, required: 48 },
    { batch: 'GM100-009', item: 'Garam Masala 100g', status: 'Released', expiry: '20 Feb 2027', shelf: 65, available: 36, qty: 24, required: 24 },
    { batch: 'GM50-008', item: 'Garam Masala 50g', status: 'Hold', expiry: '18 Jan 2027', shelf: 58, available: 50, qty: 0, required: 0 },
  ];
  function dispatch() {
    return pageHead('DISPATCH WORKSPACE', 'Dispatch', 'The right stock, in the right order, for every customer.') + `<article class="card card-pad"><div class="order-summary"><div><label>SALES ORDER</label><strong>SO-FM-0036</strong><p>2 outstanding item lines</p></div><div><label>CUSTOMER</label><strong>Apex Retailers</strong><p>Finished goods delivery</p></div><div><label>DELIVERY DATE</label><strong>25 Oct 2026</strong><p>Sales order commitment</p></div><div><label>WAREHOUSE</label><strong>Finished Goods</strong><p>Company dispatch stock</p></div></div><div class="mini-divider" style="margin-bottom:13px"></div><div class="filters">${badge('FEFO · Block', 'neutral')}${badge('Minimum shelf life · 30%', 'neutral')}<span class="muted" style="font-size:9px;margin-left:auto">Policy checks remain authoritative.</span></div></article><article class="card card-pad section-gap">${cardHead('Sales quantity → stock quantity', 'Allocate in packs, with the sales conversion always visible.')}<div class="conversion-grid">${[['Garam Masala 50g', 2, 48], ['Garam Masala 100g', 1, 24]].map(([n, q, v]) => `<div class="conversion"><h3>${n}</h3><div class="conversion-row"><p><strong style="font-size:11px;font-family:var(--body);letter-spacing:0">${q} ${q === 1 ? 'carton' : 'cartons'}</strong> × 24 packs</p><strong>${v} <small>packs required</small></strong></div></div>`).join('')}</div></article><article class="card scan-card section-gap">${icon('barcode')}<div><strong>Scan a batch</strong><p>Enter focuses the matching available quantity field.</p></div><form class="scan-input" id="scan-form"><input id="scan-batch" placeholder="Batch ID, then Enter" aria-label="Scan batch ID" autocomplete="off"><button class="button" type="submit">Find ${icon('arrow')}</button></form></article><p id="scan-message" class="scan-message" role="status" hidden></p><form id="dispatch-form"><article class="card section-gap"><div class="card-pad" style="padding-bottom:0">${cardHead('FEFO batch allocations', 'Released batches, ordered by earliest expiry.', badge('Stock UOM · packs'))}</div>${table(['Batch / item', 'Quality', 'Expiry', 'Shelf life', 'Available', 'Pick · packs'], picks.map((p, i) => `<tr class="${p.status === 'Hold' ? 'disabled-row' : ''}">${td('Batch / item', `<strong>${p.batch}</strong><small>${p.item}</small>${p.status === 'Hold' ? '<small class="negative">Blocked · held stock</small>' : '<small>Earliest eligible expiry</small>'}`)}${td('Quality', badge(p.status, kind(p.status)))}${td('Expiry', p.expiry)}${td('Shelf life', `<div class="shelf"><span>${p.shelf}%</span><div class="bar-track"><div class="bar-fill" style="width:${p.shelf}%"></div></div></div>`)}${td('Available', `${p.available} packs`, 'numeric')}${td('Pick · packs', `<input class="pick-input" type="number" min="0" max="${Math.min(p.available, p.required)}" step="1" value="${p.qty}" data-pick="${i}" data-batch="${p.batch}" aria-label="Picked packs from ${p.batch}" ${p.status === 'Hold' ? 'disabled' : ''} required><span class="pick-uom">packs</span>`, 'numeric')}</tr>`), 'FEFO stock allocations')}</article><div class="card bottom-summary section-gap"><div><h3 id="dispatch-total">2 lines · 72 packs allocated</h3><p>Suggestions do not reserve stock. Eligibility is rechecked on submit.</p></div><div><button class="button primary" type="submit">Review dispatch ${icon('arrow')}</button></div></div></form>`;
  }
  let recallSearched = true; let recallQuery = 'CHI-014';
  function recallResults() {
    if (!recallSearched) return `<article class="card empty section-gap">${icon('trace')}<h2>Every batch has a story.</h2><p>Trace an exact batch ID to see affected stock and customer deliveries.</p><button class="button" style="margin-top:20px" type="button" data-action="sample-trace">Explore sample · CHI-014 ${icon('arrow')}</button></article>`;
    if (!['CHI-014', 'GM-BULK-028', 'GM50-021', 'GM100-009'].includes(recallQuery)) return `<article class="card empty section-gap">${icon('search')}<h2>No batch found</h2><p>“${escape(recallQuery)}” is not in this illustrative dataset.</p><button class="button" style="margin-top:20px" type="button" data-action="sample-trace">Use sample CHI-014</button></article>`;
    const all = [['CHI-014', 'Chilli Powder', 'SV-261001', 'Quarantine'], ['GM-BULK-028', 'Garam Masala Bulk', 'Internal batch', 'Hold'], ['GM50-021', 'Garam Masala 50g', 'Internal batch', 'Released'], ['GM100-009', 'Garam Masala 100g', 'Internal batch', 'Released']];
    const affected = recallQuery === 'CHI-014' ? all : all.filter(r => r[0] === recallQuery || (recallQuery === 'GM-BULK-028' && ['GM50-021', 'GM100-009'].includes(r[0])));
    const deliveries = [['DN-0032', 'Apex Retailers', 'GM50-021', '24 Oct 2026', 48, 'Dispatch'], ['DN-0033', 'Metro Stores', 'GM100-009', '24 Oct 2026', 24, 'Dispatch'], ['DN-RET-0004', 'Metro Stores', 'GM100-009', '25 Oct 2026', -6, 'Return']].filter(r => affected.some(a => a[0] === r[2]));
    return `<section class="trace-summary section-gap"><article class="card card-pad source-batch"><span class="item-icon">${icon('box')}</span><div><label>SOURCE BATCH</label><strong>${escape(recallQuery)}</strong><p>${affected.find(a => a[0] === recallQuery)?.[1] || 'Batch record'}</p></div></article><article class="card metric"><span class="metric-label">Affected batches</span><div class="metric-value" style="margin-top:9px">${affected.length}</div><p class="metric-note">Within this trace result</p></article><article class="card metric"><span class="metric-label">Delivery records</span><div class="metric-value" style="margin-top:9px">${deliveries.length}</div><p class="metric-note">Includes marked returns</p></article></section><div class="section-gap">${info('Illustrative incomplete-result state: the trace reached its six-level / 200-batch limit. Review any remaining batches before acting.', 'warn')}</div><article class="card section-gap"><div class="card-pad" style="padding-bottom:0">${cardHead('Affected batches', 'Quality status remains visible throughout the investigation.', `<a class="text-link" data-route="quality" href="${href('quality')}">Open quality ${icon('upRight')}</a>`)}</div>${table(['Batch', 'Item', 'Supplier lot', 'Quality status'], affected.map(r => `<tr>${td('Batch', `<strong>${r[0]}</strong>`)}${td('Item', r[1])}${td('Supplier lot', r[2])}${td('Quality status', badge(r[3], kind(r[3])))}</tr>`), 'Affected batch records')}</article><article class="card section-gap"><div class="card-pad" style="padding-bottom:0">${cardHead('Customer deliveries & returns', 'Affected quantities in each item’s stock UOM.')}</div>${deliveries.length ? table(['Delivery', 'Customer', 'Batch', 'Date', 'Stock quantity', 'Type'], deliveries.map(r => `<tr>${td('Delivery', `<strong>${r[0]}</strong>`)}${td('Customer', r[1])}${td('Batch', r[2])}${td('Date', r[3])}${td('Stock quantity', `<span class="${r[4] < 0 ? 'negative' : ''}">${r[4] > 0 ? '+' : ''}${r[4]} packs</span>`, 'numeric')}${td('Type', badge(r[5], r[5] === 'Return' ? 'warn' : 'neutral'))}</tr>`), 'Affected deliveries and returns') : '<div class="empty"><p>No deliveries for this batch in the sample.</p></div>'}</article>`;
  }
  function recall() {
    return pageHead('BATCH INVESTIGATION', 'Recall & traceability', 'Follow affected batches to the customers they reached.', `${badge('Read-only investigation')}<a class="button" data-route="quality" href="${href('quality')}">Open quality ${icon('arrow')}</a>`) + `<article class="card card-pad"><form class="trace-search" id="recall-form"><div><label class="search">${icon('search')}<input id="recall-batch" name="batch" placeholder="Scan or enter an exact batch ID" aria-label="Batch ID to trace" value="${escape(recallQuery)}" required autocomplete="off"></label></div><button class="button primary" type="submit">Trace batch ${icon('trace')}</button></form><p class="muted" style="font-size:9px;margin-top:12px">Read-only results. Hold decisions use the audited Quality workflow.</p></article><div id="recall-results">${recallResults()}</div>`;
  }
  function renderPage() {
    const renderers = { overview, production, quality, receiving, dispatch, recall };
    document.querySelector('#main').innerHTML = (renderers[page] || overview)() + footer();
    applyAppearance();
  }
  const galleryRoutes = [ ['overview', '', 'Plant overview'], ['production', '', 'Production workspace'], ['production', 'insights', 'Production insights'], ['quality', '', 'Quality workspace'], ['quality', 'insights', 'Quality overview'], ['receiving', '', 'Goods in'], ['dispatch', '', 'Dispatch'], ['recall', '', 'Recall & traceability'] ];
  function gallery() {
    document.body.className = 'gallery-body';
    document.body.innerHTML = `<header class="gallery-top"><a class="brand" href="index.html"><span class="brand-logo">FMC</span><span><span class="brand-name">FMC Studio</span><small>The food manufacturing workspace.</small></span></a><div class="toolbar">${themePicker()}<a class="button primary" id="launch-preview" data-presentation="true" data-route="overview" href="${href('overview')}" target="_blank" rel="noopener">Launch presentation ${icon('upRight')}</a></div></header><main class="gallery-main"><header class="gallery-heading"><div><div class="eyebrow" style="color:var(--primary)">FMC · PRESENTATION EDITION</div><h1>Designed for the way<br>your factory works.</h1><p>A complete, connected workspace. Explore six operational pages, three dashboard experiences and five considered color palettes.</p></div><label class="field" style="min-width:200px">Typography pairing<select data-font-pick><option value="studio" ${font === 'studio' ? 'selected' : ''}>Studio · Jakarta Sans + Inter</option><option value="humanist" ${font === 'humanist' ? 'selected' : ''}>Humanist · Inter + Jakarta Sans</option></select></label></header><section class="theme-showcase" aria-label="Select color palette">${Object.entries(themes).map(([key, t]) => `<button class="theme-tile" type="button" data-theme-pick="${key}" aria-pressed="${key === theme}">${swatches(key)}<span><strong>${t.name}</strong><small>${t.note}</small></span></button>`).join('')}</section><section class="demo-frame" aria-label="Live design preview"><div class="frame-toolbar"><label><span class="sr-only">Select page or dashboard</span><select id="gallery-screen">${galleryRoutes.map(([id, view, n], i) => `<option value="${i}">${n}</option>`).join('')}</select></label><div class="device-controls"><button class="active" type="button" data-device="desktop" aria-pressed="true">Desktop</button><button type="button" data-device="phone" aria-pressed="false">Phone</button><a class="icon-button" id="open-frame" data-route="overview" href="${href('overview')}" target="_blank" rel="noopener" aria-label="Open preview in new tab">${icon('upRight')}</a></div></div><div class="frame-stage" id="frame-stage"><iframe title="FMC interactive design preview" id="demo-frame" allowfullscreen src="${href('overview')}"></iframe></div></section><section class="gallery-pages" aria-label="All pages">${pages.map(([key, n, glyph]) => `<a class="gallery-page" data-route="${key}" href="${href(key)}">${icon(glyph)}<span><h3>${n}</h3><p>${({ overview: 'Your operation, in focus.', production: 'Every run, clearly managed.', quality: 'Considered batch decisions.', receiving: 'A traceable beginning.', dispatch: 'The right stock, every time.', recall: 'From batch to customer.' })[key]}</p></span>${icon('upRight')}</a>`).join('')}</section><footer class="gallery-note"><span>Interactive design preview · Illustrative data · No ERPNext records are written.</span><span>Locally hosted fonts &amp; assets · Presentation-ready offline</span></footer></main><div id="toast" role="status" hidden></div>`;
    applyAppearance();
    document.querySelector('#demo-frame').addEventListener('load', () => applyAppearance());
  }
  let toastTimeout;
  function toast(message) {
    const el = document.querySelector('#toast'); el.textContent = message; el.className = 'toast'; el.hidden = false;
    clearTimeout(toastTimeout); toastTimeout = setTimeout(() => { el.hidden = true; }, 3800);
  }
  function review(title, description, entries) {
    const dialog = document.querySelector('#review-dialog');
    dialog.innerHTML = `<div class="dialog-head"><div><h2 id="dialog-title">${escape(title)}</h2><p>${escape(description)}</p></div><button class="icon-button" type="button" data-action="close-dialog" aria-label="Close review">${icon('close')}</button></div><div class="dialog-body"><dl>${entries.map(([key, value]) => `<dt>${escape(key)}</dt><dd>${escape(value)}</dd>`).join('')}</dl><div class="mini-divider"></div>${info('This is a design preview. No receipt, quality decision or stock transaction will be posted.')}</div><div class="dialog-foot"><small>Review flow · Illustrative data</small>${button('Back to workspace', 'close-dialog', true, 'check')}</div>`;
    dialog.showModal();
  }
  function receivingTotal() {
    const inputs = [...document.querySelectorAll('[data-receive-qty]')];
    const sum = inputs.reduce((s, el) => s + Math.max(0, Number(el.value) || 0), 0);
    document.querySelector('#receiving-total').textContent = `${inputs.filter(el => Number(el.value) > 0).length} lines · ${num(sum)} kg to receive`;
  }
  function pickTotal() {
    const selected = [...document.querySelectorAll('[data-pick]:not(:disabled)')];
    const sum = selected.reduce((s, el) => s + Math.max(0, Number(el.value) || 0), 0);
    document.querySelector('#dispatch-total').textContent = `${selected.filter(el => Number(el.value) > 0).length} lines · ${num(sum)} packs allocated`;
  }
  function scanBatch() {
    const scan = document.querySelector('#scan-batch');
    const target = [...document.querySelectorAll('input[data-batch]:not(:disabled)')].find(el => el.dataset.batch.toLowerCase() === scan.value.trim().toLowerCase());
    const message = document.querySelector('#scan-message');
    if (target) { target.focus(); target.select(); message.hidden = true; }
    else { message.textContent = 'This batch is not available for picking on this order.'; message.hidden = false; }
    scan.value = '';
  }
  document.addEventListener('click', async event => {
    const themeButton = event.target.closest('[data-theme-pick]');
    if (themeButton) { theme = themeButton.dataset.themePick; applyAppearance(); if (parent !== window) parent.postMessage({ type: 'fmc:appearance-change', theme, font }, '*'); return; }
    const order = event.target.closest('[data-order]');
    if (order) { selectedOrder = Number(order.dataset.order); renderPage(); return; }
    const filter = event.target.closest('[data-filter]');
    if (filter) { qualityFilter = filter.dataset.filter; renderPage(); return; }
    const batch = event.target.closest('[data-quality]');
    if (batch) { selectedBatch = batch.dataset.quality; document.querySelector('#batch-detail').innerHTML = batchDetail(); document.querySelector('#quality-results tbody').innerHTML = batchRows(); return; }
    const device = event.target.closest('[data-device]');
    if (device) {
      document.querySelector('#frame-stage').classList.toggle('phone', device.dataset.device === 'phone');
      document.querySelectorAll('[data-device]').forEach(el => { el.classList.toggle('active', el === device); el.setAttribute('aria-pressed', String(el === device)); }); return;
    }
    const action = event.target.closest('[data-action]')?.dataset.action;
    if (action === 'close-dialog') document.querySelector('#review-dialog').close();
    if (action === 'refresh') toast('Illustrative data refreshed. This preview is not connected to your site.');
    if (action === 'open-production') location.href = href('production');
    if (action === 'sample-trace') { recallQuery = 'CHI-014'; recallSearched = true; renderPage(); }
    if (action === 'present') {
      document.body.classList.toggle('presentation-mode');
      try { if (!document.fullscreenElement) await document.documentElement.requestFullscreen(); else await document.exitFullscreen(); }
      catch { toast('Presentation view is ready. Your browser may require manual fullscreen.'); }
    }
  });
  document.addEventListener('change', event => {
    if (event.target.matches('[data-font-pick]')) { font = event.target.value; applyAppearance(); if (parent !== window) parent.postMessage({ type: 'fmc:appearance-change', theme, font }, '*'); }
    if (event.target.matches('input[name=decision]')) { const reason = document.querySelector('#quality-form textarea'); reason.setCustomValidity(''); }
    if (event.target.id === 'purchase-order') { selectedPO = event.target.value; renderPage(); }
    if (event.target.matches('[data-period]')) toast('Period selected. Figures are illustrative in this design preview.');
    if (event.target.id === 'gallery-screen') {
      const [name, view] = galleryRoutes[Number(event.target.value)];
      const url = href(name, view); document.querySelector('#demo-frame').src = url; document.querySelector('#open-frame').href = url; document.querySelector('#open-frame').dataset.route = name; document.querySelector('#open-frame').dataset.view = view;
      const launch = document.querySelector('#launch-preview'); launch.dataset.route = name; launch.dataset.view = view; launch.href = url + '&present=1';
    }
  });
  document.addEventListener('input', event => {
    if (event.target.id === 'quality-search') { qualitySearch = event.target.value; document.querySelector('#quality-results tbody').innerHTML = batchRows(); }
    if (event.target.matches('[data-receive-qty]')) receivingTotal();
    if (event.target.matches('[data-pick]')) pickTotal();
  });
  document.addEventListener('keydown', event => {
    if (event.target.matches('[data-supplier-lot]') && event.key === 'Enter') event.preventDefault();
    if (event.key === 'Escape') document.querySelectorAll('.theme-picker[open]').forEach(el => { el.open = false; });
    if (params.get('present') === '1' && !event.target.closest('input,textarea,select,dialog,button') && ['ArrowLeft', 'ArrowRight'].includes(event.key)) {
      const index = galleryRoutes.findIndex(([r, view]) => r === page && Boolean(view) === insights);
      const next = galleryRoutes[(index + (event.key === 'ArrowRight' ? 1 : galleryRoutes.length - 1)) % galleryRoutes.length];
      if (next) location.href = href(next[0], next[1]);
    }
  });
  document.addEventListener('submit', event => {
    const form = event.target;
    if (!['production-form', 'quality-form', 'receiving-form', 'scan-form', 'dispatch-form', 'recall-form'].includes(form.id)) return;
    event.preventDefault();
    if (!form.reportValidity()) return;
    const data = new FormData(form);
    if (form.id === 'production-form') {
      const w = workOrders[selectedOrder];
      review('Review production completion', 'Check the selected run and output quantities.', [['Work order', w.id], ['Product', w.item], ['Good output', `${num(data.get('good'))} ${w.uom}`], ['Process loss', `${num(data.get('loss'))} ${w.uom}`], ['Output batch', data.get('batch') || 'Automatic naming']]);
    }
    if (form.id === 'quality-form') {
      const reason = String(data.get('reason') || '').trim(); const decision = data.get('decision');
      if (decision !== 'Release' && !reason) { const input = form.elements.reason; input.setCustomValidity('Enter a reason for Hold or Reject.'); input.reportValidity(); input.addEventListener('input', () => input.setCustomValidity(''), { once: true }); return; }
      if (decision === 'Release' && !document.querySelector('#inspection').value) { toast('Select an accepted inspection for this batch before reviewing Release.'); return; }
      review('Review quality decision', 'This decision will be an audited record in the implemented product.', [['Batch', selectedBatch], ['Decision', decision], ['Inspection', document.querySelector('#inspection').value || 'None'], ['Notes', reason || 'No additional notes']]);
    }
    if (form.id === 'receiving-form') {
      const po = purchaseOrders[selectedPO]; const lines = po.items.map((item, i) => [item, i, Number(data.get(`qty-${i}`))]).filter(([, , q]) => q > 0);
      if (!lines.length) { toast('Enter a positive receive quantity for at least one line.'); return; }
      const missing = lines.find(([, i]) => !String(data.get(`lot-${i}`) || '').trim());
      if (missing) { form.elements[`lot-${missing[1]}`].focus(); toast('Capture the supplier lot for each selected line.'); return; }
      review('Review goods receipt', 'Verify quantities and lots before creating the receipt.', [['Purchase order', selectedPO], ['Supplier', po.supplier], ...lines.map(([item, i, q]) => [item.name, `${num(q)} kg · ${data.get(`lot-${i}`)}`]), ['Destination', po.warehouse]]);
    }
    if (form.id === 'scan-form') scanBatch();
    if (form.id === 'dispatch-form') {
      const quantities = [...document.querySelectorAll('[data-pick]:not(:disabled)')].filter(el => Number(el.value) > 0);
      if (!quantities.length) { toast('Allocate a positive stock quantity before reviewing the dispatch.'); return; }
      review('Review dispatch', 'Stock quantities are shown in packs. Suggestions do not reserve stock.', [['Sales order', 'SO-FM-0036'], ['Customer', 'Apex Retailers'], ...quantities.map(el => [el.dataset.batch, `${num(el.value)} packs`]), ['FEFO policy', 'Block · minimum shelf life 30%']]);
    }
    if (form.id === 'recall-form') { recallQuery = String(data.get('batch')).trim().toUpperCase(); recallSearched = true; renderPage(); }
  });
  window.addEventListener('message', event => {
    if (page === 'gallery' && event.source === document.querySelector('#demo-frame')?.contentWindow && event.data?.type === 'fmc:appearance-change') {
      if (themes[event.data.theme]) theme = event.data.theme;
      if (['studio', 'humanist'].includes(event.data.font)) font = event.data.font;
      applyAppearance(); return;
    }
    if (event.source !== parent || event.data?.type !== 'fmc:appearance') return;
    if (themes[event.data.theme]) theme = event.data.theme;
    if (['studio', 'humanist'].includes(event.data.font)) font = event.data.font;
    applyAppearance();
  });
  document.documentElement.dataset.theme = theme; document.documentElement.dataset.font = font;
  if (page === 'gallery') gallery(); else shell();
})();
