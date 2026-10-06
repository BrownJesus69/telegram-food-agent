import html
import logging
import re
import uuid

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from rapidfuzz import fuzz

from foodbot import config, db, geo, orders, parser
from foodbot import keyboards as kb
from foodbot.services import catalogue
from foodbot.services.catalogue import RESTAURANTS, get_item, get_items_for_restaurant, get_restaurant
from foodbot.services.distance import haversine_km
from foodbot.services.search import closed_matches, search_items

log = logging.getLogger(__name__)
router = Router()
esc = html.escape

# last restaurants shown to each user, so "show menu" with no name means "the first one I just saw"
LAST_SHOWN: dict[int, list[str]] = {}

STATUS_TEXT = {
    "ACCEPTED": "✅ Order #{id} was accepted. The restaurant is getting started.",
    "PREPARING": "👨‍🍳 Order #{id} is being prepared.",
    "OUT_FOR_DELIVERY": "🛵 Order #{id} is out for delivery.",
    "DELIVERED": "🎉 Order #{id} was delivered. Enjoy your meal!",
}

DIET_ICON = {"veg": "🟢", "egg": "🟡", "nonveg": "🔴"}


def is_admin(user_id, chat_id):
    return user_id in config.ADMIN_IDS or chat_id in config.ADMIN_IDS


def detect_menu_request(text: str):
    n = re.sub(r"\s+", " ", (text or "").strip().lower())
    patterns = [
        r"^show me menu of (?P<name>.+)$",
        r"^show menu of (?P<name>.+)$",
        r"^menu of (?P<name>.+)$",
        r"^show (?P<name>.+) menu$",
        r"^what is available in (?P<name>.+)$",
        r"^show menu for (?P<name>.+)$",
    ]
    for pat in patterns:
        m = re.match(pat, n)
        if m:
            name = (m.group("name") or "").strip(" ?.!").strip()
            if name:
                return name
    if n in {"show menu", "show me menu", "menu", "its menu", "show its menu"}:
        return "__LAST__"
    return None


def find_restaurant(name: str, uid: int, user=None):
    """Resolve a typed restaurant name against the catalogue; ties go to the one nearest the user."""
    target = (name or "").strip().lower()
    if not target:
        return None
    if target == "__last__":
        ids = LAST_SHOWN.get(uid) or []
        return get_restaurant(ids[0]) if ids else None
    has_loc = bool(user) and user["latitude"] is not None
    scored = []
    for rest in RESTAURANTS.values():
        rn = rest.name.lower()
        score = 100 if rn == target else max(fuzz.WRatio(target, rn), 90 if target in rn else 0)
        if score >= 80:
            dist = haversine_km(user["latitude"], user["longitude"], rest.lat, rest.lon) if has_loc else 0.0
            scored.append((-score, dist, rest.id, rest))
    scored.sort(key=lambda x: x[:3])
    return scored[0][3] if scored else None


def build_menu_text_for_restaurant(rest):
    items = [i for i in get_items_for_restaurant(rest.id) if i.available]
    head = (
        f"🍽 <b>{esc(rest.name)}</b> · {esc(rest.category)}\n"
        f"⭐ {rest.rating:.1f} ({rest.rating_count}) · {esc(rest.locality)} · {rest.hours_label}"
        + ("" if rest.open_at() else " · <b>closed now</b>")
    )
    if not items:
        return head + "\n\nNo items are available right now."
    items.sort(key=lambda x: (x.category, x.price, x.name))
    lines = [head]
    current = None
    for it in items[:45]:
        if it.category != current:
            current = it.category
            lines.append(f"\n<b>{esc(current)}</b>")
        lines.append(f"{DIET_ICON.get(it.diet, '')} {esc(it.name)} — ₹{it.price}")
    if len(items) > 45:
        lines.append(f"\nShowing 45 of {len(items)} items.")
    return "\n".join(lines)


def result_text(r):
    it, rest = r.item, r.restaurant
    spice = "🌶" * it.spice if it.spice else ""
    lines = [
        f"{DIET_ICON.get(it.diet, '')} <b>{esc(it.name)}</b> — ₹{it.price} {spice}".rstrip(),
        f"{esc(rest.name)} · {esc(rest.locality)}",
        f"⭐ {rest.rating:.1f} · {r.distance_km:.1f} km · ⏱ {r.eta_min}–{r.eta_max} min",
    ]
    if it.description:
        lines.append(f"<i>{esc(it.description)}</i>")
    return "\n".join(lines)


def cart_text(s):
    lines = "\n".join(f"{ln['name']} × {ln['qty']} — ₹{ln['amount']}" for ln in s["lines"])
    return (
        f"🛒 <b>Your cart</b> — {esc(s['rest'].name)}\n\n{esc(lines)}\n\n"
        f"Subtotal: ₹{s['subtotal']}\nDelivery: ₹{s['fee']}\n<b>Total: ₹{s['total']}</b>\n"
        f"Estimated delivery: {s['eta'][0]}–{s['eta'][1]} min (catalogue estimate)\n"
        f"Payment: cash on delivery"
    )


def admin_card(order, items):
    lines = "\n".join(f"{i['quantity']} × {i['item_name']} (₹{i['unit_price']})" for i in items)
    rest = get_restaurant(order["restaurant_id"])
    maps = f"https://maps.google.com/?q={order['latitude']},{order['longitude']}"
    return (
        f"🔔 <b>ORDER #{order['id']}</b> — {esc(order['status'])}\n"
        f"Restaurant: {esc(rest.name if rest else order['restaurant_id'])}\n"
        f"Customer: {esc(order['customer_name'] or '-')} (ID {order['customer_id']})\n\n"
        f"{esc(lines)}\n\n"
        f"Subtotal ₹{order['subtotal']} · Delivery ₹{order['delivery_fee']} · <b>Total ₹{order['total']}</b>\n"
        f"Payment: {order['payment_method']}\n"
        f"Address: {esc(order['address'] or '-')}\n"
        f"Landmark: {esc(order['landmark'] or '-')}\n"
        f"Map: {maps}"
    )


async def safe_edit(msg, text, markup=None):
    try:
        await msg.edit_text(text, reply_markup=markup)
    except TelegramBadRequest:
        pass


async def send_cart(msg, tg_id, edit=False):
    s = orders.cart_summary(tg_id)
    if not s or not s.get("lines"):
        text, markup = "Your cart is empty. Tell me what you'd like to eat.", None
    else:
        text = cart_text(s)
        if s["issues"]:
            text += "\n\n⚠️ " + esc(" ".join(s["issues"]))
        markup = kb.cart(s["lines"])
    if edit:
        await safe_edit(msg, text, markup)
    else:
        await msg.answer(text, reply_markup=markup)


@router.message(CommandStart())
@router.message(Command("help"))
async def start(m: Message):
    db.upsert_user(m.from_user.id, m.from_user.full_name)
    slot = catalogue.current_slot()
    await m.answer(
        "👋 Hi! I find food from Bengaluru kitchens near you — all restaurants and menus here are simulated.\n"
        "Share your location, then tell me what you want — e.g. <i>I am hungry, I want biryani under 300</i>.\n"
        f"<i>Right now it's {slot} time in Bengaluru.</i>",
        reply_markup=kb.location_request(),
    )


@router.message(Command("location"))
async def ask_location(m: Message):
    await m.answer("Tap the button to share your delivery location.", reply_markup=kb.location_request())


@router.message(Command("cart"))
async def show_cart(m: Message):
    await send_cart(m, m.from_user.id)


@router.message(Command("orders"))
async def admin_orders(m: Message):
    if not is_admin(m.from_user.id, m.chat.id):
        return
    rows = orders.recent_orders(10)
    if not rows:
        await m.answer("No orders yet.")
        return
    await m.answer("\n".join(f"#{r['id']} · {r['status']} · ₹{r['total']} · {r['created_at']}" for r in rows))


@router.message(F.location)
async def got_location(m: Message):
    db.upsert_user(m.from_user.id, m.from_user.full_name)
    lat, lon = m.location.latitude, m.location.longitude
    label = await geo.reverse_geocode(lat, lon)
    db.set_location(m.from_user.id, lat, lon, label)
    where = f"\n📍 {esc(label)}" if label else ""
    await m.answer(f"Location saved.{where}\nWhat would you like to eat?", reply_markup=ReplyKeyboardRemove())


@router.message(F.text & ~F.text.startswith("/"))
async def on_text(m: Message):
    uid = m.from_user.id
    db.upsert_user(uid, m.from_user.full_name)
    user = db.get_user(uid)

    if not user:
        await m.answer("Please send /start first.")
        return

    if user["awaiting"] == "landmark":
        db.set_field(uid, landmark=m.text[:200], awaiting=None)
        await show_confirm(m, uid)
        return

    menu_target = detect_menu_request(m.text)
    if menu_target:
        rest = find_restaurant(menu_target, uid, user)
        if not rest:
            await m.answer("I couldn't find that restaurant. Try: <i>show me menu of Darshini</i>, or search for a dish first.")
            return
        await m.answer(build_menu_text_for_restaurant(rest))
        return

    if user["latitude"] is None:
        await m.answer("Please share your location first.", reply_markup=kb.location_request())
        return

    q = parser.parse(m.text)
    lat, lon = user["latitude"], user["longitude"]
    results = search_items(q.dish, lat, lon, budget=q.budget, diet=q.diet, limit=config.MAX_SEARCH_RESULTS) if q.dish else []

    if not results:
        q2 = await parser.groq_extract(m.text)
        if q2 and q2.dish:
            q = q2
            results = search_items(q.dish, lat, lon, budget=q.budget, diet=q.diet, limit=config.MAX_SEARCH_RESULTS)

    if not q.dish:
        await m.answer("What would you like to eat? Example: <i>chicken biryani under 300</i>")
        return

    if not results:
        text = f"I couldn't find “{esc(q.dish)}” open and delivering to you right now."
        later = closed_matches(q.dish, lat, lon, budget=q.budget, diet=q.diet)
        if later:
            text += "\n\nThese match but are closed at the moment:\n" + "\n".join(
                f"• {esc(r.restaurant.name)} (opens {r.restaurant.hours_label.split(' – ')[0]})" for r in later
            )
        await m.answer(text)
        return

    LAST_SHOWN[uid] = [r.restaurant.id for r in results]
    await m.answer(f"Top {len(results)} option(s) near you:")
    for r in results:
        await m.answer(result_text(r), reply_markup=kb.select(r.item.id, q.qty))


@router.callback_query(F.data == "noop")
async def cb_noop(cb: CallbackQuery):
    await cb.answer()


@router.callback_query(F.data.startswith("sel:"))
async def cb_select(cb: CallbackQuery):
    await cb.answer()
    _, item_id, qty = cb.data.split(":")
    it = get_item(item_id)
    if not it or not it.available:
        await cb.message.answer("Sorry, that item is no longer available.")
        return
    if orders.add_item(cb.from_user.id, item_id, int(qty)) == "conflict":
        await cb.message.answer(
            "Your cart has items from another restaurant. Clear it and start a new cart?",
            reply_markup=kb.swap_cart(item_id, int(qty)),
        )
        return
    await send_cart(cb.message, cb.from_user.id)


@router.callback_query(F.data.startswith("swap:"))
async def cb_swap(cb: CallbackQuery):
    await cb.answer()
    _, item_id, qty = cb.data.split(":")
    orders.add_item(cb.from_user.id, item_id, int(qty), replace=True)
    await send_cart(cb.message, cb.from_user.id, edit=False)


@router.callback_query(F.data == "keep")
async def cb_keep(cb: CallbackQuery):
    await cb.answer("Kept your current cart.")
    await send_cart(cb.message, cb.from_user.id)


@router.callback_query(F.data.startswith(("inc:", "dec:")))
async def cb_qty(cb: CallbackQuery):
    await cb.answer()
    action, item_id = cb.data.split(":")
    orders.change_qty(cb.from_user.id, item_id, 1 if action == "inc" else -1)
    await send_cart(cb.message, cb.from_user.id, edit=True)


@router.callback_query(F.data == "clear")
async def cb_clear(cb: CallbackQuery):
    await cb.answer("Cart cleared.")
    orders.clear_cart(cb.from_user.id)
    db.set_field(cb.from_user.id, awaiting=None, pending_key=None, landmark=None)
    await safe_edit(cb.message, "Cart cleared. Tell me what you'd like to eat.")


@router.callback_query(F.data == "checkout")
async def cb_checkout(cb: CallbackQuery):
    await cb.answer()
    s = orders.cart_summary(cb.from_user.id)
    if not s or not s.get("lines"):
        await cb.message.answer("Your cart is empty.")
        return
    if s["issues"]:
        await cb.message.answer("⚠️ " + esc(" ".join(s["issues"])))
        return
    db.set_field(cb.from_user.id, awaiting="landmark")
    await cb.message.answer(
        "Send a landmark or delivery instruction (e.g. <i>Main gate, opposite ABC College</i>), or tap Skip.",
        reply_markup=kb.skip_landmark(),
    )


@router.callback_query(F.data == "skip_landmark")
async def cb_skip(cb: CallbackQuery):
    await cb.answer()
    db.set_field(cb.from_user.id, awaiting=None, landmark=None)
    await show_confirm(cb.message, cb.from_user.id)


async def show_confirm(msg, uid):
    s = orders.cart_summary(uid)
    if not s or not s.get("lines") or s["issues"]:
        await msg.answer("⚠️ " + esc(" ".join((s or {}).get("issues", ["Your cart is empty."]))))
        return
    key = uuid.uuid4().hex[:16]
    db.set_field(uid, pending_key=key)
    user = db.get_user(uid)
    text = cart_text(s)
    text += f"\n\nDeliver to: {esc(user['address'] or 'your shared location')}"
    text += f"\nInstructions: {esc(user['landmark'] or '-')}"
    await msg.answer(text, reply_markup=kb.confirm(key))


@router.callback_query(F.data.startswith("confirm:"))
async def cb_confirm(cb: CallbackQuery):
    await cb.answer()
    key = cb.data.split(":", 1)[1]
    try:
        oid, new = orders.create_order(cb.from_user.id, key)
    except orders.OrderError as e:
        await cb.message.answer(f"⚠️ {esc(str(e))}")
        return
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass
    if not new:
        await cb.message.answer(f"Order #{oid} was already placed.")
        return
    order, items = orders.get_order(oid)
    sent = 0
    for admin_id in config.ADMIN_IDS:
        try:
            await cb.bot.send_message(admin_id, admin_card(order, items), reply_markup=kb.admin(oid, "PENDING"))
            sent += 1
        except Exception as e:
            log.warning("admin notify failed for %s: %s", admin_id, type(e).__name__)
    text = f"✅ Order #{oid} placed and sent to the restaurant. Waiting for acceptance."
    if not sent:
        text += "\n⚠️ Could not reach the restaurant admin yet; your order is saved."
    await cb.message.answer(text, reply_markup=kb.customer_cancel(oid))


@router.callback_query(F.data.startswith("ucancel:"))
async def cb_user_cancel(cb: CallbackQuery):
    oid = int(cb.data.split(":")[1])
    order, _ = orders.get_order(oid)
    if not order or order["customer_id"] != cb.from_user.id:
        await cb.answer("Not your order.", show_alert=True)
        return
    try:
        orders.transition(oid, "CANCELLED", "cancelled by customer")
    except orders.OrderError:
        await cb.answer("Too late to cancel here. Please contact the restaurant.", show_alert=True)
        return
    await cb.answer()
    await safe_edit(cb.message, f"Order #{oid} cancelled.")
    for admin_id in config.ADMIN_IDS:
        try:
            await cb.bot.send_message(admin_id, f"⌁ Order #{oid} was cancelled by the customer.")
        except Exception:
            pass


async def notify_customer(bot, order, text):
    try:
        await bot.send_message(order["customer_id"], text)
    except Exception as e:
        log.warning("customer notify failed: %s", type(e).__name__)


@router.callback_query(F.data.startswith("adm:"))
async def cb_admin(cb: CallbackQuery):
    if not is_admin(cb.from_user.id, cb.message.chat.id):
        await cb.answer("Unauthorized", show_alert=True)
        return
    _, status, oid = cb.data.split(":")
    oid = int(oid)
    try:
        orders.transition(oid, status)
    except orders.OrderError as e:
        await cb.answer(str(e), show_alert=True)
        return
    await cb.answer(status)
    order, items = orders.get_order(oid)
    await safe_edit(cb.message, admin_card(order, items), kb.admin(oid, status))
    text = STATUS_TEXT[status].format(id=oid)
    if status == "ACCEPTED":
        text += f"\nEstimated delivery: {order['eta_min']}–{order['eta_max']} min."
    await notify_customer(cb.bot, order, text)


@router.callback_query(F.data.startswith("rej:"))
async def cb_reject(cb: CallbackQuery):
    if not is_admin(cb.from_user.id, cb.message.chat.id):
        await cb.answer("Unauthorized", show_alert=True)
        return
    await cb.answer()
    oid = int(cb.data.split(":")[1])
    await cb.message.edit_reply_markup(reply_markup=kb.reject_reasons(oid))


@router.callback_query(F.data.startswith("rr:"))
async def cb_reject_reason(cb: CallbackQuery):
    if not is_admin(cb.from_user.id, cb.message.chat.id):
        await cb.answer("Unauthorized", show_alert=True)
        return
    _, oid, idx = cb.data.split(":")
    oid = int(oid)
    reason = kb.REASONS[int(idx)]
    try:
        orders.transition(oid, "REJECTED", reason)
    except orders.OrderError as e:
        await cb.answer(str(e), show_alert=True)
        return
    await cb.answer("Rejected")
    order, items = orders.get_order(oid)
    await safe_edit(cb.message, admin_card(order, items) + f"\nReason: {esc(reason)}", None)
    await notify_customer(cb.bot, order, f"Order #{oid} could not be accepted.\nReason: {reason}.\nNo payment was collected.")
