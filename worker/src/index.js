// Worker Cloudflare « Nous votons » : abonnements et envoi des notifications.
// Gratuit : Workers (100 000 requêtes/jour) + D1 (base de données).
import { sendPush } from './webpush.js';

const TOPICS = ['favoris', 'majeur', 'sondages', 'tv', 'test', 'tout']; // test : téléphones en mode test ; tout : rythme « Tout suivre »
// Plafond par type d'alerte, par personne et par jour. « Tout suivre » triple les plafonds. Les essais ne comptent pas.
const PLAFOND = { favoris: 6, majeur: 2, sondages: 2, tv: 1 };
const LOT = 40;           // envois par appel (limite gratuite : 50 sous-requêtes)

const jourParis = () => new Intl.DateTimeFormat('fr-CA', { timeZone: 'Europe/Paris' }).format(new Date());

function cors(env, res) {
  res.headers.set('Access-Control-Allow-Origin', env.ALLOWED_ORIGIN);
  res.headers.set('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.headers.set('Access-Control-Allow-Headers', 'Content-Type');
  return res;
}
const json = (o, s = 200) => new Response(JSON.stringify(o), { status: s, headers: { 'Content-Type': 'application/json' } });

async function idOf(endpoint) {
  const h = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(endpoint));
  return [...new Uint8Array(h)].slice(0, 16).map((b) => b.toString(16).padStart(2, '0')).join('');
}
const clean = (arr, ok) => (Array.isArray(arr) ? arr.filter((x) => typeof x === 'string' && (!ok || ok.includes(x))).slice(0, 20) : []);

export default {
  async fetch(req, envIn) {
    const env = { ALLOWED_ORIGIN: 'https://denyslx33.github.io', VAPID_SUBJECT: 'mailto:denyslx.pro@gmail.com', ...envIn };
    const url = new URL(req.url);
    if (req.method === 'OPTIONS') return cors(env, new Response(null, { status: 204 }));

    // Abonnement depuis l'app (ou mise à jour des choix)
    if (url.pathname === '/subscribe' && req.method === 'POST') {
      const b = await req.json().catch(() => null);
      const s = b && b.subscription;
      if (!s || !s.endpoint || !s.keys || !s.keys.p256dh || !s.keys.auth || !/^https:\/\//.test(s.endpoint)) return cors(env, json({ ok: false }, 400));
      const id = await idOf(s.endpoint);
      await env.DB.prepare(`INSERT INTO subs (id, endpoint, p256dh, auth, topics, favs, created) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)
        ON CONFLICT(id) DO UPDATE SET p256dh = ?3, auth = ?4, topics = ?5, favs = ?6`)
        .bind(id, s.endpoint, s.keys.p256dh, s.keys.auth, JSON.stringify(clean(b.topics, TOPICS)), JSON.stringify(clean(b.favs)), jourParis()).run();
      return cors(env, json({ ok: true }));
    }

    // Désabonnement
    if (url.pathname === '/unsubscribe' && req.method === 'POST') {
      const b = await req.json().catch(() => null);
      if (b && b.endpoint) await env.DB.prepare('DELETE FROM subs WHERE id = ?1').bind(await idOf(b.endpoint)).run();
      return cors(env, json({ ok: true }));
    }

    // À partir d'ici : réservé à la GitHub Action (mot de passe)
    if (req.headers.get('Authorization') !== `Bearer ${env.SEND_TOKEN}`) return json({ ok: false }, 401);

    if (url.pathname === '/stats') {
      const rows = (await env.DB.prepare('SELECT topics, favs FROM subs').all()).results;
      const sujets = {}; let fav = {}, nfav = 0;
      for (const x of rows) {
        const t = JSON.parse(x.topics || '[]'); t.forEach((k) => { sujets[k] = (sujets[k] || 0) + 1; });
        if (t.includes('favoris')) { nfav++; JSON.parse(x.favs || '[]').forEach((c) => { fav[c] = (fav[c] || 0) + 1; }); }
      }
      // Classement des favoris : anonyme, et seulement à partir de 50 abonnés pour que personne ne soit reconnaissable
      return json({ abonnes: rows.length, sujets, favoris: nfav >= 50 ? fav : null });
    }

    // Envoi d'une notification à un sujet, par lots. Corps :
    // { topic, cands?, title, body, url, tag, after? }  ->  { sent, skipped, dead, next }
    if (url.pathname === '/send' && req.method === 'POST') {
      const m = await req.json();
      if (!TOPICS.includes(m.topic) || !m.title) return json({ ok: false }, 400);
      const day = jourParis();
      const rows = (await env.DB.prepare(`SELECT * FROM subs WHERE id > ?1 AND topics LIKE ?2 ORDER BY id LIMIT ?3`)
        .bind(m.after || '', `%"${m.topic}"%`, LOT).all()).results;
      let sent = 0, skipped = 0, dead = 0;
      const payload = { title: m.title, body: m.body || '', url: m.url || '/', tag: m.tag || m.topic };
      await Promise.all(rows.map(async (s) => {
        if (m.topic === 'favoris') {
          const favs = JSON.parse(s.favs || '[]');
          if (!(m.cands || []).some((c) => favs.includes(c))) { skipped++; return; }
        }
        let cpt = {}; try { const d = JSON.parse(s.day || '{}'); if (d.d === day) cpt = d.c || {}; } catch (e) {}
        const tout = JSON.parse(s.topics || '[]').includes('tout');
        const max = (PLAFOND[m.topic] || 2) * (tout ? 3 : 1);
        if ((cpt[m.topic] || 0) >= max && !m.urgent && m.topic !== 'test') { skipped++; return; }
        const st = await sendPush(s, payload, env).catch(() => 0);
        if (st === 404 || st === 410) { dead++; await env.DB.prepare('DELETE FROM subs WHERE id = ?1').bind(s.id).run(); return; }
        if (st >= 200 && st < 300) { sent++; if (m.topic !== 'test') { cpt[m.topic] = (cpt[m.topic] || 0) + 1; await env.DB.prepare('UPDATE subs SET day = ?2, n = ?3 WHERE id = ?1').bind(s.id, JSON.stringify({ d: day, c: cpt }), Object.values(cpt).reduce((a, b) => a + b, 0)).run(); } }
      }));
      return json({ sent, skipped, dead, next: rows.length === LOT ? rows[rows.length - 1].id : null });
    }

    return json({ ok: false }, 404);
  },
  // Réveil toutes les 15 minutes (déclencheur cron de Cloudflare) : relance le fil d'actu sur GitHub,
  // qui enchaîne ensuite les sondages et les alertes. GH_TOKEN : clé GitHub limitée aux Actions de ce dépôt.
  async scheduled(event, envIn, ctx) {
    if (!envIn.GH_TOKEN) return;
    const r = await fetch('https://api.github.com/repos/denyslx33/presidentielle-2027/actions/workflows/flux.yml/dispatches', {
      method: 'POST',
      headers: { Authorization: `Bearer ${envIn.GH_TOKEN}`, Accept: 'application/vnd.github+json', 'User-Agent': 'nousvotons-push', 'Content-Type': 'application/json' },
      body: JSON.stringify({ ref: 'main' }),
    });
    console.log('Réveil GitHub :', r.status);
  },
};
