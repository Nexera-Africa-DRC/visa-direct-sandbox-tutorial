# Visa Direct Sandbox en Python — Les 7 pièges non documentés

> 🇬🇧 English: [`README.md`](README.md)

**Traduction française à venir — Phase 2.**

Ce dépôt documente les 7 pièges qui m'ont coûté 6 heures de debug sur l'intégration Visa Direct sandbox en Python. Le README anglais contient actuellement l'intégralité du contenu technique.

Un article Medium en français ainsi qu'une traduction complète de ce README arrivent dans la phase 2 du projet. En attendant, le code source (`src/`) est bilingue par nature (comments en anglais mais variables/structure clairs) et les commentaires des pitfalls dans [`README.md`](README.md) devraient être compréhensibles.

**Résumé express des 7 pièges** :

1. `ca-cert.pem` au format DER, pas PEM → utiliser `certifi`
2. `cert.pem` et `key.pem` dépareillés → vérifier le modulus md5
3. Fichiers PEM sur une seule ligne → reformater avec `fold -w 64`
4. **MLE (Message Level Encryption) est obligatoire, pas optionnel** → tous les endpoints business l'exigent
5. **A128GCM, pas A256GCM** → confirmé en décompilant `vdpplayground.jar`
6. **Header HTTP `keyId:` obligatoire** quand MLE utilisé → non documenté
7. **httpx 0.28 échoue, `requests` passe** sur le même payload → utiliser `requests` wrappé dans `asyncio.to_thread`

Code fonctionnel : `src/visa_mle.py` + `src/push_funds.py`.

---

**Auteur :** Henock BARAKAEL — [Nexera Africa DRC](https://nexera.africa)  
**Licence :** MIT  
**Validé :** Visa sandbox le 2026-10-27 — Push Funds Transfer retourne `actionCode: 00` (APPROVED).

*Nexera · Fais-le tourner.*
