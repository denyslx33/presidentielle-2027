#!/usr/bin/env python3
"""Petits candidats en réserve : un candidat passe tout seul dans l'appli (fiche, liste, actu)
dès qu'il atteint au moins 1 % dans au moins 2 sondages différents des 60 derniers jours.
Sans IA. Prévient les téléphones « Alertes de test » (Dénys) quand ça arrive."""
import csv, json, os, re, unicodedata, urllib.request
from datetime import date, timedelta

SEUIL, NB, JOURS = 1.0, 2, 60
F = 'data/candidats.json'

def polls():
    out = []
    for p in ('data/sondages.csv', 'data/ajouts.csv'):
        if os.path.exists(p): out += list(csv.DictReader(open(p, encoding='utf-8')))
    return out

def norm(x):
    x = unicodedata.normalize('NFD', x.lower())
    return ''.join(ch for ch in x if unicodedata.category(ch) != 'Mn').replace('’', "'")

# Annonce officielle de candidature dans un titre de presse
ANNONCE = re.compile(r"(annonce|officialise|declare|confirme|lance) sa candidature|se (declare|lance|porte) candidate?|(est|sera) candidate?|candidate? (a|pour) la presidentielle|entre (officiellement )?dans la course")

def alerte(titre, corps):
    api, tok = os.environ.get('PUSH_API', '').rstrip('/'), os.environ.get('SEND_TOKEN', '')
    if not (api and tok): return
    msg = {'topic': 'test', 'title': titre, 'body': corps, 'url': './#candidats', 'tag': 'reserve', 'urgent': True}
    req = urllib.request.Request(api + '/send', data=json.dumps(msg).encode(), headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + tok, 'User-Agent': 'NousVotons-Alertes/1.0'})
    try: urllib.request.urlopen(req, timeout=30)
    except Exception as e: print('alerte non envoyée', e)

def officialise(d):
    """Une candidature pas encore officielle le devient quand au moins 2 médias différents
    du fil d'actu titrent sur son annonce (nom complet + formule d'annonce, pas au conditionnel)."""
    try: flux = json.load(open('data/flux.json', encoding='utf-8')).get('items', [])
    except Exception: return []
    faits = []
    for c in d.get('reserve', []):
        if c.get('officiel'): continue
        nom = norm(c['nom'])
        its = [i for i in flux if nom in norm(i['t']) and ANNONCE.search(norm(i['t'])) and not re.search(r"\b(pourrait|envisage|hesite|n'exclut|songe|renonce|ne sera pas)\b", norm(i['t']))]
        if len({i['s'] for i in its}) < 2: continue
        it = sorted(its, key=lambda i: i['d'])[0]
        c['officiel'] = True
        c['annonce'] = 'Candidature annoncée le ' + it['d'][8:10] + '/' + it['d'][5:7] + '/' + it['d'][:4] + '.'
        c['source_annonce'] = {'nom': it['s'], 'url': it['u']}
        faits.append(c['nom'])
    return faits

def main():
    d = json.load(open(F, encoding='utf-8'))
    res = d.get('reserve', [])
    if not res: return
    faits = officialise(d)
    if faits:
        d['maj'] = date.today().isoformat()
        json.dump(d, open(F, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('Candidature officielle :', ', '.join(faits))
        alerte('Candidature officielle', ', '.join(faits) + ' : annonce reprise par plusieurs médias, ajouté à « Les autres candidats ». Vérifie sa fiche.')
    lim = (date.today() - timedelta(days=JOURS)).isoformat()
    vus = {}
    for r in polls():
        if (r.get('fin_enquete') or '') < lim or not (r.get('tour') or '').startswith('1'): continue
        try: v = float(str(r.get('intentions', '')).replace(',', '.'))
        except ValueError: continue
        if v >= SEUIL: vus.setdefault(r['complete_name'], set()).add((r['nom_institut'], r['fin_enquete']))
    promus = [c for c in res if c.get('officiel') and len(vus.get(c['nom'], ())) >= NB]
    if not promus: print('Aucun candidat de réserve à ajouter'); return
    for c in promus:
        res.remove(c); c['promu_auto'] = date.today().isoformat(); d['principaux'].append(c)
    d['principaux'].sort(key=lambda c: c['id']); d['maj'] = date.today().isoformat()
    json.dump(d, open(F, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    noms = ', '.join(c['nom'] for c in promus)
    print('Ajouté(s) dans l\'appli :', noms)
    alerte('Nouveau candidat dans l\'appli', f'{noms} atteint 1 % dans plusieurs sondages : sa fiche est en ligne. Pense à sa photo.')

if __name__ == '__main__':
    main()
