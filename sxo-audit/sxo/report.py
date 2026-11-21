"""Write the shareable, self-contained HTML dashboard."""
from __future__ import annotations

import json
from pathlib import Path

TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SXO Competitor Audit</title>
<style>
:root{
  --bg:#f6f7f9;--surface:#fff;--surface-2:#f0f2f5;--text:#16191f;--muted:#5d6470;--border:#e1e4ea;
  --accent:#0f6e5a;--pass:#1a7f4b;--pass-bg:#e3f4ea;--warn:#9a6300;--warn-bg:#fdf1d8;
  --fail:#b42318;--fail-bg:#fde7e5;--info:#4b5563;--info-bg:#eceef2;--bar:#d9dde4;
}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){
  --bg:#0f1115;--surface:#171a20;--surface-2:#1e222a;--text:#e8eaee;--muted:#9aa2ae;--border:#2a2f38;
  --accent:#4fc1a6;--pass:#5fd394;--pass-bg:#173326;--warn:#f0b54a;--warn-bg:#3a2c12;
  --fail:#ff8a7f;--fail-bg:#3d1c1a;--info:#b5bcc7;--info-bg:#262a32;--bar:#2e333c;}}
:root[data-theme="dark"]{
  --bg:#0f1115;--surface:#171a20;--surface-2:#1e222a;--text:#e8eaee;--muted:#9aa2ae;--border:#2a2f38;
  --accent:#4fc1a6;--pass:#5fd394;--pass-bg:#173326;--warn:#f0b54a;--warn-bg:#3a2c12;
  --fail:#ff8a7f;--fail-bg:#3d1c1a;--info:#b5bcc7;--info-bg:#262a32;--bar:#2e333c;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:28px 16px 64px}
h1{font-size:26px;margin:0 0 4px;letter-spacing:-.01em}
h2{font-size:18px;margin:36px 0 12px}
.sub{color:var(--muted);margin:0}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px;margin-top:22px}
.card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:18px}
.card.ours{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent) inset}
.card h3{margin:0;font-size:15px}
.card .url{color:var(--muted);font-size:12px;word-break:break-all}
.big{font-size:44px;font-weight:700;line-height:1;margin:14px 0 2px;font-variant-numeric:tabular-nums}
.big small{font-size:14px;color:var(--muted);font-weight:500}
.bars{margin-top:14px;display:grid;gap:8px}
.bar{display:grid;grid-template-columns:42px 1fr 34px;align-items:center;gap:8px;font-size:13px}
.track{height:8px;background:var(--bar);border-radius:99px;overflow:hidden}
.fill{height:100%;border-radius:99px;background:var(--accent)}
.num{text-align:right;font-variant-numeric:tabular-nums;color:var(--muted)}
.chip{display:inline-block;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.04em;padding:2px 7px;border-radius:99px;white-space:nowrap}
.pass{color:var(--pass);background:var(--pass-bg)}.warn{color:var(--warn);background:var(--warn-bg)}
.fail{color:var(--fail);background:var(--fail-bg)}.info{color:var(--info);background:var(--info-bg)}
.list{display:grid;gap:10px}
.item{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:12px 14px}
.item .t{display:flex;gap:8px;align-items:center;flex-wrap:wrap;font-weight:600}
.item .s{color:var(--muted);font-size:14px;margin-top:4px}
.item .r{font-size:14px;margin-top:6px}
.sec{font-size:11px;color:var(--muted);border:1px solid var(--border);border-radius:4px;padding:0 5px}
.tabs{display:flex;gap:6px;margin:36px 0 12px;flex-wrap:wrap}
.tab{border:1px solid var(--border);background:var(--surface);color:var(--text);border-radius:99px;padding:6px 14px;font:inherit;cursor:pointer}
.tab[aria-selected="true"]{background:var(--accent);border-color:var(--accent);color:#fff}
.tablewrap{overflow-x:auto;background:var(--surface);border:1px solid var(--border);border-radius:12px}
table{border-collapse:collapse;width:100%}
th,td{text-align:left;vertical-align:top;padding:10px 12px;border-bottom:1px solid var(--border);font-size:14px}
th{font-size:12px;color:var(--muted);font-weight:600;text-transform:uppercase;letter-spacing:.04em;background:var(--surface-2)}
tr.check{cursor:pointer}tr.check:hover td{background:var(--surface-2)}
tr.check td:first-child{font-weight:600;min-width:180px}
.cell .s{color:var(--muted);font-size:13px;margin-top:3px}
tr.detail td{background:var(--surface-2);padding:14px}
.dgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:14px}
.dgrid h4{margin:0 0 6px;font-size:13px}
.miniwrap{max-height:340px;overflow:auto;background:var(--surface);border:1px solid var(--border);border-radius:8px}
.mini{width:100%;font-size:12px}
.mini th,.mini td{font-size:12px;padding:5px 8px}
.rec{margin:0 0 10px;font-size:14px}
ul.plain{margin:0;padding-left:18px;font-size:12px;max-height:340px;overflow:auto}
.foot{color:var(--muted);font-size:13px;margin-top:40px}
.foot code{background:var(--surface-2);padding:1px 4px;border-radius:4px}
.empty{color:var(--muted);font-size:14px}
.stage{font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--accent);margin:44px 0 0}
.stage + h2{margin-top:4px}
.lede{color:var(--muted);margin:0 0 14px;max-width:820px;font-size:14px}
.filters{display:flex;gap:6px;flex-wrap:wrap;margin:0 0 10px}
.st-open{color:var(--pass);background:var(--pass-bg)}.st-theirs{color:var(--fail);background:var(--fail-bg)}
.st-contested{color:var(--warn);background:var(--warn-bg)}.st-ours{color:#fff;background:var(--accent)}
.st-unchecked{color:var(--info);background:var(--info-bg)}
.obar{display:flex;align-items:center;gap:8px;min-width:110px}
.obar .track{flex:1;height:6px}
.doms{font-size:12px;color:var(--muted)}
.two{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}
.pill{display:inline-block;font-size:12px;border:1px solid var(--border);border-radius:99px;padding:2px 8px;margin:2px 3px 2px 0;background:var(--surface)}
.pill.tracked{border-color:var(--accent);color:var(--accent);font-weight:600}
td.k{font-weight:600}
</style>
</head>
<body>
<div class="wrap">
  <h1>SXO Competitor Audit</h1>
  <p class="sub" id="meta"></p>

  <p class="stage">Stage 1 · SEO</p>
  <h2>Keyword ownership</h2>
  <p class="lede">Who ranks in the top 10 today (Brave Search), how much people search it (Google Autocomplete, relative),
  and how closely it matches what only we do. <b>Opportunity</b> = √demand × fit × how beatable tracked rivals are.
  Click a keyword for the searches around it.</p>
  <div class="filters" id="kwFilters"></div>
  <div class="tablewrap"><table id="kwTable"></table></div>

  <div class="two" style="margin-top:22px">
    <div>
      <h2 style="margin-top:0">Who actually wins these searches</h2>
      <p class="lede">Companies most often in the top 10 across all keywords (reference sites removed). Outlined = already tracked.
      Strong candidates for the competitor list.</p>
      <div id="winners"></div>
    </div>
    <div>
      <h2 style="margin-top:0">What each site emphasizes</h2>
      <p class="lede">Most distinctive phrases per site (class TF-IDF, weighted by title, URL and heading placement).</p>
      <div class="two" id="distinctive"></div>
    </div>
  </div>

  <p class="stage">Foundation</p>
  <h2>Site audit scores</h2>
  <div class="cards" id="cards"></div>

  <h2>Fix first: <span id="oursName"></span></h2>
  <div class="list" id="fixes"></div>

  <h2>Where competitors are ahead</h2>
  <div id="gaps"></div>

  <div class="tabs" role="tablist" id="tabs"></div>
  <div class="tablewrap"><table id="checks"></table></div>

  <div class="foot" id="foot"></div>
</div>
<script id="data" type="application/json">__DATA__</script>
<script>
const D = JSON.parse(document.getElementById('data').textContent);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const chip = st => `<span class="chip ${st}">${st}</span>`;
const sites = D.sites;
const ours = sites.find(s => s.site.is_ours) || sites[0];

document.getElementById('meta').textContent =
  `${sites.map(s => s.site.name).join(' vs ')} · generated ${D.generated.replace('T',' ')} · ` +
  sites.map(s => `${s.site.pages_crawled} pages from ${s.site.name}`).join(', ');
document.getElementById('oursName').textContent = ours.site.name;

document.getElementById('cards').innerHTML = sites.map(s => `
  <div class="card ${s.site.is_ours ? 'ours' : ''}">
    <h3>${esc(s.site.name)}${s.site.is_ours ? ' <span class="sec">us</span>' : ''}</h3>
    <div class="url">${esc(s.site.origin || s.site.url)}</div>
    <div class="big">${s.scores.overall ?? '–'}<small> / 100 overall</small></div>
    <div class="bars">${['UX','SEO','AEO'].map(k => `
      <div class="bar"><span>${k}</span><div class="track"><div class="fill" style="width:${s.scores[k] ?? 0}%"></div></div>
      <span class="num">${s.scores[k] ?? '–'}</span></div>`).join('')}
    </div>
    ${s.site.errors.length ? `<div class="s" style="color:var(--fail)">${esc(s.site.errors.join('; '))}</div>` : ''}
  </div>`).join('');

document.getElementById('fixes').innerHTML = D.fix_first.length ? D.fix_first.map((f, i) => `
  <div class="item">
    <div class="t">${i + 1}. ${esc(f.name)} ${chip(f.status)} <span class="sec">${f.section}</span></div>
    <div class="s">${esc(f.summary)}</div>
    <div class="r">→ ${esc(f.recommendation)}</div>
  </div>`).join('') : '<p class="empty">Nothing below the bar.</p>';

document.getElementById('gaps').innerHTML = D.gaps.length ? `<div class="tablewrap"><table>
  <tr><th>Check</th><th>Competitor</th><th>Them</th><th>Us</th></tr>
  ${D.gaps.map(g => `<tr><td><b>${esc(g.name)}</b> <span class="sec">${g.section}</span></td><td>${esc(g.competitor)}</td>
    <td>${esc(g.theirs)}</td><td>${esc(g.ours)}</td></tr>`).join('')}
  </table></div>` : '<p class="empty">No check where a competitor leads by 20+ points.</p>';

function detailBlock(d) {
  if (!d || !d.length) return '<p class="empty">No details.</p>';
  if (typeof d[0] === 'object') {
    const cols = Object.keys(d[0]);
    return `<div class="miniwrap"><table class="mini"><tr>${cols.map(c => `<th>${esc(c)}</th>`).join('')}</tr>
      ${d.map(r => `<tr>${cols.map(c => `<td>${esc(r[c])}</td>`).join('')}</tr>`).join('')}</table></div>`;
  }
  return `<ul class="plain">${d.map(x => `<li>${esc(x)}</li>`).join('')}</ul>`;
}

const ids = ours.checks.map(c => c.id);
const bySite = sites.map(s => Object.fromEntries(s.checks.map(c => [c.id, c])));
let current = 'UX';
function renderTable() {
  const rows = ids.filter(id => bySite[0][id].section === current);
  const head = `<tr><th>Check</th>${sites.map(s => `<th>${esc(s.site.name)}</th>`).join('')}</tr>`;
  document.getElementById('checks').innerHTML = head + rows.map(id => {
    const base = bySite[0][id];
    const cells = bySite.map(m => m[id] ? `<td class="cell">${chip(m[id].status)}
      ${m[id].score != null ? `<b> ${Math.round(m[id].score * 100)}</b>` : ''}<div class="s">${esc(m[id].summary)}</div></td>` : '<td>–</td>').join('');
    const detail = `<tr class="detail" hidden data-for="${id}"><td colspan="${sites.length + 1}">
      ${base.recommendation ? `<p class="rec"><b>How to improve:</b> ${esc(base.recommendation)}</p>` : ''}
      <div class="dgrid">${bySite.map((m, i) => `<div><h4>${esc(sites[i].site.name)}</h4>${detailBlock(m[id] && m[id].details)}</div>`).join('')}</div>
      </td></tr>`;
    return `<tr class="check" data-id="${id}" tabindex="0" aria-expanded="false"><td>${esc(base.name)}</td>${cells}</tr>` + detail;
  }).join('');
}
document.getElementById('checks').addEventListener('click', e => toggle(e.target.closest('tr.check')));
document.getElementById('checks').addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(e.target.closest('tr.check')); } });
function toggle(tr) {
  if (!tr) return;
  const d = document.querySelector(`tr.detail[data-for="${tr.dataset.id}"]`);
  d.hidden = !d.hidden; tr.setAttribute('aria-expanded', String(!d.hidden));
}
document.getElementById('tabs').innerHTML = ['UX','SEO','AEO'].map(k => {
  const n = ours.checks.filter(c => c.section === k).length;
  return `<button class="tab" role="tab" data-k="${k}" aria-selected="${k === current}">${k} · ${n} checks</button>`;
}).join('');
document.getElementById('tabs').addEventListener('click', e => {
  const b = e.target.closest('.tab'); if (!b) return;
  current = b.dataset.k;
  document.querySelectorAll('.tab').forEach(t => t.setAttribute('aria-selected', String(t === b)));
  renderTable();
});
renderTable();

const KW = D.keywords || {keywords: [], distinctive: {}, search_winners: []};
const ST = {'open gap': ['Open gap', 'st-open'], 'theirs': ['Theirs', 'st-theirs'], 'contested': ['Contested', 'st-contested'],
            'ours': ['Ours', 'st-ours'], 'not checked': ['Not checked', 'st-unchecked']};
let kwFilter = 'all';
const rankTxt = r => r == null ? '—' : `#${r}`;
function renderKw() {
  const rows = KW.keywords.filter(k => kwFilter === 'all' || k.status === kwFilter);
  const head = `<tr><th>Keyword</th><th>Status</th><th>Opportunity</th><th>Demand</th><th>Fit</th><th>${esc(ours.site.name)}</th>
    <th>Best tracked rival</th><th>Ranking now</th></tr>`;
  document.getElementById('kwTable').innerHTML = head + rows.map((k, i) => {
    const [label, cls] = ST[k.status] || [k.status, 'st-unchecked'];
    const rival = k.best_rival ? `${esc(k.best_rival)} ${rankTxt(k.rival_ranks[k.best_rival])}` : '—';
    const targeting = Object.entries(k.targeting).map(([n, v]) => `${esc(n)}: ${Math.round(v * 100)}%`).join(' · ');
    const list = (title, xs) => xs && xs.length ? `<div><h4>${title}</h4>${xs.map(x => `<span class="pill">${esc(x)}</span>`).join('')}</div>` : '';
    const detail = `<tr class="detail" hidden data-for="kw${i}"><td colspan="8"><div class="dgrid">
      ${list('Autocomplete variants', k.autocomplete)}${list('Related searches', k.related)}${list('Questions searchers ask', k.faq)}
      ${list('Top 10 right now', k.top_domains)}
      <div><h4>On-page targeting</h4><p class="rec">${targeting}</p><p class="rec">Source: ${esc(k.source)}</p></div>
      </div></td></tr>`;
    return `<tr class="check" data-id="kw${i}" tabindex="0" aria-expanded="false"><td class="k">${esc(k.keyword)}</td>
      <td><span class="chip ${cls}">${label}</span></td>
      <td><div class="obar"><div class="track"><div class="fill" style="width:${k.opportunity}%"></div></div><b>${k.opportunity}</b></div></td>
      <td>${Math.round(k.demand * 100)}</td><td>${Math.round(k.fit * 100)}</td><td>${rankTxt(k.our_rank)}</td><td>${rival}</td>
      <td class="doms">${k.top_domains.slice(0, 3).map(esc).join(', ') || '—'}</td></tr>` + detail;
  }).join('');
}
const counts = KW.keywords.reduce((m, k) => (m[k.status] = (m[k.status] || 0) + 1, m), {});
document.getElementById('kwFilters').innerHTML = [['all', `All · ${KW.keywords.length}`]]
  .concat(Object.keys(ST).filter(s => counts[s]).map(s => [s, `${ST[s][0]} · ${counts[s]}`]))
  .map(([k, t]) => `<button class="tab" data-f="${k}" aria-selected="${k === kwFilter}">${t}</button>`).join('');
document.getElementById('kwFilters').addEventListener('click', e => {
  const b = e.target.closest('.tab'); if (!b) return;
  kwFilter = b.dataset.f;
  document.querySelectorAll('#kwFilters .tab').forEach(t => t.setAttribute('aria-selected', String(t === b)));
  renderKw();
});
const kwTable = document.getElementById('kwTable');
kwTable.addEventListener('click', e => toggle(e.target.closest('tr.check')));
kwTable.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(e.target.closest('tr.check')); } });
renderKw();
document.getElementById('winners').innerHTML = KW.search_winners.length ? KW.search_winners.map(w =>
  `<span class="pill ${w.tracked ? 'tracked' : ''}">${esc(w.domain)} · ${w.top10_count}</span>`).join('') : '<p class="empty">No ranking data.</p>';
document.getElementById('distinctive').innerHTML = Object.entries(KW.distinctive).map(([n, xs]) =>
  `<div><h4>${esc(n)}</h4>${xs.slice(0, 20).map(x => `<span class="pill">${esc(x.phrase)}</span>`).join('')}</div>`).join('');

document.getElementById('foot').innerHTML = `
  <p><b>Method.</b> Every check uses free data: the public HTML of up to ${D.config.max_pages} pages per site (homepage, navigation,
  then sitemap pages matching our keywords), robots.txt, sitemap.xml, llms.txt, a 404 probe, and Google PageSpeed Insights.
  Scores are 0–100; pass ≥ 80, warn ≥ 50. Click any row for evidence.</p>
  <p><b>Keywords:</b> ${D.config.keywords.map(esc).join(' · ')}</p>
  <p><b>Buyer questions:</b> ${D.config.questions.map(esc).join(' · ')}</p>`;
</script>
</body>
</html>
"""


def write_dashboard(report: dict, path: Path) -> Path:
    data = json.dumps(report).replace("</", "<\\/")
    path.write_text(TEMPLATE.replace("__DATA__", data))
    return path
