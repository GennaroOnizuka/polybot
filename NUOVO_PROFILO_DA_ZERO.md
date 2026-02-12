# Profilo nuovo da zero — setup corretto

Se crei un **nuovo account Polymarket** (nuovo wallet o nuovo profilo), segui questi passi per avere subito le chiavi giuste per il bot.

---

## 1. Crea il wallet / account Polymarket

- **Opzione A – MetaMask**  
  Crea un nuovo account in MetaMask (o usa uno esistente).  
  Esporta la **Private Key**. Su Polymarket connetti questo wallet.  
  L’indirizzo che vedi su Polymarket è il **proxy/funder** → `POLY_SAFE_ADDRESS`.  
  Usa **SIGNATURE_TYPE=2**.

- **Opzione B – Registrazione per email (Magic Link)**  
  Registrati su polymarket.com con **email** (niente MetaMask).  
  Poi: **Settings → Export key** (o Export Private Key) e esporta la **private key** del wallet.  
  L’indirizzo che vedi su Polymarket (in alto o in Settings) è il **funder** → `POLY_SAFE_ADDRESS`.  
  Usa **SIGNATURE_TYPE=1** (wallet email/Magic).

In entrambi i casi ti servono:
- **Private key** (esportata da Polymarket o MetaMask) = L1
- **Indirizzo mostrato su Polymarket** (dove fai Deposit) = **funder** → `POLY_SAFE_ADDRESS`

---

## 2. Crea il file .env (solo le cose essenziali)

Nella cartella del bot crea/modifica `.env` con **solo** questo (niente API key ancora).

**Se ti sei registrato per EMAIL (niente MetaMask):**

```env
# Chiave privata esportata da Polymarket (Settings → Export key)
PRIVATE_KEY=la_tua_private_key_esportata

# Indirizzo che vedi su Polymarket (in alto o in Settings)
POLY_SAFE_ADDRESS=0xIndirizzoMostratoSuPolymarket

# 1 = account email / Magic Link (registrazione per mail)
SIGNATURE_TYPE=1

# Lascia VUOTE: le generiamo con lo script
POLYMARKET_API_KEY=
POLYMARKET_API_SECRET=
POLYMARKET_API_PASSPHRASE=

# Proxy (se ti serve per restrizioni geografiche)
PROXY_URL=http://user:password@gw.dataimpulse.com:823
```

**Se usi MetaMask:**

```env
PRIVATE_KEY=la_tua_private_key_senza_0x
POLY_SAFE_ADDRESS=0xIndirizzoMostratoSuPolymarket
SIGNATURE_TYPE=2
POLYMARKET_API_KEY=
POLYMARKET_API_SECRET=
POLYMARKET_API_PASSPHRASE=
PROXY_URL=...
```

- **PRIVATE_KEY**: con o senza `0x`, il bot accetta entrambi.
- **POLY_SAFE_ADDRESS**: copia **esattamente** l’indirizzo che vedi su polymarket.com.
- **SIGNATURE_TYPE**: **1** = email/Magic, **2** = MetaMask (proxy Gnosis Safe).
- **POLYMARKET_***: lasciati **vuoti**; le generiamo al passo 3.

---

## 3. Genera le credenziali CLOB (non usare Builder)

**Non** creare chiavi da Settings → Builder Codes. Quelle non servono al bot.

Esegui:

```bash
python3 test_connection.py
```

Lo script:
- userà la tua **PRIVATE_KEY** (L1)
- chiamerà il CLOB per **creare/derivare** le credenziali L2 (quelle giuste per trading/saldo)
- ti stamperà qualcosa tipo:

```
POLYMARKET_API_KEY=xxxx-xxxx-...
POLYMARKET_API_SECRET=...
POLYMARKET_API_PASSPHRASE=...
```

e, se tutto ok, il **saldo USDC**.

Copia quelle tre righe **nel .env** (sostituendo le righe vuote di POLYMARKET_*). Salva il file.

---

## 4. Verifica

Esegui di nuovo:

```bash
python3 test_connection.py
```

Dovresti vedere il **saldo** senza 401. A quel punto puoi usare lo stesso .env per:

```bash
python3 bot_async.py
```

---

## Riepilogo “profilo nuovo da zero”

| Cosa | Dove / come |
|------|--------------|
| Private key | Polymarket → Settings → Export key (email), oppure MetaMask → Esporta chiave |
| Indirizzo funder | Quello che vedi su Polymarket (in alto o Settings) → `POLY_SAFE_ADDRESS` |
| SIGNATURE_TYPE | **1** = registrazione per email (Magic). **2** = MetaMask (proxy) |
| API key / secret / passphrase | **Non** da Builder. Solo da `python3 test_connection.py` con POLYMARKET_* vuote, poi copi nel .env |

Se fai così con un profilo nuovo, le chiavi sono quelle giuste per il CLOB e il bot si connette.
