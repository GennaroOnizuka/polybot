# Bot Async - Versione Stabile con WebSocket

## ⚠️ IMPORTANTE

**Usa `bot_async.py` invece di `bot.py` per connessioni WebSocket stabili!**

Il problema con `websocket-client` è stato risolto passando a `websockets` (asyncio).

## Installazione

```bash
pip install -r requirements.txt
```

Assicurati che `websockets>=12.0` sia installato (già incluso in requirements.txt).

## Esecuzione

```bash
python3 bot_async.py
```

## Differenze dalla versione sincrona

- ✅ Usa `websockets` (asyncio) invece di `websocket-client` (sincrono)
- ✅ Connessioni WebSocket più stabili e compatibili con il server Polymarket
- ✅ Gestione automatica del ping/pong
- ✅ Riconnessione automatica in caso di disconnessione
- ✅ Migliore gestione degli errori

## Configurazione

La configurazione è identica alla versione sincrona. Usa il file `.env`:

```bash
MONITOR_EVENT_SLUG=btc-updown-5m-1770909300
```

## Perché questa versione?

Il server WebSocket di Polymarket richiede un handshake HTTP/1.1 corretto e header specifici. La libreria `websocket-client` (sincrona) non è sempre compatibile al 100%, mentre `websockets` (asyncio) gestisce correttamente:

- Handshake HTTP/1.1
- Header Origin e User-Agent
- Ping/Pong automatico
- Gestione delle riconnessioni

## Troubleshooting

Se vedi ancora disconnessioni:

1. Verifica che `websockets>=12.0` sia installato
2. Controlla la connessione internet
3. Verifica che il firewall non blocchi le connessioni WebSocket
4. Controlla i log per vedere il codice di chiusura (1006 = chiusura anomala)

## Note

- Il bot è completamente asincrono
- Tutte le operazioni WebSocket sono non-bloccanti
- Il bot può gestire migliaia di token simultaneamente
- La riconnessione è automatica e trasparente
