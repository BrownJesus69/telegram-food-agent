"""Delivery addresses: an address book, switching anywhere in the journey, and ordering for someone else.

A customer can keep Home / Office / Friend / custom addresses, add one by dropping a pin, typing an address,
or picking an area, and change the active address from the search results, the cart or the confirm screen.
Each address carries a recipient (name + phone), and an order snapshots the address and recipient it was placed with.
"""
from __future__ import annotations

import html
import logging
import re

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from foodbot import db, geo, geocoding
from foodbot import keyboards as kb
from foodbot.services import catalogue
from foodbot.services.distance import haversine_km

log = logging.getLogger(__name__)
router = Router()
esc = html.escape

AWAITING = {"addr_text", "addr_label", "rcpt_name", "rcpt_phone"}


def _handlers():
    from foodbot import handlers  # late import: handlers imports this module for text routing
    return handlers


# ----------------------------------------------------------------------------- views
def describe(addr) -> str:
    """One-line description used in headers and the confirm screen."""
    return f"{kb.label_icon(addr['label'])} <b>{esc(addr['label'])}</b> — {esc(addr['address'])}"


def recipient_line(addr, fallback_name=None) -> str:
    name = addr["recipient_name"] or fallback_name or "you"
    phone = f" · {esc(addr['recipient_phone'])}" if addr["recipient_phone"] else ""
    return f"{esc(name)}{phone}"


async def show_book(msg: Message, uid: int, ctx: str = "a", edit: bool = False):
    addrs = db.list_addresses(uid)
    active = db.get_active_address(uid)
    if addrs:
        text = "📍 <b>Where should we deliver?</b>\nTap an address to deliver there, or add a new one (home, office, a friend's place…)."
    else:
        text = "📍 You have no saved addresses yet. Add one to start ordering."
    markup = kb.address_book(addrs, active["id"] if active else None, ctx)
    if edit:
        await _handlers().safe_edit(msg, text, markup)
    else:
        await msg.answer(text, reply_markup=markup)


async def begin_add(msg: Message, uid: int, ctx: str):
    db.set_draft(uid, {"ctx": ctx})
    db.set_field(uid, awaiting="addr_text")
    await msg.answer(
        "Send a 📎 <b>location pin</b> (works for anywhere in Bengaluru — even a friend's place), "
        "or <b>type the address or area</b>, e.g. <i>Embassy Tech Village, Bellandur</i>.",
        reply_markup=kb.location_request(),
    )
    await msg.answer("Or pick a popular area:", reply_markup=kb.areas(geocoding.popular_areas(8)))


async def after_switch(msg: Message, uid: int, ctx: str):
    """Return the customer to wherever they were once the active address has changed."""
    h = _handlers()
    if ctx == "c":
        await h.send_cart(msg, uid)
    elif ctx == "k":
        await h.show_confirm(msg, uid)
    elif ctx == "s":
        await h.rerun_last_search(msg, uid)
    else:
        await show_book(msg, uid, "a")


def _nearest_area(lat: float, lon: float) -> str | None:
    best = min(((haversine_km(lat, lon, la, lo), name) for name, (la, lo, _) in catalogue.localities().items()),
               default=None)
    return best[1] if best and best[0] <= 8 else None


# -------------------------------------------------------------------- draft pipeline
async def _ask_label(msg: Message, uid: int, lat: float, lon: float, address: str, precision: str):
    draft = db.get_draft(uid)
    draft.update(lat=lat, lon=lon, address=address, precision=precision)
    db.set_draft(uid, draft)
    db.set_field(uid, awaiting=None)
    note = ""
    if precision == "area":
        note = "\n<i>This is the centre of the area — add a landmark at checkout so the rider can find you.</i>"
    await msg.answer(f"📍 <b>{esc(address)}</b>{note}\n\nWhat should I call this address?", reply_markup=kb.label_choice())


async def _save(msg: Message, uid: int):
    draft = db.get_draft(uid)
    ctx = draft.get("ctx", "s")
    user = db.get_user(uid)
    if draft.get("mode") == "edit":
        db.update_recipient(uid, draft["addr_id"], draft.get("recipient_name"), draft.get("recipient_phone"))
        addr = db.get_address(draft["addr_id"], uid)
        text = f"✅ Recipient updated: {recipient_line(addr)}"
    else:
        aid = db.add_address(
            uid, draft["label"], draft["address"], draft["lat"], draft["lon"],
            draft.get("recipient_name") or (user["name"] if user else None), draft.get("recipient_phone"),
        )
        addr = db.get_address(aid, uid)
        text = f"✅ Saved. Delivering to {describe(addr)}\nRecipient: {recipient_line(addr)}"
    db.set_draft(uid, None)
    db.set_field(uid, awaiting=None)
    await msg.answer(text, reply_markup=ReplyKeyboardRemove())
    await after_switch(msg, uid, ctx)


async def handle_text(m: Message, user) -> bool:
    """Consume free text while an address step is pending. Returns True when the message was used."""
    uid, step, text = m.from_user.id, user["awaiting"], (m.text or "").strip()
    if step not in AWAITING:
        return False
    draft = db.get_draft(uid)

    if step == "addr_text":
        places = await geocoding.search_address(text)
        if not places:
            await m.answer(
                "I couldn't place that inside Bengaluru. Try an area name like <i>Indiranagar</i>, "
                "a landmark with its area, or send a location pin.",
                reply_markup=kb.areas(geocoding.popular_areas(6)),
            )
            return True
        draft["cands"] = [[p.label, p.lat, p.lon, p.precision] for p in places]
        db.set_draft(uid, draft)
        await m.answer("Which one is it?", reply_markup=kb.place_candidates(draft["cands"]))
        return True

    if step == "addr_label":
        label = geocoding.clean_name(text)
        if not label:
            await m.answer("Please send a short name for this address, e.g. <i>Gym</i> or <i>Parents</i>.")
            return True
        draft["label"] = label
        db.set_draft(uid, draft)
        await _save(m, uid)
        return True

    if step == "rcpt_name":
        name = geocoding.clean_name(text)
        if not name:
            await m.answer("Please send the recipient's name (2–40 characters).")
            return True
        draft["recipient_name"] = name
        db.set_draft(uid, draft)
        db.set_field(uid, awaiting="rcpt_phone")
        await m.answer(f"Phone number for {esc(name)}? The rider may call it.", reply_markup=kb.skip_phone())
        return True

    if step == "rcpt_phone":
        phone = geocoding.normalise_phone(text)
        if not phone:
            await m.answer("That doesn't look like an Indian mobile number. Send 10 digits (e.g. 98450 12345) or tap Skip.",
                           reply_markup=kb.skip_phone())
            return True
        draft["recipient_phone"] = phone
        db.set_draft(uid, draft)
        await _save(m, uid)
        return True
    return False


# ----------------------------------------------------------------- natural language
_BOOK = re.compile(r"^(?:please )?(?:change|switch|update|edit|set|manage|show)(?: my)?(?: delivery)?(?: address(?:es)?| location)\b")
_USE = re.compile(r"^(?:please )?(?:deliver|send)(?: it| this| the order| my order)? to (?:my )?(?P<label>home|office|work|[a-z ]{3,30})$")


async def maybe_handle_intent(m: Message, uid: int) -> bool:
    text = re.sub(r"\s+", " ", (m.text or "").strip().lower()).strip(" .!?")
    if _BOOK.match(text) or text in {"addresses", "my addresses", "address", "location"}:
        await show_book(m, uid, "a")
        return True
    hit = _USE.match(text)
    if hit:
        wanted = hit.group("label").strip()
        wanted = "office" if wanted == "work" else wanted
        for a in db.list_addresses(uid):
            if a["label"].lower().startswith(wanted):
                db.set_active_address(uid, a["id"])
                await m.answer(f"📍 Now delivering to {describe(a)}")
                await after_switch(m, uid, "s")
                return True
        await m.answer(f"I don't have a “{esc(wanted)}” address yet — let's add it.")
        await begin_add(m, uid, "s")
        return True
    return False


# --------------------------------------------------------------------- telegram routes
@router.message(Command("address"))
@router.message(Command("addresses"))
async def cmd_address(m: Message):
    db.upsert_user(m.from_user.id, m.from_user.full_name)
    await show_book(m, m.from_user.id, "a")


@router.message(F.location)
async def got_location(m: Message):
    uid = m.from_user.id
    db.upsert_user(uid, m.from_user.full_name)
    lat, lon = m.location.latitude, m.location.longitude
    if not geocoding.in_bengaluru(lat, lon):
        await m.answer(
            "📍 That pin is outside Bengaluru — my restaurants only cover Bengaluru. "
            "Pick a Bengaluru area instead (handy for trying the demo from anywhere):",
            reply_markup=kb.areas(geocoding.popular_areas(8)),
        )
        if not db.get_draft(uid):
            db.set_draft(uid, {"ctx": "s"})
        return
    if not db.get_draft(uid):
        db.set_draft(uid, {"ctx": "s"})
    label = await geo.reverse_geocode(lat, lon)
    if not label:
        area = _nearest_area(lat, lon)
        label = f"Pin near {area}" if area else f"Pin ({lat:.4f}, {lon:.4f})"
    await _ask_label(m, uid, lat, lon, label, "exact")


@router.callback_query(F.data.startswith("addr:book:"))
async def cb_book(cb: CallbackQuery):
    await cb.answer()
    await show_book(cb.message, cb.from_user.id, cb.data.split(":")[2])


@router.callback_query(F.data.startswith("addr:use:"))
async def cb_use(cb: CallbackQuery):
    _, _, aid, ctx = cb.data.split(":")
    if not db.set_active_address(cb.from_user.id, int(aid)):
        await cb.answer("That address no longer exists.", show_alert=True)
        return
    await cb.answer("Delivering there now")
    await after_switch(cb.message, cb.from_user.id, ctx)


@router.callback_query(F.data.startswith("addr:new:"))
async def cb_new(cb: CallbackQuery):
    await cb.answer()
    await begin_add(cb.message, cb.from_user.id, cb.data.split(":")[2])


@router.callback_query(F.data.startswith("addr:area:"))
async def cb_area(cb: CallbackQuery):
    await cb.answer()
    uid, name = cb.from_user.id, cb.data.split(":", 2)[2]
    loc = catalogue.localities().get(name)
    if not loc:
        await cb.message.answer("I don't know that area.")
        return
    if not db.get_draft(uid):
        db.set_draft(uid, {"ctx": "s"})
    await _ask_label(cb.message, uid, loc[0], loc[1], f"{name} (area centre)", "area")


@router.callback_query(F.data.startswith("addr:pick:"))
async def cb_pick(cb: CallbackQuery):
    uid = cb.from_user.id
    cands = db.get_draft(uid).get("cands") or []
    idx = int(cb.data.split(":")[2])
    if idx >= len(cands):
        await cb.answer("That choice expired — type the address again.", show_alert=True)
        return
    await cb.answer()
    label, lat, lon, precision = cands[idx]
    await _ask_label(cb.message, uid, lat, lon, label, precision)


@router.callback_query(F.data.startswith("addr:lbl:"))
async def cb_label(cb: CallbackQuery):
    uid, kind = cb.from_user.id, cb.data.split(":")[2]
    draft = db.get_draft(uid)
    if "lat" not in draft:
        await cb.answer("That step expired — start again with /address.", show_alert=True)
        return
    await cb.answer()
    if kind in ("home", "office"):
        draft["label"] = kind.capitalize()
        db.set_draft(uid, draft)
        await _save(cb.message, uid)
    elif kind == "friend":
        draft["label"] = "Friend"
        db.set_draft(uid, draft)
        db.set_field(uid, awaiting="rcpt_name")
        await cb.message.answer("👥 Who will receive this order? Send their <b>name</b>.")
    else:
        db.set_draft(uid, draft)
        db.set_field(uid, awaiting="addr_label")
        await cb.message.answer("✏️ Send a short name for this address, e.g. <i>Gym</i> or <i>Parents</i>.")


@router.callback_query(F.data == "addr:skipphone")
async def cb_skip_phone(cb: CallbackQuery):
    uid = cb.from_user.id
    if db.get_user(cb.from_user.id)["awaiting"] != "rcpt_phone":
        await cb.answer("Nothing to skip.")
        return
    await cb.answer()
    await _save(cb.message, uid)


@router.callback_query(F.data == "addr:manage")
async def cb_manage(cb: CallbackQuery):
    await cb.answer()
    await _handlers().safe_edit(cb.message, "🗑 Tap an address to remove it.", kb.manage_addresses(db.list_addresses(cb.from_user.id)))


@router.callback_query(F.data.startswith("addr:del:"))
async def cb_delete(cb: CallbackQuery):
    ok = db.delete_address(cb.from_user.id, int(cb.data.split(":")[2]))
    await cb.answer("Removed" if ok else "Already removed")
    await show_book(cb.message, cb.from_user.id, "a", edit=True)


@router.callback_query(F.data.startswith("addr:rcpt:"))
async def cb_recipient(cb: CallbackQuery):
    uid, ctx = cb.from_user.id, cb.data.split(":")[2]
    addr = db.get_active_address(uid)
    if not addr:
        await cb.answer("Choose an address first.", show_alert=True)
        return
    await cb.answer()
    db.set_draft(uid, {"mode": "edit", "addr_id": addr["id"], "ctx": ctx})
    db.set_field(uid, awaiting="rcpt_name")
    await cb.message.answer(f"👤 Who receives orders at {describe(addr)}? Send their <b>name</b>.")


@router.callback_query(F.data == "addr:cancel")
async def cb_cancel(cb: CallbackQuery):
    await cb.answer("Cancelled")
    db.set_draft(cb.from_user.id, None)
    db.set_field(cb.from_user.id, awaiting=None)
    await cb.message.answer("Okay, nothing changed.", reply_markup=ReplyKeyboardRemove())
