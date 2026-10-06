"""Bengaluru neighbourhood centroids (approximate), used to place synthetic restaurants.

Coordinates are approximate area centres, good to roughly a kilometre. Every restaurant
generated from them is fictional. `weight` biases how many restaurants an area gets and
`premium` nudges menu prices (central / tech-corridor areas cost a little more).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Locality:
    name: str
    lat: float
    lon: float
    pincode: str
    weight: float = 1.0
    premium: float = 1.0
    streets: tuple[str, ...] = ("Main Road", "1st Cross", "2nd Main", "Temple Street", "Market Road")


COMMON_STREETS = ("Main Road", "1st Cross", "2nd Main", "4th Cross", "Temple Street", "Market Road", "5th Main", "Service Road")

LOCALITIES: list[Locality] = [
    Locality("Indiranagar", 12.9784, 77.6408, "560038", 1.6, 1.12, ("100 Feet Road", "12th Main", "CMH Road", "6th Main", "Double Road")),
    Locality("Koramangala", 12.9352, 77.6245, "560034", 1.7, 1.12, ("80 Feet Road", "5th Block", "6th Block", "7th Block", "Jyothi Nivas College Road")),
    Locality("HSR Layout", 12.9116, 77.6389, "560102", 1.5, 1.05, ("27th Main", "Sector 2", "Sector 6", "Outer Ring Road", "14th Cross")),
    Locality("BTM Layout", 12.9166, 77.6101, "560076", 1.4, 1.0, ("2nd Stage", "16th Main", "Udupi Garden Road", "29th Main", "Hosur Main Road")),
    Locality("Jayanagar", 12.9299, 77.5838, "560011", 1.5, 1.0, ("4th Block", "9th Block", "11th Main", "Cool Joint Road", "30th Cross")),
    Locality("JP Nagar", 12.9063, 77.5857, "560078", 1.3, 1.0, ("2nd Phase", "5th Phase", "24th Main", "15th Cross", "Ring Road")),
    Locality("Basavanagudi", 12.9422, 77.5738, "560004", 1.2, 0.95, ("Gandhi Bazaar", "DVG Road", "Bull Temple Road", "Bugle Rock Road")),
    Locality("Malleshwaram", 13.0035, 77.5646, "560003", 1.2, 0.95, ("8th Cross", "Margosa Road", "Sampige Road", "15th Cross")),
    Locality("Rajajinagar", 12.9916, 77.5520, "560010", 1.0, 0.95, ("Dr Rajkumar Road", "Chord Road", "4th Block", "West of Chord Road")),
    Locality("Whitefield", 12.9698, 77.7500, "560066", 1.4, 1.08, ("ITPL Main Road", "Hope Farm Junction", "Varthur Road", "Kadugodi", "Borewell Road")),
    Locality("Marathahalli", 12.9591, 77.6974, "560037", 1.3, 1.02, ("Outer Ring Road", "Kundalahalli Gate", "Varthur Road", "Munekolala")),
    Locality("Bellandur", 12.9304, 77.6784, "560103", 1.2, 1.05, ("Outer Ring Road", "Ecospace Road", "Sarjapur Road", "Doddakannelli")),
    Locality("Sarjapur Road", 12.9100, 77.6870, "560035", 1.1, 1.03, ("Carmelaram Road", "Dommasandra Circle", "Kasavanahalli", "Haralur Road")),
    Locality("Electronic City", 12.8452, 77.6602, "560100", 1.1, 0.98, ("Phase 1", "Phase 2", "Neeladri Road", "Hosur Road")),
    Locality("Hebbal", 13.0358, 77.5970, "560024", 1.0, 1.0, ("Bellary Road", "Kempapura", "Outer Ring Road", "Hebbal Main Road")),
    Locality("Yelahanka", 13.1007, 77.5963, "560064", 0.8, 0.95, ("Main Road", "New Town", "Doddaballapur Road", "Kogilu Cross")),
    Locality("Yeshwanthpur", 13.0285, 77.5409, "560022", 0.9, 0.95, ("Tumkur Road", "Mathikere", "Sunkadakatte", "Market Road")),
    Locality("MG Road", 12.9756, 77.6066, "560001", 1.3, 1.15, ("Brigade Road", "Church Street", "Residency Road", "Lavelle Road", "Rest House Road")),
    Locality("Shivajinagar", 12.9857, 77.6057, "560051", 1.0, 0.95, ("Commercial Street", "Russell Market Road", "Tannery Road", "Infantry Road")),
    Locality("Frazer Town", 12.9985, 77.6130, "560005", 0.9, 0.98, ("Mosque Road", "Pottery Road", "Cox Town", "Wheeler Road")),
    Locality("Banaswadi", 13.0134, 77.6500, "560043", 0.9, 0.97, ("Main Road", "Ramamurthy Nagar", "Hennur Road", "Kacharakanahalli")),
    Locality("KR Puram", 13.0074, 77.6960, "560036", 0.8, 0.95, ("Old Madras Road", "Tin Factory", "Hoodi", "Ramamurthy Nagar")),
    Locality("Kalyan Nagar", 13.0280, 77.6400, "560043", 0.9, 1.0, ("HRBR Layout", "Outer Ring Road", "Babusahib Palya", "Kammanahalli Main Road")),
    Locality("Vijayanagar", 12.9719, 77.5300, "560040", 0.9, 0.93, ("Hampi Nagar", "Magadi Road", "Attiguppe", "Chandra Layout")),
    Locality("Banashankari", 12.9255, 77.5468, "560070", 1.0, 0.95, ("2nd Stage", "3rd Stage", "Kathriguppe", "Hosakerehalli")),
    Locality("Bannerghatta Road", 12.8900, 77.5970, "560076", 1.1, 1.0, ("Arekere", "Gottigere", "Hulimavu", "IIMB Road")),
    Locality("Domlur", 12.9609, 77.6387, "560071", 0.9, 1.07, ("Old Airport Road", "Intermediate Ring Road", "Amarjyothi Layout", "EGL")),
    Locality("Ulsoor", 12.9810, 77.6200, "560008", 0.8, 1.05, ("Halasuru", "Kensington Road", "MG Road Extension", "Lakeside Road")),
    Locality("Sadashivanagar", 13.0068, 77.5813, "560080", 0.7, 1.1, ("Palace Road", "Bellary Road", "Vyalikaval", "CBI Road")),
    Locality("RT Nagar", 13.0210, 77.5960, "560032", 0.8, 0.97, ("Ganganagar", "Hebbal Road", "Dinnur Main Road", "Mekhri Circle")),
    Locality("Hennur", 13.0390, 77.6400, "560043", 0.8, 0.98, ("Hennur Main Road", "Bagalur Road", "Kothanur", "Horamavu")),
    Locality("CV Raman Nagar", 12.9850, 77.6640, "560093", 0.9, 1.0, ("Baiyappanahalli", "Kaggadasapura", "DRDO Road", "Old Madras Road")),
    Locality("Brookefield", 12.9650, 77.7170, "560037", 0.8, 1.03, ("Hoodi Circle", "ITPL Back Gate", "Kundalahalli", "Brookefield Main Road")),
    Locality("Mahadevapura", 12.9910, 77.6970, "560048", 0.9, 1.0, ("Old Madras Road", "Garudachar Palya", "Bhattarahalli", "Phoenix Marketcity Road")),
    Locality("Silk Board", 12.9170, 77.6230, "560068", 0.9, 1.0, ("Hosur Road", "Madiwala", "Mico Layout", "Outer Ring Road")),
    Locality("Wilson Garden", 12.9490, 77.5960, "560027", 0.8, 0.95, ("Lalbagh Road", "Hosur Main Road", "Shanti Nagar", "Richmond Town")),
    Locality("Kengeri", 12.9170, 77.4830, "560060", 0.6, 0.9, ("Mysore Road", "Satellite Town", "Kengeri Hobli", "NICE Road")),
    Locality("Jakkur", 13.0770, 77.6070, "560064", 0.6, 0.97, ("Jakkur Main Road", "Amruthahalli", "Bellary Road", "Thanisandra")),
    Locality("Sanjay Nagar", 13.0360, 77.5700, "560094", 0.7, 0.96, ("RMV 2nd Stage", "Ganganagar", "Mathikere", "Sanjay Nagar Main Road")),
    Locality("Richmond Town", 12.9630, 77.6020, "560025", 0.7, 1.08, ("Richmond Road", "Brunton Road", "Hosur Road", "Langford Town")),
    Locality("Lavelle Road", 12.9710, 77.5950, "560001", 0.6, 1.15, ("Lavelle Road", "St Marks Road", "Vittal Mallya Road", "Kasturba Road")),
    Locality("Mathikere", 13.0320, 77.5610, "560054", 0.7, 0.95, ("MSRIT Road", "New BEL Road", "Gokula Extension", "Mattikere Main Road")),
    Locality("Nagarbhavi", 12.9610, 77.5130, "560072", 0.7, 0.93, ("Nagarbhavi Circle", "BDA Complex", "Chandra Layout", "Ullal Road")),
    Locality("Kammanahalli", 13.0150, 77.6390, "560084", 0.8, 0.98, ("Kammanahalli Main Road", "St Thomas Town", "Bank Colony", "Lingarajapuram")),
    Locality("Bommanahalli", 12.9070, 77.6280, "560068", 0.8, 0.97, ("Hosur Road", "Begur Road", "Garvebhavi Palya", "Kudlu Gate")),
    Locality("Thanisandra", 13.0580, 77.6330, "560077", 0.6, 0.97, ("Thanisandra Main Road", "Kothanur Road", "Hennur Bagalur Road", "Nagavara")),
    Locality("Basaveshwaranagar", 12.9900, 77.5380, "560079", 0.8, 0.94, ("1st Block", "3rd Block", "West of Chord Road", "Mahakavi Kuvempu Road")),
    Locality("Hosur Road", 12.8990, 77.6370, "560068", 0.8, 0.98, ("Singasandra", "Hongasandra", "Electronic City Flyover", "Roopena Agrahara")),
]


def by_name(name: str) -> Locality:
    for loc in LOCALITIES:
        if loc.name == name:
            return loc
    raise KeyError(name)
