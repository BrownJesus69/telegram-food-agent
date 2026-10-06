import pandas as pd
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
RESTAURANTS_FILE = BASE_DIR / "restaurants_clean.csv"
OUT_FILE = BASE_DIR / "menu.csv"

DEFAULT_TAX_RATE = 0.05
DEFAULT_CURRENCY = "INR"

TEMPLATES = {
    "biryani": [
        ("Chicken Biryani", "Classic chicken dum biryani", "Main Course", 0, 189, 25),
        ("Veg Biryani", "Fragrant basmati rice with vegetables", "Main Course", 1, 149, 20),
        ("Paneer Biryani", "Paneer biryani with aromatic spices", "Main Course", 1, 169, 22),
        ("Chicken Kebab", "Juicy grilled chicken kebab", "Sides", 0, 129, 18),
        ("Raita", "Cooling curd accompaniment", "Sides", 1, 39, 5),
    ],
    "kebab": [
        ("Chicken Shawarma", "Classic chicken shawarma wrap", "Main Course", 0, 129, 15),
        ("Chicken Kebab Plate", "Chargrilled kebab platter", "Main Course", 0, 179, 20),
        ("Paneer Roll", "Paneer wrap with sauces", "Main Course", 1, 119, 15),
        ("French Fries", "Crispy salted fries", "Sides", 1, 79, 10),
        ("Mint Mayo Dip", "Creamy mint dip", "Sides", 1, 25, 3),
    ],
    "pizza": [
        ("Margherita Pizza", "Classic cheese pizza", "Main Course", 1, 199, 20),
        ("Farmhouse Pizza", "Veg-loaded farmhouse pizza", "Main Course", 1, 259, 22),
        ("Chicken Tikka Pizza", "Chicken tikka pizza", "Main Course", 0, 299, 24),
        ("Garlic Bread", "Toasted garlic bread", "Sides", 1, 109, 12),
        ("Choco Lava Cake", "Warm chocolate dessert", "Dessert", 1, 99, 10),
    ],
    "burger": [
        ("Veg Burger", "Crispy veg burger", "Main Course", 1, 129, 12),
        ("Chicken Burger", "Juicy chicken burger", "Main Course", 0, 159, 14),
        ("Paneer Burger", "Paneer patty burger", "Main Course", 1, 149, 13),
        ("Fries", "Golden crispy fries", "Sides", 1, 79, 10),
        ("Coke", "Chilled soft drink", "Beverages", 1, 49, 2),
    ],
    "dosa": [
        ("Masala Dosa", "Crispy dosa with potato masala", "Main Course", 1, 99, 15),
        ("Plain Dosa", "Classic dosa", "Main Course", 1, 79, 12),
        ("Idli Vada Combo", "Idli and vada with sambar", "Main Course", 1, 89, 10),
        ("Filter Coffee", "South Indian filter coffee", "Beverages", 1, 39, 5),
        ("Ghee Podi Dosa", "Dosa with podi and ghee", "Main Course", 1, 129, 16),
    ],
    "chinese": [
        ("Veg Fried Rice", "Wok-tossed fried rice", "Main Course", 1, 139, 18),
        ("Chicken Fried Rice", "Chicken fried rice", "Main Course", 0, 169, 18),
        ("Veg Noodles", "Hakka noodles with vegetables", "Main Course", 1, 149, 18),
        ("Chicken Noodles", "Chicken hakka noodles", "Main Course", 0, 179, 18),
        ("Gobi Manchurian", "Crispy gobi in Manchurian sauce", "Sides", 1, 159, 16),
    ],
    "cafe": [
        ("Cappuccino", "Freshly brewed cappuccino", "Beverages", 1, 119, 8),
        ("Cold Coffee", "Chilled coffee beverage", "Beverages", 1, 139, 8),
        ("Veg Sandwich", "Grilled veg sandwich", "Main Course", 1, 149, 12),
        ("Pasta Alfredo", "Creamy alfredo pasta", "Main Course", 1, 199, 18),
        ("Brownie", "Chocolate brownie", "Dessert", 1, 99, 6),
    ],
    "juice": [
        ("Mango Juice", "Fresh mango juice", "Beverages", 1, 89, 5),
        ("Watermelon Juice", "Refreshing watermelon juice", "Beverages", 1, 79, 5),
        ("Banana Shake", "Creamy banana shake", "Beverages", 1, 99, 6),
        ("Fruit Bowl", "Seasonal fruit bowl", "Dessert", 1, 119, 6),
        ("Lime Soda", "Sweet and salted lime soda", "Beverages", 1, 59, 4),
    ],
    "bakery": [
        ("Veg Puff", "Flaky veg puff", "Snacks", 1, 35, 4),
        ("Chicken Puff", "Flaky chicken puff", "Snacks", 0, 45, 4),
        ("Black Forest Pastry", "Chocolate pastry slice", "Dessert", 1, 85, 5),
        ("Tea", "Hot tea", "Beverages", 1, 25, 3),
        ("Coffee", "Hot coffee", "Beverages", 1, 30, 3),
    ],
    "default": [
        ("Veg Meal", "Balanced vegetarian meal", "Main Course", 1, 149, 20),
        ("Chicken Meal", "Complete chicken meal", "Main Course", 0, 189, 22),
        ("Paneer Starter", "Paneer starter", "Sides", 1, 129, 16),
        ("Soft Drink", "Chilled beverage", "Beverages", 1, 49, 2),
        ("Dessert Cup", "Chef special dessert", "Dessert", 1, 89, 8),
    ],
}

KEYWORDS = {
    "biryani": ["biryani", "donne", "behrouz", "manda", "pilaf", "pulao"],
    "kebab": ["kebab", "kabab", "shawarma", "grill", "tandoor", "rolls", "wrap"],
    "pizza": ["pizza", "pizzeria"],
    "burger": ["burger", "burgers"],
    "dosa": ["dosa", "idli", "udupi", "darshini", "south indian"],
    "chinese": ["chinese", "noodle", "noodles", "fried rice", "manchurian", "asian"],
    "cafe": ["cafe", "coffee", "espresso", "bistro"],
    "juice": ["juice", "smoothie", "shake"],
    "bakery": ["bakery", "bake", "patisserie", "pastry"],
}


def clean_text(v):
    if pd.isna(v):
        return ""
    return str(v).strip()


def infer_template(name, category, cuisine):
    hay = " ".join([clean_text(name), clean_text(category), clean_text(cuisine)]).lower()
    hay = re.sub(r'[^a-z0-9\s,&-]', ' ', hay)
    hay = re.sub(r'\s+', ' ', hay).strip()

    for template, words in KEYWORDS.items():
        for w in words:
            if w in hay:
                return template
    return "default"


def price_adjustment(name, category, cuisine):
    hay = " ".join([clean_text(name), clean_text(category), clean_text(cuisine)]).lower()
    premium_words = ["premium", "royal", "grand", "bbq", "barbeque", "signature", "express", "lounge"]
    budget_words = ["mess", "canteen", "darshini", "cafe", "juice", "bakery"]

    if any(w in hay for w in premium_words):
        return 1.15
    if any(w in hay for w in budget_words):
        return 0.90
    return 1.00


def main():
    if not RESTAURANTS_FILE.exists():
        raise FileNotFoundError(f"Missing file: {RESTAURANTS_FILE}")

    restaurants = pd.read_csv(RESTAURANTS_FILE)
    for col in ["restaurant_id", "name", "category", "cuisine"]:
        if col not in restaurants.columns:
            restaurants[col] = ""

    rows = []
    item_counter = 1

    for _, r in restaurants.iterrows():
        restaurant_id = clean_text(r.get("restaurant_id"))
        restaurant_name = clean_text(r.get("name"))
        category = clean_text(r.get("category"))
        cuisine = clean_text(r.get("cuisine"))

        if not restaurant_id or not restaurant_name:
            continue

        template = infer_template(restaurant_name, category, cuisine)
        multiplier = price_adjustment(restaurant_name, category, cuisine)
        items = TEMPLATES.get(template, TEMPLATES["default"])

        for item_name, desc, menu_category, veg, price, prep in items:
            adjusted_price = int(round(price * multiplier / 5) * 5)
            rows.append({
                "menu_item_id": f"M{item_counter:06d}",
                "restaurant_id": restaurant_id,
                "restaurant_name": restaurant_name,
                "template_used": template,
                "item_name": item_name,
                "item_description": desc,
                "category": menu_category,
                "veg": veg,
                "price": adjusted_price,
                "currency": DEFAULT_CURRENCY,
                "in_stock": 1,
                "prep_minutes": prep,
                "tax_rate": DEFAULT_TAX_RATE,
                "active": 1,
            })
            item_counter += 1

    menu = pd.DataFrame(rows)
    menu.to_csv(OUT_FILE, index=False)
    print(f"Wrote {len(menu)} rows to {OUT_FILE}")
    print(menu.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
