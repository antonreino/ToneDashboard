"""Rondas seguras de «Adivina el Pokémon» para el Dashboard."""
from __future__ import annotations

import json
import random
from urllib.request import Request, urlopen

POKEAPI = "https://pokeapi.co/api/v2/pokemon/{pokemon_id}"


def _fetch_pokemon(pokemon_id: int, opener=urlopen) -> dict:
    request = Request(POKEAPI.format(pokemon_id=pokemon_id), headers={"User-Agent": "ToneDashboard/1.2 (+local game)"})
    with opener(request, timeout=8) as response:
        payload = json.load(response)
    artwork = payload.get("sprites", {}).get("other", {}).get("official-artwork", {})
    image = artwork.get("front_default") or payload.get("sprites", {}).get("front_default")
    name = payload.get("name")
    if not isinstance(name, str) or not name or not isinstance(image, str) or not image.startswith("https://"):
        raise ValueError("Respuesta incompleta de PokéAPI")
    return {"id": pokemon_id, "name": name.replace("-", " ").title(), "image": image}


def new_round(opener=urlopen, chooser=None) -> dict:
    chooser = chooser or random.SystemRandom()
    identifiers = chooser.sample(range(1, 152), 4)
    pokemon = [_fetch_pokemon(identifier, opener) for identifier in identifiers]
    correct = chooser.choice(pokemon)
    return {
        "pokemon": {"id": correct["id"], "image": correct["image"]},
        "options": [{"id": item["id"], "name": item["name"]} for item in pokemon],
        "correct_id": correct["id"],
    }
