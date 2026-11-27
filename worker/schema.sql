CREATE TABLE IF NOT EXISTS subs (
  id TEXT PRIMARY KEY,          -- empreinte de l'adresse d'abonnement
  endpoint TEXT NOT NULL,
  p256dh TEXT NOT NULL,
  auth TEXT NOT NULL,
  topics TEXT NOT NULL,         -- JSON : ["favoris","majeur","sondages","tv"]
  favs TEXT NOT NULL,           -- JSON : identifiants des candidats favoris
  day TEXT,                     -- jour du dernier envoi (AAAA-MM-JJ, Paris)
  n INTEGER DEFAULT 0,          -- nombre d'envois ce jour-là
  created TEXT
);
CREATE INDEX IF NOT EXISTS subs_created ON subs(created);
