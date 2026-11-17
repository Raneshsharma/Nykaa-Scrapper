-- Nykaa intelligence — NORMALIZED schema for Supabase (Postgres).
-- products = one row per product (slowly-changing dimension)
-- snapshots = lean daily fact (price/rank/reviews/stock) -> keeps history cheap
-- estimates = lean daily sales/revenue estimates
-- storage.init_schema() creates these automatically; this file is the reference.

create table if not exists products (
    product_id text primary key,
    sku text, name text, brand text, brand_id text,
    type text, is_lux integer, image_url text, slug text,
    first_seen text, last_seen text
);

create table if not exists snapshots (
    snapshot_date text, category text, product_id text, rank integer,
    price real, mrp real, discount real, rating real, rating_count integer, in_stock integer,
    primary key (snapshot_date, category, product_id)
);

create table if not exists estimates (
    est_date text, category text, product_id text,
    price real, prev_rating_count integer, rating_count integer, delta_reviews integer,
    est_units_per_day real, est_revenue_per_day real,
    rank integer, prev_rank integer, rank_change integer,
    primary key (est_date, category, product_id)
);

create index if not exists idx_snap_date      on snapshots(snapshot_date);
create index if not exists idx_snap_cat_date  on snapshots(category, snapshot_date);
create index if not exists idx_snap_date_pid  on snapshots(snapshot_date, product_id);
create index if not exists idx_prod_brand     on products(brand);

-- Aggregate views exposed to the public (anon) dashboard; raw tables stay private.
-- See setup_readaccess.py for the view definitions + RLS lockdown.
