# Riferimento setup POLYBOT vs guida esterna

## Nomi variabili .env

La guida usa nomi diversi. **Nel nostro progetto** servono questi:

| Guida (esempio) | POLYBOT (.env) |
|-----------------|----------------|
| `API_KEY` | `POLYMARKET_API_KEY` |
| `API_SECRET` | `POLYMARKET_API_SECRET` |
| `API_PASSPHRASE` | `POLYMARKET_API_PASSPHRASE` |
| `FUNDER_ADDRESS` | `POLY_SAFE_ADDRESS` |
| `PRIVATE_KEY` | `PRIVATE_KEY` (uguale) |
| `SIGNATURE_TYPE` | `SIGNATURE_TYPE` (uguale) |
| `ALL_PROXY` | `PROXY_URL` (noi usiamo PROXY_URL per DataImpulse) |

## Configurazione corretta per il tuo wallet

- **MetaMask (firma)**: `PRIVATE_KEY=310f93...2030` (senza 0x) → indirizzo 0x6166...575a
- **Polymarket (proxy/funder)**: indirizzo 0xbb69...2b38 → `POLY_SAFE_ADDRESS=0xbb695d7164aae7ba0e0fd30a7983129e1f5d2b38`
- **Signature type**: proxy wallet = **2** (GNOSIS_SAFE), non 1.
- **API key/secret/passphrase**: vanno in `POLYMARKET_API_KEY`, `POLYMARKET_API_SECRET`, `POLYMARKET_API_PASSPHRASE`.

Se usi le chiavi della guida nel nostro .env, devono essere sotto i nomi POLYMARKET_* e POLY_SAFE_ADDRESS.

## Differenza importante nella libreria

Nella guida c’è `client.get_balance()`: **in py_clob_client quel metodo non esiste**.

- **Libreria reale**: c’è solo `get_balance_allowance(params)` con `BalanceAllowanceParams(asset_type=COLLATERAL, signature_type=-1)`.
- **POLYBOT**: in `executor.py` e `test_connection.py` usiamo già `get_balance_allowance`, non `get_balance`.

Quindi lo script della guida va in errore al passo “Verifica saldo”; il nostro `test_connection.py` è allineato alla libreria.

## Se ricevi 401 (Unauthorized/Invalid api key)

Le credenziali che hai (019c5384-..., secret, passphrase) potrebbero essere:

1. **Builder key** (da Settings → Builder Codes), non per il CLOB trading → il CLOB restituisce 401.
2. Associate a un altro account/indirizzo.

**Cosa fare:**

1. Nel `.env` **lascia vuote** le tre righe:  
   `POLYMARKET_API_KEY=`  
   `POLYMARKET_API_SECRET=`  
   `POLYMARKET_API_PASSPHRASE=`
2. Esegui: `python3 test_connection.py`
3. Il client userà la **PRIVATE_KEY** (L1) per **creare/derivare** credenziali L2 dal CLOB.
4. Copia le tre righe stampate (API_KEY, SECRET, PASSPHRASE) nel `.env` sotto i nomi POLYMARKET_*.
5. Riesegui `test_connection.py`: dovresti vedere il saldo.

## Checklist .env per POLYBOT

- [ ] `PRIVATE_KEY=` (MetaMask, 64 caratteri hex, senza 0x)
- [ ] `POLY_SAFE_ADDRESS=0xbb695d7164aae7ba0e0fd30a7983129e1f5d2b38` (indirizzo Polymarket)
- [ ] `SIGNATURE_TYPE=2`
- [ ] `POLYMARKET_API_KEY=`, `POLYMARKET_API_SECRET=`, `POLYMARKET_API_PASSPHRASE=` (pieni se le hai valide per il CLOB, altrimenti vuoti per farle derivare)
- [ ] `PROXY_URL=http://...` (DataImpulse o altro)

## Script da usare qui

- **Test connessione + saldo**: `python3 test_connection.py` (usa proxy, CLOB, get_balance_allowance, e in caso di credenziali vuote le deriva).
- **Bot trading**: `python3 bot_async.py`

Non usare gli script della guida così come sono: usano nomi variabili e `get_balance()` non presenti/compatibili con questo progetto.
