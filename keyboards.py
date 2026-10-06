from aiogram.types import (InlineKeyboardButton as B, InlineKeyboardMarkup,
                           KeyboardButton, ReplyKeyboardMarkup)


def location_request():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📍 Share location", request_location=True)]],
        resize_keyboard=True, one_time_keyboard=True,
    )


def select(item_id, qty):
    return InlineKeyboardMarkup(inline_keyboard=[[B(text="Select", callback_data=f"sel:{item_id}:{qty}")]])


def swap_cart(item_id, qty):
    return InlineKeyboardMarkup(inline_keyboard=[[
        B(text="Clear and continue", callback_data=f"swap:{item_id}:{qty}"),
        B(text="Keep current cart", callback_data="keep"),
    ]])


def cart(lines):
    rows = []
    for ln in lines:
        rows.append([
            B(text="−", callback_data=f"dec:{ln['item_id']}"),
            B(text=f"{ln['name'][:18]} x{ln['qty']}", callback_data="noop"),
            B(text="+", callback_data=f"inc:{ln['item_id']}"),
        ])
    rows.append([B(text="Checkout", callback_data="checkout"), B(text="Clear cart", callback_data="clear")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def skip_landmark():
    return InlineKeyboardMarkup(inline_keyboard=[[B(text="Skip", callback_data="skip_landmark")]])


def confirm(key):
    return InlineKeyboardMarkup(inline_keyboard=[[
        B(text="Confirm COD order", callback_data=f"confirm:{key}"),
        B(text="Cancel", callback_data="clear"),
    ]])


def customer_cancel(order_id):
    return InlineKeyboardMarkup(inline_keyboard=[[B(text="Cancel order", callback_data=f"ucancel:{order_id}")]])


def admin(order_id, status):
    nxt = {
        "PENDING": [("Accept", f"adm:ACCEPTED:{order_id}"), ("Reject", f"rej:{order_id}")],
        "ACCEPTED": [("Preparing", f"adm:PREPARING:{order_id}")],
        "PREPARING": [("Out for delivery", f"adm:OUT_FOR_DELIVERY:{order_id}")],
        "OUT_FOR_DELIVERY": [("Delivered", f"adm:DELIVERED:{order_id}")],
    }.get(status)
    if not nxt:
        return None
    return InlineKeyboardMarkup(inline_keyboard=[[B(text=t, callback_data=d) for t, d in nxt]])


REASONS = ["Item unavailable", "Restaurant closed", "Outside delivery area", "Unable to fulfil"]


def reject_reasons(order_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [B(text=r, callback_data=f"rr:{order_id}:{i}")] for i, r in enumerate(REASONS)
    ])
