"""FR -> EN translation of every text object of a figure (FIGLANG=en)."""
import os
LANG = os.environ.get("FIGLANG", "fr")
FR_EN = {
    "Taille du message (octets)": "Message length (bytes)",
    "Cycles (modèle Cortex-M4)": "Cycles (Cortex-M4 model)",
    "Cycles par octet": "Cycles per byte",
    "Unités ChaChaPoly mesurées (Arduino Due)": "Measured ChaChaPoly units (Arduino Due)",
    "Unités ChaChaPoly modélisées": "Modelled ChaChaPoly units",
    "chiffrer 128 o": "encrypt 128 B", "déchiffrer 128 o": "decrypt 128 B",
    "chiffrer 16 o": "encrypt 16 B", "déchiffrer 16 o": "decrypt 16 B",
    "Énergie par nœud-jour (J)": "Energy per node-day (J)",
    "Hôpital": "Hospital", "Domicile": "Home", "Rural": "Rural",
    "radio": "radio", "cryptographie": "cryptography",
    "Énergie par trame (µJ)": "Energy per frame (µJ)",
    "Charge utile applicative (octets)": "Application payload (bytes)",
    "AUC de l'attaquant (trames V)": "Attacker AUC (V frames)",
    "AUC de l'attaquant (trames R ou V)": "Attacker AUC (R or V frames)",
    "hasard": "chance",
    "Enregistrements V": "V records", "Enregistrements R": "R records",
    "sans attaque": "no attack", "sous brouillage": "under jamming",
    "Part des enregistrements (%)": "Share of records (%)",
    "Exactitude": "Accuracy",
    "Exactitude (%)": "Accuracy (%)",
    "Bayes, taille seule": "Bayes, size only",
    "RF, taille liée à la classe": "RF, class-dependent size",
    "RF, taille indépendante": "RF, independent size",
    "Valeur publiée (2026)": "Reported value (2026)",
    "classe majoritaire": "majority class",
    "Multiplicateur du TEB": "BER multiplier",
    "Écart d'énergie FLOOR-E / règle Elad 2026 (%)": "Energy change FLOOR-E vs Elad 2026 rule (%)",
    "sous le plancher": "below floor", "algorithme hors ensemble autorisé": "algorithm outside policy set",
    "conforme": "compliant",
    "Longueur de trame (octets)": "Frame length (bytes)",
    "Densité": "Density",
    "trames sans V": "frames without V", "trames avec V": "frames with V",
    "Variation d'énergie vs FLOOR-E (%)": "Energy change vs FLOOR-E (%)",
    "Écart d'énergie vs FLOOR-E (%)": "Energy change vs FLOOR-E (%)",
    "Algorithme AEAD": "AEAD algorithm",
    "Taux d'échec d'échéance (%)": "Deadline miss rate (%)",
    "Temps (h)": "Time (h)",
    "toutes variables": "all features", "heure seule (a priori)": "time of day only (prior)",
    "Facteur d'échéance": "Deadline factor", "FLOOR vs Static-Ascon (%)": "FLOOR vs Static-Ascon (%)",
    "trait plein : FLOOR-E\ntirets : FLOOR-L(q16)": "solid: FLOOR-E\ndashed: FLOOR-L(q16)", "longueur seule": "length only",
    "FLOOR-E vs règle Elad 2026 (%)": "FLOOR-E vs Elad 2026 rule (%)",
    "Règle Elad 2026": "Elad 2026 rule", "Énergie par nœud-jour, domicile (J)": "Energy per node-day, home (J)",
    "Latence P95, FLOOR-E (s)": "95th-percentile latency, FLOOR-E (s)", "échéance N": "N deadline",
    "plein : N ; tirets : R": "solid: N; dashed: R",
    "Échéances manquées, FLOOR-E (10$^{-3}$ %)": "Missed deadlines, FLOOR-E (10$^{-3}$ %)",
}


def _tr(s):
    if LANG == "fr" or not s:
        return s
    out = FR_EN.get(s, s)
    for fr, en in FR_EN.items():
        if fr in out and len(fr) > 6:
            out = out.replace(fr, en)
    return out


def translate_figure(fig):
    if LANG == "fr":
        return
    import matplotlib.text as mtext
    from matplotlib.ticker import FixedFormatter
    for ax in fig.axes:
        for axis in (ax.xaxis, ax.yaxis):
            fmt = axis.get_major_formatter()
            if isinstance(fmt, FixedFormatter):
                fmt.seq = [_tr(x) for x in fmt.seq]
    for t in fig.findobj(mtext.Text):
        t.set_text(_tr(t.get_text()))
