# Notify capability

`api.py` owns customer-facing confirmation text. `order_confirmation(recipient, order_id, total_cents)` returns the stable text consumed by the checkout contract.

Notify must not import orders, inventory, pricing, `shop`, or `cli`. It formats supplied values and owns no order, stock, or price state.

