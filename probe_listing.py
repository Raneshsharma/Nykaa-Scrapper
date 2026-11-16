import re, json
from nykaa_scraper import NykaaScraper

s = NykaaScraper(); s._ensure_session()
url = "https://www.nykaa.com/search/result/?q=shampoo"
r = s.session.get(url, headers={"Accept": "text/html,*/*", "Referer": "https://www.nykaa.com"}, timeout=20)
print("search page HTTP", r.status_code, "len", len(r.text))
html = r.text

m = re.search(r'__PRELOADED_STATE__\s*=\s*(\{.*)', html, re.DOTALL)
raw = m.group(1) if m else ""
print("preloaded raw len:", len(raw))

data = None
if raw:
    depth = 0; endi = None
    for i, ch in enumerate(raw):
        if ch == '{': depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0: endi = i + 1; break
    if endi:
        try:
            data = json.loads(raw[:endi])
        except Exception as e:
            print("json err:", str(e)[:140])

PRICE_KEYS = {"price", "offerPrice", "mrp", "finalPrice", "sellingPrice"}

def walk(o, path="", depth=0):
    if depth > 5: return
    if isinstance(o, dict):
        for k, v in o.items():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                pk = set(v[0].keys())
                if PRICE_KEYS.intersection(pk) or ("name" in pk and ("id" in pk or "productId" in pk)):
                    print(f"ARRAY at {path}.{k}  len={len(v)}  keys={sorted(pk)[:22]}")
            walk(v, f"{path}.{k}", depth + 1)
    elif isinstance(o, list) and o:
        walk(o[0], path + "[0]", depth + 1)

if data:
    walk(data, "state")
else:
    for sig in ['"productId"', '"sku"', '"offerPrice"', '"childId"', '"position"']:
        print(sig, "count:", html.count(sig))
