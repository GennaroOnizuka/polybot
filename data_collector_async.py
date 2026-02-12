"""
Data Collection Layer for Polymarket Bot (Async Version)
Handles API connections and WebSocket feeds for real-time market data
Uses websockets (asyncio) instead of websocket-client for better compatibility
"""

import os
import requests
import json
import asyncio
import websockets
from typing import Dict, List, Optional, Callable
from tenacity import retry, stop_after_attempt, wait_exponential


class GammaAPIClient:
    """Client for Polymarket's Gamma API - used for market discovery. Usa sempre il proxy se impostato (tutto da Svizzera)."""
    
    BASE_URL = "https://gamma-api.polymarket.com"

    def __init__(self):
        self._session = requests.Session()
        proxy_url = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
        if proxy_url:
            self._session.proxies = {"http": proxy_url, "https": proxy_url}
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def get_active_markets(self, limit: int = 100) -> List[Dict]:
        """
        Fetch active markets from Gamma API
        
        Args:
            limit: Maximum number of markets to return
            
        Returns:
            List of market dictionaries with clobTokenIds
        """
        # Use /markets endpoint instead of /events to get markets directly with token IDs
        url = f"{self.BASE_URL}/markets"
        params = {
            "closed": "false",
            "limit": limit,
            "enableOrderBook": "true"  # Only markets with orderbook enabled
        }
        
        try:
            response = self._session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, list) else []
        except requests.exceptions.RequestException as e:
            print(f"Error fetching markets from Gamma API: {e}")
            return []
    
    def get_market_details(self, event_id: str) -> Optional[Dict]:
        """Get detailed information about a specific market"""
        url = f"{self.BASE_URL}/events/{event_id}"
        try:
            response = self._session.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching market details: {e}")
            return None
    
    def get_event_by_slug(self, slug: str) -> Optional[Dict]:
        """Get event details by slug (timeout 20s, 2 tentativi su timeout)."""
        url = f"{self.BASE_URL}/events/slug/{slug}"
        for attempt in range(2):
            try:
                response = self._session.get(url, timeout=20)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                print(f"Error fetching event by slug: {e}")
                if attempt < 1:
                    import time
                    time.sleep(2)
        return None
    
    def get_markets_for_event(self, event_id: str) -> List[Dict]:
        """Get all markets for a specific event"""
        url = f"{self.BASE_URL}/markets"
        params = {
            "event_id": event_id,
            "closed": "false",
            "enableOrderBook": "true"
        }
        try:
            response = self._session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, list) else []
        except requests.exceptions.RequestException as e:
            print(f"Error fetching markets for event: {e}")
            return []

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def get_active_btc_updown_event(self) -> Optional[Dict]:
        """
        Trova l'evento "Bitcoin Up or Down" 5m attualmente attivo.
        Prima prova GET /events; se non trova nulla, cerca tra GET /markets (più affidabile).
        """
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)

        # 1) Prova da /events
        url = f"{self.BASE_URL}/events"
        params = {"active": "true", "closed": "false", "limit": 250}
        try:
            response = self._session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            events = data if isinstance(data, list) else []
        except requests.exceptions.RequestException as e:
            events = []

        candidates = []
        for ev in events:
            slug = (ev.get("slug") or "").lower()
            title = (ev.get("title") or "").lower()
            if "btc-updown" not in slug and "bitcoin up or down" not in title:
                continue
            end_date_str = ev.get("endDate") or ev.get("end_date") or ""
            if not end_date_str:
                continue
            try:
                end_dt = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
                if end_dt > now:
                    candidates.append((end_dt, ev))
            except Exception:
                continue

        if candidates:
            candidates.sort(key=lambda x: x[0])
            return candidates[0][1]

        # 2) Fallback: usa get_active_btc_updown_markets (filtro question "bitcoin up or down")
        markets = self.get_active_btc_updown_markets()
        if not markets:
            return None
        first_market = markets[0]
        event_id = None
        events_arr = first_market.get("events")
        if events_arr and len(events_arr) > 0 and isinstance(events_arr[0], dict):
            event_id = events_arr[0].get("id")
        end_date_str = first_market.get("endDate") or first_market.get("end_date") or ""
        if event_id:
            return {
                "id": event_id,
                "slug": first_market.get("slug") or "btc-updown-5m",
                "title": first_market.get("question") or "Bitcoin Up or Down 5m",
                "endDate": end_date_str,
            }
        return {
            "id": first_market.get("id"),
            "slug": first_market.get("slug") or "btc-updown-5m",
            "title": first_market.get("question") or "Bitcoin Up or Down 5m",
            "endDate": end_date_str,
        }

    @staticmethod
    def _parse_iso_date(s: str):
        """Parse ISO date from Gamma API (Z → +00:00 for timezone-aware)."""
        from datetime import datetime
        if not s:
            return None
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            return None

    def find_active_btc_5m_market_by_slug(self) -> Optional[Dict]:
        """
        Trova il market BTC Up/Down 5m costruendo lo slug dalla finestra temporale corrente
        (stesso approccio del bot Rust cakaroni/polymarket-arbitrage-bot-btc-15m).
        Slug: btc-updown-5m-{unix_ts_arrotondato_alla_finestra_5m}.
        Prova la finestra corrente e le 3 precedenti.
        Returns:
            dict (market) da event['markets'][0] oppure None.
        """
        import time
        period_secs = 300  # 5 minuti
        now_secs = int(time.time())
        rounded = (now_secs // period_secs) * period_secs

        for offset in range(4):  # 0 = corrente, 1,2,3 = precedenti
            try_ts = rounded - (offset * period_secs)
            slug = f"btc-updown-5m-{try_ts}"
            event = self.get_event_by_slug(slug)
            if not event:
                continue
            markets = event.get("markets")
            if not markets or not isinstance(markets, list):
                continue
            market = markets[0] if isinstance(markets[0], dict) else None
            if not market:
                continue
            if market.get("closed") is True:
                continue
            if offset > 0:
                print(f"   [slug] Trovato market 5m con slug precedente: {slug}")
            return market
        return None

    def find_active_btc_5m_market(self, limit: int = 1000) -> Optional[Dict]:
        """
        Trova il market 'Bitcoin Up or Down' attivo (finestra 5m più vicina nel futuro).
        Prima prova discovery per slug (come bot Rust); fallback: Gamma /markets con filtri.
        Returns:
            dict (market) oppure None se non trovato
        """
        market = self.find_active_btc_5m_market_by_slug()
        if market:
            return market

        from datetime import datetime, timezone
        try:
            response = self._session.get(
                f"{self.BASE_URL}/markets",
                params={
                    "active": True,
                    "closed": False,
                    "limit": limit,
                    "order": "endDate",
                    "ascending": True,
                },
                timeout=15,
            )
            if not response.ok:
                print(f"Gamma /markets status: {response.status_code}")
            response.raise_for_status()
            data = response.json()
            markets = data if isinstance(data, list) else []
        except Exception as e:
            print("Errore chiamando Gamma API /markets:", e)
            return None

        now = datetime.now(timezone.utc)
        candidates = []

        for m in markets:
            q = m.get("question") or ""
            q_lower = q.lower()
            if not q_lower or "bitcoin" not in q_lower or "up" not in q_lower or "down" not in q_lower:
                continue
            end_date_str = m.get("endDate") or m.get("end_date")
            if not end_date_str:
                continue
            end_dt = self._parse_iso_date(end_date_str)
            if end_dt is None or end_dt <= now:
                continue
            candidates.append((end_dt, m))

        if not candidates:
            with_btc = sum(1 for m in markets if "bitcoin" in (m.get("question") or "").lower())
            print(f"   [debug] Gamma /markets: {len(markets)} totali, {with_btc} con 'bitcoin'. Nessuno con endDate>now.")
            return None
        candidates.sort(key=lambda x: x[0])
        return candidates[0][1]

    def debug_markets_raw(self, limit: int = 50) -> None:
        """
        Ispeziona la risposta grezza di Gamma /markets (status, tipo, primi market).
        Chiamare da bot o REPL per debugging: client.debug_markets_raw()
        """
        try:
            response = self._session.get(
                f"{self.BASE_URL}/markets",
                params={
                    "active": True,
                    "closed": False,
                    "limit": limit,
                    "order": "endDate",
                    "ascending": True,
                },
                timeout=15,
            )
            print("Status:", response.status_code)
            data = response.json()
            print("Tipo risposta:", type(data))
            if isinstance(data, list):
                print("Numero markets:", len(data))
                for i, m in enumerate(data[:3]):
                    print(f"\n--- MARKET {i+1} ---")
                    print("Keys:", list(m.keys())[:20])
                    print("slug:", m.get("slug"))
                    print("question:", (m.get("question") or "")[:80])
                    print("endDate:", m.get("endDate"))
            else:
                print("Contenuto (snippet):", str(data)[:500])
        except Exception as e:
            print("Errore:", e)

    def get_active_btc_updown_markets(self) -> List[Dict]:
        """
        Ritorna i market "Bitcoin Up or Down" 5m per la finestra attiva.
        Usa find_active_btc_5m_market(); se c'è un event_id nel market, restituisce tutti i market dell'evento.
        """
        market = self.find_active_btc_5m_market(limit=1000)
        if not market:
            return []
        event_id = None
        events_arr = market.get("events")
        if events_arr and len(events_arr) > 0 and isinstance(events_arr[0], dict):
            event_id = events_arr[0].get("id")
        if event_id:
            event_markets = self.get_markets_for_event(event_id)
            if event_markets:
                return event_markets
        return [market]


class CLOBWebSocketClient:
    """
    Async WebSocket client for real-time Polymarket orderbook updates
    Uses websockets (asyncio) for better compatibility with Polymarket server
    """
    
    WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
    
    def __init__(self, on_message_callback: Optional[Callable] = None):
        """
        Initialize WebSocket client
        
        Args:
            on_message_callback: Async function to call when messages are received
        """
        self.on_message_callback = on_message_callback
        self.connected = False
        self.subscribed_tokens = set()
        self.ws = None
        self._running = False
        self._reconnect_interval = 5.0
        self._ping_interval = 20.0
        self._ping_timeout = 10.0
    
    async def connect(self):
        """Establish WebSocket connection"""
        try:
            self.ws = await websockets.connect(
                self.WS_URL,
                ping_interval=self._ping_interval,
                ping_timeout=self._ping_timeout,
                close_timeout=10
            )
            self.connected = True
            print("WebSocket connected successfully")
            return True
        except Exception as e:
            print(f"Error connecting to WebSocket: {e}")
            self.connected = False
            return False
    
    async def subscribe(self, token_ids: List[str]):
        """
        Subscribe to orderbook updates for token IDs
        
        Args:
            token_ids: List of CLOB token IDs to subscribe to
        """
        if not self.connected or not self.ws:
            print("WebSocket not connected. Call connect() first.")
            return False
        
        subscription_msg = {
            "type": "market",
            "assets_ids": token_ids
        }
        
        try:
            await self.ws.send(json.dumps(subscription_msg))
            self.subscribed_tokens.update(token_ids)
            print(f"✅ Subscribed to {len(token_ids)} tokens")
            return True
        except Exception as e:
            print(f"Error subscribing to tokens: {e}")
            return False
    
    async def subscribe_more(self, token_ids: List[str]):
        """
        Subscribe to additional tokens after initial subscription
        
        Args:
            token_ids: Additional token IDs to subscribe to
        """
        if not self.connected or not self.ws:
            return False
        
        subscription_msg = {
            "assets_ids": token_ids,
            "operation": "subscribe"
        }
        
        try:
            await self.ws.send(json.dumps(subscription_msg))
            self.subscribed_tokens.update(token_ids)
            print(f"✅ Subscribed to {len(token_ids)} additional tokens")
            return True
        except Exception as e:
            print(f"Error subscribing to additional tokens: {e}")
            return False
    
    async def unsubscribe(self, token_ids: List[str]):
        """Unsubscribe from orderbook updates for specific tokens"""
        if not self.connected or not self.ws:
            return False
        
        unsubscribe_msg = {
            "assets_ids": token_ids,
            "operation": "unsubscribe"
        }
        
        try:
            await self.ws.send(json.dumps(unsubscribe_msg))
            self.subscribed_tokens.difference_update(token_ids)
            print(f"Unsubscribed from {len(token_ids)} tokens")
            return True
        except Exception as e:
            print(f"Error unsubscribing: {e}")
            return False
    
    async def _handle_message(self, message: str):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(message)
            
            # Handle ping/pong (websockets handles this automatically, but just in case)
            if isinstance(data, str) and data == "PONG":
                return
            
            # Call callback if provided
            if self.on_message_callback:
                if asyncio.iscoroutinefunction(self.on_message_callback):
                    await self.on_message_callback(data)
                else:
                    # If callback is not async, run it in executor to avoid blocking
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, self.on_message_callback, data)
                    
        except json.JSONDecodeError as e:
            print(f"Error parsing WebSocket message: {e}")
            print(f"Message was: {message[:200]}")
        except Exception as e:
            print(f"Error handling WebSocket message: {e}")
            import traceback
            traceback.print_exc()
    
    async def run(self, auto_reconnect: bool = True):
        """
        Run the WebSocket client and process messages
        
        Args:
            auto_reconnect: Whether to automatically reconnect on disconnect
        """
        self._running = True
        
        while self._running:
            try:
                # Connect
                if not await self.connect():
                    if auto_reconnect:
                        print(f"Reconnecting in {self._reconnect_interval}s...")
                        await asyncio.sleep(self._reconnect_interval)
                        continue
                    else:
                        break
                
                # Subscribe to tokens if we have any
                if self.subscribed_tokens:
                    await self.subscribe(list(self.subscribed_tokens))
                
                # Process messages
                try:
                    async for message in self.ws:
                        await self._handle_message(message)
                except websockets.exceptions.ConnectionClosed as e:
                    print(f"WebSocket connection closed: {e.code} - {e.reason}")
                    self.connected = False
                    
                    if not self._running:
                        break
                    
                    if auto_reconnect:
                        print(f"Reconnecting in {self._reconnect_interval}s...")
                        await asyncio.sleep(self._reconnect_interval)
                    else:
                        break
                        
            except Exception as e:
                print(f"Error in WebSocket run loop: {e}")
                self.connected = False
                
                if not self._running:
                    break
                
                if auto_reconnect:
                    print(f"Reconnecting in {self._reconnect_interval}s...")
                    await asyncio.sleep(self._reconnect_interval)
                else:
                    break
    
    async def disconnect(self):
        """Close WebSocket connection"""
        self._running = False
        self.connected = False
        if self.ws:
            await self.ws.close()
        print("WebSocket disconnected")
    
    def stop(self):
        """Stop the WebSocket client"""
        self._running = False
