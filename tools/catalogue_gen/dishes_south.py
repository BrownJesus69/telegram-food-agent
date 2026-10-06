"""Karnataka, Andhra, Kerala, coastal and Tamil-style dishes."""
from tools.catalogue_gen.dsl import block

DISHES = []

# ---------------------------------------------------------------- tiffin
DISHES += block("Breakfast & Tiffin", "tiffin", [
    ("Idli (2 pcs)", "v", 50, 8, "bsd", 0, 140, "Steamed rice-lentil cakes with sambar and two chutneys", "idly|idli sambar", "jain|light|bestseller"),
    ("Thatte Idli", "v", 70, 10, "bs", 0, 220, "Large flat Bangalore-style plate idli with chutney and sambar", "plate idli|thatte idly", "must-try"),
    ("Button Idli with Ghee", "v", 80, 10, "bs", 1, 260, "Mini idlis tossed in ghee and idli podi", "mini idli|podi idli", "kids-fav"),
    ("Rava Idli", "v", 70, 10, "bs", 1, 230, "Soft semolina idli with cashew and coriander", "", ""),
    ("Medu Vada (2 pcs)", "v", 60, 10, "bs", 1, 280, "Crisp lentil doughnuts with sambar and chutney", "uddina vade|vada sambar|medhu vada", "bestseller"),
    ("Idli Vada Combo", "v", 80, 10, "bs", 1, 330, "One idli and one vada with sambar", "idli vada", "bestseller"),
    ("Sambar Vada", "v", 70, 10, "bs", 1, 300, "Vada soaked in hot sambar", "vada sambar", ""),
    ("Curd Vada", "v", 75, 8, "bsl", 0, 290, "Vada in chilled spiced curd", "dahi vada|mosaru vade", ""),
    ("Plain Dosa", "v", 60, 10, "bsd", 0, 170, "Thin crisp rice-lentil crepe with chutney and sambar", "sada dosa|dose", ""),
    ("Masala Dosa", "v", 90, 12, "bsdn", 1, 330, "Crisp dosa stuffed with spiced potato masala", "masale dose|masala dose|mysore masala", "bestseller"),
    ("Set Dosa (3 pcs)", "v", 85, 10, "bsd", 0, 360, "Three soft spongy dosas served with vegetable saagu", "set dose|saagu dosa", "must-try"),
    ("Benne Masala Dosa", "v", 110, 14, "bs", 1, 420, "Davangere-style butter roast dosa with potato palya", "davangere benne dose|butter dosa|benne dose", "must-try|bestseller"),
    ("Ghee Podi Dosa", "v", 105, 12, "bsd", 2, 380, "Dosa roasted in ghee with spicy gunpowder", "podi dosa|ghee roast|gun powder dosa", ""),
    ("Mysore Masala Dosa", "v", 105, 13, "bsd", 2, 370, "Dosa with red chutney spread and potato masala", "mysore dosa", "bestseller"),
    ("Paper Dosa", "v", 95, 12, "bs", 0, 240, "Extra-large paper-thin crispy dosa", "paper roast", ""),
    ("Rava Dosa", "v", 95, 12, "bsd", 1, 310, "Lacy crispy semolina dosa with onion and chillies", "onion rava dosa|rava dose", ""),
    ("Onion Uttapam", "v", 90, 12, "bsd", 1, 300, "Thick pancake topped with onions and green chillies", "uttappa|uthappam|onion oothappam", ""),
    ("Tomato Onion Uttapam", "v", 95, 12, "bsd", 1, 310, "Thick pancake with tomato, onion and coriander", "", ""),
    ("Neer Dosa with Coconut Chutney", "v", 90, 12, "bs", 0, 230, "Delicate rice-batter lace dosas, three pieces", "neer dose", ""),
    ("Akki Rotti", "v", 85, 12, "bs", 1, 260, "Rice-flour flatbread with onion, dill and coconut", "akki roti|rice roti", ""),
    ("Ragi Rotti", "v", 85, 12, "bs", 1, 240, "Finger-millet flatbread with onion and coriander", "ragi roti|ragi dose", "healthy|light"),
    ("Ragi Dosa", "v", 85, 12, "bsd", 0, 190, "Finger-millet dosa with coconut chutney", "ragi dose", "healthy|light"),
    ("Pesarattu", "v", 85, 12, "bs", 1, 250, "Andhra green-gram dosa with ginger chutney", "pesara dosa|green gram dosa", "healthy|high-protein"),
    ("Upma", "v", 55, 8, "bs", 0, 240, "Savoury semolina porridge with cashews", "uppittu|rava upma", "light"),
    ("Khara Bath", "v", 60, 8, "bs", 1, 250, "Spiced semolina upma with vegetables", "khara bhath|kharabath", "bestseller"),
    ("Kesari Bath", "v", 55, 8, "bs", 0, 320, "Saffron-coloured sweet semolina with ghee", "kesari bhath|rava kesari|sheera", "sweet"),
    ("Chow Chow Bath", "v", 90, 8, "bs", 1, 560, "Half khara bath, half kesari bath, the classic Bangalore combo", "chow chow bhath|chowchow bath", "must-try|bestseller"),
    ("Ven Pongal", "v", 70, 10, "bs", 1, 330, "Creamy rice-lentil porridge with pepper and ghee", "pongal|huggi", "comfort"),
    ("Pongal Vada Combo", "v", 95, 10, "bs", 1, 560, "Ven pongal with a crisp medu vada", "", ""),
    ("Poori Saagu (3 pcs)", "v", 85, 12, "bs", 1, 480, "Fluffy puris with potato-vegetable saagu", "poori bhaji|puri saagu|puri sagu", "bestseller"),
    ("Chapati Saagu", "v", 80, 10, "bsd", 1, 420, "Two soft chapatis with vegetable saagu", "chapathi saagu", ""),
    ("Avalakki Uppittu", "v", 60, 8, "bs", 1, 260, "Flattened-rice upma with peanuts and curry leaves", "poha|avalakki|avalakki bath", "light"),
    ("Menthe Bath", "v", 65, 8, "bs", 1, 270, "Fenugreek-flavoured semolina bath", "", ""),
    ("Maddur Vada (2 pcs)", "v", 55, 10, "s", 1, 300, "Crisp onion-semolina fritters from Maddur", "maddur vade", "must-try|street-food"),
    ("Thatte Idli with Ghee Podi", "v", 90, 10, "bs", 2, 300, "Thatte idli smothered in ghee and spiced podi", "", ""),
    ("Bonda Soup", "v", 70, 10, "sd", 1, 310, "Lentil bondas in a hot coconut-coriander broth", "bonda soup|bonda sambar", "comfort"),
    ("Mangalore Bonda (3 pcs)", "v", 60, 8, "s", 0, 300, "Soft fried maida-yogurt fritters with chutney", "goli baje|mangalore buns bonda", ""),
])

# --------------------------------------------------------- south rice bowls
DISHES += block("Rice & Bath", "ricebowl_south,meals_light", [
    ("Bisi Bele Bath", "v", 95, 10, "bld", 1, 420, "Spicy lentil-rice one-pot with vegetables, ghee and boondi", "bisibelebath|bisi bele bhath", "must-try|bestseller|comfort"),
    ("Vangi Bath", "v", 85, 10, "bld", 2, 400, "Brinjal-spiced rice with roasted masala", "vangibath|brinjal rice", ""),
    ("Tomato Bath", "v", 80, 10, "bld", 1, 390, "Tangy tomato rice with cashews", "tomato rice|tomato bhath", ""),
    ("Lemon Rice", "v", 75, 8, "bld", 0, 350, "Tempered turmeric lemon rice with peanuts", "chitranna|nimbe rice", "vegan|jain|bestseller"),
    ("Puliyogare", "v", 85, 8, "bld", 1, 380, "Tamarind rice with peanuts and sesame", "puliogare|tamarind rice|huli anna", "vegan"),
    ("Curd Rice", "v", 75, 6, "bld", 0, 320, "Cooling yoghurt rice with pomegranate and mustard tempering", "mosaranna|dahi rice|thayir sadam", "comfort|light"),
    ("Coconut Rice", "v", 80, 8, "bld", 0, 380, "Rice tossed with fresh coconut and cashew", "thengai sadam", ""),
    ("Jeera Rice with Dal", "v", 110, 12, "ld", 0, 480, "Cumin rice served with tadka dal", "", ""),
    ("Sambar Rice", "v", 95, 8, "ld", 1, 410, "Rice mixed with piping-hot sambar and ghee", "sambar sadam", "comfort"),
    ("Rasam Rice", "v", 90, 8, "ld", 1, 340, "Rice with peppery tomato rasam", "rasam anna", "comfort|light"),
    ("Pulao with Raita", "v", 120, 12, "ld", 1, 450, "Vegetable pulao with cucumber raita", "veg pulao|pulav", ""),
])

# ---------------------------------------------------------- karnataka meals
DISHES += block("Meals & Thali", "meals", [
    ("Karnataka Meals (Unlimited)", "v", 190, 15, "l", 1, 900, "Rice, sambar, rasam, two palyas, kosambari, payasa, curd, pickle and papad", "full meals|south indian meals|oota|meals", "bestseller|must-try"),
    ("Mini Meals", "v", 130, 12, "ld", 1, 650, "Rice, sambar, rasam, one palya, curd and sweet", "mini oota", ""),
    ("Ragi Mudde with Soppu Saaru", "v", 140, 15, "ld", 1, 520, "Finger-millet balls with greens curry", "ragi ball|ragi mudde|mudde saaru", "healthy|must-try"),
    ("Ragi Mudde with Chicken Curry", "n", 210, 20, "ld", 2, 680, "Finger-millet balls with country chicken curry", "mudde chicken|nati kodi saaru mudde", "must-try"),
    ("Jolada Rotti Oota", "v", 150, 15, "ld", 2, 560, "North-Karnataka sorghum rotti with ennegayi brinjal and chutneys", "jowar roti meals|jolada rotti|north karnataka oota", "must-try"),
    ("Ennegayi Palya", "v", 110, 12, "ld", 2, 280, "Stuffed baby brinjals in a peanut-coconut masala", "ennegai|stuffed brinjal", ""),
    ("Hesarubele Kosambari", "v", 60, 5, "ls", 0, 130, "Moong dal and cucumber salad with coconut", "kosambari|kosambri", "vegan|light"),
    ("Holige Oota", "v", 160, 15, "l", 0, 700, "Obbattu with ghee and coconut milk, served with a small meal", "obbattu meals", "festive"),
    ("South Indian Thali", "v", 210, 15, "ld", 1, 950, "Rice, two curries, kootu, sambar, rasam, poriyal, appalam and payasam", "south thali|tamil meals|chettinad veg meals", ""),
    ("Curd Rice and Pickle Combo", "v", 95, 6, "ld", 0, 360, "Curd rice with mango pickle and fried chillies", "", "light"),
])

# ------------------------------------------------------- military / nati style
DISHES += block("Nati Style Specials", "military", [
    ("Nati Koli Saaru (Country Chicken Curry)", "n", 280, 25, "ld", 3, 520, "Country-chicken curry cooked with roasted coconut and masala", "nati chicken|nati kodi|koli saaru", "must-try|bestseller"),
    ("Mutton Pulao", "n", 290, 25, "ld", 2, 710, "Bangalore military-hotel style mutton pulao with raita", "military pulao|mutton pulav", "bestseller"),
    ("Mutton Kheema Ball Curry", "n", 290, 25, "ld", 2, 560, "Mutton kheema balls in a thick coconut gravy", "kheema unde|kheema ball", ""),
    ("Mutton Chops Fry", "n", 330, 25, "ld", 3, 540, "Pepper-roasted mutton chops", "chops", ""),
    ("Chicken Pepper Fry", "n", 240, 20, "ld", 3, 420, "Dry chicken fry with crushed black pepper", "pepper chicken", "bestseller"),
    ("Chicken Sukka", "n", 250, 20, "ld", 3, 430, "Dry-roasted chicken in coconut-chilli masala", "sukka|kodi sukka", ""),
    ("Egg Masala Gravy", "e", 150, 15, "ld", 2, 340, "Boiled eggs in onion-tomato masala", "egg curry|motte curry", ""),
    ("Kheema Rice", "n", 230, 18, "ld", 2, 620, "Rice cooked with minced mutton and spices", "keema rice|kheema pulao", ""),
    ("Mutton Biryani (Military Style)", "n", 310, 28, "ld", 2, 760, "Seeraga samba style mutton biryani with onion raita", "mutton biriyani", "bestseller"),
    ("Chicken Ghee Rice with Chicken Gravy", "n", 240, 20, "ld", 2, 640, "Ghee rice with spicy chicken gravy", "ghee rice chicken|ghee rice combo", ""),
    ("Liver Fry", "n", 220, 18, "ld", 3, 360, "Spicy mutton liver fry", "mutton liver|boti fry", ""),
    ("Bangude Fry (Mackerel)", "n", 230, 18, "ld", 2, 380, "Rava-coated mackerel fry", "mackerel fry", ""),
    ("Chicken Chops", "n", 260, 22, "ld", 3, 480, "Chicken chops slow-cooked with whole spices", "", ""),
    ("Egg Bhurji with Chapati", "e", 140, 12, "bld", 1, 420, "Spiced scrambled eggs with two chapatis", "egg bhurji", ""),
    ("Paya Soup", "n", 160, 25, "bd", 2, 220, "Slow-cooked trotter soup with parotta", "paya|trotters soup", "comfort"),
    ("Mutton Soup", "n", 140, 20, "d", 2, 210, "Peppery clear mutton soup", "", "comfort"),
])

# ---------------------------------------------------------------- andhra
DISHES += block("Andhra Favourites", "andhra", [
    ("Andhra Chicken Fry", "n", 260, 22, "ld", 3, 450, "Spicy Guntur-style dry chicken fry", "chicken fry|guntur chicken", "bestseller"),
    ("Gongura Mutton", "n", 340, 28, "ld", 3, 580, "Mutton cooked with tangy sorrel leaves", "gongura mamsam", "must-try"),
    ("Gongura Chicken", "n", 280, 25, "ld", 3, 500, "Chicken cooked with tangy sorrel leaves", "", ""),
    ("Natu Kodi Pulusu", "n", 290, 25, "ld", 3, 520, "Country chicken in tamarind-spiced gravy", "kodi pulusu", ""),
    ("Andhra Chicken Biryani", "n", 270, 25, "ld", 3, 780, "Spicy Andhra-style dum biryani with mirchi ka salan", "andhra biryani|andhra biriyani", "bestseller"),
    ("Andhra Meals (Veg)", "v", 200, 15, "l", 3, 950, "Rice, pappu, gutti vankaya, tomato pachadi, rasam, curd and sweet", "andhra thali|veg meals andhra", ""),
    ("Andhra Meals (Non-Veg)", "n", 260, 18, "l", 3, 1050, "Andhra meals with chicken curry and fry", "", "bestseller"),
    ("Gutti Vankaya Curry", "v", 170, 18, "ld", 2, 340, "Stuffed brinjal curry with peanut-sesame masala", "stuffed brinjal curry", ""),
    ("Pappu Charu Combo", "v", 130, 12, "ld", 1, 450, "Toor dal with tangy rasam and rice", "pappu annam", "comfort"),
    ("Apollo Fish", "n", 270, 18, "ld", 3, 430, "Spicy fried boneless fish tossed with curry leaves and chillies", "apollo fish|fish apollo", "bestseller"),
    ("Chilli Chicken Andhra Style", "n", 250, 18, "ld", 3, 440, "Dry fried chicken with green chillies", "", ""),
    ("Egg Pulusu", "e", 160, 15, "ld", 2, 320, "Eggs in tangy tamarind gravy", "", ""),
    ("Kodi Vepudu with Ragi Sangati", "n", 270, 22, "ld", 3, 700, "Chicken fry with ragi sangati", "ragi sangati", ""),
    ("Bheemavaram Prawn Fry", "n", 340, 20, "ld", 3, 410, "Crisp spiced prawn fry", "royyala vepudu|prawn fry", ""),
])

# ---------------------------------------------------------------- kerala
DISHES += block("Kerala Kitchen", "kerala", [
    ("Appam with Veg Stew (2 pcs)", "v", 150, 15, "bd", 0, 420, "Lacy appams with coconut-milk vegetable stew", "appam stew|palappam", "bestseller"),
    ("Appam with Chicken Stew (2 pcs)", "n", 210, 18, "bd", 1, 520, "Appams with mild chicken stew", "chicken stew appam", "bestseller"),
    ("Kerala Parotta (2 pcs)", "v", 80, 10, "ldn", 0, 460, "Flaky layered parottas", "malabar parotta|parotta|barota", ""),
    ("Parotta with Chicken Curry", "n", 220, 18, "ldn", 2, 780, "Two parottas with Kerala chicken curry", "parotta chicken|kerala parotta curry", "bestseller"),
    ("Chicken Roast Kerala Style", "n", 260, 22, "ld", 3, 480, "Slow-roasted chicken in onion-tomato masala", "nadan chicken roast", "must-try"),
    ("Kerala Fish Curry Meals", "n", 250, 20, "l", 3, 820, "Rice with spicy red fish curry, thoran, pickle and papad", "meen curry meals|fish meals kerala", "must-try"),
    ("Meen Pollichathu", "n", 330, 25, "ld", 2, 450, "Fish marinated and grilled in banana leaf", "karimeen pollichathu|fish pollichathu", "must-try"),
    ("Prawn Roast", "n", 320, 20, "ld", 3, 380, "Prawns roasted with coconut slivers and curry leaves", "chemmeen roast", ""),
    ("Puttu and Kadala Curry", "v", 120, 14, "b", 1, 480, "Steamed rice-coconut cylinders with black chickpea curry", "puttu kadala", "must-try"),
    ("Egg Roast with Appam", "e", 160, 15, "bd", 2, 460, "Kerala egg roast with two appams", "", ""),
    ("Kerala Veg Meals (Sadya Style)", "v", 220, 18, "l", 1, 880, "Rice, parippu, sambar, avial, thoran, olan, pachadi, pickle and payasam", "sadya|onam sadya|kerala sadya", "festive"),
    ("Avial", "v", 130, 12, "ld", 0, 260, "Mixed vegetables in coconut-curd gravy", "aviyal", ""),
    ("Beetroot Thoran", "v", 90, 10, "ld", 0, 160, "Beetroot stir-fried with grated coconut", "thoran", "light"),
    ("Chicken Biryani Malabar Style", "n", 260, 25, "ld", 2, 780, "Malabar dum biryani with jeerakasala rice", "thalassery biryani|malabar biryani", "bestseller"),
    ("Banana Fritters (Pazham Pori)", "v", 70, 10, "s", 0, 330, "Ripe banana dipped in batter and fried", "pazham pori|ethakka appam", "street-food"),
    ("Unniyappam (6 pcs)", "v", 80, 12, "s", 0, 340, "Sweet jaggery-banana rice balls", "", "sweet"),
    ("Payasam (Palada)", "v", 90, 10, "ld", 0, 310, "Rice-flake milk pudding with cardamom", "palada payasam|ada pradhaman", "sweet|festive"),
    ("Duck Roast", "n", 360, 30, "d", 3, 560, "Kuttanad-style duck roast", "", ""),
])

# -------------------------------------------------------------- coastal / mangalorean
DISHES += block("Coastal Karnataka", "coastal,seafood", [
    ("Chicken Ghee Roast", "n", 290, 22, "ld", 3, 520, "Mangalorean red chilli chicken roasted in ghee", "ghee roast chicken", "must-try|bestseller"),
    ("Kori Rotti with Chicken Gassi", "n", 280, 20, "ld", 2, 600, "Crisp rice wafers with coconut chicken curry", "kori roti|kori rotti", "must-try"),
    ("Mangalore Buns (2 pcs)", "v", 70, 10, "bs", 0, 340, "Sweet banana puris served with coconut chutney", "banana buns|mangalore bun", ""),
    ("Goli Baje", "v", 65, 10, "s", 0, 300, "Fluffy deep-fried maida-yoghurt dumplings", "mangalore bajji|golibaje", "street-food"),
    ("Neer Dosa with Chicken Sukka", "n", 250, 18, "bld", 2, 560, "Three neer dosas with Mangalorean chicken sukka", "", "bestseller"),
    ("Fish Tawa Fry (Anjal)", "n", 380, 20, "ld", 2, 420, "Seer fish marinated in red masala and pan-fried", "anjal fry|surmai fry|king fish fry", "must-try"),
    ("Pomfret Rava Fry", "n", 420, 20, "ld", 2, 440, "Whole pomfret coated in rava and shallow-fried", "pomfret fry", ""),
    ("Prawn Gassi", "n", 330, 22, "ld", 3, 450, "Prawns in a roasted coconut gravy", "prawns gassi|chemmeen gassi", ""),
    ("Fish Curry Rice (Mangalorean)", "n", 230, 18, "l", 3, 740, "Rice with Mangalorean red fish curry", "meen saaru|fish thali", "bestseller"),
    ("Kane Rava Fry", "n", 360, 20, "ld", 2, 410, "Lady fish rava fry", "ladyfish fry", ""),
    ("Squid Ghee Roast", "n", 340, 22, "ld", 3, 400, "Tender squid rings roasted in ghee masala", "calamari ghee roast", ""),
    ("Crab Masala", "n", 480, 30, "ld", 3, 430, "Whole mud crab in a spicy coconut masala", "crab curry", ""),
    ("Fish Thali (Seafood Meals)", "n", 330, 20, "l", 3, 960, "Rice, fish curry, fish fry, sol kadi and kheer", "seafood thali|fish meals", ""),
    ("Prawn Biryani", "n", 340, 25, "ld", 2, 720, "Coastal prawn dum biryani", "prawns biryani|chemmeen biryani", ""),
    ("Surmai Thali Konkan", "n", 360, 22, "l", 2, 900, "Konkan-style king fish thali with sol kadhi", "", ""),
    ("Sol Kadhi", "v", 60, 4, "ld", 0, 120, "Chilled kokum-coconut digestive drink", "kokum drink", "light"),
])

# ------------------------------------------------------- tamil / chettinad / madurai
DISHES += block("Chettinad & Madurai", "tamil", [
    ("Chettinad Chicken Curry", "n", 280, 22, "ld", 3, 520, "Fiery chettinad chicken with stone-ground masala", "chettinad chicken", "bestseller"),
    ("Chicken 65", "n", 220, 15, "sdn", 3, 420, "Crisp spicy fried chicken bites with curry leaves", "chicken sixty five|chicken 65 dry", "bestseller"),
    ("Kothu Parotta (Chicken)", "n", 230, 18, "dn", 2, 780, "Shredded parotta stir-fried with chicken and egg", "kothu parota|kothu paratha|chicken kothu", "bestseller|must-try"),
    ("Kothu Parotta (Veg)", "v", 190, 15, "dn", 2, 720, "Shredded parotta stir-fried with vegetable salna", "veg kothu parotta", ""),
    ("Egg Kothu Parotta", "e", 200, 15, "dn", 2, 740, "Shredded parotta with scrambled egg and salna", "", ""),
    ("Parotta Salna", "v", 110, 12, "dn", 2, 540, "Two parottas with spicy vegetable salna", "parotta with salna", ""),
    ("Pepper Chicken Chettinad", "n", 260, 20, "ld", 3, 440, "Dry pepper chicken with chettinad spice", "", ""),
    ("Mutton Chukka", "n", 330, 28, "ld", 3, 520, "Dry mutton roast with shallots and pepper", "mutton chukka varuval", ""),
    ("Madurai Mutton Biryani", "n", 330, 28, "ld", 2, 760, "Short-grain mutton biryani with brinjal thokku", "", ""),
    ("Meen Kuzhambu with Rice", "n", 240, 20, "l", 3, 700, "Tangy tamarind fish curry with steamed rice", "fish kuzhambu", ""),
    ("Egg Dosa", "e", 110, 10, "bsdn", 1, 340, "Dosa topped with whisked egg and pepper", "muttai dosa", "bestseller"),
    ("Kal Dosa with Sambar", "v", 95, 12, "bsd", 0, 270, "Soft thick dosas, three pieces", "kal dosai", ""),
    ("Idiyappam with Kurma", "v", 110, 14, "bd", 0, 360, "String hoppers with coconut vegetable kurma", "string hoppers|nool puttu", ""),
    ("Filter Coffee Combo with Pongal", "v", 110, 10, "b", 1, 400, "Ven pongal with a tumbler of filter coffee", "", ""),
    ("Sundal", "v", 70, 8, "s", 1, 220, "Boiled chickpeas tempered with coconut and mustard", "chana sundal", "healthy|light"),
])
