# FoodBot — Telegram food ordering MVP

Telegram long-polling bot: location -> natural-language dish search -> cart -> COD order -> admin accept/reject/status.
Catalogue is local CSV (`data/`). Geoapify is used for address labels and an info-only "nearby places" fallback. Groq is only a parser fallback.

## Run
```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                   # fill in the 4 keys
python -m pytest -q                                    # optional sanity tests
python app.py
```
1. Open your bot in Telegram and press Start. The admin account (ADMIN_CHAT_ID) must also press Start once, otherwise Telegram will not let the bot message it.
2. Edit `data/restaurants.csv` so the sample coordinates are near you (or keep `service_radius_km` large).
3. Test: share location -> "I am hungry, I want shawarma under 200" -> Select -> Checkout -> Skip -> Confirm.

## Notes
- Only run one instance at a time (long polling).
- Get your numeric ID from @userinfobot. For a group admin, use the group's negative chat ID.
- Never commit `.env`. Rotate any key that has been shared in chat or screenshots.
- Ratings/ETAs are catalogue values, not live platform data. Sample restaurants are fictional.
