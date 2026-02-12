"""
Polymarket Trading Bot (Async Version)
Main orchestration file that coordinates data collection, strategy, and execution
Uses websockets (asyncio) for stable WebSocket connections
"""

import os
import json
import asyncio
import signal
import sys
import logging
from urllib.parse import quote_plus, urlparse
from typing import Dict, List, Optional

from dotenv import load_dotenv
load_dotenv()

# Logging: utile per verificare che le richieste passino dal proxy
_log = logging.getLogger("polybot")
if os.getenv("POLYBOT_DEBUG_PROXY"):
    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger("httpx").setLevel(logging.DEBUG)


def _get_proxy_url() -> str:
    """Legge URL proxy HTTP da .env (DataImpulse, come su Replit). PROXY_URL o PROXY_HOST/PORT/USER/PASS."""
    proxy_url = os.getenv("PROXY_URL", "").strip()
    if not proxy_url:
        host = os.getenv("PROXY_HOST", "").strip()
        port = os.getenv("PROXY_PORT", "").strip()
        if host and port:
            user = os.getenv("PROXY_USER", "").strip()
            password = os.getenv("PROXY_PASSWORD", "").strip()
            if user and password:
                proxy_url = f"http://{quote_plus(user)}:{quote_plus(password)}@{host}:{port}"
            else:
                proxy_url = f"http://{host}:{port}"
    return proxy_url


def _setup_proxy() -> None:
    """Proxy HTTP DataImpulse (come Replit): env + patch httpx per CLOB."""
    proxy_url = _get_proxy_url()
    if not proxy_url:
        return
    os.environ["HTTP_PROXY"] = proxy_url
    os.environ["HTTPS_PROXY"] = proxy_url
    import httpx
    import py_clob_client.http_helpers.helpers as _clob_helpers
    _clob_helpers._http_client = httpx.Client(http2=True, proxy=proxy_url, timeout=30.0)
    parsed = urlparse(proxy_url)
    print(f"Proxy DataImpulse (HTTP): tutto il traffico passa da {parsed.hostname}:{parsed.port or 823}")


def _verify_exit_ip() -> None:
    """Verifica l'IP di uscita (deve essere quello del proxy se configurato). Usa requests per inviare auth proxy."""
    proxy_url = _get_proxy_url()
    if not proxy_url:
        return
    try:
        import requests
        r = requests.get(
            "https://api.ipify.org?format=json",
            proxies={"http": proxy_url, "https": proxy_url},
            timeout=10,
            headers={"User-Agent": "Polybot"},
        )
        r.raise_for_status()
        print(f"  Exit IP (proxy): {r.text.strip()}")
        _log.info("Exit IP check: %s", r.text)
    except Exception as e:
        _log.warning("Exit IP check failed: %s", e)
        print(f"  Exit IP check failed: {e}")


def check_proxy_location() -> bool:
    """
    Verifica paese dell'IP di uscita (proxy). Ritorna True se CH (Svizzera) o se non c'è proxy.
    Se non è CH e PROXY_ALLOW_NON_CH non è impostato, stampa warning e ritorna False.
    """
    proxy_url = _get_proxy_url()
    if not proxy_url:
        return True
    try:
        import requests
        proxies = {"http": proxy_url, "https": proxy_url}
        r = requests.get(
            "http://ip-api.com/json/?fields=query,country,countryCode,city,isp",
            proxies=proxies,
            timeout=10,
            headers={"User-Agent": "Polybot"},
        )
        r.raise_for_status()
        data = r.json()
        ip = data.get("query", "?")
        country = data.get("country", "?")
        code = data.get("countryCode", "?")
        city = data.get("city", "?")
        isp = data.get("isp", "?")
        print(f"  Proxy location: IP={ip} | {country} ({code}) | {city} | {isp}")
        if code != "CH":
            print(f"  WARNING: Proxy non è in Svizzera (CH). Polymarket potrebbe bloccare con 403.")
            if not os.getenv("PROXY_ALLOW_NON_CH"):
                print("  Imposta PROXY_ALLOW_NON_CH=1 in .env per avviare comunque.")
                return False
            return True
        print("  Svizzera (CH) confermata.")
        return True
    except Exception as e:
        _log.warning("Proxy location check failed: %s", e)
        print(f"  Location check failed: {e} (avvio comunque)")
        return True


def get_proxy_ip_and_country() -> tuple:
    """Ritorna (ip, country_code) dell'uscita proxy, o (None, None) se errore."""
    proxy_url = _get_proxy_url()
    if not proxy_url:
        return (None, None)
    try:
        import requests
        r = requests.get(
            "http://ip-api.com/json/?fields=query,countryCode",
            proxies={"http": proxy_url, "https": proxy_url},
            timeout=8,
            headers={"User-Agent": "Polybot"},
        )
        r.raise_for_status()
        data = r.json()
        return (data.get("query"), data.get("countryCode"))
    except Exception:
        return (None, None)


def test_dataimpulse_proxy() -> bool:
    """Test proxy HTTP: Polymarket CLOB raggiungibile. Eseguito dopo _setup_proxy."""
    proxy_url = _get_proxy_url()
    if not proxy_url:
        return True
    parsed = urlparse(proxy_url)
    if not parsed.hostname:
        print("  Proxy URL incompleto: serve host e porta (es. gw.dataimpulse.com:823)")
        return False
    print("  Testing proxy DataImpulse (HTTP)...")
    try:
        import requests
        proxies = {"http": proxy_url, "https": proxy_url}
        r = requests.get(
            "https://clob.polymarket.com/",
            proxies=proxies,
            timeout=15,
            headers={"User-Agent": "Polybot-ProxyTest"},
        )
        print(f"  Polymarket CLOB: HTTP {r.status_code}")
        try:
            r2 = requests.get("https://api.ipify.org?format=json", proxies=proxies, timeout=10, headers={"User-Agent": "Polybot"})
            print(f"  Exit IP: {r2.text.strip()}")
        except Exception:
            pass
        print("  Proxy OK — avvio bot.")
        return True
    except Exception as e:
        print(f"  Proxy test fallito: {e}")
        _log.error("Proxy test failed: %s", e)
        return False


_setup_proxy()
if proxy_url := _get_proxy_url():
    _verify_exit_ip()
if _get_proxy_url() and not os.getenv("SKIP_PROXY_TEST"):
    if not test_dataimpulse_proxy():
        print("Proxy configurato ma test fallito. Verifica PROXY_URL in .env (porta 823).")
        sys.exit(1)
if _get_proxy_url() and not check_proxy_location():
    print("Proxy non in Svizzera (CH). Avvio interrotto. Usa sticky session o PROXY_ALLOW_NON_CH=1.")
    sys.exit(1)

from data_collector_async import GammaAPIClient, CLOBWebSocketClient
from strategy import SumToOneArbitrageStrategy, ArbitrageOpportunity
from executor import OrderExecutor


def _best_bid_ask(book) -> tuple:
    """Estrae best bid e best ask dall'orderbook (dict o oggetto). Per diagnosi: se non cambiano → mercato statico."""
    if not book:
        return (None, None)
    try:
        if isinstance(book, dict):
            bids = book.get("bids", [])
            asks = book.get("asks", [])
        else:
            bids = getattr(book, "bids", []) or []
            asks = getattr(book, "asks", []) or []
        if not bids and not asks:
            return (None, None)
        best_bid = None
        best_ask = None
        if bids:
            b = bids[0]
            if isinstance(b, (list, tuple)):
                best_bid = f"{float(b[0]):.2f}"
            elif isinstance(b, dict):
                best_bid = f"{float(b.get('price', b.get('price', 0))):.2f}"
            else:
                best_bid = f"{float(b):.2f}"
        if asks:
            a = asks[0]
            if isinstance(a, (list, tuple)):
                best_ask = f"{float(a[0]):.2f}"
            elif isinstance(a, dict):
                best_ask = f"{float(a.get('price', a.get('price', 1))):.2f}"
            else:
                best_ask = f"{float(a):.2f}"
        return (best_bid, best_ask)
    except Exception:
        return (None, None)


def _best_ask_float(book) -> Optional[float]:
    """Estrae il prezzo (float) della migliore ask dall'orderbook (dict o oggetto CLOB)."""
    if book is None:
        return None
    asks = None
    if isinstance(book, dict):
        asks = book.get("asks") or book.get("asks_array")
    elif hasattr(book, "asks"):
        asks = getattr(book, "asks", None)
    if not asks or not isinstance(asks, (list, tuple)):
        return None
    first = asks[0] if asks else None
    if first is None:
        return None
    try:
        if isinstance(first, (list, tuple)):
            return float(first[0])
        if isinstance(first, dict):
            return float(first.get("price", first.get("price_float", 0)))
        return float(first)
    except (TypeError, ValueError, IndexError):
        return None


class PolymarketBot:
    """Main bot class that orchestrates all components (Async version)"""
    
    def __init__(self):
        """Initialize bot with configuration from environment variables"""
        # API credentials
        self.api_key = os.getenv("POLYMARKET_API_KEY")
        self.api_secret = os.getenv("POLYMARKET_API_SECRET")
        self.api_passphrase = os.getenv("POLYMARKET_API_PASSPHRASE")
        self.private_key = os.getenv("PRIVATE_KEY")
        self.builder_key = os.getenv("BUILDER_KEY", "")
        
        # Configuration
        self.signature_type = int(os.getenv("SIGNATURE_TYPE", "1"))
        self.max_position_size = float(os.getenv("MAX_POSITION_SIZE", "0.05"))
        self.min_profit_margin = float(os.getenv("MIN_PROFIT_MARGIN", "0.02"))
        
        # Validate required credentials (solo private_key obbligatorio; API key derivate dalla chiave se assenti)
        if not self.private_key:
            raise ValueError("PRIVATE_KEY is required in .env file")
        # Verifica: l'indirizzo derivato da PRIVATE_KEY deve essere il wallet a cui è legata l'API key (altrimenti 401)
        try:
            from eth_account import Account
            pk = (self.private_key or "").strip()
            if pk and not pk.startswith("0x"):
                pk = "0x" + pk
            if pk:
                addr = Account.from_key(pk).address
                print(f"Wallet (da PRIVATE_KEY): {addr}")
        except Exception:
            pass

        # Initialize components
        self.gamma_client = GammaAPIClient()
        self.ws_client = None
        self.strategy = SumToOneArbitrageStrategy(min_profit_margin=self.min_profit_margin)
        self.executor = OrderExecutor(
            api_key=self.api_key,
            api_secret=self.api_secret,
            api_passphrase=self.api_passphrase,
            private_key=self.private_key,
            signature_type=self.signature_type
        )
        
        # State tracking
        self.running = False
        self.monitored_markets = {}
        self.orderbook_cache = {}
        self.token_to_market_map = {}  # Map token_id -> (yes_token_id, no_token_id, market_id)
        self._proxy_request_count = 0
        self._last_proxy_ip = None
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print("\nShutdown signal received. Stopping bot...")
        self.running = False
        # Note: We'll handle cleanup in the async context
    
    def discover_markets(self, limit: int = 50, event_slug: Optional[str] = None) -> List[Dict]:
        """
        Discover markets using Gamma API
        
        Args:
            limit: Maximum number of markets to fetch (if not using event_slug)
            event_slug: Optional slug of a specific event to monitor
            
        Returns:
            List of market dictionaries with clobTokenIds
        """
        if event_slug:
            event_slug = (event_slug or "").strip()
            # Lavorare solo con Bitcoin Up or Down 5m: https://polymarket.com/event/btc-updown-5m
            # Usiamo sempre l'evento ATTIVO (finestra 5m corrente).
            use_only_btc_5m = event_slug.lower() == "btc-updown-5m"
            event = None
            if use_only_btc_5m:
                print(f"🎯 Working only with Bitcoin Up or Down 5m (current active event)")
                # Cerca i market direttamente da /markets (più affidabile di /events per BTC 5m)
                markets = self.gamma_client.get_active_btc_updown_markets()
                if markets:
                    print(f"✅ Found {len(markets)} markets for current 5m window — {markets[0].get('question', '')[:55]}")
                    return markets
                # Fallback: evento da get_active_btc_updown_event
                event = self.gamma_client.get_active_btc_updown_event()
                if event:
                    print(f"✅ Active 5m event: {event.get('slug')} — {event.get('title', '')[:55]}")
                else:
                    print(f"❌ No active Bitcoin Up or Down 5m event found. Try again in a few seconds.")
                    return []
            else:
                # Slug con timestamp (es. btc-updown-5m-1770909300): se chiuso, usa evento attivo
                is_btc_5m_ts = "btc-updown" in event_slug and "5m" in event_slug
                if is_btc_5m_ts:
                    requested = self.gamma_client.get_event_by_slug(event_slug)
                    if requested and (requested.get("closed", False) or not requested.get("active", True)):
                        try:
                            ts = int(event_slug.split("-")[-1])
                            import datetime as dt
                            when = dt.datetime.utcfromtimestamp(ts)
                            print(f"⚠️  Event {event_slug} is CLOSED (Past/Ended).")
                            print(f"    Timestamp {ts} = {when.isoformat()} UTC. Using current active 5m event.")
                        except Exception:
                            print(f"⚠️  Event {event_slug} is closed. Using current active 5m event.")
                    event = self.gamma_client.get_active_btc_updown_event()
                    if event:
                        print(f"✅ Using active 5m event: {event.get('slug')} — {event.get('title', '')[:55]}")
                if not event:
                    event = self.gamma_client.get_event_by_slug(event_slug)
            if not event:
                print(f"❌ Event not found: {event_slug}")
                return []

            event_id = event.get("id")
            if not event_id:
                print(f"❌ Event ID not found in response")
                return []

            markets = self.gamma_client.get_markets_for_event(event_id)
            print(f"Found {len(markets)} markets for event '{event.get('title', event_slug)}'")
            return markets
        else:
            print(f"Discovering active markets (limit: {limit})...")
            markets = self.gamma_client.get_active_markets(limit=limit)
            print(f"Found {len(markets)} active markets")
            return markets
    
    def setup_market_monitoring(self, markets: List[Dict], quiet: bool = False) -> List[str]:
        """
        Setup market monitoring and extract token IDs
        
        Args:
            markets: List of market dictionaries from Gamma API
            quiet: Se True, non stampa debug né riepilogo (usato per refresh periodico)
            
        Returns:
            List of token IDs to subscribe to
        """
        # Extract token IDs from markets
        token_ids = set()
        markets_processed = 0
        
        if markets and not quiet:
            print(f"\nDebug: Sample market structure:")
            sample_market = markets[0]
            print(f"  Keys: {list(sample_market.keys())[:15]}...")
            if "clobTokenIds" in sample_market:
                print(f"  clobTokenIds: {sample_market['clobTokenIds']}")
        
        for market in markets:
            try:
                markets_processed += 1
                market_id = market.get("id") or market.get("slug") or "unknown"
                
                # Extract clobTokenIds from market
                clob_token_ids = market.get("clobTokenIds")
                
                if clob_token_ids:
                    # Handle different formats
                    token_list = []
                    if isinstance(clob_token_ids, str):
                        # Try to parse as JSON array first
                        try:
                            parsed = json.loads(clob_token_ids)
                            if isinstance(parsed, list):
                                token_list = parsed
                            else:
                                # If not a list, try comma-separated
                                token_list = [t.strip() for t in clob_token_ids.split(",") if t.strip()]
                        except (json.JSONDecodeError, ValueError):
                            # If not JSON, try comma-separated
                            token_list = [t.strip() for t in clob_token_ids.split(",") if t.strip()]
                    elif isinstance(clob_token_ids, list):
                        token_list = clob_token_ids
                    
                    if markets_processed == 1 and not quiet:
                        print(f"  Extracted {len(token_list)} tokens from first market: {token_list[:2]}...")
                    
                    # Process tokens and map YES/NO pairs
                    yes_token = None
                    no_token = None
                    outcomes = market.get("outcomes", [])
                    
                    # Process all tokens from the list
                    for i, token_id in enumerate(token_list):
                        if token_id:
                            token_id_str = str(token_id)
                            token_ids.add(token_id_str)  # Add to set (will deduplicate)
                            
                            # Try to determine if YES or NO from outcomes
                            # Outcomes can be a list of strings or list of dicts
                            outcome_type = "unknown"
                            if outcomes and i < len(outcomes):
                                outcome = outcomes[i]
                                # Handle both string and dict formats
                                if isinstance(outcome, str):
                                    outcome_type = outcome.upper()
                                elif isinstance(outcome, dict):
                                    outcome_type = outcome.get("outcome", "").upper()
                                
                                if outcome_type in ["YES", "UP"]:
                                    yes_token = token_id_str
                                elif outcome_type in ["NO", "DOWN"]:
                                    no_token = token_id_str
                            
                            # Store market info
                            self.monitored_markets[token_id_str] = {
                                "market_id": market_id,
                                "outcome": outcome_type,
                                "market_data": market
                            }
                    
                    # Map YES/NO pairs for arbitrage detection
                    # For binary markets, we need both tokens
                    if yes_token and no_token:
                        self.token_to_market_map[yes_token] = (yes_token, no_token, market_id)
                        self.token_to_market_map[no_token] = (yes_token, no_token, market_id)
                    elif len(token_list) >= 2:
                        # If we have 2+ tokens but couldn't identify YES/NO, assume first is YES, second is NO
                        token_0_str = str(token_list[0])
                        token_1_str = str(token_list[1])
                        self.token_to_market_map[token_0_str] = (token_0_str, token_1_str, market_id)
                        self.token_to_market_map[token_1_str] = (token_0_str, token_1_str, market_id)
                
            except Exception as e:
                print(f"Error processing market {markets_processed}: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        if not quiet:
            print(f"Processed {markets_processed} markets, found {len(token_ids)} token IDs")
        return list(token_ids)

    def _fetch_markets_for_event_quiet(self, event_slug: str) -> List[Dict]:
        """Ritorna i mercati per l'evento (stessa logica di discover_markets) senza stampare messaggi di successo."""
        event_slug = (event_slug or "").strip()
        use_only_btc_5m = event_slug.lower() == "btc-updown-5m"
        event = None
        if use_only_btc_5m:
            markets = self.gamma_client.get_active_btc_updown_markets()
            if markets:
                return markets
            event = self.gamma_client.get_active_btc_updown_event()
            if not event:
                return []
        else:
            is_btc_5m_ts = "btc-updown" in event_slug and "5m" in event_slug
            if is_btc_5m_ts:
                requested = self.gamma_client.get_event_by_slug(event_slug)
                if requested and (requested.get("closed", False) or not requested.get("active", True)):
                    event = self.gamma_client.get_active_btc_updown_event()
                else:
                    event = requested
            if not event:
                event = self.gamma_client.get_active_btc_updown_event()
            if not event:
                event = self.gamma_client.get_event_by_slug(event_slug)
        if not event:
            return []
        event_id = event.get("id")
        if not event_id:
            return []
        return self.gamma_client.get_markets_for_event(event_id) or []

    def _refresh_event_markets(self) -> bool:
        """Refetch mercati per l'evento (es. nuova finestra 5m) e aggiorna monitored_markets / token_to_market_map."""
        event_slug = os.getenv("MONITOR_EVENT_SLUG", "btc-updown-5m")
        markets = self._fetch_markets_for_event_quiet(event_slug)
        if not markets:
            return False
        self.monitored_markets.clear()
        self.token_to_market_map.clear()
        token_ids = self.setup_market_monitoring(markets, quiet=True)
        if token_ids:
            print(f"🔄 Mercati 5m aggiornati (nuova finestra), {len(token_ids)} token.")
        return len(token_ids) > 0

    def _tick_proxy_check(self) -> None:
        """Ogni 50 richieste CLOB verifica che l'IP proxy non sia cambiato (sticky session)."""
        if not _get_proxy_url():
            return
        self._proxy_request_count += 1
        if self._proxy_request_count % 50 != 0:
            return
        ip, country = get_proxy_ip_and_country()
        if ip is None:
            return
        if self._last_proxy_ip is not None and self._last_proxy_ip != ip:
            _log.warning("Proxy IP changed: %s -> %s (country %s)", self._last_proxy_ip, ip, country)
            print(f"  ⚠️  Proxy IP cambiato: {self._last_proxy_ip} → {ip} (paese {country})")
        if country and country != "CH":
            _log.warning("Proxy country is %s, not CH", country)
            print(f"  ⚠️  Proxy non in Svizzera (attuale: {country}) — rischio 403.")
        self._last_proxy_ip = ip

    async def _run_single_bet(self) -> bool:
        """Deprecato: usa _run_quote_and_trigger_loop per monitor + trigger 90%/10%."""
        return await self._run_quote_and_trigger_loop()

    async def _run_quote_and_trigger_loop(self) -> bool:
        """
        Monitora quote UP/DOWN ogni secondo. Quando una quota arriva >= 90% e l'altra è ~10%,
        e le quote sono allineate (somma ~1.0), compra il lato a ~10% con bet minima (~1$).
        """
        # Soglie da .env (default: compra il lato a ~10% quando l'altro è >= 90%)
        trigger_high = float(os.getenv("TRIGGER_HIGH_PCT", "90")) / 100.0   # es. 0.90
        trigger_low = float(os.getenv("TRIGGER_LOW_PCT", "12")) / 100.0      # es. 0.12
        alignment_tol = float(os.getenv("ALIGNMENT_TOL", "0.05"))            # somma in [1-tol, 1+tol]
        min_bet_usd = float(os.getenv("MIN_BET_USD", "1.0"))
        min_size_quote = float(os.getenv("MIN_ORDER_SIZE_QUOTE", "5"))       # CLOB richiede size >= 5

        import time
        loop = asyncio.get_event_loop()
        cooldown_sec = int(os.getenv("COOLDOWN_SECONDS", "120"))
        refresh_sec = int(os.getenv("REFRESH_MARKETS_SECONDS", "90"))  # refetch mercati 5m ogni N secondi (nuova finestra)
        last_order_ts = None
        last_refresh_ts = time.time()

        yes_token_id, no_token_id, market_label = self._get_current_window_tokens()
        if not yes_token_id or not no_token_id:
            if self._refresh_event_markets():
                yes_token_id, no_token_id, market_label = self._get_current_window_tokens()
            if not yes_token_id or not no_token_id:
                print("⚠️  Nessun market 5m trovato per il trigger.")
                return False

        print(f"\n📈 Quote ogni secondo. Trigger: quando un lato >= {trigger_high:.0%} (e l'altro ~10%), compro il FAVORITO (quello a 90%). Somma quote in [1±{alignment_tol}]. Bet min ~{min_bet_usd}$. Cooldown {cooldown_sec}s. Refresh mercati ogni {refresh_sec}s (nuova finestra 5m).")
        print("=" * 60)

        while self.running:
            try:
                self._tick_proxy_check()
                # Refresh periodico: quando finiscono i 5 minuti Gamma espone la nuova finestra; aggiorniamo token
                if time.time() - last_refresh_ts >= refresh_sec:
                    self._refresh_event_markets()
                    last_refresh_ts = time.time()
                    yes_token_id, no_token_id, market_label = self._get_current_window_tokens()
                if not yes_token_id or not no_token_id:
                    if self._refresh_event_markets():
                        yes_token_id, no_token_id, market_label = self._get_current_window_tokens()
                    if not yes_token_id or not no_token_id:
                        print("   [Nessun market 5m attivo] Riprovo tra 5s...")
                        await asyncio.sleep(5)
                        continue
                yes_price, no_price = await self._get_up_down_prices(loop, yes_token_id, no_token_id)
                if yes_price is None and no_price is None:
                    await asyncio.sleep(1)
                    continue

                import datetime as dt
                ts = dt.datetime.now().strftime("%H:%M:%S")
                up_s = f"{yes_price:.2f}" if yes_price is not None else "N/A"
                down_s = f"{no_price:.2f}" if no_price is not None else "N/A"
                print(f"[{ts}]  UP {up_s}  DOWN {down_s}")

                # Allineamento: quote devono sommare ~1 (non 0.90+0.90)
                y, n = yes_price or 0, no_price or 0
                if y <= 0 or n <= 0:
                    await asyncio.sleep(1)
                    continue
                total = y + n
                if abs(total - 1.0) > alignment_tol:
                    await asyncio.sleep(1)
                    continue

                # Trigger: un lato >= 90% e l'altro ~10%, quote allineate → compra il FAVORITO (quello a 90%)
                skip_buy = os.getenv("SKIP_BUY", "1").strip().lower() in ("1", "true", "yes")
                if not skip_buy:
                    if y >= trigger_high and n <= trigger_low:
                        token_id = yes_token_id
                        price = y
                        side_label = "UP"
                    elif n >= trigger_high and y <= trigger_low:
                        token_id = no_token_id
                        price = n
                        side_label = "DOWN"
                    else:
                        await asyncio.sleep(1)
                        continue

                    # Per almeno cooldown_sec secondi dopo l'ultimo ordine: SOLO quote, nessun ordine
                    now_ts = time.time()
                    if last_order_ts is not None:
                        elapsed = now_ts - last_order_ts
                        if elapsed <= cooldown_sec:
                            remaining = int(cooldown_sec - elapsed) + 1
                            print(f"   [Cooldown] Solo quote per altri {remaining}s, nessun ordine.")
                            await asyncio.sleep(1)
                            continue

                    size = max(round(min_bet_usd / price, 2), min_size_quote)
                    usd_approx = size * price
                    print(f"\n🎯 Trigger: compro il FAVORITO {side_label} a {price:.2%} (altro lato ~{1-price:.0%}). Quote allineate (somma={total:.2f}).")
                    print(f"   Ordine: BUY {size} quote @ {price:.4f} → ~{usd_approx:.2f}$ (min size CLOB = {min_size_quote})")
                    self._tick_proxy_check()
                    result = await loop.run_in_executor(
                        None,
                        lambda: self.executor.place_limit_order(
                            token_id=token_id,
                            side="BUY",
                            size=size,
                            price=price,
                            post_only=False,
                        ),
                    )
                    if result:
                        last_order_ts = time.time()
                        print(f"✅ Ordine piazzato. Prossimo ordine possibile tra {cooldown_sec}s.")
                    else:
                        print("❌ Ordine fallito. Continuo a monitorare.")
            except Exception as e:
                print(f"\n⚠️  Errore: {e}")
            await asyncio.sleep(1)
        return False

    def _get_current_window_tokens(self):
        """Ritorna (yes_token_id, no_token_id, market_label) per la finestra 5m corrente."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        event_slug = os.getenv("MONITOR_EVENT_SLUG", "btc-updown-5m")
        candidates = []
        for token_id, market_info in self.monitored_markets.items():
            market_data = market_info.get("market_data", {})
            if event_slug not in (market_data.get("slug") or ""):
                continue
            if token_id not in self.token_to_market_map:
                continue
            yes_t, no_t, _ = self.token_to_market_map[token_id]
            end_str = market_data.get("endDate") or market_data.get("end_date") or ""
            if not end_str:
                continue
            try:
                end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                if end_dt <= now:
                    continue
                q = market_data.get("question", "")
                candidates.append((end_dt, yes_t, no_t, q))
            except Exception:
                continue
        if not candidates:
            for tid in self.token_to_market_map:
                yes_t, no_t, _ = self.token_to_market_map[tid]
                return (yes_t, no_t, "")
        candidates.sort(key=lambda x: x[0])
        _, yes_t, no_t, q = candidates[0]
        return (yes_t, no_t, (q[:50] + "...") if len(q) > 50 else q)

    async def _get_up_down_prices(self, loop, yes_token_id: str, no_token_id: str):
        """Ritorna (yes_price, no_price) da orderbook poi midpoint."""
        yes_book = await loop.run_in_executor(None, self.executor.get_orderbook, yes_token_id)
        no_book = await loop.run_in_executor(None, self.executor.get_orderbook, no_token_id)
        yes_bid, yes_ask = _best_bid_ask(yes_book)
        no_bid, no_ask = _best_bid_ask(no_book)

        def _mid(bid, ask):
            if bid and ask:
                try:
                    return (float(bid) + float(ask)) / 2
                except (TypeError, ValueError):
                    pass
            if ask:
                try:
                    return float(ask)
                except (TypeError, ValueError):
                    pass
            if bid:
                try:
                    return float(bid)
                except (TypeError, ValueError):
                    pass
            return None

        yes_price = _mid(yes_bid, yes_ask)
        no_price = _mid(no_bid, no_ask)
        if yes_price is None or no_price is None:
            yes_mid = await loop.run_in_executor(None, self.executor.get_midpoint_price, yes_token_id)
            no_mid = await loop.run_in_executor(None, self.executor.get_midpoint_price, no_token_id)
            if yes_price is None:
                yes_price = yes_mid
            if no_price is None:
                no_price = no_mid
        return (yes_price, no_price)

    async def _handle_ws_message(self, message):
        """Handle incoming WebSocket messages (async)"""
        try:
            # Handle both dict and list formats
            if isinstance(message, list):
                # Process each message in the list
                for msg in message:
                    await self._process_single_message(msg)
            elif isinstance(message, dict):
                await self._process_single_message(message)
            else:
                # Try to convert object to dict
                message_dict = self._convert_to_dict(message)
                if message_dict:
                    await self._process_single_message(message_dict)
                else:
                    print(f"⚠️  Unexpected message type: {type(message)}, skipping...")
            
        except Exception as e:
            print(f"Error handling WebSocket message: {e}")
            import traceback
            traceback.print_exc()
    
    def _convert_to_dict(self, obj):
        """Convert object to dict, handling various formats"""
        if isinstance(obj, dict):
            return obj
        elif obj is None:
            return None
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        elif hasattr(obj, 'dict'):
            try:
                return obj.dict()
            except:
                pass
        elif hasattr(obj, '_asdict'):  # NamedTuple
            try:
                return obj._asdict()
            except:
                pass
        
        # Try to access common attributes directly
        result = {}
        try:
            # Common orderbook attributes
            if hasattr(obj, 'bids'):
                result['bids'] = obj.bids
            if hasattr(obj, 'asks'):
                result['asks'] = obj.asks
            if hasattr(obj, 'buys'):
                result['bids'] = obj.buys
            if hasattr(obj, 'sells'):
                result['asks'] = obj.sells
            if hasattr(obj, 'asset_id'):
                result['asset_id'] = obj.asset_id
            if hasattr(obj, 'event_type'):
                result['event_type'] = obj.event_type
            if hasattr(obj, 'market'):
                result['market'] = obj.market
            if hasattr(obj, 'timestamp'):
                result['timestamp'] = obj.timestamp
            
            # If we got some attributes, return the dict
            if result:
                return result
        except:
            pass
        
        # Last resort: try to access all attributes
        try:
            for attr in dir(obj):
                if not attr.startswith('_') and not callable(getattr(obj, attr, None)):
                    try:
                        value = getattr(obj, attr)
                        if not callable(value):
                            result[attr] = value
                    except:
                        pass
            return result if result else None
        except:
            return None
    
    async def _process_single_message(self, message):
        """Process a single WebSocket message"""
        # Convert message to dict if needed
        message_dict = self._convert_to_dict(message)
        if not message_dict:
            # If conversion failed, try to handle as orderbook object directly
            if hasattr(message, 'bids') and hasattr(message, 'asks'):
                # This is likely an OrderBookSummary object
                asset_id = getattr(message, 'asset_id', None) or getattr(message, 'token_id', None)
                if asset_id:
                    orderbook_dict = {
                        "bids": list(message.bids) if hasattr(message.bids, '__iter__') else [],
                        "asks": list(message.asks) if hasattr(message.asks, '__iter__') else [],
                        "asset_id": str(asset_id),
                        "market": getattr(message, 'market', ''),
                        "timestamp": getattr(message, 'timestamp', 0),
                        "hash": getattr(message, 'hash', '')
                    }
                    self.orderbook_cache[str(asset_id)] = orderbook_dict
                    await self._check_and_execute_arbitrage(str(asset_id))
            return
        
        event_type = message_dict.get("event_type", "")
        
        if event_type == "book" or (not event_type and ("bids" in message_dict or "asks" in message_dict)):
            # Orderbook update
            asset_id = message_dict.get("asset_id", message_dict.get("token_id", ""))
            if asset_id:
                # Extract bids and asks, handling different formats
                bids = message_dict.get("bids", message_dict.get("buys", []))
                asks = message_dict.get("asks", message_dict.get("sells", []))
                
                # Convert to dict format for consistency
                orderbook_dict = {
                    "bids": bids if isinstance(bids, list) else [],
                    "asks": asks if isinstance(asks, list) else [],
                    "asset_id": str(asset_id),
                    "market": message_dict.get("market", ""),
                    "timestamp": message_dict.get("timestamp", 0),
                    "hash": message_dict.get("hash", "")
                }
                self.orderbook_cache[str(asset_id)] = orderbook_dict
                # Check for arbitrage opportunities
                await self._check_and_execute_arbitrage(str(asset_id))
        
        elif event_type == "price_change":
            # Price change update - update orderbook cache if needed
            price_changes = message_dict.get("price_changes", [])
            for change in price_changes:
                change_dict = self._convert_to_dict(change)
                if not change_dict:
                    continue
                
                asset_id = change_dict.get("asset_id", "")
                if asset_id:
                    # Update cache with new best bid/ask
                    if asset_id in self.orderbook_cache:
                        # Ensure cache entry is a dict
                        cache_entry = self.orderbook_cache[asset_id]
                        if not isinstance(cache_entry, dict):
                            cache_entry = self._convert_to_dict(cache_entry)
                            if cache_entry:
                                self.orderbook_cache[asset_id] = cache_entry
                            else:
                                continue
                        
                        self.orderbook_cache[asset_id].update({
                            "best_bid": change_dict.get("best_bid", 0),
                            "best_ask": change_dict.get("best_ask", 1)
                        })
                    await self._check_and_execute_arbitrage(asset_id)
    
    async def _check_and_execute_arbitrage(self, token_id: str):
        """
        Check for arbitrage opportunities and execute if found (async)
        
        Args:
            token_id: Token ID that was updated
        """
        # Find the pair (YES/NO) for this market
        if token_id not in self.token_to_market_map:
            return
        
        yes_token_id, no_token_id, market_id = self.token_to_market_map[token_id]
        
        # Get orderbooks
        yes_orderbook = self.orderbook_cache.get(yes_token_id)
        no_orderbook = self.orderbook_cache.get(no_token_id)
        
        if not yes_orderbook or not no_orderbook:
            # Fetch orderbooks if not in cache (sync call, but ok for now)
            yes_orderbook = self.executor.get_orderbook(yes_token_id)
            no_orderbook = self.executor.get_orderbook(no_token_id)
            
            if yes_orderbook:
                self.orderbook_cache[yes_token_id] = yes_orderbook
            if no_orderbook:
                self.orderbook_cache[no_token_id] = no_orderbook
        
        if not yes_orderbook or not no_orderbook:
            return
        
        # Check for arbitrage opportunity
        opportunity = self.strategy.check_arbitrage_opportunity(
            market_id=market_id,
            yes_token_id=yes_token_id,
            no_token_id=no_token_id,
            yes_orderbook=yes_orderbook,
            no_orderbook=no_orderbook
        )
        
        if opportunity:
            print(f"\n🎯 Arbitrage opportunity found!")
            print(f"Market: {market_id}")
            print(f"YES price: ${opportunity.yes_price:.4f}")
            print(f"NO price: ${opportunity.no_price:.4f}")
            print(f"Total cost: ${opportunity.total_cost:.4f}")
            print(f"Profit margin: {opportunity.profit_margin*100:.2f}%")
            print(f"Action: {opportunity.action}")
            
            # Get portfolio balance
            balance = self.executor.get_balance()
            if balance <= 0:
                print("⚠️  Insufficient balance. Skipping trade.")
                return
            
            # Calculate position sizes
            yes_size, no_size = self.strategy.calculate_position_size(
                opportunity=opportunity,
                portfolio_value=balance,
                max_position_size=self.max_position_size
            )
            
            print(f"Executing trade: YES=${yes_size:.2f}, NO=${no_size:.2f}")
            
            # Execute arbitrage
            success = self.executor.execute_arbitrage(
                opportunity=opportunity,
                yes_size=yes_size,
                no_size=no_size
            )
            
            if success:
                print("✅ Orders placed successfully")
            else:
                print("❌ Failed to place orders")
    
    async def run(self):
        """Main bot loop (async)"""
        print("=" * 60)
        print("Polymarket Trading Bot Starting...")
        print("=" * 60)
        
        self.running = True
        
        try:
            # Check if specific event slug is provided via environment variable
            event_slug = os.getenv("MONITOR_EVENT_SLUG", None)
            
            if event_slug:
                print(f"🎯 Monitoring specific event: {event_slug}")
                markets = self.discover_markets(event_slug=event_slug)
            else:
                markets = self.discover_markets(limit=50)
            
            if not markets:
                print("No markets found. Exiting.")
                return
            
            # Setup monitoring and extract token IDs
            token_ids = self.setup_market_monitoring(markets)
            
            if not token_ids:
                print("⚠️  No token IDs found in markets. Exiting.")
                return

            # Modalità singola scommessa: 1$ sul lato con quota più alta, poi stop
            # Default: una bet da 1$ e stop. Con SINGLE_BET=0 si fa monitoraggio continuo.
            single_bet = os.getenv("SINGLE_BET", "1").strip().lower() in ("1", "true", "yes")
            if single_bet:
                await self._run_single_bet()
                return
            
            # Initialize WebSocket client
            self.ws_client = CLOBWebSocketClient(on_message_callback=self._handle_ws_message)
            
            # Start WebSocket in background task
            ws_task = asyncio.create_task(self.ws_client.run(auto_reconnect=True))
            
            # Wait a bit for connection
            await asyncio.sleep(2)
            
            # Subscribe to all tokens
            if self.ws_client.connected:
                print(f"✅ WebSocket connected, subscribing to {len(token_ids)} tokens...")
                # Subscribe in batches to avoid overwhelming
                BATCH_SIZE = 20
                for i in range(0, len(token_ids), BATCH_SIZE):
                    batch = token_ids[i:i + BATCH_SIZE]
                    if i == 0:
                        await self.ws_client.subscribe(batch)
                    else:
                        await self.ws_client.subscribe_more(batch)
                    await asyncio.sleep(0.5)  # Small delay between batches
                
                print(f"✅ Successfully subscribed to {len(token_ids)} tokens")
            else:
                print("⚠️  WebSocket not connected. Retrying...")
            
            print(f"\n📊 Monitoring {len(token_ids)} tokens across {len(markets)} markets")
            print("\nBot is running. Monitoring markets for opportunities...")
            print("Press Ctrl+C to stop.\n")
            
            # Start quote display task if monitoring specific event
            quote_task = None
            if event_slug:
                # Wait a bit for WebSocket to connect and receive initial data
                await asyncio.sleep(3)
                quote_task = asyncio.create_task(self._display_quotes_loop(event_slug))
            
            # Main loop - just wait while WebSocket handles messages
            while self.running:
                await asyncio.sleep(1)
                
                # Check if WebSocket is still connected
                if not self.ws_client.connected and self.running:
                    print("⚠️  WebSocket disconnected, waiting for reconnect...")
                    await asyncio.sleep(5)
            
            # Cancel quote task if running
            if quote_task:
                quote_task.cancel()
                try:
                    await quote_task
                except asyncio.CancelledError:
                    pass
        
        except KeyboardInterrupt:
            print("\nKeyboard interrupt received")
        except Exception as e:
            print(f"Error in main loop: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await self.stop()
    
    async def _display_quotes_loop(self, event_slug: str):
        """Display quotes every second. Usa il market con endDate PIÙ VICINO nel futuro (finestra 5m corrente)."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        candidates = []  # (end_dt, yes_token, no_token, question, liquidity, volume)

        for token_id, market_info in self.monitored_markets.items():
            market_data = market_info.get("market_data", {})
            market_slug = market_data.get("slug", "")
            if event_slug not in market_slug and market_slug != event_slug:
                continue
            if token_id not in self.token_to_market_map:
                continue
            yes_token, no_token, _ = self.token_to_market_map[token_id]
            end_date_str = market_data.get("endDate") or market_data.get("end_date") or ""
            if not end_date_str:
                continue
            try:
                end_dt = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
                if end_dt <= now:
                    continue
                liq = market_data.get("liquidity") or market_data.get("liquidityNum") or 0
                vol = market_data.get("volume") or market_data.get("volumeNum") or 0
                try:
                    liq = float(liq) if liq else 0
                except (TypeError, ValueError):
                    liq = 0
                try:
                    vol = float(vol) if vol else 0
                except (TypeError, ValueError):
                    vol = 0
                question = market_data.get("question", "")
                candidates.append((end_dt, yes_token, no_token, question, liq, vol))
            except Exception:
                continue

        # Scegli il market con endDate più vicino nel futuro = finestra 5m CORRENTE (non tra 2 ore)
        if not candidates:
            # fallback: qualsiasi coppia
            for token_id in self.token_to_market_map.keys():
                yes_token, no_token, _ = self.token_to_market_map[token_id]
                candidates = [(now, yes_token, no_token, "", 0, 0)]
                break

        if not candidates:
            print(f"⚠️  Could not find YES/NO tokens for event {event_slug}")
            return

        candidates.sort(key=lambda x: x[0])
        end_dt, yes_token_id, no_token_id, market_label, liq, vol = candidates[0]
        market_label = (market_label[:55] + "...") if market_label and len(market_label) > 55 else (market_label or "")

        print(f"\n📈 Displaying quotes for event: {event_slug}")
        print(f"   Market (endDate più vicino): {market_label}")
        print(f"   endDate: {end_dt.isoformat()}  liquidity: {liq}  volume: {vol}")
        print("=" * 60)

        loop = asyncio.get_event_loop()
        while self.running:
            try:
                # Ordine book prima: quote reali da orderbook; midpoint come fallback (può dare 0.99/0.01 se mercato chiuso)
                yes_book = await loop.run_in_executor(None, self.executor.get_orderbook, yes_token_id)
                no_book = await loop.run_in_executor(None, self.executor.get_orderbook, no_token_id)
                yes_bid, yes_ask = _best_bid_ask(yes_book)
                no_bid, no_ask = _best_bid_ask(no_book)

                def _price_from_bid_ask(bid: Optional[str], ask: Optional[str]) -> Optional[float]:
                    if bid and ask:
                        try:
                            return (float(bid) + float(ask)) / 2
                        except (TypeError, ValueError):
                            pass
                    if ask:
                        try:
                            return float(ask)
                        except (TypeError, ValueError):
                            pass
                    if bid:
                        try:
                            return float(bid)
                        except (TypeError, ValueError):
                            pass
                    return None

                yes_price = _price_from_bid_ask(yes_bid, yes_ask)
                no_price = _price_from_bid_ask(no_bid, no_ask)
                # Se orderbook vuoto/stale, usa midpoint CLOB
                if yes_price is None or no_price is None:
                    yes_mid = await loop.run_in_executor(
                        None, self.executor.get_midpoint_price, yes_token_id
                    )
                    no_mid = await loop.run_in_executor(
                        None, self.executor.get_midpoint_price, no_token_id
                    )
                    if yes_price is None:
                        yes_price = yes_mid
                    if no_price is None:
                        no_price = no_mid

                import datetime as dt
                timestamp = dt.datetime.now().strftime("%H:%M:%S")
                up_str = f"{yes_price:.2f}" if yes_price is not None else "N/A"
                down_str = f"{no_price:.2f}" if no_price is not None else "N/A"
                up_ba = f" (bid {yes_bid or '—'}/ask {yes_ask or '—'})" if (yes_bid or yes_ask) else ""
                down_ba = f" (bid {no_bid or '—'}/ask {no_ask or '—'})" if (no_bid or no_ask) else ""
                print(f"[{timestamp}]  UP {up_str}{up_ba}  DOWN {down_str}{down_ba}")
            except Exception as e:
                print(f"\n⚠️  Error displaying quotes: {e}")
            await asyncio.sleep(1)
    
    async def stop(self):
        """Stop the bot and cleanup (async)"""
        print("\nStopping bot...")
        self.running = False
        
        if self.ws_client:
            await self.ws_client.disconnect()
        
        print("Bot stopped.")


async def main():
    """Entry point (async)"""
    try:
        bot = PolymarketBot()
        await bot.run()
    except Exception as e:
        print(f"Failed to start bot: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
