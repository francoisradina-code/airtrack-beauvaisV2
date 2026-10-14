"""AirTrack Beauvais – une journée type de trafic aérien à Paris-Beauvais (LFOB), piste 12.

Lancement local : streamlit run app.py   ·   En ligne : Streamlit Community Cloud (voir README.md)

Données (dossier data/, produites par le notebook Colab du dossier methode/) :
    app_trajectoires.csv, app_vols.csv, app_trafic_par_heure.csv, app_profils_phase.csv
Les trajectoires sont SYNTHÉTIQUES : elles démontrent la méthode.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from airtrack.map_component import build_payload, render_html
from airtrack.media import AIRCRAFT, AIRLINES, logo_data_uri, logo_html, photo

DATA_DIR = Path(__file__).parent / "data"
COL = {"ARR": "#0B6E99", "DEP": "#E07A00"}
SENS_LABEL = {"ARR": "Arrivée", "DEP": "Départ"}
CIE_COL = {"Ryanair": "#073590", "Ryanair UK": "#5B7FC4", "Wizz Air": "#C6007E", "Wizz Air Malta": "#7E3A92"}
PHASE_LABEL = {
    "roulage_atterrissage": "Roulage (atterrissage)", "finale_ILS_piste12": "Finale ILS piste 12",
    "approche_intermediaire": "Approche intermédiaire", "arrivee_descente": "Arrivée – descente",
    "roulage_decollage": "Roulage (décollage)", "montee_initiale": "Montée initiale",
    "montee_depart": "Montée de départ", "montee_en_route": "Montée en route",
}

st.set_page_config(page_title="AirTrack Beauvais", page_icon="✈️", layout="wide", initial_sidebar_state="collapsed")
st.markdown(
    """
    <style>
    .block-container {padding-top: 1.4rem; padding-bottom: 1rem; max-width: 1500px;}
    [data-testid="stMetricValue"] {font-size: 1.5rem;}
    .cie-card {display:flex; gap:12px; align-items:center;}
    .cie-card .name {font-weight:700; font-size:1.05rem; line-height:1.2}
    .cie-card .codes {color:#5B6B82; font-size:.85rem}
    .big {font-size:1.6rem; font-weight:700; line-height:1.1}
    .muted {color:#5B6B82; font-size:.85rem}
    .photo {width:100%; height:190px; object-fit:cover; border-radius:8px; background:#E6ECF2; display:block}
    .credit {color:#5B6B82; font-size:.75rem; margin-top:3px}
    .credit a {color:#5B6B82}
    .spec {display:grid; grid-template-columns:auto 1fr; gap:1px 12px; font-size:.86rem; margin-top:6px}
    .spec span:nth-child(odd) {color:#5B6B82}
    .flight-row {display:grid; grid-template-columns:30px 62px 74px 1fr auto; gap:8px; align-items:center;
                 padding:5px 8px; border-left:4px solid; border-radius:6px; background:#fff; margin-bottom:4px; font-size:.9rem}
    </style>
    """,
    unsafe_allow_html=True,
)


# ----------------------------------------------------------------------------- données
def plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def hms_to_s(txt: str) -> int:
    h, m, s = (int(v) for v in txt.split(":"))
    return h * 3600 + m * 60 + s


@st.cache_data(show_spinner="Chargement des données…")
def load():
    traj = pd.read_csv(DATA_DIR / "app_trajectoires.csv")
    vols = pd.read_csv(DATA_DIR / "app_vols.csv")
    hourly = pd.read_csv(DATA_DIR / "app_trafic_par_heure.csv").set_index("heure_locale")
    phases = pd.read_csv(DATA_DIR / "app_profils_phase.csv")
    vols["t_event_s"] = vols.heure_evenement_retenue.map(hms_to_s)
    vols["heure"] = vols.t_event_s // 3600
    vols["type_nom"] = vols.type_avion.map(lambda t: AIRCRAFT.get(t, {}).get("nom", t))

    air = traj[~traj.on_ground].copy()
    air["bin"] = air.dist_arp_nm.round().astype(int)
    prof = {s: {v: air[air.sens == s].groupby("bin")[v].quantile([.1, .5, .9]).unstack() for v in ("alt_ft", "gs_kt")}
            for s in ("ARR", "DEP")}
    t0 = traj.groupby("flight_id").t_local_s.min().to_numpy(); t1 = traj.groupby("flight_id").t_local_s.max().to_numpy()
    c = np.arange(1440) * 60 + 30
    conc = ((t0[None, :] <= c[:, None]) & (c[:, None] <= t1[None, :])).sum(axis=1)
    return traj, vols, hourly, phases, prof, conc


@st.cache_data(show_spinner="Préparation de la carte 3D…")
def map_html() -> str:
    traj, vols, *_ = load()
    return render_html(build_payload(traj, vols, PHASE_LABEL))


traj, vols, hourly, phases, prof, conc = load()
tot = hourly["Total"]

# ----------------------------------------------------------------------------- en-tête
st.title("✈️ AirTrack Beauvais")
st.caption("Une journée type de trafic aérien à Paris-Beauvais (LFOB) · piste 12 · lundi 12 octobre 2026 · "
           "zone d'étude : 25 NM autour de l'aéroport")
st.warning("**Jeu de données fictif.** Trajectoires synthétiques construites à partir du planning du jour et des "
           "corridors de la carte DGAC du 20 juin 2025 ; elles servent à démontrer la méthode.", icon="⚠️")

with st.sidebar:
    st.header("À propos")
    st.markdown(
        f"- **{len(vols)} vols** ({(vols.sens == 'ARR').sum()} arrivées, {(vols.sens == 'DEP').sum()} départs)\n"
        f"- **{len(traj):,} points** de trajectoire (1 toutes les 5 s)\n".replace(",", " ")
        + "- Piste 12/30 : seuils réels (OurAirports)\n- Planning : 12/10/2026\n- Corridors : carte DGAC/DSNA du 20/06/2025")
    st.divider()
    st.markdown("**Sources des images**\n\n- Logos : [Jxck-S/airline-logos](https://github.com/Jxck-S/airline-logos) "
                "(usage d'identification)\n- Photos : Wikimedia Commons (lien sous chaque photo)\n"
                "- Fonds de carte : OpenFreeMap / OpenStreetMap, CARTO, Esri")

tab_map, tab_hour, tab_fleet = st.tabs(["🗺️ Carte 3D", "🕒 Trafic par heure", "🛫 Compagnies et appareils"])

# ============================================================================= ONGLET 1 – CARTE 3D
with tab_map:
    st.iframe(map_html(), height=880)
    st.caption("Tout se pilote dans la carte : curseur et boutons de temps, lecture (×1 à ×300), clic sur un avion "
               "ou une ligne de la liste pour le suivre, options d'affichage et fonds de carte dans le panneau de gauche. "
               "Clic droit + glisser (ou Ctrl + glisser) pour faire pivoter et incliner la vue.")

# ============================================================================= ONGLET 2 – TRAFIC PAR HEURE
with tab_hour:
    top3 = tot.nlargest(3)
    peak_h = int(tot.idxmax())
    quiet = [h for h in range(24) if tot[h] == 0]
    pk = int(np.argmax(conc))

    k = st.columns(4)
    k[0].metric("Mouvements sur la journée", int(tot.sum()),
                f"{int(hourly['Arrivées'].sum())} arrivées · {int(hourly['Départs'].sum())} départs", delta_color="off")
    k[1].metric("Heure la plus chargée", f"{peak_h:02d}h–{peak_h + 1:02d}h", f"{int(tot[peak_h])} mouvements", delta_color="off")
    k[2].metric("Moyenne sur les heures actives", f"{tot[tot > 0].mean():.1f} / h")
    k[3].metric("Pic d'avions simultanés", int(conc.max()), f"vers {pk // 60:02d}:{pk % 60:02d}", delta_color="off")

    split = st.segmented_control("Couleurs du graphique", ["Arrivées / départs", "Compagnies"], default="Arrivées / départs")
    fig = go.Figure()
    if split == "Compagnies":
        by = vols.pivot_table(index="heure", columns="compagnie", values="vol", aggfunc="count", fill_value=0).reindex(range(24), fill_value=0)
        for cie in by.sum().sort_values(ascending=False).index:
            fig.add_bar(x=by.index, y=by[cie], name=cie, marker_color=CIE_COL.get(cie, "#888"))
    else:
        fig.add_bar(x=hourly.index, y=hourly["Arrivées"], name="Arrivées", marker_color=COL["ARR"])
        fig.add_bar(x=hourly.index, y=hourly["Départs"], name="Départs", marker_color=COL["DEP"])
    fig.add_scatter(x=hourly.index, y=tot + 0.4, mode="text", text=[str(v) if v else "" for v in tot],
                    showlegend=False, hoverinfo="skip", textfont=dict(size=12))
    for h in top3.index:
        fig.add_vrect(x0=h - 0.5, x1=h + 0.5, fillcolor="#C0392B", opacity=0.07, line_width=0)
    fig.update_layout(barmode="stack", height=400, margin=dict(l=0, r=0, t=60, b=0), plot_bgcolor="rgba(0,0,0,0)",
                      title="Mouvements par heure locale (zones rosées : les 3 heures les plus chargées)",
                      xaxis=dict(tickvals=list(range(24)), ticktext=[f"{h:02d}h" for h in range(24)]),
                      yaxis=dict(title="Mouvements"), legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1))
    st.plotly_chart(fig, width="stretch")

    left, right = st.columns([1, 1.15], gap="large")
    with left:
        st.subheader("À retenir")
        arr_p, dep_p = int(hourly.loc[peak_h, "Arrivées"]), int(hourly.loc[peak_h, "Départs"])
        st.markdown(
            f"- **Pointe :** {peak_h:02d}h–{peak_h + 1:02d}h avec {int(tot[peak_h])} mouvements ({arr_p} arrivées, {dep_p} départs).\n"
            f"- **Concentration :** les 3 heures les plus chargées ({', '.join(f'{h:02d}h' for h in top3.index)}) "
            f"regroupent {top3.sum() / tot.sum():.0%} du trafic.\n"
            f"- **Heures creuses :** aucun mouvement à {', '.join(f'{h:02d}h' for h in quiet) if quiet else '—'}.\n"
            f"- **Densité :** jusqu'à {int(conc.max())} avions en même temps dans la zone, {conc.mean():.1f} en moyenne."
        )
        slots = {"Nuit (00h–06h)": (0, 6), "Matin (06h–12h)": (6, 12), "Après-midi (12h–18h)": (12, 18), "Soir (18h–24h)": (18, 24)}
        st.dataframe(pd.DataFrame([{"Période": n, "Arrivées": int(hourly["Arrivées"][a:b].sum()),
                                    "Départs": int(hourly["Départs"][a:b].sum()), "Total": int(tot[a:b].sum()),
                                    "Part": f"{tot[a:b].sum() / tot.sum():.0%}"} for n, (a, b) in slots.items()]),
                     hide_index=True, width="stretch")
        cie_h = vols.pivot_table(index="compagnie", columns="sens", values="vol", aggfunc="count", fill_value=0)
        cie_h["Logo"] = [logo_data_uri(c) for c in cie_h.index]
        cie_h = cie_h.rename(columns={"ARR": "Arrivées", "DEP": "Départs"}).reset_index().rename(columns={"compagnie": "Compagnie"})
        cie_h["Total"] = cie_h["Arrivées"] + cie_h["Départs"]
        st.markdown("**Mouvements par compagnie**")
        st.dataframe(cie_h[["Logo", "Compagnie", "Arrivées", "Départs", "Total"]].sort_values("Total", ascending=False),
                     hide_index=True, width="stretch", column_config={"Logo": st.column_config.ImageColumn("", width="small")})
    with right:
        st.subheader("Les vols d'une heure")
        active_hours = [h for h in range(24) if tot[h] > 0]
        h_sel = st.select_slider("Heure", options=active_hours, value=peak_h, format_func=lambda h: f"{h:02d}h–{h + 1:02d}h")
        sub = vols[vols.heure == h_sel].sort_values("t_event_s")
        st.caption(f"{len(sub)} mouvements : {(sub.sens == 'ARR').sum()} arrivées, {(sub.sens == 'DEP').sum()} départs")
        rows = []
        for r in sub.itertuples():
            rows.append(
                f'<div class="flight-row" style="border-left-color:{COL[r.sens]}">{logo_html(r.compagnie, 26)}'
                f'<b>{r.heure_evenement_retenue[:5]}</b><span><b>{r.vol}</b></span>'
                f'<span>{"🛬 de" if r.sens == "ARR" else "🛫 vers"} {r.aeroport_lie_ville}</span>'
                f'<span class="muted">{r.type_avion} · {r.immat}</span></div>')
        st.markdown("".join(rows), unsafe_allow_html=True)

# ============================================================================= ONGLET 3 – COMPAGNIES ET APPAREILS
with tab_fleet:
    k = st.columns(5)
    k[0].metric("Vols", len(vols))
    k[1].metric("Compagnies", vols.compagnie.nunique())
    k[2].metric("Types d'appareils", vols.type_avion.nunique())
    k[3].metric("Avions distincts", vols.immat.nunique(), help="Nombre d'immatriculations différentes")
    k[4].metric("Villes desservies", vols.aeroport_lie_ville.nunique())

    st.subheader("Compagnies")
    cie = vols.compagnie.value_counts()
    cols = st.columns(len(cie))
    for col, (name, n) in zip(cols, cie.items()):
        d = vols[vols.compagnie == name]
        icao, iata, _ = AIRLINES.get(name, ("—", "—", ""))
        fleet = d.type_avion.value_counts()
        routes = d.aeroport_lie_ville.value_counts().head(3)
        with col.container(border=True):
            st.markdown(f'<div class="cie-card">{logo_html(name, 54)}<div><div class="name">{name}</div>'
                        f'<div class="codes">OACI {icao} · IATA {iata}</div></div></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="big">{n} <span class="muted">mouvements · {n / len(vols):.0%}</span></div>'
                        f'<div class="spec"><span>Avions</span><span>{plural(d.immat.nunique(), "avion différent", "avions différents")}</span>'
                        f'<span>Flotte</span><span>{", ".join(f"{t} ({v})" for t, v in fleet.items())}</span>'
                        f'<span>Liaisons</span><span>{", ".join(routes.index)}</span></div><div style="height:8px"></div>', unsafe_allow_html=True)
    st.caption("Référence Flightradar24 (moyennes quotidiennes à BVA) : Ryanair ≈ 87 · Wizz Air Malta ≈ 11 · Wizz Air ≈ 7 · "
               "Ryanair UK < 1 vol.")

    c1, c2 = st.columns([1.1, 1], gap="large")
    with c1:
        f = go.Figure(go.Bar(x=cie.values[::-1], y=cie.index[::-1], orientation="h",
                             marker_color=[CIE_COL.get(c, "#888") for c in cie.index[::-1]],
                             text=[f"<b>{c}</b>  {v} ({v / len(vols):.0%})" for c, v in zip(cie.index[::-1], cie.values[::-1])],
                             textposition="outside", cliponaxis=False, hovertemplate="%{y} : %{x} mouvements<extra></extra>"))
        for i, name in enumerate(cie.index[::-1]):
            uri = logo_data_uri(name)
            if uri:
                f.add_layout_image(source=uri, xref="paper", yref="y", x=-0.012, y=i, xanchor="right", yanchor="middle",
                                   sizex=0.1, sizey=0.8, layer="above")
        f.update_layout(title="Mouvements par compagnie", height=300, margin=dict(l=62, r=10, t=40, b=0),
                        plot_bgcolor="rgba(0,0,0,0)", xaxis=dict(range=[0, cie.max() * 1.55]),
                        yaxis=dict(showticklabels=False))
        st.plotly_chart(f, width="stretch")
    with c2:
        dst = vols.aeroport_lie_ville.value_counts().head(10)
        f = go.Figure(go.Bar(x=dst.values[::-1], y=dst.index[::-1], orientation="h", marker_color="#B5651D",
                             text=dst.values[::-1], textposition="outside"))
        f.update_layout(title="Top 10 liaisons (mouvements)", height=300, margin=dict(l=0, r=30, t=40, b=0),
                        plot_bgcolor="rgba(0,0,0,0)", xaxis=dict(range=[0, dst.max() * 1.2]))
        st.plotly_chart(f, width="stretch")

    st.subheader("Appareils")
    typ = vols.type_avion.value_counts()
    for row in range(0, len(typ), 3):
        cols = st.columns(3, gap="medium")
        for col, (t, n) in zip(cols, list(typ.items())[row:row + 3]):
            a = AIRCRAFT.get(t, {})
            d = vols[vols.type_avion == t]
            ph = photo(t)
            with col.container(border=True):
                if ph:
                    img, page, leg = ph
                    st.markdown(f'<img class="photo" src="{img}" alt="{a.get("nom", t)}" loading="lazy">'
                                f'<div class="credit">{leg} · <a href="{page}" target="_blank">photo Wikimedia Commons '
                                f'(auteur et licence)</a></div>', unsafe_allow_html=True)
                ops = '<span style="display:flex;gap:6px">' + "".join(logo_html(c, 24) for c in d.compagnie.value_counts().index) + "</span>"
                st.markdown(
                    f'<div style="display:flex;justify-content:space-between;align-items:baseline;margin-top:6px">'
                    f'<div><b style="font-size:1.05rem">{a.get("nom", t)}</b> <span class="muted">({t})</span></div>{ops}</div>'
                    f'<div class="big" style="margin-top:4px">{n} <span class="muted">mouvements · {n / len(vols):.0%} · '
                    f'{plural(d.immat.nunique(), "avion", "avions")}</span></div>'
                    f'<div class="spec"><span>Sièges</span><span>{a.get("sieges", "—")}</span>'
                    f'<span>Longueur</span><span>{a.get("longueur", "—")}</span><span>Envergure</span><span>{a.get("envergure", "—")}</span>'
                    f'<span>Masse max.</span><span>{a.get("mtow", "—")}</span><span>Moteurs</span><span>{a.get("moteurs", "—")}</span>'
                    f'<span>Vitesse d\'approche</span><span>{a.get("vapp", "—")}</span></div><div style="height:8px"></div>', unsafe_allow_html=True)
    st.caption("Caractéristiques indicatives (constructeurs, configurations usuelles des compagnies présentes à Beauvais).")

    c3, c4 = st.columns([1, 1.1], gap="large")
    with c3:
        st.markdown("**Compagnie × type d'appareil**")
        st.dataframe(pd.crosstab(vols.compagnie, vols.type_avion, margins=True, margins_name="Total"), width="stretch")
    with c4:
        st.markdown("**Mouvements par corridor**")
        corr = vols.groupby(["corridor", "sens"]).size().unstack(fill_value=0)
        corr.columns = [SENS_LABEL[c] + "s" for c in corr.columns]
        st.dataframe(corr, width="stretch", height=250)

    st.subheader("Altitudes et vitesses en approche et au décollage")
    st.caption("Médiane (trait) et enveloppe 10–90 % (zone) selon la distance à l'aéroport, avions en l'air.")
    fig = make_subplots(rows=2, cols=2, shared_xaxes=True, vertical_spacing=0.07, horizontal_spacing=0.08,
                        subplot_titles=("Arrivées – altitude (ft)", "Départs – altitude (ft)",
                                        "Arrivées – vitesse sol (kt)", "Départs – vitesse sol (kt)"))
    for j, sens in enumerate(("ARR", "DEP"), start=1):
        rgb = tuple(int(COL[sens][i:i + 2], 16) for i in (1, 3, 5))
        for i, var in enumerate(("alt_ft", "gs_kt"), start=1):
            q = prof[sens][var]
            fig.add_scatter(x=q.index, y=q[0.9], mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip", row=i, col=j)
            fig.add_scatter(x=q.index, y=q[0.1], mode="lines", line=dict(width=0), fill="tonexty",
                            fillcolor=f"rgba{rgb + (0.22,)}", showlegend=False, hoverinfo="skip", row=i, col=j)
            fig.add_scatter(x=q.index, y=q[0.5], mode="lines", line=dict(color=COL[sens], width=2.5), showlegend=False,
                            hovertemplate="%{x} NM : %{y:.0f}<extra></extra>", row=i, col=j)
    fig.update_xaxes(autorange="reversed", col=1)
    fig.update_xaxes(title_text="Distance à l'aéroport (NM)", row=2)
    fig.update_layout(height=540, margin=dict(l=0, r=0, t=40, b=0), plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, width="stretch")

    ph = phases.copy()
    ph["sens"] = ph.sens.map(SENS_LABEL)
    ph["phase"] = ph.phase.map(PHASE_LABEL)
    st.markdown("**Statistiques par phase de vol**")
    st.dataframe(ph.rename(columns={"sens": "Sens", "phase": "Phase", "points": "Points", "alt_med": "Altitude médiane (ft)",
                                    "vitesse_med_kt": "Vitesse médiane (kt)", "vitesse_max_kt": "Vitesse max (kt)"}),
                 hide_index=True, width="stretch")
