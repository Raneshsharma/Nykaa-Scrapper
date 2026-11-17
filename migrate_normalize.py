"""One-off: migrate live Supabase to normalized schema, preserving history."""
import json, urllib.request
REF = "rwpzxiekkaewlgurfouq"
CRED = r"C:/Users/ranes/Desktop/TrustMRR_API .env.txt"
TOKEN = [l.split(":", 1)[1].strip() for l in open(CRED, encoding="utf-8", errors="ignore")
         if l.strip().lower().startswith("supabase")][0]

def q(sql):
    req = urllib.request.Request(f"https://api.supabase.com/v1/projects/{REF}/database/query",
        method="POST", headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
        data=json.dumps({"query": sql}).encode())
    try:
        return urllib.request.urlopen(req, timeout=120).read().decode()[:200], 200
    except urllib.error.HTTPError as e:
        return e.read().decode()[:300], e.code

SQL = """
create table if not exists products (
  product_id text primary key, sku text, name text, brand text, brand_id text,
  type text, is_lux int, image_url text, slug text, first_seen text, last_seen text);
insert into products (product_id, sku, name, brand, brand_id, type, is_lux, image_url, slug, first_seen, last_seen)
select product_id, max(sku), max(name), max(brand), max(brand_id), max(type), max(is_lux),
       max(image_url), max(slug), min(snapshot_date), max(snapshot_date)
from snapshots group by product_id on conflict (product_id) do nothing;

create table snapshots_lean (
  snapshot_date text, category text, product_id text, rank int,
  price real, mrp real, discount real, rating real, rating_count int, in_stock int,
  primary key (snapshot_date, category, product_id));
insert into snapshots_lean
select snapshot_date, category, product_id, rank, price, mrp, discount, rating, rating_count, in_stock from snapshots;

drop table snapshots cascade;
alter table snapshots_lean rename to snapshots;

drop table if exists estimates;
create table estimates (
  est_date text, category text, product_id text,
  price real, prev_rating_count int, rating_count int, delta_reviews int,
  est_units_per_day real, est_revenue_per_day real,
  rank int, prev_rank int, rank_change int,
  primary key (est_date, category, product_id));

create index if not exists idx_snap_date on snapshots(snapshot_date);
create index if not exists idx_snap_cat_date on snapshots(category, snapshot_date);
create index if not exists idx_snap_date_pid on snapshots(snapshot_date, product_id);
create index if not exists idx_prod_brand on products(brand);

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
alter table products enable row level security;
revoke select on snapshots from anon;
revoke select on products from anon;
revoke select on estimates from anon;
alter view v_overview set (security_invoker=false);
alter view v_top_brands set (security_invoker=false);
alter view v_category_summary set (security_invoker=false);
alter view v_top_discounts set (security_invoker=false);
grant select on v_overview, v_top_brands, v_category_summary, v_top_discounts to anon;
"""
print(q(SQL))
