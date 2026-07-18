# Inventory capability

`api.py` owns stock validation and reservation. `reserve(stock, sku, quantity)` returns a new mapping and never mutates the caller's mapping.

Inventory must not import orders, pricing, notify, `shop`, or `cli`. Cross-capability workflows call this public function from their owning composition boundary.

