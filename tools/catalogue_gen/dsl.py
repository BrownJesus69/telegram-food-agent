"""Tiny DSL so the dish master list stays readable.

A row is: (name, diet, price, prep, slots, spice, kcal, description[, aliases[, tags]])
  diet  : v = veg, e = egg, n = non-veg
  slots : letters from b(reakfast) l(unch) s(nack) d(inner) n(ight/late)
  price : base price in INR for a mid-range (price level 2) restaurant
  aliases/tags : pipe-separated strings
"""
from __future__ import annotations

import re
from dataclasses import dataclass

SLOT_NAMES = {"b": "breakfast", "l": "lunch", "s": "snack", "d": "dinner", "n": "latenight"}
DIET_NAMES = {"v": "veg", "e": "egg", "n": "nonveg"}


@dataclass(frozen=True)
class Dish:
    name: str
    section: str
    families: tuple[str, ...]
    diet: str  # veg | egg | nonveg
    price: int
    prep: int
    slots: tuple[str, ...]
    spice: int
    kcal: int
    desc: str
    aliases: tuple[str, ...]
    tags: tuple[str, ...]


# Vegetarian dishes that are traditionally made without onion or garlic. They get the `jain` tag so the concierge can
# honour "no onion/garlic" requests. The list is deliberately conservative: a dish is only tagged when it is the
# usual preparation, and the bot tells the customer the tag is catalogue-based.
JAIN_KEYWORDS = (
    "idli", "plain dosa", "pongal", "curd rice", "lemon rice", "coconut rice", "kesari", "payasam", "kheer", "mysore pak",
    "juice", "lassi", "majjige", "buttermilk", "coconut water", "ice cream", "gulab jamun", "rasmalai", "jalebi", "laddu",
    "burfi", "pedha", "halwa", "kulfi", "falooda", "filter coffee", "chai", "tea", "coffee", "hot chocolate", "shake",
    "lime", "kaju", "soan papdi", "holige", "obbattu", "rasgulla", "sandesh", "mishti doi", "dhokla", "khandvi", "thepla",
    "sugarcane", "badam milk", "rose milk", "banana", "nankhatai", "biscuit", "rusk", "banana chips", "kodubale", "chakli",
    "nippattu", "jaljeera", "cake", "brownie", "pancake", "waffle", "croissant", "muffin",
)


def _split(s: str) -> tuple[str, ...]:
    return tuple(x.strip() for x in s.split("|") if x.strip())


def block(section: str, families: str, rows: list[tuple]) -> list[Dish]:
    out = []
    fams = tuple(f.strip() for f in families.split(",") if f.strip())
    for row in rows:
        name, diet, price, prep, slots, spice, kcal, desc, *rest = row
        aliases = _split(rest[0]) if len(rest) > 0 else ()
        tags = _split(rest[1]) if len(rest) > 1 else ()
        low = name.lower()
        padded = " " + " ".join(re.findall("[a-z]+", low)) + " "
        if DIET_NAMES[diet] == "veg" and "jain" not in tags and any(f" {k} " in padded or f" {k}s " in padded for k in JAIN_KEYWORDS):
            tags = tags + ("jain",)
        out.append(
            Dish(
                name=name,
                section=section,
                families=fams,
                diet=DIET_NAMES[diet],
                price=price,
                prep=prep,
                slots=tuple(SLOT_NAMES[c] for c in slots),
                spice=spice,
                kcal=kcal,
                desc=desc,
                aliases=aliases,
                tags=tags,
            )
        )
    return out
