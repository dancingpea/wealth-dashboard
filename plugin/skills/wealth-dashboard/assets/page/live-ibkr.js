(function () {
  /* Optional live section for Interactive Brokers: four live queries on the viewer's own IBKR connector.
     Included only when the page is built with `wealth.py page --live ibkr`. */
  const asJson = (a) => typeof a === 'string' ? JSON.parse(a) : a;
  const splitDesc = (desc) => { const s = String(desc || ''); const at = s.indexOf(' @'); return at >= 0 ? [s.slice(0, at), s.slice(at + 2)] : [s, '']; };
  dash.loader('ibkr_positions', {
    description: 'One row per IBKR position; the exchange is the part of the description after "@".',
    fn: ({ answer }) => {
      const a = asJson(answer); if (a && a.error) throw new Error(a.error);
      return ((a && a.positions) || []).map(p => { const [symbol, exchange] = splitDesc(p.contract_description); return {
        symbol, exchange, contract_id: String(p.contract_id), quantity: Number(p.position), price: Number(p.market_price), market_value: Number(p.market_value),
        currency: p.currency, average_price: Number(p.average_price), unrealized_pnl: Number(p.unrealized_pnl), daily_pnl: Number(p.daily_pnl), asset_class: p.asset_class }; });
    }
  });
  dash.loader('ibkr_balances', {
    description: 'One row per currency from IBKR balances; BASE is the account total in its base currency.',
    fn: ({ answer }) => {
      const a = asJson(answer); if (a && a.error) throw new Error(a.error);
      return ((a && a.balances) || []).map(b => ({ currency: b.currency, cash_balance: Number(b.cash_balance), net_liquidation_value: Number(b.net_liquidation_value),
        stock_market_value: Number(b.stock_market_value), unrealized_pnl: Number(b.unrealized_pnl), exchange_rate: Number(b.exchange_rate) }));
    }
  });
  dash.loader('ibkr_performance', {
    description: 'The 12-month series from IBKR performance: one row per day with account value and cumulative return.',
    fn: ({ answer }) => {
      const a = asJson(answer); if (a && a.error) throw new Error(a.error);
      const acct = Object.values((a && a.accounts) || {})[0];
      const p = acct && acct.periods && acct.periods['1Y'];
      if (!p) throw new Error('The performance answer has no 1Y period');
      const day = s => `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}`;
      const rows = [];
      if (Number(p.start_nav) > 0) rows.push({ date: day(String(p.start_date)), nav: Number(p.start_nav), cps: 0 });
      p.dates.forEach((d, i) => rows.push({ date: day(String(d)), nav: Number(p.nav[i]), cps: Number(p.cps[i]) }));
      return { data: rows, columns: ['date', 'nav', 'cps'], meta: [{ label: 'Return method', value: String(a.portfolio_measure || '') }, { label: 'Base currency', value: String(acct.base_currency || '') }] };
    }
  });
  dash.loader('ibkr_history', {
    description: 'For each IBKR position, weekly closing prices over six months from get_price_history.',
    fn: async ({ answer, call }) => {
      const a = asJson(answer); if (a && a.error) throw new Error(a.error);
      const rows = [], missing = [];
      for (const p of ((a && a.positions) || [])) {
        const [symbol, exchange] = splitDesc(p.contract_description);
        const args = { contract_id: Number(p.contract_id), security_type: 'STK', step: 'ONE_WEEK', period: 'SIX_MONTHS', outside_rth: false };
        if (exchange) args.exchange = exchange;
        let h;
        try { h = asJson(await call('get_price_history', args)); } catch (e) { missing.push(symbol); continue; }
        if (!h || h.error || !Array.isArray(h.time)) { missing.push(symbol + (h && h.error ? ': ' + h.error : '')); continue; }
        h.time.forEach((t, i) => rows.push({ symbol, date: String(t).slice(0, 10), close: Number(h.close[i]) }));
      }
      return { data: rows, columns: ['symbol', 'date', 'close'], meta: missing.length ? [{ label: 'No price history', value: missing.join('; ') }] : [] };
    }
  });
  dash.calc('ibkr_positions_base', {
    inputs: ['ibkr_positions', 'ibkr_balances'], title: 'IBKR positions in base currency',
    description: "Each position's value, cost and profit in the account's base currency at IBKR's current exchange rate, and its weight among the positions.",
    fn: (ibkr_positions, ibkr_balances) => {
      const fx = {}; for (const b of ibkr_balances) fx[b.currency] = Number(b.exchange_rate);
      const rows = ibkr_positions.map(p => { const rate = fx[p.currency] === undefined ? 1 : fx[p.currency]; const cost = p.average_price * p.quantity;
        return { symbol: p.symbol, currency: p.currency, quantity: p.quantity, price: p.price, average_price: p.average_price, value_base: p.market_value * rate,
          cost_base: cost * rate, pnl_base: p.unrealized_pnl * rate, pnl_pct: cost ? p.unrealized_pnl / cost : null, day_pnl_base: p.daily_pnl * rate }; });
      const total = rows.reduce((s, r) => s + r.value_base, 0); rows.forEach(r => { r.weight = total ? r.value_base / total : 0; });
      return rows.sort((x, y) => y.value_base - x.value_base);
    }
  });
  dash.calc('ibkr_kpis', {
    inputs: ['ibkr_balances', 'ibkr_performance', 'ibkr_positions_base'], title: 'IBKR headline figures',
    description: "Net value, positions and cash from IBKR's base-currency balance; this year's and 12-month time-weighted return; today's change.",
    fn: (ibkr_balances, ibkr_performance, ibkr_positions_base) => {
      const base = ibkr_balances.find(b => b.currency === 'BASE') || {};
      const last = ibkr_performance[ibkr_performance.length - 1] || { date: '', cps: null };
      const before = ibkr_performance.filter(r => r.date < String(last.date).slice(0, 4) + '-01-01'); const yStart = before[before.length - 1];
      return [{ as_of: last.date, net_value: base.net_liquidation_value, shares_value: base.stock_market_value, cash: base.cash_balance, positions: ibkr_positions_base.length,
        unrealized_pnl: base.unrealized_pnl, day_pnl: ibkr_positions_base.reduce((s, r) => s + r.day_pnl_base, 0),
        return_ytd: yStart && last.cps != null ? (1 + last.cps) / (1 + yStart.cps) - 1 : null, return_1y: last.cps }];
    }
  });

  let sort = { key: 'value_base', dir: -1 };
  const K = () => window.wdKit;
  const cols = () => { const k = K(); return [
    { key: 'symbol' }, { key: 'quantity', cls: 'pt-r pt-hide-narrow', fmt: q => d3.format(',.4~f')(q) },
    { key: 'price', cls: 'pt-r pt-hide-narrow', fmt: (q, row) => k.priceTxt(q, row.currency) },
    { key: 'value_base', cls: 'pt-r', fmt: q => k.fullAmt(q) }, { key: 'weight', cls: 'pt-r pt-hide-narrow', fmt: q => k.pct(q) },
    { key: 'pnl_base', cls: 'pt-r', fmt: q => k.signedFull(q), tone: q => q < 0 ? 'pt-down' : 'pt-up' },
    { key: 'pnl_pct', cls: 'pt-r', fmt: q => q == null ? '—' : k.signedPct(q), tone: q => q == null ? '' : q < 0 ? 'pt-down' : 'pt-up' },
    { key: 'day_pnl_base', cls: 'pt-r pt-hide-narrow', fmt: q => k.signedFull(q), tone: q => q < 0 ? 'pt-down' : 'pt-up' }
  ]; };
  const sortRows = rows => rows.sort((a, b) => { const x = a[sort.key], y = b[sort.key]; if (typeof x === 'string') return sort.dir * String(x).localeCompare(String(y)); return sort.dir * ((x == null ? -Infinity : x) - (y == null ? -Infinity : y)); });
  function drawMultiples() {
    const k = K(); const box = document.getElementById('ibkr-mini'); if (!box) return;
    const pos = dash.data('ibkr_positions_base'), hist = dash.data('ibkr_history'); box.replaceChildren();
    if (pos.status !== 'ok' || hist.status !== 'ok') {
      const bad = [pos, hist].find(d => d.status !== 'ok' && d.status !== 'loading');
      if (bad) { box.classList.remove('dash-skeleton'); k.failLine(box, bad.status === 'connect' ? 'Needs your IBKR sign-in' : 'Failed to load'); } else box.classList.add('dash-skeleton');
      return;
    }
    box.classList.remove('dash-skeleton');
    const bySym = d3.group(hist.data, q => q.symbol); const cw = 200, ch = 56;
    pos.data.forEach(p => {
      const card = document.createElement('div'); card.className = 'pt-mini';
      const head = document.createElement('div'); head.className = 'pt-mini-head';
      const sym = document.createElement('span'); sym.className = 'pt-mini-sym'; sym.textContent = p.symbol;
      const chg = document.createElement('span'); chg.textContent = p.pnl_pct == null ? '—' : k.signedPct(p.pnl_pct); chg.className = p.pnl_pct == null ? 'pt-muted' : p.pnl_pct < 0 ? 'pt-down' : 'pt-up';
      head.append(sym, chg);
      const sub = document.createElement('div'); sub.className = 'pt-mini-sub'; sub.textContent = k.fullAmt(p.value_base) + ' · ' + k.pct(p.weight);
      card.append(head, sub);
      const series = (bySym.get(p.symbol) || []).map(q => ({ date: k.parseDay(q.date), close: Number(q.close) })).filter(q => k.isNum(q.close));
      if (series.length < 2) { const e = document.createElement('div'); e.className = 'pt-mini-empty'; e.textContent = 'No price history for this exchange'; card.append(e); }
      else {
        const y = d3.scaleLinear(d3.extent(series.map(q => q.close).concat([p.average_price])), [ch - 4, 4]);
        const x = d3.scaleUtc(d3.extent(series, q => q.date), [2, cw - 6]);
        const svg = d3.select(card).append('svg').attr('width', '100%').attr('viewBox', `0 0 ${cw} ${ch}`).attr('role', 'img').attr('aria-label', p.symbol + ' price, last six months');
        svg.append('line').attr('x1', 2).attr('x2', cw - 6).attr('y1', y(p.average_price)).attr('y2', y(p.average_price)).style('stroke', 'var(--cds-chart-reference)').style('stroke-width', '1px').style('stroke-dasharray', '3 3');
        const color = p.pnl_pct != null && p.pnl_pct < 0 ? 'var(--cds-chart-status-critical)' : dash.colors[0];
        svg.append('path').datum(series).attr('d', d3.line().x(q => x(q.date)).y(q => y(q.close))).style('fill', 'none').style('stroke', color).style('stroke-width', '1.75px').style('stroke-linejoin', 'round').style('stroke-linecap', 'round');
        const lp = series[series.length - 1]; svg.append('circle').attr('cx', x(lp.date)).attr('cy', y(lp.close)).attr('r', 2.5).style('fill', color);
      }
      box.append(card);
    });
  }
  function draw(range) {
    const k = K(); if (!k) return;
    k.FMT.ibkr_kpis = { net_value: k.money, shares_value: k.money, cash: v => k.fullAmt(v), positions: v => String(v), unrealized_pnl: k.signedFull, day_pnl: k.signedFull,
      return_ytd: v => v == null ? '—' : k.signedPct(v), return_1y: v => v == null ? '—' : k.signedPct(v) };
    const rows = k.fillMarks('ibkr_kpis'); const kr = rows && rows[0];
    const note = document.getElementById('ibkr-cash-note'); if (note) note.textContent = kr && kr.cash < 0 ? 'Negative: borrowed on margin' : 'All currencies';
    const cb = document.getElementById('chart-ibkr');
    if (cb) {
      const inote = document.getElementById('ibkr-range-note'); inote.textContent = '';
      const pf = dash.data('ibkr_performance');
      if (k.prep(cb, pf) && pf.data.length) {
        const sel = k.inRange(pf.data.map(q => ({ date: k.parseDay(q.date), cps: q.cps, nav: q.nav })), range); inote.textContent = sel.note; const c0 = sel.rows[0].cps;
        k.lineChart(cb, sel.rows.map(q => ({ date: q.date, ret: (1 + q.cps) / (1 + c0) - 1, nav: q.nav })), [{ key: 'ret', label: 'Return', color: dash.colors[0] }],
          { label: 'IBKR return over the period', yFmt: q => d3.format('.0%')(q), endFmt: k.signedPct, tipFmt: k.signedPct, refY: 0, zero: true, tipExtra: q => 'Account value ' + k.fullAmt(q.nav) });
      }
    }
    k.fillTable('ibkr_positions_base', 'ibkr-body', cols(), rs => sortRows(rs).map(q => ({ ...q, __key: k.enc(q.symbol) })));
    drawMultiples();
  }
  function mount(host) {
    host.querySelectorAll('#ibkr-table th.pt-sortable').forEach(th => th.addEventListener('click', () => {
      const key = th.getAttribute('data-field'); sort = { key, dir: sort.key === key ? -sort.dir : (key === 'symbol' ? 1 : -1) };
      host.querySelectorAll('#ibkr-table th.pt-sortable').forEach(o => o.removeAttribute('aria-sort'));
      th.setAttribute('aria-sort', sort.dir > 0 ? 'ascending' : 'descending');
      const k = K(); k.fillTable('ibkr_positions_base', 'ibkr-body', cols(), rs => sortRows(rs).map(q => ({ ...q, __key: k.enc(q.symbol) })));
    }));
  }
  window.wdLive = { draw, mount };
})();
