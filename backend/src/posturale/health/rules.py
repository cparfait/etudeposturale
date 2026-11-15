"""Moteur d'aide à la décision (docs/01_metriques.md § 7).

Croise les mesures (profil, face, dos), les douleurs, les auto-tests, les capteurs et les ressentis.
Produit des HYPOTHÈSES ordonnées selon la séquence des fitters : santé → charge → cales → hauteur de selle
→ recul → cockpit → manivelle. Jamais un diagnostic.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

ORDER = {"sante": 0, "charge": 1, "asymetrie": 2, "cales": 3, "selle_hauteur": 4, "selle_recul": 5, "cockpit": 6, "manivelle": 7}


@dataclass
class Hypothesis:
    id: str
    categorie: str
    titre: str
    constats: list[str]
    hypothese: str
    action: str
    priorite: str            # haute | moyenne | info
    fiabilite: str           # etude | pratique | a_definir
    sources: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class Context:
    profil: dict[str, dict] = field(default_factory=dict)   # côté → résultat d'analyse de profil
    face: dict | None = None
    dos: dict | None = None
    douleurs: list[dict] = field(default_factory=list)       # entrées actives
    tests: list[dict] = field(default_factory=list)
    fit: dict | None = None
    ressentis: list[dict] = field(default_factory=list)
    config: dict | None = None


def _m(res: dict | None, key: str) -> float | None:
    if not res:
        return None
    v = res.get("metriques", {}).get(key, {}).get("moyenne")
    return v if isinstance(v, (int, float)) else None


def _pain(ctx: Context, zone_prefix: str, cote: str | None = None) -> list[dict]:
    return [d for d in ctx.douleurs if d["zone"].startswith(zone_prefix) and (cote is None or d.get("cote") in (cote, "centre"))]


def _test(ctx: Context, tid: str, cote: str | None = None) -> dict | None:
    ts = [t for t in ctx.tests if t["test_id"] == tid and (cote is None or t.get("cote") == cote)]
    return ts[-1] if ts else None


def evaluate(ctx: Context) -> list[dict]:
    out: list[Hypothesis] = []

    # ------------------------------------------------------------ santé : signaux d'alerte
    red = [d for d in ctx.douleurs if d.get("intensite", 0) >= 7 or "repos" in (d.get("moment") or "").lower()]
    if red:
        out.append(Hypothesis(
            "alerte_medicale", "sante", "Douleur forte ou présente au repos",
            [f"{d['zone'].replace('_', ' ')} ({d.get('cote')}) : {d.get('intensite')}/10" + (f", {d['moment']}" if d.get("moment") else "") for d in red],
            "Une douleur intense ou au repos dépasse le cadre d'un réglage de position.",
            "Consulter un professionnel de santé (médecin du sport, kinésithérapeute) avant de modifier la position.",
            "haute", "pratique"))

    # ------------------------------------------------------------ ménisque : prudence sur la flexion du genou
    menisc = [d for d in ctx.douleurs if d["zone"].startswith("genou_menisque")]
    if menisc:
        out.append(Hypothesis(
            "menisque", "sante", "Douleur méniscale : avis médical et genou ménagé",
            [f"{d['zone'].replace('genou_menisque_', 'ménisque ').replace('int', 'interne').replace('ext', 'externe')} ({d.get('cote')}) : {d.get('intensite')}/10" for d in menisc],
            "Un ménisque supporte mal la flexion profonde du genou en charge et les rotations forcées du tibia.",
            "Faire confirmer par un médecin. En attendant : pas de selle trop basse ni trop avancée (flexion maximale du genou modérée "
            "en haut du coup de pédale), cales avec un peu de liberté angulaire, et pas de changement brutal de rotation de cale.",
            "haute" if any((d.get("intensite") or 0) >= 5 for d in menisc) else "moyenne", "pratique"))

    # ------------------------------------------------------------ charge d'entraînement
    long_pains = [d for d in ctx.douleurs if any(w in (d.get("moment") or "").lower() for w in ("longue", "grosse", "km", "heure", " h"))]
    big = [r for r in ctx.ressentis if (r.get("distance_km") or 0) >= 80 or (r.get("duree_min") or 0) >= 240]
    drift = None
    if ctx.fit and len(ctx.fit.get("par_heure", [])) >= 2:
        hours = [h for h in ctx.fit["par_heure"] if h.get("equilibre_gauche_pct") is not None]
        if len(hours) >= 2:
            drift = hours[-1]["equilibre_gauche_pct"] - hours[0]["equilibre_gauche_pct"]
    if long_pains or big or (drift is not None and abs(drift) >= 2):
        constats = [f"Douleur liée à la durée : {d['zone'].replace('_', ' ')} ({d.get('moment')})" for d in long_pains]
        constats += [f"Sortie longue : {r.get('distance_km') or '?'} km / {r.get('duree_min') or '?'} min" for r in big[-2:]]
        if drift is not None and abs(drift) >= 2:
            constats.append(f"Équilibre gauche {'en baisse' if drift < 0 else 'en hausse'} de {abs(drift):.1f} points entre la 1re et la dernière heure")
        out.append(Hypothesis(
            "charge", "charge", "La durée et la fatigue jouent un rôle",
            constats,
            "Une hausse brutale du volume (ex. première sortie de 90 km) est une cause fréquente de douleur au genou, indépendamment des réglages ; la position se dégrade aussi avec la fatigue.",
            "Augmenter le volume progressivement (≈ +10 % par semaine) ; faire une capture « fin d'effort » pour voir si l'extension du genou ou le bassin changent.",
            "haute" if long_pains else "moyenne", "pratique", ["Revue douleur du genou (Dovepress 2022)"]))

    # ------------------------------------------------------------ asymétries G/D
    p1 = {s: _m(r, "P1") for s, r in ctx.profil.items()}
    asym = []
    if p1.get("G") is not None and p1.get("D") is not None and abs(p1["G"] - p1["D"]) > 5:
        asym.append(f"Extension max du genou : G {p1['G']:.0f}° / D {p1['D']:.0f}° (écart {abs(p1['G'] - p1['D']):.0f}°)")
    if ctx.dos and isinstance(ctx.dos.get("metriques", {}).get("D3"), (int, float)) and abs(ctx.dos["metriques"]["D3"]) > 2:
        asym.append(f"Bassin incliné en moyenne de {ctx.dos['metriques']['D3']:.1f}° (vue de dos)")
    if ctx.fit and (eg := ctx.fit.get("global", {}).get("equilibre_gauche_pct")) is not None and abs(eg - 50) > 2:
        asym.append(f"Équilibre de puissance {eg:.1f} % gauche / {100 - eg:.1f} % droite")
    t9 = _test(ctx, "T9")
    if t9 and t9.get("valeur") is not None and abs(t9["valeur"]) > 5:
        asym.append(f"Inégalité de longueur de jambes estimée : {t9['valeur']:+.0f} mm")
    if asym:
        out.append(Hypothesis(
            "asymetrie", "asymetrie", "Asymétrie gauche / droite",
            asym + [f"Douleur d'un seul côté : {d['zone'].replace('_', ' ')} {d['cote']}" for d in ctx.douleurs if d.get("cote") in ("G", "D")][:3],
            "Un bassin qui bascule ou une jambe plus longue fait travailler les deux genoux différemment (une jambe trop tendue, l'autre trop pliée).",
            "Vérifier la vue de dos et le réglage des deux cales ; une inégalité > 5 mm est à confirmer par un professionnel avant toute cale d'épaisseur.",
            "haute", "pratique", ["Roadman Cycling — inégalité de longueur de jambes"]))

    # ------------------------------------------------------------ cales / alignement frontal
    if ctx.face:
        for s, data in ctx.face.get("metriques", {}).get("cotes", {}).items():
            f1 = data.get("F1", {}).get("moyenne")
            unit = ctx.face["metriques"].get("unite")
            limit = 20 if unit == "mm" else 10
            if isinstance(f1, (int, float)) and f1 > limit:
                out.append(Hypothesis(
                    f"cales_{s}", "cales", f"Genou {'gauche' if s == 'G' else 'droit'} qui oscille latéralement",
                    [f"Va-et-vient du genou : {f1:.0f} {unit} par tour (repère < {limit} {unit})"] +
                    [f"Douleur {d['zone'].replace('_', ' ')} {s}" for d in _pain(ctx, "genou", s)][:2],
                    "Rotation, position latérale de la cale ou avant-pied non compensé (fitters).",
                    "Essai : 1 à 2° de rotation de cale ou 1 à 2 mm de décalage latéral du côté concerné, puis nouvelle vue de face.",
                    "moyenne", "pratique", ["Pratique de fitters (Hogg)"]))

    # ------------------------------------------------------------ hauteur de selle (par côté)
    for s, res in ctx.profil.items():
        v = res.get("verdict_selle") or {}
        p1s, p5, p10 = _m(res, "P1"), _m(res, "P5"), _m(res, "P10")
        back = _pain(ctx, "genou_arriere", s) + _pain(ctx, "cuisse_arriere", s)
        front = _pain(ctx, "genou_avant", s)
        roll = _m(ctx.dos, "D1") if ctx.dos else None
        if ctx.dos:
            roll = ctx.dos.get("metriques", {}).get("D1", {}).get("moyenne")
        if v.get("statut") == "trop_tendu":
            constats = [f"Extension max du genou {s} : {v['flexion_moyenne']}° (plage {v['plage_min']:g}–{v['plage_max']:g}°)"]
            if p5 is not None:
                constats.append(f"Plage de cheville : {p5:.0f}°")
            if isinstance(roll, (int, float)) and roll > 6:
                constats.append(f"Bassin qui bascule : {roll:.1f}° par tour")
            constats += [f"Douleur {d['zone'].replace('_', ' ')} {s} ({d.get('intensite')}/10)" for d in back]
            t4 = _test(ctx, "T4", s)
            if t4 and (t4.get("valeur") or 99) < 70:
                constats.append(f"Ischio-jambiers raides (élévation jambe tendue {t4['valeur']:.0f}°)")
            out.append(Hypothesis(
                f"selle_haute_{s}", "selle_hauteur", "Selle possiblement trop haute",
                constats, "Genou en extension forte en bas du coup de pédale ; signe classique associé aux douleurs à l'arrière du genou.",
                f"Baisser la selle de {abs(v['correction_mm']):.0f} mm (calcul géométrique), rouler 2 à 3 sorties, puis nouvelle capture.",
                "haute" if back else "moyenne", "etude", ["Holmes 1994", "Ferrer-Roca 2012", "Bini 2011"]))
        elif v.get("statut") == "trop_plie":
            constats = [f"Extension max du genou {s} : {v['flexion_moyenne']}° (plage {v['plage_min']:g}–{v['plage_max']:g}°)"]
            constats += [f"Douleur {d['zone'].replace('_', ' ')} {s} ({d.get('intensite')}/10)" for d in front]
            out.append(Hypothesis(
                f"selle_basse_{s}", "selle_hauteur", "Selle possiblement trop basse",
                constats, "Genou très plié en bas du coup de pédale : charge accrue sur l'avant du genou (consensus de fitters, preuves mitigées).",
                f"Monter la selle de {abs(v['correction_mm']):.0f} mm, puis nouvelle capture.",
                "haute" if front else "moyenne", "etude", ["Holmes 1994", "Bini & Hume (preuves mitigées)"]))
        elif back and p10 is not None and isinstance(roll, (int, float)) and roll > 6:
            out.append(Hypothesis(
                f"selle_instable_{s}", "selle_hauteur", "Bassin instable malgré un genou dans la plage",
                [f"Bascule du bassin {roll:.1f}° par tour"], "Selle légèrement haute ou assise instable.",
                "Essai : −3 mm, ou vérifier la largeur de selle (ischions).", "moyenne", "pratique"))

    # ------------------------------------------------------------ recul de selle
    for s, res in ctx.profil.items():
        p6 = _m(res, "P6")
        if p6 is not None and abs(p6) > 25:
            out.append(Hypothesis(
                f"recul_{s}", "selle_recul", "Genou loin de la verticale de la pédale à 3 h",
                [f"Genou {abs(p6):.0f} mm {'en avant' if p6 > 0 else 'en arrière'} de l'axe de pédale (KOPS)"],
                "Point de départ empirique, sans base biomécanique démontrée : à interpréter avec les douleurs.",
                f"Si douleur {'avant' if p6 > 0 else 'arrière'} du genou : essai de {'reculer' if p6 > 0 else 'avancer'} la selle de 5 mm (et recontrôler la hauteur).",
                "info", "pratique", ["Revue bike fitting (PMC9219349)"]))

    # ------------------------------------------------------------ manivelle
    for s, res in ctx.profil.items():
        p2, p4 = _m(res, "P2"), _m(res, "P4")
        front = _pain(ctx, "genou_avant", s) + _pain(ctx, "hanche_avant", s)
        if p2 is not None and p2 > 115 and front:
            crank = (ctx.config or {}).get("manivelle_mm")
            out.append(Hypothesis(
                f"manivelle_{s}", "manivelle", "Haut du coup de pédale compressé",
                [f"Flexion max du genou {s} : {p2:.0f}°"] + ([f"Angle de hanche fermé : {p4:.0f}°"] if p4 else []) +
                [f"Douleur {d['zone'].replace('_', ' ')} {s}" for d in front][:2],
                "Des manivelles plus courtes réduisent la flexion de hanche et de genou en haut du coup de pédale.",
                f"Après avoir validé la hauteur de selle : essai de manivelles 5 à 10 mm plus courtes{f' que {crank:g} mm' if crank else ''} (remonter la selle d'autant).",
                "info", "etude", ["Ferrer-Roca 2017", "Université de Derby"]))

    out.sort(key=lambda h: (ORDER.get(h.categorie, 9), {"haute": 0, "moyenne": 1, "info": 2}[h.priorite]))
    return [h.as_dict() for h in out]
