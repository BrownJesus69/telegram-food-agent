# Map picker (Telegram Mini App)

Customers can choose a delivery address by dropping a pin on a map instead of typing: handy for a friend's place,
or a building the geocoder does not know. It is one static HTML file, no build step, no server, no cost.

## How it works

```
 address prompt                    Mini App (docs/miniapp/index.html)            bot
 ┌──────────────────────┐  tap     ┌───────────────────────────┐  sendData  ┌──────────────────────────┐
 │ [📍 Share location]  │ ───────► │ Leaflet + OpenStreetMap   │ ─────────► │ F.web_app_data handler   │
 │ [🗺 Pick on map]     │          │ tap / drag the pin        │  {lat,lon} │ parse + validate         │
 └──────────────────────┘          │ [Use this location]       │            │ same path as a GPS pin   │
                                   └───────────────────────────┘            └──────────────────────────┘
```

1. `foodbot/keyboards.py::location_request()` adds a **🗺 Pick on map** reply-keyboard button next to
   **📍 Share location**, but only when `MINIAPP_URL` is an `https://` URL. Every address prompt uses this keyboard.
   (`sendData()` only works for Mini Apps opened from a *reply-keyboard* button, which is why it is not an inline button.)
2. The page centres on Bengaluru, shows a draggable pin and the coordinates, and draws a dashed outline of the service
   area. Outside it, the pin turns red, a message explains why, and the button is disabled.
3. **Use this location** calls `Telegram.WebApp.sendData('{"lat":..,"lon":..}')`; Telegram delivers it to the bot as a
   service message and closes the Mini App.
4. `foodbot/address_flow.py::got_miniapp_pin` validates the payload, removes the map keyboard, then hands the point to
   the same `_handle_pin` that a shared GPS pin uses: Bengaluru bounding-box check, reverse geocoding, then the label
   (Home / Office / Friend / custom) and recipient steps. So ordering for someone else works exactly as before.

The page theme follows Telegram (`themeParams`, `colorScheme`); map tiles are inverted in dark mode.

## Hosting it free on GitHub Pages

The repo is already on GitHub, so Pages is the zero-cost option. Telegram requires HTTPS, which Pages provides.

1. Repository **Settings → Pages**.
2. **Source: Deploy from a branch**, branch `main`, folder **`/docs`** (the only folders Pages offers are `/` and `/docs`).
   The page lives in `docs/miniapp/`, so the URL is `https://<user>.github.io/<repo>/miniapp/` (the whole `docs/` folder is published,
   which is fine for a public repo; `docs/.nojekyll` turns off Jekyll processing).
3. Wait for the first deploy, open the URL in a browser (you should see the map and a "Preview only" note: it only
   becomes usable inside Telegram).
4. Put the URL in `.env`:

   ```
   MINIAPP_URL=https://<user>.github.io/<repo>/miniapp/
   ```

5. Restart the bot (`docker compose up -d --build`). The "🗺 Pick on map" button appears in the address prompts.
   Leave `MINIAPP_URL` empty to turn the feature off; nothing else changes.

No BotFather configuration is needed: a Mini App opened from a reply-keyboard button needs no registered short name.


## Privacy

- The only thing the page sends anywhere is `{"lat": ..., "lon": ...}`, to the bot, through Telegram. No name, phone
  number, Telegram ID, or address text is read by the page.
- The page has no backend and no analytics; GitHub Pages sees an ordinary page request.
- Loading the map contacts three third parties from the phone: `telegram.org` (the Web App script),
  `cdnjs.cloudflare.com` (Leaflet, pinned with Subresource Integrity hashes so a tampered file will not run) and
  `tile.openstreetmap.org` (map tiles, which reveal roughly what area is being viewed). The page makes no
  geolocation request; the pin starts at the city centre.
- OpenStreetMap's tile servers are for light use. Fine for a demo; for real traffic switch to a tile provider with a
  free tier and an API key, or self-host tiles.

## Threat notes: `web_app_data` is untrusted

The payload comes from the client. Anyone can send a bot a `web_app_data` message with any content (a modified page,
a script, or a different Mini App), so the bot treats it exactly like typed text:

| Risk | Control |
| --- | --- |
| Oversized or hostile body | Rejected above 256 bytes before parsing; the parser never raises |
| Non-JSON, wrong shape, extra nesting | `json.loads` failure or anything other than an object is rejected |
| Wrong types (`"12.9"`, `true`, `null`, arrays) | Only real numbers are accepted; booleans are excluded explicitly |
| `NaN`, `Infinity`, `1e999`, huge integers | `math.isfinite` check, and overflow is caught |
| Out-of-range values | Latitude within ±90, longitude within ±180 |
| Pin outside the service area | Same Bengaluru bounding box as a shared GPS pin; the page's own check is only a convenience |
| State corruption | A rejected payload changes nothing (no draft, awaiting step, or address is touched) |
| Injection into replies | Only numbers survive parsing; the address text is generated by the bot (reverse geocoding) and escaped as before |

A valid-looking but false location (someone picks a pin that is not theirs) is not a vulnerability: it is the feature,
because customers can order for someone else. The delivery address is confirmed by the customer on the confirm screen
before an order is placed.

The bounding box is duplicated in `docs/miniapp/index.html` (`BBOX`); `tests/test_miniapp.py` fails if it drifts from
`foodbot/geocoding.py::BENGALURU_BBOX`.

## Tests

`tests/test_miniapp.py` drives the real dispatcher with synthetic `web_app_data` updates: a valid pick reaches the label
prompt and saves like a GPS pin, an out-of-area pick is refused, a long list of malformed / oversized / NaN /
wrong-type payloads is rejected without exceptions or state changes, and the button appears only when `MINIAPP_URL` is
an `https://` URL.
