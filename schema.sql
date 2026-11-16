-- Nykaa intelligence schema for Supabase (Postgres).
-- Paste this into Supabase -> SQL Editor -> Run, to create the tables.

create table if not exists snapshots (
    snapshot_date text,
    captured_at   text,
    category      text,
    rank          integer,
    product_id    text,
    sku           text,
    name          text,
    brand         text,
    brand_id      text,
    price         real,
    mrp           real,
    discount      real,
    rating        real,
    rating_count  integer,
    in_stock      integer,
    is_lux        integer,
    type          text,
    image_url     text,
    slug          text,
    primary key (snapshot_date, category, product_id)
);

create table if not exists estimates (
    est_date            text,
    category            text,
    product_id          text,
    name                text,
    brand               text,
    price               real,
    prev_rating_count   integer,
    rating_count        integer,
    delta_reviews       integer,
    est_units_per_day   real,
    est_revenue_per_day real,
    rank                integer,
    prev_rank           integer,
    rank_change         integer,
    primary key (est_date, category, product_id)
);

-- helpful indexes for the API / dashboard queries
create index if not exists idx_snap_brand    on snapshots (brand);
create index if not exists idx_snap_cat_date on snapshots (category, snapshot_date);
create index if not exists idx_est_cat_date  on estimates (category, est_date);
create index if not exists idx_est_revenue   on estimates (est_revenue_per_day desc);
