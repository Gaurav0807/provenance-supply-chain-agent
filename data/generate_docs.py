"""Create synthetic supplier documents that match the generated data in data/generate.py.

Penalty rates, lead times, late purchase orders, penalty amounts, defect rates and
low-stock SKUs all come from the same data the tables use.
Each document is split into pages with '## Page N' headings, so answers can cite document and page.

Usage (from the project root):
  python -m data.generate_docs
"""
import random
from pathlib import Path

from data.generate import MODELS, build_tables

OUT = Path(__file__).parent / "documents"

SLA_TEXT = """# Logistics Service Level Agreement, 2026

This agreement sets delivery standards for all contract factories.

## Page 2: Standards

1. A shipment is on time if it arrives on or before the promised delivery date.
2. A shipment is critical if it is more than 5 days late. Critical shipments are reported to the Stride operations team within one business day.
3. Stock below the reorder point must be flagged to procurement the same day.

## Page 3: Reporting

4. Each factory receives a monthly scorecard: on-time rate, average days late, and open critical shipments.
5. A factory with on-time performance below 85% for two consecutive months enters a corrective action plan."""


def slug(text):
    return text.lower().replace(" ", "_").replace(".", "")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.md"):
        old.unlink()

    t = build_tables()
    rng = random.Random(7)
    factories = {f["factory_id"]: f for f in t["factories"]}
    products = {p["sku"]: p for p in t["products"]}
    pos = {p["po_id"]: p for p in t["purchase_orders"]}
    ships = {s["po_id"]: s for s in t["shipments"]}
    models = ", ".join(MODELS)
    written = 0

    def write(name, body):
        nonlocal written
        (OUT / name).write_text(body.strip() + "\n")
        written += 1

    # 1. One supply agreement per factory, with its real penalty rate and lead time
    for fid, f in factories.items():
        pen = f["penalty_pct_per_late_week"]
        if pen:
            clause = (
                f"If a shipment arrives after the promised delivery date, the supplier pays {pen}% "
                "of the purchase order value for each full week late. The penalty is deducted from "
                "the next invoice and applies to each late purchase order separately."
            )
        else:
            clause = (
                "This agreement has no late delivery penalty. Repeated delays are reviewed in the "
                "quarterly business review."
            )
        write(
            f"contract_{fid}_{slug(f['name'])}.md",
            f"""# Supply Agreement: {f['name']} ({fid})

Stride Footwear and {f['name']} ({f['country']}, {f['tier']} tier) agree to the following terms.

1. Scope: {models}, all sizes and colours.
2. Lead time: {f['lead_days']} days from purchase order to promised delivery date.

## Page 2: Late delivery penalty

3. {clause}

## Page 3: Termination

4. Either party may terminate with 60 days written notice.
5. If the supplier is late on three or more purchase orders in one quarter, Stride may review the agreement.""",
        )

    # 2. A delay notice for every late purchase order, with the penalty worked out
    for po_id, po in pos.items():
        s = ships[po_id]
        days = (s["delivered_date"] - po["promised_date"]).days
        if days <= 0:
            continue
        f = factories[po["factory_id"]]
        p = products[po["sku"]]
        weeks = days // 7
        value = po["qty"] * p["unit_cost"]
        pen = f["penalty_pct_per_late_week"]
        penalty = value * pen / 100 * weeks
        write(
            f"delay_notice_{po_id}.md",
            f"""# Delay Notice: {po_id}

Factory: {f['name']} ({po['factory_id']})
Product: {p['model']}, size {p['size']}, {p['colour']} (SKU {po['sku']})
Quantity: {po['qty']} pairs
Order date: {po['order_date']}
Promised delivery: {po['promised_date']}
Actual delivery: {s['delivered_date']}
Days late: {days} ({weeks} full weeks)

## Page 2: Penalty calculation

Purchase order value: {po['qty']} x {p['unit_cost']:.2f} = {value:.2f}
Penalty rate: {pen}% per full week late
Penalty: {value:.2f} x {pen}% x {weeks} = {penalty:.2f}""",
        )

    # 3. Quality report per factory
    for fid, f in factories.items():
        rate = round(rng.uniform(1.5, 4.5), 1)
        status = "within the 2.5% target" if rate <= 2.5 else "above the 2.5% target"
        action = "root-cause review with the factory is required" if rate > 2.5 else "none required"
        write(
            f"quality_report_{fid}_2026Q3.md",
            f"""# Quality Report: {f['name']} ({fid}), Q3 2026

## Page 1: Inspection summary

Defect rate: {rate}% ({status}).
Corrective action: {action}.""",
        )

    # 4. Stock note for each SKU below its reorder point, with the warehouses affected
    low = {}
    for i in t["inventory"]:
        if i["on_hand"] < i["reorder_point"]:
            low.setdefault(i["sku"], []).append(f"{i['warehouse_id']} ({i['on_hand']} on hand)")
    for sku, where in sorted(low.items()):
        p = products[sku]
        write(
            f"stock_note_{sku}.md",
            f"""# Stock Note: {p['model']}, size {p['size']}, {p['colour']} ({sku})

Stock is below the reorder point of 100 units in: {', '.join(where)}.

## Page 2: Action

Procurement should raise a replenishment purchase order and confirm the expected delivery date with the factory.""",
        )

    # 5. Logistics service level agreement
    write("logistics_sla_2026.md", SLA_TEXT)

    print(f"wrote {written} documents to {OUT}")


if __name__ == "__main__":
    main()
