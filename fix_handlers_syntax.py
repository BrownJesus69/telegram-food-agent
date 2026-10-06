from pathlib import Path
import shutil
import re

handlers = Path("handlers.py")
if not handlers.exists():
    raise SystemExit("handlers.py not found in current directory")

backup = Path("handlers.py.bak_syntax_fix")
shutil.copy2(handlers, backup)

text = handlers.read_text(encoding="utf-8")

new_func = '''def result_text(r):
    it, rest = r.item, r.restaurant
    veg_label = "Veg" if getattr(it, "veg", False) else "Non-veg"
    lines = [
        f"{it.name} — {rest.name}",
        f"Price: ₹{it.price}",
        f"Rating: {float(getattr(rest, 'rating', 4.0)):.1f}",
        f"Distance: {r.distance_km:.2f} km",
        f"ETA: {r.eta_min}-{r.eta_max} min",
        f"Category: {it.category}",
        f"Type: {veg_label}",
    ]
    return "\\n".join(lines)

'''

pattern = r"def result_text\(r\):.*?(?=\n@|\ndef |\nasync def |\Z)"
if not re.search(pattern, text, flags=re.S):
    raise SystemExit("Could not find result_text(r) function to replace")

text = re.sub(pattern, new_func, text, count=1, flags=re.S)

text = text.replace('r["item"].id', 'r.item.id')
text = text.replace('r["item"]', 'r.item')
text = text.replace('r["rest"]', 'r.restaurant')
text = text.replace('r["restaurant"]', 'r.restaurant')
text = text.replace('r["distance_km"]', 'r.distance_km')
text = text.replace('r["eta_min"]', 'r.eta_min')
text = text.replace('r["eta_max"]', 'r.eta_max')
text = text.replace('r["score"]', 'r.score')
text = text.replace('r.restaurantaurant', 'r.restaurant')
text = text.replace('it, rest = r.item, r.rest', 'it, rest = r.item, r.restaurant')
text = text.replace('it, rest = r.item, r.restaurantaurant', 'it, rest = r.item, r.restaurant')

handlers.write_text(text, encoding="utf-8", newline="\n")

print("handlers.py syntax fixed")
print(f"backup saved to: {backup}")
print("now run: python .\\app.py")