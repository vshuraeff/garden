# Capability boundaries

The canonical domain names are `orders`, `inventory`, `pricing`, and `notify`. Their public modules are the `capabilities.<name>.api` modules.

| Capability | Owns | Public contract | Must not import |
| --- | --- | --- | --- |
| `orders` | Order record construction | `capabilities.orders.api.create_order` | `pricing`, `notify`; `inventory` is allowed only for T2's registered boundary crossing |
| `inventory` | Stock validation and reservation | `capabilities.inventory.api.reserve` | `orders`, `pricing`, `notify` |
| `pricing` | Coupon lookup and discounted totals | `capabilities.pricing.api.discount_percent`, `discounted_total` | `orders`, `inventory`, `notify` |
| `notify` | Customer-facing confirmation text | `capabilities.notify.api.order_confirmation` | `orders`, `inventory`, `pricing` |

`shop.py` is the composition boundary and may import all four public modules. Capability modules must not import `shop` or `cli`. `cli.py` may call `shop.checkout` but must not reach into capability internals.

