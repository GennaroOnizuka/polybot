# POLYBOT – farlo girare con il PC spento

**Importante:** se il bot gira sul tuo Mac/PC, quando **spegni il computer si ferma**.  
Per averlo **sempre acceso** (anche con PC spento) devi metterlo su un **server in cloud** che resta acceso 24/7. Costa circa 5–7 €/mese (VPS) o ~5 $/mese (Railway).

Sotto trovi tre strade: **A) VPS + Docker**, **B) Railway**, **C) Render** (tutte senza tenere il PC acceso).

---

## Prima di tutto: il file `.env`

Sul tuo Mac, nella cartella POLYBOT, devi avere un file `.env` con tutte le variabili (chiavi, proxy, evento, ecc.). Se il bot andava in locale, ce l’hai già.  
Questo file **lo copierai sul server** (o lo incollerai come “Environment” / “Variables” su Railway o Render). **Non** mettere mai il `.env` su Git o in posti pubblici.

---

## Opzione A: VPS + Docker (server sempre acceso)

Un VPS è un mini-computer in cloud: ci metti sopra il progetto e Docker; il bot gira 24/7 anche con il tuo PC spento.

### A1. Crea un VPS

1. Scegli un provider (es. [Hetzner](https://www.hetzner.com/cloud), [DigitalOcean](https://www.digitalocean.com), [Linode](https://www.linode.com)).
2. Crea un server (droplet/instance):
   - **OS:** Ubuntu 22.04 o 24.04
   - **Tipo:** il piano più economico (es. 1 vCPU, 1 GB RAM, ~5 €/mese)
3. Annota **IP pubblico** e **utente** (di solito `root` o `ubuntu`). Ricevi anche una chiave SSH o una password.

### A2. Connettiti al VPS

Dal tuo Mac (Terminale):

```bash
ssh root@IP_DEL_TUO_VPS
```

(Oppure `ssh ubuntu@IP_DEL_TUO_VPS` se il provider usa l’utente `ubuntu`.)  
Se chiede la password, usala; se usa una chiave SSH, assicurati di averla configurata.

### A3. Installa Docker sul VPS

Una volta collegato al VPS (prompt tipo `root@server:~#`), esegui:

```bash
apt-get update && apt-get install -y docker.io docker-compose-plugin
```

Poi (opzionale ma utile, per non usare sempre root):

```bash
usermod -aG docker root
```

(Se hai creato un utente diverso da `root`, metti quel nome al posto di `root`.)

### A4. Copia il progetto POLYBOT dal Mac al VPS

**Sul tuo Mac** (apri un secondo terminale, lascia la SSH aperta nell’altro), dalla cartella che contiene POLYBOT:

```bash
cd /Users/matteogianino/Desktop
scp -r POLYBOT root@IP_DEL_TUO_VPS:~/
```

Inserisci la password del VPS se richiesta. Così la cartella `POLYBOT` (con `Dockerfile`, `docker-compose.yml`, `bot_async.py`, `.env`, ecc.) finisce nella home del VPS (`~/POLYBOT`).

**Importante:** nel progetto deve esserci il file `.env` (sul Mac è nella cartella POLYBOT; con `scp -r` viene copiato). Se per sicurezza non vuoi includere `.env` nello `scp`, dopo la copia crea il `.env` sul server (es. `nano ~/POLYBOT/.env`) e incolla le variabili.

### A5. Avvia il bot sul VPS

Torna nel terminale dove sei connesso **al VPS** (SSH) e esegui:

```bash
cd ~/POLYBOT
docker compose up -d --build
```

La prima volta scarica l’immagine e le dipendenze (1–2 minuti). Poi vedrai qualcosa tipo `Container polybot Started`.

### A6. Controlla che giri (e che resti su dopo che ti disconnetti)

- Log in tempo reale:  
  `docker compose logs -f`  
  (Ctrl+C per uscire; il bot **continua a girare**.)
- Stato:  
  `docker compose ps`  
  deve mostrare `polybot` in stato `running`.

Quando chiudi la SSH (o spegni il Mac), il VPS resta acceso e il bot **continua a girare**. Il proxy (DataImpulse) funziona perché le variabili `PROXY_*` sono nel `.env` sul server.

**Comandi utili sul VPS (via SSH):**
- `cd ~/POLYBOT && docker compose logs -f` → vedi i log
- `cd ~/POLYBOT && docker compose stop` → fermi il bot
- `cd ~/POLYBOT && docker compose start` → riavvii il bot

---

## Opzione B: Railway (nessun server da gestire)

Railway è un servizio che esegue il tuo codice in cloud. Non devi creare un VPS né usare SSH: colleghi un repo Git (o carichi il progetto) e imposti le variabili; loro tengono il processo sempre acceso (a pagamento).

### B1. Account e progetto

1. Vai su [railway.app](https://railway.app) e crea un account.
2. Crea un nuovo progetto e aggiungi un servizio (es. “Empty” o “Deploy from GitHub”).

### B2. Fornire il codice

- **Se usi GitHub:** collega il repo che contiene POLYBOT. Imposta la **root directory** al percorso della cartella del bot (se il repo è solo POLYBOT, è la root).
- **Se non usi Git:** usa “Deploy from CLI” o carica i file come da istruzioni Railway (di solito serve il loro CLI e `railway up` dalla cartella del progetto).

### B3. Comando di avvio

Nel servizio, nella sezione **Settings** (o “Build & Deploy”), imposta:

- **Start command:**  
  `python3 bot_async.py`

(Se usi un Dockerfile, Railway può rilevarlo; in quel caso il comando è quello nel `CMD` del Dockerfile, cioè `python3 bot_async.py`.)

### B4. Variabili d’ambiente (il tuo `.env`)

Nella scheda **Variables** del servizio, aggiungi **tutte** le variabili del tuo `.env` (una per riga), ad esempio:

- `PRIVATE_KEY=...`
- `POLY_SAFE_ADDRESS=...`
- `SIGNATURE_TYPE=2`
- `PROXY_URL=...` (o PROXY_HOST, PROXY_PORT, PROXY_USER, PROXY_PASSWORD)
- `MONITOR_EVENT_SLUG=btc-updown-5m`
- ecc.

Niente spazi intorno al `=`. Il proxy funziona perché queste variabili sono le stesse che usa il bot.

### B5. Deploy

Salva e avvia il deploy. Railway costruirà l’ambiente e avvierà `python3 bot_async.py`. Con il piano a pagamento il servizio resta **sempre on**, anche con il tuo PC spento.

Per vedere i log: nella dashboard del servizio apri la sezione **Logs**.

---

## Opzione C: Render (Background Worker)

Render è un PaaS come Railway: colleghi un repo, imposti build/start e variabili; il bot gira in cloud. Per processi che **non servono pagine web** (come il nostro bot) si usa un **Background Worker**, che resta in esecuzione 24/7.

### C1. Account e repo su GitHub/GitLab

1. Vai su [render.com](https://render.com) e crea un account (o accedi con GitHub).
2. Il codice di POLYBOT deve essere su **GitHub** o **GitLab** (Render si collega al repo). Se non l’hai ancora:
   - Crea un repo (es. `polybot`) e **non** includere il file `.env` (metti `.env` in `.gitignore`).
   - Push del progetto: dalla cartella POLYBOT sul Mac:  
     `git init && git add . && git commit -m "polybot" && git remote add origin URL_DEL_REPO && git push -u origin main`

### C2. Crea un Background Worker su Render

1. Nella [Dashboard Render](https://dashboard.render.com): **New +** → **Background Worker**.
2. Collega il **repository** (GitHub/GitLab) e scegli il repo che contiene POLYBOT.
3. **Settings** del worker:
   - **Name:** ad es. `polybot`.
   - **Region:** scegli la più vicina (es. Frankfurt).
   - **Branch:** `main` (o il branch che usi).
   - **Root Directory:** lascia vuoto se il repo è tutto POLYBOT; altrimenti indica la sottocartella (es. `POLYBOT`).
   - **Runtime:** Python 3.
   - **Build Command:**  
     `pip install -r requirements.txt`
   - **Start Command:**  
     `python3 bot_async.py`

### C3. Variabili d’ambiente (il tuo `.env`)

Nella sezione **Environment** del worker aggiungi **tutte** le variabili del tuo `.env` (stesso formato che usi in locale):

- `PRIVATE_KEY=...`
- `POLY_SAFE_ADDRESS=...`
- `SIGNATURE_TYPE=2`
- `PROXY_URL=...` (o PROXY_HOST, PROXY_PORT, PROXY_USER, PROXY_PASSWORD)
- `MONITOR_EVENT_SLUG=btc-updown-5m`
- eventuali altre (POLYMARKET_API_KEY, ecc.)

**Non** mettere spazi intorno al `=`. Il proxy DataImpulse funziona perché il bot legge queste variabili come in locale.

### C4. Piano e deploy

- **Free tier:** il worker può andare in “sleep” o avere limiti; non è adatto a un bot che deve stare sempre acceso.
- **Piano a pagamento** (es. Starter): il Background Worker resta **sempre on** (~7 $/mese circa, controlla i prezzi su Render).

Clicca **Create Background Worker**. Render farà il build (`pip install -r requirements.txt`) e avvierà `python3 bot_async.py`. I **Logs** nella dashboard mostrano l’output del bot (WebSocket, proxy, ecc.).

Da quel momento il bot gira su Render 24/7 anche con il PC spento.

---

## Riepilogo

| Obiettivo              | Cosa fare |
|------------------------|-----------|
| Bot **sempre acceso** con PC spento | Mettere il bot su un **server** (VPS, Railway o Render). |
| VPS                    | Opzione A: VPS, Docker, copi POLYBOT, `docker compose up -d`. |
| Zero server (Railway)  | Opzione B: Railway, repo + Variables + start command. |
| Zero server (Render)  | Opzione C: Render, **Background Worker**, repo + Environment + `python3 bot_async.py`. |

In tutti i casi il bot gira **in cloud** 24/7; il tuo PC può restare spento.

---

## Docker solo sul tuo Mac (per test)

Se avvii il bot **solo sul tuo computer** con:

```bash
cd /Users/matteogianino/Desktop/POLYBOT
docker compose up -d --build
```

il bot gira finché il Mac è acceso e Docker è avviato. **Quando spegni il PC il bot si ferma.**  
Per “girare col PC spento” usa una delle opzioni A, B o C sopra (VPS, Railway o Render).
