import re, json
from nykaa_scraper import NykaaScraper
s = NykaaScraper(); s._ensure_session()

def ids_for(url):
    r = s.session.get(url, headers={"Accept": "text/html,*/*", "Referer": "https://www.nykaa.com"}, timeout=20)
    m = re.search(r'__PRELOADED_STATE__\s*=\s*(\{.*)', r.text, re.DOTALL)
    raw = m.group(1); depth = 0
    for i, ch in enumerate(raw):
        if ch == '{': depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                st = json.loads(raw[:i+1]); break
    prods = st["categoryListing"]["listingData"]["products"]
    return [str(p.get("id")) for p in prods]

base = "https://www.nykaa.com/hair-care/hair/shampoo/c/316"
for variant in ["", "?page_no=2", "?page_no=3", "?page=2", "?sort=popularity&page_no=2"]:
    ids = ids_for(base + variant)
    print(f"{variant or '(page1)':<28} -> {len(ids)} products, first3={ids[:3]}")
