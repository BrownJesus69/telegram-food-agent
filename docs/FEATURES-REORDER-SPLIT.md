# Reorder, "the usual" and split-the-bill

Both features are rule-based and deterministic. Nothing here goes through the LLM, and prices always come from the catalogue.

## Reorder (`/reorder`, "order again")

- **Entry points:** `/reorder`; the texts *order again*, *reorder*, *same as last time*, *the usual*, *repeat my last order*
  (matched by `handlers._REORDER` before the LLM is consulted, so voice notes work too); the **🔁 Order again** button on the
  delivered message (it stays on the "Thanks for rating" message); and the *Your usual* line described below.
- **Picker:** the last 3 `DELIVERED` orders as buttons with callback data `again:<order_id>`.
- **Rebuild** (`orders.reorder_plan` / `orders.reorder`): the order must belong to the caller and be `DELIVERED`
  (`OrderError` otherwise, so a forged `again:<someone else's id>` is refused with a popup). Each line is kept only if the
  item still exists on that restaurant's menu and is available. Quantity goes through `clamp_qty`, the unit price is today's
  catalogue price (the old order's price is ignored). If the restaurant is inactive/closed (`Restaurant.open_at`) or the active
  address is outside its delivery radius, nothing is kept and `plan.blocked` says why. With no active address the radius
  check is skipped and the normal cart screen asks for an address.
- **Result:** the cart is replaced (the user is told if it replaced something), dropped lines are listed with a reason, and
  the normal `send_cart` screen follows. If nothing is kept the cart is not touched.
- **Callback parsing:** `handlers._parse_again` accepts only `again:<ASCII digits, at most 12>`; zero, signs, spaces, other
  scripts' digits and extra segments are rejected.

## "Your usual <slot>"

`orders.usual_for_slot(tg_id)`: from the customer's 60 most recent delivered orders, group by restaurant those placed in
the **current meal slot** (`catalogue.current_slot`, judged in IST from `orders.created_at`). A restaurant with at least 2
such orders is a habit; the most frequent wins (ties: most recent). It is offered only if its latest order can be rebuilt right
now (open, in range, something available). No migration: it is a single read of the existing `orders` table.

It appears as one line, "🔁 Your usual lunch: 2 × X from Y (₹NNN)", plus a button (`again:<latest order id>`) on the greeting
and on an "I'm hungry"-style message with no dish named, and at the top of the `/reorder` list.

## Split the bill

- **Pure maths:** `foodbot/billing.py::split_total(total, people)` splits the order's stored total (items **plus delivery fee**)
  equally in whole rupees. The remainder `total mod n` is handed out one rupee at a time to the first people, so the shares
  always sum exactly to the total, differ by at most ₹1, and are never negative. `people` must be 1..20 (buttons offer 2..8).
  Example: ₹175 / 3 -> ₹59, ₹58, ₹58.
- **Text:** `format_split` returns plain, forwardable text with the restaurant name HTML-escaped, e.g.
  `Order #12 · Moonlight Kitchen · total ₹175 / 3 → ₹59, ₹58, ₹58` (`₹X each` when all shares are equal), plus a line saying the
  delivery fee is included.
- **Flow:** a **🧾 Split bill** button (`split:<order_id>`) is on the order-placed message, the tracking screen and the delivered
  message. When an order has 2 or more portions the bot also asks right after placement "Split the bill between how many
  people?" with buttons 2-8 (`split:<order_id>:<n>`). Only the order's own customer can use either callback; cancelled or
  rejected orders are refused; `handlers._parse_split` is strict like `_parse_pick`.

## Tests

`tests/test_reorder.py` (rebuild, dropped item, closed, out of radius, forged ids, clamp, usual-slot rule with the frozen
clock and IST handling, end-to-end bot flow) and `tests/test_billing.py` (Hypothesis properties plus the bot flow).
