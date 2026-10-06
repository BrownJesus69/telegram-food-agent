"""North Indian, Mughlai, biryani, Indo-Chinese, Tibetan, regional thalis, Arabian, BBQ."""
from tools.catalogue_gen.dsl import block

DISHES = []

# ---------------------------------------------------------------- north curries
DISHES += block("Curries", "north", [
    ("Butter Chicken", "n", 320, 22, "ld", 1, 560, "Tandoori chicken simmered in a buttery tomato-cream gravy", "murgh makhani|chicken makhani", "bestseller|must-try"),
    ("Chicken Tikka Masala", "n", 320, 22, "ld", 2, 540, "Chargrilled chicken tikka in spiced onion-tomato gravy", "tikka masala", "bestseller"),
    ("Kadai Chicken", "n", 310, 22, "ld", 2, 520, "Chicken with peppers and freshly ground kadai masala", "chicken kadai", ""),
    ("Chicken Curry (Home Style)", "n", 240, 20, "ld", 2, 420, "Light onion-tomato chicken curry", "chicken gravy|chicken curry", ""),
    ("Mutton Rogan Josh", "n", 380, 30, "ld", 2, 620, "Kashmiri-style mutton in aromatic chilli-fennel gravy", "rogan josh|laal maas", ""),
    ("Egg Curry (Dhaba Style)", "e", 170, 15, "ld", 2, 340, "Boiled eggs in thick dhaba masala", "anda curry|egg masala", ""),
    ("Paneer Butter Masala", "v", 280, 18, "ld", 1, 520, "Soft paneer in a creamy tomato-cashew gravy", "paneer makhani|pbm", "bestseller|must-try"),
    ("Kadai Paneer", "v", 270, 18, "ld", 2, 490, "Paneer with onions and capsicum in kadai masala", "paneer kadai", ""),
    ("Palak Paneer", "v", 260, 18, "ld", 1, 420, "Paneer cubes in smooth spinach gravy", "saag paneer", "healthy"),
    ("Shahi Paneer", "v", 280, 18, "ld", 1, 540, "Paneer in a rich royal cashew-cream gravy", "", ""),
    ("Paneer Tikka Masala", "v", 290, 20, "ld", 2, 520, "Smoky grilled paneer in masala gravy", "", ""),
    ("Malai Kofta", "v", 270, 20, "ld", 1, 560, "Paneer-potato dumplings in creamy gravy", "", ""),
    ("Dal Makhani", "v", 230, 20, "ld", 1, 440, "Slow-cooked black lentils finished with butter and cream", "dal makkhani|maa ki dal", "bestseller|comfort"),
    ("Dal Tadka", "v", 170, 15, "ld", 1, 320, "Yellow lentils tempered with garlic and cumin", "tadka dal|yellow dal", "vegan|comfort"),
    ("Chana Masala", "v", 190, 15, "ld", 2, 380, "Chickpeas in tangy onion-tomato masala", "chole masala|chole", "vegan|bestseller"),
    ("Rajma Masala", "v", 190, 18, "ld", 1, 380, "Kidney beans slow-cooked in a thick gravy", "rajma", "vegan|comfort"),
    ("Aloo Gobi", "v", 190, 15, "ld", 1, 300, "Potato and cauliflower with turmeric and cumin", "gobi aloo", "vegan"),
    ("Bhindi Masala", "v", 190, 15, "ld", 1, 260, "Stir-fried okra with onions and spices", "bhindi do pyaza", "vegan"),
    ("Mixed Veg Curry", "v", 190, 15, "ld", 1, 320, "Seasonal vegetables in a mild gravy", "mix veg|veg kolhapuri|veg jalfrezi", ""),
    ("Baingan Bharta", "v", 200, 18, "ld", 2, 280, "Smoky mashed aubergine with onion and tomato", "", "vegan"),
    ("Paneer Bhurji", "v", 240, 15, "bld", 1, 420, "Scrambled paneer with onion, tomato and spices", "", "high-protein"),
    ("Kadhi Pakora", "v", 190, 18, "ld", 1, 380, "Gram-flour dumplings in tangy yoghurt curry", "", "comfort"),
    ("Matar Paneer", "v", 250, 18, "ld", 1, 440, "Paneer and green peas in tomato gravy", "", ""),
    ("Veg Kolhapuri", "v", 220, 18, "ld", 3, 360, "Spicy mixed vegetables in Kolhapuri masala", "", ""),
])

DISHES += block("Breads & Rice", "north,biryani_side", [
    ("Butter Naan", "v", 60, 8, "ld", 0, 290, "Soft leavened tandoor bread brushed with butter", "naan", "bestseller"),
    ("Garlic Naan", "v", 70, 8, "ld", 0, 300, "Tandoor naan topped with garlic and coriander", "", "bestseller"),
    ("Cheese Garlic Naan", "v", 110, 10, "ld", 0, 380, "Naan stuffed with cheese and garlic", "cheese naan", "kids-fav"),
    ("Tandoori Roti", "v", 30, 6, "ld", 0, 130, "Whole-wheat bread baked in the tandoor", "roti|tandoor roti", "vegan"),
    ("Butter Roti", "v", 35, 6, "ld", 0, 150, "Tandoori roti with butter", "", ""),
    ("Laccha Paratha", "v", 65, 8, "ld", 0, 280, "Flaky layered whole-wheat paratha", "lachha paratha|layered paratha", ""),
    ("Kulcha (Amritsari)", "v", 90, 10, "ld", 1, 340, "Stuffed potato-onion kulcha with chole", "amritsari kulcha|aloo kulcha", ""),
    ("Jeera Rice", "v", 120, 10, "ld", 0, 310, "Basmati rice tempered with cumin", "", "vegan"),
    ("Steamed Rice", "v", 90, 8, "ld", 0, 260, "Plain steamed basmati", "plain rice", "vegan|light"),
    ("Veg Pulao", "v", 150, 12, "ld", 1, 380, "Fragrant rice with vegetables and whole spices", "vegetable pulao", ""),
    ("Dal Khichdi", "v", 160, 15, "ld", 0, 380, "Rice and lentils cooked with ghee and turmeric", "khichdi|khichadi", "comfort|light"),
    ("Curd Rice North Style (Dahi Chawal)", "v", 110, 6, "ld", 0, 300, "Rice with fresh curd and tempering", "dahi chawal", "light"),
    ("Rajma Chawal", "v", 190, 15, "ld", 1, 560, "Rajma masala with steamed rice and onion", "rajma rice", "bestseller|comfort"),
    ("Chole Bhature (2 pcs)", "v", 170, 15, "bld", 2, 720, "Fluffy bhature with spicy chickpea curry, onion and pickle", "chola bhatura|chhole bhature", "bestseller|must-try"),
    ("Aloo Paratha (2 pcs)", "v", 130, 12, "bld", 1, 520, "Stuffed potato parathas with curd and pickle", "aloo parantha", "bestseller|comfort"),
    ("Gobi Paratha (2 pcs)", "v", 140, 12, "bld", 1, 500, "Cauliflower-stuffed parathas with curd", "gobhi paratha", ""),
    ("Paneer Paratha (2 pcs)", "v", 160, 12, "bld", 1, 560, "Paneer-stuffed parathas with butter", "paneer parantha", ""),
    ("Mixed Veg Paratha (2 pcs)", "v", 140, 12, "bld", 1, 500, "Parathas stuffed with seasonal vegetables", "", ""),
    ("Puri Bhaji (3 pcs)", "v", 120, 12, "bs", 1, 560, "North-style puris with potato curry", "poori aloo", ""),
])

DISHES += block("Combos", "north,homefood", [
    ("North Indian Thali (Veg)", "v", 260, 18, "ld", 1, 980, "Dal, paneer sabzi, seasonal veg, rice, 2 rotis, raita, pickle, salad and sweet", "veg thali|north thali|punjabi thali", "bestseller"),
    ("North Indian Thali (Non-Veg)", "n", 330, 20, "ld", 2, 1100, "Chicken curry, dal, rice, 2 rotis, raita, salad and sweet", "non veg thali|chicken thali", ""),
    ("Mini Veg Combo (Roti, Dal, Sabzi)", "v", 180, 12, "ld", 1, 640, "Two rotis, dal tadka, one sabzi and rice", "dal roti sabzi combo|office lunch box", "light"),
    ("Chicken Curry Rice Bowl", "n", 220, 15, "ld", 2, 650, "Home-style chicken curry over steamed rice", "chicken rice bowl", "bestseller"),
    ("Paneer Rice Bowl", "v", 210, 15, "ld", 1, 640, "Paneer butter masala over jeera rice", "paneer bowl", ""),
    ("Egg Fried Rice Combo with Gravy", "e", 200, 15, "ld", 2, 680, "Egg fried rice with veg manchurian gravy", "", ""),
])

# ------------------------------------------------------------------ tandoor / mughlai
DISHES += block("Tandoor & Kebabs", "mughlai,tandoor", [
    ("Chicken Tikka", "n", 280, 20, "sdn", 2, 380, "Boneless chicken marinated in yoghurt and spices, chargrilled", "tikka|murgh tikka", "bestseller|high-protein"),
    ("Tandoori Chicken (Half)", "n", 320, 25, "dn", 2, 480, "Half chicken marinated and cooked in the clay oven", "tandoori murgh|tandoori chicken", "bestseller"),
    ("Tandoori Chicken (Full)", "n", 560, 30, "dn", 2, 960, "Whole chicken in the clay oven", "full tandoori|tandoori chicken full", ""),
    ("Murgh Malai Kebab", "n", 300, 20, "sdn", 1, 400, "Creamy cheese-cashew marinated chicken kebab", "malai tikka|chicken malai tikka|malai chicken", "must-try"),
    ("Chicken Reshmi Kebab", "n", 300, 20, "sdn", 1, 390, "Silky mild chicken kebab", "reshmi tikka", ""),
    ("Hariyali Chicken Tikka", "n", 290, 20, "sdn", 2, 370, "Mint-coriander marinated chicken tikka", "hara bhara chicken", ""),
    ("Seekh Kebab (Mutton)", "n", 340, 22, "sdn", 2, 460, "Minced mutton skewers grilled over charcoal", "mutton seekh|seekh kabab", "bestseller"),
    ("Galouti Kebab (4 pcs)", "n", 380, 20, "dn", 1, 520, "Melt-in-mouth Lucknowi mutton patties with ulte tawe ka paratha", "galawati|galouti", "must-try"),
    ("Afghani Chicken", "n", 320, 25, "dn", 1, 470, "Creamy mild tandoori chicken", "afghani tikka", ""),
    ("Paneer Tikka", "v", 260, 18, "sdn", 2, 390, "Chargrilled paneer cubes with peppers and onions", "paneer tikka dry|paneer kebab", "bestseller|high-protein"),
    ("Malai Paneer Tikka", "v", 280, 18, "sdn", 1, 410, "Cream-marinated paneer, mild and soft", "", ""),
    ("Hara Bhara Kebab", "v", 220, 15, "sdn", 1, 340, "Spinach, peas and potato patties", "veg kebab|hara bhara kabab", "healthy"),
    ("Dahi Ke Kebab", "v", 240, 18, "sd", 1, 360, "Hung-curd kebabs pan-fried till crisp", "", ""),
    ("Tandoori Mushroom", "v", 240, 18, "sdn", 2, 310, "Button mushrooms marinated and grilled in the tandoor", "mushroom tikka", ""),
    ("Tandoori Gobi", "v", 220, 18, "sd", 2, 300, "Cauliflower florets marinated in spiced curd and roasted", "", "vegan"),
    ("Fish Tikka", "n", 340, 22, "sdn", 2, 360, "Boneless fish marinated in ajwain and yoghurt", "amritsari fish tikka|fish kebab", ""),
    ("Tandoori Prawns", "n", 420, 22, "dn", 2, 340, "Jumbo prawns chargrilled with spices", "prawn tikka", ""),
    ("Mutton Seekh Roll Platter", "n", 360, 20, "dn", 2, 640, "Seekh kebabs served with rumali roti and mint chutney", "", ""),
    ("Rumali Roti", "v", 40, 6, "ld", 0, 150, "Handkerchief-thin soft bread", "", ""),
])

# ----------------------------------------------------------------- biryani
DISHES += block("Biryani", "biryani", [
    ("Hyderabadi Chicken Dum Biryani", "n", 289, 28, "ldn", 3, 780, "Layered long-grain rice and marinated chicken sealed and slow-cooked", "chicken biryani|hyderabadi biryani|chicken biriyani|dum biryani", "bestseller|must-try"),
    ("Hyderabadi Mutton Dum Biryani", "n", 349, 32, "ldn", 3, 840, "Tender mutton layered with saffron rice", "mutton biryani|mutton biriyani", "bestseller"),
    ("Chicken 65 Biryani", "n", 299, 28, "ldn", 3, 820, "Biryani topped with crisp chicken 65", "", ""),
    ("Donne Chicken Biryani", "n", 259, 25, "ld", 2, 740, "Bangalore donne-style seeraga samba chicken biryani in a leaf bowl", "donne biryani|star biryani|bangalore biryani", "must-try|bestseller"),
    ("Donne Mutton Biryani", "n", 329, 28, "ld", 2, 800, "Donne-style seeraga samba mutton biryani", "", ""),
    ("Egg Biryani", "e", 199, 22, "ldn", 2, 700, "Biryani with boiled and masala-fried eggs", "egg biriyani|anda biryani", ""),
    ("Veg Dum Biryani", "v", 199, 22, "ld", 2, 640, "Vegetables and saffron rice sealed on dum", "veg biryani|vegetable biryani", "bestseller"),
    ("Paneer Biryani", "v", 229, 22, "ld", 2, 690, "Paneer tikka layered in dum biryani", "paneer biriyani", ""),
    ("Mushroom Biryani", "v", 219, 22, "ld", 2, 650, "Mushrooms and masala rice on dum", "", ""),
    ("Lucknowi Chicken Biryani", "n", 319, 28, "ld", 1, 740, "Mild aromatic Awadhi chicken biryani", "awadhi biryani", ""),
    ("Ambur Chicken Biryani", "n", 289, 28, "ld", 3, 760, "Short-grain Ambur-style chicken biryani with brinjal salan", "ambur biryani", ""),
    ("Kolkata Chicken Biryani with Potato", "n", 299, 28, "ld", 1, 760, "Light Kolkata biryani with potato and egg", "calcutta biryani", ""),
    ("Fish Biryani", "n", 329, 25, "ld", 2, 720, "Spiced fish layered with basmati", "", ""),
    ("Chicken Biryani Family Pack (Serves 4)", "n", 899, 35, "ldn", 3, 3000, "Hyderabadi dum biryani for four with raita and salan", "family biryani|party pack biryani", "bestseller"),
    ("Mutton Biryani Family Pack (Serves 4)", "n", 1199, 38, "ldn", 3, 3200, "Dum mutton biryani for four", "", ""),
    ("Veg Biryani Family Pack (Serves 4)", "v", 699, 30, "ld", 2, 2600, "Veg dum biryani for four", "", ""),
    ("Chicken Biryani (Boneless)", "n", 319, 28, "ldn", 3, 760, "Boneless chicken dum biryani", "boneless biryani", ""),
    ("Raita (Boondi)", "v", 50, 3, "ldn", 0, 90, "Chilled whisked curd with boondi", "boondi raita|curd", "light"),
    ("Mirchi Ka Salan", "v", 70, 5, "ldn", 2, 150, "Green chillies in a peanut-sesame gravy", "mirchi salan|salan", ""),
    ("Double Ka Meetha", "v", 110, 10, "ldn", 0, 380, "Hyderabadi bread pudding with saffron", "", "sweet|must-try"),
    ("Qubani Ka Meetha", "v", 130, 8, "ldn", 0, 320, "Stewed apricot dessert with cream", "", "sweet"),
    ("Phirni", "v", 90, 6, "ld", 0, 260, "Ground-rice pudding set in a clay bowl", "firni", "sweet"),
])

# ------------------------------------------------------------- Indo-Chinese
DISHES += block("Indo-Chinese", "chinese", [
    ("Veg Fried Rice", "v", 150, 15, "ldn", 1, 520, "Wok-tossed rice with vegetables and soy", "vegetable fried rice", "bestseller"),
    ("Egg Fried Rice", "e", 160, 15, "ldn", 1, 560, "Wok-tossed rice with egg and spring onion", "", "bestseller"),
    ("Chicken Fried Rice", "n", 190, 15, "ldn", 1, 620, "Wok-tossed rice with chicken and egg", "chicken rice", "bestseller"),
    ("Schezwan Chicken Fried Rice", "n", 210, 15, "ldn", 3, 650, "Fiery schezwan-sauce fried rice with chicken", "szechuan chicken rice", ""),
    ("Schezwan Veg Fried Rice", "v", 170, 15, "ldn", 3, 560, "Spicy schezwan fried rice", "szechuan fried rice", ""),
    ("Triple Schezwan Rice", "n", 260, 18, "dn", 3, 880, "Rice, noodles and gravy tossed in schezwan sauce", "triple rice", ""),
    ("Veg Hakka Noodles", "v", 150, 15, "ldn", 1, 500, "Stir-fried noodles with crunchy vegetables", "veg noodles|vegetable noodles", "bestseller"),
    ("Egg Hakka Noodles", "e", 170, 15, "ldn", 1, 540, "Hakka noodles with scrambled egg", "egg noodles", ""),
    ("Chicken Hakka Noodles", "n", 190, 15, "ldn", 1, 580, "Hakka noodles with chicken strips", "chicken noodles", "bestseller"),
    ("Schezwan Noodles (Veg)", "v", 170, 15, "ldn", 3, 540, "Hot schezwan noodles", "szechuan noodles", ""),
    ("Chilli Garlic Noodles", "v", 160, 15, "ldn", 3, 520, "Noodles tossed in chilli-garlic sauce", "garlic noodles", ""),
    ("Singapore Noodles", "n", 220, 15, "ldn", 2, 600, "Thin rice noodles with curry powder, chicken and prawn", "", ""),
    ("Veg Manchurian Gravy", "v", 170, 15, "ldn", 1, 380, "Vegetable balls in soy-garlic gravy", "veg manchurian|manchurian", "bestseller"),
    ("Gobi Manchurian (Dry)", "v", 170, 15, "sldn", 2, 410, "Crisp cauliflower tossed in manchurian sauce", "gobi manchurian|cauliflower manchurian|gobi dry", "bestseller|street-food"),
    ("Chicken Manchurian", "n", 220, 18, "ldn", 2, 460, "Fried chicken in manchurian gravy", "", "bestseller"),
    ("Chilli Chicken (Dry)", "n", 230, 18, "sldn", 3, 450, "Crisp chicken with green chillies and peppers", "chilly chicken|chilli chicken", "bestseller"),
    ("Chilli Chicken (Gravy)", "n", 240, 18, "ldn", 3, 480, "Chilli chicken in a spicy sauce", "chilly chicken gravy", ""),
    ("Dragon Chicken", "n", 250, 18, "sdn", 3, 470, "Crisp chicken in a fiery red chilli sauce with cashews", "", ""),
    ("Chilli Paneer (Dry)", "v", 220, 15, "sldn", 2, 420, "Paneer cubes tossed with chillies and capsicum", "chilly paneer|paneer chilli", "bestseller|high-protein"),
    ("Paneer Manchurian", "v", 220, 15, "ldn", 2, 440, "Paneer in manchurian sauce", "", ""),
    ("Chilli Gobi", "v", 180, 15, "sldn", 3, 380, "Dry cauliflower with chilli sauce", "chilly gobi", ""),
    ("Honey Chilli Potato", "v", 170, 12, "sdn", 1, 440, "Crispy potato fingers glazed in honey-chilli sauce", "chilli potato|honey potato", "kids-fav"),
    ("Veg Spring Rolls (4 pcs)", "v", 140, 12, "sd", 0, 380, "Crisp rolls with cabbage and carrot", "spring roll|veg spring roll", ""),
    ("Chicken Lollipop (6 pcs)", "n", 260, 18, "sdn", 2, 520, "Fried chicken winglets with schezwan dip", "chicken lollypop", "bestseller"),
    ("Hot and Sour Soup (Veg)", "v", 110, 8, "ld", 2, 120, "Peppery tangy soup with vegetables", "hot n sour soup", "light"),
    ("Hot and Sour Soup (Chicken)", "n", 130, 8, "ld", 2, 160, "Peppery tangy soup with shredded chicken", "", "light"),
    ("Sweet Corn Soup (Veg)", "v", 100, 8, "ld", 0, 140, "Creamy sweet-corn soup", "sweet corn veg soup", "light|comfort"),
    ("Manchow Soup (Chicken)", "n", 130, 8, "ld", 2, 200, "Thick spicy soup topped with crispy noodles", "manchow soup", ""),
    ("American Chopsuey", "n", 240, 15, "ld", 1, 700, "Crisp noodles topped with sweet-and-sour sauce and chicken", "chopsuey", ""),
    ("Burnt Garlic Fried Rice", "v", 170, 15, "ldn", 2, 560, "Fried rice with burnt garlic and spring onion", "", ""),
    ("Veg Pan Fried Noodles", "v", 190, 15, "dn", 1, 570, "Crispy noodle bed with vegetables in sauce", "", ""),
])

# ------------------------------------------------------------------ tibetan / momos
DISHES += block("Momos & Tibetan", "momos", [
    ("Veg Steamed Momos (8 pcs)", "v", 120, 12, "sdn", 1, 330, "Cabbage-carrot dumplings steamed, with fiery red chutney", "veg momos|vegetable momos|steamed momos", "bestseller|street-food"),
    ("Chicken Steamed Momos (8 pcs)", "n", 140, 12, "sdn", 1, 360, "Juicy chicken dumplings with red chutney", "chicken momos|chicken dumplings", "bestseller|street-food"),
    ("Paneer Steamed Momos (8 pcs)", "v", 140, 12, "sdn", 1, 360, "Paneer-stuffed dumplings", "paneer momos", ""),
    ("Veg Fried Momos (8 pcs)", "v", 130, 14, "sdn", 1, 420, "Crisp golden-fried veg dumplings", "fried momos", ""),
    ("Chicken Fried Momos (8 pcs)", "n", 150, 14, "sdn", 1, 450, "Crisp fried chicken dumplings", "chicken fried momos", ""),
    ("Chicken Kurkure Momos (6 pcs)", "n", 170, 14, "sdn", 2, 480, "Crunchy-coated chicken dumplings", "kurkure momos", ""),
    ("Chicken Pan-Fried Momos (8 pcs)", "n", 160, 14, "sdn", 2, 440, "Pan-seared momos tossed in chilli oil", "pan fried momos|jhol momos", ""),
    ("Chicken Jhol Momos", "n", 170, 14, "sdn", 2, 400, "Steamed chicken momos in tangy sesame-tomato broth", "jhol momo", "must-try"),
    ("Tandoori Momos (6 pcs)", "n", 180, 15, "sdn", 2, 420, "Momos marinated in tandoori masala and grilled", "afghani momos", ""),
    ("Chicken Thukpa", "n", 190, 15, "ld", 1, 380, "Himalayan noodle soup with chicken and vegetables", "thukpa|thenthuk", "comfort"),
    ("Veg Thukpa", "v", 170, 15, "ld", 1, 340, "Himalayan noodle soup with vegetables", "", "comfort|light"),
    ("Chilli Momos (Chicken)", "n", 180, 15, "sdn", 3, 460, "Fried momos tossed in a hot chilli sauce", "", ""),
    ("Cheese Corn Momos (8 pcs)", "v", 150, 12, "sdn", 0, 400, "Cheesy sweet-corn dumplings", "", "kids-fav"),
    ("Wai Wai Sadeko", "v", 100, 8, "s", 2, 280, "Spicy Nepali instant-noodle snack", "wai wai", "street-food"),
])

# --------------------------------------------------- regional thali / gujarati etc.
DISHES += block("Gujarati & Rajasthani", "gujarati,homefood", [
    ("Gujarati Thali", "v", 280, 20, "ld", 0, 1000, "Dal, kadhi, two sabzis, rotli, rice, farsan and sweet", "gujju thali|kathiyawadi thali", "bestseller"),
    ("Dhokla Plate (6 pcs)", "v", 100, 8, "bs", 0, 240, "Steamed gram-flour sponge with chutney", "khaman dhokla|dhokla", "light|bestseller"),
    ("Khandvi", "v", 110, 8, "bs", 0, 230, "Silky gram-flour rolls tempered with mustard and coconut", "", "light"),
    ("Methi Thepla (4 pcs)", "v", 110, 10, "bs", 1, 420, "Fenugreek flatbreads with pickle and curd", "thepla", ""),
    ("Fafda Jalebi", "v", 140, 10, "bs", 1, 560, "Crisp gram-flour fafda with sweet jalebi and chutney", "", "street-food"),
    ("Undhiyu", "v", 240, 22, "ld", 2, 440, "Winter vegetable medley with fenugreek dumplings", "", "festive"),
    ("Dal Baati Churma", "v", 260, 22, "ld", 1, 920, "Baked wheat balls with panchmel dal and sweet churma", "daal baati|dal bati churma", "must-try"),
    ("Gatte Ki Sabzi with Roti", "v", 210, 18, "ld", 2, 540, "Gram-flour dumplings in curd gravy", "", ""),
    ("Ker Sangri", "v", 230, 18, "ld", 2, 380, "Desert beans and berries Rajasthani speciality", "", ""),
    ("Handvo Slice", "v", 90, 10, "bs", 1, 260, "Savoury lentil-rice cake with bottle gourd", "", ""),
    ("Sev Tamatar Sabzi", "v", 190, 15, "ld", 1, 350, "Tomato curry topped with crunchy sev", "sev tameta", ""),
])

DISHES += block("Bengali & East", "bengali", [
    ("Kolkata Chicken Kathi Roll", "n", 170, 12, "sdn", 2, 520, "Paratha wrapped around egg-coated chicken, onions and chutney", "kolkata roll|chicken roll|kathi roll", "bestseller|street-food"),
    ("Egg Roll Kolkata Style", "e", 110, 10, "bsdn", 1, 440, "Flaky paratha wrapped with fried egg and onions", "egg roll|egg kathi roll", "street-food"),
    ("Kosha Mangsho with Luchi", "n", 340, 30, "ld", 2, 780, "Slow-cooked Bengali mutton curry with puffed luchis", "kosha mangsho|bengali mutton curry", "must-try"),
    ("Shorshe Ilish", "n", 450, 25, "ld", 2, 520, "Hilsa in mustard gravy", "ilish maach|hilsa curry", ""),
    ("Macher Jhol with Rice", "n", 280, 20, "l", 1, 640, "Light Bengali fish curry with rice", "fish jhol|rohu curry", ""),
    ("Chingri Malai Curry", "n", 400, 22, "ld", 1, 520, "Prawns in coconut milk gravy", "prawn malai curry", ""),
    ("Luchi with Aloor Dom", "v", 150, 15, "bs", 1, 560, "Puffed flatbreads with Bengali dum aloo", "luchi alur dom|luchi aloo", ""),
    ("Mishti Doi", "v", 80, 4, "lsd", 0, 220, "Sweet caramelised set yoghurt in a clay pot", "sweet curd|misti doi", "sweet|must-try"),
    ("Rasgulla (2 pcs)", "v", 70, 4, "lsd", 0, 190, "Spongy cottage-cheese balls in light syrup", "rosogolla", "sweet"),
    ("Sandesh (2 pcs)", "v", 80, 4, "lsd", 0, 200, "Fresh chhena sweets", "", "sweet"),
    ("Jhal Muri", "v", 60, 5, "s", 2, 180, "Spicy puffed-rice street snack with mustard oil", "jhalmuri|bhel muri", "street-food|light"),
    ("Kolkata Biryani Egg Roll Combo", "e", 240, 15, "dn", 1, 900, "Egg roll with a mini biryani box", "", ""),
])

# --------------------------------------------------------------- arabian
DISHES += block("Arabian & Shawarma", "arabian", [
    ("Chicken Shawarma Roll", "n", 130, 10, "sdn", 1, 480, "Marinated chicken, garlic sauce and pickles in a toasted wrap", "chicken shawarma|shawarma wrap|shawarma roll|shawarma", "bestseller|street-food"),
    ("Chicken Shawarma Plate", "n", 220, 14, "ldn", 1, 780, "Shawarma chicken with khubz, hummus, fries and garlic dip", "shawarma plate", "bestseller"),
    ("Double Chicken Shawarma", "n", 190, 12, "sdn", 1, 720, "Extra-filled chicken shawarma wrap", "", ""),
    ("Peri Peri Shawarma", "n", 160, 10, "sdn", 2, 520, "Shawarma wrap with peri-peri sauce", "", ""),
    ("Falafel Wrap", "v", 140, 10, "sdn", 1, 450, "Crisp chickpea falafel with hummus and salad", "falafel roll", "vegan|bestseller"),
    ("Falafel Plate (6 pcs)", "v", 180, 12, "ldn", 1, 520, "Six falafel with hummus, pita and tabbouleh", "", "vegan"),
    ("Hummus with Pita", "v", 170, 8, "sdn", 0, 380, "Smooth chickpea-tahini dip with warm pita", "humus", "vegan"),
    ("Baba Ganoush", "v", 180, 10, "sdn", 0, 260, "Smoky aubergine and tahini dip", "", "vegan"),
    ("Grilled Chicken Al Faham (Half)", "n", 280, 25, "ldn", 1, 540, "Charcoal-grilled half chicken with Arabian rice or pita and garlic sauce", "al faham|alfaham|al faham chicken", "bestseller|must-try"),
    ("Grilled Chicken Al Faham (Full)", "n", 520, 30, "ldn", 1, 1000, "Whole charcoal-grilled chicken with garlic mayo", "full alfaham", ""),
    ("Chicken Mandi (Half)", "n", 340, 30, "ld", 1, 920, "Smoky tender chicken on fragrant mandi rice", "mandi|chicken mandi", "must-try"),
    ("Mutton Mandi", "n", 480, 35, "ld", 1, 980, "Slow-cooked mutton on spiced mandi rice", "", ""),
    ("Arabian Mixed Grill Platter", "n", 640, 30, "dn", 1, 1400, "Tikka, kebab, shawarma and grilled chicken for two", "mixed grill", ""),
    ("Kunafa", "v", 190, 10, "sdn", 0, 480, "Warm shredded-pastry dessert with cheese and sugar syrup", "knafeh", "sweet|must-try"),
    ("Baklava (3 pcs)", "v", 170, 5, "sd", 0, 420, "Flaky pastry with pistachio and honey", "", "sweet"),
    ("Arabian Garlic Mayo Dip", "v", 30, 2, "sldn", 0, 150, "Creamy garlic dip", "garlic sauce|toum", ""),
])

# ------------------------------------------------------------------ bbq / grill
DISHES += block("Grills & Barbecue", "bbq", [
    ("BBQ Chicken Wings (6 pcs)", "n", 280, 20, "sdn", 1, 520, "Smoky barbecue-glazed wings", "bbq wings", "bestseller"),
    ("Peri Peri Grilled Chicken", "n", 320, 25, "ld", 2, 480, "Leg and thigh grilled with peri-peri marinade", "peri peri chicken", "bestseller"),
    ("Lemon Herb Grilled Fish", "n", 380, 22, "ld", 0, 360, "Basa grilled with lemon, garlic and herbs", "grilled fish", "healthy"),
    ("BBQ Pork Ribs", "n", 480, 35, "d", 1, 760, "Slow-cooked ribs glazed with barbecue sauce", "ribs|pork ribs", ""),
    ("Grilled Paneer Steak", "v", 290, 20, "ld", 1, 460, "Paneer steak with pepper sauce and sauteed vegetables", "paneer steak", "high-protein"),
    ("Grilled Veg Platter", "v", 280, 20, "ld", 0, 360, "Seasonal vegetables chargrilled with herb butter", "", "healthy"),
    ("Chicken Steak with Mash and Veg", "n", 380, 25, "ld", 1, 620, "Pepper-sauce chicken steak with mashed potato", "chicken steak", ""),
    ("Mixed Grill Platter (2 pax)", "n", 780, 30, "d", 1, 1500, "Chicken, fish, sausages, ribs, grilled veg and sauces", "bbq platter", ""),
    ("Loaded BBQ Chicken Fries", "n", 260, 15, "sdn", 1, 700, "Fries topped with BBQ chicken, cheese and jalapeno", "", ""),
])
