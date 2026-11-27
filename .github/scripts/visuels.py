"""Visuels des émissions : récupère l'image d'aperçu (og:image) de la page source des débats et émissions à venir."""
import json, re, html, urllib.request, urllib.parse, datetime as dt

P = "data/agenda.json"
UA = {"User-Agent": "Mozilla/5.0 (compatible; NousVotonsBot/1.0)"}
EXCLUS = ("wikipedia.org", "votons-2027", "datan.fr")

def og_image(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=15) as r:
        page = r.read(600000).decode("utf-8", "ignore")
    for prop in ("og:image", "twitter:image", "og:image:url"):
        for m in re.finditer(r"<meta[^>]+>", page, re.I):
            tag = m.group(0)
            if re.search(r'(property|name)\s*=\s*["\']' + re.escape(prop) + r'["\']', tag, re.I):
                c = re.search(r'content\s*=\s*["\']([^"\']+)', tag, re.I)
                if c:
                    img = urllib.parse.urljoin(url, html.unescape(c.group(1).strip()))
                    if img.startswith("https://"):
                        return img
    return ""

d = json.load(open(P, encoding="utf-8"))
today = dt.date.today().isoformat()
change = False
for e in d.get("evenements", []):
    if e.get("type") not in ("debat", "emission") or "image" in e:
        continue
    if (e.get("fin") or e.get("date") or "") < today:
        continue
    url = e.get("url") or ""
    if not url.startswith("http") or any(x in url for x in EXCLUS):
        continue
    try:
        e["image"] = og_image(url)
    except Exception:
        continue
    change = True
if change:
    open(P, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False, indent=1) + "\n")
