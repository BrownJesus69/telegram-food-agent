from aiogram.types import InlineKeyboardButton as B
from aiogram.types import InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, WebAppInfo

from foodbot import config
from foodbot.billing import BUTTON_PEOPLE


def location_request():
    """Share-my-location button, plus "Pick on map" (a Mini App) when MINIAPP_URL is configured.

    Telegram only allows web_app buttons on https URLs and only delivers sendData() from reply-keyboard Mini Apps.
    """
    row = [KeyboardButton(text="📍 Share location", request_location=True)]
    if config.MINIAPP_URL.startswith("https://"):
        row.append(KeyboardButton(text="🗺 Pick on map", web_app=WebAppInfo(url=config.MINIAPP_URL)))
    return ReplyKeyboardMarkup(
        keyboard=[row],
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
    rows.append([B(text="📍 Change address", callback_data="addr:book:c")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def skip_landmark():
    return InlineKeyboardMarkup(inline_keyboard=[[B(text="Skip", callback_data="skip_landmark")]])


def confirm(key):
    return InlineKeyboardMarkup(inline_keyboard=[
        [B(text="Confirm COD order", callback_data=f"confirm:{key}"), B(text="Cancel", callback_data="clear")],
        [B(text="📍 Change address", callback_data="addr:book:k"), B(text="👤 Change recipient", callback_data="addr:rcpt:k")],
    ])


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


# ------------------------------------------------------------------ addresses
LABEL_ICON = {"home": "🏠", "office": "🏢", "work": "🏢", "friend": "👥"}


def label_icon(label):
    low = (label or "").lower()
    for key, icon in LABEL_ICON.items():
        if low.startswith(key):
            return icon
    return "📍"


def _short(text, n=42):
    text = (text or "").replace(chr(10), " ")
    return text if len(text) <= n else text[: n - 1] + "…"


def change_address(ctx):
    return InlineKeyboardMarkup(inline_keyboard=[[B(text="📍 Change address", callback_data=f"addr:book:{ctx}")]])


def address_book(addresses, active_id, ctx):
    rows = []
    for a in addresses:
        mark = "✓ " if a["id"] == active_id else ""
        rows.append([B(text=f"{mark}{label_icon(a['label'])} {a['label']} — {_short(a['address'])}",
                       callback_data=f"addr:use:{a['id']}:{ctx}")])
    rows.append([B(text="➕ Add new address", callback_data=f"addr:new:{ctx}")])
    if addresses:
        rows.append([B(text="🗑 Remove an address", callback_data="addr:manage")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def manage_addresses(addresses):
    rows = [[B(text=f"🗑 {a['label']} — {_short(a['address'], 30)}", callback_data=f"addr:del:{a['id']}")] for a in addresses]
    rows.append([B(text="⬅ Back", callback_data="addr:book:a")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def label_choice():
    return InlineKeyboardMarkup(inline_keyboard=[
        [B(text="🏠 Home", callback_data="addr:lbl:home"), B(text="🏢 Office", callback_data="addr:lbl:office")],
        [B(text="👥 A friend / family", callback_data="addr:lbl:friend"), B(text="✏️ Other", callback_data="addr:lbl:other")],
        [B(text="Cancel", callback_data="addr:cancel")],
    ])


def place_candidates(places):
    rows = [[B(text=f"{i + 1}. {_short(p[0], 55)}", callback_data=f"addr:pick:{i}")] for i, p in enumerate(places)]
    rows.append([B(text="Cancel", callback_data="addr:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def areas(names):
    rows = [[B(text=n, callback_data=f"addr:area:{n}") for n in names[i:i + 2]] for i in range(0, len(names), 2)]
    rows.append([B(text="Cancel", callback_data="addr:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def skip_phone():
    return InlineKeyboardMarkup(inline_keyboard=[[B(text="Skip phone number", callback_data="addr:skipphone")]])


# ------------------------------------------------------------------ concierge
def plan_add(token, total):
    return InlineKeyboardMarkup(inline_keyboard=[[B(text=f"🛒 Add all to cart · ₹{total}", callback_data=f"plan:{token}")]])


def quick_picks(slot, labels, usual_order_id=None, usual_label="🔁 Your usual"):
    rows = []
    if usual_order_id:
        rows.append([B(text=usual_label, callback_data=f"again:{usual_order_id}")])
    rows.append([B(text=lab, callback_data=f"ask:{slot}:{i}") for i, lab in enumerate(labels)])
    rows.append([B(text="📍 Change address", callback_data="addr:book:s")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# --------------------------------------------------------------------- tracking and feedback
def again(order_id):
    return InlineKeyboardMarkup(inline_keyboard=[[B(text="🔁 Order again", callback_data=f"again:{order_id}")]])


def rating(order_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [B(text=f"{n}⭐", callback_data=f"rate:{order_id}:{n}") for n in range(1, 6)],
        [B(text="🔁 Order again", callback_data=f"again:{order_id}"), B(text="🧾 Split bill", callback_data=f"split:{order_id}")],
    ])


def track(order_id, can_cancel=False):
    row = [B(text="🔄 Refresh", callback_data=f"track:{order_id}")]
    if can_cancel:
        row.append(B(text="Cancel order", callback_data=f"ucancel:{order_id}"))
    return InlineKeyboardMarkup(inline_keyboard=[row, [B(text="🧾 Split bill", callback_data=f"split:{order_id}")]])


def reorder_choices(rows):
    """rows: [(order_id, label)] -> one 'again:<id>' button per past order."""
    return InlineKeyboardMarkup(inline_keyboard=[[B(text=label, callback_data=f"again:{oid}")] for oid, label in rows])


def split_choice(order_id):
    nums = [B(text=str(n), callback_data=f"split:{order_id}:{n}") for n in BUTTON_PEOPLE]
    return InlineKeyboardMarkup(inline_keyboard=[nums[:4], nums[4:]])
