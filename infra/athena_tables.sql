-- Athena table definitions for the Stride Footwear data in S3.
-- Run in the Athena console (Query editor), one statement at a time.

CREATE DATABASE IF NOT EXISTS provenance;

CREATE EXTERNAL TABLE IF NOT EXISTS provenance.factories (
  factory_id string,
  name string,
  country string,
  tier string,
  lead_days bigint,
  penalty_pct_per_late_week double
)
STORED AS PARQUET
LOCATION 's3://provenance-data-4102a6/raw/factories/';

CREATE EXTERNAL TABLE IF NOT EXISTS provenance.products (
  sku string,
  model string,
  size bigint,
  colour string,
  unit_cost double
)
STORED AS PARQUET
LOCATION 's3://provenance-data-4102a6/raw/products/';

CREATE EXTERNAL TABLE IF NOT EXISTS provenance.warehouses (
  warehouse_id string,
  city string,
  region string
)
STORED AS PARQUET
LOCATION 's3://provenance-data-4102a6/raw/warehouses/';

CREATE EXTERNAL TABLE IF NOT EXISTS provenance.purchase_orders (
  po_id string,
  factory_id string,
  sku string,
  qty bigint,
  order_date date,
  promised_date date
)
STORED AS PARQUET
LOCATION 's3://provenance-data-4102a6/raw/purchase_orders/';

CREATE EXTERNAL TABLE IF NOT EXISTS provenance.shipments (
  shipment_id string,
  po_id string,
  ship_date date,
  delivered_date date,
  status string
)
STORED AS PARQUET
LOCATION 's3://provenance-data-4102a6/raw/shipments/';

CREATE EXTERNAL TABLE IF NOT EXISTS provenance.inventory (
  warehouse_id string,
  sku string,
  on_hand bigint,
  reorder_point bigint
)
STORED AS PARQUET
LOCATION 's3://provenance-data-4102a6/raw/inventory/';

-- Test: delayed shipments per factory (should match planted_facts.json)
SELECT f.factory_id, f.name, COUNT(*) AS late_shipments
FROM provenance.shipments s
JOIN provenance.purchase_orders p ON s.po_id = p.po_id
JOIN provenance.factories f ON p.factory_id = f.factory_id
WHERE s.delivered_date > p.promised_date
GROUP BY f.factory_id, f.name
ORDER BY late_shipments DESC;
