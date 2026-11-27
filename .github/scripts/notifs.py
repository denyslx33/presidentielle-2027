#!/usr/bin/env python3
"""Repère ce qui mérite une alerte et l'envoie au serveur Cloudflare.
Tourne sur GitHub (gratuit). Sans IA : il lit seulement les fichiers déjà publiés.
Sans PUSH_API ni SEND_TOKEN, il affiche ce qu'il aurait envoyé (essai à blanc)."""
import csv, json, os, sys, urllib.request, urllib.error
from datetime import datetime, timedelta, timezone
import re, unicodedata
from zoneinfo import ZoneInfo

API, TOKEN = os.environ.get('PUSH_API', '').rstrip('/'), os.environ.get('SEND_TOKEN', '')
ETAT = 'data/notifs-etat.json'
now = datetime.now(ZoneInfo('Europe/Paris')); today = now.strftime('%Y-%m-%d')
PRIO = ['franceinfo', 'Le Monde', 'Ouest-France', 'La Croix', 'Le Figaro', 'Libération', 'Le Parisien', '20 Minutes', 'France 24', 'RFI', 'LCP', 'BFMTV']
MAJ = re.compile(r"(annonce|officialise|confirme) sa candidature|se (declare|lance) candidat|retire sa candidature|renonce a (la presidentielle|se presenter|sa candidature|etre candidat)|jette l.eponge|se retire de la course|conseil constitutionnel|liste (officielle )?des candidats")
def norm(t):
    t = unicodedata.normalize('NFD', t.lower()); return ''.join(c for c in t if unicodedata.category(c) != 'Mn')
def titre(it):
    t = re.sub(r'^(DIRECT|VIDÉO|VIDEO|INFO [A-Z0-9 ]+)[.:]\s*', '', it['t']).strip()
    return (t if len(t) <= 170 else t[:167].rsplit(' ', 1)[0] + '…') + f" ({it['s']})"

def load(p, d):
    try: return json.load(open(p, encoding='utf-8'))
    except Exception: return d

def polls():
    """Sondages de premier tour, un par institut et date (fichier allégé + ajouts à la main)."""
    seen = {}
    for p in ('data/sondages.csv', 'data/ajouts.csv'):
        if not os.path.exists(p): continue
        for r in csv.DictReader(open(p, encoding='utf-8')):
            if (r.get('fin_enquete') or '') < '2026-01-01': continue
            k = f"{r['nom_institut']}|{r['fin_enquete']}"
            seen.setdefault(k, r)
    return seen

def send(topic, title, body, url='./', tag=None, cands=None, urgent=False):
    msg = {'topic': topic, 'title': title, 'body': body, 'url': url, 'tag': tag or topic, 'cands': cands or [], 'urgent': urgent}
    if not (API and TOKEN):
        print('[essai]', json.dumps(msg, ensure_ascii=False)); return
    after, tot = '', 0
    for _ in range(500):  # 500 lots de 40, soit 20 000 abonnés par alerte
        req = urllib.request.Request(API + '/send', data=json.dumps({**msg, 'after': after}).encode(),
                                     headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + TOKEN, 'User-Agent': 'NousVotons-Alertes/1.0'})
        try:
            r = json.load(urllib.request.urlopen(req, timeout=60))
        except urllib.error.HTTPError as e:
            sys.exit(f"Serveur des alertes : erreur {e.code} {e.read()[:300]!r}")
        tot += r['sent']
        if not r['next']: break
        after = r['next']
    print(f'{topic}: {tot} envoyées, {r.get("skipped", 0)} ignorées, {r.get("dead", 0)} abonnements périmés')

def main():
    test = os.environ.get('TEST_MSG', '').strip()
    if test:  # alerte d'essai lancée à la main depuis GitHub (onglet Actions)
        send('test', 'Test Nous votons', test, './', 'test', urgent=True); return
    etat = load(ETAT, None); first = etat is None
    etat = etat or {'sondages': [], 'actu': [], 'tv': [], 'fav': {}, 'maj': ''}
    cand = {c['id']: c['nom'] for c in load('data/candidats.json', {}).get('principaux', [])}
    out = []

    # 1. Nouveaux sondages (sans chiffres dans l'alerte)
    for k, r in polls().items():
        if k in etat['sondages']: continue
        etat['sondages'].append(k)
        com = f" pour {r['commanditaire']}" if r.get('commanditaire') else ''
        out.append(('sondages', 'Nouveau sondage', f"{r['nom_institut']}{com}, enquête terminée le {datetime.strptime(r['fin_enquete'], '%Y-%m-%d').strftime('%d/%m')}. Voir les intentions de vote", './#sondages', 'sondage'))

    # 2. Favoris et infos majeures, à partir des titres des médias (data/flux.json, mis à jour sans IA
    #    toutes les 15 minutes). « Grosse actu » = au moins 3 médias différents en parlent en 3 heures.
    #    Une alerte par candidat et par jour au plus, une info majeure par jour au plus.
    flux = load('data/flux.json', {}).get('items', [])
    lo = (now - timedelta(hours=3)).astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    win = [i for i in flux if i.get('d', '') >= lo]
    etat.setdefault('fav', {}); etat.setdefault('maj', '')
    by = {}
    for i in win:
        for c in i.get('qui', []):
            by.setdefault(c, []).append(i)
    for c, its in by.items():
        if len({i['s'] for i in its}) < 3 or etat['fav'].get(c) == today or c not in cand: continue
        etat['fav'][c] = today
        it = sorted(its, key=lambda i: PRIO.index(i['s']) if i['s'] in PRIO else 99)[0]
        out.append(('favoris', cand[c], titre(it), f'./#c-{c}', 'fav-' + c, [c]))
    maj = [i for i in win if MAJ.search(norm(i['t']))]
    if len({i['s'] for i in maj}) >= 3 and etat['maj'] != today:
        etat['maj'] = today
        it = sorted(maj, key=lambda i: PRIO.index(i['s']) if i['s'] in PRIO else 99)[0]
        out.append(('majeur', 'Info importante', titre(it), './#flux', 'majeur'))
    # Le robot de mise à jour peut aussi marquer une actu « majeur »: true dans data/actu.json
    for it in load('data/actu.json', {}).get('items', []):
        k = it.get('url') or it.get('texte', '')[:80]
        if not it.get('majeur') or k in etat['actu'] or it.get('date', '') < today: continue
        etat['actu'].append(k)
        if etat['maj'] != today:
            etat['maj'] = today
            out.append(('majeur', 'Info importante', it['texte'], './#actu', 'majeur'))

    # 3. Grosses émissions TV du jour, envoyées à partir de 9 h
    if now.hour >= 9:
        for ev in load('data/agenda.json', {}).get('evenements', []):
            if ev.get('date') != today or ev.get('type') not in ('debat', 'emission'): continue
            k = today + '|' + ev['titre'][:60]
            if k in etat['tv']: continue
            etat['tv'].append(k)
            quand = f" à {ev['heure']}" if ev.get('heure') else ' ce soir' if ev.get('type') == 'debat' else " aujourd'hui"
            out.append(('tv', 'À la télé' + quand, f"{ev['titre']}{' sur ' + ev['chaine'] if ev.get('chaine') else ''}", './#agenda', 'tv'))

    if not (8 <= now.hour < 22) and out:
        print('Nuit : rien envoyé, ce sera au prochain passage après 8 h'); return
    if first:
        print('Premier passage : état enregistré, rien envoyé'); out = []
    for o in out[:6]:  # garde-fou : jamais une rafale
        send(*o)
    for k in etat:
        if isinstance(etat[k], list): etat[k] = etat[k][-400:]
    json.dump(etat, open(ETAT, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)

if __name__ == '__main__':
    main()
