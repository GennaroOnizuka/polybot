"""
Strategy Layer for Polymarket Bot
Implements trading strategies including sum-to-one arbitrage
"""

from typing import Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class ArbitrageOpportunity:
    """Represents an arbitrage opportunity"""
    market_id: str
    yes_token_id: str
    no_token_id: str
    yes_price: float
    no_price: float
    total_cost: float
    profit_margin: float
    action: str  # "buy_both" or "sell_both"


class SumToOneArbitrageStrategy:
    """
    Sum-to-One Arbitrage Strategy
    
    In a binary market, YES + NO prices should equal $1.00
    If they don't, there's an arbitrage opportunity
    """
    
    def __init__(self, min_profit_margin: float = 0.02):
        """
        Initialize strategy
        
        Args:
            min_profit_margin: Minimum profit margin required (default 2%)
        """
        self.min_profit_margin = min_profit_margin
    
    def _convert_orderbook_to_dict(self, orderbook):
        """Helper to convert orderbook to dict format"""
        if isinstance(orderbook, dict):
            return orderbook
        elif orderbook is None:
            return None
        elif hasattr(orderbook, '__dict__'):
            return orderbook.__dict__
        elif hasattr(orderbook, 'dict'):
            try:
                return orderbook.dict()
            except:
                pass
        elif hasattr(orderbook, 'bids') and hasattr(orderbook, 'asks'):
            return {
                "bids": list(orderbook.bids) if hasattr(orderbook.bids, '__iter__') else [],
                "asks": list(orderbook.asks) if hasattr(orderbook.asks, '__iter__') else []
            }
        return None
    
    def calculate_midpoint_price(self, orderbook) -> Optional[float]:
        """
        Calculate midpoint price from orderbook
        
        Args:
            orderbook: Orderbook data with bids and asks (dict or object)
            
        Returns:
            Midpoint price or None if insufficient liquidity
        """
        try:
            # Handle both dict and object formats
            if not isinstance(orderbook, dict):
                if hasattr(orderbook, '__dict__'):
                    orderbook = orderbook.__dict__
                elif hasattr(orderbook, 'dict'):
                    orderbook = orderbook.dict()
                elif hasattr(orderbook, 'bids') and hasattr(orderbook, 'asks'):
                    # Direct attribute access
                    bids = orderbook.bids if hasattr(orderbook.bids, '__iter__') else []
                    asks = orderbook.asks if hasattr(orderbook.asks, '__iter__') else []
                else:
                    return None
            
            # Extract bids and asks
            if isinstance(orderbook, dict):
                bids = orderbook.get("bids", [])
                asks = orderbook.get("asks", [])
            else:
                bids = getattr(orderbook, "bids", [])
                asks = getattr(orderbook, "asks", [])
            
            if not bids or not asks:
                return None
            
            # Get best bid and ask
            # Handle different formats: list of lists, list of dicts, or objects
            if bids and len(bids) > 0:
                if isinstance(bids[0], (list, tuple)):
                    best_bid = float(bids[0][0])
                elif isinstance(bids[0], dict):
                    best_bid = float(bids[0].get("price", bids[0].get("price", 0)))
                else:
                    best_bid = float(bids[0])
            else:
                return None
            
            if asks and len(asks) > 0:
                if isinstance(asks[0], (list, tuple)):
                    best_ask = float(asks[0][0])
                elif isinstance(asks[0], dict):
                    best_ask = float(asks[0].get("price", asks[0].get("price", 1)))
                else:
                    best_ask = float(asks[0])
            else:
                return None
            
            # Calculate midpoint
            midpoint = (best_bid + best_ask) / 2
            return midpoint
            
        except (KeyError, ValueError, IndexError, AttributeError, TypeError) as e:
            print(f"Error calculating midpoint price: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def check_arbitrage_opportunity(
        self,
        market_id: str,
        yes_token_id: str,
        no_token_id: str,
        yes_orderbook: Dict,
        no_orderbook: Dict
    ) -> Optional[ArbitrageOpportunity]:
        """
        Check for sum-to-one arbitrage opportunity
        
        Args:
            market_id: Market identifier
            yes_token_id: CLOB token ID for YES outcome
            no_token_id: CLOB token ID for NO outcome
            yes_orderbook: Orderbook for YES token
            no_orderbook: Orderbook for NO token
            
        Returns:
            ArbitrageOpportunity if found, None otherwise
        """
        yes_price = self.calculate_midpoint_price(yes_orderbook)
        no_price = self.calculate_midpoint_price(no_orderbook)
        
        if yes_price is None or no_price is None:
            return None
        
        total_cost = yes_price + no_price
        
        # Check if prices sum to less than $1.00 (buy opportunity)
        if total_cost < 1.0:
            profit_margin = 1.0 - total_cost
            
            if profit_margin >= self.min_profit_margin:
                return ArbitrageOpportunity(
                    market_id=market_id,
                    yes_token_id=yes_token_id,
                    no_token_id=no_token_id,
                    yes_price=yes_price,
                    no_price=no_price,
                    total_cost=total_cost,
                    profit_margin=profit_margin,
                    action="buy_both"
                )
        
        # Check if prices sum to more than $1.00 (sell opportunity)
        elif total_cost > 1.0:
            profit_margin = total_cost - 1.0
            
            if profit_margin >= self.min_profit_margin:
                return ArbitrageOpportunity(
                    market_id=market_id,
                    yes_token_id=yes_token_id,
                    no_token_id=no_token_id,
                    yes_price=yes_price,
                    no_price=no_price,
                    total_cost=total_cost,
                    profit_margin=profit_margin,
                    action="sell_both"
                )
        
        return None
    
    def calculate_position_size(
        self,
        opportunity: ArbitrageOpportunity,
        portfolio_value: float,
        max_position_size: float = 0.05
    ) -> Tuple[float, float]:
        """
        Calculate position sizes for YES and NO tokens
        
        Args:
            opportunity: The arbitrage opportunity
            portfolio_value: Total portfolio value in USDC
            max_position_size: Maximum position size as fraction of portfolio
            
        Returns:
            Tuple of (yes_size, no_size) in USDC
        """
        max_investment = portfolio_value * max_position_size
        
        # For sum-to-one arbitrage, invest equal amounts in both sides
        yes_size = max_investment / 2
        no_size = max_investment / 2
        
        return yes_size, no_size
