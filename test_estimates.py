"""Verify the estimation logic by simulating a prior-day snapshot."""
import sqlite3, random
from datetime import date, timedelta
import storage
from collect_catalog import collect

DB = "nykaa_intel.db"

# 1) collect today's shampoo snapshot (10 pages for speed)
collect("https://www.nykaa.com/hair-care/hair/shampoo/c/316", "haircare:shampoo", max_pages=10)

# 2) simulate YESTERDAY: copy today's rows with slightly lower rating_count + shuffled rank
con = sqlite3.connect(DB)
today = date.today().isoformat()
yday = (date.today() - timedelta(days=1)).isoformat()
con.execute("DELETE FROM snapshots WHERE snapshot_date=?", (yday,))
rows = con.execute("SELECT * FROM snapshots WHERE snapshot_date=?", (today,)).fetchall()
sim = []
for r in rows:
    r = list(r)
    r[0] = yday                       # snapshot_date
    # yesterday had FEWER reviews -> today's growth implies sales
    rc = r[13] or 0
    r[13] = max(0, rc - random.randint(0, 60))   # rating_count yesterday
    r[3] = (r[3] or 0) + random.randint(-3, 3)    # rank wobble
    sim.append(tuple(r))
con.executemany("INSERT OR REPLACE INTO snapshots VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", sim)
con.commit(); con.close()

# 3) compute estimates today vs yesterday
conn, flavor = storage.connect()
n = storage.compute_estimates(conn, flavor, today, yday)
print(f"\nestimates computed for {n} products\n")

cur = conn.cursor()
print("=== TOP 8 by ESTIMATED daily revenue (proxy) ===")
for row in cur.execute("""SELECT brand, name, price, delta_reviews, est_units_per_day, est_revenue_per_day, rank, rank_change
                          FROM estimates ORDER BY est_revenue_per_day DESC LIMIT 8"""):
    brand, name, price, dr, units, rev, rank, rc = row
    arrow = f"up{rc}" if (rc or 0) > 0 else (f"down{-rc}" if (rc or 0) < 0 else "flat")
    print(f"  {brand[:16]:<16} Rs{price:<5} | +{dr} rev/day -> ~{units:.0f} units/day -> ~Rs{rev:,.0f}/day | rank#{rank} ({arrow})")

print("\n=== CATEGORY TOTALS (estimated) ===")
tot = cur.execute("SELECT SUM(est_units_per_day), SUM(est_revenue_per_day) FROM estimates").fetchone()
print(f"  est units/day: ~{tot[0]:,.0f}   est revenue/day: ~Rs{tot[1]:,.0f}   (monthly ~Rs{tot[1]*30:,.0f})")
conn.close()
