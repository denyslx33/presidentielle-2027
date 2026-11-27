#!/usr/bin/env python3
"""Petits candidats en réserve : un candidat passe tout seul dans l'appli (fiche, liste, actu)
dès qu'il atteint au moins 1 % dans au moins 2 sondages différents des 60 derniers jours.
Sans IA. Prévient les téléphones « Alertes de test » (Dénys) quand ça arrive."""
import csv, json, os, urllib.request
from datetime import date, timedelta

SEUIL, NB, JOURS = 1.0, 2, 60
F = 'data/candidats.json'

def polls():
    out = []
    for p in ('data/sondages.csv', 'data/ajouts.csv'):
        if os.path.exists(p): out += list(csv.DictReader(open(p, encoding='utf-8')))
    return out

def main():
    d = json.load(open(F, encoding='utf-8'))
    res = d.get('reserve', [])
    if not res: return
    lim = (date.today() - timedelta(days=JOURS)).isoformat()
    vus = {}
    for r in polls():
        if (r.get('fin_enquete') or '') < lim or not (r.get('tour') or '').startswith('1'): continue
        try: v = float(str(r.get('intentions', '')).replace(',', '.'))
        except ValueError: continue
        if v >= SEUIL: vus.setdefault(r['complete_name'], set()).add((r['nom_institut'], r['fin_enquete']))
    promus = [c for c in res if len(vus.get(c['nom'], ())) >= NB]
    if not promus: print('Aucun candidat de réserve à ajouter'); return
    for c in promus:
        res.remove(c); c['promu_auto'] = date.today().isoformat(); d['principaux'].append(c)
    d['principaux'].sort(key=lambda c: c['id']); d['maj'] = date.today().isoformat()
    json.dump(d, open(F, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    noms = ', '.join(c['nom'] for c in promus)
    print('Ajouté(s) dans l\'appli :', noms)
    api, tok = os.environ.get('PUSH_API', '').rstrip('/'), os.environ.get('SEND_TOKEN', '')
    if api and tok:
        msg = {'topic': 'test', 'title': 'Nouveau candidat dans l\'appli', 'body': f'{noms} atteint 1 % dans plusieurs sondages : sa fiche est en ligne. Pense à sa photo.', 'url': './#candidats', 'tag': 'reserve', 'urgent': True}
        req = urllib.request.Request(api + '/send', data=json.dumps(msg).encode(), headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + tok, 'User-Agent': 'NousVotons-Alertes/1.0'})
        try: urllib.request.urlopen(req, timeout=30)
        except Exception as e: print('alerte non envoyée', e)

if __name__ == '__main__':
    main()
