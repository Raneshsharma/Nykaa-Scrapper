"""
Discover Nykaa's BEAUTY category tree via bounded top-down crawl.
Dedupes by category id, captures product count (totalFound), flags leaf
categories (<= CAP products = fully scrapeable under the ~page-100 cap).
Skips fashion verticals and brand pages. Saves categories.json.
"""
import re, json, time
from nykaa_scraper import NykaaScraper

MAX_FETCHES = 500
CAP = 1800                 # Nykaa deep-pagination soft cap (~page 100 x ~18)
PROG = "discover_progress.txt"

EXCLUDE = re.compile(r"/brands/|lingerie|sleep-lounge|jewellery|apparel|footwear|"
                     r"/bags|watches|sunglasses|/men-fashion|/women/western|/kids-fashion", re.I)

SEEDS = [
    "https://www.nykaa.com/makeup/c/12",
    "https://www.nykaa.com/skin/c/8377",
    "https://www.nykaa.com/hair-care/c/24",
    "https://www.nykaa.com/bath-body/c/1380",
    "https://www.nykaa.com/fragrance/c/53",
    "https://www.nykaa.com/personal-care/c/4809",
    "https://www.nykaa.com/natural/c/9564",
    "https://www.nykaa.com/wellness/c/671",
    "https://www.nykaa.com/luxe/c/194",
    "https://www.nykaa.com/mom-and-baby/c/3098",
    "https://www.nykaa.com/men/c/5333",
]

s = NykaaScraper(); s._ensure_session()

def cid(url):
    m = re.search(r"/c/(\d+)", url)
    return m.group(1) if m else None

def page_info(url):
    try:
        r = s.session.get(url, headers={"Accept": "text/html,*/*", "Referer": "https://www.nykaa.com"}, timeout=20)
        if r.status_code != 200:
            return None, None, []
    except Exception:
        return None, None, []
    html = r.text
    m = re.search(r'__PRELOADED_STATE__\s*=\s*(\{.*)', html, re.DOTALL)
    total = title = None
    if m:
        raw = m.group(1); d = 0
        for i, ch in enumerate(raw):
            if ch == '{': d += 1
            elif ch == '}':
                d -= 1
                if d == 0:
                    try:
                        ld = json.loads(raw[:i+1]).get("categoryListing", {}).get("listingData", {})
                        total, title = ld.get("totalFound"), ld.get("title")
                    except Exception:
                        pass
                    break
    links = set(re.findall(r'(/[a-z0-9\-/]+/c/\d+)', html))
    return total, title, links

seen_ids, found, queue, fetches = set(), {}, list(SEEDS), 0
while queue and fetches < MAX_FETCHES:
    url = queue.pop(0)
    cid_ = cid(url)
    if not cid_ or cid_ in seen_ids or EXCLUDE.search(url):
        continue
    seen_ids.add(cid_)
    total, title, links = page_info(url); fetches += 1
    if total is not None:
        found[cid_] = {"id": cid_, "label": title or url.split("/c/")[0].split("/")[-1],
                       "url": "https://www.nykaa.com" + re.search(r'(/[a-z0-9\-/]+/c/\d+)', url).group(1),
                       "total": total, "leaf": total <= CAP}
    for link in links:
        lid = cid(link)
        if lid and lid not in seen_ids and not EXCLUDE.search(link):
            queue.append("https://www.nykaa.com" + link)
    if fetches % 25 == 0:
        open(PROG, "w").write(f"{fetches} fetched, {len(found)} cats, {len(queue)} queued\n")
    time.sleep(0.6)

cats = sorted(found.values(), key=lambda c: -(c["total"] or 0))
json.dump(cats, open("categories.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
leaves = [c for c in cats if c["leaf"] and c["total"]]
leaf_products = sum(c["total"] for c in leaves)
msg = (f"DONE: {len(cats)} categories, {len(leaves)} leaf (<= {CAP}) covering ~{leaf_products:,} products, "
       f"{len([c for c in cats if not c['leaf']])} too-big (need deeper drill)")
open(PROG, "a").write(msg + "\n")
print(msg)
