"""Agenda automatique : repère dans le fil d'actu les rendez-vous annoncés avec une date
(« réunion prévue lundi soir », « meeting samedi à Lyon », « invité dimanche sur TF1 »…)
et les ajoute à data/agenda.json, avec le lien de l'article. Sans IA, règles simples et prudentes."""
import json, re, unicodedata, datetime as dt

P = "data/agenda.json"
JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS = ["janvier", "fevrier", "mars", "avril", "mai", "juin", "juillet", "aout", "septembre", "octobre", "novembre", "decembre"]

def norm(s):
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn").replace("’", "'")

# Le titre doit annoncer quelque chose à venir, pas raconter ce qui s'est passé
FUTUR = re.compile(r"\b(prevue?s?|programmee?s?|annoncee?s?|organisera|organise|tiendra|se tiendra|aura lieu|sera|seront|va |vont |invitee?s? de|attendue?s?|rendez-vous|rdv|ce soir|demain|prochain|prochaine)\b")
PASSE = re.compile(r"\b(a ete|ont ete|etait|s'est tenue?|s'est deroulee?|hier|retour sur|ce qu'il faut retenir|ce qu'il faut en retenir|replay|revoir)\b")
TYPES = [
    ("debat", re.compile(r"\bdebats?\b|\bface-a-face\b|\bduel\b")),
    ("emission", re.compile(r"\bemission\b|\binvitee?s?\b|\binterview\b|\bgrand oral\b|\bplateau\b|\bsur (tf1|france 2|france 3|bfmtv|lci|cnews|franceinfo|france inter|rtl|europe 1|m6|c8|arte|public senat|lcp)\b")),
    ("meeting", re.compile(r"\bmeetings?\b|\breunion publique\b|\bgrand rassemblement\b")),
    ("vote", re.compile(r"\bprimaire\b|\bvote des (adherents|militants)\b|\bcongres\b|\bconseil national\b")),
    ("evenement", re.compile(r"\breunion\b|\brencontre\b|\bdiner\b|\bsommet\b|\bdeplacement\b|\bvisite\b|\bconference de presse\b|\bpresentera\b|\bdevoilera\b|\blancement\b")),
]

def date_annoncee(nt, pub):
    """Date de l'événement à partir du titre et de la date de publication, ou None."""
    m = re.search(r"\b(?:le |ce |du )?(\d{1,2})(?:er)? (" + "|".join(MOIS) + r")\b", nt)
    if m:
        j, mo = int(m.group(1)), MOIS.index(m.group(2)) + 1
        for an in (pub.year, pub.year + 1):
            try:
                d = dt.date(an, mo, j)
            except ValueError:
                return None
            if d >= pub:
                return d
        return None
    if re.search(r"\bce soir\b|\bcet apres-midi\b|\baujourd'hui\b", nt):
        return pub
    if re.search(r"\bdemain\b", nt):
        return pub + dt.timedelta(days=1)
    m = re.search(r"\b(ce |cette semaine |)(" + "|".join(JOURS) + r")( prochain)?\b", nt)
    if m:
        cible = JOURS.index(m.group(2))
        ecart = (cible - pub.weekday()) % 7
        if ecart == 0 and (m.group(3) or not m.group(1)):
            ecart = 7 if m.group(3) else 0
        return pub + dt.timedelta(days=ecart)
    return None

def heure(nt):
    m = re.search(r"\ba (\d{1,2})h(\d{2})?\b", nt)
    if m and int(m.group(1)) < 24:
        return f"{int(m.group(1))}h{m.group(2) or ''}"
    for mot, txt in (("soir", "en soirée"), ("soiree", "en soirée"), ("matin", "le matin"), ("apres-midi", "l'après-midi")):
        if re.search(r"\b" + mot + r"\b", nt):
            return txt
    return None

def titre_propre(t):
    t = re.sub(r"^\s*(DIRECT|VIDEO|VIDÉO|INFO [^.:]+|EXCLUSIF|INFO)\s*[.:]\s*", "", t, flags=re.I)
    t = re.sub(r"^\s*Présidentielle( 2027)?\s*:\s*", "", t, flags=re.I)
    return t[:1].upper() + t[1:]

def main():
    flux = json.load(open("data/flux.json", encoding="utf-8")).get("items", [])
    ag = json.load(open(P, encoding="utf-8"))
    evs = ag.setdefault("evenements", [])
    today = dt.date.today()
    ajouts = 0
    for it in flux:
        t, qui = it.get("t", ""), it.get("qui") or []
        if not qui:
            continue
        nt = norm(t)
        if PASSE.search(nt) or "sondage" in nt:
            continue
        typ = next((k for k, rx in TYPES if rx.search(nt)), None)
        if not typ:
            continue
        pub = dt.datetime.fromisoformat(it["d"].replace("Z", "+00:00")).astimezone(dt.timezone(dt.timedelta(hours=1))).date()
        d = date_annoncee(nt, pub)
        if not d or d < today or (d - pub).days > 60:
            continue
        # Annonce explicite : un mot de futur, ou une date précise donnée à l'avance
        if not FUTUR.search(nt) and d == pub:
            continue
        iso = d.isoformat()
        # Déjà dans l'agenda : même jour et au moins un candidat en commun, ou même article
        if any(e.get("url") == it["u"] or (e.get("date") == iso and set(e.get("qui") or []) & set(qui)) for e in evs):
            continue
        evs.append({"date": iso, "heure": heure(nt), "type": typ, "titre": titre_propre(t), "lieu": None,
                    "chaine": None, "qui": qui, "url": it["u"], "source": it.get("s"), "auto": True})
        ajouts += 1
    if ajouts:
        evs.sort(key=lambda e: (e["date"], e.get("heure") or ""))
        ag["maj"] = today.isoformat()
        open(P, "w", encoding="utf-8").write(json.dumps(ag, ensure_ascii=False, indent=1) + "\n")
    print("agenda auto :", ajouts, "ajout(s)")

if __name__ == "__main__":
    main()
