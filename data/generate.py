"""Generate synthetic shoe supply chain tables for the fictional brand "Stride Footwear".

Usage:
  python data/generate.py
  python data/generate.py --upload provenance-data-4102a6 --profile provenance-new --region us-east-1

Output: data/out/*.parquet and data/out/planted_facts.json (ground truth for evals).
The same seed always produces the same data. All names are fictional.
"""
import argparse
import json
import random
from datetime import date, timedelta
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

SEED = 42
OUT = Path(__file__).parent / "out"
START = date(2025, 1, 1)

MODELS = ["Runner X", "Court Pro", "Trail Max", "City Glide", "Sprint Lite", "Hike Ridge"]
SIZES = [7, 8, 9, 10, 11]
COLOURS = {"Black": 1, "White": 1}  # colour -> unit cost multiplier

FACTORIES = [  # factory_id, name, country, tier, lead_days, penalty_pct_per_late_week
    ("F001", "Saigon Stitch Co", "Vietnam", "Gold", 14, 0.0),
    ("F002", "Hanoi Sole Works", "Vietnam", "Gold", 15, 0.0),
    ("F003", "Java Lace Mfg", "Indonesia", "Silver", 18, 0.0),
    ("F004", "Surabaya Foam Ltd", "Indonesia", "Bronze", 20, 2.0),
    ("F005", "Guangzhou Heel Co", "China", "Gold", 16, 0.0),
    ("F006", "Dongguan Mesh Factory", "China", "Silver", 17, 0.0),
    ("F007", "Shenzhen Rubber Ltd", "China", "Silver", 15, 0.0),
    ("F008", "Chennai Knit Works", "India", "Silver", 22, 0.0),
    ("F009", "Pune Upper Mills", "India", "Bronze", 24, 0.0),
    ("F010", "Ho Chi Minh Insole", "Vietnam", "Silver", 13, 0.0),
    ("F011", "Bekasi Cushion Co", "Indonesia", "Bronze", 21, 1.5),
    ("F012", "Ningbo Eyelet Ltd", "China", "Gold", 14, 0.0),
]
BAD_FACTORIES = {"F004", "F011"}  # planted: often late

WAREHOUSES = [  # warehouse_id, city, region
    ("W01", "Memphis", "US"),
    ("W02", "Rotterdam", "EU"),
    ("W03", "Singapore", "APAC"),
    ("W04", "Los Angeles", "US"),
]

N_POS = 300
BASE_LATE_RATE = 0.08          # normal factories
BAD_FACTORY_LATE_RATE = 0.40   # planted
LOW_STOCK_MODEL = "Runner X"   # planted: popular model, size 9, below reorder point
REORDER_POINT = 100

rng = random.Random(SEED)


def build_tables():
    rng.seed(SEED)  # same data every call
    factories = [
        {"factory_id": f, "name": n, "country": c, "tier": t, "lead_days": ld, "penalty_pct_per_late_week": p}
        for f, n, c, t, ld, p in FACTORIES
    ]

    products = []
    i = 0
    for model in MODELS:
        for size in SIZES:
            for colour, mult in COLOURS.items():
                i += 1
                products.append({
                    "sku": f"SF-{i:03d}",
                    "model": model,
                    "size": size,
                    "colour": colour,
                    "unit_cost": round(rng.uniform(18, 45) * mult, 2),
                })

    warehouses = [{"warehouse_id": w, "city": c, "region": r} for w, c, r in WAREHOUSES]

    low_stock_skus = {p["sku"] for p in products if p["model"] == LOW_STOCK_MODEL and p["size"] == 9}
    inventory = []
    for w in warehouses:
        for p in products:
            on_hand = rng.randint(5, 30) if p["sku"] in low_stock_skus else rng.randint(150, 600)
            inventory.append({
                "warehouse_id": w["warehouse_id"],
                "sku": p["sku"],
                "on_hand": on_hand,
                "reorder_point": REORDER_POINT,
            })

    purchase_orders, shipments = [], []
    for n in range(1, N_POS + 1):
        factory = rng.choice(factories)
        product = rng.choice(products)
        order_date = START + timedelta(days=rng.randint(0, 300))
        promised = order_date + timedelta(days=factory["lead_days"] + rng.randint(0, 5))
        po_id = f"PO-{n:05d}"
        purchase_orders.append({
            "po_id": po_id,
            "factory_id": factory["factory_id"],
            "sku": product["sku"],
            "qty": rng.randint(200, 2000),
            "order_date": order_date,
            "promised_date": promised,
        })
        late_rate = BAD_FACTORY_LATE_RATE if factory["factory_id"] in BAD_FACTORIES else BASE_LATE_RATE
        is_late = rng.random() < late_rate
        delivered = promised + timedelta(days=rng.randint(1, 10)) if is_late else promised - timedelta(days=rng.randint(0, 2))
        shipments.append({
            "shipment_id": f"SH-{n:05d}",
            "po_id": po_id,
            "ship_date": order_date + timedelta(days=rng.randint(3, 8)),
            "delivered_date": delivered,
            "status": "Delivered",
        })

    return {
        "factories": factories,
        "products": products,
        "warehouses": warehouses,
        "purchase_orders": purchase_orders,
        "shipments": shipments,
        "inventory": inventory,
    }


def planted_facts(t):
    """Compute the facts from the data itself, so the ground truth matches the files."""
    ship_by_po = {s["po_id"]: s for s in t["shipments"]}
    late = [p for p in t["purchase_orders"] if ship_by_po[p["po_id"]]["delivered_date"] > p["promised_date"]]
    late_by_factory = {}
    for p in late:
        late_by_factory[p["factory_id"]] = late_by_factory.get(p["factory_id"], 0) + 1
    low_stock = sorted({i["sku"] for i in t["inventory"] if i["on_hand"] < i["reorder_point"]})
    return {
        "seed": SEED,
        "brand": "Stride Footwear (fictional)",
        "late_shipments": len(late),
        "total_shipments": len(t["shipments"]),
        "late_pct": round(100 * len(late) / len(t["shipments"]), 1),
        "late_by_factory": dict(sorted(late_by_factory.items(), key=lambda kv: -kv[1])),
        "skus_below_reorder_point": low_stock,
        "planted_late_factories": sorted(BAD_FACTORIES),
        "planted_penalty_factory": "F004 (2% per late week)",
    }


def write_parquet(tables):
    OUT.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, rows in tables.items():
        path = OUT / f"{name}.parquet"
        pq.write_table(pa.Table.from_pylist(rows), path)
        paths.append(path)
    return paths


def upload(paths, bucket, profile, region):
    import boto3  # imported here so local generation works without AWS packages

    s3 = boto3.Session(profile_name=profile or None, region_name=region).client("s3")
    for path in paths:
        table = path.stem  # one folder per table, so Athena reads only that table
        key = f"raw/{table}/{path.name}"
        s3.upload_file(str(path), bucket, key)
        print(f"uploaded s3://{bucket}/{key}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--upload", metavar="BUCKET", help="S3 bucket to upload to")
    parser.add_argument("--profile", default="provenance-new")
    parser.add_argument("--region", default="us-east-1")
    args = parser.parse_args()

    tables = build_tables()
    paths = write_parquet(tables)
    facts = planted_facts(tables)
    (OUT / "planted_facts.json").write_text(json.dumps(facts, indent=2, default=str))
    print(f"wrote {len(paths)} tables to {OUT}")
    print(f"late shipments: {facts['late_shipments']}/{facts['total_shipments']} ({facts['late_pct']}%)")
    print(f"SKUs below reorder point: {facts['skus_below_reorder_point']}")

    if args.upload:
        upload(paths, args.upload, args.profile, args.region)


if __name__ == "__main__":
    main()
