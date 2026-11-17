"""One-time: set public READ access (anon key + RLS to aggregate views only) and
create overview views in Supabase. Raw products/snapshots/estimates stay private;
the public dashboard reads only the aggregate views."""
import json, os, urllib.request

REF = "rwpzxiekkaewlgurfouq"
CRED = r"C:/Users/ranes/Desktop/TrustMRR_API .env.txt"
TOKEN = [l.split(":", 1)[1].strip() for l in open(CRED, encoding="utf-8", errors="ignore")
         if l.strip().lower().startswith("supabase")][0]

def api(method, path, body=None):
    req = urllib.request.Request("https://api.supabase.com" + path, method=method,
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
        data=json.dumps(body).encode() if body else None)
    try:
        return json.loads(urllib.request.urlopen(req, timeout=60).read().decode() or "null"), 200
    except urllib.error.HTTPError as e:
        return e.read().decode(), e.code

# 1) publishable (public read) key
keys, _ = api("GET", f"/v1/projects/{REF}/api-keys")
pub = next((k["api_key"] for k in keys if (k.get("api_key") or "").startswith("sb_publishable_")), None)
if not pub:
    pub = next((k["api_key"] for k in keys if k.get("name") == "anon"), None)
print("read key:", "sb_publishable" if pub.startswith("sb_publishable") else "anon-jwt")

# 2) aggregate views (joined to products dim) + RLS lockdown to views only
SQL = """
create or replace view v_overview as
 select (select max(snapshot_date) from snapshots) latest_date,
   count(distinct s.product_id) products, count(distinct p.brand) brands,
   count(distinct s.category) categories, round(avg(s.price)) avg_price
 from snapshots s join products p on s.product_id=p.product_id
 where s.snapshot_date=(select max(snapshot_date) from snapshots);
create or replace view v_top_brands as
 select p.brand, count(distinct s.product_id) products, round(avg(s.price)) avg_price,
   round(avg(s.rating)::numeric,2) avg_rating, sum(s.rating_count) total_reviews
 from snapshots s join products p on s.product_id=p.product_id
 where s.snapshot_date=(select max(snapshot_date) from snapshots)
 group by p.brand order by products desc limit 25;
create or replace view v_category_summary as
 select category, count(distinct product_id) products, round(avg(price)) avg_price, round(avg(discount)) avg_discount
 from snapshots where snapshot_date=(select max(snapshot_date) from snapshots)
 group by category order by products desc limit 40;
create or replace view v_top_discounts as
 select p.brand, p.name, s.price, s.mrp, s.discount, s.rating, s.rating_count, s.category
 from snapshots s join products p on s.product_id=p.product_id
 where s.snapshot_date=(select max(snapshot_date) from snapshots) and s.discount>0
 order by s.discount desc, s.rating_count desc limit 30;

alter table snapshots enable row level security;
alter table products  enable row level security;
alter table estimates enable row level security;
revoke select on snapshots, products, estimates from anon;
alter view v_overview         set (security_invoker = false);
alter view v_top_brands       set (security_invoker = false);
alter view v_category_summary set (security_invoker = false);
alter view v_top_discounts    set (security_invoker = false);
grant select on v_overview, v_top_brands, v_category_summary, v_top_discounts to anon;
"""
res, code = api("POST", f"/v1/projects/{REF}/database/query", {"query": SQL})
print("views+RLS:", "OK" if code == 200 and not (isinstance(res, dict) and res.get("message")) else res)

# 3) persist read config (gitignored .env + dashboard_config.json)
env_txt = open(".env", encoding="utf-8").read() if os.path.exists(".env") else ""
if "SUPABASE_ANON_KEY=" not in env_txt:
    with open(".env", "a", encoding="utf-8") as f:
        f.write(f"\nSUPABASE_URL=https://{REF}.supabase.co\nSUPABASE_ANON_KEY={pub}\n")
json.dump({"url": f"https://{REF}.supabase.co", "anon_key": pub}, open("dashboard_config.json", "w"), indent=1)
print("saved read config. REST base:", f"https://{REF}.supabase.co/rest/v1/")
