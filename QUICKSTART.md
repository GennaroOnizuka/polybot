# Quick Start Guide

## Setup Rapido (5 minuti)

### 1. Installa le Dipendenze

```bash
pip install -r requirements.txt
```

### 2. Configura le Credenziali

Apri il file `.env` e compila:

```bash
# Ottieni queste informazioni da Polymarket:
POLYMARKET_API_KEY=la_tua_api_key
POLYMARKET_API_SECRET=il_tuo_secret
POLYMARKET_API_PASSPHRASE=la_tua_passphrase

# Esporta la chiave privata dal wallet Polymarket:
PRIVATE_KEY=la_tua_chiave_privata_senza_0x

# Builder Key (già configurato)
BUILDER_KEY=019c3a33-11c8-7651-85f8-48d588ba088e
```

### 3. Test dei Componenti

Prima di eseguire il bot con soldi reali, testa i componenti:

```bash
python test_bot.py
```

Questo verificherà:
- ✅ Connessione alla Gamma API
- ✅ Inizializzazione del client CLOB
- ✅ Fetch del balance

### 4. Esegui il Bot

```bash
python bot.py
```

Il bot inizierà a:
1. Scoprire mercati attivi
2. Connettersi al WebSocket per aggiornamenti in tempo reale
3. Monitorare opportunità di arbitraggio
4. Eseguire trade automaticamente

## Come Ottenere le Credenziali

### API Credentials (Polymarket)

1. Accedi a [Polymarket](https://polymarket.com)
2. Vai su Settings → API
3. Crea una nuova API Key
4. Salva Key, Secret e Passphrase

### Private Key (Wallet)

1. Su Polymarket, vai su "Cash"
2. Menu a tre puntini → "Export Private Key"
3. **IMPORTANTE**: Copia la chiave SENZA il prefisso `0x`
4. Incollala nel file `.env`

## Modalità Paper Trading (Test)

Per testare senza rischiare soldi reali, modifica `bot.py`:

```python
# Aggiungi questa flag all'inizio della classe PolymarketBot
PAPER_TRADING = True  # Non eseguirà ordini reali
```

## Troubleshooting

### "Missing required API credentials"
→ Controlla che il file `.env` sia compilato correttamente

### "Authentication error"
→ Verifica che la chiave privata sia nel formato corretto (senza 0x)

### "WebSocket connection failed"
→ Controlla la connessione internet e il firewall

### Nessuna opportunità trovata
→ I mercati potrebbero essere efficienti. Prova a ridurre `MIN_PROFIT_MARGIN` nel `.env`

## Prossimi Passi

1. ✅ Testa con `test_bot.py`
2. ✅ Inizia con fondi limitati
3. ✅ Monitora i log per vedere le opportunità rilevate
4. ✅ Aggiusta i parametri in `.env` secondo le tue preferenze

## Supporto

Per problemi o domande, consulta il `README.md` completo.
