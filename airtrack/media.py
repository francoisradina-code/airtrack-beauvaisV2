"""Logos des compagnies, photos et fiches des types d'appareils."""
from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

ASSETS = Path(__file__).resolve().parent.parent / "assets"

# Compagnie -> (code OACI, code IATA, couleur de repli)
AIRLINES = {
    "Ryanair": ("RYR", "FR", "#073590"),
    "Ryanair UK": ("RUK", "RK", "#073590"),
    "Wizz Air": ("WZZ", "W6", "#C6007E"),
    "Wizz Air Malta": ("WMT", "W4", "#C6007E"),
}


@lru_cache(maxsize=None)
def logo_data_uri(airline: str) -> str | None:
    """Logo embarqué (data URI) ; None si absent."""
    icao = AIRLINES.get(airline, (None,))[0]
    path = ASSETS / "logos" / f"{icao}.png"
    if not icao or not path.exists():
        return None
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


def logo_html(airline: str, size: int = 28) -> str:
    uri = logo_data_uri(airline)
    if uri:
        return f'<img src="{uri}" alt="{airline}" width="{size}" height="{size}" style="object-fit:contain;vertical-align:middle">'
    iata = AIRLINES.get(airline, ("", "?", "#5B6B82"))
    return (f'<span style="display:inline-flex;width:{size}px;height:{size}px;border-radius:6px;background:{iata[2]};'
            f'color:#fff;font-weight:700;font-size:11px;align-items:center;justify-content:center">{iata[1]}</span>')


def commons(file_name: str, width: int = 640) -> tuple[str, str]:
    """(URL de l'image redimensionnée, URL de la page Commons avec auteur et licence)."""
    name = quote(file_name.replace(" ", "_"))
    return (f"https://commons.wikimedia.org/wiki/Special:FilePath/{name}?width={width}",
            f"https://commons.wikimedia.org/wiki/File:{name}")


# Fiches des types d'appareils. Valeurs typiques (constructeur / configuration des compagnies opérant à BVA).
AIRCRAFT = {
    "B738": dict(nom="Boeing 737-800", famille="Boeing 737 Next Generation", sieges="189 (Ryanair)",
                 longueur="39,5 m", envergure="35,8 m", mtow="79 t", moteurs="2 × CFM56-7B", vapp="≈ 145 kt",
                 photo="Ryanair, EI-EXD, Boeing 737-8AS (31399910568).jpg",
                 legende="EI-EXD, l'avion du vol FR594/595 Porto du planning"),
    "B38M": dict(nom="Boeing 737 MAX 8-200", famille="Boeing 737 MAX", sieges="197 (Ryanair)",
                 longueur="39,5 m", envergure="35,9 m", mtow="82 t", moteurs="2 × CFM LEAP-1B", vapp="≈ 145 kt",
                 photo="Hamburg Airport Ryanair Boeing 737-8200 MAX EI-HGZ (DSC06013).jpg",
                 legende="EI-HGZ, l'avion du vol FR1083/1084 Lisbonne du planning"),
    "A320": dict(nom="Airbus A320", famille="Airbus A320ceo", sieges="180",
                 longueur="37,6 m", envergure="35,8 m", mtow="78 t", moteurs="2 × CFM56-5B / IAE V2500", vapp="≈ 138 kt",
                 photo="9H-LON Lauda Europe Airbus A320-214 close STN 161221.jpg",
                 legende="A320 Lauda Europe (même flotte que 9H-LMT et 9H-LOM, vols pour Ryanair)"),
    "A20N": dict(nom="Airbus A320neo", famille="Airbus A320neo", sieges="186 (Wizz Air)",
                 longueur="37,6 m", envergure="35,8 m", mtow="79 t", moteurs="2 × Pratt & Whitney PW1100G", vapp="≈ 136 kt",
                 photo="Airbus A320neo first takeoff at Toulouse Blagnac Airport 02.jpg",
                 legende="Airbus A320neo (photo du type, aux couleurs Airbus)"),
    "A321": dict(nom="Airbus A321", famille="Airbus A321ceo", sieges="230 (Wizz Air)",
                 longueur="44,5 m", envergure="35,8 m", mtow="93,5 t", moteurs="2 × IAE V2500", vapp="≈ 142 kt",
                 photo="Wizz Air, HA-LXP, Airbus A321-231 (52928095506).jpg",
                 legende="A321 Wizz Air, HA-LXP"),
    "A21N": dict(nom="Airbus A321neo", famille="Airbus A321neo", sieges="239 (Wizz Air)",
                 longueur="44,5 m", envergure="35,8 m", mtow="97 t", moteurs="2 × Pratt & Whitney PW1100G", vapp="≈ 140 kt",
                 photo="Wizz Air, HA-LVI, Airbus A321-271NX.jpg",
                 legende="A321neo Wizz Air, HA-LVI"),
}


def photo(type_code: str, width: int = 640) -> tuple[str, str, str] | None:
    """(url image, url page Commons, légende) pour un type OACI."""
    a = AIRCRAFT.get(type_code)
    if not a:
        return None
    img, page = commons(a["photo"], width)
    return img, page, a["legende"]
