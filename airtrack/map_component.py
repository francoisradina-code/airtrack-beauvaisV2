"""Carte 3D animée : prépare les données et produit la page HTML (deck.gl + MapLibre) affichée dans Streamlit.

Toute l'animation tourne dans le navigateur : le mouvement est fluide (60 images/s) et le curseur
ne provoque aucun aller-retour avec le serveur.
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

from .media import AIRCRAFT, AIRLINES, logo_data_uri

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = Path(__file__).resolve().parent / "map_template.html"

# Bibliothèques JavaScript (versions figées). Variable d'environnement AIRTRACK_LIB_BASE : copies locales (tests).
LIBS = {
    "__MAPLIBRE_CSS__": "https://unpkg.com/maplibre-gl@5.24.0/dist/maplibre-gl.css",
    "__MAPLIBRE_JS__": "https://unpkg.com/maplibre-gl@5.24.0/dist/maplibre-gl.js",
    "__DECK_JS__": "https://unpkg.com/deck.gl@9.3.11/dist.min.js",
}

RUNWAY = {"thr12": [2.10385, 49.45830], "thr30": [2.13174, 49.44620]}   # seuils réels (OurAirports)
CENTER = [(2.10385 + 2.13174) / 2, (49.45830 + 49.44620) / 2]
ELEV_FT = 359


def _model_uri(name: str) -> str:
    data = (ROOT / "assets" / "models" / name).read_bytes()
    return "data:model/gltf-binary;base64," + base64.b64encode(data).decode()


def build_payload(traj: pd.DataFrame, vols: pd.DataFrame, phase_labels: dict[str, str]) -> dict:
    phases = sorted(traj.phase.unique())
    ph_idx = {p: i for i, p in enumerate(phases)}
    info = vols.set_index("flight_id")
    flights = []
    for fid, g in traj.sort_values(["flight_id", "t_local_s"]).groupby("flight_id", sort=False):
        r = info.loc[fid]
        flights.append(dict(
            id=fid, vol=r.vol, sens=r.sens, cie=r.compagnie, iata=AIRLINES.get(r.compagnie, ("", "?"))[1],
            type=r.type_avion, type_nom=AIRCRAFT.get(r.type_avion, {}).get("nom", r.type_avion), immat=r.immat,
            ville=r.aeroport_lie_ville, ev=int(r.t_event_s),
            t=np.round(g.t_local_s.to_numpy(float), 1).tolist(),
            lon=np.round(g.lon.to_numpy(float), 5).tolist(), lat=np.round(g.lat.to_numpy(float), 5).tolist(),
            alt=g.alt_ft.astype(int).tolist(), gs=g.gs_kt.astype(int).tolist(), hdg=g.heading_deg.astype(int).tolist(),
            ph=[ph_idx[p] for p in g.phase],
        ))
    t0 = np.array([f["t"][0] for f in flights]); t1 = np.array([f["t"][-1] for f in flights])
    centers = np.arange(1440) * 60 + 30
    conc = ((t0[None, :] <= centers[:, None]) & (centers[:, None] <= t1[None, :])).sum(axis=1)
    peak_min = int(np.argmax(conc))
    events = sorted(int(v) for v in vols.t_event_s)
    return dict(
        flights=flights, phases=[phase_labels.get(p, p) for p in phases], conc=conc.tolist(),
        peak_s=peak_min * 60 + 30, start_s=peak_min * 60 + 30, events=events,
        ticks=[dict(t=int(r.t_event_s), s=r.sens) for r in vols.itertuples()],
        logos={c: logo_data_uri(c) for c in vols.compagnie.unique() if logo_data_uri(c)},
        models={"ARR": _model_uri("plane_arr.glb"), "DEP": _model_uri("plane_dep.glb")},
        runway=RUNWAY, center=CENTER, elev_ft=ELEV_FT,
    )


def render_html(payload: dict) -> str:
    html = TEMPLATE.read_text(encoding="utf-8")
    base = os.environ.get("AIRTRACK_LIB_BASE")
    for key, url in LIBS.items():
        if base:   # ex. http://localhost:8765 -> copies locales pour les tests hors ligne
            url = url.replace("https://unpkg.com", base.rstrip("/"))
        html = html.replace(key, url)
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return html.replace("__DATA__", data)
