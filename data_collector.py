"""
Data Collection Layer for Polymarket Bot
Handles API connections and WebSocket feeds for real-time market data
"""

import requests
import json
import websocket
import threading
import time
from typing import Dict, List, Optional, Callable
from tenacity import retry, stop_after_attempt, wait_exponential


class GammaAPIClient:
    """Client for Polymarket's Gamma API - used for market discovery"""
    
    BASE_URL = "https://gamma-api.polymarket.com"
    
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
            response = requests.get(url, params=params, timeout=10)
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
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching market details: {e}")
            return None
    
    def get_event_by_slug(self, slug: str) -> Optional[Dict]:
        """Get event details by slug"""
        url = f"{self.BASE_URL}/events/slug/{slug}"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching event by slug: {e}")
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
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, list) else []
        except requests.exceptions.RequestException as e:
            print(f"Error fetching markets for event: {e}")
            return []


class CLOBWebSocketClient:
    """WebSocket client for real-time Polymarket orderbook updates"""
    
    WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
    
    def __init__(self, on_message_callback: Optional[Callable] = None):
        """
        Initialize WebSocket client
        
        Args:
            on_message_callback: Function to call when messages are received
        """
        self.ws = None
        self.on_message_callback = on_message_callback
        self.connected = False
        self.subscribed_tokens = set()
        self.heartbeat_thread = None
        self.pending_subscription = None  # Store subscription to send after connection
        
    def connect(self):
        """Establish WebSocket connection"""
        try:
            self.ws = websocket.WebSocketApp(
                self.WS_URL,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
                on_open=self._on_open
            )
            
            # Start WebSocket in a separate thread
            self.ws_thread = threading.Thread(target=self.ws.run_forever, daemon=True)
            self.ws_thread.start()
            
            # Wait for connection
            timeout = 5
            start_time = time.time()
            while not self.connected and (time.time() - start_time) < timeout:
                time.sleep(0.1)
                
            if self.connected:
                self._start_heartbeat()
                print("WebSocket connected successfully")
            else:
                print("Failed to establish WebSocket connection")
                
        except Exception as e:
            print(f"Error connecting to WebSocket: {e}")
    
    def _on_open(self, ws):
        """Handle WebSocket open event"""
        self.connected = True
        self.ws = ws
        print("WebSocket connection opened")
        
        # Send pending subscription immediately if we have one
        if self.pending_subscription:
            try:
                time.sleep(0.2)  # Small delay to ensure connection is ready
                # Ensure type is lowercase (per official documentation)
                if "type" in self.pending_subscription:
                    self.pending_subscription["type"] = "market"
                ws.send(json.dumps(self.pending_subscription))
                self.subscribed_tokens.update(self.pending_subscription.get("assets_ids", []))
                print(f"✅ Sent initial subscription for {len(self.pending_subscription.get('assets_ids', []))} tokens")
                self.pending_subscription = None
            except Exception as e:
                print(f"Error sending pending subscription: {e}")
    
    def _on_message(self, ws, message):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(message)
            
            # Handle ping/pong
            if isinstance(data, str) and data == "PONG":
                return
            
            # Call callback if provided
            if self.on_message_callback:
                self.on_message_callback(data)
                
        except json.JSONDecodeError as e:
            print(f"Error parsing WebSocket message: {e}")
    
    def _on_error(self, ws, error):
        """Handle WebSocket errors"""
        print(f"WebSocket error: {error}")
    
    def _on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket close event"""
        self.connected = False
        print("WebSocket connection closed")
        # Don't auto-reconnect here - let the bot handle reconnection logic
        # Auto-reconnection can cause infinite loops
    
    def _start_heartbeat(self):
        """Start heartbeat thread to keep connection alive"""
        def heartbeat():
            while self.connected:
                try:
                    if self.ws and self.ws.sock:
                        self.ws.send("PING")
                    time.sleep(10)  # Send ping every 10 seconds (per documentation)
                except Exception as e:
                    print(f"Heartbeat error: {e}")
                    break
        
        self.heartbeat_thread = threading.Thread(target=heartbeat, daemon=True)
        self.heartbeat_thread.start()
    
    def subscribe_to_market(self, token_id: str):
        """
        Subscribe to orderbook updates for a specific token
        
        Args:
            token_id: CLOB token ID for YES or NO outcome
        """
        if not self.connected:
            print("WebSocket not connected. Call connect() first.")
            return
        
        # Add token to subscribed list first
        self.subscribed_tokens.add(token_id)
        
        # Use correct format: if first subscription, use type="market" (lowercase), otherwise use operation="subscribe"
        if len(self.subscribed_tokens) == 1:
            # First subscription - use type format
            subscription = {
                "type": "market",  # Lowercase per documentation
                "assets_ids": [token_id]
            }
        else:
            # Subsequent subscriptions - use operation format
            subscription = {
                "assets_ids": [token_id],
                "operation": "subscribe"
            }
        
        try:
            self.ws.send(json.dumps(subscription))
            print(f"Subscribed to token: {token_id}")
        except Exception as e:
            print(f"Error subscribing to token {token_id}: {e}")
            self.subscribed_tokens.discard(token_id)
    
    def unsubscribe_from_market(self, token_id: str):
        """Unsubscribe from orderbook updates for a specific token"""
        if not self.connected:
            return
        
        subscription = {
            "assets_ids": [token_id],
            "operation": "unsubscribe"
        }
        
        try:
            self.ws.send(json.dumps(subscription))
            self.subscribed_tokens.discard(token_id)
            print(f"Unsubscribed from token: {token_id}")
        except Exception as e:
            print(f"Error unsubscribing from token {token_id}: {e}")
    
    def disconnect(self):
        """Close WebSocket connection"""
        self.connected = False
        if self.ws:
            self.ws.close()
        print("WebSocket disconnected")
