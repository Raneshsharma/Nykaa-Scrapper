"""
Backfill / reconciliation pass — runs AFTER the sharded collect to guarantee
consistent daily coverage. Finds categories that are missing from today's
snapshot or came back far thinner than their recent norm (a sign of a transient
Akamai block or a failed/slow shard) and re-scrapes just those, over a few rounds.
"""
import os, re, json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import storage
from collect_catalog import collect

IST = ZoneInfo("Asia/Kolkata")


def slug_label(url):
    m = re.search(r'https://www\.nykaa\.com/(.+?)/c/\d+', url)
    return m.group(1).replace("/", ":") if m else url


def have_counts(conn, flavor, date):
    ph = "%s" if flavor == "pg" else "?"
    cur = conn.cursor()
    cur.execute(f"SELECT category, COUNT(*) FROM snapshots WHERE snapshot_date={ph} GROUP BY category", (date,))
    return {c: n for c, n in cur.fetchall()}


def baselines(conn, flavor, today):
    """Each category's typical daily yield = max count over the prior 7 days."""
    ph = "%s" if flavor == "pg" else "?"
    since = (datetime.now(IST).date() - timedelta(days=7)).isoformat()
    cur = conn.cursor()
    cur.execute(f"""SELECT category, MAX(cnt) FROM (
        SELECT category, snapshot_date, COUNT(*) cnt FROM snapshots
        WHERE snapshot_date < {ph} AND snapshot_date >= {ph}
        GROUP BY category, snapshot_date) t GROUP BY category""", (today, since))
    return {c: n for c, n in cur.fetchall()}


def main():
    leaves = [c for c in json.load(open("categories.json", encoding="utf-8"))
              if c.get("leaf") and c.get("total")]
    by_label = {slug_label(c["url"]): c for c in leaves}

    conn, flavor = storage.connect()
    storage.init_schema(conn, flavor)
    today = datetime.now(IST).date().isoformat()
    base = baselines(conn, flavor, today)
    rounds = int(os.environ.get("BACKFILL_ROUNDS", "3"))
    dry = os.environ.get("BACKFILL_DRY") == "1"

    for rnd in range(1, rounds + 1):
        have = have_counts(conn, flavor, today)
        todo = []
        for label, c in by_label.items():
            got = have.get(label, 0)
            # expected = recent norm, else a conservative fallback for never-seen cats
            expected = base.get(label) or min(int(c.get("total") or 0), 60)
            if got < max(1, 0.5 * expected):
                todo.append((label, c, got, expected))
        print(f"[backfill round {rnd}] {len(have)} categories present today; "
              f"{len(todo)} missing/thin to re-scrape")
        if dry:
            for label, c, got, expected in todo[:20]:
                print(f"  WOULD re-scrape {label}: have {got}, norm ~{int(expected)}")
            break
        if not todo:
            break
        for label, c, got, expected in todo:
            try:
                n = collect(c["url"], label)
                print(f"  BACKFILL-OK {label}: {n} (was {got}, norm ~{int(expected)})")
            except Exception as e:
                print(f"  BACKFILL-FAIL {label}: {e}")

    have = have_counts(conn, flavor, today)
    print(f"[backfill done] today={today}: {len(have)} categories, "
          f"{sum(have.values())} product-rows")
    conn.close()


if __name__ == "__main__":
    main()
