# AirTrack Beauvais

Une journée type de trafic aérien à Paris-Beauvais (LFOB), piste 12 : carte 3D animée des arrivées et des départs, trafic par heure, compagnies et appareils.

> **Données fictives.** Les trajectoires sont synthétiques : planning réel du 12/10/2026, corridors tirés de la carte DGAC/DSNA du 20/06/2025, piste calée sur ses seuils réels. Elles démontrent la méthode. Avec de vraies données ADS-B au même format, l'application fonctionne sans modification.

---

## Mettre l'application en ligne (sans ligne de commande)

Comptez une quinzaine de minutes. Il faut deux comptes gratuits : **GitHub** (pour héberger les fichiers) et **Streamlit Community Cloud** (pour faire tourner l'application).

### Étape 1 : créer le dépôt GitHub

1. Créez un compte sur [github.com](https://github.com) si vous n'en avez pas.
2. En haut à droite, cliquez sur **+** puis **New repository**.
3. Nom : `airtrack-beauvais`. Visibilité : **Public**. La version gratuite de Streamlit Cloud déploie les dépôts publics ; un dépôt privé est possible après avoir autorisé Streamlit à y accéder.
4. Ne cochez rien d'autre. Cliquez sur **Create repository**.

### Étape 2 : déposer les fichiers

1. Décompressez `airtrack-beauvais.zip` sur votre ordinateur.
2. Sur la page du dépôt vide, cliquez sur le lien **uploading an existing file**. Sinon : **Add file** puis **Upload files**.
3. Ouvrez le dossier décompressé `airtrack-beauvais`, sélectionnez **tout son contenu** (`app.py`, `requirements.txt`, les dossiers `airtrack`, `assets`, `data`, `methode`…) et glissez-le dans la page GitHub. Les sous-dossiers sont conservés.
4. Attendez la fin du chargement, puis cliquez sur **Commit changes** en bas.
5. Vérifiez que `app.py` et `requirements.txt` apparaissent **à la racine** du dépôt, et pas dans un sous-dossier.

**Le thème (facultatif).** Le dossier `.streamlit` commence par un point. Selon votre système, il peut ne pas être visible ou pas envoyé. Sans lui, l'application fonctionne avec les couleurs par défaut de Streamlit. Pour l'ajouter quand même : **Add file** puis **Create new file**, nom `.streamlit/config.toml`, et collez le contenu du fichier du même nom.

### Étape 3 : déployer sur Streamlit Community Cloud

1. Allez sur [share.streamlit.io](https://share.streamlit.io) et cliquez sur **Continue with GitHub**. Acceptez l'accès demandé.
2. Cliquez sur **Create app**, puis **Deploy a public app from GitHub** (ou « Yup, I have an app »).
3. Remplissez :
   - **Repository** : `votre-nom/airtrack-beauvais`
   - **Branch** : `main`
   - **Main file path** : `app.py`. Si vous avez glissé le dossier entier plutôt que son contenu, mettez `airtrack-beauvais/app.py`.
   - **App URL** : choisissez une adresse, par exemple `airtrack-beauvais`.
4. Ouvrez **Advanced settings** et choisissez **Python 3.12** (ou 3.13).
5. Cliquez sur **Deploy**. La première installation prend 2 à 4 minutes. L'application s'ouvre ensuite sur une adresse du type `https://airtrack-beauvais.streamlit.app`, que vous pouvez partager.

### Modifier l'application ensuite

Toute modification d'un fichier sur GitHub (crayon ✏️ sur la page du fichier, ou nouvel upload qui remplace l'ancien) est reprise automatiquement par Streamlit Cloud en une minute environ. Pour changer les données, remplacez les fichiers du dossier `data/` en gardant les mêmes noms.

**En cas de problème :** sur share.streamlit.io, le menu **⋮** de l'application, puis **Manage app**, affiche le journal d'erreurs. **Reboot app** relance l'application.

---

## Ce que contient l'application

**Carte 3D** : les positions sont recalculées à chaque image par le navigateur, donc le mouvement est continu et fluide, sans saut d'un point à l'autre.
- Avions en 3D orientés selon leur cap, leur assiette et leur inclinaison dans les virages ; étiquette vol, type, altitude et vitesse.
- Trajectoire en traîne, parcourue ou complète, avec un **mur translucide jusqu'au sol** pour lire la trajectoire dans l'espace.
- Lecture de ×1 (temps réel) à ×300 ; curseur 24 h ; frise des avions présents et des mouvements piste.
- Clic sur un avion ou sur la liste : fiche détaillée et suivi par la caméra.
- Fonds de carte : **Plan 3D** (OpenFreeMap, bâtiments en relief en zoomant), **Sombre** (CARTO), **Satellite** (Esri). La vue « Aéroport » montre de près la piste et les bâtiments en relief issus d'OpenStreetMap.
- Cercles de 5 à 25 NM et axe d'approche de la piste 12.

**Trafic par heure** : mouvements par heure (par sens ou par compagnie), heures de pointe et creuses, liste des vols de l'heure choisie avec les logos.

**Compagnies et appareils** : fiche de chaque compagnie (logo, flotte, liaisons), fiche de chaque type d'avion (photo, caractéristiques, compagnies qui l'exploitent), profils d'altitude et de vitesse.

## Organisation des fichiers

```
app.py                     application Streamlit (3 onglets)
requirements.txt           bibliothèques Python
airtrack/
  map_component.py         prépare les données de la carte
  map_template.html        carte 3D (deck.gl + MapLibre, exécutée dans le navigateur)
  media.py                 logos, photos et fiches appareils
assets/
  models/                  modèles 3D d'avion (.glb), générés par methode/make_plane_model.py
  logos/                   logos des compagnies
data/                      les 4 fichiers produits par le notebook Colab
methode/
  AirTrack_BVA_colab.ipynb notebook Colab : contrôles, analyses, export des fichiers de data/
  generate_fake_dataset.py fabrication du jeu de données fictif
  parse_consigne.py        extraction du planning depuis le document Word
  make_plane_model.py      fabrication des modèles 3D
  donnees_sources/         planning et CSV d'entrée du notebook
```

## Sources

- Planning des vols : relevé du 12/10/2026 (document de consigne).
- Corridors de trajectoires : carte DGAC/DSNA « Beauvais Tillé – Face à l'Est – 20 juin 2025 ».
- Seuils de piste : [OurAirports](https://ourairports.com/airports/LFOB/).
- Logos : [Jxck-S/airline-logos](https://github.com/Jxck-S/airline-logos), usage d'identification. Les logos restent la propriété des compagnies.
- Photos : Wikimedia Commons, sous licence libre. Auteur et licence sont accessibles par le lien sous chaque photo.
- Fonds de carte : © OpenStreetMap contributors, OpenFreeMap, CARTO, Esri.

## Lancer en local (facultatif)

```
pip install -r requirements.txt
streamlit run app.py
```

Sous Windows, si `pip` n'est pas reconnu : `py -m pip install -r requirements.txt` puis `py -m streamlit run app.py`.
