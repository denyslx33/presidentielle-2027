#!/usr/bin/env python3
"""Fichier de sondages allégé pour l'appli : seulement 2026 et les colonnes utiles.
Tourne sur les serveurs de GitHub, sans IA, sans rien sur l'ordinateur de Dénys."""
import csv, io, os, sys, urllib.request

URL = 'https://raw.githubusercontent.com/MieuxVoter/presidentielle2027/refs/heads/main/presidentielle2027.csv'
OUT = 'data/sondages.csv'
COLS = ['poll_id', 'hypothese', 'nom_institut', 'commanditaire', 'debut_enquete', 'fin_enquete', 'echantillon',
        'tour', 'complete_name', 'parti', 'intentions', 'erreur_sup']
DEPUIS = '2026-01-01'

def main():
    raw = urllib.request.urlopen(URL, timeout=30).read().decode('utf-8')
    rows = list(csv.DictReader(io.StringIO(raw)))
    if len(rows) < 1000 or not set(COLS) <= set(rows[0]):
        sys.exit('Source douteuse, fichier non remplacé')  # on garde l'ancien plutôt qu'un fichier cassé
    keep = [r for r in rows if (r.get('fin_enquete') or '') >= DEPUIS]
    buf = io.StringIO(); w = csv.writer(buf, lineterminator='\n'); w.writerow(COLS)
    for r in keep: w.writerow([r.get(c, '') for c in COLS])
    new = buf.getvalue()
    old = open(OUT, encoding='utf-8').read() if os.path.exists(OUT) else ''
    if new != old:
        open(OUT, 'w', encoding='utf-8').write(new)
    print(f'{len(keep)} lignes, {len(new)//1024} Ko', 'modifié' if new != old else 'inchangé')

if __name__ == '__main__':
    main()
