#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Génération d'un FAUX jeu de données de trajectoires – Paris-Beauvais (LFOB), piste 12
====================================================================================

Objectif : démontrer la chaîne « planning du jour  ->  trajectoires 3D  ->  application »
quand on ne dispose pas des vraies données ADS-B.

MÉTHODE (résumé)
1. Planning : on lit le planning réel du 12/10/2026 (57 arrivées + 57 départs).
2. Heures d'événement : arrivée = heure d'atterrissage à BVA ; départ = heure de décollage,
   déduite de l'heure d'atterrissage à destination moins la durée de vol.
   Les heures manquantes sont imputées ; les conflits de piste sont résolus (séparations min.).
3. Corridors : 6 familles d'arrivées et 7 familles de départs, tracées d'après la carte
   DGAC/DSNA « Beauvais Tillé – Face à l'Est – 20 juin 2025 » (piste 12), calées en km autour de
   l'ARP (échelle 30 px/km sur le rendu 150 dpi). Chaque vol reçoit un corridor (tirage pondéré
   par la densité observée et le cap vers son aéroport), puis une variation latérale aléatoire.
4. Profils verticaux et vitesses (continus) calés sur les couleurs d'altitude de la carte
   (0-1000 m / 1001-2000 / 2001-3000 / 3001-4000) et sur les vitesses classiques :
     arrivée : 250 kt IAS -> ~175-190 kt (configuration) -> Vapp ~140 kt (finale ILS 3°) -> arrêt ;
     départ  : accélération au sol (V ∝ √distance) -> rotation ~150 kt -> 250 kt IAS.
   Vitesse sol = IAS × (1 + 1,65 %/1000 ft). Le temps est obtenu en intégrant ds/v le long de
   la trajectoire : positions, altitudes et vitesses sont mutuellement cohérentes.
5. Échantillonnage 1 point / 5 s (comme un flux ADS-B), léger bruit de mesure.

ZONE D'ÉTUDE : cercle de 25 NM autour de l'ARP ; plafond 15 000 ft.

ATTENTION : trajectoires SYNTHÉTIQUES. L'appariement vol <-> corridor est plausible mais n'est
pas la trajectoire réellement volée.

Utilisation (Colab ou local) :
    pip install numpy pandas scipy
    python generate_fake_dataset.py --planning planning_LFOB_2026-10-12.csv --out .
Sorties : trajectoires_LFOB_2026-10-12.csv  et  vols_LFOB_2026-10-12.csv
"""
from __future__ import annotations

import argparse
import zlib
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.interpolate import PchipInterpolator, splev, splprep

# ----------------------------------------------------------------------------- constantes
KM_PER_NM = 1.852
FT_PER_M = 3.280839895
# Origine du repère = centre de la piste 12/30 (seuils OurAirports : THR12 49.45830 N 2.10385 E,
# THR30 49.44620 N 2.13174 E). La carte DGAC a été calée sur ce centre de piste.
ARP_LAT, ARP_LON, ARP_ELEV_FT = 49.45225, 2.117795, 359.0  # LFOB, centre de piste
KM_PER_DEG_LAT = 111.22
KM_PER_DEG_LON = 72.48                                        # à 49,45° N
RWY_HDG = 123.65                   # cap vrai de la piste 12 (calculé entre les deux seuils)
RWY_HALF_KM = 1.214                # piste de 2 428 m
ZONE_R_KM = 25 * KM_PER_NM         # 46,3 km
ZONE_CEILING_FT = 15000
STEP_S = 5                         # pas d'échantillonnage (s)
DS_KM = 0.04                       # pas de la trajectoire dense (40 m)
UTC_OFFSET_H = 2                   # CEST
SEED = 2026
R_MIN_KM = 2.0          # arrivées : rayon de virage minimal (≈ 200 kt à ~28° d'inclinaison)
R_MIN_DEP_KM = 1e-6     # départs : pas de lissage supplémentaire (arcs de ~1,7 km déjà dans les points)

U = np.array([np.sin(np.radians(RWY_HDG)), np.cos(np.radians(RWY_HDG))])   # vers le SE
T12 = -RWY_HALF_KM * U            # seuil piste 12 (extrémité NO), repère km centré sur l'ARP

ACFT = {
    "B738": dict(vapp=143, vr=148, climb=1.00),
    "B38M": dict(vapp=146, vr=150, climb=1.06),
    "A320": dict(vapp=138, vr=145, climb=1.00),
    "A20N": dict(vapp=138, vr=145, climb=1.06),
    "A321": dict(vapp=141, vr=150, climb=0.90),
    "A21N": dict(vapp=142, vr=150, climb=0.92),
}

AIRPORTS = {
    "LPPR": (41.248, -8.681), "LPPT": (38.781, -9.136), "EGBB": (52.454, -1.748), "LRTR": (45.810, 21.338),
    "LEVC": (39.489, -0.482), "LMML": (35.858, 14.477), "LIRN": (40.886, 14.291), "LBSF": (42.695, 23.406),
    "LYTV": (42.405, 18.723), "EIDW": (53.421, -6.270), "UGKO": (42.177, 42.483), "LICC": (37.467, 15.066),
    "LEBL": (41.297, 2.078), "LDZA": (45.743, 16.069), "EGAA": (54.658, -6.216), "ESSA": (59.652, 17.919),
    "UDYZ": (40.147, 44.396), "LEGE": (41.901, 2.761), "EPKK": (50.078, 19.785), "LIPH": (45.648, 12.194),
    "EPWR": (51.103, 16.886), "LGTS": (40.520, 22.971), "LEAL": (38.282, -0.558), "LYBE": (44.818, 20.309),
    "LYPG": (42.359, 19.252), "LIRP": (43.684, 10.393), "LOWW": (48.110, 16.570), "GMFO": (34.787, -1.924),
    "LIRF": (41.800, 12.239), "GMFF": (33.927, -4.978), "GMTT": (35.727, -5.917), "LRCL": (46.785, 23.686),
    "LIMC": (45.631, 8.723), "LFKF": (41.501, 9.098), "LATI": (41.415, 19.721), "GMMX": (31.607, -8.036),
    "EGCC": (53.354, -2.275), "GCTS": (28.045, -16.573), "LCPH": (34.718, 32.486), "LROP": (44.571, 26.085),
    "LUKK": (46.928, 28.931), "LIME": (45.674, 9.704), "EICK": (51.841, -8.491), "EKCH": (55.618, 12.656),
    "EPPO": (52.421, 16.826), "LRTM": (46.468, 24.413), "LRIA": (47.179, 27.621), "LIPE": (44.535, 11.289),
    "GMMI": (31.398, -9.682), "LDDU": (42.561, 18.268),
}

COUNTRY_BY_REG = {"EI": "Irlande", "9H": "Malte", "SP": "Pologne", "HA": "Hongrie", "G": "Royaume-Uni"}


# ----------------------------------------------------------------------------- géométrie
def km_to_latlon(x, y):
    return ARP_LAT + np.asarray(y) / KM_PER_DEG_LAT, ARP_LON + np.asarray(x) / KM_PER_DEG_LON


def bearing_dist(icao):
    lat, lon = AIRPORTS[icao]
    p1, p2, dl = np.radians(ARP_LAT), np.radians(lat), np.radians(lon - ARP_LON)
    brg = np.degrees(np.arctan2(np.sin(dl) * np.cos(p2),
                                np.cos(p1) * np.sin(p2) - np.sin(p1) * np.cos(p2) * np.cos(dl))) % 360
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    dist = 2 * 6371.0 * np.arcsin(np.sqrt(a))
    return brg, dist


def axis_pt(d_km):
    """Point de l'axe d'approche à d km AVANT le seuil 12 (d<0 : après le seuil)."""
    return T12 - U * d_km


# ----------------------------------------------------------------------------- corridors (km, x=Est, y=Nord)
ARR_TEMPLATES = {
    "A_NO_axe": [(*axis_pt(54), 1.2), (*axis_pt(40), 1.0), (*axis_pt(28), 0.9), (*axis_pt(18), 0.5), (*axis_pt(12), 0.2)],
    "A_O": [(-52, 9.0, 2.0), (-38, 10.5, 2.0), (-26, 10.8, 1.5), (-17, 10.0, 0.9), (*axis_pt(13), 0.2)],
    "A_E_NE": [(52, 16.5, 2.0), (32, 17.5, 2.0), (12, 18.3, 1.5), (-6, 18.8, 1.2), (-15, 17.8, 0.8),
               (-19, 14.3, 0.6), (-16.2, 10.3, 0.4), (*axis_pt(11), 0.2)],
    "A_N": [(8, 53, 2.0), (-1, 38, 1.8), (-9, 26, 1.2), (-16.5, 17.5, 0.8), (-17.5, 12.5, 0.5),
            (-15, 9.3, 0.4), (*axis_pt(11), 0.2)],
    "A_SO": [(-36, -34, 2.5), (-26, -21, 2.0), (-17, -10, 1.2), (-12.5, -2.0, 0.6), (-10.5, 3.5, 0.4),
             (*axis_pt(8), 0.15)],
    "A_S": [(-8, -52, 2.0), (-12, -34, 1.8), (-14, -18, 1.0), (-12.5, -6, 0.6), (-10.8, 2.8, 0.4),
            (*axis_pt(8), 0.15)],
}

_ARC = "(2.76, -1.53, 0.05), (3.96, -1.03, 0.1), (4.46, 0.17, 0.15), (4.6, 1.6, 0.2)"
DEP_TEMPLATES = {
    "D_SE": dict(pts=[(3.2, -2.2, 0.1), (9, -6.2, 0.4), (15, -9.4, 0.7), (22, -12.3, 1.0), (31, -15.2, 1.4),
                      (41, -18.5, 1.8), (55, -23.0, 2.0)], climb=0.82),
    "D_S": dict(pts=[(3.2, -2.2, 0.1), (9, -6.2, 0.4), (14, -9.5, 0.7), (16.8, -14.5, 0.8), (17.8, -25, 1.0),
                     (18.5, -38, 1.5), (19, -55, 2.0)], climb=0.95),
    "D_E": dict(pts=[(3.0, -1.6, 0.1), (6.0, -1.4, 0.25), (11, -1.2, 0.35), (18, -0.8, 0.5), (26, -0.2, 0.7),
                     (38, 1.2, 1.2), (55, 3.5, 1.8)], climb=1.15),
    "D_NE": dict(pts=[(3.2, -1.6, 0.1), (7, -0.4, 0.3), (12, 3.0, 0.6), (20, 8.5, 1.0), (31, 15.5, 1.5),
                      (42, 23.5, 2.0), (52, 31, 2.0)], climb=1.05),
    "D_N": dict(pts=[(2.76, -1.53, 0.05), (3.96, -1.03, 0.1), (4.46, 0.17, 0.15), (4.6, 1.6, 0.2),
                     (4.2, 3.4, 0.3), (3.2, 5.6, 0.4), (2.3, 9, 0.5),
                     (1.7, 16, 0.7), (1.4, 28, 0.9), (1.2, 42, 1.2), (1.0, 56, 1.5)], climb=1.0),
    "D_NO": dict(pts=[(2.76, -1.53, 0.05), (3.96, -1.03, 0.1), (4.46, 0.17, 0.15), (4.6, 1.6, 0.2),
                      (4.2, 3.4, 0.3), (3.2, 5.6, 0.4), (2.2, 10, 0.6),
                      (-0.5, 18, 1.0), (-6, 28, 1.5), (-14, 39, 2.0), (-21, 49, 2.0)], climb=1.0),
    "D_SO": dict(pts=[(2.76, -1.53, 0.05), (3.96, -1.03, 0.1), (4.46, 0.17, 0.15), (4.6, 1.6, 0.2),
                      (4.7, 3.2, 0.25), (3.9, 5.0, 0.25), (1.8, 5.9, 0.25), (-1.2, 5.7, 0.3),
                      (-5.2, 4.2, 0.4), (-9.0, 0.6, 0.5), (-14.5, -4.5, 0.8), (-25, -13.5, 1.5),
                      (-38, -23.5, 2.0), (-50, -32, 2.5)], climb=1.0),
}


def ang_diff(a, b):
    return abs((a - b + 180) % 360 - 180)


def pick_template(sens, brg, rng):
    """Tirage pondéré : a priori (densité observée sur la carte) × proximité du cap du corridor
    avec le cap vers l'aéroport du vol (cohérence géographique douce)."""
    if sens == "ARR":
        sectors = {"A_NO_axe": (305, 0.30), "A_O": (270, 0.12), "A_E_NE": (60, 0.20),
                   "A_N": (5, 0.10), "A_SO": (215, 0.18), "A_S": (180, 0.10)}
    else:
        sectors = {"D_SE": (125, 0.22), "D_S": (185, 0.08), "D_E": (85, 0.22), "D_NE": (45, 0.08),
                   "D_N": (5, 0.16), "D_NO": (320, 0.10), "D_SO": (235, 0.18)}
    names = list(sectors)
    d = np.array([ang_diff(brg, sectors[n][0]) for n in names], float)
    w = np.array([sectors[n][1] for n in names]) * (0.15 + np.exp(-(d / 45.0) ** 2))
    w /= w.sum()
    return names[rng.choice(len(names), p=w)]


# ----------------------------------------------------------------------------- trajectoires
def limit_curvature(x, y, protect_start_km=0.0, protect_end_km=0.0, iters=150, ramp_km=2.0, r_min=R_MIN_KM):
    """Lisse localement la trajectoire tant que le rayon de courbure est < r_min.
    Le lissage est appliqué avec un poids qui part de 0 au bord d'une zone protégée (piste / finale)
    et monte progressivement sur `ramp_km` : aucune discontinuité."""
    n = len(x)
    ds = DS_KM
    idx = np.arange(n)
    w = np.ones(n)
    if protect_start_km > 0:
        w = np.minimum(w, np.clip((idx * ds - protect_start_km) / ramp_km, 0, 1))
    if protect_end_km > 0:
        w = np.minimum(w, np.clip(((n - 1 - idx) * ds - protect_end_km) / ramp_km, 0, 1))
    w = w * w * (3 - 2 * w)
    half = 12
    gk = np.exp(-0.5 * (np.arange(-3 * half, 3 * half + 1) / half) ** 2); gk /= gk.sum()
    xs, ys = x.copy(), y.copy()
    for _ in range(iters):
        dx, dy = np.gradient(xs, ds), np.gradient(ys, ds)
        ddx, ddy = np.gradient(dx, ds), np.gradient(dy, ds)
        kappa = np.abs(dx * ddy - dy * ddx) / np.maximum((dx ** 2 + dy ** 2) ** 1.5, 1e-9)
        bad = (kappa > 1.0 / r_min) & (w > 0.05)
        if not bad.any():
            break
        m = (np.convolve(bad.astype(float), np.ones(2 * 25 + 1), mode="same") > 0).astype(float)
        xg = np.convolve(np.pad(xs, 3 * half, mode="edge"), gk, mode="valid")
        yg = np.convolve(np.pad(ys, 3 * half, mode="edge"), gk, mode="valid")
        xs = xs + 0.5 * m * (xg - xs)
        ys = ys + 0.5 * m * (yg - ys)
    return x + w * (xs - x), y + w * (ys - y)


def build_path(wps, rng, jitter_scale=1.0, protect_start_km=0.0, protect_end_km=0.0, r_min=R_MIN_KM):
    """Spline cubique passant par les points (jitter latéral), ré-échantillonnée tous les DS_KM."""
    pts = np.array([(x, y) for x, y, _ in wps], float)
    sig = np.array([s for *_, s in wps], float) * jitter_scale
    tang = np.gradient(pts, axis=0)
    nrm = np.stack([-tang[:, 1], tang[:, 0]], axis=1)
    nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-9
    off = rng.normal(0, 1, len(pts))
    off = np.convolve(np.pad(off, 1, mode="edge"), [0.25, 0.5, 0.25], mode="valid") * sig * 1.4
    pts = pts + nrm * off[:, None]
    seg = np.r_[0, np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))]
    keep = np.r_[True, np.diff(seg) > 0.2]
    pts, seg = pts[keep], seg[keep]
    tck, _ = splprep([pts[:, 0], pts[:, 1]], u=seg, s=0, k=3)
    s_dense = np.arange(0, seg[-1], DS_KM)
    x, y = splev(s_dense, tck)
    x, y = limit_curvature(np.array(x), np.array(y), protect_start_km, protect_end_km, r_min=r_min)
    s_dense = np.r_[0, np.cumsum(np.hypot(np.diff(x), np.diff(y)))]
    return x, y, s_dense


def rms_noise(rng, n, sigma, corr=6):
    """Bruit lissé (autocorrélé) pour éviter les dents de scie."""
    z = rng.normal(0, 1, n + 2 * corr)
    k = np.ones(2 * corr + 1) / (2 * corr + 1)
    z = np.convolve(z, k, mode="same")[corr:-corr]
    return z / (z.std() + 1e-9) * sigma


def tas_factor(alt_ft):
    return 1.0 + 0.0165 * alt_ft / 1000.0


def arrival_track(wps, ac, rng, t_td):
    """Trajectoire d'arrivée ; t_td = heure du toucher des roues (s depuis minuit local)."""
    p = ACFT[ac]
    last_d = float(np.dot(T12 - np.array(wps[-1][:2]), U))
    tail = [(*axis_pt(d), 0.0) for d in (9, 6, 3, 1.2) if d < last_d - 1.0]
    tail += [(*axis_pt(0), 0.0), (*axis_pt(-1.2), 0.0), (*axis_pt(-2.0), 0.0)]
    x, y, s = build_path(wps + tail, rng, protect_end_km=14.0)
    i_thr = np.argmin(np.hypot(x - T12[0], y - T12[1]))
    d = (s[i_thr] - s)                       # km avant le seuil
    alt_gp = rng.uniform(2600, 3100)
    d_gp = (alt_gp - 409) / 172.0            # 3° = 172 ft/km
    cap = rng.uniform(9000, 10800)
    sl = rng.uniform(0.9, 1.15)
    tab_d = np.array([-3, -0.45, 0.0, d_gp, d_gp + 8, d_gp + 20, d_gp + 32, d_gp + 60, d_gp + 120])
    tab_a = np.array([ARP_ELEV_FT, ARP_ELEV_FT, ARP_ELEV_FT + 50, alt_gp, alt_gp + 450 * sl,
                      alt_gp + 2400 * sl, alt_gp + 4900 * sl, cap, cap + 1000])
    alt = PchipInterpolator(tab_d, np.minimum(tab_a, cap + 500))(np.clip(d, -3, d_gp + 120))
    alt = np.minimum(alt, cap)
    alt[d < -0.45] = ARP_ELEV_FT
    va = p["vapp"] + rng.uniform(-3, 4)
    tab_dv = np.array([-3, -2.0, -1.3, -0.45, 0.0, 3, 6, 9, 12, 16, 20, 26, 32, 40, 120])
    tab_v = np.array([18, 24, 55, va - 5, va, va + 2, va + 8, va + 20, 175 + rng.uniform(-6, 6), 190, 205, 222,
                      240, 250, 250])
    ias = PchipInterpolator(tab_dv, tab_v)(np.clip(d, -3, 120))
    gs = ias * tas_factor(alt)
    v_kms = np.maximum(gs, 12) * KM_PER_NM / 3600.0
    dt = DS_KM / (0.5 * (v_kms[1:] + v_kms[:-1]))
    t_rel = np.r_[0, np.cumsum(dt)]
    i_td = np.argmin(np.abs(d + 0.45))
    t = t_rel - t_rel[i_td] + t_td
    r = np.hypot(x, y)
    inside = np.where(r <= ZONE_R_KM)[0]
    i0 = inside[0]
    sl_ = slice(i0, None)
    return dict(x=x[sl_], y=y[sl_], alt=alt[sl_], gs=gs[sl_], t=t[sl_], d=d[sl_], s=s[sl_]), d_gp


def departure_track(tpl, ac, rng, t_lo):
    """Trajectoire de départ ; t_lo = heure de décollage (lift-off), s depuis minuit local."""
    p = ACFT[ac]
    run = [(*(T12 + k * U), 0.0) for k in (0.2, 0.9, 1.6, 2.4, 3.4)]
    x, y, s = build_path(run + tpl["pts"], rng, protect_start_km=2.2, r_min=R_MIN_DEP_KM)
    s_lo = rng.uniform(1.85, 2.15)            # distance de roulage jusqu'à la rotation (km)
    vr = p["vr"] + rng.uniform(-3, 4) + 5
    sa = s - 0.0
    tab_s = np.array([s_lo, s_lo + 0.6, s_lo + 3.0, s_lo + 7.0, s_lo + 11, s_lo + 15, s_lo + 20, s_lo + 28, s_lo + 200])
    tab_v = np.array([vr, vr + 8, 172, 190, 218, 240, 250, 250, 250])
    ias_air = PchipInterpolator(tab_s, tab_v)(np.clip(sa, s_lo, s_lo + 200))
    ias = np.where(sa < s_lo, vr * np.sqrt(np.maximum(sa, DS_KM * 0.25) / s_lo), ias_air)
    sl_ = (s - s_lo)
    fac = tpl["climb"] * p["climb"] * rng.uniform(0.9, 1.12)
    tab_k = np.array([0, 1.5, 3.7, 5.6, 9.3, 13, 18.5, 26, 33, 41.5, 55, 75, 120])
    tab_h = np.array([0, 450, 1000, 1500, 2500, 3500, 5100, 6800, 8000, 9300, 10800, 12600, 14000])
    alt = ARP_ELEV_FT + np.interp(np.clip(sl_, 0, 120), tab_k, tab_h) * fac
    alt[sl_ < 0] = ARP_ELEV_FT
    ias = ias + 15 * np.clip((alt - 10000) / 3000, 0, 1) * (sl_ > 0)
    gs = ias * tas_factor(alt)
    v_kms = np.maximum(gs, 1.0) * KM_PER_NM / 3600.0
    dt = DS_KM / (0.5 * (v_kms[1:] + v_kms[:-1]))
    t_rel = np.r_[0, np.cumsum(dt)]
    i_lo = np.argmin(np.abs(sl_))
    t = t_rel - t_rel[i_lo] + t_lo
    r = np.hypot(x, y)
    out = np.where((r > ZONE_R_KM) | (alt > ZONE_CEILING_FT))[0]
    out = out[out > 0]
    i1 = out[0] if len(out) else len(x) - 1
    sl2 = slice(0, i1 + 1)
    return dict(x=x[sl2], y=y[sl2], alt=alt[sl2], gs=gs[sl2], t=t[sl2], d=sl_[sl2], s=s[sl2])


def sample(tr, sens, rng, d_gp=None):
    """Échantillonne 1 pt / STEP_S, calcule cap et taux de montée, ajoute un léger bruit de mesure."""
    t = tr["t"]
    t0 = np.ceil(t[0] / STEP_S) * STEP_S + rng.uniform(0, STEP_S)
    ts = np.arange(t0, t[-1], STEP_S)
    ts = ts[(ts > t[0] + 2.0) & (ts < t[-1] - 2.0)]       # pas de points quasi confondus avec les extrémités
    ts = np.r_[t[0], ts, t[-1]]
    x = np.interp(ts, t, tr["x"]); y = np.interp(ts, t, tr["y"])
    alt = np.interp(ts, t, tr["alt"]); gs = np.interp(ts, t, tr["gs"]); d = np.interp(ts, t, tr["d"])
    dx = np.gradient(tr["x"], tr["t"]); dy = np.gradient(tr["y"], tr["t"])
    hdg_dense = np.degrees(np.arctan2(dx, dy)) % 360
    hdg_u = np.unwrap(np.radians(hdg_dense))
    hdg = np.degrees(np.interp(ts, t, hdg_u)) % 360
    vs = np.gradient(tr["alt"], tr["t"]) * 60.0
    vs = np.convolve(np.pad(vs, 25, mode="edge"), np.ones(51) / 51, mode="valid")
    vs = np.interp(ts, t, vs)
    on_ground = alt <= ARP_ELEV_FT + 5
    n = len(ts)
    x = x + rms_noise(rng, n, 0.012); y = y + rms_noise(rng, n, 0.012)
    alt_n = alt + np.where(on_ground, 0, rms_noise(rng, n, 25, 3))
    gs_n = gs + np.where(on_ground, 0, rms_noise(rng, n, 1.5, 3))
    hdg_n = hdg + rms_noise(rng, n, 0.4, 3)
    vs_n = vs + rms_noise(rng, n, 40, 3)
    if sens == "ARR":
        phase = np.where(on_ground, "roulage_atterrissage",
                 np.where(d <= d_gp, "finale_ILS_piste12",
                 np.where(d <= 30, "approche_intermediaire", "arrivee_descente")))
    else:
        phase = np.where(on_ground, "roulage_decollage",
                 np.where(alt < ARP_ELEV_FT + 1500, "montee_initiale",
                 np.where(alt < 10000, "montee_depart", "montee_en_route")))
    alt_r = np.where(on_ground, ARP_ELEV_FT, np.round(alt_n / 25) * 25)
    return pd.DataFrame(dict(
        t_local_s=np.round(ts, 1), x_km=np.round(x, 3), y_km=np.round(y, 3),
        alt_ft=alt_r.astype(int), gs_kt=np.round(np.maximum(gs_n, 0)).astype(int),
        heading_deg=np.round(hdg_n % 360).astype(int),
        vs_fpm=(np.round(vs_n / 64) * 64).astype(int), phase=phase, on_ground=on_ground,
        dist_arp_nm=np.round(np.hypot(x, y) / KM_PER_NM, 2)))


# ----------------------------------------------------------------------------- planning
def hhmm_to_s(txt):
    h, m = map(int, txt.split(":"))
    return (h * 60 + m) * 60


def prepare_events(plan: pd.DataFrame) -> pd.DataFrame:
    df = plan.copy()
    df["time_imputed"] = df["heure_liste"].isna()
    for sens in ("ARR", "DEP"):
        idx = df.index[df.sens == sens]
        t = df.loc[idx, "heure_liste"].map(lambda v: hhmm_to_s(v) if isinstance(v, str) else np.nan).to_numpy(float).copy()
        for k in np.where(np.isnan(t))[0]:
            up = next((t[j] for j in range(k - 1, -1, -1) if not np.isnan(t[j])), None)
            dn = next((t[j] for j in range(k + 1, len(t)) if not np.isnan(t[j])), None)
            t[k] = np.mean([v for v in (up, dn) if v is not None])
        df.loc[idx, "t_liste_s"] = t
    brg_dist = df["icao"].map(bearing_dist)
    df["cap_vers_aeroport"] = brg_dist.map(lambda v: round(v[0], 1))
    df["distance_km"] = brg_dist.map(lambda v: round(v[1], 1))
    est_air = df["distance_km"] / 760.0 * 60 + 12
    air = np.maximum(df["duree_vol_min"], 0.85 * est_air)
    df["t_event_planifie_s"] = np.where(df.sens == "ARR", df["t_liste_s"], df["t_liste_s"] - air * 60)
    return df


def deconflict(df: pd.DataFrame) -> pd.DataFrame:
    """Séparations minimales sur la piste unique (secondes)."""
    gap = {("ARR", "ARR"): 100, ("ARR", "DEP"): 75, ("DEP", "ARR"): 80, ("DEP", "DEP"): 95}
    order = df.sort_values("t_event_planifie_s", kind="stable").index
    t_final = {}
    prev_t, prev_s = None, None
    for i in order:
        t = df.at[i, "t_event_planifie_s"]
        s = df.at[i, "sens"]
        if prev_t is not None:
            t = max(t, prev_t + gap[(prev_s, s)])
        t_final[i] = t
        prev_t, prev_s = t, s
    df["t_event_s"] = pd.Series(t_final)
    df["decalage_s"] = (df["t_event_s"] - df["t_event_planifie_s"]).round(0).astype(int)
    return df


def fmt_local(sec):
    h, rem = divmod(int(round(sec)), 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


# ----------------------------------------------------------------------------- main
def main(planning_csv, out_dir):
    out = Path(out_dir)
    plan = pd.read_csv(planning_csv)
    ev = deconflict(prepare_events(plan))
    date = "2026-10-12"
    rows, meta = [], []
    for i, r in ev.sort_values("t_event_s").iterrows():
        seed = zlib.crc32(f"{r.vol}-{r.sens}-{SEED}".encode())
        rng = np.random.default_rng(seed)
        brg = r.cap_vers_aeroport
        tid = pick_template(r.sens, brg, rng)
        flight_id = f"{r.vol}_{date.replace('-', '')}_{r.sens}"
        if r.sens == "ARR":
            tr, d_gp = arrival_track(ARR_TEMPLATES[tid], r.type_avion, rng, r.t_event_s)
        else:
            tr = departure_track(DEP_TEMPLATES[tid], r.type_avion, rng, r.t_event_s)
            d_gp = None
        df = sample(tr, r.sens, rng, d_gp)
        lat, lon = km_to_latlon(df.pop("x_km"), df.pop("y_km"))
        df.insert(0, "flight_id", flight_id)
        df.insert(1, "lat", np.round(lat, 5)); df.insert(2, "lon", np.round(lon, 5))
        rows.append(df)
        reg = r.immat
        pref = reg.split("-")[0]
        meta.append(dict(
            flight_id=flight_id, vol=r.vol, sens=r.sens, runway=12,
            compagnie=r.compagnie, type_avion=r.type_avion, immat=reg,
            pays_immat=COUNTRY_BY_REG.get(pref, pref),
            aeroport_lie_ville=r.ville, aeroport_lie_icao=r.icao, aeroport_lie_iata=r.iata,
            cap_vers_aeroport_deg=r.cap_vers_aeroport, distance_km=r.distance_km,
            duree_vol_liste_min=r.duree_vol_min,
            heure_liste=r.heure_liste if isinstance(r.heure_liste, str) else "",
            heure_imputee=bool(r.time_imputed),
            heure_evenement_planifiee=fmt_local(r.t_event_planifie_s),
            heure_evenement_retenue=fmt_local(r.t_event_s), decalage_conflit_s=int(r.decalage_s),
            evenement="atterrissage" if r.sens == "ARR" else "decollage",
            corridor=tid, n_points=len(df),
            entree_zone_local=fmt_local(df.t_local_s.iloc[0]), sortie_zone_local=fmt_local(df.t_local_s.iloc[-1]),
            alt_max_ft=int(df.alt_ft.max()), vitesse_max_kt=int(df.gs_kt.max()),
        ))
    traj = pd.concat(rows, ignore_index=True)
    midnight_utc = pd.Timestamp(f"{date} 00:00:00") - pd.Timedelta(hours=UTC_OFFSET_H)
    traj.insert(1, "timestamp_utc", (midnight_utc + pd.to_timedelta(traj.t_local_s, unit="s"))
                .dt.strftime("%Y-%m-%dT%H:%M:%S.%f").str[:-5] + "Z")
    traj.insert(traj.columns.get_loc("alt_ft") + 1, "alt_m", np.round(traj.alt_ft / FT_PER_M).astype(int))
    meta = pd.DataFrame(meta)
    f_t = out / f"trajectoires_LFOB_{date}.csv"
    f_v = out / f"vols_LFOB_{date}.csv"
    traj.to_csv(f_t, index=False)
    meta.to_csv(f_v, index=False, encoding="utf-8")
    print(f"{len(meta)} vols, {len(traj)} points -> {f_t.name}, {f_v.name}")
    return traj, meta


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--planning", default="planning_LFOB_2026-10-12.csv")
    ap.add_argument("--out", default=".")
    a = ap.parse_args()
    main(a.planning, a.out)
