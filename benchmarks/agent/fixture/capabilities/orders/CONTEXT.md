# Orders capability

`api.py` owns construction and validation of public order records. Its current public function is `create_order(order_id, sku, quantity, unit_price_cents, total_cents)`.

Orders must not calculate discounts, format notifications, or mutate inventory. T2 may add one explicit import of `capabilities.inventory.api` for the registered reserved-order workflow; no other capability import is allowed for that task.

