(function () {
  /* Wealth dashboard page. Every figure comes from the datasets written by wealth.py; nothing personal is in this file.
     Views: "Household" plus one per person in settings (section "person"); joint lines split by section "joint_share". */

  /* ================= Wealth calculations ================= */
  dash.calc('series', {
    inputs: ['snapshots', 'attribution', 'settings'], title: 'Net worth by date',
    description: 'Assets, debt and net worth on each date for the household and each person (joint lines split as set, equally if not), with running totals of saved, markets and gifts.',
    fn: (snapshots, attribution, settings) => {
      const ppl = settings.filter(q => q.section === 'person').map(q => q.key);
      const js = {}; settings.filter(q => q.section === 'joint_share').forEach(q => { js[q.key] = Number(q.value); });
      const views = ['Household'].concat(ppl.length > 1 ? ppl : []);
      const f = (view, o) => view === 'Household' ? 1 : o === view ? 1 : o === 'Joint' ? (Number.isFinite(js[view]) ? js[view] : 1 / ppl.length) : 0;
      const dates = [...new Set(snapshots.map(r => r.date))].sort();
      const out = [];
      for (const view of views) {
        const by = {}, att = {};
        for (const r of snapshots) {
          const k = f(view, r.owner); if (!k) continue;
          const o = by[r.date] || (by[r.date] = { invested: 0, other: 0, debt: 0 }); const v = Number(r.value) * k;
          if (r.group === 'Debt') o.debt += v; else if (r.group === 'Invested') o.invested += v; else o.other += v;
        }
        for (const a of attribution) {
          const k = f(view, a.owner); if (!k) continue;
          const o = att[a.month] || (att[a.month] = { saved: 0, markets: 0, gifts: 0 });
          o.saved += Number(a.saved) * k; o.markets += Number(a.markets) * k; o.gifts += Number(a.gifts) * k;
        }
        let cs = 0, cm = 0, cg = 0;
        for (const d of dates) {
          const o = by[d] || { invested: 0, other: 0, debt: 0 }; const a = att[d.slice(0, 7)];
          if (a) { cs += a.saved; cm += a.markets; cg += a.gifts; }
          out.push({ view, date: d, invested: o.invested, other: o.other, total_assets: o.invested + o.other, debt: o.debt, net_worth: o.invested + o.other + o.debt,
            saved_cum: cs, markets_cum: cm, gifts_cum: cg });
        }
      }
      return out;
    }
  });
  dash.calc('by_category', {
    inputs: ['snapshots', 'settings'], title: 'Assets and debt by category',
    description: 'Each category on each date for each view (joint lines split as set).',
    fn: (snapshots, settings) => {
      const ppl = settings.filter(q => q.section === 'person').map(q => q.key);
      const js = {}; settings.filter(q => q.section === 'joint_share').forEach(q => { js[q.key] = Number(q.value); });
      const views = ['Household'].concat(ppl.length > 1 ? ppl : []);
      const f = (view, o) => view === 'Household' ? 1 : o === view ? 1 : o === 'Joint' ? (Number.isFinite(js[view]) ? js[view] : 1 / ppl.length) : 0;
      const m = {};
      for (const view of views) for (const r of snapshots) {
        const k = f(view, r.owner); if (!k) continue;
        const key = view + '|' + r.date + '|' + r.category;
        if (!m[key]) m[key] = { view, date: r.date, group: r.group, category: r.category, value: 0 };
        m[key].value += Number(r.value) * k;
      }
      return Object.values(m);
    }
  });
  dash.calc('latest_items', {
    inputs: ['snapshots', 'settings'], title: 'Holdings today',
    description: 'Every line on the latest date, at its share in each view (joint lines split as set).',
    fn: (snapshots, settings) => {
      const ppl = settings.filter(q => q.section === 'person').map(q => q.key);
      const js = {}; settings.filter(q => q.section === 'joint_share').forEach(q => { js[q.key] = Number(q.value); });
      const views = ['Household'].concat(ppl.length > 1 ? ppl : []);
      const f = (view, o) => view === 'Household' ? 1 : o === view ? 1 : o === 'Joint' ? (Number.isFinite(js[view]) ? js[view] : 1 / ppl.length) : 0;
      const last = snapshots.reduce((m, r) => r.date > m ? r.date : m, '');
      const out = [];
      for (const view of views) for (const r of snapshots) {
        if (r.date !== last) continue; const k = f(view, r.owner); if (!k) continue;
        out.push({ view, item: r.item, owner: r.owner, group: r.group, kind: r.kind, category: r.category, platform: r.platform,
          value: Number(r.value) * k, full_value: Number(r.value), share: k, updates_via: r.updates_via, estimated: r.estimated === true || r.estimated === 'true', date: r.date });
      }
      return out;
    }
  });
  dash.calc('breakdown', {
    inputs: ['latest_items'], title: 'Breakdown by category',
    description: 'Each category today as a share of total assets; debt against the same total.',
    fn: (latest_items) => {
      const m = {}, tot = {};
      for (const r of latest_items) {
        const k = r.view + '|' + r.category;
        if (!m[k]) m[k] = { view: r.view, group: r.group, category: r.category, value: 0 };
        m[k].value += r.value;
        if (r.group !== 'Debt') tot[r.view] = (tot[r.view] || 0) + r.value;
      }
      const order = { Invested: 0, Other: 1, Debt: 2 };
      return Object.values(m).filter(r => Math.abs(r.value) >= 0.5).map(r => ({ ...r, share: tot[r.view] ? r.value / tot[r.view] : 0 }))
        .sort((a, b) => order[a.group] - order[b.group] || Math.abs(b.value) - Math.abs(a.value));
    }
  });
  dash.calc('kpis', {
    inputs: ['series', 'latest_items'], title: 'Headline figures',
    description: 'Latest net worth, assets and debt per view; the change since the 1st of the month and since 1 January, split into saved, markets and gifts; what the other assets are.',
    fn: (series, latest_items) => {
      const out = [];
      for (const view of [...new Set(series.map(r => r.view))]) {
        const s = series.filter(r => r.view === view); const last = s[s.length - 1]; if (!last) continue;
        const y = last.date.slice(0, 4), m = last.date.slice(0, 7);
        const prevYear = s.filter(r => r.date < y + '-01-01').pop() || s[0];
        const prevMonth = s.filter(r => r.date < m + '-01').pop() || s[0];
        const ch = last.net_worth - prevYear.net_worth;
        const oc = {}; latest_items.filter(r => r.view === view && r.group === 'Other').forEach(r => { oc[r.category] = (oc[r.category] || 0) + r.value; });
        const top = Object.entries(oc).filter(e => e[1] > 0.5).sort((a, b) => b[1] - a[1]).map(e => e[0]);
        const desc = top.length ? (top.length > 3 ? top.slice(0, 3).join(', ') + ' and more' : top.join(', ')) : 'None';
        out.push({ view, as_of: last.date, net_worth: last.net_worth, total_assets: last.total_assets, invested: last.invested, other: last.other,
          invested_share: last.total_assets ? last.invested / last.total_assets : 0, debt: last.debt, debt_abs: Math.abs(last.debt),
          nw_mtd: last.net_worth - prevMonth.net_worth, change_ytd: ch, change_ytd_abs: Math.abs(ch), other_desc: desc,
          saved_ytd: last.saved_cum - prevYear.saved_cum, markets_ytd: last.markets_cum - prevYear.markets_cum, gifts_ytd: last.gifts_cum - prevYear.gifts_cum });
      }
      return out;
    }
  });
  dash.calc('exposure', {
    inputs: ['latest_items', 'region_weights'], title: 'Investments by region',
    description: 'Each account split by the region weights of what it holds (from its funds and shares), summed by region for each view. Accounts with no region data are left out.',
    fn: (latest_items, region_weights) => {
      const w = {}; for (const r of region_weights) (w[r.item] = w[r.item] || []).push([r.region, Number(r.weight)]);
      const out = [];
      for (const view of [...new Set(latest_items.map(r => r.view))]) {
        const by = {};
        for (const it of latest_items.filter(r => r.view === view)) for (const [reg, f] of (w[it.item] || [])) by[reg] = (by[reg] || 0) + it.value * f;
        const total = Object.values(by).reduce((s, v) => s + v, 0);
        for (const reg of Object.keys(by)) if (by[reg] > 0.5) out.push({ view, region: reg, value: by[reg], share: total ? by[reg] / total : 0 });
      }
      return out.sort((a, b) => b.value - a.value);
    }
  });
  dash.calc('exposure_kpis', {
    inputs: ['exposure', 'settings'], title: 'Largest region',
    description: 'For each view, the region holding the largest share of investments with region data.',
    fn: (exposure, settings) => {
      const ppl = settings.filter(q => q.section === 'person').map(q => q.key);
      return ['Household'].concat(ppl.length > 1 ? ppl : []).map(view => {
        const r = exposure.filter(q => q.view === view).sort((a, b) => b.value - a.value)[0];
        return { view, top_region: r ? r.region : '', top_share: r ? r.share : null,
          summary: r ? 'The largest part, ' + Math.round(r.share * 100) + '%, is in ' + r.region + '.' : 'No region data yet: ask Claude to add the regions your funds invest in.' };
      });
    }
  });
  dash.calc('loan_kpis', {
    inputs: ['loan', 'series'], title: 'Loans today',
    description: 'From the repayment schedules: balance after the current month, payments and interest left, and the last payment month.',
    fn: (loan, series) => {
      const today = series.reduce((m, r) => r.date > m ? r.date : m, '').slice(0, 7);
      if (!loan.length) return [{ month: today, has_schedule: false, left: 0, payment: 0, payments_left: 0, cost_left: 0, end: '', end_note: 'No repayment schedule' }];
      const now = loan.filter(r => r.month <= today).pop() || loan[0];
      const rest = loan.filter(r => r.month > today && Number(r.payment) > 0);
      const lastPay = loan.filter(r => Number(r.payment) > 0).pop();
      const end = lastPay ? lastPay.month : '';
      const mon = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
      const endTxt = end ? mon[Number(end.slice(5, 7)) - 1] + ' ' + end.slice(0, 4) : '';
      return [{ month: today, has_schedule: true, left: Number(now.balance), payment: rest.length ? Number(rest[0].payment) : 0, payments_left: rest.length,
        cost_left: rest.reduce((s, r) => s + Number(r.interest) + Number(r.insurance || 0), 0), end, end_note: rest.length ? 'Scheduled loans paid off ' + endTxt : 'Scheduled loans paid off' }];
    }
  });
  dash.calc('cash_items', {
    inputs: ['latest_items'], title: 'Cash by account',
    description: 'Every cash account today, at its share in each view.',
    fn: (latest_items) => latest_items.filter(r => r.kind === 'cash').map(r => ({ view: r.view, item: r.item, owner: r.owner, value: r.value })).sort((a, b) => b.value - a.value)
  });
  dash.calc('cash_series', {
    inputs: ['snapshots', 'settings'], title: 'Cash over time', description: 'Total of all cash accounts on each date, per view (joint accounts split as set).',
    fn: (snapshots, settings) => {
      const ppl = settings.filter(q => q.section === 'person').map(q => q.key);
      const js = {}; settings.filter(q => q.section === 'joint_share').forEach(q => { js[q.key] = Number(q.value); });
      const views = ['Household'].concat(ppl.length > 1 ? ppl : []);
      const f = (view, o) => view === 'Household' ? 1 : o === view ? 1 : o === 'Joint' ? (Number.isFinite(js[view]) ? js[view] : 1 / ppl.length) : 0;
      const dates = [...new Set(snapshots.map(r => r.date))].sort(); const out = [];
      for (const view of views) for (const d of dates) out.push({ view, date: d, cash: snapshots.filter(r => r.date === d && r.kind === 'cash').reduce((s, r) => s + Number(r.value) * f(view, r.owner), 0) });
      return out;
    }
  });
  dash.calc('cf_kpis', {
    inputs: ['cashflow'], title: 'Cash flow, last 12 months',
    description: 'Household averages over the last 12 budget months: income, spending (loan interest included, principal excluded), what was left, and the savings rate.',
    fn: (cashflow) => {
      const s = cashflow.slice().sort((a, b) => a.month < b.month ? -1 : 1).slice(-12); const n = s.length || 1;
      const inc = s.reduce((t, r) => t + Number(r.revenues), 0) / n, sp = s.reduce((t, r) => t + Number(r.spending) - Number(r.loan_principal || 0), 0) / n, sv = s.reduce((t, r) => t + Number(r.savings_adjusted), 0) / n;
      return [{ months: s.length, from: s[0] ? s[0].month : '', to: s.length ? s[s.length - 1].month : '', avg_income: s.length ? inc : null, avg_spending: s.length ? sp : null, avg_saved: s.length ? sv : null, savings_rate: inc ? sv / inc : null }];
    }
  });
  dash.calc('cash_kpis', {
    inputs: ['cash_items', 'cf_kpis', 'settings'], title: 'Cash cover',
    description: 'Cash today per view and how many months of average household spending it covers.',
    fn: (cash_items, cf_kpis, settings) => {
      const ppl = settings.filter(q => q.section === 'person').map(q => q.key);
      return ['Household'].concat(ppl.length > 1 ? ppl : []).map(view => { const c = cash_items.filter(r => r.view === view).reduce((s, r) => s + r.value, 0);
        return { view, cash: c, months_covered: cf_kpis[0] && cf_kpis[0].avg_spending ? c / cf_kpis[0].avg_spending : null }; });
    }
  });
  dash.calc('spend_cats', {
    inputs: ['spending'], title: 'Spending by category',
    description: 'Average per month over the last 12 budget months, by category, grouped into needs, wants and loan payments.',
    fn: (spending) => {
      const months = [...new Set(spending.map(r => r.month))].sort().slice(-12); const keep = new Set(months); const m = {};
      for (const r of spending) { if (!keep.has(r.month)) continue; const k = r.kind + '|' + r.category; if (!m[k]) m[k] = { kind: r.kind, category: r.category, total: 0 }; m[k].total += Number(r.amount); }
      const rows = Object.values(m).map(r => ({ kind: r.kind, category: r.category, value: r.total / Math.max(1, months.length) }));
      const tot = rows.reduce((s, r) => s + r.value, 0); const order = { Needs: 0, Wants: 1, Loan: 2 };
      return rows.map(r => ({ ...r, key: r.kind + ': ' + r.category, share: tot ? r.value / tot : 0 })).sort((a, b) => (order[a.kind] ?? 3) - (order[b.kind] ?? 3) || b.value - a.value);
    }
  });

  /* ================= Goals ================= */
  dash.calc('budget_months', {
    inputs: ['cashflow', 'spending', 'budget_map'], title: 'Needs, wants and savings by month',
    description: "Each budget month's household income split into needs, wants and what was kept. Each category follows the map (one missing from it counts as wants); loan payments count as needs except their principal, which is kept.",
    fn: (cashflow, spending, budget_map) => {
      const bucket = {}; for (const r of budget_map) bucket[r.category] = r.bucket;
      const per = {};
      for (const r of spending) {
        const b = r.kind === 'Loan' ? 'Loan' : (bucket[r.category] || r.kind || 'Wants');
        if (b === 'Loan') continue;
        const p = per[r.month] || (per[r.month] = { Needs: 0, Wants: 0 }); p[b === 'Needs' ? 'Needs' : 'Wants'] += Number(r.amount);
      }
      return cashflow.map(c => {
        const p = { Needs: 0, Wants: 0, ...(per[c.month] || {}) };
        p.Needs += Math.max(0, Number(c.loan_payment || 0) - Number(c.loan_principal || 0));
        const income = Number(c.revenues), savings = income - p.Needs - p.Wants;
        return { month: c.month, period_end: c.period_end, income, needs: p.Needs, wants: p.Wants, savings,
          needs_share: income ? p.Needs / income : null, wants_share: income ? p.Wants / income : null, savings_share: income ? savings / income : null };
      }).sort((a, b) => a.month < b.month ? -1 : 1);
    }
  });
  dash.calc('budget', {
    inputs: ['budget_months', 'goals'], title: 'Budget against goals',
    description: 'Needs, wants and savings over the last month, 3 months and 12 months: average a month, share of income, and the goal as a share of income or an amount a month. Needs and wants are limits, savings a minimum; a start month limits the months counted; a deadline still ahead turns a miss into "Not yet".',
    fn: (budget_months, goals) => {
      const out = []; const today = budget_months.length ? budget_months[budget_months.length - 1].period_end : '';
      for (const g of goals.filter(q => q.kind === 'budget')) {
        for (const [period, n] of [['1M', 1], ['3M', 3], ['12M', 12]]) {
          let rows = budget_months.slice(-n);
          if (g.from) rows = rows.filter(r => r.month >= String(g.from).slice(0, 7));
          if (!rows.length) continue;
          const inc = rows.reduce((s, r) => s + r.income, 0) / rows.length;
          const act = rows.reduce((s, r) => s + Number(r[g.metric] || 0), 0) / rows.length;
          const t = Number(g.target), isAmt = g.unit === 'eur' || g.unit === 'amount', min = g.metric === 'savings';
          const tAmt = isAmt ? t : inc * t / 100, tShare = isAmt ? (inc ? t / inc : null) : t / 100;
          const met = min ? act >= tAmt : act <= tAmt, margin = min ? act - tAmt : tAmt - act;
          let status = met ? 'On track' : min ? 'Short' : 'Over';
          if (!met && g.deadline) status = String(g.deadline) >= today ? 'Not yet' : 'Missed';
          out.push({ period, id: g.id, bucket: g.metric, label: g.label, unit: isAmt ? 'amount' : 'pct', target: t, direction: min ? 'min' : 'max', months: rows.length,
            from: rows[0].month, to: rows[rows.length - 1].month, income: inc, actual: act, share: inc ? act / inc : null, target_eur: tAmt, target_share: tShare,
            margin, margin_abs: Math.abs(margin), margin_word: margin >= 0 ? (min ? 'above the goal' : 'under the limit') : (min ? 'short of the goal' : 'over the limit'),
            met, deadline: g.deadline || '', status });
        }
      }
      return out;
    }
  });
  dash.calc('goal_status', {
    inputs: ['goals', 'budget', 'series', 'cash_series', 'cash_kpis'], title: 'Where each goal stands',
    description: "Every goal: budget goals over the last 12 months; milestones from today's figures, with the pace of the last 12 months (gifts left out) and the month the target is reached at that pace (left blank beyond 50 years), against any deadline. Debt is a limit; the others are minimums.",
    fn: (goals, budget, series, cash_series, cash_kpis) => {
      const addMonths = (ym, n) => new Date(Date.UTC(Number(ym.slice(0, 4)), Number(ym.slice(5, 7)) - 1 + n, 1)).toISOString().slice(0, 7);
      const out = [];
      for (const g of goals) {
        const t = Number(g.target);
        const unit = g.unit === 'eur' ? 'amount' : g.unit;
        const base = { id: g.id, label: g.label, view: g.view || 'Household', kind: g.kind, metric: g.metric, unit, target: t, deadline: g.deadline || '', note: g.note || '' };
        if (g.kind === 'budget') {
          const b = budget.find(r => r.id === g.id && r.period === '12M');
          if (!b) { out.push({ ...base, direction: g.metric === 'savings' ? 'min' : 'max', current: null, progress: null, pace: null, projected: '', status: 'No data' }); continue; }
          out.push({ ...base, direction: b.direction, current: unit === 'amount' ? b.actual : b.share * 100,
            progress: b.direction === 'min' && b.target_eur > 0 ? Math.max(0, b.actual / b.target_eur) : null, pace: null, projected: '', status: b.status });
          continue;
        }
        const s = series.filter(r => r.view === base.view); const last = s[s.length - 1];
        if (!last) { out.push({ ...base, direction: 'min', current: null, progress: null, pace: null, projected: '', status: 'No data' }); continue; }
        const yearAgo = String(Number(last.date.slice(0, 4)) - 1) + last.date.slice(4);
        const then = s.filter(r => r.date <= yearAgo).pop() || s[0];
        const months = Math.max(1, (Number(last.date.slice(0, 4)) - Number(then.date.slice(0, 4))) * 12 + Number(last.date.slice(5, 7)) - Number(then.date.slice(5, 7)));
        const cs = cash_series.filter(r => r.view === base.view).sort((a, b) => a.date < b.date ? -1 : 1);
        const cashNow = cs.length ? cs[cs.length - 1].cash : 0, cashThen = (cs.filter(r => r.date <= yearAgo).pop() || cs[0] || { cash: 0 }).cash;
        const ck = cash_kpis.find(r => r.view === base.view);
        let current = null, pace = null, direction = 'min';
        if (g.metric === 'net_worth') { current = last.net_worth; pace = ((last.net_worth - then.net_worth) - (last.gifts_cum - then.gifts_cum)) / months; }
        else if (g.metric === 'invested' || g.metric === 'total_assets') { current = last[g.metric]; pace = ((last[g.metric] - then[g.metric]) - (last.gifts_cum - then.gifts_cum)) / months; }
        else if (g.metric === 'cash') { current = cashNow; pace = (cashNow - cashThen) / months; }
        else if (g.metric === 'debt') { direction = 'max'; current = Math.abs(last.debt); pace = (Math.abs(then.debt) - Math.abs(last.debt)) / months; }
        else if (g.metric === 'cash_months' && ck && ck.months_covered != null) {
          current = ck.months_covered; const spend = ck.months_covered ? ck.cash / ck.months_covered : null; pace = spend ? (cashNow - cashThen) / months / spend : null;
        }
        if (current == null) { out.push({ ...base, direction, current: null, progress: null, pace: null, projected: '', status: 'No data' }); continue; }
        const reached = direction === 'min' ? current >= t : current <= t;
        const gap = direction === 'min' ? t - current : current - t, ym = last.date.slice(0, 7);
        const need = pace > 0 ? Math.ceil(gap / pace) : null;
        const projected = reached || need == null || need > 600 ? '' : addMonths(ym, need);
        const dl = g.deadline ? String(g.deadline).slice(0, 7) : '';
        const status = reached ? 'Reached' : dl ? (projected && projected <= dl ? 'On track' : dl < ym ? 'Missed' : 'Behind') : (projected ? 'In progress' : 'Stalled');
        out.push({ ...base, direction, current, progress: direction === 'min' && t > 0 ? Math.max(0, current / t) : null, pace, projected, status });
      }
      return out;
    }
  });
  dash.calc('goals_kpis', {
    inputs: ['goal_status', 'budget'], title: 'Goals summary',
    description: 'How many goals are reached or on track (a milestone with no deadline counts while it is moving towards its target), and the 12-month needs, wants and savings shares of income against their goals.',
    fn: (goal_status, budget) => {
      const good = goal_status.filter(g => ['Reached', 'On track', 'In progress'].includes(g.status)).length;
      const b = (k, f) => { const r = budget.find(q => q.period === '12M' && q.bucket === k); return r && r[f] != null ? r[f] : null; };
      const em = goal_status.find(g => g.metric === 'cash_months');
      return [{ total: goal_status.length, on_track: good, on_track_txt: good + ' of ' + goal_status.length,
        savings_share: b('savings', 'share'), savings_target: b('savings', 'target_share'), needs_share: b('needs', 'share'), needs_target: b('needs', 'target_share'),
        wants_share: b('wants', 'share'), wants_target: b('wants', 'target_share'), cash_months_target: em ? em.target : null }];
    }
  });

  /* ================= How you compare ================= */
  dash.calc('peers_view', {
    inputs: ['peers', 'peers_meta', 'settings', 'kpis', 'latest_items', 'cashflow'], title: 'How you compare',
    description: "Your figures placed in each country's distribution: net worth (with and without pensions) against all households and households whose main earner is your age (the oldest adult for the household); household net income per person over the last 12 budget months on the EU equivalence scale (adults and children from the settings); household gross income and each person's earnings from the gross incomes in the settings; the saving rate against the national average. Survey figures were brought to recent prices with each country's consumer prices; your figures are converted at the exchange rates in the settings. Between published points percentiles are interpolated; where only a median (by age) or three points (earnings) are published they are estimated, and flagged.",
    fn: (peers, peers_meta, settings, kpis, latest_items, cashflow) => {
      const num = v => v === null || v === undefined || v === '' || !Number.isFinite(Number(v)) ? null : Number(v);
      const set = (sec, key) => { const r = settings.find(q => q.section === sec && q.key === key); return r ? r.value : null; };
      const people = settings.filter(r => r.section === 'person');
      const sym = String(set('meta', 'symbol') || '');
      const kh = kpis.find(q => q.view === 'Household'); if (!kh) return [];
      const today = kh.as_of;
      const ageOf = b => { if (!b) return null; const [y, m, d] = String(b).split('-').map(Number); const [ty, tm, td] = today.split('-').map(Number); return ty - y - ((tm < (m || 1) || (tm === (m || 1) && td < (d || 1))) ? 1 : 0); };
      const age = {}, gross = {}; people.forEach(p => { age[p.key] = ageOf(p.birth_date); gross[p.key] = num(p.gross_income); });
      const defaults = String(set('compare', 'countries') || 'NL,FR,DE,US').split(',').map(c => c.trim()).filter(Boolean);
      const per = { EUR: num(set('fx', 'EUR')), USD: num(set('fx', 'USD')) };
      const fx = { EUR: per.EUR ? 1 / per.EUR : null, USD: per.USD ? 1 / per.USD : null };
      const meta = {}; for (const m of peers_meta) meta[m.country + '|' + m.metric + '|' + m.population] = m;
      const grids = {};
      for (const r of peers) { const k = r.country + '|' + r.metric + '|' + r.population; (grids[k] = grids[k] || []).push({ p: Number(r.p), v: Number(r.value) }); }
      for (const k of Object.keys(grids)) grids[k].sort((a, b) => a.p - b.p);
      const Phi = z => { const t = 1 / (1 + 0.2316419 * Math.abs(z)); const d = 0.3989423 * Math.exp(-z * z / 2); const pr = d * t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274)))); return z > 0 ? 1 - pr : pr; };
      const place = (g, x) => {
        if (!g || !g.length || x == null) return null;
        const med = (g.find(q => q.p === 50) || {}).v;
        if (g.length <= 5) {
          const lo = g.find(q => q.p === 10), hi = g.find(q => q.p === 90);
          if (!lo || !hi || !(med > 0) || !(x > 0)) return null;
          const sig = x >= med ? Math.log(hi.v / med) / 1.2816 : Math.log(med / lo.v) / 1.2816;
          return { p: Math.min(99.5, Math.max(0.5, 100 * Phi(Math.log(x / med) / sig))), bound: '', est: true, median: med };
        }
        if (x < g[0].v) return { p: g[0].p, bound: 'below', est: false, median: med };
        if (x > g[g.length - 1].v) return { p: g[g.length - 1].p, bound: 'above', est: false, median: med };
        for (let i = 0; i < g.length - 1; i++) {
          const a = g[i], b = g[i + 1];
          if (x >= a.v && x <= b.v) return { p: b.v === a.v ? (a.p + b.p) / 2 : a.p + (b.p - a.p) * (x - a.v) / (b.v - a.v), bound: '', est: false, median: med };
        }
        return null;
      };
      const ageGrid = (c, metric, a) => {
        const cands = Object.keys(grids).filter(k => k.startsWith(c + '|' + metric + '|age:')).map(k => { const [lo, hi] = k.split('age:')[1].split('-').map(Number); return { k, lo, hi, w: hi - lo }; }).sort((p, q) => p.w - q.w);
        const hit = cands.find(q => a != null && a >= q.lo && a <= q.hi);
        if (!hit) return null;
        const g = grids[hit.k]; const all = grids[c + '|' + metric + '|all'];
        if (g.length > 1) return { g, key: hit.k, est: false };
        const med = g[0].v, allMed = all && (all.find(q => q.p === 50) || {}).v;
        if (!all || !(allMed > 0) || !(med > 0)) return { g, key: hit.k, est: true, only: true };
        return { g: all.map(q => ({ p: q.p, v: q.v * med / allMed })), key: hit.k, est: true };
      };
      const cf = cashflow.slice().sort((a, b) => a.month < b.month ? -1 : 1).slice(-12); const n = cf.length;
      const yr = f => n ? cf.reduce((t, r) => t + Number(r[f] || 0), 0) * 12 / n : null;
      const penYear = (num(set('pension', 'monthly_contribution')) || 0) * 12;
      const kids14 = num(set('household', 'children_14_plus')) || 0, kidsU = num(set('household', 'children_under_14')) || 0;
      const adults = Math.max(1, people.length);
      const scale = 1 + 0.5 * (adults - 1 + kids14) + 0.3 * kidsU;
      const disp = yr('revenues');
      const saved = yr('savings_adjusted');
      const famTxt = (() => { const k = kidsU + kids14; return adults + ' adult' + (adults > 1 ? 's' : '') + (k ? ' and ' + k + ' child' + (k > 1 ? 'ren' : '') : ''); })();
      const amt = x => sym + Math.round(x).toLocaleString('en');
      const knownGross = people.length && people.every(p => gross[p.key] != null);
      const hhGross = knownGross ? people.reduce((t, p) => t + gross[p.key], 0) : null;
      const rate = disp ? (saved + penYear) / (disp + penYear) : null;
      const countries = [...new Set(peers_meta.map(m => m.country))];
      const views = ['Household'].concat(people.length > 1 ? people.map(p => p.key) : []);
      const out = [];
      for (const view of views) {
        const k = kpis.find(q => q.view === view); if (!k) continue;
        const pen = latest_items.filter(r => r.view === view && r.kind === 'retirement').reduce((t, r) => t + r.value, 0);
        const ages = people.map(p => age[p.key]).filter(a => a != null);
        const refAge = view === 'Household' ? (ages.length ? Math.max(...ages) : null) : age[view];
        const metrics = view === 'Household'
          ? [['net_wealth', 'Net worth'], ['equiv_income', 'Net income per person, after tax'], ['hh_gross_income', 'Household income before tax'], ['saving_rate', 'Saving rate']]
          : [['net_wealth', 'Net worth'], ['earnings', 'Earnings before tax'], ['equiv_income', 'Household net income per person, after tax']];
        const notes = {
          equiv_income: disp != null ? 'Household income after tax ' + amt(disp) + ' a year (last ' + n + ' budget month' + (n > 1 ? 's' : '') + ', scaled to a year) shared by ' + famTxt + ' (÷' + scale.toFixed(1) + ', the EU scale)' : ''
        };
        for (const c of countries) {
          const cname = (peers_meta.find(m => m.country === c) || {}).country_name || c;
          const cur = c === 'US' ? 'USD' : 'EUR', rateFx = fx[cur];
          for (const [metric, mlabel] of metrics) {
            for (const pen_mode of (metric === 'net_wealth' ? ['without', 'with'] : ['na'])) {
              let you = null, why = '';
              if (metric === 'net_wealth') you = pen_mode === 'with' ? k.net_worth : k.net_worth - pen;
              else if (metric === 'equiv_income') { you = disp != null ? disp / scale : null; if (you == null) why = 'Needs a few months of your budget'; }
              else if (metric === 'hh_gross_income') { you = hhGross; if (you == null) why = 'Ask Claude to add each adult’s gross income'; }
              else if (metric === 'earnings') { you = gross[view]; if (you == null) why = 'Ask Claude to add ' + view + '’s gross income'; else if (you === 0) { you = null; why = 'No earnings this year'; } }
              else if (metric === 'saving_rate') you = rate;
              const tm = metric === 'net_wealth' && c === 'US' && pen_mode === 'without' ? 'net_wealth_ex_ret' : metric;
              const base = { view, pension: pen_mode, country: c, country_name: cname, is_default: defaults.includes(c), default_rank: defaults.indexOf(c), metric, metric_label: mlabel, you, you_note: notes[metric] || '', currency: cur };
              if (metric === 'saving_rate') {
                const m = meta[c + '|saving_rate|all'];
                out.push({ ...base, population: 'all', pop_label: m ? m.pop_label : 'National average', percentile: null, bound: '', estimated: false, median: null,
                  national: m ? Number((peers.find(r => r.country === c && r.metric === 'saving_rate') || {}).value) : null, ref_month: m ? m.ref_month : '', source: m ? m.source : '', note: m ? m.note : '', missing: m ? '' : 'No national figure' });
                continue;
              }
              if (rateFx == null && you != null) { why = 'Ask Claude to add the ' + cur + ' exchange rate'; }
              const pops = [['all', grids[c + '|' + tm + '|all'], meta[c + '|' + tm + '|all'], false]];
              const ag = ageGrid(c, tm, metric === 'equiv_income' ? null : refAge);
              if (metric !== 'equiv_income') pops.push(['age', ag && ag.g, ag && meta[ag.key], ag ? ag.est : false, ag && ag.only]);
              for (const [pop, g, m, est, only] of pops) {
                const x = you == null || rateFx == null ? null : you * rateFx;
                const pl = only ? null : place(g, x);
                const med = g ? ((only ? g[0] : g.find(q => q.p === 50)) || {}).v : null;
                out.push({ ...base, population: pop, pop_label: m ? m.pop_label : (pop === 'age' ? 'Your age group' : 'Everyone'), percentile: pl ? Math.round(pl.p) : null,
                  bound: pl ? pl.bound : '', estimated: !!(est || (pl && pl.est)), median: med == null ? null : med, ratio: med && x != null ? x / med : null,
                  ref_month: m ? m.ref_month : '', source: m ? m.source : '', note: m ? m.note : '',
                  missing: why || (!g ? (pop === 'age' ? (refAge == null ? 'Ask Claude to add birth years' : 'No figures for this age group') : 'No comparable figures') : (pl ? '' : (only ? 'Median only' : 'Not placed'))) });
              }
            }
          }
        }
      }
      return out;
    }
  });

  /* ================= Projection ================= */
  dash.calc('projection', {
    inputs: ['series', 'cashflow', 'settings', 'loan'], title: 'Projection',
    description: "Household, month by month from today, in three return scenarios from the settings: invested assets grow at the yearly return and receive the monthly saving (the settings value, or the last 12 budget months' average, which counts loan principal) plus pension contributions, less loan principal while a scheduled loan runs; other assets stay flat; scheduled loans follow their schedule and other debts stay as they are. Also in today's money, deflated by the settings' inflation.",
    fn: (series, cashflow, settings, loan) => {
      const num = v => v === null || v === undefined || v === '' || !Number.isFinite(Number(v)) ? null : Number(v);
      const set = (sec, key) => { const r = settings.find(q => q.section === sec && q.key === key); return r ? num(r.value) : null; };
      const s = series.filter(r => r.view === 'Household'); const last = s[s.length - 1]; if (!last) return [];
      const cf = cashflow.slice().sort((a, b) => a.month < b.month ? -1 : 1).slice(-12);
      const avg = cf.length ? cf.reduce((t, r) => t + Number(r.savings_adjusted), 0) / cf.length : 0;
      const saving = (set('projection', 'monthly_saving') ?? avg) + (set('pension', 'monthly_contribution') || 0);
      const years = set('projection', 'years') || 30, infl = set('projection', 'inflation') ?? 0.02;
      const rates = { low: set('projection', 'return_low') ?? 0.03, mid: set('projection', 'return_mid') ?? 0.06, high: set('projection', 'return_high') ?? 0.09 };
      const bal = {}; for (const r of loan) bal[r.month] = Number(r.balance);
      const lastLoan = loan.reduce((m, r) => r.month > m ? r.month : m, '');
      const start = last.date.slice(0, 7);
      const schedNow = loan.length ? (bal[start] !== undefined ? bal[start] : (start > lastLoan ? 0 : Number((loan.filter(r => r.month <= start).pop() || loan[0]).balance))) : 0;
      const flatDebt = Math.max(0, Math.abs(last.debt) - schedNow);
      const addM = (ym, k) => new Date(Date.UTC(Number(ym.slice(0, 4)), Number(ym.slice(5, 7)) - 1 + k, 1)).toISOString().slice(0, 7);
      const out = [];
      for (const [scenario, r] of Object.entries(rates)) {
        const rm = Math.pow(1 + r, 1 / 12) - 1;
        let inv = last.invested, sched = schedNow; const other = last.other;
        out.push({ scenario, month: start, step: 0, invested: inv, total_assets: inv + other, net_worth: inv + other - sched - flatDebt, total_assets_real: inv + other, net_worth_real: inv + other - sched - flatDebt });
        for (let k = 1; k <= years * 12; k++) {
          const ym = addM(start, k);
          const nd = !loan.length || ym > lastLoan ? 0 : Math.max(0, bal[ym] !== undefined ? bal[ym] : sched);
          const principal = Math.max(0, sched - nd);
          inv = inv * (1 + rm) + saving - principal; sched = nd;
          const defl = Math.pow(1 + infl, k / 12);
          out.push({ scenario, month: ym, step: k, invested: inv, total_assets: inv + other, net_worth: inv + other - sched - flatDebt, total_assets_real: (inv + other) / defl, net_worth_real: (inv + other - sched - flatDebt) / defl });
        }
      }
      return out;
    }
  });
  dash.calc('projection_summary', {
    inputs: ['projection', 'cashflow', 'settings'], title: 'Projection summary',
    description: 'The monthly amount invested in the projection and where it came from, the three yearly returns, and assets and net worth at the end of the projection in each scenario, as recorded and in today\'s money.',
    fn: (projection, cashflow, settings) => {
      const num = v => v === null || v === undefined || v === '' || !Number.isFinite(Number(v)) ? null : Number(v);
      const set = (sec, key) => { const r = settings.find(q => q.section === sec && q.key === key); return r ? num(r.value) : null; };
      const cf = cashflow.slice().sort((a, b) => a.month < b.month ? -1 : 1).slice(-12);
      const avg = cf.length ? cf.reduce((t, r) => t + Number(r.savings_adjusted), 0) / cf.length : 0;
      const manual = set('projection', 'monthly_saving');
      const o = { saving: (manual ?? avg) + (set('pension', 'monthly_contribution') || 0), saving_basis: manual != null ? 'the amount you set' : cf.length ? 'the last ' + cf.length + ' budget months\' average' : 'no budget yet, so nothing',
        years: (set('projection', 'years') || 30) + ' years', rate_low: set('projection', 'return_low') ?? 0.03, rate_mid: set('projection', 'return_mid') ?? 0.06, rate_high: set('projection', 'return_high') ?? 0.09 };
      for (const sc of ['low', 'mid', 'high']) {
        const rs = projection.filter(r => r.scenario === sc); const e = rs[rs.length - 1] || {};
        o['end_' + sc + '_total_assets'] = e.total_assets ?? null; o['end_' + sc + '_net_worth'] = e.net_worth ?? null;
        o['end_' + sc + '_total_assets_real'] = e.total_assets_real ?? null; o['end_' + sc + '_net_worth_real'] = e.net_worth_real ?? null;
      }
      return [o];
    }
  });
  dash.calc('projection_kpis', {
    inputs: ['projection', 'goals'], title: 'When goals are reached',
    description: 'For each household goal that is an amount of net worth, total assets or invested assets: the first month the projection reaches it in each scenario, as recorded and in today\'s money (blank if not within the projection).',
    fn: (projection, goals) => goals.filter(g => g.kind === 'milestone' && (g.view || 'Household') === 'Household' && ['net_worth', 'total_assets', 'invested'].includes(g.metric)).map(g => {
      const t = Number(g.target); const o = { goal: g.id, label: g.label, metric: g.metric, target: t, deadline: g.deadline || '' };
      for (const sc of ['low', 'mid', 'high']) {
        const rs = projection.filter(r => r.scenario === sc);
        const hit = rs.find(r => r[g.metric] >= t); const hitR = rs.find(r => (g.metric === 'invested' ? r.invested : r[g.metric + '_real']) >= t);
        o[sc] = hit ? hit.month : ''; o[sc + '_real'] = hitR ? hitR.month : '';
      }
      return o;
    })
  });

  /* ================= Investments ================= */
  dash.calc('inv_positions', {
    inputs: ['holdings', 'settings'], title: 'Positions in each view',
    description: "Each position's value and cost in your currency (at the exchange rate of the last update), its gain and return since bought, and its weight among the positions in each view (joint accounts split as set).",
    fn: (holdings, settings) => {
      const ppl = settings.filter(q => q.section === 'person').map(q => q.key);
      const js = {}; settings.filter(q => q.section === 'joint_share').forEach(q => { js[q.key] = Number(q.value); });
      const views = ['Household'].concat(ppl.length > 1 ? ppl : []);
      const f = (view, o) => view === 'Household' ? 1 : o === view ? 1 : o === 'Joint' ? (Number.isFinite(js[view]) ? js[view] : 1 / ppl.length) : 0;
      const out = [];
      for (const view of views) {
        const rows = [];
        for (const h of holdings) {
          const k = f(view, h.owner); if (!k) continue;
          const value = Number(h.value) * k, cost = h.cost === null || h.cost === undefined || h.cost === '' ? null : Number(h.cost) * k;
          rows.push({ view, id: h.id, name: h.name, ticker: h.ticker || '', account: h.account, owner: h.owner, class: h.class || 'other', currency: h.currency, unit: h.unit || '',
            quantity: h.quantity === null || h.quantity === undefined ? null : Number(h.quantity) * k, price: h.price === null || h.price === undefined ? null : Number(h.price),
            avg_price: cost != null && h.quantity ? (Number(h.cost) / Number(h.quantity)) / (Number(h.fx) || 1) : null,
            value, cost, gain: cost != null ? value - cost : null, ret: cost ? (value - cost) / cost : null, price_date: h.price_date || '', is_cash: h.is_cash === true || h.is_cash === 'true' });
        }
        const total = rows.reduce((s, r) => s + r.value, 0); rows.forEach(r => { r.weight = total ? r.value / total : 0; });
        out.push(...rows.sort((a, b) => b.value - a.value));
      }
      return out;
    }
  });
  dash.calc('inv_kpis', {
    inputs: ['inv_positions', 'settings'], title: 'Investments headline figures',
    description: 'Per view: value of all positions, the cost of those with a known cost, gain and return on them, how many positions, and the oldest price date.',
    fn: (inv_positions, settings) => {
      const ppl = settings.filter(q => q.section === 'person').map(q => q.key);
      return ['Household'].concat(ppl.length > 1 ? ppl : []).map(view => {
        const rs = inv_positions.filter(r => r.view === view && !r.is_cash); const known = rs.filter(r => r.cost != null);
        const value = rs.reduce((s, r) => s + r.value, 0), kv = known.reduce((s, r) => s + r.value, 0), cost = known.reduce((s, r) => s + r.cost, 0);
        const dates = rs.map(r => r.price_date).filter(Boolean).sort(); const oldest = dates[0] || '', newest = dates[dates.length - 1] || '';
        const stale = rs.filter(r => r.price_date && newest && (Date.parse(newest) - Date.parse(r.price_date)) > 35 * 864e5).length;
        return { view, value, cost, gain: kv - cost, gain_abs: Math.abs(kv - cost), ret: cost ? (kv - cost) / cost : null, cost_cover: value ? kv / value : null,
          positions: rs.length, price_date: newest, oldest_price: oldest, stale_txt: stale ? stale + ' price' + (stale > 1 ? 's are' : ' is') + ' older than a month' : 'All prices current' };
      });
    }
  });
  dash.calc('inv_classes', {
    inputs: ['inv_positions'], title: 'Positions by asset class', description: 'Value of positions in each asset class, per view.',
    fn: (inv_positions) => {
      const m = {}, tot = {};
      for (const r of inv_positions) { const k = r.view + '|' + r.class; m[k] = m[k] || { view: r.view, class: r.class, value: 0 }; m[k].value += r.value; tot[r.view] = (tot[r.view] || 0) + r.value; }
      return Object.values(m).filter(r => r.value > 0.5).map(r => ({ ...r, share: tot[r.view] ? r.value / tot[r.view] : 0 })).sort((a, b) => b.value - a.value);
    }
  });
  dash.calc('inv_accounts', {
    inputs: ['inv_positions'], title: 'Positions by account', description: 'Value of positions and uninvested cash in each account, per view.',
    fn: (inv_positions) => {
      const m = {}, tot = {};
      for (const r of inv_positions) { const k = r.view + '|' + r.account; m[k] = m[k] || { view: r.view, account: r.account, value: 0 }; m[k].value += r.value; tot[r.view] = (tot[r.view] || 0) + r.value; }
      return Object.values(m).filter(r => Math.abs(r.value) > 0.5).map(r => ({ ...r, share: tot[r.view] ? r.value / tot[r.view] : 0 })).sort((a, b) => b.value - a.value);
    }
  });

  /* ================= formatting ================= */
  let SYM = '€';
  const compact = new Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 });
  const comma = d3.format(',');
  const absTxt = v => Math.abs(v) >= 10000 ? compact.format(Math.abs(v)) : comma(Math.round(Math.abs(v)));
  const money = v => (v < 0 ? '−' : '') + SYM + absTxt(v);
  const signed = v => (v < 0 ? '−' : '+') + SYM + absTxt(v);
  const pct = d3.format('.1%');
  const pct0 = d3.format('.0%');
  const signedPct = v => (v < 0 ? '−' : '+') + pct(Math.abs(v));
  const fullAmt = v => (Number(v) < 0 ? '−' : '') + SYM + comma(Math.round(Math.abs(Number(v))));
  const signedFull = v => (Number(v) < 0 ? '−' : '+') + SYM + comma(Math.round(Math.abs(Number(v))));
  const axisAmt = q => (q < 0 ? '−' : '') + SYM + compact.format(Math.abs(q));
  const dayFmt = d3.utcFormat('%-d %b %Y');
  const monFmt = d3.utcFormat('%b %Y');
  const parseDay = s => new Date(String(s).slice(0, 10) + 'T00:00:00Z');
  const parseMon = s => new Date(String(s).slice(0, 7) + '-15T00:00:00Z');
  const isNum = v => typeof v === 'number' && Number.isFinite(v);
  const CUR_SYM = { EUR: '€', USD: '$', GBP: '£', JPY: '¥', CHF: 'CHF ', CAD: 'C$', AUD: 'A$', SEK: 'SEK ', NOK: 'NOK ', DKK: 'DKK ', PLN: 'PLN ', CZK: 'CZK ', HUF: 'HUF ' };
  const priceTxt = (v, cur) => v == null ? '—' : (CUR_SYM[cur] || (cur ? cur + ' ' : '')) + d3.format(v < 10 ? ',.4~f' : ',.2f')(v);
  const FMT = {
    kpis: { as_of: v => dayFmt(parseDay(v)), net_worth: money, total_assets: money, invested: money, other: money, invested_share: pct, debt: money, debt_abs: money,
      nw_mtd: signed, change_ytd: signed, change_ytd_abs: money, saved_ytd: money, markets_ytd: signed, gifts_ytd: money, other_desc: v => String(v) },
    loan_kpis: { left: money, payment: v => fullAmt(v), payments_left: v => String(v), cost_left: v => fullAmt(v), end: v => v ? monFmt(parseMon(v)) : '—', end_note: v => String(v) },
    cash_kpis: { cash: money, months_covered: v => v == null ? '—' : d3.format('.1f')(v) },
    cf_kpis: { avg_income: v => v == null ? '—' : fullAmt(v), avg_spending: v => v == null ? '—' : fullAmt(v), avg_saved: v => v == null ? '—' : signedFull(v), savings_rate: v => v == null ? '—' : signedPct(v) },
    exposure_kpis: { summary: v => String(v) },
    projection_summary: { saving: v => fullAmt(v), saving_basis: v => String(v), years: v => String(v), rate_low: pct, rate_mid: pct, rate_high: pct,
      end_low_total_assets: money, end_mid_total_assets: money, end_high_total_assets: money, end_low_net_worth: money, end_mid_net_worth: money, end_high_net_worth: money,
      end_low_total_assets_real: money, end_mid_total_assets_real: money, end_high_total_assets_real: money, end_low_net_worth_real: money, end_mid_net_worth_real: money, end_high_net_worth_real: money },
    budget: { share: pct, target_share: v => pct0(v), actual: v => fullAmt(v), target_eur: v => fullAmt(v), margin_abs: v => fullAmt(v), income: v => fullAmt(v),
      from: v => monFmt(parseMon(v)), to: v => monFmt(parseMon(v)), status: v => String(v), margin_word: v => String(v) },
    goals_kpis: { on_track_txt: v => String(v), savings_share: pct, savings_target: v => pct0(v), needs_share: pct, needs_target: v => pct0(v),
      wants_share: pct, wants_target: v => pct0(v), cash_months_target: v => d3.format('.1~f')(Number(v)) },
    inv_kpis: { value: money, cost: money, gain: signed, gain_abs: money, ret: v => v == null ? '—' : signedPct(v), cost_cover: v => v == null ? '—' : pct0(v),
      positions: v => String(v), price_date: v => v ? dayFmt(parseDay(v)) : '—', stale_txt: v => String(v) }
  };

  /* ================= state ================= */
  const RANGES = ['1M', 'YTD', 'LTM', '5Y', 'ALL'];
  const P = () => dash.params() || {};
  let PEOPLE = [];
  const VIEWS = () => ['Household'].concat(PEOPLE.length > 1 ? PEOPLE : []);
  const owner = () => VIEWS().includes(P().owner) ? P().owner : 'Household';
  const range = () => RANGES.includes(P().range) ? P().range : 'LTM';
  const chartView = () => P().view === 'stack' ? 'stack' : 'line';
  const debtMode = () => P().debt === 'separate' ? 'separate' : 'net';
  const bperiod = () => ['1M', '3M', '12M'].includes(P().bperiod) ? P().bperiod : '12M';
  const gunit = () => P().gunit === 'eur' ? 'eur' : 'pct';
  const ppen = () => P().ppen === 'with' ? 'with' : 'without';
  const pmetric = () => P().pmetric === 'net_worth' ? 'net_worth' : 'total_assets';
  const preal = () => P().preal === 'real' ? 'real' : 'nominal';
  const GOOD = ['On track', 'Reached', 'In progress'];
  const toneStatus = (el) => { const t = el.textContent; el.classList.toggle('pt-up', GOOD.includes(t)); el.classList.toggle('pt-warn', t === 'Not yet'); el.classList.toggle('pt-down', !GOOD.includes(t) && t !== 'Not yet' && t !== '—'); };
  const whoLabel = v => v === 'Household' ? (PEOPLE.length > 1 ? 'Household' : 'Your') : v + '’s';

  function readSettings() {
    const s = dash.data('settings');
    if (s.status !== 'ok' || !Array.isArray(s.data)) return;
    PEOPLE = s.data.filter(q => q.section === 'person').map(q => q.key);
    const sym = s.data.find(q => q.section === 'meta' && q.key === 'symbol');
    if (sym && sym.value) SYM = String(sym.value);
    const amt = document.getElementById('gunit-amount'); if (amt) amt.textContent = SYM.trim() + ' a month';
    const t = s.data.find(q => q.section === 'meta' && q.key === 'title');
    if (t && t.value) document.getElementById('top').textContent = String(t.value);
  }

  /* ================= helpers ================= */
  function failLine(box, text) {
    const w = document.createElement('div'); w.className = 'pt-fail';
    const dot = document.createElement('span'); dot.className = 'pt-fail-dot';
    const t = document.createElement('span'); t.textContent = text || 'Failed to load';
    w.append(dot, t); box.append(w);
  }
  function emptyLine(box, text) { const e = document.createElement('div'); e.className = 'pt-empty'; e.textContent = text; box.append(e); }
  function prep(box, d) {
    box.replaceChildren();
    if (d.status === 'ok') { box.classList.remove('dash-skeleton'); return true; }
    if (d.status === 'loading') { box.classList.add('dash-skeleton'); return false; }
    box.classList.remove('dash-skeleton');
    failLine(box, d.status === 'connect' ? 'Needs your sign-in' : 'Failed to load');
    return false;
  }
  const enc = s => encodeURIComponent(s);
  function fillMarks(source, where) {
    const d = dash.data(source);
    const rows = d.status === 'ok' && Array.isArray(d.data) ? d.data : null;
    document.querySelectorAll(`.pt [data-source="${source}"][data-field]`).forEach(el => {
      if (el.tagName === 'TH') return;
      if (where && el.hasAttribute('data-where')) el.setAttribute('data-where', where(el));
      let row = null;
      if (rows) {
        if (el.hasAttribute('data-row')) row = rows[Number(el.getAttribute('data-row'))];
        else if (el.hasAttribute('data-where')) {
          const conds = el.getAttribute('data-where').split('&').map(kv => kv.split('=').map(decodeURIComponent));
          row = rows.find(r => conds.every(([k, v]) => String(r[k]) === v));
        }
      }
      if (!row) { el.textContent = '—'; el.classList.toggle('dash-skeleton', d.status === 'loading'); return; }
      el.classList.remove('dash-skeleton');
      const f = el.getAttribute('data-field'); const v = row[f]; const fmt = FMT[source] && FMT[source][f];
      el.textContent = v == null ? '—' : (fmt ? fmt(v) : String(v));
      if (el.classList.contains('pt-signed') && isNum(v)) { el.classList.toggle('pt-up', v >= 0); el.classList.toggle('pt-down', v < 0); }
    });
    return rows;
  }
  function drawXAxis(svg, x, ext, W, H, mb, ml, mr) {
    const spanDays = (ext[1] - ext[0]) / 86400000;
    const nX = Math.max(2, Math.min(7, Math.floor((W - ml - mr) / 70)));
    let iv, fmt;
    if (spanDays <= 62) { iv = d3.utcWeek.every(Math.max(1, Math.ceil(spanDays / 7 / nX))); fmt = d3.utcFormat('%-d %b'); }
    else if (spanDays <= 1100) { iv = d3.utcMonth.every(Math.max(1, Math.ceil(spanDays / 30.4 / nX))); fmt = d3.utcFormat('%b %y'); }
    else { iv = d3.utcYear.every(Math.max(1, Math.ceil(spanDays / 365 / nX))); fmt = d3.utcFormat('%Y'); }
    const g = svg.append('g').attr('transform', `translate(0,${H - mb})`).call(d3.axisBottom(x).ticks(iv || nX).tickFormat(fmt).tickSizeOuter(0));
    g.attr('font-size', null).attr('font-family', null);
    g.select('.domain').style('stroke', 'var(--cds-chart-axis)');
    g.selectAll('.tick line').style('stroke', 'var(--cds-chart-axis)');
    g.selectAll('.tick text').style('fill', 'var(--color-fg-muted)').style('font-size', 'var(--cds-font-size-caption)');
  }
  function rangeStart(last, r) {
    const y = last.getUTCFullYear(), m = last.getUTCMonth(), d = last.getUTCDate();
    if (r === '1M') return new Date(Date.UTC(y, m - 1, d));
    if (r === 'YTD') return new Date(Date.UTC(y, 0, 1));
    if (r === 'LTM') return new Date(Date.UTC(y - 1, m, d));
    if (r === '5Y') return new Date(Date.UTC(y - 5, m, d));
    return null;
  }
  function inRange(rows, r) {
    if (!rows.length) return { rows, note: '' };
    const start = rangeStart(rows[rows.length - 1].date, r);
    if (!start) return { rows, note: '' };
    let out = rows.filter(q => q.date >= start);
    const before = rows.filter(q => q.date < start);
    if (before.length) out = [before[before.length - 1]].concat(out);
    const note = rows[0].date > start ? 'Data starts ' + monFmt(rows[0].date) + '.' : '';
    return { rows: out.length ? out : rows, note };
  }
  function measureText(svg, txt) {
    const t = svg.append('text').style('font-size', 'var(--cds-font-size-caption)').text(txt);
    const w = t.node().getComputedTextLength(); t.remove(); return w;
  }
  function tipBox(box) { const tip = document.createElement('div'); tip.className = 'pt-tip'; box.append(tip); return tip; }
  function placeTip(tip, box, W, cx, cy) {
    tip.style.display = 'block';
    const bw = box.clientWidth, sc = bw / W, tw = tip.offsetWidth;
    let left = cx * sc + 12; if (left + tw > bw) left = cx * sc - tw - 12;
    tip.style.left = Math.max(0, left) + 'px'; tip.style.top = Math.max(0, cy * sc - 40) + 'px';
  }
  function tipLine(tip, color, text, muted) {
    const l = document.createElement('div'); l.className = 'pt-tip-line' + (muted ? ' pt-muted' : '');
    if (color) { const sw = document.createElement('span'); sw.className = 'pt-swatch'; sw.style.background = color; l.append(sw); }
    const t = document.createElement('span'); t.textContent = text; l.append(t); tip.append(l);
  }

  function lineChart(box, rows, series, opts) {
    if (!rows.length) return;
    const W = Math.max(280, box.clientWidth || 600), H = opts.height || 240, mt = 12, mb = 26;
    const svg = d3.select(box).append('svg').attr('width', '100%').attr('viewBox', `0 0 ${W} ${H}`).attr('role', 'img').attr('aria-label', opts.label || '').style('font-family', 'var(--font-anthropic-sans)');
    const dataVals = rows.flatMap(r => series.map(s => r[s.key])).filter(isNum);
    const vals = dataVals.concat((opts.refLines || []).map(rl => rl.y).filter(v => isNum(v) && v <= 1.5 * d3.max(dataVals)));
    let lo = d3.min(vals), hi = d3.max(vals);
    if (opts.zero) { lo = Math.min(lo, 0); hi = Math.max(hi, 0); }
    const pad = (hi - lo) * 0.08 || Math.abs(hi) * 0.05 || 1;
    const y = d3.scaleLinear([opts.zero && lo >= 0 ? 0 : lo - pad, hi + pad], [H - mb, mt]).nice(4);
    const ticks = y.ticks(4);
    const ml = d3.max(ticks, t => measureText(svg, opts.yFmt(t))) + 10;
    const last = rows[rows.length - 1];
    const labels = series.filter(s => isNum(last[s.key]) && !s.noLabel).map(s => ({ s, text: opts.nameOnly ? s.label : s.label + ' ' + opts.endFmt(last[s.key]) }));
    const mr = (d3.max(labels, l => measureText(svg, l.text)) || 0) + 14;
    const ext = d3.extent(rows, r => r.date); if (+ext[0] === +ext[1]) ext[1] = new Date(+ext[0] + 86400000);
    const x = d3.scaleUtc(ext, [ml, W - mr]);
    ticks.forEach(t => {
      svg.append('line').attr('x1', ml).attr('x2', W - mr).attr('y1', y(t)).attr('y2', y(t)).style('stroke', 'var(--cds-chart-grid)').style('stroke-width', '1px');
      svg.append('text').attr('x', ml - 8).attr('y', y(t)).attr('dy', '0.32em').attr('text-anchor', 'end').style('fill', 'var(--color-fg-muted)').style('font-size', 'var(--cds-font-size-caption)').text(opts.yFmt(t));
    });
    (opts.refLines || []).forEach(rl => { if (y.domain()[0] <= rl.y && rl.y <= y.domain()[1]) {
      svg.append('line').attr('x1', ml).attr('x2', W - mr).attr('y1', y(rl.y)).attr('y2', y(rl.y)).style('stroke', 'var(--color-fg)').style('stroke-width', '1px').style('stroke-dasharray', '4 3');
      svg.append('text').attr('x', ml + 4).attr('y', y(rl.y) - 4).style('fill', 'var(--color-fg-muted)').style('font-size', 'var(--cds-font-size-caption)').text(rl.label);
    } });
    if (opts.refY !== undefined && y.domain()[0] <= opts.refY && opts.refY <= y.domain()[1])
      svg.append('line').attr('x1', ml).attr('x2', W - mr).attr('y1', y(opts.refY)).attr('y2', y(opts.refY)).style('stroke', 'var(--cds-chart-reference)').style('stroke-width', '1px');
    drawXAxis(svg, x, ext, W, H, mb, ml, mr);
    series.forEach(s => {
      const pts = rows.filter(r => isNum(r[s.key]));
      svg.append('path').datum(pts).attr('d', d3.line().x(r => x(r.date)).y(r => y(r[s.key])))
        .style('fill', 'none').style('stroke', s.color).style('stroke-width', s.width || '2px').style('stroke-dasharray', s.dash ? '4 4' : null)
        .style('stroke-linecap', s.dash ? null : 'round').style('stroke-linejoin', 'round');
    });
    labels.forEach(l => { l.y = y(last[l.s.key]); }); labels.sort((p, q) => p.y - q.y);
    for (let i = 1; i < labels.length; i++) if (labels[i].y - labels[i - 1].y < 14) labels[i].y = labels[i - 1].y + 14;
    const over = labels.length ? labels[labels.length - 1].y - (H - mb) : 0; if (over > 0) labels.forEach(l => { l.y -= over; });
    labels.forEach(l => svg.append('text').attr('x', W - mr + 8).attr('y', l.y).attr('dy', '0.32em').style('fill', l.s.dash ? 'var(--color-fg-muted)' : 'var(--color-fg)').style('font-size', 'var(--cds-font-size-caption)').text(l.text));
    const rule = svg.append('line').attr('y1', mt).attr('y2', H - mb).style('stroke', 'var(--cds-chart-reference)').style('stroke-width', '1px').style('display', 'none');
    const dots = series.map(s => svg.append('circle').attr('r', 3.5).style('fill', s.color).style('display', 'none'));
    const tip = tipBox(box);
    svg.append('rect').attr('x', ml).attr('y', mt).attr('width', Math.max(0, W - mr - ml)).attr('height', H - mt - mb).style('fill', 'transparent')
      .on('pointermove', (ev) => {
        const [px] = d3.pointer(ev); const xv = x.invert(px); const r = d3.least(rows, q => Math.abs(q.date - xv)); const cx = x(r.date);
        rule.attr('x1', cx).attr('x2', cx).style('display', null);
        series.forEach((s, i) => { if (isNum(r[s.key])) dots[i].attr('cx', cx).attr('cy', y(r[s.key])).style('display', null); else dots[i].style('display', 'none'); });
        tip.replaceChildren(); const dt = document.createElement('div'); dt.className = 'pt-tip-date'; dt.textContent = (opts.dateFmt || dayFmt)(r.date); tip.append(dt);
        series.forEach(s => { if (isNum(r[s.key])) tipLine(tip, s.color, s.label + ' ' + opts.tipFmt(r[s.key])); });
        if (opts.tipExtra) { const ex = opts.tipExtra(r); if (ex) tipLine(tip, null, ex, true); }
        placeTip(tip, box, W, cx, isNum(r[series[0].key]) ? y(r[series[0].key]) : mt);
      })
      .on('pointerleave', () => { tip.style.display = 'none'; rule.style('display', 'none'); dots.forEach(c => c.style('display', 'none')); });
  }

  function stackChart(box, rows, keys, colors, opts) {
    if (!rows.length) return;
    const W = Math.max(280, box.clientWidth || 600), H = opts.height || 260, mt = 12, mb = 26, mr = 12;
    const svg = d3.select(box).append('svg').attr('width', '100%').attr('viewBox', `0 0 ${W} ${H}`).attr('role', 'img').attr('aria-label', opts.label || '').style('font-family', 'var(--font-anthropic-sans)');
    const series = d3.stack().keys(keys).offset(d3.stackOffsetDiverging)(rows);
    let hi = d3.max(series.flat(), d => d[1]) || 1, lo = Math.min(0, d3.min(series.flat(), d => d[0]) || 0);
    if (opts.lineKey) { hi = Math.max(hi, d3.max(rows, r => r[opts.lineKey])); lo = Math.min(lo, d3.min(rows, r => r[opts.lineKey])); }
    const y = d3.scaleLinear([lo * 1.04, hi * 1.04], [H - mb, mt]).nice(4);
    const ticks = y.ticks(4);
    const ml = d3.max(ticks, t => measureText(svg, opts.yFmt(t))) + 10;
    const ext = d3.extent(rows, r => r.date); if (+ext[0] === +ext[1]) ext[1] = new Date(+ext[0] + 86400000);
    const x = d3.scaleUtc(ext, [ml, W - mr]);
    ticks.forEach(t => {
      svg.append('line').attr('x1', ml).attr('x2', W - mr).attr('y1', y(t)).attr('y2', y(t)).style('stroke', t === 0 ? 'var(--cds-chart-axis)' : 'var(--cds-chart-grid)').style('stroke-width', '1px');
      svg.append('text').attr('x', ml - 8).attr('y', y(t)).attr('dy', '0.32em').attr('text-anchor', 'end').style('fill', 'var(--color-fg-muted)').style('font-size', 'var(--cds-font-size-caption)').text(opts.yFmt(t));
    });
    drawXAxis(svg, x, ext, W, H, mb, ml, mr);
    const area = d3.area().x(d => x(d.data.date)).y0(d => y(d[0])).y1(d => y(d[1]));
    series.forEach((s, i) => svg.append('path').datum(s).attr('d', area).style('fill', colors[i]).style('fill-opacity', 0.85).style('stroke', 'var(--color-panel)').style('stroke-width', '0.5px'));
    if (opts.lineKey) svg.append('path').datum(rows).attr('d', d3.line().x(r => x(r.date)).y(r => y(r[opts.lineKey]))).style('fill', 'none').style('stroke', 'var(--color-fg)').style('stroke-width', '2px').style('stroke-linejoin', 'round');
    const rule = svg.append('line').attr('y1', mt).attr('y2', H - mb).style('stroke', 'var(--cds-chart-reference)').style('stroke-width', '1px').style('display', 'none');
    const tip = tipBox(box);
    svg.append('rect').attr('x', ml).attr('y', mt).attr('width', Math.max(0, W - mr - ml)).attr('height', H - mt - mb).style('fill', 'transparent')
      .on('pointermove', (ev) => {
        const [px] = d3.pointer(ev); const xv = x.invert(px); const r = d3.least(rows, q => Math.abs(q.date - xv)); const cx = x(r.date);
        rule.attr('x1', cx).attr('x2', cx).style('display', null);
        tip.replaceChildren(); const dt = document.createElement('div'); dt.className = 'pt-tip-date'; dt.textContent = dayFmt(r.date); tip.append(dt);
        keys.slice().reverse().forEach(k => { if (Math.abs(r[k] || 0) >= 1) tipLine(tip, colors[keys.indexOf(k)], k + ' ' + fullAmt(r[k] || 0)); });
        if (opts.lineKey) tipLine(tip, 'var(--color-fg)', (opts.lineLabel || 'Total') + ' ' + fullAmt(r[opts.lineKey]));
        placeTip(tip, box, W, cx, mt + 40);
      })
      .on('pointerleave', () => { tip.style.display = 'none'; rule.style('display', 'none'); });
  }

  function barLineChart(box, rows) {
    if (!rows.length) return;
    const W = Math.max(280, box.clientWidth || 600), H = 250, mt = 12, mb = 26, mr = 12;
    const svg = d3.select(box).append('svg').attr('width', '100%').attr('viewBox', `0 0 ${W} ${H}`).attr('role', 'img').attr('aria-label', 'Monthly income and spending').style('font-family', 'var(--font-anthropic-sans)');
    const vals = rows.flatMap(r => [r.income, r.spending, r.saved]);
    const y = d3.scaleLinear([Math.min(0, d3.min(vals)) * 1.05, d3.max(vals) * 1.05], [H - mb, mt]).nice(4);
    const ticks = y.ticks(4);
    const ml = d3.max(ticks, t => measureText(svg, axisAmt(t))) + 10;
    const x = d3.scaleBand(rows.map(r => r.month), [ml, W - mr]).paddingInner(0.25).paddingOuter(0.1);
    ticks.forEach(t => {
      svg.append('line').attr('x1', ml).attr('x2', W - mr).attr('y1', y(t)).attr('y2', y(t)).style('stroke', t === 0 ? 'var(--cds-chart-axis)' : 'var(--cds-chart-grid)').style('stroke-width', '1px');
      svg.append('text').attr('x', ml - 8).attr('y', y(t)).attr('dy', '0.32em').attr('text-anchor', 'end').style('fill', 'var(--color-fg-muted)').style('font-size', 'var(--cds-font-size-caption)').text(axisAmt(t));
    });
    const bw = x.bandwidth() / 2;
    const c = [dash.colors[0], 'var(--cds-chart-muted)'];
    rows.forEach(r => {
      [['income', 0], ['spending', 1]].forEach(([k, i]) => {
        const v = r[k]; svg.append('rect').attr('x', x(r.month) + i * bw).attr('width', Math.max(1, bw - 1)).attr('y', y(Math.max(0, v))).attr('height', Math.abs(y(v) - y(0))).attr('rx', Math.min(3, bw / 2)).style('fill', c[i]);
      });
    });
    const cx = r => x(r.month) + x.bandwidth() / 2;
    svg.append('path').datum(rows).attr('d', d3.line().x(cx).y(r => y(r.saved))).style('fill', 'none').style('stroke', dash.colors[1]).style('stroke-width', '2px').style('stroke-linejoin', 'round');
    rows.forEach(r => svg.append('circle').attr('cx', cx(r)).attr('cy', y(r.saved)).attr('r', 2.5).style('fill', dash.colors[1]));
    const every = Math.max(1, Math.ceil(rows.length / Math.max(2, Math.floor((W - ml - mr) / 60))));
    rows.forEach((r, i) => { if (i % every) return; svg.append('text').attr('x', cx(r)).attr('y', H - mb + 16).attr('text-anchor', 'middle').style('fill', 'var(--color-fg-muted)').style('font-size', 'var(--cds-font-size-caption)').text(d3.utcFormat('%b %y')(parseMon(r.month))); });
    const tip = tipBox(box);
    svg.append('rect').attr('x', ml).attr('y', mt).attr('width', W - ml - mr).attr('height', H - mt - mb).style('fill', 'transparent')
      .on('pointermove', (ev) => {
        const [px] = d3.pointer(ev); const r = d3.least(rows, q => Math.abs(cx(q) - px));
        tip.replaceChildren(); const dt = document.createElement('div'); dt.className = 'pt-tip-date'; dt.textContent = monFmt(parseMon(r.month)); tip.append(dt);
        tipLine(tip, c[0], 'Income ' + fullAmt(r.income)); tipLine(tip, c[1], 'Spending ' + fullAmt(r.spending)); tipLine(tip, dash.colors[1], 'Left over ' + signedFull(r.saved));
        placeTip(tip, box, W, cx(r), mt + 40);
      }).on('pointerleave', () => { tip.style.display = 'none'; });
  }

  function drawBars(box, rows, labelKey, colorOf, groupKey, valFmt) {
    const max = d3.max(rows, r => Math.abs(Number(r.value))) || 1; let cur = null;
    rows.forEach((r, i) => {
      if (groupKey && r[groupKey] !== cur) {
        cur = r[groupKey]; const g = rows.filter(q => q[groupKey] === cur);
        const head = document.createElement('div'); head.className = 'pt-group-head';
        const a = document.createElement('span'); a.textContent = cur;
        const b = document.createElement('span'); b.textContent = fullAmt(d3.sum(g, q => Number(q.value)));
        head.append(a, b); box.append(head);
      }
      const row = document.createElement('div'); row.className = 'pt-bar-row';
      const lab = document.createElement('span'); lab.className = 'pt-bar-label'; lab.textContent = r[labelKey]; lab.title = r[labelKey];
      const track = document.createElement('div'); track.className = 'pt-bar-track';
      const fill = document.createElement('div'); fill.className = 'pt-bar-fill'; fill.style.width = (Math.abs(Number(r.value)) / max * 100) + '%'; fill.style.background = colorOf(r, i);
      track.append(fill);
      const val = document.createElement('span'); val.className = 'pt-bar-val';
      const st = document.createElement('span'); st.className = 'pt-strong'; st.textContent = valFmt ? valFmt(r) : pct(Number(r.share));
      val.append(st, document.createTextNode(' · ' + fullAmt(r.value)));
      row.append(lab, track, val); box.append(row);
    });
  }

  function fillTable(source, bodyId, cols, rowsOf, emptyText) {
    const body = document.getElementById(bodyId); if (!body) return;
    const d = dash.data(source); body.replaceChildren();
    if (d.status !== 'ok') {
      const tr = document.createElement('tr'); const td = document.createElement('td'); td.colSpan = cols.length;
      if (d.status === 'loading') { td.className = 'dash-skeleton'; td.style.height = '3rem'; } else failLine(td, d.status === 'connect' ? 'Needs your sign-in' : 'Failed to load');
      tr.append(td); body.append(tr); return;
    }
    const rows = rowsOf ? rowsOf(d.data.slice()) : d.data;
    if (!rows.length && emptyText) {
      const tr = document.createElement('tr'); const td = document.createElement('td'); td.colSpan = cols.length; td.className = 'pt-muted'; td.textContent = emptyText; tr.append(td); body.append(tr); return;
    }
    rows.forEach(r => {
      const tr = document.createElement('tr');
      if (r.__key) tr.setAttribute('data-key', r.__key);
      if (r.__cls) tr.className = r.__cls;
      cols.forEach(c => {
        const td = document.createElement('td'); if (c.cls) td.className = c.cls;
        const v = r[c.key]; td.textContent = c.fmt ? c.fmt(v, r) : (v === '' || v == null ? '—' : String(v));
        if (c.tone) { const t = c.tone(v, r); if (t) td.classList.add(t); }
        if (c.tag) { const t = c.tag(v, r); if (t) { const s = document.createElement('span'); s.className = 'pt-tag'; s.textContent = ' ' + t; td.append(s); } }
        tr.append(td);
      });
      body.append(tr);
    });
  }

  /* ================= category colours ================= */
  let CAT_ORDER = [];
  function setCategoryOrder() {
    const d = dash.data('breakdown');
    if (d.status !== 'ok') return;
    const hh = d.data.filter(q => q.view === 'Household');
    CAT_ORDER = hh.filter(q => q.group !== 'Debt').map(q => q.category).concat(hh.filter(q => q.group === 'Debt').map(q => q.category));
  }
  const isDebtCat = c => { const d = dash.data('breakdown'); return d.status === 'ok' && d.data.some(q => q.category === c && q.group === 'Debt'); };
  const catColor = (c) => isDebtCat(c) ? 'var(--cds-chart-status-critical)' : (dash.colors[CAT_ORDER.filter(x => !isDebtCat(x)).indexOf(c)] || 'var(--cds-chart-muted)');

  /* ================= overview ================= */
  function drawOverview() {
    const v = owner(), r = range();
    const whereView = el => el.getAttribute('data-where').replace(/view=[^&]*/, 'view=' + enc(v));
    const k = fillMarks('kpis', whereView);
    fillMarks('loan_kpis');
    fillMarks('exposure_kpis', whereView);
    fillMarks('goals_kpis');
    const kr = k && k.find(q => q.view === v);
    document.getElementById('tk-who').textContent = whoLabel(v);
    document.getElementById('tk-dir').textContent = kr && kr.change_ytd < 0 ? 'fallen' : 'grown';

    // wealth over time
    const box = document.getElementById('chart-time'), legend = document.getElementById('assets-legend'), note = document.getElementById('time-range-note');
    legend.replaceChildren(); note.textContent = '';
    const mode = debtMode();
    if (chartView() === 'line') {
      const s = dash.data('series');
      document.getElementById('over-time-note').textContent = mode === 'net'
        ? 'Net worth (assets less debt). The dashed line is net worth at the start of the period plus what was saved and gifted since, so the gap to it is what markets and revaluation did.'
        : 'Total assets, debt and net worth, side by side.';
      if (prep(box, s)) {
        const all = s.data.filter(q => q.view === v).map(q => ({ date: parseDay(q.date), nw: q.net_worth, assets: q.total_assets, debt: q.debt, added: q.saved_cum + q.gifts_cum, mk: q.markets_cum }));
        const sel = inRange(all, r); note.textContent = sel.note; const b0 = sel.rows[0];
        if (b0) {
          const rows = sel.rows.map(q => ({ ...q, base: b0.nw + (q.added - b0.added) }));
          const series = mode === 'net'
            ? [{ key: 'nw', label: 'Net worth', color: dash.colors[0] }, { key: 'base', label: 'Start + saved', color: 'var(--cds-chart-muted)', dash: true, width: '1.5px' }]
            : [{ key: 'assets', label: 'Assets', color: dash.colors[0] }, { key: 'nw', label: 'Net worth', color: dash.colors[1] }, { key: 'debt', label: 'Debt', color: 'var(--cds-chart-status-critical)' }];
          lineChart(box, rows, series, { label: 'Wealth over time', yFmt: axisAmt, endFmt: money, tipFmt: q => fullAmt(q), refY: 0,
            tipExtra: q => mode === 'net' ? 'Markets since start ' + signedFull(q.mk - b0.mk) : null });
        }
      }
    } else {
      const c = dash.data('by_category'), s = dash.data('series');
      document.getElementById('over-time-note').textContent = mode === 'net'
        ? 'Each category stacked; the line is net worth, so the gap between the top of the stack and the line is debt.'
        : 'Each category stacked above zero, debt below it.';
      if (prep(box, c.status !== 'ok' ? c : s)) {
        const rowsV = c.data.filter(q => q.view === v && (mode === 'separate' || q.group !== 'Debt'));
        const known = CAT_ORDER.filter(cc => rowsV.some(q => q.category === cc));
        const cats = known.concat([...new Set(rowsV.map(q => q.category))].filter(cc => !known.includes(cc)));
        const nw = {}; s.data.filter(q => q.view === v).forEach(q => { nw[q.date] = q.net_worth; });
        const wide = Array.from(d3.group(rowsV, q => q.date), ([d, rs]) => { const o = { date: parseDay(d), nw: nw[d] }; cats.forEach(cc => { o[cc] = 0; }); rs.forEach(q => { o[q.category] += q.value; }); return o; }).sort((p, q) => p.date - q.date);
        const sel = inRange(wide, r); note.textContent = sel.note;
        const colors = cats.map(catColor);
        cats.forEach((cc, i) => { const it = document.createElement('span'); const sw = document.createElement('i'); sw.style.background = colors[i]; it.append(sw, document.createTextNode(cc)); legend.append(it); });
        stackChart(box, sel.rows, cats, colors, { label: 'Wealth by category', yFmt: axisAmt, lineKey: 'nw', lineLabel: 'Net worth' });
      }
    }

    // breakdown
    const bb = document.getElementById('breakdown-bars'); const bd = dash.data('breakdown');
    if (prep(bb, bd)) drawBars(bb, bd.data.filter(q => q.view === v), 'category', q => catColor(q.category), 'group');

    // exposure
    const eb = document.getElementById('exposure-bars'); const ex = dash.data('exposure');
    if (prep(eb, ex)) {
      const rows = ex.data.filter(q => q.view === v);
      if (rows.length) drawBars(eb, rows, 'region', (q, i) => i === 0 ? dash.colors[0] : 'var(--cds-chart-muted)');
    }

    // loan
    const lb = document.getElementById('chart-loan'); const ln = dash.data('loan');
    const hasLoan = ln.status === 'ok' && ln.data.length > 0;
    document.getElementById('debt-note').hidden = ln.status === 'ok' && !hasLoan;
    document.getElementById('debt-none').hidden = !(ln.status === 'ok' && !hasLoan);
    if (prep(lb, ln) && hasLoan) {
      const rows = ln.data.map(q => ({ date: parseMon(q.month), bal: Number(q.balance) }));
      lineChart(lb, rows, [{ key: 'bal', label: 'Balance', color: 'var(--cds-chart-status-critical)' }], { height: 140, label: 'Scheduled loan balance', yFmt: axisAmt, endFmt: money, tipFmt: q => fullAmt(q), dateFmt: monFmt, zero: true });
    }
    lb.style.minHeight = hasLoan || ln.status !== 'ok' ? '' : '0';

    // holdings
    const order = { Invested: 0, Other: 1, Debt: 2 };
    fillTable('latest_items', 'holdings-body', [
      { key: 'item', tag: (q, row) => row.estimated ? 'estimated' : '' }, { key: 'owner', cls: 'pt-hide-narrow pt-muted', fmt: (q, row) => q === 'Joint' && v !== 'Household' ? 'Joint (' + pct0(row.share) + ')' : q },
      { key: 'category', cls: 'pt-hide-narrow pt-muted' }, { key: 'value', cls: 'pt-r', fmt: q => fullAmt(q), tone: q => q < 0 ? 'pt-down' : '' },
      { key: 'updates_via', cls: 'pt-hide-narrow pt-muted' }
    ], rows => rows.filter(q => q.view === v).sort((a, b) => order[a.group] - order[b.group] || b.value - a.value).map(q => ({ ...q, __key: enc(q.view) + ',' + enc(q.item) })));
    drawCompare();
    fillTable('checkin', 'checkin-body', [
      { key: 'item' }, { key: 'cadence', cls: 'pt-hide-narrow pt-muted' }, { key: 'next', fmt: q => q ? dayFmt(parseDay(q)) : '—' }, { key: 'how', cls: 'pt-hide-narrow pt-muted' }
    ], rows => rows.map(q => ({ ...q, __key: enc(q.item) })));
    const nl = document.getElementById('notes-list'); const nd = dash.data('notes');
    if (prep(nl, nd)) {
      if (!nd.data.length) emptyLine(nl, 'Nothing estimated.');
      nd.data.forEach(q => { const li = document.createElement('li'); li.textContent = q.note; nl.append(li); });
    }
  }

  /* ================= cash & spending ================= */
  function drawCash() {
    const v = owner(), r = range();
    fillMarks('cash_kpis', el => 'view=' + enc(v));
    fillMarks('cf_kpis');
    fillMarks('goals_kpis');
    const bbx = document.getElementById('cash-budget-bars'); const bd = dash.data('budget');
    if (prep(bbx, bd)) { const rows = bd.data.filter(q => q.period === '12M'); if (rows.length) drawBudgetBars(bbx, rows, 'pct'); else emptyLine(bbx, 'Add your monthly income and spending to compare them with your goals.'); }
    fillTable('cash_items', 'cash-body', [
      { key: 'item' }, { key: 'owner', cls: 'pt-hide-narrow pt-muted', fmt: q => q === 'Joint' && v !== 'Household' ? 'Joint (share)' : q }, { key: 'value', cls: 'pt-r', fmt: q => fullAmt(q) }
    ], rows => rows.filter(q => q.view === v).map(q => ({ ...q, __key: enc(q.view) + ',' + enc(q.item) })), 'No cash accounts');
    const cb = document.getElementById('chart-cash'), cn = document.getElementById('cash-range-note'); cn.textContent = '';
    const cs = dash.data('cash_series');
    if (prep(cb, cs)) {
      const sel = inRange(cs.data.filter(q => q.view === v).map(q => ({ date: parseDay(q.date), cash: q.cash })).sort((a, b) => a.date - b.date), r); cn.textContent = sel.note;
      lineChart(cb, sel.rows, [{ key: 'cash', label: 'Cash', color: dash.colors[0] }], { label: 'Cash over time', yFmt: axisAmt, endFmt: money, tipFmt: q => fullAmt(q), zero: true });
    }
    const fb = document.getElementById('chart-cf'), fn = document.getElementById('cf-range-note'), lg = document.getElementById('cf-legend');
    fn.textContent = ''; lg.replaceChildren();
    [['Income', dash.colors[0]], ['Spending', 'var(--cds-chart-muted)'], ['Left over', dash.colors[1]]].forEach(([t, c]) => { const it = document.createElement('span'); const sw = document.createElement('i'); sw.style.background = c; it.append(sw, document.createTextNode(t)); lg.append(it); });
    const cf = dash.data('cashflow');
    if (prep(fb, cf)) {
      const all = cf.data.map(q => ({ month: q.month, date: parseMon(q.month), income: Number(q.revenues), spending: Number(q.spending) - Number(q.loan_principal || 0), saved: Number(q.savings_adjusted) })).sort((a, b) => a.date - b.date);
      if (!all.length) emptyLine(fb, 'Add your monthly income and spending to see this.');
      else { let sel = inRange(all, r); if (sel.rows.length < 3) sel = { rows: all.slice(-3), note: 'Showing the last three months.' }; fn.textContent = sel.note; barLineChart(fb, sel.rows); }
    }
    const sb = document.getElementById('spend-bars'); const sc = dash.data('spend_cats');
    if (prep(sb, sc)) {
      if (!sc.data.length) emptyLine(sb, 'Add your monthly spending to see where the money goes.');
      else drawBars(sb, sc.data, 'category', q => q.kind === 'Needs' ? dash.colors[0] : q.kind === 'Wants' ? dash.colors[1] : 'var(--cds-chart-muted)', 'kind');
    }
  }

  /* ================= goals ================= */
  const BUCKET_COLOR = { needs: () => dash.colors[0], wants: () => dash.colors[1], savings: () => dash.colors[2] };
  const bucketColor = (k) => (BUCKET_COLOR[k] || (() => 'var(--cds-chart-muted)'))();
  function drawBudgetBars(box, rows, unit) {
    const val = r => unit === 'eur' ? r.actual : r.share, tgt = r => unit === 'eur' ? r.target_eur : r.target_share;
    const fmt = v => v == null ? '—' : unit === 'eur' ? fullAmt(v) : pct(v);
    const fmtT = v => v == null ? '—' : unit === 'eur' ? fullAmt(v) : pct0(v);
    const max = (d3.max(rows, r => Math.max(val(r) || 0, tgt(r) || 0)) || 1) * 1.08;
    rows.forEach(r => {
      const row = document.createElement('div'); row.className = 'pt-bar-row';
      const lab = document.createElement('span'); lab.className = 'pt-bar-label'; lab.textContent = r.label;
      const track = document.createElement('div'); track.className = 'pt-bar-track';
      const fill = document.createElement('div'); fill.className = 'pt-bar-fill';
      fill.style.width = (Math.max(0, val(r) || 0) / max * 100) + '%'; fill.style.background = r.met ? bucketColor(r.bucket) : 'var(--cds-chart-status-critical)';
      const tick = document.createElement('div'); tick.className = 'pt-bar-tick'; tick.style.left = 'calc(' + (Math.max(0, tgt(r) || 0) / max * 100) + '% - 1px)';
      track.append(fill, tick);
      const vv = document.createElement('span'); vv.className = 'pt-bar-val';
      const st = document.createElement('span'); st.className = 'pt-strong'; st.textContent = fmt(val(r));
      vv.append(st, document.createTextNode((r.direction === 'min' ? ' · goal at least ' : ' · limit ') + fmtT(tgt(r))));
      row.append(lab, track, vv); box.append(row);
    });
  }
  function drawBudgetTrend(box, rows, goals, unit) {
    const grid = document.createElement('div'); grid.className = 'pt-trend-grid'; box.append(grid);
    const panels = [['needs', 'Needs'], ['wants', 'Wants'], ['savings', 'Savings']].map(([k, name]) => {
      const panel = document.createElement('div'); panel.className = 'pt-trend-panel'; grid.append(panel); return [k, name, panel];
    });
    panels.forEach(([k, name, panel]) => {
      const g = goals.find(q => q.kind === 'budget' && q.metric === k);
      const gAmt = g && (g.unit === 'eur' || g.unit === 'amount');
      const head = document.createElement('div'); head.className = 'pt-kpi-label'; head.textContent = name + (g ? (k === 'savings' ? ', goal at least ' : ', limit ') + (gAmt ? fullAmt(g.target) + ' a month' : g.target + '% of income') : ', no goal set');
      panel.append(head);
      const val = q => unit === 'eur' ? q[k] : q[k + '_share'];
      const tgt = q => !g ? null : gAmt ? (unit === 'eur' ? Number(g.target) : (q.income ? Number(g.target) / q.income : null)) : (unit === 'eur' ? q.income * Number(g.target) / 100 : Number(g.target) / 100);
      const pts = rows.map(q => ({ ...q, v: val(q), t: tgt(q) })).filter(q => isNum(q.v));
      if (!pts.length) return;
      const W = Math.max(220, panel.clientWidth || 300), H = 150, mt = 8, mb = 22, mr = 6;
      const svg = d3.select(panel).append('svg').attr('width', '100%').attr('viewBox', `0 0 ${W} ${H}`).attr('role', 'img').attr('aria-label', name + ' each month against the goal').style('font-family', 'var(--font-anthropic-sans)');
      const all = pts.flatMap(q => [q.v, q.t]).filter(isNum);
      const y = d3.scaleLinear([Math.min(0, d3.min(all)), Math.max(0, d3.max(all))], [H - mb, mt]).nice(3);
      const yFmt = unit === 'eur' ? axisAmt : (q => d3.format('.0%')(q));
      const ticks = y.ticks(3); const ml = d3.max(ticks, t => measureText(svg, yFmt(t))) + 8;
      const x = d3.scaleBand(pts.map(q => q.month), [ml, W - mr]).paddingInner(0.25).paddingOuter(0.1);
      ticks.forEach(t => {
        svg.append('line').attr('x1', ml).attr('x2', W - mr).attr('y1', y(t)).attr('y2', y(t)).style('stroke', t === 0 ? 'var(--cds-chart-axis)' : 'var(--cds-chart-grid)').style('stroke-width', '1px');
        svg.append('text').attr('x', ml - 6).attr('y', y(t)).attr('dy', '0.32em').attr('text-anchor', 'end').style('fill', 'var(--color-fg-muted)').style('font-size', 'var(--cds-font-size-caption)').text(yFmt(t));
      });
      const ok = q => !isNum(q.t) || (k === 'savings' ? q.v >= q.t : q.v <= q.t);
      pts.forEach(q => svg.append('rect').attr('x', x(q.month)).attr('width', x.bandwidth()).attr('y', y(Math.max(0, q.v))).attr('height', Math.max(1, Math.abs(y(q.v) - y(0))))
        .attr('rx', Math.min(3, x.bandwidth() / 2)).style('fill', ok(q) ? bucketColor(k) : 'var(--cds-chart-status-critical)'));
      const tp = pts.filter(q => isNum(q.t));
      if (tp.length) svg.append('path').datum(tp).attr('d', d3.line().x(q => x(q.month) + x.bandwidth() / 2).y(q => y(q.t)).curve(d3.curveStep))
        .style('fill', 'none').style('stroke', 'var(--color-fg)').style('stroke-width', '1.5px').style('stroke-dasharray', '4 3');
      const every = Math.max(1, Math.ceil(pts.length / Math.max(2, Math.floor((W - ml - mr) / 52))));
      pts.forEach((q, i) => { if ((pts.length - 1 - i) % every) return; svg.append('text').attr('x', x(q.month) + x.bandwidth() / 2).attr('y', H - mb + 15).attr('text-anchor', 'middle').style('fill', 'var(--color-fg-muted)').style('font-size', 'var(--cds-font-size-caption)').text(d3.utcFormat('%b %y')(parseMon(q.month))); });
      const tip = tipBox(panel); const fmt = v => unit === 'eur' ? fullAmt(v) : pct(v);
      svg.append('rect').attr('x', ml).attr('y', mt).attr('width', Math.max(0, W - ml - mr)).attr('height', H - mt - mb).style('fill', 'transparent')
        .on('pointermove', (ev) => {
          const [px] = d3.pointer(ev); const q = d3.least(pts, p => Math.abs(x(p.month) + x.bandwidth() / 2 - px));
          tip.replaceChildren(); const dt = document.createElement('div'); dt.className = 'pt-tip-date'; dt.textContent = monFmt(parseMon(q.month)); tip.append(dt);
          tipLine(tip, ok(q) ? bucketColor(k) : 'var(--cds-chart-status-critical)', name + ' ' + fmt(q.v));
          if (isNum(q.t)) tipLine(tip, 'var(--color-fg)', (k === 'savings' ? 'Goal ' : 'Limit ') + fmt(q.t));
          tipLine(tip, null, 'Income ' + fullAmt(q.income), true);
          placeTip(tip, panel, W, x(q.month) + x.bandwidth() / 2, mt + 30);
        }).on('pointerleave', () => { tip.style.display = 'none'; });
    });
  }
  const statusCols = (fmtNum) => [
    { key: 'label' }, { key: 'view', cls: 'pt-hide-narrow pt-muted', fmt: q => q === 'Household' && PEOPLE.length < 2 ? 'You' : q },
    { key: 'target', cls: 'pt-r', fmt: (q, row) => (row.direction === 'min' ? 'at least ' : 'at most ') + fmtNum(q, row, true) },
    { key: 'current', cls: 'pt-r', fmt: (q, row) => fmtNum(q, row, false) },
    { key: 'progress', cls: 'pt-r pt-hide-narrow', fmt: q => q == null ? '—' : pct0(q) },
    { key: 'deadline', fmt: q => q ? monFmt(parseMon(q)) : '—' },
    { key: 'projected', cls: 'pt-hide-narrow', fmt: (q, row) => q ? monFmt(parseMon(q)) : row.kind === 'budget' || row.status === 'Reached' || row.status === 'No data' ? '—' : 'Not at this pace' },
    { key: 'status', tone: q => GOOD.includes(q) ? 'pt-up' : q === 'Not yet' ? 'pt-warn' : q === 'No data' ? 'pt-muted' : 'pt-down' }
  ];
  const goalNum = (q, row, isTarget) => {
    if (q == null) return '—';
    if (row.unit === 'pct') return d3.format(isTarget ? '.0f' : '.1f')(q) + '% of income';
    if (row.unit === 'months') return d3.format('.1~f')(q) + ' months';
    return row.kind === 'budget' ? fullAmt(q) + ' a month' : money(q);
  };
  function drawGoals() {
    const per = bperiod(), unit = gunit();
    document.querySelectorAll('.pt #goals [data-source="budget"][data-where]').forEach(el => el.setAttribute('data-where', el.getAttribute('data-where').replace(/period=[^&]*/, 'period=' + per)));
    document.querySelectorAll('.pt .pt-g-main').forEach(el => el.setAttribute('data-field', unit === 'eur' ? 'actual' : 'share'));
    document.querySelectorAll('.pt .pt-g-alt').forEach(el => el.setAttribute('data-field', unit === 'eur' ? 'share' : 'actual'));
    document.querySelectorAll('.pt .pt-g-target').forEach(el => el.setAttribute('data-field', unit === 'eur' ? 'target_eur' : 'target_share'));
    document.querySelectorAll('.pt .pt-g-alt-unit').forEach(el => { el.textContent = unit === 'eur' ? 'of income' : 'a month'; });
    fillMarks('budget'); fillMarks('goals_kpis');
    document.querySelectorAll('.pt .pt-g-status').forEach(toneStatus);
    const tb = document.getElementById('chart-budget'), tn = document.getElementById('budget-range-note'); tn.textContent = '';
    const bm = dash.data('budget_months'), gl = dash.data('goals');
    if (prep(tb, bm.status !== 'ok' ? bm : gl)) {
      const all = bm.data.map(q => ({ ...q, date: parseMon(q.month) }));
      if (!all.length) emptyLine(tb, 'Add your monthly income and spending to track the budget rule.');
      else { let sel = inRange(all, range()); if (sel.rows.length < 3) sel = { rows: all.slice(-3), note: 'Showing the last three months.' }; tn.textContent = sel.note; drawBudgetTrend(tb, sel.rows, gl.data, unit); }
    }
    fillTable('goal_status', 'goals-body', statusCols(goalNum), rows => rows.map(q => ({ ...q, __key: enc(q.id) })), 'No goals yet: ask Claude to add one.');
    drawProjection();
    fillTable('budget_map', 'budget-map-body', [{ key: 'category' }, { key: 'bucket' }],
      rows => rows.map(q => ({ ...q, __key: enc(q.kind) + ',' + enc(q.category) })), 'No spending categories yet');
  }

  /* ================= how you compare ================= */
  const pctTxt = r => {
    if (r.percentile == null) return '—';
    if (r.bound === 'above') return 'Above P' + r.percentile + ' · top ' + (100 - r.percentile) + '%';
    if (r.bound === 'below') return 'Below P' + r.percentile;
    const p = r.percentile; return (r.estimated ? '≈ ' : '') + 'P' + p + ' · ' + (p >= 50 ? 'top ' + Math.max(1, 100 - p) + '%' : 'bottom ' + Math.max(1, p) + '%');
  };
  const curFmt = (v, cur) => v == null ? '—' : ((v < 0 ? '−' : '') + (cur === 'USD' ? '$' : '€') + absTxt(v));
  function drawCompare() {
    const box = document.getElementById('cmp-list'), chips = document.getElementById('cmp-countries');
    const v = owner(), pen = ppen(); const d = dash.data('peers_view');
    document.getElementById('cmp-who').textContent = v === 'Household' ? (PEOPLE.length > 1 ? 'the household' : 'you') : v;
    chips.replaceChildren();
    if (!prep(box, d)) return;
    const rows = d.data.filter(r => r.view === v && (r.pension === 'na' || r.pension === pen));
    const names = new Map(); rows.forEach(r => { if (r.country) names.set(r.country, r.country_name); });
    const added = String(P().padd || '').split(',').filter(c => names.has(c));
    const hidden = String(P().phide || '').split(',').filter(Boolean);
    const defaults = [...new Set(rows.filter(r => r.is_default).sort((a, b) => a.default_rank - b.default_rank).map(r => r.country))];
    const shown = [...defaults, ...added.filter(c => !defaults.includes(c))].filter(c => !hidden.includes(c));
    const toggle = (c) => {
      if (defaults.includes(c)) { const h = hidden.includes(c) ? hidden.filter(x => x !== c) : hidden.concat([c]); dash.setParams({ phide: h.join(',') || null }); }
      else dash.setParams({ padd: added.filter(x => x !== c).join(',') || null });
    };
    [...defaults, ...added.filter(c => !defaults.includes(c))].forEach(c => {
      const b = document.createElement('button'); b.className = 'pt-chip'; b.setAttribute('aria-pressed', String(shown.includes(c)));
      b.textContent = names.get(c) || c; b.addEventListener('click', () => toggle(c)); chips.append(b);
    });
    const sel = document.createElement('select'); sel.setAttribute('aria-label', 'Add a country');
    sel.append(new Option('+ Add a country', ''));
    [...names.entries()].filter(([c]) => !defaults.includes(c) && !added.includes(c)).sort((a, b) => a[1].localeCompare(b[1])).forEach(([c, n]) => sel.append(new Option(n, c)));
    sel.addEventListener('change', () => { if (sel.value) dash.setParams({ padd: added.concat([sel.value]).join(',') }); });
    chips.append(sel);
    const order = [...new Set(rows.map(r => r.metric))];
    order.forEach(metric => {
      const mr = rows.filter(r => r.metric === metric); if (!mr.length) return;
      const wrap = document.createElement('div'); wrap.className = 'pt-cmp-metric';
      const head = document.createElement('div'); head.className = 'pt-cmp-head';
      const t = document.createElement('span'); t.className = 'pt-cmp-title'; t.textContent = mr[0].metric_label;
      const you = document.createElement('span'); you.className = 'pt-cmp-you';
      const yv = mr[0].you; const b = document.createElement('b');
      b.textContent = yv == null ? 'not set' : metric === 'saving_rate' ? pct(yv) : fullAmt(yv) + (metric === 'net_wealth' ? '' : ' a year');
      you.append(document.createTextNode(v === 'Household' ? (PEOPLE.length > 1 ? 'Household: ' : 'You: ') : v + ': '), b);
      if (metric === 'net_wealth') you.append(document.createTextNode(pen === 'with' ? ' (pensions included)' : ' (pensions left out)'));
      if (metric === 'saving_rate') you.append(document.createTextNode(' of income, pension contributions included'));
      head.append(t, you); wrap.append(head);
      if (mr[0].you_note) { const nt = document.createElement('div'); nt.className = 'pt-cmp-note'; nt.textContent = mr[0].you_note; wrap.append(nt); }
      shown.forEach(c => {
        const cr = mr.filter(r => r.country === c); if (!cr.length) return;
        const row = document.createElement('div'); row.className = 'pt-cmp-country';
        const nm = document.createElement('span'); nm.className = 'pt-cmp-name'; nm.textContent = cr[0].country_name; row.append(nm);
        cr.forEach(r => {
          const line = document.createElement('div'); line.className = 'pt-cmp-line';
          const lab = document.createElement('span'); lab.textContent = r.population === 'all' ? (metric === 'equiv_income' ? 'Everyone' : metric === 'earnings' ? 'All full-time' : 'All households') : (r.pop_label || '').replace('Households, main earner aged ', 'Aged ').replace('Households, main earner under ', 'Under ').replace('Households, head under ', 'Under ').replace('Households, head aged ', 'Aged ').replace('Full-time employees ', '').replace('aged ', 'Aged ');
          if (metric === 'saving_rate') {
            const val = document.createElement('span'); val.style.gridColumn = '2 / span 2';
            val.textContent = r.national == null ? 'No national figure' : 'National average ' + pct(r.national) + ' (' + String(r.ref_month).slice(0, 4) + ')';
            line.append(lab, val); row.append(line); return;
          }
          const track = document.createElement('div'); track.className = 'pt-cmp-track';
          const mid = document.createElement('div'); mid.className = 'pt-cmp-mid';
          if (r.percentile != null) {
            const fill = document.createElement('div'); fill.className = 'pt-cmp-fill'; fill.style.width = Math.max(2, r.percentile) + '%';
            fill.style.background = dash.colors[0]; if (r.estimated) fill.style.opacity = '0.55'; track.append(fill);
          }
          track.append(mid);
          const val = document.createElement('span');
          if (r.percentile != null) {
            const st = document.createElement('span'); st.className = 'pt-strong'; st.textContent = pctTxt(r); val.append(st);
            if (r.median != null) val.append(document.createTextNode(' · median ' + curFmt(r.median, r.currency)));
          } else val.textContent = r.missing === 'Median only' && r.median != null ? 'Median ' + curFmt(r.median, r.currency) + (r.ratio ? ' · you ' + d3.format('.1f')(r.ratio) + '×' : '') : (r.missing || '—');
          line.title = (r.source || '') + (r.ref_month ? ', ' + r.ref_month : '') + (r.estimated ? ' · estimated' : '');
          line.append(lab, track, val); row.append(line);
        });
        wrap.append(row);
      });
      box.append(wrap);
    });
    if (!shown.length) { const e = document.createElement('div'); e.className = 'pt-cmp-empty'; e.textContent = 'Pick a country above.'; box.append(e); }
  }

  /* ================= projection ================= */
  function drawProjection() {
    const metric = pmetric(), real = preal() === 'real', suffix = real ? '_real' : '';
    document.querySelectorAll('.pt #proj-kpis [data-source="projection_summary"][data-field^="end_"]').forEach(el => {
      const sc = el.getAttribute('data-field').split('_')[1]; el.setAttribute('data-field', 'end_' + sc + '_' + metric + suffix);
    });
    fillMarks('projection_summary');
    const box = document.getElementById('chart-proj'), lg = document.getElementById('proj-legend'); lg.replaceChildren();
    const pr = dash.data('projection'), pk = dash.data('projection_kpis');
    const names = { low: 'Cautious', mid: 'Middle', high: 'Strong' }, cols = { low: 'var(--cds-chart-muted)', mid: dash.colors[0], high: dash.colors[1] };
    if (prep(box, pr)) {
      const by = {}; pr.data.forEach(r => { const o = by[r.month] || (by[r.month] = { date: parseMon(r.month) }); o[r.scenario] = r[metric + suffix]; });
      const rows = Object.values(by).sort((a, b) => a.date - b.date);
      const series = ['high', 'mid', 'low'].map(k => ({ key: k, label: names[k], color: cols[k], width: k === 'mid' ? '2.5px' : '1.75px' }));
      ['low', 'mid', 'high'].forEach(k => { const it = document.createElement('span'); const sw = document.createElement('i'); sw.style.background = cols[k]; it.append(sw, document.createTextNode(names[k])); lg.append(it); });
      const goals = pk.status === 'ok' ? pk.data.filter(g => g.metric === metric) : [];
      lineChart(box, rows, series, { label: 'Projected ' + (metric === 'net_worth' ? 'net worth' : 'assets'), yFmt: axisAmt, endFmt: money, tipFmt: q => fullAmt(q), dateFmt: monFmt, zero: true, refLines: goals.map(g => ({ y: g.target, label: g.label })) });
    }
    document.querySelectorAll('.pt #proj-table th[data-field]').forEach(th => { const f = th.getAttribute('data-field').replace('_real', ''); th.setAttribute('data-field', ['low', 'mid', 'high'].includes(f) ? f + suffix : f); });
    const when = q => q ? monFmt(parseMon(q)) : 'Not within the projection';
    fillTable('projection_kpis', 'proj-body', [{ key: 'label' }, { key: 'target', cls: 'pt-r', fmt: q => money(q) },
      { key: 'low' + suffix, cls: 'pt-r', fmt: when }, { key: 'mid' + suffix, cls: 'pt-r', fmt: when }, { key: 'high' + suffix, cls: 'pt-r', fmt: when }],
      rows => rows.map(q => ({ ...q, __key: enc(q.goal) })), 'Ask Claude for an amount goal (net worth, assets or invested) to see when you could reach it.');
  }

  /* ================= investments ================= */
  let invSort = { key: 'value', dir: -1 };
  const invCols = [
    { key: 'name', fmt: (q, row) => q + (row.ticker && row.ticker !== q ? ' · ' + row.ticker : '') }, { key: 'account', cls: 'pt-hide-narrow pt-muted' },
    { key: 'quantity', cls: 'pt-r pt-hide-narrow', fmt: (q, row) => q == null ? '—' : d3.format(',.4~f')(q) + (row.unit ? ' ' + row.unit : '') },
    { key: 'price', cls: 'pt-r pt-hide-narrow', fmt: (q, row) => priceTxt(q, row.currency) },
    { key: 'value', cls: 'pt-r', fmt: q => fullAmt(q) }, { key: 'weight', cls: 'pt-r pt-hide-narrow', fmt: q => pct(q) },
    { key: 'gain', cls: 'pt-r', fmt: q => q == null ? '—' : signedFull(q), tone: q => q == null ? '' : q < 0 ? 'pt-down' : 'pt-up' },
    { key: 'ret', cls: 'pt-r', fmt: q => q == null ? '—' : signedPct(q), tone: q => q == null ? '' : q < 0 ? 'pt-down' : 'pt-up' }
  ];
  const sortInv = rows => rows.sort((a, b) => { const x = a[invSort.key], y = b[invSort.key]; if (typeof x === 'string' || typeof y === 'string') return invSort.dir * String(x || '').localeCompare(String(y || '')); return invSort.dir * ((x == null ? -Infinity : x) - (y == null ? -Infinity : y)); });
  function drawInvMultiples(v) {
    const box = document.getElementById('inv-mini'); if (!box) return;
    const pos = dash.data('inv_positions'), hist = dash.data('price_history'); box.replaceChildren();
    if (pos.status !== 'ok' || hist.status !== 'ok') {
      const bad = [pos, hist].find(d => d.status !== 'ok' && d.status !== 'loading');
      if (bad) { box.classList.remove('dash-skeleton'); failLine(box, 'Failed to load'); } else box.classList.add('dash-skeleton');
      return;
    }
    box.classList.remove('dash-skeleton');
    const rows = pos.data.filter(p => p.view === v && !p.is_cash && p.price != null);
    if (!rows.length) { emptyLine(box, 'No positions with a price yet.'); return; }
    const byId = d3.group(hist.data, q => q.holding); const cw = 200, ch = 56;
    rows.forEach(p => {
      const card = document.createElement('div'); card.className = 'pt-mini';
      const head = document.createElement('div'); head.className = 'pt-mini-head';
      const sym = document.createElement('span'); sym.className = 'pt-mini-sym'; sym.textContent = p.ticker || p.name; sym.title = p.name;
      const chg = document.createElement('span'); chg.textContent = p.ret == null ? '—' : signedPct(p.ret); chg.className = p.ret == null ? 'pt-muted' : p.ret < 0 ? 'pt-down' : 'pt-up';
      head.append(sym, chg);
      const sub = document.createElement('div'); sub.className = 'pt-mini-sub'; sub.textContent = fullAmt(p.value) + ' · ' + pct(p.weight);
      card.append(head, sub);
      const series = (byId.get(p.id) || []).map(q => ({ date: parseDay(q.date), close: Number(q.price) })).filter(q => isNum(q.close)).sort((a, b) => a.date - b.date);
      if (series.length < 2) { const e = document.createElement('div'); e.className = 'pt-mini-empty'; e.textContent = 'The line grows with each monthly update'; card.append(e); }
      else {
        const ys = series.map(q => q.close).concat(isNum(p.avg_price) ? [p.avg_price] : []);
        const y = d3.scaleLinear(d3.extent(ys), [ch - 4, 4]);
        const x = d3.scaleUtc(d3.extent(series, q => q.date), [2, cw - 6]);
        const svg = d3.select(card).append('svg').attr('width', '100%').attr('viewBox', `0 0 ${cw} ${ch}`).attr('role', 'img').attr('aria-label', (p.ticker || p.name) + ' price at each update');
        if (isNum(p.avg_price)) svg.append('line').attr('x1', 2).attr('x2', cw - 6).attr('y1', y(p.avg_price)).attr('y2', y(p.avg_price)).style('stroke', 'var(--cds-chart-reference)').style('stroke-width', '1px').style('stroke-dasharray', '3 3');
        const color = p.ret != null && p.ret < 0 ? 'var(--cds-chart-status-critical)' : dash.colors[0];
        svg.append('path').datum(series).attr('d', d3.line().x(q => x(q.date)).y(q => y(q.close))).style('fill', 'none').style('stroke', color).style('stroke-width', '1.75px').style('stroke-linejoin', 'round').style('stroke-linecap', 'round');
        const lp = series[series.length - 1]; svg.append('circle').attr('cx', x(lp.date)).attr('cy', y(lp.close)).attr('r', 2.5).style('fill', color);
      }
      box.append(card);
    });
  }
  function drawInvestments() {
    const v = owner();
    const whereView = el => el.getAttribute('data-where').replace(/view=[^&]*/, 'view=' + enc(v));
    const k = fillMarks('inv_kpis', whereView); const kr = k && k.find(q => q.view === v);
    const who = document.getElementById('inv-who'); if (who) who.textContent = whoLabel(v);
    const dir = document.getElementById('inv-dir'); if (dir) dir.textContent = kr && kr.gain < 0 ? 'down' : 'up';
    const cb = document.getElementById('inv-class-bars'); const cl = dash.data('inv_classes');
    if (cb && prep(cb, cl)) { const rows = cl.data.filter(q => q.view === v).map(q => ({ ...q, label: q.class.charAt(0).toUpperCase() + q.class.slice(1) })); if (rows.length) drawBars(cb, rows, 'label', (q, i) => dash.colors[i] || 'var(--cds-chart-muted)'); else emptyLine(cb, 'No positions yet.'); }
    const ab = document.getElementById('inv-account-bars'); const ac = dash.data('inv_accounts');
    if (ab && prep(ab, ac)) { const rows = ac.data.filter(q => q.view === v); if (rows.length) drawBars(ab, rows, 'account', (q, i) => dash.colors[i] || 'var(--cds-chart-muted)'); else emptyLine(ab, 'No positions yet.'); }
    fillTable('inv_positions', 'inv-body', invCols, rows => sortInv(rows.filter(q => q.view === v)).map(q => ({ ...q, __key: enc(q.view) + ',' + enc(q.id) })), 'No positions yet: ask Claude to add what your investment accounts hold.');
    drawInvMultiples(v);
  }

  window.wdKit = { FMT, fillMarks, prep, failLine, emptyLine, lineChart, fillTable, inRange, parseDay, monFmt, dayFmt, pct, signedPct, fullAmt, signedFull, money, axisAmt, priceTxt, isNum, enc };

  /* ================= tabs and controls ================= */
  const TABS = ['overview', 'cash', 'goals', 'investments'].concat(document.getElementById('live') ? ['live'] : []);
  const ready = { investments: false, live: false };
  let current = 'overview';
  function mountTemplate(tab) {
    if (ready[tab] === undefined || ready[tab]) return;
    const host = document.getElementById(tab); const tpl = document.getElementById(tab + '-tpl'); if (!host || !tpl) return;
    host.append(tpl.content.cloneNode(true)); ready[tab] = true;
    if (tab === 'investments') host.querySelectorAll('#inv-table th.pt-sortable').forEach(th => th.addEventListener('click', () => {
      const key = th.getAttribute('data-field'); invSort = { key, dir: invSort.key === key ? -invSort.dir : (key === 'name' || key === 'account' ? 1 : -1) };
      host.querySelectorAll('#inv-table th.pt-sortable').forEach(o => o.removeAttribute('aria-sort'));
      th.setAttribute('aria-sort', invSort.dir > 0 ? 'ascending' : 'descending');
      drawInvestments();
    }));
    if (tab === 'live' && window.wdLive) window.wdLive.mount(host);
  }
  function show(tab) {
    if (!TABS.includes(tab)) tab = 'overview';
    current = tab;
    document.querySelectorAll('.pt .pt-tab').forEach(b => b.setAttribute('aria-selected', String(b.dataset.tab === tab)));
    TABS.forEach(t => { const el = document.getElementById(t); if (el) el.hidden = t !== tab; });
    mountTemplate(tab);
    dash.setLink(tab); drawAll();
  }
  function buildOwnerSeg() {
    const seg = document.getElementById('owner-seg'); const want = VIEWS();
    const have = [...seg.querySelectorAll('button')].map(b => b.dataset.owner);
    if (have.join('|') !== want.join('|')) {
      seg.replaceChildren();
      want.forEach(vw => { const b = document.createElement('button'); b.dataset.owner = vw; b.textContent = vw; b.addEventListener('click', () => dash.setParams({ owner: vw })); seg.append(b); });
    }
    seg.style.display = want.length > 1 && current !== 'goals' && current !== 'live' ? '' : 'none';
  }
  function sync() {
    const pairs = [['owner-seg', 'owner', owner()], ['range-seg', 'range', range()], ['view-seg', 'view', chartView()], ['debt-seg', 'debt', debtMode()], ['bperiod-seg', 'bperiod', bperiod()], ['gunit-seg', 'gunit', gunit()], ['ppen-seg', 'ppen', ppen()], ['pmetric-seg', 'pmetric', pmetric()], ['preal-seg', 'preal', preal()]];
    pairs.forEach(([id, attr, val]) => document.querySelectorAll(`.pt #${id} button`).forEach(b => b.setAttribute('aria-pressed', String(b.dataset[attr] === val))));
    document.getElementById('range-seg').style.display = current === 'investments' ? 'none' : '';
  }
  [['range-seg', 'range'], ['view-seg', 'view'], ['debt-seg', 'debt'], ['bperiod-seg', 'bperiod'], ['gunit-seg', 'gunit'], ['ppen-seg', 'ppen'], ['pmetric-seg', 'pmetric'], ['preal-seg', 'preal']].forEach(([id, attr]) =>
    document.querySelectorAll(`.pt #${id} button`).forEach(b => b.addEventListener('click', () => dash.setParams({ [attr]: b.dataset[attr] }))));
  function drawAll() {
    readSettings(); setCategoryOrder(); buildOwnerSeg(); sync();
    fillMarks('kpis', el => el.closest('#asof-pill') ? 'view=Household' : el.getAttribute('data-where'));
    if (current === 'overview') drawOverview(); else if (current === 'cash') drawCash(); else if (current === 'goals') drawGoals(); else if (current === 'investments') drawInvestments(); else if (window.wdLive) window.wdLive.draw(range());
  }
  document.querySelectorAll('.pt .pt-tab').forEach(b => b.addEventListener('click', () => show(b.dataset.tab)));
  document.querySelectorAll('.pt [data-goto]').forEach(b => b.addEventListener('click', () => { show(b.dataset.goto); window.scrollTo(0, 0); }));
  dash.onData(drawAll);
  const h = location.hash.slice(1); if (TABS.includes(h) && h !== 'overview') show(h);
})();
