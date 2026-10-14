"""Construit un petit modèle 3D d'avion de ligne biréacteur (format glTF binaire .glb).

Repère de construction (mètres) : x = aile droite, y = nez (avant), z = haut.
Repère exporté (convention deck.gl ScenegraphLayer) : x = nez, y = aile gauche, z = haut.
Dimensions proches d'un A320 / 737-800 : longueur 38 m, envergure 34 m.
Deux variantes de couleur (empennage + réacteurs) : arrivée (bleu) et départ (ambre).

Usage : python make_plane_model.py <dossier_sortie>
"""
import sys
from pathlib import Path

import numpy as np
import trimesh
from trimesh.visual.material import PBRMaterial


def revolve(stations):
    """Fuselage : surface de révolution. stations = [(y, rayon, z_centre, ratio_vertical)]."""
    n = 28
    th = np.linspace(0, 2 * np.pi, n, endpoint=False)
    verts, faces = [], []
    for y, r, zc, ev in stations:
        for a in th:
            verts.append([r * np.cos(a), y, zc + r * ev * np.sin(a)])
    m = len(stations)
    for i in range(m - 1):
        for j in range(n):
            a, b = i * n + j, i * n + (j + 1) % n
            c, d = a + n, b + n
            faces += [[a, c, b], [b, c, d]]
    # bouchons
    for idx, (y, r, zc, ev) in ((0, stations[0]), (m - 1, stations[-1])):
        verts.append([0, y, zc]); ci = len(verts) - 1
        for j in range(n):
            a, b = idx * n + j, idx * n + (j + 1) % n
            faces.append([ci, b, a] if idx == 0 else [ci, a, b])
    return trimesh.Trimesh(np.array(verts), np.array(faces), process=True)


def slab(outline_xy, thickness, z0=0.0):
    """Plaque d'épaisseur `thickness` à partir d'un contour 2D (x, y) ; base à z0."""
    from shapely.geometry import Polygon
    m = trimesh.creation.extrude_polygon(Polygon(outline_xy), thickness)
    m.apply_translation([0, 0, z0 - thickness / 2])
    return m


def wing_half(side, root_y, root_c, tip_c, semi, sweep_deg, dihedral_deg, x0, z0, th):
    s = np.tan(np.radians(sweep_deg))
    le_root, le_tip = root_y, root_y - semi * s
    pts = [(x0, le_root), (x0 + semi, le_tip), (x0 + semi, le_tip - tip_c), (x0, le_root - root_c)]
    if side < 0:
        pts = [(-x, y) for x, y in pts][::-1]
    m = slab(pts, th, z0)
    v = m.vertices.copy()
    v[:, 2] += np.tan(np.radians(dihedral_deg)) * np.abs(v[:, 0])
    m.vertices = v
    return m


def fin():
    # dérive : contour dans le plan (y, z), extrudé en x
    from shapely.geometry import Polygon
    prof = [(-13.6, 1.6), (-17.6, 8.6), (-19.6, 8.6), (-19.3, 1.6)]
    m = trimesh.creation.extrude_polygon(Polygon(prof), 0.45)
    # extrude_polygon : contour en (x,y) extrudé selon z -> on réordonne (y,z,x)
    v = m.vertices.copy()
    m.vertices = np.c_[v[:, 2] - 0.225, v[:, 0], v[:, 1]]
    m.fix_normals()
    return m


def engine(x):
    e = trimesh.creation.cylinder(radius=0.95, height=4.2, sections=24)
    e.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
    e.apply_translation([x, 4.2, -1.55])
    pylon = trimesh.creation.box(extents=[0.3, 3.0, 1.0])
    pylon.apply_translation([x, 3.4, -0.6])
    return trimesh.util.concatenate([e, pylon])


def build(accent_rgb):
    fus = revolve([
        (19.0, 0.05, -0.35, 1.0), (18.4, 0.75, -0.25, 1.0), (17.2, 1.45, -0.1, 1.02),
        (15.5, 1.9, 0.0, 1.05), (13.0, 2.0, 0.0, 1.05), (-8.0, 2.0, 0.0, 1.05),
        (-12.0, 1.85, 0.25, 1.0), (-15.5, 1.3, 0.8, 0.95), (-18.5, 0.6, 1.3, 0.9), (-19.6, 0.15, 1.5, 0.9),
    ])
    wings = trimesh.util.concatenate([
        wing_half(+1, 3.6, 6.2, 1.6, 15.5, 25, 5, 1.6, -0.9, 0.45),
        wing_half(-1, 3.6, 6.2, 1.6, 15.5, 25, 5, 1.6, -0.9, 0.45),
    ])
    stab = trimesh.util.concatenate([
        wing_half(+1, -15.2, 3.4, 1.3, 5.6, 30, 6, 0.5, 1.2, 0.25),
        wing_half(-1, -15.2, 3.4, 1.3, 5.6, 30, 6, 0.5, 1.2, 0.25),
    ])
    engines = trimesh.util.concatenate([engine(5.6), engine(-5.6)])
    tail = fin()

    def mat(rgb, metal=0.1, rough=0.55):
        return PBRMaterial(baseColorFactor=[*rgb, 1.0], metallicFactor=metal, roughnessFactor=rough)

    white, grey = (0.96, 0.96, 0.97), (0.78, 0.80, 0.83)
    acc = tuple(c / 255 for c in accent_rgb)
    scene = trimesh.Scene()
    for name, mesh, m in (("fuselage", fus, mat(white)), ("ailes", wings, mat(grey, 0.3, 0.4)),
                          ("stabilisateur", stab, mat(grey, 0.3, 0.4)), ("derive", tail, mat(acc)),
                          ("reacteurs", engines, mat(acc, 0.2, 0.45))):
        mesh.visual = trimesh.visual.TextureVisuals(material=m)
        v = mesh.vertices.copy()
        mesh.vertices = np.c_[v[:, 1], -v[:, 0], v[:, 2]]      # nez vers +x, aile gauche vers +y
        scene.add_geometry(mesh, node_name=name, geom_name=name)
    return scene


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    out.mkdir(parents=True, exist_ok=True)
    for name, rgb in (("plane_arr.glb", (11, 110, 153)), ("plane_dep.glb", (224, 122, 0))):
        data = build(rgb).export(file_type="glb", include_normals=True)
        (out / name).write_bytes(data)
        print(name, len(data), "octets")
