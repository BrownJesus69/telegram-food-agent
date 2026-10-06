"""Deterministic interpreter: text -> FoodRequest. Free, instant, and the first thing tried on every message.

It understands English plus the Hinglish / Kannada words people actually type when ordering in Bengaluru
("ondu masala dose", "kuch meetha", "sasta biryani", "kodi saaru"). The LLM is only consulted when this finds
nothing useful or when its reading returns no results.
"""
from __future__ import annotations

import re
import unicodedata

from foodbot.concierge.intent import FoodRequest, Group

NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "ondu": 1, "oka": 1, "eradu": 2, "yeradu": 2, "mooru": 3, "moru": 3, "nalku": 4, "naalku": 4, "aidu": 5,
    "ek": 1, "do": 2, "teen": 3, "char": 4, "chaar": 4, "paanch": 5, "panch": 5, "couple": 2,
}
_NUM = r"(?:\d{1,2}|" + "|".join(NUMBER_WORDS) + r")"

HI_MARKERS = {"mujhe", "chahiye", "chahie", "bhook", "kuch", "hai", "nahi", "nahin", "jaldi", "sasta", "meetha", "teekha",
              "khana", "khaana", "aur", "mein", "andar", "kam", "paanch", "teen", "chaar", "bhaiya", "yaar", "wala", "wali"}
KN_MARKERS = {"ondu", "eradu", "yeradu", "mooru", "naalku", "nalku", "aidu", "beku", "bekku", "illa", "alla", "hasivu", "dose",
              "kodi", "kaapi", "oota", "tindi", "saaru", "sihi", "khara", "swalpa", "sakkath", "maadi"}

FILLER = set("""
i im am is are was be to a an the and with for of in on at from by it its my me we us you your our please pls plz can could would
should will want wants wanna need needs get give gimme find show order eat have having like love crave craving cravings hungry
hungary something anything somethin food foods dish dishes some any good best tasty yummy delicious nice really very bit little
near nearby around here there now today tonight tomorrow asap quickly fast just also maybe or but so then that this these those
mujhe chahiye chahie hai ho do kuch bhook lagi hain tha thi aur mein se ka ke ki ko yaar bhaiya beku bekku maadi illa alla
hasivu swalpa sakkath one more another plate plates portion portions piece pieces pcs order orders restaurant restaurants place
places hotel hotels delivery deliver delivered home office feed feeds serve serving per person people rich aagide aagthide
aagi ide ittu tell recommend suggest suggestion suggestions choose pick surprise lot lots enough
liye log logon s t what whats which where how kya raining rain rainy weather birthday party extra total date nothing too kids kid children jana
""".split())

# Kannada / Hindi dish words -> catalogue vocabulary
DISH_MAP = {
    "dose": "dosa", "dosey": "dosa", "dosai": "dosa", "idly": "idli", "idlis": "idli", "dosas": "dosa", "vade": "vada", "vadai": "vada",
    "kodi": "chicken", "koli": "chicken", "kozhi": "chicken", "murgh": "chicken", "murg": "chicken", "kaapi": "coffee",
    "kapi": "coffee", "tindi": "tiffin", "oota": "meals", "ooota": "meals", "khana": "meals", "khaana": "meals", "anna": "rice",
    "saaru": "rasam", "meen": "fish", "machli": "fish", "gosht": "mutton", "anda": "egg", "motte": "egg", "masale": "masala",
    "biriyani": "biryani", "briyani": "biryani", "chai": "chai", "parota": "parotta", "paratha": "paratha",
    "momo": "momos", "noodle": "noodles", "chinese": "chinese", "burgers": "burger", "pizzas": "pizza", "sandwiches": "sandwich",
    "samosas": "samosa", "juices": "juice", "shakes": "shake", "cakes": "cake", "puffs": "puff", "rolls": "roll",
    "meetha": "", "sihi": "", "teekha": "", "khara": "", "bhath": "bath", "bhat": "bath",
}

SLOT_WORDS = {
    "breakfast": "breakfast", "brunch": "breakfast", "morning": "breakfast", "tiffin": "breakfast", "nashta": "breakfast",
    "lunch": "lunch", "afternoon": "lunch", "snack": "snack", "snacks": "snack", "evening": "snack",
    "dinner": "dinner", "supper": "dinner", "midnight": "latenight",
    "shaam": "snack", "subah": "breakfast", "dopahar": "lunch", "raat": "dinner",
}
SLOT_PHRASES = {"late night": "latenight", "tea time": "snack", "night time": "dinner", "at night": "dinner", "after midnight": "latenight",
                "2 am": "latenight", "3 am": "latenight", "1 am": "latenight", "12 am": "latenight"}

CUISINE_WORDS = [
    ("south indian", "south indian"), ("north indian", "north indian"), ("indo chinese", "chinese"), ("indo-chinese", "chinese"),
    ("chinese", "chinese"), ("italian", "italian"), ("continental", "continental"), ("arabian", "arabian"), ("arabic", "arabian"),
    ("mughlai", "mughlai"), ("kerala", "kerala"), ("malabar", "kerala"), ("mangalorean", "coastal"), ("coastal", "coastal"),
    ("andhra", "andhra"), ("hyderabadi", "hyderabadi"), ("tibetan", "tibetan"), ("thai", "asian"), ("japanese", "asian"),
    ("korean", "asian"), ("asian", "asian"), ("bengali", "bengali"), ("gujarati", "gujarati"), ("street food", "street food"),
    ("punjabi", "north indian"),
]

TAG_WORDS = {
    "sweet": "sweet", "sweets": "sweet", "dessert": "sweet", "desserts": "sweet", "meetha": "sweet", "sihi": "sweet",
    "healthy": "healthy", "health": "healthy", "diet": "healthy", "fit": "healthy", "gym": "high-protein", "protein": "high-protein",
    "high protein": "high-protein", "light": "light", "comfort": "comfort", "festive": "festive", "kids": "kids-fav",
    "kid": "kids-fav", "child": "kids-fav", "comforting": "comfort", "comfy": "comfort", "bestseller": "bestseller", "popular": "bestseller", "vegan": "vegan",
}

EXCLUDE_WORDS = {
    "onion": "onion-garlic", "onions": "onion-garlic", "garlic": "onion-garlic", "nuts": "nuts", "nut": "nuts", "cashew": "nuts",
    "peanut": "peanut", "peanuts": "peanut", "dairy": "dairy", "milk": "dairy", "lactose": "dairy", "gluten": "gluten",
    "egg": "egg", "eggs": "egg", "cheese": "dairy", "butter": "dairy", "cream": "dairy", "curd": "dairy",
    "ghee": "dairy", "fish": "fish", "seafood": "fish", "shellfish": "fish", "soy": "soy", "sesame": "sesame",
    "cashews": "nuts", "almond": "nuts", "almonds": "nuts", "walnut": "nuts", "walnuts": "nuts", "pistachio": "nuts", "pistachios": "nuts",
    "hazelnut": "nuts", "hazelnuts": "nuts", "wheat": "gluten", "maida": "gluten", "prawn": "fish", "prawns": "fish", "shrimp": "fish",
    "crab": "fish", "lobster": "fish", "squid": "fish",
}
_ALLERGEN_WORDS = "|".join(sorted(EXCLUDE_WORDS, key=len, reverse=True))
# phrases that introduce something the customer cannot or will not have ("no X", "can't eat X", "do not add X", "allergic to X")
EXCLUDE_TRIGGERS = (r"(?:no|without|avoid|skip|minus|free of|allergic to|allergy to|allergic|except|na|intolerant to|sensitive to|stay away from"
                    r"|(?:can'?t|cannot|can not|cant|don'?t|dont|do not|doesn'?t|doesnt|never|won'?t|wont)\s+(?:eat|have|add|take|use|put|want)"
                    r"|not\s+(?:to\s+)?(?:add|use|put))")
_MODIFIERS = r"(?:(?:raw|tree|any|all|the|of|extra|added|dried|fresh|cooked|kind|kinds|type|types|product|products|item|items|anywhere|in|with)\s+){0,2}"


# Things a customer may say that the catalogue cannot enforce (no column for them). The bot must not pretend: it says so.
UNSUPPORTED = {"halal", "kosher", "pork", "beef", "bacon", "ham", "mushroom", "mushrooms", "honey", "sugar", "msg", "mustard", "coconut",
               "tomato", "tomatoes", "brinjal", "capsicum", "coriander", "potato", "potatoes", "oil", "salt"}
HEALTH_CUES = r"\b(?:halal|kosher|diabet\w*|keto|cholesterol|low[- ]sodium|sugar[- ]free|celiac|coeliac)\b"
STRONG_TRIGGER = re.compile(r"(?:allerg|intoleran|sensitive|can'?t|cannot|can not|cant|don'?t|dont|do not|doesn'?t|doesnt|never|won'?t|wont|stay away|avoid)")
_NOT_A_FOOD = {"and", "or", "no", "without", "avoid", "spicy", "spice", "hot", "oily", "heavy", "fried", "sweet", "sweets", "junk", "delay", "late",
               "queue", "rush", "crowd", "severe", "serious", "bad", "mild", "strong", "real", "food", "any", "my", "his", "her", "our", "have", "has", "with", "the", "change", "changes", "issue", "problem", "problems", "trouble", "thing", "things", "stuff", "foods"}


def _unrecognised(word: str) -> bool:
    """A word after 'allergic to' / 'can't eat' that is not an allergen we know: a constraint we cannot apply."""
    return (len(word) > 2 and word not in EXCLUDE_WORDS and word not in FILLER and word not in _NOT_A_FOOD
            and word not in NUMBER_WORDS and word not in TAG_WORDS and word not in SLOT_WORDS)


TOGETHER = {"and", "with", "plus", "mattu", "aur", "saath", "tatha"}
EITHER = {"or", "athava", "ya"}
PLEASANTRIES = {"thanks", "thank", "thx", "you", "ok", "okay", "cool", "great", "bye", "goodbye", "dhanyavad", "dhanyavadagalu",
                "nice", "awesome", "perfect", "fine", "alright", "sure", "yes", "no", "good", "night", "later", "see", "ya"}


def _take(text: str, pattern: str):
    m = re.search(pattern, text)
    if not m:
        return None, text
    return m, text[: m.start()] + " " + text[m.end():]


def _num(tok: str) -> int | None:
    if tok.isdigit():
        return int(tok)
    return NUMBER_WORDS.get(tok)


def _detect_language(tokens: list[str]) -> str:
    hi = sum(t in HI_MARKERS for t in tokens)
    kn = sum(t in KN_MARKERS for t in tokens)
    if hi and kn:
        return "mixed"
    return "hi" if hi else "kn" if kn else "en"


# letters from other alphabets that are indistinguishable from Latin ones (a customer, or a pasted message, can contain them)
_LOOKALIKES = str.maketrans({"а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x", "і": "i", "ѕ": "s", "ј": "j",
                             "ԁ": "d", "һ": "h", "ո": "n", "ν": "v", "ο": "o", "ε": "e", "ι": "i", "α": "a"})
_LEET = {"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "8": "b", "9": "g", "2": "z", "6": "g"}
_WORD_NUMBERS = (("one thousand", 1000), ("two thousand", 2000), ("thousand", 1000), ("nine hundred", 900), ("eight hundred", 800),
                 ("seven hundred", 700), ("six hundred", 600), ("five hundred", 500), ("four hundred", 400), ("three hundred", 300),
                 ("two hundred", 200), ("one hundred", 100), ("hundred", 100), ("seventy five", 75), ("fifty", 50), ("twenty five", 25))


def _normalise(raw: str) -> str:
    """Fold what a reader cannot tell apart: full-width forms, invisible characters, Cyrillic/Greek lookalikes, '1,000', '2k'."""
    s = unicodedata.normalize("NFKC", raw).translate(_LOOKALIKES)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Cf")           # zero-width spaces, joiners, bidi controls
    s = s.lower().replace("’", "'")
    s = re.sub(r"(?<=[a-z])[0-9](?=[a-z])", lambda m: _LEET[m.group(0)], s)           # v3getarian, g1ve: digits *inside* a word only
    s = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", s)                             # 1,000 -> 1000
    s = re.sub(r"\b(\d+(?:\.\d+)?)\s*k\b", lambda m: str(int(float(m.group(1)) * 1000)), s)
    for word, value in _WORD_NUMBERS:
        s = re.sub(rf"\b{word}\b", str(value), s)
    return s


def interpret_rules(raw: str) -> FoodRequest:
    original = raw or ""
    t = " " + re.sub(r"\s+", " ", _normalise(original).replace(",", " , ").replace("&", " and ")) + " "
    t = re.sub(r"\b(?:not|never|no)\s+(?:a\s+)?(?:pure\s+)?veg(?:etarian)?\b(?!\s+(?:alla|nahi|nahin|illa))", "nonveg", t)    # "I'm not vegetarian"
    t = re.sub(r"non[\s-]+veg(?:etarian)?", "nonveg", t)
    t = re.sub(r"\bnon\s*veg\b", "nonveg", t)
    req = FoodRequest(raw=original, source="rules")
    tokens_all = re.findall(r"[a-z]+", t)
    req.language = _detect_language(tokens_all)
    if req.language == "en":
        t = re.sub(r"\bdo\b", " ", t)                    # "do you have thatte idli" is not a request for two
    t = re.sub(r"\bdate night\b", " for two ", t)
    if re.search(r"\b(?:kids?|children)\b", t):
        req.tags.append("kids-fav")

    # --- greeting / other intents --------------------------------------------------------------
    stripped = t.strip(" .!?,")
    if re.fullmatch(r"(?:hi+|hello+|hey+|hola|namaste|namaskara|good (?:morning|afternoon|evening|night)|yo|sup)(?: there| bot)?", stripped):
        req.intent = "greeting"
        return req.clean()
    if stripped and set(re.findall(r"[a-z]+", stripped)) <= PLEASANTRIES:
        req.intent = "other"
        return req.clean()
    if re.fullmatch(r"(?:(?:my|show|view|open|see|check)\s+)*(?:cart|basket)|checkout|check out", stripped):
        req.intent = "cart"
        return req.clean()

    # --- mixed-diet groups: "2 veg and 2 non veg" ----------------------------------------------
    groups: dict[str, int] = {}
    for m in list(re.finditer(rf"\b({_NUM})\s*(nonveg|veg(?:etarian)?)\b", t)):
        n = _num(m.group(1))
        if n:
            diet = "nonveg" if m.group(2) == "nonveg" else "veg"
            groups[diet] = groups.get(diet, 0) + n
    if len(groups) >= 2:
        req.groups = [Group(d, c) for d, c in groups.items()]
        t = re.sub(rf"\b{_NUM}\s*(?:nonveg|veg(?:etarian)?)\b", " ", t)

    # --- exclusions ----------------------------------------------------------------------------
    excl: list[str] = []
    if re.search(r"\b(?:jain|sattvic|satvik|sattvik|satvic)\b", t):
        excl.append("onion-garlic")
        t = re.sub(r"\b(?:jain|sattvic|satvik|sattvik|satvic)\b", " ", t)
    if re.search(r"\bvegan\b", t):                            # vegan is more than "no meat": no milk products either
        excl.append("dairy")
    for m in re.finditer(r"\b(egg|dairy|nut|gluten|lactose)less\b", t):
        excl.append(EXCLUDE_WORDS.get(m.group(1), m.group(1)))
    t = re.sub(r"\b(?:egg|dairy|nut|gluten|lactose)less\b", " ", t)
    cautions: list[str] = [m.group(0) for m in re.finditer(HEALTH_CUES, t)]
    for m in list(re.finditer(rf"\b{EXCLUDE_TRIGGERS}\s+{_MODIFIERS}((?:[a-z]+)(?:\s*(?:,|and|or|&)\s*(?:(?:no|without|avoid)\s+)?{_MODIFIERS}[a-z]+){{0,3}})", t)):
        strong = bool(STRONG_TRIGGER.match(m.group(0)))
        for w in re.findall(r"[a-z]+", m.group(1)):
            if w in EXCLUDE_WORDS:
                excl.append(EXCLUDE_WORDS[w])
            elif w in UNSUPPORTED or (strong and _unrecognised(w)):          # said out loud, but there is no filter for it
                cautions.append(w)
    t = re.sub(rf"\b{EXCLUDE_TRIGGERS}\s+{_MODIFIERS}(?:[a-z]+)(?:\s*(?:,|and|or|&)\s*(?:(?:no|without|avoid)\s+)?(?:{_ALLERGEN_WORDS}))*", " ", t)
    for m in re.finditer(rf"\b({_ALLERGEN_WORDS})[\s-]*(?:allergy|allergic|free|intolerant|intolerance)\b", t):
        excl.append(EXCLUDE_WORDS.get(m.group(1), m.group(1)))
    t = re.sub(rf"\b(?:{_ALLERGEN_WORDS})[\s-]*(?:allergy|allergic|free|intolerant|intolerance)\b", " ", t)
    for m in re.finditer(r"\b([a-z]+)[\s-]*(?:allergy|allergies|intolerance|intolerant)\b", t):        # "sulphite allergy": an allergen we do not model
        if _unrecognised(m.group(1)):
            cautions.append(m.group(1))
    if re.search(r"\ballerg", t) and not excl and not cautions:
        cautions.append("that allergy")
    req.exclude = excl
    req.cautions = cautions

    # --- budget --------------------------------------------------------------------------------
    for pat in (
        r"\b(\d{2,5})\s*(?:per person|per head|each|a head|per plate|pp)\b",
        r"(?:under|below|within|upto|up to|max|maximum|less than|budget(?: of| is)?|around|about|total|only)\s*(?:of\s*)?(?:₹|rs\.?|inr|rupees?)?\s*(\d{2,5})\b",
        r"(?:₹|rs\.?|inr|rupees?)\s*(\d{2,5})\b",
        r"\b(\d{2,5})\s*(?:rs|rupees|rupee|inr|₹|bucks)\b",
        r"\b(\d{2,5})\s*(?:ke andar|se kam|tak|kulla|olage|mein)\b",
    ):
        m, t2 = _take(t, pat)
        if m:
            req.budget = int(m.group(1))
            ctx = t[max(0, m.start() - 12): m.end() + 22]
            t = t2
            if re.search(r"per person|each|a head|per head|pp\b|per plate", ctx):
                req.budget_scope = "per_person"
            elif re.search(r"\btotal|in all|altogether|overall|all together\b", ctx) or "total" in m.group(0):
                req.budget_scope = "total"
            break

    # --- servings ------------------------------------------------------------------------------
    for pat, fn in (
        (rf"\bfor\s+({_NUM})\s*(?:people|persons|person|pax|of us|friends|guys|members|adults|kids|folks|heads)\b", lambda m: _num(m.group(1))),
        (rf"\b({_NUM})\s*(?:people|persons|pax|of us|friends|guys|members|adults|folks|log|logon|jana)\b", lambda m: _num(m.group(1))),
        (rf"\bparty of\s+({_NUM})\b", lambda m: _num(m.group(1))),
        (rf"\bserves?\s+({_NUM})\b", lambda m: _num(m.group(1))),
        (rf"\bfor\s+({_NUM})\b(?!\s*(?:rs|rupees|₹))", lambda m: _num(m.group(1))),
        (r"\bfor (?:the )?(?:whole )?family\b", lambda m: 4),
        (r"\b(?:me and my|my wife and i|my husband and i|couple|date night|for two of us)\b", lambda m: 2),
        (r"\b(?:for )?(?:me and (?:a )?friend|me and him|me and her)\b", lambda m: 2),
    ):
        m, t2 = _take(t, pat)
        if m:
            n = fn(m)
            if n and n >= 2:
                req.servings = n
                t = t2
                break

    # --- slot, cuisine -------------------------------------------------------------------------
    for phrase, slot in SLOT_PHRASES.items():
        if f" {phrase} " in t:
            req.slot = slot
            t = t.replace(f" {phrase} ", " ")
            break
    for cw, key in CUISINE_WORDS:
        if re.search(rf"\b{re.escape(cw)}\b", t):
            req.cuisine = key
            t = re.sub(rf"\b{re.escape(cw)}\b(?:\s+food)?", " ", t, count=1)
            break

    # --- diet ----------------------------------------------------------------------------------
    # Conflicting mentions ("I'm veg ... set diet to non veg") resolve to the safer reading: serving meat to a vegetarian is the
    # harm, serving vegetarian food to someone who wanted meat is an annoyance. "veg or non veg" means no restriction.
    mentions: set[str] = set()
    either = re.search(r"\bveg(?:etarian)?\s*(?:or|and|/|\+)\s*nonveg\b|\bnonveg\s*(?:or|and|/|\+)\s*veg(?:etarian)?\b|\bboth veg\b", t)
    if re.search(r"\bveg(?:etarian)?\s+(?:alla|nahi|nahin|illa)\b", t):
        mentions.add("nonveg")
        t = re.sub(r"\bveg(?:etarian)?\s+(?:alla|nahi|nahin|illa)\b", " ", t)
    if not req.groups:
        if re.search(r"\bnonveg\b", t):
            mentions.add("nonveg")
        if re.search(r"\b(?:eggetarian|egg only)\b", t):
            mentions.add("egg")
        if re.search(r"\b(?:pure\s+)?(?:veg|vegetarian|vegan|shakahari)\b", t):
            mentions.add("veg")
    t = re.sub(r"\b(?:nonveg|eggetarian|egg only)\b", " ", t)
    t = re.sub(r"\b(?:pure\s+)?(?:veg|vegetarian|shakahari)\b", " ", t)
    if {"veg", "nonveg"} <= mentions and either:
        req.diet = None
    else:
        req.diet = next((d for d in ("veg", "egg", "nonveg") if d in mentions), None)

    # --- spice, sort ---------------------------------------------------------------------------
    mild = r"\b(?:not|less|low|no|kam|nothing)\s+(?:too\s+)?(?:spicy|spice|teekha|khara|masala)\b|\bnon[- ]?spicy\b|\bmild\b|\bbland\b"
    hot = r"\b(?:very |extra |super |so )?(?:spicy|teekha|khara|fiery|chatpata)\b|\b(?:very|extra|super) hot\b"
    if re.search(mild, t):
        req.spice = "mild"
        t = re.sub(mild, " ", t)
    elif re.search(hot, t):
        req.spice = "hot"
        t = re.sub(hot, " ", t)
    elif re.search(r"\bmedium (?:spicy|spice)\b", t):
        req.spice = "medium"
        t = re.sub(r"\bmedium (?:spicy|spice)\b", " ", t)
    for pat, key in (
        (r"\b(?:cheapest|cheap|sasta|budget friendly|economical|affordable|low cost|lowest price)\b", "cheapest"),
        (r"\b(?:fastest|quick|quickly|jaldi|urgent|urgently|asap|in a hurry|fast delivery|hurry|immediately)\b", "fastest"),
        (r"\b(?:top rated|best rated|highest rated|best reviewed|top)\b", "top_rated"),
        (r"\b(?:nearest|closest|near me)\b", "nearest"),
    ):
        if re.search(pat, t):
            if req.sort == "relevance":
                req.sort = key                  # first match wins, but every sort word is stripped from the dish text
            t = re.sub(pat, " ", t)

    # --- tags & slot words ---------------------------------------------------------------------
    tags = list(req.tags)                         # keeps tags found earlier (kids)
    for phrase in ("high protein", "street food"):
        if f" {phrase} " in t:
            tags.append("street-food" if phrase == "street food" else "high-protein")
            t = t.replace(f" {phrase} ", " ")
    words = re.findall(r"[a-z]+", t)
    keep = []
    for w in words:
        if w in TAG_WORDS and not (w == "diet" and req.diet):
            tags.append(TAG_WORDS[w])
        elif w in SLOT_WORDS and w not in ("tiffin", "tindi"):
            req.slot = req.slot or SLOT_WORDS[w]
        elif w in ("tiffin", "tindi"):
            req.slot = req.slot or "breakfast"
            keep.append(w)
        else:
            keep.append(w)
    if "vegan" in tags and not req.diet:
        req.diet = "veg"
    req.tags = [x for x in dict.fromkeys(tags)]

    # --- quantity ------------------------------------------------------------------------------
    lead = re.search(rf"(?<![\w])({_NUM})\b(?=\s+[a-z])", t)
    if lead and req.servings == 1:
        n = _num(lead.group(1))
        if n and n <= 10:
            req.quantity = n

    # --- dishes --------------------------------------------------------------------------------
    cleaned = " ".join(keep)
    # split on connectors into phrases; "and"/"with"/"plus" means "together", "or" means "either"
    raw_parts = re.split(r"\b(and|with|plus|or|mattu|aur|saath|tatha|athava|ya)\b|\+|\|", " " + re.sub(r"\s+", " ", t) + " ")
    phrases, connectors = [], []
    for part in raw_parts:
        if part in TOGETHER | EITHER:
            connectors.append(part)
            continue
        if part is None:
            continue
        toks = []
        for w in re.findall(r"[a-z]+", part):
            if w in NUMBER_WORDS and (w != "do"):
                continue
            if w in FILLER or w in TAG_WORDS or w in SLOT_WORDS and w != "tiffin" or w in {"veg", "nonveg"}:
                continue
            if w in EXCLUDE_WORDS and EXCLUDE_WORDS[w] in req.exclude:      # only words that were *excluded*; 'prawn biryani, no onion' keeps the prawn
                continue
            mapped = DISH_MAP.get(w, w)
            if mapped:
                toks.append(mapped)
        phrase = " ".join(toks).strip()
        if phrase and len(phrase) > 1:
            phrases.append(phrase)
    del cleaned
    if phrases:
        req.dishes = phrases[:4]
        req.combine = len(phrases) >= 2 and any(c in TOGETHER for c in connectors) and not any(c in EITHER for c in connectors)
    return req.clean()
