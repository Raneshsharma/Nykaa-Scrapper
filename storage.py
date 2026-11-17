"""
Storage layer + sales/revenue estimation for the Nykaa intelligence pipeline.

NORMALIZED schema (keeps daily history cheap):
  products  = one row per product (slowly-changing: name, brand, image, slug...)
  snapshots = lean daily fact (price, rank, rating, reviews, stock) per product/day
  estimates = lean daily sales/revenue estimates per product/day

Backend auto-selected: DATABASE_URL set -> Supabase Postgres, else local SQLite.
Estimation: est_units_per_day = max(0, reviews_today - reviews_prev) * REVIEW_SALES_MULT
            est_revenue_per_day = est_units_per_day * price   (review-velocity method)
"""
import os
import sqlite3

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

DB_URL = os.environ.get("DATABASE_URL")
REVIEW_SALES_MULT = float(os.environ.get("REVIEW_SALES_MULT", "20"))


def connect():
    if DB_URL:
        import psycopg2
        return psycopg2.connect(DB_URL), "pg"
    return sqlite3.connect(os.environ.get("NYKAA_DB", "nykaa_intel.db")), "sqlite"


def _ph(flavor):
    return "%s" if flavor == "pg" else "?"


def init_schema(conn, flavor):
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS products (
        product_id TEXT PRIMARY KEY, sku TEXT, name TEXT, brand TEXT, brand_id TEXT,
        type TEXT, is_lux INTEGER, image_url TEXT, slug TEXT,
        first_seen TEXT, last_seen TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS snapshots (
        snapshot_date TEXT, category TEXT, product_id TEXT, rank INTEGER,
        price REAL, mrp REAL, discount REAL, rating REAL, rating_count INTEGER, in_stock INTEGER,
        PRIMARY KEY (snapshot_date, category, product_id))""")
    cur.execute("""CREATE TABLE IF NOT EXISTS estimates (
        est_date TEXT, category TEXT, product_id TEXT,
        price REAL, prev_rating_count INTEGER, rating_count INTEGER, delta_reviews INTEGER,
        est_units_per_day REAL, est_revenue_per_day REAL,
        rank INTEGER, prev_rank INTEGER, rank_change INTEGER,
        PRIMARY KEY (est_date, category, product_id))""")
    conn.commit()


# wide row from the collector (unchanged), indices:
# 0 snapshot_date 1 captured_at 2 category 3 rank 4 product_id 5 sku 6 name 7 brand
# 8 brand_id 9 price 10 mrp 11 discount 12 rating 13 rating_count 14 in_stock
# 15 is_lux 16 type 17 image_url 18 slug
def upsert_snapshots(conn, flavor, rows):
    if not rows:
        return
    cur = conn.cursor()
    products, snaps = {}, []
    for r in rows:
        pid, d = r[4], r[0]
        # keep one dim row per product this run; first_seen/last_seen set to this date
        products[pid] = (pid, r[5], r[6], r[7], r[8], r[16], r[15], r[17], r[18], d, d)
        snaps.append((d, r[2], pid, r[3], r[9], r[10], r[11], r[12], r[13], r[14]))
    prod_rows = list(products.values())

    if flavor == "pg":
        from psycopg2.extras import execute_values
        execute_values(cur,
            "INSERT INTO products VALUES %s ON CONFLICT (product_id) DO UPDATE SET "
            "sku=EXCLUDED.sku, name=EXCLUDED.name, brand=EXCLUDED.brand, brand_id=EXCLUDED.brand_id, "
            "type=EXCLUDED.type, is_lux=EXCLUDED.is_lux, image_url=EXCLUDED.image_url, slug=EXCLUDED.slug, "
            "last_seen=EXCLUDED.last_seen",
            prod_rows, page_size=500)
        execute_values(cur,
            "INSERT INTO snapshots VALUES %s ON CONFLICT (snapshot_date, category, product_id) DO UPDATE SET "
            "rank=EXCLUDED.rank, price=EXCLUDED.price, mrp=EXCLUDED.mrp, discount=EXCLUDED.discount, "
            "rating=EXCLUDED.rating, rating_count=EXCLUDED.rating_count, in_stock=EXCLUDED.in_stock",
            snaps, page_size=500)
    else:
        cur.executemany(
            "INSERT INTO products VALUES (?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(product_id) DO UPDATE SET sku=excluded.sku, name=excluded.name, brand=excluded.brand, "
            "brand_id=excluded.brand_id, type=excluded.type, is_lux=excluded.is_lux, image_url=excluded.image_url, "
            "slug=excluded.slug, last_seen=excluded.last_seen", prod_rows)
        cur.executemany("INSERT OR REPLACE INTO snapshots VALUES (?,?,?,?,?,?,?,?,?,?)", snaps)
    conn.commit()


def compute_estimates(conn, flavor, today, prev_date, mult=REVIEW_SALES_MULT):
    """Diff today's snapshot vs prev_date to estimate daily sales/revenue."""
    cur = conn.cursor()
    p = _ph(flavor)
    cur.execute(f"SELECT category, product_id, rating_count, rank FROM snapshots WHERE snapshot_date={p}", (prev_date,))
    prev = {(c, pid): (rc or 0, rk) for c, pid, rc, rk in cur.fetchall()}

    cur.execute(f"SELECT category, product_id, price, rating_count, rank FROM snapshots WHERE snapshot_date={p}", (today,))
    out = []
    for cat, pid, price, rc, rank in cur.fetchall():
        rc = rc or 0
        prc, prank = prev.get((cat, pid), (None, None))
        if prc is None:
            continue
        delta = max(0, rc - prc)
        out.append((today, cat, pid, price, prc, rc, delta,
                    delta * mult, delta * mult * (price or 0),
                    rank, prank, (prank - rank) if (prank is not None and rank is not None) else None))
    if out:
        ph = ",".join([p] * 12)
        if flavor == "pg":
            sql = (f"INSERT INTO estimates VALUES ({ph}) ON CONFLICT (est_date, category, product_id) "
                   "DO UPDATE SET delta_reviews=EXCLUDED.delta_reviews, est_units_per_day=EXCLUDED.est_units_per_day, "
                   "est_revenue_per_day=EXCLUDED.est_revenue_per_day, rank_change=EXCLUDED.rank_change")
        else:
            sql = f"INSERT OR REPLACE INTO estimates VALUES ({ph})"
        cur.executemany(sql, out)
        conn.commit()
    return len(out)
