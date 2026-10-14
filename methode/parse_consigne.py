"""Extrait le planning du jour (arrivées + départs) du document Word « Consigne.docx ».

Usage : python parse_consigne.py Consigne.docx  ->  planning_LFOB_2026-10-12.csv
Chaque vol occupe 11 paragraphes (date, heure, vol, ville, ICAO, IATA, compagnie,
type, immat., durée, statut) ; 4 vols Wizz Air n'ont pas d'heure (champ vide).
Les 57 premiers enregistrements sont les arrivées, les 57 suivants les départs.
"""
import re, sys
import pandas as pd
from docx import Document

N_ARR = 57
src = sys.argv[1] if len(sys.argv) > 1 else "/mnt/user-data/uploads/Consigne.docx"
out = sys.argv[2] if len(sys.argv) > 2 else "data/planning_LFOB_2026-10-12.csv"
par = [p.text.strip() for p in Document(src).paragraphs if p.text.strip()]
starts = [i for i, t in enumerate(par) if re.fullmatch(r"oct\. \d+", t)]
rows = []
for k, (a, b) in enumerate(zip(starts, starts[1:] + [len(par)])):
    r = par[a:b]
    if len(r) == 10:
        r.insert(1, "")
    _, t, flight, city, icao, iata, airline, ac, reg, dur, status = r
    m = re.fullmatch(r"(\d+)h(\d+)m", dur)
    rows.append(dict(sens="ARR" if k < N_ARR else "DEP", rang=k if k < N_ARR else k - N_ARR,
                     date="2026-10-12", heure_liste=t.replace(" CEST", ""), vol=flight,
                     ville=city, icao=icao, iata=iata, compagnie=airline, type_avion=ac,
                     immat=reg, duree_vol_min=int(m.group(1)) * 60 + int(m.group(2)),
                     statut_brut=status))
pd.DataFrame(rows).to_csv(out, index=False, encoding="utf-8")
print(len(rows), "vols ->", out)
