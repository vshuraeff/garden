# Pricing capability

`api.py` owns coupon lookup and discounted-total arithmetic. `discount_percent(coupon_code)` returns an integer percentage, and `discounted_total(subtotal_cents, percent)` uses integer half-up rounding.

Pricing must not import orders, inventory, notify, `shop`, or `cli`. Coupon identifiers are pricing-owned data.

