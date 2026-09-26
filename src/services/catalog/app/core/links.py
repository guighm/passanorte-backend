"""Deep links externos a partir de coordenadas (RF28, D-07) — T021."""

from __future__ import annotations


def build_external_links(latitude: float, longitude: float, spot_name: str) -> dict[str, str]:
    """Links para apps externos: mapas e transporte (sem API server-side).

    A cota gratuita do Google Maps é limitada (Proposta §4): os links não
    consomem chamadas de API — são URLs de redirecionamento para o cliente.
    """
    name = spot_name.replace(" ", "+")
    dest = f"{latitude},{longitude}"
    return {
        "google_maps": f"https://www.google.com/maps/dir/?api=1&destination={dest}",
        "uber": f"https://m.uber.com/?action=setPickup&pickup=my_location&dropoff[formatted_address]={name}&dropoff[latitude]={latitude}&dropoff[longitude]={longitude}",
        "ninenine": f"https://99app.com/?dest={dest}",
    }
