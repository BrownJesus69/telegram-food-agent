import html
import logging
import re
import uuid

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message
from rapidfuzz import fuzz

from foodbot import address_flow, billing, config, db, fulfilment, metrics, orders, stats
from foodbot import keyboards as kb
from foodbot.concierge import planner, vision
from foodbot.concierge.intent import FoodRequest
from foodbot.concierge.llm import default_client
from foodbot.concierge.rules import interpret_rules
from foodbot.concierge.understand import second_opinion, understand
from foodbot.fulfilment import admin_card, progress_bar
from foodbot.observability import TokenBucket
from foodbot.services import catalogue
from foodbot.services.catalogue import RESTAURANTS, get_item, get_items_for_restaurant, get_restaurant
from foodbot.services.distance import haversine_km

log = logging.getLogger(__name__)
router = Router()
esc = html.escape

# last restaurants shown to each user, so "show menu" with no name means "the first one I just saw"
LAST_SHOWN: dict[int, list[str]] = {}
# the last parsed food request per user, so switching address can re-run it
LAST_QUERY: dict[int, FoodRequest] = {}
# "add all" plans offered to a user: token -> (user id, [(item id, qty)]); small LRU
PLANS: dict[str, tuple[int, list[tuple[str, int]]]] = {}

QUICK_PICKS = {
    "breakfast": ["masala dosa", "idli vada", "filter coffee"],
    "lunch": ["karnataka meals", "chicken biryani", "north indian thali"],
    "snack": ["samosa", "pani puri", "masala chai"],
    "dinner": ["biryani", "kothu parotta", "butter chicken"],
    "latenight": ["chicken roll", "biryani", "masala maggi"],
}

# A photo read costs ~2,000 tokens against Groq's free 8,000/minute: each customer gets a small burst then one every 20 s,
# and the bot as a whole is held to about 3 a minute so that text messages keep their share of the quota.
PHOTO_LIMIT = TokenBucket(config.PHOTO_BURST, config.PHOTO_PER_SECOND)
PHOTO_GLOBAL = TokenBucket(config.PHOTO_GLOBAL_BURST, config.PHOTO_GLOBAL_PER_SECOND)

DIET_ICON = {"veg": "🟢", "egg": "🟡", "nonveg": "🔴"}


def caution_line(req: FoodRequest) -> str:
    """Be honest about a stated need we cannot filter on (halal, diabetic, 'no mushrooms'...): never imply a guarantee we do not have."""
    if not req.cautions:
        return ""
    things = ", ".join(esc(c) for c in req.cautions)
    return f"\n⚠️ I can't filter for <b>{things}</b> yet. Please check each dish's details with the kitchen before ordering."


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


def find_restaurant(name: str, uid: int):
    """Resolve a typed restaurant name against the catalogue; ties go to the one nearest the user."""
    target = (name or "").strip().lower()
    if not target:
        return None
    if target == "__last__":
        ids = LAST_SHOWN.get(uid) or []
        return get_restaurant(ids[0]) if ids else None
    here = db.location_of(uid)
    scored = []
    for rest in RESTAURANTS.values():
        rn = rest.name.lower()
        score = 100 if rn == target else max(fuzz.WRatio(target, rn), 90 if target in rn else 0)
        if score >= 80:
            dist = haversine_km(here[0], here[1], rest.lat, rest.lon) if here else 0.0
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
    db.set_field(m.from_user.id, awaiting=None)
    db.set_draft(m.from_user.id, None)
    slot = catalogue.current_slot()
    await m.answer(
        "👋 Hi! I find food from Bengaluru kitchens near you — all restaurants and menus here are simulated.\n"
        "Tell me what you want in plain words (English, Hinglish or Kannada) — <i>light dinner for 2 under 500</i>, "
        "<i>ondu masala dose</i>, <i>kuch meetha</i>, <i>feed 4: 2 veg 2 non-veg under 1500</i> — or send a voice note.\n"
        "I can deliver to your spot, your office, or a friend's place: /address · your cart: /cart\n"
        f"<i>Right now it's {slot} time in Bengaluru.</i>",
        reply_markup=kb.location_request(),
    )
    if not db.get_active_address(m.from_user.id):
        await address_flow.begin_add(m, m.from_user.id, "s")


@router.message(Command("location"))
async def ask_location(m: Message):
    await address_flow.show_book(m, m.from_user.id, "a")


@router.message(Command("cart"))
async def show_cart(m: Message):
    await send_cart(m, m.from_user.id)


@router.message(Command("stats"))
async def admin_stats(m: Message):
    if not is_admin(m.from_user.id, m.chat.id):
        return
    await m.answer(stats.summary_text())


@router.message(Command("orders"))
async def admin_orders(m: Message):
    if not is_admin(m.from_user.id, m.chat.id):
        return
    rows = orders.recent_orders(10)
    if not rows:
        await m.answer("No orders yet.")
        return
    await m.answer("\n".join(f"#{r['id']} · {r['status']} · ₹{r['total']} · {r['created_at']}" for r in rows))


def delivery_header(addr) -> str:
    return f"📍 Delivering to {address_flow.describe(addr)}"


def rec_text(rec: planner.Recommendation) -> str:
    rest = rec.restaurant
    if len(rec.lines) == 1:
        it = rec.item
        spice = "🌶" * it.spice if it.spice else ""
        qty = f" × {rec.lines[0].qty}" if rec.lines[0].qty > 1 else ""
        lines = [f"{DIET_ICON.get(it.diet, '')} <b>{esc(it.name)}</b>{qty} — ₹{rec.subtotal} {spice}".rstrip()]
        if it.description:
            lines.append(f"<i>{esc(it.description)}</i>")
    else:
        lines = [f"🍽 <b>One order, {len(rec.lines)} items</b>"]
        lines += [f"{DIET_ICON.get(ln.item.diet, '')} {ln.qty} × {esc(ln.item.name)} — ₹{ln.amount}" for ln in rec.lines]
        lines.append(f"Subtotal ₹{rec.subtotal} + ₹{rest.delivery_fee} delivery = <b>₹{rec.total}</b>")
    lines.append(f"{esc(rest.name)} · {esc(rest.locality)}")
    lines.append(f"⭐ {rest.rating:.1f} · {rec.distance_km:.1f} km · ⏱ {rec.eta_min}–{rec.eta_max} min")
    if rec.reasons:
        lines.append("✨ " + esc(" · ".join(rec.reasons)))
    return "\n".join(lines)


def _remember_plan(uid: int, rec: planner.Recommendation) -> str:
    token = uuid.uuid4().hex[:10]
    PLANS[token] = (uid, [(ln.item.id, ln.qty) for ln in rec.lines])
    while len(PLANS) > 500:
        PLANS.pop(next(iter(PLANS)))
    return token


async def search_and_show(msg: Message, uid: int, req: FoodRequest, *, text: str | None = None):
    """Plan an answer for the request at the customer's active address and present it."""
    addr = db.get_active_address(uid)
    if not addr:
        await msg.answer("Where should I deliver? Choose or add an address first.", reply_markup=kb.change_address("s"))
        return
    lat, lon = addr["latitude"], addr["longitude"]
    slot = catalogue.current_slot()
    recs = planner.recommend(req, lat, lon, limit=config.MAX_SEARCH_RESULTS, current_slot=slot)
    hints: list[str] = []
    if not recs and req.has_target:
        hints = planner.diagnose(req, lat, lon, current_slot=slot)
        # A constraint that explains the empty result (budget, hours, range, allergen) means the reading was fine;
        # only an unexplained miss (typo, Kannada, odd phrasing) is worth an LLM second opinion.
        if not hints and text and req.source == "rules":
            better = await second_opinion(text, req)
            if better and better.has_target:
                req = better
                recs = planner.recommend(req, lat, lon, limit=config.MAX_SEARCH_RESULTS, current_slot=slot)
                hints = [] if recs else planner.diagnose(req, lat, lon, current_slot=slot)
    if req.has_target:
        LAST_QUERY[uid] = req
    metrics.SEARCHES.inc(result="found" if recs else "empty", source=req.source)
    db.log_event("search", uid, found=len(recs), source=req.source)

    ai = " <i>(AI-assisted)</i>" if req.source == "llm" else ""
    caution = caution_line(req)
    if not recs:
        reply = f"I couldn't find a match for <b>{esc(req.describe())}</b>{ai} delivering to <b>{esc(addr['label'])}</b> right now."
        if hints:
            reply += "\n\n" + "\n".join(f"• {esc(h)}" for h in hints)
        await msg.answer(reply + caution, reply_markup=kb.change_address("s"))
        return

    LAST_SHOWN[uid] = [r.restaurant.id for r in recs]
    understood = f"🧠 {esc(req.describe())}{ai}" if req.has_target else f"🧠 It's {slot} time — popular right now"
    usual = None if req.has_target else orders.usual_for_slot(uid)
    if usual:                                           # "I'm hungry": offer the customer's own habit first
        await msg.answer(usual_line(usual), reply_markup=kb.again(usual.order_id))
    await msg.answer(f"{delivery_header(addr)}\n{understood}{caution}\nTop {len(recs)} option(s):", reply_markup=kb.change_address("s"))
    for rec in recs:
        if len(rec.lines) == 1:
            markup = kb.select(rec.item.id, rec.lines[0].qty)
        else:
            markup = kb.plan_add(_remember_plan(uid, rec), rec.subtotal)
        await msg.answer(rec_text(rec), reply_markup=markup)


async def rerun_last_search(msg: Message, uid: int):
    req = LAST_QUERY.get(uid)
    if req and req.has_target:
        await msg.answer(f"Re-checking “{esc(req.describe())}” for your new address…")
        await search_and_show(msg, uid, req)
    else:
        await msg.answer(f"📍 Delivering to {address_flow.describe(db.get_active_address(uid))}\nWhat would you like to eat?")


def _pretty_slot(slot: str) -> str:
    return {"latenight": "late-night"}.get(slot, slot)


def usual_line(u: orders.Usual) -> str:
    names = ", ".join(f"{k.qty} × {k.name}" if k.qty > 1 else k.name for k in u.plan.kept[:2])
    more = f" +{len(u.plan.kept) - 2} more" if len(u.plan.kept) > 2 else ""
    rest = catalogue.get_restaurant(u.plan.restaurant_id)
    return f"🔁 Your usual {_pretty_slot(u.slot)}: {esc(names)}{more} from {esc(rest.name if rest else '')} (₹{u.plan.subtotal})"


async def greet(msg: Message, uid: int):
    slot = catalogue.current_slot()
    labels = QUICK_PICKS[slot]
    usual = orders.usual_for_slot(uid)
    text = f"👋 Hello! It's {_pretty_slot(slot)} time in Bengaluru. Fancy one of these, or tell me anything else?"
    if usual:
        text += "\n" + usual_line(usual)
    await msg.answer(text, reply_markup=kb.quick_picks(slot, labels, usual.order_id if usual else None,
                                                        f"🔁 Your usual {_pretty_slot(slot)}"))


async def process_text(m: Message, uid: int, text: str):
    """Everything after the per-user state checks: understand the message and act on it."""
    if _REORDER.match(_norm(text)):                      # rules only: never sent to the LLM
        await show_reorder(m, uid)
        return
    req = await understand(text)

    if req.intent == "greeting":
        await greet(m, uid)
        return
    if req.intent == "cart":
        await send_cart(m, uid)
        return
    if req.intent == "address":
        await address_flow.show_book(m, uid, "a")
        return
    if req.intent == "menu" or (req.restaurant and not req.dishes):
        rest = find_restaurant(req.restaurant or "__last__", uid)
        await m.answer(build_menu_text_for_restaurant(rest) if rest else "Which restaurant's menu? Try: <i>show me menu of Darshini</i>.")
        return
    if req.intent == "other" and not req.has_target:
        await m.answer("Happy to help! Tell me what you feel like eating — or /address, /cart.")
        return

    if not db.get_active_address(uid):
        await m.answer("Where should I deliver? Share a pin, type an address, or pick an area.", reply_markup=kb.location_request())
        await address_flow.begin_add(m, uid, "s")
        return
    await search_and_show(m, uid, req, text=text)


def track_text(order) -> str:
    rest = get_restaurant(order["restaurant_id"])
    rider = db.get_courier(order["id"])
    lines = [f"📦 <b>Order #{order['id']}</b> — {esc(rest.name if rest else order['restaurant_id'])}", progress_bar(order["status"])]
    if rider:
        lines.append(f"🛵 {esc(rider['name'])} ({rider['rating']}★) · {esc(rider['vehicle'])}")
        if order["status"] == "OUT_FOR_DELIVERY" and rider["travel_s"]:
            lines.append(f"📍 About <b>{fulfilment.minutes_left(order, rider)} min</b> away — see the live location above")
    if order["status"] in ("PENDING", "ACCEPTED", "PREPARING"):
        lines.append(f"⏱ Estimated delivery {order['eta_min']}–{order['eta_max']} min after acceptance")
    lines.append(f"Deliver to: {esc(order['recipient_name'] or '-')} · {esc(order['address_label'] or '')} — {esc(order['address'] or '')}")
    lines.append(f"Total ₹{order['total']} · cash on delivery")
    if order["rating"]:
        lines.append(f"You rated: {'⭐' * int(order['rating'])}")
    return "\n".join(lines)


async def show_tracking(msg: Message, uid: int):
    rows = orders.orders_of(uid, 5)
    if not rows:
        await msg.answer("You have no orders yet. Tell me what you'd like to eat!")
        return
    order = next((r for r in rows if r["status"] in orders.ACTIVE), rows[0])
    await msg.answer(track_text(order), reply_markup=kb.track(order["id"], order["status"] == "PENDING"))


_TRACK = re.compile(r"^(?:track|where(?:'s| is)? (?:my )?(?:order|food|delivery)|order status|status|track (?:my )?order|my orders?)\b")


@router.message(Command("track"))
async def cmd_track(m: Message):
    db.upsert_user(m.from_user.id, m.from_user.full_name)
    await show_tracking(m, m.from_user.id)


@router.callback_query(F.data.startswith("track:"))
async def cb_track(cb: CallbackQuery):
    order, _ = orders.get_order(int(cb.data.split(":")[1]))
    if not order or order["customer_id"] != cb.from_user.id:
        await cb.answer("Not your order.", show_alert=True)
        return
    await cb.answer("Updated")
    await safe_edit(cb.message, track_text(order), kb.track(order["id"], order["status"] == "PENDING"))


@router.callback_query(F.data.startswith("rate:"))
async def cb_rate(cb: CallbackQuery):
    _, oid, stars = cb.data.split(":")
    try:
        orders.rate_order(int(oid), cb.from_user.id, int(stars))
    except orders.OrderError as e:
        await cb.answer(str(e), show_alert=True)
        return
    await cb.answer("Thanks!")
    await safe_edit(cb.message, f"Thanks for rating order #{oid}: {'⭐' * int(stars)}", kb.again(int(oid)))
    await fulfilment.notify_admins(cb.bot, f"⭐ Order #{oid} was rated {stars}/5 by the customer.")
    await fulfilment.refresh_admin_cards(cb.bot, int(oid))


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

    if user["awaiting"] in address_flow.AWAITING and await address_flow.handle_text(m, user):
        return

    if await address_flow.maybe_handle_intent(m, uid):
        return

    if _TRACK.match(re.sub(r"\s+", " ", m.text.strip().lower()).strip(" ?!.")):
        await show_tracking(m, uid)
        return

    menu_target = detect_menu_request(m.text)
    if menu_target:
        rest = find_restaurant(menu_target, uid)
        if not rest:
            await m.answer("I couldn't find that restaurant. Try: <i>show me menu of Darshini</i>, or search for a dish first.")
            return
        await m.answer(build_menu_text_for_restaurant(rest))
        return

    await process_text(m, uid, m.text)


async def transcribe_voice(bot, voice) -> str | None:
    """Download a Telegram voice note and turn it into text (None if unavailable)."""
    buf = await bot.download(voice.file_id)
    return await default_client().transcribe(buf.read() if buf else b"")


@router.message(F.voice)
async def on_voice(m: Message):
    uid = m.from_user.id
    db.upsert_user(uid, m.from_user.full_name)
    if (m.voice.duration or 0) > 30:
        await m.answer("🎙 Voice notes up to 30 seconds please.")
        return
    text = await transcribe_voice(m.bot, m.voice)
    if not text:
        await m.answer("🎙 I couldn't make that out (or voice is unavailable right now). Please type your order.")
        return
    await m.answer(f"🎙 I heard: <i>“{esc(text[:300])}”</i>")
    await process_text(m, uid, text)


async def download_photo(bot, size) -> bytes:
    """Download one Telegram PhotoSize (a JPEG) into memory. Nothing is written to disk."""
    buf = await bot.download(size.file_id)
    return buf.read() if buf else b""


@router.message(F.photo)
async def on_photo(m: Message):
    """Photo of the food the customer wants: a vision model proposes dishes, the usual boundary disposes (docs/FEATURES-PHOTO.md)."""
    uid = m.from_user.id
    db.upsert_user(uid, m.from_user.full_name)
    caption = (m.caption or "").strip()[:300]
    if caption:                                   # words next to a photo are read by the deterministic rules first
        said = interpret_rules(caption)
        if said.dishes or said.intent in {"cart", "address", "menu"}:
            await process_text(m, uid, caption)   # they already said what they want: no vision call needed
            return
    if not PHOTO_LIMIT.allow(uid):
        await m.answer("📸 One photo at a time, please: give me a few seconds, or just type what you'd like.")
        return
    if not PHOTO_GLOBAL.allow(0):
        await m.answer("📸 I'm reading a lot of photos right now. Try again in a moment, or just type what you'd like.")
        return
    if not db.get_active_address(uid):
        await m.answer("Where should I deliver? Share a pin, type an address, or pick an area, then send the photo again.",
                       reply_markup=kb.location_request())
        await address_flow.begin_add(m, uid, "s")
        return
    client = default_client()
    if not vision.available(client):
        await m.answer("📸 Photo search is unavailable right now. Tell me what you'd like in words and I'll search for that.")
        return

    size = vision.pick_photo_size(m.photo)
    try:
        data = await download_photo(m.bot, size)
        info = vision.inspect_image(data)
    except vision.PhotoError as e:
        await m.answer(f"📸 {esc(str(e))} Please send a different photo, or type what you'd like.")
        return
    except Exception as e:                        # Telegram hiccup while fetching the file
        log.warning("photo download failed: %s", type(e).__name__)
        await m.answer("📸 I couldn't fetch that photo. Please try again, or type what you'd like.")
        return

    req = await vision.describe_photo(data, info.mime, client=client)
    del data                                      # the image is never kept
    if req is None:
        db.log_event("photo", uid, outcome="unavailable")
        await m.answer("📸 I couldn't read that photo right now. Tell me what you'd like in words and I'll search for that.")
        return
    if not req.has_target:
        db.log_event("photo", uid, outcome="unsure")
        await m.answer("📸 I can't tell what food that is, and I'd rather not guess. Tell me in words, e.g. <i>masala dosa under 150</i>.")
        return
    db.log_event("photo", uid, outcome="read", dishes=len(req.dishes))
    seen = req.describe()
    req = vision.with_caption(req, caption)
    await m.answer(f"📸 Looks like: <b>{esc(seen)}</b> <i>(AI-assisted guess)</i>\nNot right? Just type what you'd like and I'll search for that instead.")
    await search_and_show(m, uid, req)


@router.callback_query(F.data.startswith("ask:"))
async def cb_ask(cb: CallbackQuery):
    await cb.answer()
    _, slot, idx = cb.data.split(":")
    picks = QUICK_PICKS.get(slot, [])
    if int(idx) >= len(picks):
        return
    await process_text(cb.message, cb.from_user.id, picks[int(idx)])


@router.callback_query(F.data.startswith("plan:"))
async def cb_plan(cb: CallbackQuery):
    entry = PLANS.get(cb.data.split(":", 1)[1])
    if not entry or entry[0] != cb.from_user.id:
        await cb.answer("That suggestion expired — ask me again.", show_alert=True)
        return
    await cb.answer()
    db.log_event("cart_add", cb.from_user.id, plan=True)
    try:
        replaced = orders.replace_cart(cb.from_user.id, entry[1])
    except orders.OrderError as e:
        await cb.message.answer(f"⚠️ {esc(str(e))}")
        return
    if replaced:
        await cb.message.answer("Replaced your previous cart with this plan.")
    await send_cart(cb.message, cb.from_user.id)


@router.callback_query(F.data == "noop")
async def cb_noop(cb: CallbackQuery):
    await cb.answer()


_REORDER = re.compile(
    r"^(?:please )?(?:"
    r"re-?order|re order|order (?:it |that |this |the same |same )?again|order again please"
    r"|(?:repeat|redo) (?:my |the )?(?:last|previous) order|repeat (?:it|that)"
    r"|same as (?:last time|before|usual)|same again|(?:the |my )?usual"
    r"|(?:order|get me|i want|i'll have|i will have) (?:the |my )?(?:usual|same as last time|same as before)"
    r")$"
)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower().replace("’", "'")).strip(" .!?")


def _digits(part: str, max_len: int = 12) -> int | None:
    """Strict non-negative integer: ASCII digits only (str.isdecimal() also accepts other scripts' digits)."""
    return int(part) if part.isascii() and part.isdigit() and len(part) <= max_len else None


def _parse_again(data: str) -> int | None:
    """`again:<order_id>` -> order id, or None when the callback was not produced by our keyboards."""
    parts = data.split(":")
    if len(parts) != 2:
        return None
    oid = _digits(parts[1])
    return oid if oid else None


def _parse_split(data: str) -> tuple[int, int | None] | None:
    """`split:<order_id>` (ask) or `split:<order_id>:<n>` (answer, n in the offered 2-8) -> (order_id, n | None), else None."""
    parts = data.split(":")
    if len(parts) not in (2, 3):
        return None
    oid = _digits(parts[1])
    if not oid:
        return None
    if len(parts) == 2:
        return oid, None
    n = _digits(parts[2], 2)
    return (oid, n) if n in billing.BUTTON_PEOPLE else None


def _parse_pick(data: str) -> tuple[str, int] | None:
    """`sel:<item>:<qty>` / `swap:<item>:<qty>` -> (item_id, qty), or None when the callback was not produced by our keyboards."""
    parts = data.split(":")
    if len(parts) != 3 or not parts[2].strip().isdecimal():
        return None
    qty = int(parts[2])
    if not 1 <= qty <= orders.MAX_QTY or parts[1] not in catalogue.ITEMS:
        return None
    return parts[1], qty


@router.callback_query(F.data.startswith("sel:"))
async def cb_select(cb: CallbackQuery):
    pick = _parse_pick(cb.data)
    if not pick:
        await cb.answer("That button is no longer valid.", show_alert=True)
        return
    await cb.answer()
    item_id, qty = pick
    it = get_item(item_id)
    if not it or not it.available:
        await cb.message.answer("Sorry, that item is no longer available.")
        return
    db.log_event("cart_add", cb.from_user.id)
    if orders.add_item(cb.from_user.id, item_id, qty) == "conflict":
        await cb.message.answer(
            "Your cart has items from another restaurant. Clear it and start a new cart?",
            reply_markup=kb.swap_cart(item_id, qty),
        )
        return
    await send_cart(cb.message, cb.from_user.id)


@router.callback_query(F.data.startswith("swap:"))
async def cb_swap(cb: CallbackQuery):
    pick = _parse_pick(cb.data)
    if not pick:
        await cb.answer("That button is no longer valid.", show_alert=True)
        return
    await cb.answer()
    try:
        orders.add_item(cb.from_user.id, *pick, replace=True)
    except orders.OrderError as e:
        await cb.message.answer(f"⚠️ {esc(str(e))}")
        return
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
    db.log_event("checkout_start", cb.from_user.id)
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
        await msg.answer("⚠️ " + esc(" ".join((s or {}).get("issues", ["Your cart is empty."]))), reply_markup=kb.change_address("c"))
        return
    key = uuid.uuid4().hex[:16]
    db.set_field(uid, pending_key=key)
    user = db.get_user(uid)
    addr = s["address"]
    text = cart_text(s)
    text += f"\n\nDeliver to: {address_flow.describe(addr)}"
    text += f"\nRecipient: {address_flow.recipient_line(addr, user['name'])}"
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
    db.log_event("order_placed", cb.from_user.id, order_id=oid)
    metrics.ORDERS.inc(status="PENDING")
    order, items = orders.get_order(oid)
    sent = 0
    for admin_id in config.ADMIN_IDS:
        try:
            msg = await cb.bot.send_message(admin_id, admin_card(order, items), reply_markup=kb.admin(oid, "PENDING"))
            db.save_order_message(oid, admin_id, msg.message_id, "admin_card")
            sent += 1
        except Exception as e:
            log.warning("admin notify failed for %s: %s", admin_id, type(e).__name__)
    group = sum(i["quantity"] for i in items) >= 2
    text = f"✅ Order #{oid} placed and sent to the restaurant. Waiting for acceptance."
    if not sent:
        text += "\n⚠️ Could not reach the restaurant admin yet; your order is saved."
    if config.SIMULATE_DELIVERY:
        text += "\n<i>The kitchen and rider here are simulated; /track shows live progress.</i>"
    await cb.message.answer(text, reply_markup=kb.track(oid, can_cancel=True))
    if group:                                            # more than one portion: probably more than one person
        await cb.message.answer("👥 Looks like a group order. Split the bill between how many people?", reply_markup=kb.split_choice(oid))


@router.callback_query(F.data.startswith("ucancel:"))
async def cb_user_cancel(cb: CallbackQuery):
    oid = int(cb.data.split(":")[1])
    order, _ = orders.get_order(oid)
    if not order or order["customer_id"] != cb.from_user.id:
        await cb.answer("Not your order.", show_alert=True)
        return
    try:
        await fulfilment.advance(cb.bot, oid, "CANCELLED", "cancelled by customer", notify=False)
    except orders.OrderError:
        await cb.answer("Too late to cancel here. Please contact the restaurant.", show_alert=True)
        return
    await cb.answer()
    await safe_edit(cb.message, f"Order #{oid} cancelled.")


@router.callback_query(F.data.startswith("adm:"))
async def cb_admin(cb: CallbackQuery):
    if not is_admin(cb.from_user.id, cb.message.chat.id):
        await cb.answer("Unauthorized", show_alert=True)
        return
    _, status, oid = cb.data.split(":")
    try:
        await fulfilment.advance(cb.bot, int(oid), status, "by restaurant operator")
    except orders.OrderError as e:
        await cb.answer(str(e), show_alert=True)
        return
    await cb.answer(status)


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
    reason = kb.REASONS[int(idx)]
    try:
        await fulfilment.advance(cb.bot, int(oid), "REJECTED", reason)
    except orders.OrderError as e:
        await cb.answer(str(e), show_alert=True)
        return
    await cb.answer("Rejected")


# ------------------------------------------------------------------ order again / "the usual"
def _order_summary(order, items) -> str:
    rest = get_restaurant(order["restaurant_id"])
    names = ", ".join(f"{i['quantity']} × {i['item_name']}" for i in items[:3])
    more = f" +{len(items) - 3} more" if len(items) > 3 else ""
    return f"#{order['id']} · {esc(rest.name if rest else order['restaurant_id'])} · {esc(names)}{more} · ₹{order['total']}"


async def show_reorder(msg: Message, uid: int):
    rows = orders.recent_delivered(uid, 3)
    if not rows:
        await msg.answer("You don't have a delivered order to repeat yet. Tell me what you'd like to eat!")
        return
    lines, buttons = [], []
    for o in rows:
        _, items = orders.get_order(o["id"])
        lines.append(_order_summary(o, items))
        rest = get_restaurant(o["restaurant_id"])
        buttons.append((o["id"], f"🔁 #{o['id']} · {(rest.name if rest else '')[:24]} · ₹{o['total']}"))
    text = "🔁 <b>Order again</b> — your last delivered orders:\n\n" + "\n".join(lines)
    text += "\n\n<i>Prices, availability and opening hours are checked again now.</i>"
    usual = orders.usual_for_slot(uid)
    if usual:
        text = usual_line(usual) + "\n\n" + text
    await msg.answer(text, reply_markup=kb.reorder_choices(buttons))


@router.message(Command("reorder"))
async def cmd_reorder(m: Message):
    db.upsert_user(m.from_user.id, m.from_user.full_name)
    await show_reorder(m, m.from_user.id)


@router.callback_query(F.data.startswith("again:"))
async def cb_again(cb: CallbackQuery):
    oid = _parse_again(cb.data)
    if oid is None:
        await cb.answer("That button is no longer valid.", show_alert=True)
        return
    try:
        plan, replaced = orders.reorder(cb.from_user.id, oid)      # refuses another customer's order
    except orders.OrderError as e:
        await cb.answer(str(e), show_alert=True)
        return
    await cb.answer()
    db.log_event("reorder", cb.from_user.id, order_id=oid, kept=len(plan.kept), dropped=len(plan.dropped))
    if plan.blocked:
        await cb.message.answer(f"⚠️ Can't repeat order #{oid}: {esc(plan.blocked)}")
        return
    if not plan.kept:
        await cb.message.answer(f"⚠️ None of the items from order #{oid} are available right now.")
        return
    note = f"🔁 Added the items from order #{oid} at today's prices."
    if plan.dropped:
        note += "\nNot added: " + "; ".join(f"{esc(d.name)} ({esc(d.reason)})" for d in plan.dropped)
    if replaced:
        note += "\nThis replaced your previous cart."
    await cb.message.answer(note)
    await send_cart(cb.message, cb.from_user.id)


# ------------------------------------------------------------------ split the bill
@router.callback_query(F.data.startswith("split:"))
async def cb_split(cb: CallbackQuery):
    parsed = _parse_split(cb.data)
    if not parsed:
        await cb.answer("That button is no longer valid.", show_alert=True)
        return
    oid, people = parsed
    order, _ = orders.get_order(oid)
    if not order or order["customer_id"] != cb.from_user.id:
        await cb.answer("Not your order.", show_alert=True)
        return
    if order["status"] in ("CANCELLED", "REJECTED"):
        await cb.answer("That order wasn't placed, so there's nothing to split.", show_alert=True)
        return
    await cb.answer()
    if people is None:
        await cb.message.answer("🧾 Split between how many people?", reply_markup=kb.split_choice(oid))
        return
    rest = get_restaurant(order["restaurant_id"])
    db.log_event("split_bill", cb.from_user.id, order_id=oid, people=people)
    await cb.message.answer(billing.format_split(oid, rest.name if rest else order["restaurant_id"],
                                                 order["total"], people, order["delivery_fee"]))
