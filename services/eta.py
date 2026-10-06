from __future__ import annotations

def estimate_eta(
    distance_km: float,
    prep_minutes: int | float = 20,
    min_delivery_minutes: int | float = 10,
    minutes_per_km: int | float = 5,
    buffer_minutes: int | float = 10,
) -> tuple[int, int]:
    try:
        distance_km = float(distance_km or 0)
        prep_minutes = float(prep_minutes or 20)
        min_delivery_minutes = float(min_delivery_minutes or 10)
        minutes_per_km = float(minutes_per_km or 5)
        buffer_minutes = float(buffer_minutes or 10)
    except (TypeError, ValueError):
        distance_km = 0.0
        prep_minutes = 20.0
        min_delivery_minutes = 10.0
        minutes_per_km = 5.0
        buffer_minutes = 10.0

    travel_minutes = max(min_delivery_minutes, round(distance_km * minutes_per_km))
    eta_min = int(round(prep_minutes + travel_minutes))
    eta_max = int(round(eta_min + buffer_minutes))
    return eta_min, eta_max


def estimate_eta_minutes(
    distance_km: float,
    prep_minutes: int | float = 20,
    min_delivery_minutes: int | float = 10,
    minutes_per_km: int | float = 5,
    buffer_minutes: int | float = 10,
) -> tuple[int, int]:
    return estimate_eta(
        distance_km=distance_km,
        prep_minutes=prep_minutes,
        min_delivery_minutes=min_delivery_minutes,
        minutes_per_km=minutes_per_km,
        buffer_minutes=buffer_minutes,
    )
