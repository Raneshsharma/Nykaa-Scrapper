"""
Storage layer + sales/revenue estimation for the Nykaa intelligence pipeline.

Backend is chosen automatically:
  - If env DATABASE_URL is set (Supabase Postgres connection string) -> Postgres
  - else -> local SQLite file (NYKAA_DB env or nykaa_intel.db)

Estimation: exact sales are private, so we estimate from the DAILY change in
review count (ratingCount delta) -- the standard review-velocity method.
  est_units_per_day   = max(0, reviews_today - reviews_prev) * REVIEW_SALES_MULT
  est_revenue_per_day = est_units_per_day * price
REVIEW_SALES_MULT is a calibration factor (only a fraction of buyers review).
"""
import os
import sqlite3

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

DB_URL = os.environ.get("DATABASE_URL")  # Supabase: postgresql://...
REVIEW_SALES_MULT = float(os.environ.get("REVIEW_SALES_MULT", "20"))


def connect():
    """Returns (conn, flavor) where flavor is 'pg' or 'sqlite'."""
    if DB_URL:
        import psycopg2  # only needed on the server
        return psycopg2.connect(DB_URL), "pg"
    return sqlite3.connect(os.environ.get("NYKAA_DB", "nykaa_intel.db")), "sqlite"


def _ph(flavor):
    return "%s" if flavor == "pg" else "?"


def init_schema(conn, flavor):
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS snapshots (
        snapshot_date TEXT, captured_at TEXT, category TEXT, rank INTEGER,
        product_id TEXT, sku TEXT, name TEXT, brand TEXT, brand_id TEXT,
        price REAL, mrp REAL, discount REAL, rating REAL, rating_count INTEGER,
        in_stock INTEGER, is_lux INTEGER, type TEXT, image_url TEXT, slug TEXT,
        PRIMARY KEY (snapshot_date, category, product_id))""")
    cur.execute("""CREATE TABLE IF NOT EXISTS estimates (
        est_date TEXT, category TEXT, product_id TEXT, name TEXT, brand TEXT,
        price REAL, prev_rating_count INTEGER, rating_count INTEGER,
        delta_reviews INTEGER, est_units_per_day REAL, est_revenue_per_day REAL,
        rank INTEGER, prev_rank INTEGER, rank_change INTEGER,
        PRIMARY KEY (est_date, category, product_id))""")
    conn.commit()


def upsert_snapshots(conn, flavor, rows):
    cur = conn.cursor()
    if flavor == "pg":
        from psycopg2.extras import execute_values
        sql = ("INSERT INTO snapshots VALUES %s "
               "ON CONFLICT (snapshot_date, category, product_id) DO UPDATE SET "
               "captured_at=EXCLUDED.captured_at, rank=EXCLUDED.rank, price=EXCLUDED.price, "
               "mrp=EXCLUDED.mrp, discount=EXCLUDED.discount, rating=EXCLUDED.rating, "
               "rating_count=EXCLUDED.rating_count, in_stock=EXCLUDED.in_stock")
        execute_values(cur, sql, rows, page_size=500)  # fast bulk insert
    else:
        placeholders = ",".join(["?"] * 19)
        cur.executemany(f"INSERT OR REPLACE INTO snapshots VALUES ({placeholders})", rows)
    conn.commit()


def compute_estimates(conn, flavor, today, prev_date, mult=REVIEW_SALES_MULT):
    """Diff today's snapshot against prev_date to estimate daily sales/revenue."""
    cur = conn.cursor()
    p = _ph(flavor)
    # previous day's review counts and ranks
    cur.execute(f"SELECT category, product_id, rating_count, rank FROM snapshots WHERE snapshot_date={p}", (prev_date,))
    prev = {(c, pid): (rc or 0, rk) for c, pid, rc, rk in cur.fetchall()}

    cur.execute(f"""SELECT category, product_id, name, brand, price, rating_count, rank
                    FROM snapshots WHERE snapshot_date={p}""", (today,))
    out = []
    for cat, pid, name, brand, price, rc, rank in cur.fetchall():
        rc = rc or 0
        prc, prank = prev.get((cat, pid), (None, None))
        if prc is None:
            continue  # no prior day -> can't estimate yet
        delta = max(0, rc - prc)
        est_units = delta * mult
        est_rev = est_units * (price or 0)
        rank_change = (prank - rank) if (prank is not None and rank is not None) else None
        out.append((today, cat, pid, name, brand, price, prc, rc, delta,
                    est_units, est_rev, rank, prank, rank_change))

    if out:
        ph = ",".join([p] * 14)
        if flavor == "pg":
            sql = (f"INSERT INTO estimates VALUES ({ph}) ON CONFLICT (est_date, category, product_id) "
                   "DO UPDATE SET delta_reviews=EXCLUDED.delta_reviews, "
                   "est_units_per_day=EXCLUDED.est_units_per_day, "
                   "est_revenue_per_day=EXCLUDED.est_revenue_per_day, rank_change=EXCLUDED.rank_change")
        else:
            sql = f"INSERT OR REPLACE INTO estimates VALUES ({ph})"
        cur.executemany(sql, out)
        conn.commit()
    return len(out)
