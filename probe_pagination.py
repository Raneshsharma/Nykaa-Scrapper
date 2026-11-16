import re, json
from nykaa_scraper import NykaaScraper
s = NykaaScraper(); s._ensure_session()

def state_of(url):
    r = s.session.get(url, headers={"Accept": "text/html,*/*", "Referer": "https://www.nykaa.com"}, timeout=20)
    m = re.search(r'__PRELOADED_STATE__\s*=\s*(\{.*)', r.text, re.DOTALL)
    if not m: return r.status_code, None
    raw = m.group(1); depth = 0
    for i, ch in enumerate(raw):
        if ch == '{': depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                try: return r.status_code, json.loads(raw[:i+1])
                except Exception: return r.status_code, None
    return r.status_code, None

# 1) Use a real CATEGORY page (not search) for shampoo, id 316
code, st = state_of("https://www.nykaa.com/hair-care/hair/shampoo/c/316")
print("category page HTTP", code)
if st:
    ld = st.get("categoryListing", {}).get("listingData", {})
    print("listingData has", len(ld.get("products", [])), "products, totalFound", ld.get("totalFound"))
    # look for api config / pagination hints anywhere in state
    blob = json.dumps(st)
    for pat in [r'/gateway-api/[a-zA-Z0-9_\-/]+', r'/catalog[a-zA-Z0-9_\-/]+', r'"apiUrl"\s*:\s*"[^"]+"', r'"url"\s*:\s*"[^"]*products[^"]*"']:
        hits = sorted(set(re.findall(pat, blob)))
        if hits: print(pat, "->", hits[:8])

# 2) Try candidate listing API endpoints directly
print("\n--- candidate API endpoints ---")
cands = [
  "https://www.nykaa.com/gateway-api/categories/316/products?page_no=2&sort=popularity",
  "https://www.nykaa.com/gateway-api/products/listing?categoryId=316&page_no=2",
  "https://www.nykaa.com/gateway-api/categories/316/products/?pageNo=2&sort=popularity&apiVersion=5",
]
for u in cands:
    try:
        r = s.session.get(u, headers={"Accept": "application/json,*/*", "Referer": "https://www.nykaa.com/hair-care/hair/shampoo/c/316"}, timeout=15)
        ct = r.headers.get("content-type", "")
        prod_n = r.text.count('"productId"') + r.text.count('"sku"')
        print(f"HTTP {r.status_code} [{ct[:20]}] len={len(r.text)} prodHits={prod_n}  {u[:70]}")
    except Exception as e:
        print("ERR", str(e)[:60], u[:60])
