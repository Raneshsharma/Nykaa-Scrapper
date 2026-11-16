import re, json
from nykaa_scraper import NykaaScraper

s = NykaaScraper(); s._ensure_session()

def get_state(url):
    r = s.session.get(url, headers={"Accept": "text/html,*/*", "Referer": "https://www.nykaa.com"}, timeout=20)
    m = re.search(r'__PRELOADED_STATE__\s*=\s*(\{.*)', r.text, re.DOTALL)
    raw = m.group(1)
    depth = 0
    for i, ch in enumerate(raw):
        if ch == '{': depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0: return json.loads(raw[:i+1]), r.status_code
    return None, r.status_code

st, code = get_state("https://www.nykaa.com/search/result/?q=shampoo&page_no=2")
ld = st["categoryListing"]["listingData"]
print("HTTP", code)
print("listingData top keys:", sorted(ld.keys()))
for k in ["total", "totalCount", "page", "pageNo", "currentPage", "totalPages", "categoryName", "title", "count"]:
    if k in ld: print(f"  {k} = {ld[k]}")
prods = ld["products"]
print("products on this page:", len(prods))
print("\n--- FULL product[0] ---")
print(json.dumps(prods[0], indent=1, ensure_ascii=False)[:1600])
