"""Split-the-bill arithmetic for group orders. Pure functions: no database, no Telegram.

Rule: the bill is the order's stored total (items + delivery fee), in whole rupees. It is divided equally; the
remainder (total mod n) is handed out one rupee at a time to the first people in the list, so the shares always
sum exactly to the total and no two shares differ by more than Rs 1. Shares come back in descending order.
"""
from __future__ import annotations

import html

MIN_PEOPLE = 1
MAX_PEOPLE = 20          # the bot's buttons offer 2-8; the function itself accepts a bit more headroom
BUTTON_PEOPLE = tuple(range(2, 9))


def split_total(total: int, people: int) -> list[int]:
    """Equal split of `total` rupees between `people`; shares sum to `total`, max - min <= 1, never negative."""
    if isinstance(total, bool) or isinstance(people, bool) or not isinstance(total, int) or not isinstance(people, int):
        raise ValueError("total and people must be whole numbers")
    if total < 0:
        raise ValueError("total cannot be negative")
    if not MIN_PEOPLE <= people <= MAX_PEOPLE:
        raise ValueError(f"people must be between {MIN_PEOPLE} and {MAX_PEOPLE}")
    base, extra = divmod(total, people)
    return [base + 1] * extra + [base] * (people - extra)


def format_split(order_id: int, restaurant: str, total: int, people: int, delivery_fee: int = 0) -> str:
    """Plain text a customer can forward to friends; safe to send with parse_mode=HTML (names are escaped)."""
    shares = split_total(total, people)
    if len(set(shares)) == 1:
        owed = f"₹{shares[0]} each"
    else:
        owed = ", ".join(f"₹{s}" for s in shares)
    head = f"Order #{int(order_id)} · {html.escape(restaurant)} · total ₹{total} / {people} → {owed}"
    if delivery_fee:
        return head + f"\n(includes ₹{delivery_fee} delivery, split equally)"
    return head
