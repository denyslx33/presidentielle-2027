"""Fil d'actu automatique : titres des flux RSS officiels de médias reconnus, filtrés sur la présidentielle 2027."""
import json, re, html, unicodedata, urllib.request, email.utils, datetime as dt, xml.etree.ElementTree as ET

FEEDS = [
    ("Le Monde", "https://www.lemonde.fr/politique/rss_full.xml"),
    ("franceinfo", "https://www.francetvinfo.fr/politique.rss"),
    ("Libération", "https://www.liberation.fr/arc/outboundfeeds/rss-all/category/politique/?outputType=xml"),
    ("Le Figaro", "https://www.lefigaro.fr/rss/figaro_politique.xml"),
    ("Le Parisien", "https://feeds.leparisien.fr/leparisien/rss/politique"),
    ("20 Minutes", "https://www.20minutes.fr/feeds/rss-politique.xml"),
    ("Ouest-France", "https://www.ouest-france.fr/rss/une"),
    ("BFMTV", "https://www.bfmtv.com/rss/politique/"),
    ("France 24", "https://www.france24.com/fr/france/rss"),
    ("La Croix", "https://www.la-croix.com/feeds/rss/politique.xml"),
    ("LCP", "https://lcp.fr/rss.xml"),
    ("RFI", "https://www.rfi.fr/fr/france/rss"),
]

def norm(s):
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")

cand = json.load(open("data/candidats.json", encoding="utf-8"))["principaux"]
# motif de détection par candidat : nom complet, ou nom de famille s'il est peu ambigu
KEYS = {}
for c in cand:
    nom = norm(c["nom"])
    fam = nom.split(" ", 1)[1] if " " in nom else nom
    keys = [nom]
    if fam not in ("philippe",) and len(fam) > 4:
        keys.append(fam)
    KEYS[c["id"]] = keys
# Partis : une actu sur le parti d'un candidat le concerne aussi (alertes favoris, filtre par candidat).
# Recherche dans le titre d'origine, majuscules comprises, pour éviter « la renaissance de… » ou « nouvelle énergie solaire ».
PARTIS = {
    "lepen": r"\bRassemblement national\b|\bRN\b|\bBardella\b",
    "melenchon": r"\bLa France insoumise\b|\bLFI\b|\b[Ii]nsoumis(es?)?\b",
    "retailleau": r"\bLes Républicains\b|\bLR\b",
    "attal": r"(?<![Ll]a )\bRenaissance\b",
    "philippe": r"\bHorizons\b",
    "lisnard": r"\bNouvelle Énergie\b",
    "zemmour": r"\bReconquête\b",
    "tondelier": r"\bLes Écologistes\b|\bEELV\b",
    "roussel": r"\bPCF\b|\bParti communiste\b|\bcommunistes?\b",
    "arthaud": r"\bLutte ouvrière\b",
    "dupont-aignan": r"\bDebout la France\b",
    "bouamrane": r"\bParti socialiste\b|\bPS\b|\bsocialistes?\b",
    "glucksmann": r"\bPlace publique\b|\bParti socialiste\b|\bPS\b",
    "villepin": r"\bLa France humaniste\b",
}
CAMPAGNE = re.compile(r"presidentiel|2027|candidat|campagne|elysee|primaire|parrainage|programme|meeting|sondage")
PARTIS = {k: re.compile(v) for k, v in PARTIS.items() if k in KEYS}
GENERAL = ["presidentielle", "elysee", "parrainage", "primaire", "candidat", "arcom", "conseil constitutionnel"]
FOREIGN_URL = re.compile(r"/(monde|international|afrique|europe|ameriques?|asie|moyen-orient|world|etats-unis|international-[a-z]+)/", re.I)
FOREIGN = re.compile(r"\b(nigeria|kenya|ghana|senegal|cameroun|cote d.ivoire|gabon|congo|rdc|benin|togo|mali|guinee|madagascar|tchad|burkina|niger|algerie|maroc|tunisie|egypte|liban|syrie|iran|irak|israel|russie|bielorussie|georgie|moldavie|roumanie|pologne|hongrie|serbie|portugal|espagne|italie|allemagne|autriche|irlande|islande|finlande|turquie|bresil|argentine|chili|colombie|perou|bolivie|equateur|venezuela|mexique|etats-unis|americaine?s?|trump|coree|japon|taiwan|philippines|indonesie|inde|sri lanka|haiti|comores|seychelles|maurice|centrafrique)\b")
POLL = re.compile(r"sondage|intentions? de vote|barom[eè]tre|\d+\s?%|\bpoints?\b.*\bavance", re.I)

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (presidentielle-2027 PWA; +https://denyslx33.github.io/presidentielle-2027/)"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()

def text(e, tag):
    x = e.find(tag)
    if x is None:
        x = next((c for c in e if c.tag.split("}")[-1] == tag), None)
    return html.unescape(re.sub(r"<[^>]+>", "", x.text or "")).strip() if x is not None and x.text else ""

now = dt.datetime.now(dt.timezone.utc)
try:
    old = json.load(open("data/flux.json", encoding="utf-8"))
except Exception:
    old = {"items": []}
items = {i["u"]: i for i in old.get("items", []) if i.get("qui") or not i.get("camp") or CAMPAGNE.search(norm(i["t"]))} if old.get("v") == 4 else {}
stats = {}
for src, url in FEEDS:
    n = 0
    try:
        root = ET.fromstring(fetch(url))
        for it in root.iter("item"):
            t, link = text(it, "title"), text(it, "link")
            if not t or not link.startswith("http"):
                continue
            desc = text(it, "description")
            nt, nd = norm(t), norm(desc)
            qui = [cid for cid, ks in KEYS.items() if any(re.search(r"\b" + re.escape(k) + r"\b", nt) for k in ks)]
            camp = [cid for cid, rx in PARTIS.items() if cid not in qui and rx.search(t)]
            if not qui and not camp:
                # sans candidat cité dans le titre : il faut la présidentielle française 2027, sans signe d'un autre pays
                fr = ("presidentielle" in nt and ("2027" in nt + " " + nd or "elysee" in nt + " " + nd)) or ("2027" in nt and any(g in nt for g in GENERAL))
                if not fr or FOREIGN_URL.search(link) or FOREIGN.search(nt + " " + nd):
                    continue
            elif not qui and (FOREIGN_URL.search(link) or FOREIGN.search(nt) or not CAMPAGNE.search(nt + " " + nd)):
                # actu d'un parti sans candidat cité : seulement si elle touche à la campagne
                continue
            if POLL.search(t):
                continue
            d = text(it, "pubDate") or text(it, "date") or text(it, "updated") or text(it, "published")
            when = None
            try:
                when = email.utils.parsedate_to_datetime(d).astimezone(dt.timezone.utc)
            except Exception:
                try:
                    when = dt.datetime.fromisoformat(d.replace("Z", "+00:00")).astimezone(dt.timezone.utc)
                except Exception:
                    m = re.search(r"-(\d{2})-(\d{2})-(20\d{2})-", link)
                    if m:
                        when = dt.datetime(int(m[3]), int(m[2]), int(m[1]), 12, tzinfo=dt.timezone.utc)
            if when is None:
                when = dt.datetime.fromisoformat(items[link]["d"].replace("Z", "+00:00")) if link in items else now
            if when > now:
                when = now
            items[link] = {"t": t, "s": src, "u": link, "d": when.strftime("%Y-%m-%dT%H:%M:%SZ"), "qui": qui}
            if camp:
                items[link]["camp"] = camp
            n += 1
        stats[src] = n
    except Exception as e:
        stats[src] = "erreur: " + type(e).__name__

# garde 7 jours, supprime les doublons de titre, 200 max
cut = (now - dt.timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
seen, out = set(), []
for i in sorted(items.values(), key=lambda x: x["d"], reverse=True):
    k = norm(re.sub(r"\W+", " ", i["t"]))[:80]
    if i["d"] < cut or k in seen or POLL.search(i["t"]):
        continue
    seen.add(k); out.append(i)
out = out[:200]
new = {"v": 4, "items": out, "sources": stats}
if old.get("v") != 4 or json.dumps(new.get("items")) != json.dumps(old.get("items")) or old.get("sources") != stats:
    new["maj"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    json.dump(new, open("data/flux.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print(json.dumps(stats, ensure_ascii=False), len(out))
