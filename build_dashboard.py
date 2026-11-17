"""Generates dashboard.html with the Supabase URL + public read key embedded."""
import json
cfg = json.load(open("dashboard_config.json"))
URL, KEY = cfg["url"], cfg["anon_key"]

HTML = """<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Nykaa Beauty Intelligence</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background:#0e0f13; color:#e7e8ea; font:14px/1.5 system-ui,Segoe UI,Roboto,sans-serif; padding:22px; }
  h1 { font-size:20px; font-weight:700; } h1 span{ color:#fc2779; }
  .sub { color:#8b8d93; font-size:12px; margin-top:2px; }
  .bar-top { display:flex; justify-content:space-between; align-items:flex-end; flex-wrap:wrap; gap:10px; margin-bottom:18px; }
  button { background:#fc2779; color:#fff; border:0; border-radius:8px; padding:8px 14px; font-weight:600; cursor:pointer; }
  .kpis { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; margin-bottom:20px; }
  .kpi { background:#17181e; border:1px solid #23252d; border-radius:12px; padding:16px; }
  .kpi .n { font-size:26px; font-weight:700; color:#fff; } .kpi .l { color:#8b8d93; font-size:12px; text-transform:uppercase; letter-spacing:.04em; }
  .grid { display:grid; grid-template-columns:1fr 1fr; gap:16px; } @media(max-width:860px){ .grid{grid-template-columns:1fr;} }
  .card { background:#17181e; border:1px solid #23252d; border-radius:12px; padding:16px; margin-bottom:16px; }
  .card h2 { font-size:14px; margin-bottom:12px; color:#c7c9cf; }
  table { width:100%; border-collapse:collapse; font-size:13px; } th,td{ text-align:left; padding:7px 8px; border-bottom:1px solid #20222a; }
  th { color:#8b8d93; font-weight:600; font-size:11px; text-transform:uppercase; } td.r,th.r{ text-align:right; }
  .brow { display:flex; align-items:center; gap:8px; margin-bottom:7px; }
  .brow .lbl { width:150px; font-size:12px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .brow .track { flex:1; background:#20222a; border-radius:5px; height:16px; overflow:hidden; }
  .brow .fill { height:100%; background:linear-gradient(90deg,#fc2779,#ff7eb0); }
  .brow .v { width:38px; text-align:right; font-size:12px; color:#c7c9cf; }
  .pill { background:#2a0f1c; color:#ff7eb0; border-radius:6px; padding:1px 7px; font-size:11px; font-weight:600; }
  .muted{ color:#8b8d93; } .note{ background:#17181e;border:1px dashed #33353f;border-radius:10px;padding:12px;color:#9a9ca3;font-size:12px;margin-top:4px;}
</style></head>
<body>
<div class="bar-top">
  <div><h1>Nykaa <span>Beauty Intelligence</span></h1><div class="sub" id="meta">loading…</div></div>
  <button onclick="load()">Refresh</button>
</div>
<div class="kpis" id="kpis"></div>
<div class="grid">
  <div class="card"><h2>Top brands by product count</h2><div id="brands"></div></div>
  <div class="card"><h2>Categories tracked</h2><div id="cats"></div></div>
</div>
<div class="card"><h2>Biggest discounts right now</h2><div id="disc"></div></div>
<div class="note" id="estnote"></div>
<script>
const U="__URL__/rest/v1", K="__KEY__";
const H={ headers:{ apikey:K, Authorization:"Bearer "+K } };
const q = (v,p="") => fetch(`${U}/${v}${p}`,H).then(r=>r.json());
const money = n => "\u20b9"+Number(n||0).toLocaleString('en-IN');

async function load(){
  const [ov] = await q("v_overview");
  document.getElementById("meta").textContent = "Live from Supabase \u00b7 latest snapshot "+(ov?.latest_date||"-");
  document.getElementById("kpis").innerHTML = [
    ["Products", Number(ov.products).toLocaleString('en-IN')],
    ["Brands", ov.brands], ["Categories", ov.categories], ["Avg price", money(ov.avg_price)],
  ].map(([l,n])=>`<div class="kpi"><div class="n">${n}</div><div class="l">${l}</div></div>`).join("");

  const brands = await q("v_top_brands","?limit=12");
  const max = Math.max(...brands.map(b=>b.products),1);
  document.getElementById("brands").innerHTML = brands.map(b=>`
    <div class="brow"><div class="lbl">${b.brand}</div>
    <div class="track"><div class="fill" style="width:${b.products/max*100}%"></div></div>
    <div class="v">${b.products}</div></div>`).join("");

  const cats = await q("v_category_summary","?limit=12");
  document.getElementById("cats").innerHTML = `<table><tr><th>Category</th><th class="r">Products</th><th class="r">Avg \u20b9</th><th class="r">Avg disc</th></tr>`+
    cats.map(c=>`<tr><td>${c.category}</td><td class="r">${c.products}</td><td class="r">${money(c.avg_price)}</td><td class="r">${c.avg_discount||0}%</td></tr>`).join("")+`</table>`;

  const d = await q("v_top_discounts","?limit=15");
  document.getElementById("disc").innerHTML = `<table><tr><th>Brand</th><th>Product</th><th class="r">Price</th><th class="r">MRP</th><th class="r">Off</th><th class="r">Reviews</th></tr>`+
    d.map(x=>`<tr><td>${x.brand}</td><td>${(x.name||'').slice(0,46)}</td><td class="r">${money(x.price)}</td><td class="r muted">${money(x.mrp)}</td><td class="r"><span class="pill">-${x.discount}%</span></td><td class="r">${Number(x.rating_count||0).toLocaleString('en-IN')}</td></tr>`).join("")+`</table>`;

  document.getElementById("estnote").innerHTML = "\u2139\ufe0f Estimated daily <b>sales & revenue</b> per product/brand appear here automatically once there are 2+ daily snapshots (the collector diffs review-count growth). Data refreshes as the daily scrape runs.";
}
load();
</script>
</body></html>"""

open("dashboard.html", "w", encoding="utf-8").write(HTML.replace("__URL__", URL).replace("__KEY__", KEY))
print("wrote dashboard.html")
