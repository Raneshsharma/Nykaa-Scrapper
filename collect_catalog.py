"""
Category catalog collector for Nykaa — builds the product-intelligence dataset.
Reuses the existing curl_cffi session (Akamai bypass) from NykaaScraper.
Pages through a CATEGORY listing URL (uses ?page_no=N), extracts price/rank/
rating per product, stores a DATED snapshot, then estimates daily sales/revenue.
Storage backend (SQLite or Supabase Postgres) is chosen in storage.py via env.
"""
import re, json, time, random, argparse
from datetime import datetime, date
from nykaa_scraper import NykaaScraper
from nykaa_scraper.utils import logger
import storage


def _extract_state(html):
    m = re.search(r'__PRELOADED_STATE__\s*=\s*(\{.*)', html, re.DOTALL)
    if not m:
        return None
    raw = m.group(1)
    depth = 0
    for i, ch in enumerate(raw):
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(raw[:i + 1])
                except Exception:
                    return None
    return None


def fetch_page(session, base_url, page_no):
    sep = "&" if "?" in base_url else "?"
    url = f"{base_url}{sep}page_no={page_no}"
    r = session.get(url, headers={"Accept": "text/html,*/*", "Referer": "https://www.nykaa.com"}, timeout=20)
    if r.status_code != 200:
        return [], 0, ""
    st = _extract_state(r.text)
    if not st:
        return [], 0, ""
    ld = st.get("categoryListing", {}).get("listingData", {})
    return ld.get("products", []), ld.get("totalFound", 0), ld.get("title", "")


def collect(base_url, category_label, max_pages=None):
    s = NykaaScraper()
    s._ensure_session()
    conn, flavor = storage.connect()
    storage.init_schema(conn, flavor)
    logger.info(f"storage backend: {flavor}")

    today = date.today().isoformat()
    now = datetime.now().isoformat(timespec="seconds")

    rows, seen, rank, page, total = [], set(), 0, 1, None
    while True:
        prods, total_found, title = fetch_page(s.session, base_url, page)
        if total is None:
            total = total_found
            logger.info(f"[{category_label}] totalFound={total} (title={title!r})")
        if not prods:
            break
        for p in prods:
            pid = str(p.get("id") or p.get("productId") or "")
            if not pid or pid in seen:   # dedupe repeated sponsored tiles, keep best (first) rank
                continue
            seen.add(pid)
            rank += 1
            rows.append((
                today, now, category_label, rank, pid, p.get("sku") or "",
                p.get("name") or p.get("title") or "", p.get("brandName") or "",
                str(p.get("brandIds") or ""), p.get("price"), p.get("mrp"), p.get("discount"),
                p.get("rating"), p.get("ratingCount"),
                1 if p.get("inStock") else 0, 1 if p.get("isLux") else 0,
                p.get("type") or "", p.get("imageUrl") or "", p.get("slug") or "",
            ))
        logger.info(f"[{category_label}] page {page}: collected {rank}/{total} distinct")
        page += 1
        if max_pages and page > max_pages:
            break
        if total and rank >= total:
            break
        time.sleep(random.uniform(0.9, 1.6))

    storage.upsert_snapshots(conn, flavor, rows)
    logger.info(f"[{category_label}] saved {len(rows)} products for {today}")

    # estimate daily sales/revenue vs the most recent earlier snapshot of this category
    cur = conn.cursor()
    ph = "%s" if flavor == "pg" else "?"
    cur.execute(f"""SELECT DISTINCT snapshot_date FROM snapshots
                    WHERE category={ph} AND snapshot_date<{ph}
                    ORDER BY snapshot_date DESC LIMIT 1""", (category_label, today))
    prev = cur.fetchone()
    if prev:
        n = storage.compute_estimates(conn, flavor, today, prev[0])
        logger.info(f"[{category_label}] estimates computed for {n} products (vs {prev[0]})")
    else:
        logger.info(f"[{category_label}] no earlier snapshot yet -> estimates start on the next daily run")
    conn.close()
    return len(rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True, help="Nykaa CATEGORY listing URL (e.g. .../c/316)")
    ap.add_argument("--label", required=True, help="category label, e.g. haircare:shampoo")
    ap.add_argument("--max-pages", type=int, default=None)
    args = ap.parse_args()
    collect(args.url, args.label, args.max_pages)
