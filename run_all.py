"""
Runs the daily collection for every tracked category, then is scheduled
(GitHub Actions / Task Scheduler / cron) to build daily history.

Add more haircare sub-categories to CATEGORIES as we map their /c/<id> URLs.
Each entry: ("label", "nykaa category URL")
"""
from collect_catalog import collect

CATEGORIES = [
    ("haircare:shampoo", "https://www.nykaa.com/hair-care/hair/shampoo/c/316"),
    # ("haircare:conditioner", "https://www.nykaa.com/hair-care/.../c/<id>"),
    # ("haircare:hair-oil",    "https://www.nykaa.com/hair-care/.../c/<id>"),
    # ("haircare:serum",       "https://www.nykaa.com/hair-care/.../c/<id>"),
    # ("haircare:hair-mask",   "https://www.nykaa.com/hair-care/.../c/<id>"),
    # ("haircare:hair-color",  "https://www.nykaa.com/hair-care/.../c/<id>"),
]

if __name__ == "__main__":
    for label, url in CATEGORIES:
        try:
            n = collect(url, label)
            print(f"OK {label}: {n} products")
        except Exception as e:
            print(f"FAIL {label}: {e}")
