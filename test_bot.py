"""
Test script for Polymarket Bot
Tests individual components without executing real trades
"""

import os
from dotenv import load_dotenv
from data_collector import GammaAPIClient
from executor import OrderExecutor


def test_gamma_api():
    """Test Gamma API connection"""
    print("=" * 60)
    print("Testing Gamma API Connection...")
    print("=" * 60)
    
    client = GammaAPIClient()
    markets = client.get_active_markets(limit=5)
    
    if markets:
        print(f"✅ Successfully fetched {len(markets)} markets")
        print("\nSample market:")
        if markets:
            market = markets[0]
            print(f"  ID: {market.get('id', 'N/A')}")
            print(f"  Title: {market.get('title', 'N/A')}")
            print(f"  Outcomes: {len(market.get('outcomes', []))}")
    else:
        print("❌ Failed to fetch markets")
    
    return markets


def test_clob_client():
    """Test CLOB client initialization"""
    print("\n" + "=" * 60)
    print("Testing CLOB Client Initialization...")
    print("=" * 60)
    
    load_dotenv()
    
    api_key = os.getenv("POLYMARKET_API_KEY")
    api_secret = os.getenv("POLYMARKET_API_SECRET")
    api_passphrase = os.getenv("POLYMARKET_API_PASSPHRASE")
    private_key = os.getenv("PRIVATE_KEY")
    signature_type = int(os.getenv("SIGNATURE_TYPE", "0"))
    
    if not all([api_key, api_secret, api_passphrase, private_key]):
        print("❌ Missing API credentials in .env file")
        print("   Please configure your .env file before testing")
        return None
    
    try:
        executor = OrderExecutor(
            api_key=api_key,
            api_secret=api_secret,
            api_passphrase=api_passphrase,
            private_key=private_key,
            signature_type=signature_type
        )
        print("✅ CLOB client initialized successfully")
        
        # Test balance fetch
        print("\nTesting balance fetch...")
        balance = executor.get_balance()
        print(f"  Balance: ${balance:.2f} USDC")
        
        return executor
    except Exception as e:
        print(f"❌ Failed to initialize CLOB client: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_orderbook_fetch(executor, token_id: str = None):
    """Test orderbook fetching"""
    print("\n" + "=" * 60)
    print("Testing Orderbook Fetch...")
    print("=" * 60)
    
    if not executor:
        print("❌ CLOB client not initialized")
        return
    
    # Use a sample token ID if none provided
    # This is a placeholder - replace with actual token ID from a market
    if not token_id:
        print("⚠️  No token ID provided. Skipping orderbook test.")
        print("   To test orderbook, provide a valid token_id from a market")
        return
    
    try:
        orderbook = executor.get_orderbook(token_id)
        if orderbook:
            print(f"✅ Successfully fetched orderbook for token {token_id}")
            bids = orderbook.get("bids", [])
            asks = orderbook.get("asks", [])
            print(f"  Bids: {len(bids)}")
            print(f"  Asks: {len(asks)}")
            if bids:
                print(f"  Best bid: {bids[0]}")
            if asks:
                print(f"  Best ask: {asks[0]}")
        else:
            print(f"❌ Failed to fetch orderbook")
    except Exception as e:
        print(f"❌ Error fetching orderbook: {e}")


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("POLYMARKET BOT - COMPONENT TESTS")
    print("=" * 60)
    print("\nThis script tests individual components without executing trades.")
    print("Make sure your .env file is configured before running.\n")
    
    # Test Gamma API
    markets = test_gamma_api()
    
    # Test CLOB client
    executor = test_clob_client()
    
    # Test orderbook (optional - requires token ID)
    # Uncomment and provide a token_id to test:
    # test_orderbook_fetch(executor, token_id="your_token_id_here")
    
    print("\n" + "=" * 60)
    print("Tests completed!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Verify all tests passed")
    print("2. Configure your .env file with real credentials")
    print("3. Start with paper trading mode")
    print("4. Run the bot: python bot.py")


if __name__ == "__main__":
    main()
