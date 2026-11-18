"""
Daily driver: scrapes every discovered LEAF category (under Nykaa's pagination
cap) into dated snapshots. Supports sharding so GitHub Actions can run many
parallel jobs on different IPs:  SHARD_INDEX / SHARD_COUNT env vars.
"""
import os, re, json
from collect_catalog import collect


def slug_label(url):
    # /hair-care/hair/shampoo/c/316 -> hair-care:hair:shampoo
    path = re.search(r'https://www\.nykaa\.com/(.+?)/c/\d+', url)
    return path.group(1).replace("/", ":") if path else url


def main():
    cats = json.load(open("categories.json", encoding="utf-8"))
    leaves = [c for c in cats if c.get("leaf") and c.get("total")]

    shard = int(os.environ.get("SHARD_INDEX", "0"))
    nshard = int(os.environ.get("SHARD_COUNT", "1"))
    mine = [c for i, c in enumerate(leaves) if i % nshard == shard]
    print(f"shard {shard}/{nshard}: handling {len(mine)} of {len(leaves)} leaf categories")

    ok = total = 0
    failed = []
    for c in mine:
        label = slug_label(c["url"])
        try:
            n = collect(c["url"], label)
            ok += 1; total += n
            print(f"OK   {label}: {n} products")
        except Exception as e:
            failed.append(c)
            print(f"FAIL {label}: {e}")

    # second pass: retry the ones that failed (transient Akamai blocks)
    if failed:
        print(f"shard {shard}: retrying {len(failed)} failed categories")
        for c in failed:
            label = slug_label(c["url"])
            try:
                n = collect(c["url"], label)
                ok += 1; total += n
                print(f"RETRY-OK {label}: {n} products")
            except Exception as e:
                print(f"RETRY-FAIL {label}: {e}")
    print(f"shard {shard} done: {ok}/{len(mine)} categories, {total} product-rows")


if __name__ == "__main__":
    main()
