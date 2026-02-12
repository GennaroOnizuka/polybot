"""
Polymarket Trading Bot
Main orchestration file that coordinates data collection, strategy, and execution
"""

import os
import json
import time
import signal
import sys
from dotenv import load_dotenv
from typing import Dict, List, Optional

# Note: This file uses the old websocket-client (synchronous)
# For stable WebSocket connections, use bot_async.py instead
from data_collector import GammaAPIClient, CLOBWebSocketClient
from strategy import SumToOneArbitrageStrategy, ArbitrageOpportunity
from executor import OrderExecutor


class PolymarketBot:
    """Main bot class that orchestrates all components"""
    
    def __init__(self):
        """Initialize bot with configuration from environment variables"""
        # Load environment variables
        load_dotenv()
        
        # API credentials
        self.api_key = os.getenv("POLYMARKET_API_KEY")
        self.api_secret = os.getenv("POLYMARKET_API_SECRET")
        self.api_passphrase = os.getenv("POLYMARKET_API_PASSPHRASE")
        self.private_key = os.getenv("PRIVATE_KEY")
        self.builder_key = os.getenv("BUILDER_KEY", "019c3a33-11c8-7651-85f8-48d588ba088e")
        
        # Configuration
        self.signature_type = int(os.getenv("SIGNATURE_TYPE", "0"))
        self.max_position_size = float(os.getenv("MAX_POSITION_SIZE", "0.05"))
        self.min_profit_margin = float(os.getenv("MIN_PROFIT_MARGIN", "0.02"))
        
        # Validate required credentials
        if not all([self.api_key, self.api_secret, self.api_passphrase, self.private_key]):
            raise ValueError("Missing required API credentials in .env file")
        
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
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print("\nShutdown signal received. Stopping bot...")
        self.stop()
        sys.exit(0)
    
    def discover_markets(self, limit: int = 50, event_slug: Optional[str] = None) -> List[Dict]:
        """
        Discover markets using Gamma API
        
        Args:
            limit: Maximum number of markets to fetch (if not using event_slug)
            event_slug: Optional slug of a specific event to monitor (e.g., "btc-updown-5m-1770909300")
            
        Returns:
            List of market dictionaries with clobTokenIds
        """
        if event_slug:
            print(f"Fetching markets for event: {event_slug}")
            # Get event by slug
            event = self.gamma_client.get_event_by_slug(event_slug)
            if not event:
                print(f"❌ Event not found: {event_slug}")
                return []
            
            event_id = event.get("id")
            if not event_id:
                print(f"❌ Event ID not found in response")
                return []
            
            # Get markets for this event
            markets = self.gamma_client.get_markets_for_event(event_id)
            print(f"Found {len(markets)} markets for event '{event.get('title', event_slug)}'")
            return markets
        else:
            print(f"Discovering active markets (limit: {limit})...")
            markets = self.gamma_client.get_active_markets(limit=limit)
            print(f"Found {len(markets)} active markets")
            return markets
    
    def setup_market_monitoring(self, markets: List[Dict]):
        """
        Setup WebSocket monitoring for markets
        
        Args:
            markets: List of market dictionaries from Gamma API
        """
        if not self.ws_client:
            self.ws_client = CLOBWebSocketClient(on_message_callback=self._handle_ws_message)
        
        # Extract token IDs from markets
        # Markets have a 'clobTokenIds' field which is a string (comma-separated or JSON array string)
        token_ids = set()
        markets_processed = 0
        
        # Debug: print first market structure
        if markets:
            print(f"\nDebug: Sample market structure:")
            sample_market = markets[0]
            print(f"  Keys: {list(sample_market.keys())[:15]}...")
            if "clobTokenIds" in sample_market:
                print(f"  clobTokenIds: {sample_market['clobTokenIds']}")
            if "outcomes" in sample_market:
                print(f"  Has 'outcomes' key")
        
        for market in markets:
            try:
                markets_processed += 1
                market_id = market.get("id") or market.get("slug") or "unknown"
                
                # Extract clobTokenIds from market
                # clobTokenIds can be a string (comma-separated) or array
                clob_token_ids = market.get("clobTokenIds")
                
                if clob_token_ids:
                    # Handle different formats
                    if isinstance(clob_token_ids, str):
                        # Try to parse as JSON array first
                        try:
                            import json
                            token_list = json.loads(clob_token_ids)
                            if isinstance(token_list, list):
                                for token_id in token_list:
                                    if token_id:
                                        token_ids.add(str(token_id))
                        except (json.JSONDecodeError, ValueError):
                            # If not JSON, try comma-separated
                            token_list = [t.strip() for t in clob_token_ids.split(",") if t.strip()]
                            for token_id in token_list:
                                token_ids.add(token_id)
                    elif isinstance(clob_token_ids, list):
                        # Already a list
                        for token_id in clob_token_ids:
                            if token_id:
                                token_ids.add(str(token_id))
                    
                    # Store market info for each token
                    for token_id in token_ids:
                        if token_id not in self.monitored_markets:
                            self.monitored_markets[token_id] = {
                                "market_id": market_id,
                                "outcome": "unknown",  # Will be determined from orderbook
                                "market_data": market
                            }
                
            except Exception as e:
                print(f"Error processing market {markets_processed}: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        print(f"Processed {markets_processed} markets, found {len(token_ids)} token IDs")
        
        # Subscribe to tokens in smaller batches (WebSocket has limits)
        if token_ids:
            # Limit batch size to avoid overwhelming the WebSocket
            BATCH_SIZE = 20  # Subscribe to 20 tokens at a time
            token_list = list(token_ids)
            
            # Connect WebSocket first
            self.ws_client.connect()
            time.sleep(2)  # Wait for connection to stabilize
            
            if self.ws_client.connected:
                print(f"✅ WebSocket connected, subscribing to {len(token_ids)} tokens in batches of {BATCH_SIZE}...")
                
                # Subscribe in batches
                for i in range(0, len(token_list), BATCH_SIZE):
                    batch = token_list[i:i + BATCH_SIZE]
                    try:
                        if self.ws_client.connected and self.ws_client.ws:
                            subscription_msg = {
                                "type": "market" if i == 0 else None,  # Only first message needs type
                                "assets_ids": batch
                            }
                            # Remove None values
                            subscription_msg = {k: v for k, v in subscription_msg.items() if v is not None}
                            
                            if i == 0:
                                # First batch uses type="market" (lowercase per documentation)
                                subscription_msg = {
                                    "assets_ids": batch,
                                    "type": "market"
                                }
                                self.ws_client.ws.send(json.dumps(subscription_msg))
                            else:
                                # Subsequent batches use operation="subscribe"
                                subscribe_msg = {
                                    "assets_ids": batch,
                                    "operation": "subscribe"
                                }
                                self.ws_client.ws.send(json.dumps(subscribe_msg))
                            
                            self.ws_client.subscribed_tokens.update(batch)
                            print(f"  Batch {i//BATCH_SIZE + 1}: Subscribed to {len(batch)} tokens")
                            time.sleep(0.5)  # Small delay between batches
                        else:
                            print(f"⚠️  WebSocket disconnected during batch {i//BATCH_SIZE + 1}")
                            break
                    except Exception as e:
                        print(f"❌ Error subscribing batch {i//BATCH_SIZE + 1}: {e}")
                        if not self.ws_client.connected:
                            break
                
                if self.ws_client.connected:
                    print(f"✅ Successfully subscribed to {len(self.ws_client.subscribed_tokens)} tokens")
                else:
                    print("⚠️  WebSocket disconnected. Bot will use REST API polling for some features.")
            else:
                print("⚠️  WebSocket connection failed. Bot will use REST API polling instead.")
                print("   (This is slower but will still work)")
        else:
            print("⚠️  No token IDs found in markets. Check market data structure.")
        
        print(f"\n📊 Monitoring {len(token_ids)} tokens across {len(markets)} markets")
    
    def _handle_ws_message(self, message: Dict):
        """Handle incoming WebSocket messages"""
        try:
            # Handle different message types from WebSocket
            # The structure may vary, so we handle multiple formats
            token_id = None
            
            # Try to extract token_id from different possible structures
            if isinstance(message, dict):
                token_id = message.get("token_id") or message.get("tokenId") or message.get("token")
                
                # If message contains orderbook data, extract it
                if "bids" in message or "asks" in message:
                    # This is an orderbook update
                    if token_id:
                        self.orderbook_cache[token_id] = message
                        # Check for arbitrage opportunities
                        self._check_and_execute_arbitrage(token_id)
                elif token_id:
                    # Store token reference for later use
                    self.orderbook_cache[token_id] = message
                    
        except Exception as e:
            print(f"Error handling WebSocket message: {e}")
            import traceback
            traceback.print_exc()
    
    def _check_and_execute_arbitrage(self, token_id: str):
        """
        Check for arbitrage opportunities and execute if found
        
        Args:
            token_id: Token ID that was updated
        """
        # Find the pair (YES/NO) for this market
        market_info = self.monitored_markets.get(token_id)
        if not market_info:
            return
        
        market_id = market_info["market_id"]
        market_data = market_info["market_data"]
        
        # Find YES and NO token IDs
        yes_token_id = None
        no_token_id = None
        
        for outcome in market_data.get("outcomes", []):
            outcome_type = outcome.get("outcome", "").upper()
            if outcome_type == "YES":
                yes_token_id = outcome.get("clobTokenId")
            elif outcome_type == "NO":
                no_token_id = outcome.get("clobTokenId")
        
        if not yes_token_id or not no_token_id:
            return
        
        # Get orderbooks
        yes_orderbook = self.orderbook_cache.get(yes_token_id)
        no_orderbook = self.orderbook_cache.get(no_token_id)
        
        if not yes_orderbook or not no_orderbook:
            # Fetch orderbooks if not in cache
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
    
    def run(self):
        """Main bot loop"""
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
            
            # Setup monitoring
            self.setup_market_monitoring(markets)
            
            # Main loop
            print("\nBot is running. Monitoring markets for opportunities...")
            print("Press Ctrl+C to stop.\n")
            
            while self.running:
                # Periodic tasks
                time.sleep(1)
                
                # Check for stale orderbooks and refresh
                # This ensures we don't miss opportunities if WebSocket fails
                if len(self.orderbook_cache) > 0:
                    # Refresh orderbooks every 30 seconds
                    # (Implementation can be added if needed)
                    pass
        
        except KeyboardInterrupt:
            print("\nKeyboard interrupt received")
        except Exception as e:
            print(f"Error in main loop: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.stop()
    
    def stop(self):
        """Stop the bot and cleanup"""
        print("\nStopping bot...")
        self.running = False
        
        if self.ws_client:
            self.ws_client.disconnect()
        
        print("Bot stopped.")


def main():
    """Entry point"""
    try:
        bot = PolymarketBot()
        bot.run()
    except Exception as e:
        print(f"Failed to start bot: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
