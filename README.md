# Polymarket Trading Bot

Un bot automatizzato per il trading su Polymarket che implementa strategie di arbitraggio, incluso il sum-to-one arbitrage.

## Caratteristiche

- **Raccolta Dati in Tempo Reale**: Connessione WebSocket per aggiornamenti istantanei dell'orderbook
- **Strategia di Arbitraggio**: Rilevamento automatico di opportunità sum-to-one (YES + NO ≠ $1.00)
- **Gestione del Rischio**: Limiti di posizione configurabili e gestione del portafoglio
- **Architettura Modulare**: Codice organizzato in layer separati per facilità di manutenzione

## Requisiti

- Python 3.9.10 o superiore
- Wallet crypto con fondi USDC su Polygon
- Credenziali API Polymarket (API Key, Secret, Passphrase)
- Chiave privata del wallet (senza prefisso 0x)

## Installazione

1. **Clona o scarica il repository**

2. **Installa le dipendenze**:
```bash
pip install -r requirements.txt
```

3. **Configura le variabili d'ambiente**:
   - Copia `.env.example` in `.env`
   - Compila le seguenti informazioni:
     - `POLYMARKET_API_KEY`: La tua API Key di Polymarket
     - `POLYMARKET_API_SECRET`: Il tuo API Secret
     - `POLYMARKET_API_PASSPHRASE`: La tua passphrase API
     - `PRIVATE_KEY`: La chiave privata del wallet (senza 0x)
     - `BUILDER_KEY`: Già configurato con la tua chiave

## Configurazione Wallet

### Ottenere le Credenziali API

1. Accedi al tuo account Polymarket
2. Vai alla sezione API/Settings
3. Genera una nuova API Key, Secret e Passphrase
4. Salva queste informazioni nel file `.env`

### Ottenere la Chiave Privata

1. Su Polymarket, vai a "Cash"
2. Clicca sul menu a tre puntini
3. Seleziona "Export Private Key"
4. **IMPORTANTE**: Salva la chiave privata nel file `.env` (senza il prefisso 0x)
5. **NON condividere mai** questa chiave o committarla su Git

### Tipo di Wallet (SIGNATURE_TYPE)

- `0`: EOA standard (MetaMask) - Richiede pagamento gas
- `1`: Account Email/Magic di Polymarket
- `2`: Gnosis Safe/Browser wallet - Consigliato per bot (gasless)

## Utilizzo

### Esecuzione Locale

```bash
python bot.py
```

Il bot:
1. Scoprirà i mercati attivi tramite Gamma API
2. Si connetterà al WebSocket per aggiornamenti in tempo reale
3. Monitorerà i mercati per opportunità di arbitraggio
4. Eseguirà automaticamente i trade quando trova opportunità profittevoli

### Test in Modalità Paper Trading

Prima di utilizzare fondi reali, è consigliabile testare il bot:

1. Modifica `bot.py` per aggiungere un flag `paper_trading = True`
2. Il bot eseguirà la logica senza inviare ordini reali
3. Monitora i log per vedere quali opportunità vengono rilevate

### Deploy su VPS

Per eseguire il bot 24/7, puoi deployarlo su un VPS:

1. **Trasferisci i file sul server**:
```bash
scp -r . user@your-vps:/path/to/bot
```

2. **Installa Python e dipendenze sul server**

3. **Usa un process manager** come PM2 o systemd:
```bash
# Con PM2
pm2 start bot.py --interpreter python3 --name polymarket-bot
pm2 save
pm2 startup
```

## Configurazione Avanzata

### Parametri di Trading

Nel file `.env` puoi configurare:

- `MAX_POSITION_SIZE`: Dimensione massima della posizione come frazione del portafoglio (default: 0.05 = 5%)
- `MIN_PROFIT_MARGIN`: Margine di profitto minimo richiesto per eseguire un trade (default: 0.02 = 2%)

### Strategie Personalizzate

Puoi estendere il bot aggiungendo nuove strategie in `strategy.py`:

```python
class YourCustomStrategy:
    def check_opportunity(self, market_data):
        # La tua logica qui
        pass
```

## Struttura del Progetto

```
POLYBOT/
├── bot.py                 # File principale del bot
├── data_collector.py      # Layer di raccolta dati (Gamma API, WebSocket)
├── strategy.py            # Layer strategia (arbitraggio)
├── executor.py            # Layer esecuzione (ordini)
├── requirements.txt       # Dipendenze Python
├── .env                   # Variabili d'ambiente (NON committare!)
├── .env.example           # Template per .env
├── .gitignore            # File da ignorare in Git
└── README.md             # Questa guida
```

## Sicurezza

⚠️ **IMPORTANTE**:

- **NON committare mai** il file `.env` su Git
- Mantieni le tue chiavi private segrete
- Usa un wallet dedicato con fondi limitati per il bot
- Testa sempre in modalità paper trading prima di usare fondi reali
- Implementa kill switches per fermare il bot in caso di problemi

## Gestione Errori

Il bot include:

- Retry logic con exponential backoff per gestire rate limits
- Gestione errori per connessioni WebSocket
- Logging per debugging
- Gestione graceful degli shutdown signals

## Limitazioni API

- **Public endpoints**: ~100 richieste/minuto
- **Trading endpoints**: ~60 ordini/minuto

Il bot gestisce automaticamente questi limiti con retry logic.

## Troubleshooting

### WebSocket non si connette
- Verifica la connessione internet
- Controlla che il firewall non blocchi le connessioni WebSocket
- Prova a riconnettere manualmente

### Errori di autenticazione
- Verifica che le credenziali API siano corrette
- Controlla che la chiave privata sia nel formato corretto (senza 0x)
- Assicurati che il `SIGNATURE_TYPE` corrisponda al tipo di wallet

### Nessuna opportunità trovata
- I mercati potrebbero essere efficienti (prezzi già corretti)
- Prova a ridurre `MIN_PROFIT_MARGIN` per trovare più opportunità
- Verifica che ci sia sufficiente liquidità nei mercati monitorati

## Prossimi Passi

- Implementa strategie avanzate (market making, arbitraggio combinatorio)
- Aggiungi analisi sentiment da news feed
- Integra alert via Discord/Telegram
- Ottimizza la latenza per trading ad alta frequenza
- Aggiungi backtesting per validare strategie

## Risorse

- [Documentazione Polymarket API](https://docs.polymarket.com/)
- [py-clob-client GitHub](https://github.com/Polymarket/py-clob-client)
- [Guida QuantVPS](https://www.quantvps.com/blog/setup-polymarket-trading-bot)

## Disclaimer

⚠️ **AVVISO LEGALE**: Questo bot è fornito "così com'è" senza garanzie. Il trading comporta rischi significativi. Usa a tuo rischio e pericolo. Non siamo responsabili per eventuali perdite finanziarie.

## Licenza

Questo progetto è fornito per scopi educativi. Usa a tuo rischio.
