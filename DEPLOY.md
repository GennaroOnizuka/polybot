# Deploy del bot POLYBOT (sempre acceso)

Il bot è un processo Python perpetuo (`bot_async.py`) con WebSocket. Per tenerlo **sempre on** puoi usare una di queste opzioni.

---

## Deploy con Docker (consigliato se vuoi usare Docker)

**Requisiti:** Docker e Docker Compose installati. Il file `.env` deve esistere nella cartella del progetto (con chiavi, proxy, `MONITOR_EVENT_SLUG`, ecc.).

1. **Nella cartella del progetto** (dove ci sono `Dockerfile`, `docker-compose.yml`, `.env`):
   ```bash
   cd /path/to/POLYBOT
   ```

2. **Build e avvio in background** (restart automatico se il bot crasha):
   ```bash
   docker compose up -d --build
   ```

3. **Controllare i log:**
   ```bash
   docker compose logs -f
   ```
   (Ctrl+C per uscire dai log; il container continua a girare.)

4. **Comandi utili:**
   ```bash
   docker compose ps          # stato del container
   docker compose stop        # ferma il bot
   docker compose start       # riavvia (senza rebuild)
   docker compose down        # ferma e rimuove il container
   ```

Il `Dockerfile` e `docker-compose.yml` sono già nel repo. Il proxy (DataImpulse) funziona: le variabili `PROXY_*` vanno nel `.env` che viene caricato con `env_file: .env`.

---

## Opzione 1: VPS Linux (senza Docker – economica e affidabile)

**Costo:** ~5–7 €/mese (Hetzner, DigitalOcean, Linode, ecc.)

**Pro:** Controllo totale, nessun sleep, riavvio automatico con systemd, stesso ambiente ovunque.

1. **Crea un VPS** (Ubuntu 22.04 o 24.04) e accedi via SSH.

2. **Installa dipendenze:**
   ```bash
   sudo apt update && sudo apt install -y python3 python3-pip python3-venv git
   ```

3. **Clona il progetto** (o carica i file):
   ```bash
   cd /opt
   sudo git clone <URL_DEL_TUO_REPO> polybot
   # oppure: scp -r ./POLYBOT user@server:/opt/polybot
   sudo chown -R $USER:$USER /opt/polybot
   cd /opt/polybot
   ```

4. **Crea ambiente virtuale e installa dipendenze:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

5. **Configura `.env`** con le tue chiavi (come in `.env.example`):
   ```bash
   cp .env.example .env
   nano .env   # inserisci PRIVATE_KEY, PROXY_*, MONITOR_EVENT_SLUG, ecc.
   ```

6. **Installa il servizio systemd** (avvio al boot + restart se crasha):
   ```bash
   sudo cp deploy/polybot.service /etc/systemd/system/
   sudo nano /etc/systemd/system/polybot.service   # verifica path /opt/polybot
   sudo systemctl daemon-reload
   sudo systemctl enable polybot
   sudo systemctl start polybot
   sudo systemctl status polybot
   ```

7. **Comandi utili:**
   ```bash
   sudo systemctl stop polybot    # ferma
   sudo systemctl start polybot   # avvia
   sudo journalctl -u polybot -f  # log in tempo reale
   ```

---

## Opzione 2: Railway (deploy da Git, zero configurazione server)

**Costo:** ~5 $/mese per una piccola VM sempre accesa (no free tier 24/7).

**Pro:** Deploy da GitHub/GitLab, gestione semplice, log e metriche.

1. Vai su [railway.app](https://railway.app), crea un progetto e collega il repo.

2. Aggiungi un **service** di tipo “Empty” (o “Python”) e configura:
   - **Build:** N/A oppure comando custom (Railway rileva spesso Python).
   - **Start command:** `python3 bot_async.py`
   - **Root directory:** cartella del bot se il repo è monorepo.

3. Nella scheda **Variables** aggiungi tutte le variabili del `.env` (una per riga):
   - `PRIVATE_KEY`, `POLYMARKET_API_KEY`, `POLYMARKET_API_SECRET`, `POLYMARKET_API_PASSPHRASE`
   - `SIGNATURE_TYPE`, `POLY_SAFE_ADDRESS`
   - `PROXY_URL` (o `PROXY_HOST`, `PROXY_PORT`, `PROXY_USER`, `PROXY_PASSWORD`)
   - `MONITOR_EVENT_SLUG`, `SINGLE_BET`, ecc.

4. Deploy: al push sul branch collegato il bot si ridistribuisce. Il servizio resta sempre on (a pagamento).

---

## Opzione 3: Docker (stesso setup ovunque – VPS, cloud, casa)

**Costo:** dipende da dove gira il container (stesso VPS di opzione 1, o altro host).

**Pro:** Ambiente identico in locale e in produzione, facile da spostare.

1. **Build e run in locale per test:**
   ```bash
   cd /path/to/POLYBOT
   docker compose up -d
   docker compose logs -f
   ```

2. **Su un server:** copia la cartella (inclusi `Dockerfile` e `docker-compose.yml`), crea il file `.env`, poi:
   ```bash
   docker compose up -d
   ```

3. **Riavvio automatico:** è già configurato in `docker-compose.yml` (`restart: unless-stopped`). Su un VPS puoi anche usare systemd per avviare `docker compose up -d` al boot.

---

## Confronto rapido

| Soluzione   | Costo/mese   | Difficoltà | Riavvio se crasha | Note                    |
|------------|--------------|------------|--------------------|-------------------------|
| VPS + systemd | ~5–7 €   | Media      | Sì (systemd)       | Massima affidabilità    |
| Railway    | ~5 $         | Bassa      | Sì (platform)      | Zero gestione server    |
| Docker     | come l’host  | Media      | Sì (restart policy)| Portabile, stesso env   |

**Raccomandazione:** per un bot trading “sempre on” la scelta più solida è **VPS + systemd** (opzione 1). Se preferisci non gestire un server, **Railway** è la più semplice; **Docker** è utile se vuoi lo stesso setup su più macchine o in locale.

---

## Proxy / “VPN” (DataImpulse) sul servizio online

Il proxy **non** dipende da Replit o dalla tua rete: è attivato **solo dalle variabili d’ambiente**. Su qualsiasi servizio a pagamento (VPS, Railway, Docker):

- Imposta le stesse variabili che usi in locale: `PROXY_URL` (o `PROXY_HOST`, `PROXY_PORT`, `PROXY_USER`, `PROXY_PASSWORD`).
- All’avvio il bot usa quel proxy per tutto il traffico HTTP/HTTPS (API CLOB, ordini, check IP). L’IP visto da Polymarket sarà quello del proxy (es. Svizzera), quindi il 403 regionale viene evitato.

**Conferma:** sì, il proxy partirà sul servizio online purché le variabili proxy siano configurate nelle Variables / nel `.env` del deploy.

## Checklist pre-deploy

- [ ] File `.env` compilato (mai committare `.env` in Git)
- [ ] Variabili **proxy** (PROXY_*) impostate anche sul servizio online
- [ ] Test in locale: `python3 bot_async.py` funziona e si riconnette ai WebSocket
- [ ] Su VPS: porta in uscita 443 (HTTPS/WSS) non bloccata dal firewall
