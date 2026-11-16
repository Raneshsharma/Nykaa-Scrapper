import re, json
from nykaa_scraper import NykaaScraper

s = NykaaScraper(); s._ensure_session()
r = s.session.get("https://www.nykaa.com/search/result/?q=shampoo",
                  headers={"Accept": "text/html,*/*", "Referer": "https://www.nykaa.com"}, timeout=20)
raw = re.search(r'__PRELOADED_STATE__\s*=\s*(\{.*)', r.text, re.DOTALL).group(1)
depth = 0
for i, ch in enumerate(raw):
    if ch == '{': depth += 1
    elif ch == '}':
        depth -= 1
        if depth == 0:
            st = json.loads(raw[:i+1]); break
ld = st["categoryListing"]["listingData"]
print("totalFound:", ld.get("totalFound"), "| sort:", ld.get("sort"), "| per page:", len(ld["products"]))
p = ld["products"][0]
# show only compact, useful fields
useful = {}
for k, v in p.items():
    if k in ("categoryIds",): continue
    if isinstance(v, (str, int, float, bool)) or v is None:
        useful[k] = v
print("\n--- useful scalar fields of product[0] ---")
print(json.dumps(useful, indent=1, ensure_ascii=False))
print("\nprice-ish keys:", [k for k in p if "price" in k.lower() or k in ("mrp","discount","finalPrice","offerPrice","sp")])
print("rating-ish keys:", [k for k in p if "rat" in k.lower() or "review" in k.lower() or "star" in k.lower()])
