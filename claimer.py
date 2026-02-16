"""
Auto-Claim Module for Polymarket Bot
Handles on-chain redemption of winning positions on Polygon.
Supports email/Magic Link accounts (signature_type=1) via proxy factory.

Flow:
1. Query Polymarket data API for redeemable positions
2. For each position, encode redeemPositions() on the CTF contract
3. Batch ALL redeems into a single proxy() call (one tx, one gas fee)
4. Sign and send the transaction on-chain (pays gas in POL)

Gas cost: ~0.10-0.20 POL per batch (~$0.05-0.10), regardless of number of positions
"""

import os
import json
import time
from typing import Optional, List, Dict, Tuple

import httpx
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from eth_account import Account


# ── Polygon mainnet contract addresses ──────────────────────────────────────
CTF_ADDRESS = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"
USDC_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
EXCHANGE_ADDRESS = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
NEG_RISK_ADAPTER_ADDRESS = "0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296"
PROXY_FACTORY_ADDRESS = "0xaB45c5A4B0c941a2F231C04C3f49182e1A254052"

HASH_ZERO = bytes(32)

# ── Minimal ABIs ────────────────────────────────────────────────────────────
CTF_REDEEM_ABI = [
    {
        "inputs": [
            {"name": "collateralToken", "type": "address"},
            {"name": "parentCollectionId", "type": "bytes32"},
            {"name": "conditionId", "type": "bytes32"},
            {"name": "indexSets", "type": "uint256[]"},
        ],
        "name": "redeemPositions",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    }
]

NEG_RISK_REDEEM_ABI = [
    {
        "inputs": [
            {"name": "conditionId", "type": "bytes32"},
            {"name": "amounts", "type": "uint256[]"},
        ],
        "name": "redeemPositions",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    }
]

PROXY_FACTORY_ABI = [
    {
        "inputs": [
            {
                "components": [
                    {"name": "typeCode", "type": "uint8"},
                    {"name": "to", "type": "address"},
                    {"name": "value", "type": "uint256"},
                    {"name": "data", "type": "bytes"},
                ],
                "name": "calls",
                "type": "tuple[]",
            }
        ],
        "name": "proxy",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    }
]

EXCHANGE_PROXY_ABI = [
    {
        "inputs": [{"name": "_addr", "type": "address"}],
        "name": "getPolyProxyWalletAddress",
        "outputs": [{"name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    }
]

CT_BALANCE_ABI = [
    {
        "constant": True,
        "inputs": [
            {"name": "account", "type": "address"},
            {"name": "id", "type": "uint256"},
        ],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
    }
]


class PositionClaimer:
    """
    Automatic on-chain claiming (redeeming) of winning Polymarket positions.
    Pays gas in POL on Polygon (~0.10-0.15 POL per tx).
    Works with email/Magic Link accounts (signature_type=1) via proxy factory.
    """

    def __init__(self, private_key: str, proxy_url: str = ""):
        pk = private_key.strip()
        if not pk.startswith("0x"):
            pk = "0x" + pk
        self.account = Account.from_key(pk)
        self.eoa_address = self.account.address
        self.proxy_url = proxy_url

        # Web3 setup (Polygon PoA chain) — custom RPC or fallback
        rpc_url = os.getenv("POLYGON_RPC_URL", "https://polygon-rpc.com")
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

        # Contract instances
        self.ctf = self.w3.eth.contract(
            address=Web3.to_checksum_address(CTF_ADDRESS), abi=CTF_REDEEM_ABI
        )
        self.neg_risk_adapter = self.w3.eth.contract(
            address=Web3.to_checksum_address(NEG_RISK_ADAPTER_ADDRESS),
            abi=NEG_RISK_REDEEM_ABI,
        )
        self.proxy_factory = self.w3.eth.contract(
            address=Web3.to_checksum_address(PROXY_FACTORY_ADDRESS),
            abi=PROXY_FACTORY_ABI,
        )
        self.exchange = self.w3.eth.contract(
            address=Web3.to_checksum_address(EXCHANGE_ADDRESS),
            abi=EXCHANGE_PROXY_ABI,
        )

        # For on-chain balance checks
        self.ct_balance = self.w3.eth.contract(
            address=Web3.to_checksum_address(CTF_ADDRESS), abi=CT_BALANCE_ABI
        )

        # HTTP client for data API (with proxy if configured)
        if proxy_url:
            self.http = httpx.Client(http2=True, proxy=proxy_url, timeout=30.0)
        else:
            self.http = httpx.Client(http2=True, timeout=30.0)

        # Derive proxy wallet address on-chain
        self.poly_proxy_address = self._get_poly_proxy_address()
        print(f"[Claimer] EOA: {self.eoa_address}")
        print(f"[Claimer] Proxy wallet: {self.poly_proxy_address}")
        try:
            pol = self.w3.eth.get_balance(self.eoa_address) / 10**18
            print(f"[Claimer] POL balance: {pol:.4f}")
        except Exception:
            print("[Claimer] POL balance: (RPC busy, skip)")

    def _get_poly_proxy_address(self) -> str:
        """Get the Polymarket proxy wallet address for this EOA."""
        return self.exchange.functions.getPolyProxyWalletAddress(
            self.eoa_address
        ).call()

    def _rpc_call_with_retry(self, fn, max_retries=3):
        """Execute an RPC call with retry on rate limit."""
        for attempt in range(max_retries):
            try:
                return fn()
            except Exception as e:
                if "rate limit" in str(e).lower() or "too many" in str(e).lower():
                    wait = 5 * (attempt + 1)
                    time.sleep(wait)
                    continue
                raise
        return fn()

    def _get_onchain_balance(self, token_id: str) -> float:
        """Check actual on-chain token balance for the proxy wallet."""
        try:
            raw = self._rpc_call_with_retry(
                lambda: self.ct_balance.functions.balanceOf(
                    Web3.to_checksum_address(self.poly_proxy_address),
                    int(token_id),
                ).call()
            )
            return raw / 1e6
        except Exception:
            return 0.0

    # ── 1. Fetch redeemable positions ───────────────────────────────────────
    def get_redeemable_positions(self) -> List[Dict]:
        """Fetch all redeemable positions from Polymarket data API."""
        try:
            params = {
                "user": self.poly_proxy_address,
                "redeemable": "true",
                "sizeThreshold": "0",
            }
            resp = self.http.get(
                "https://data-api.polymarket.com/positions", params=params
            )
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, list) else []
        except Exception as e:
            print(f"[Claimer] Errore fetch posizioni riscattabili: {e}")
            return []

    # ── 2. Encode redeemPositions call ──────────────────────────────────────
    def _encode_redeem(
        self, condition_id: str, neg_risk: bool, amounts: List[int]
    ) -> Tuple[str, str]:
        """
        Encode redeemPositions ABI call.
        Returns (target_contract_address, hex_encoded_data).
        """
        cid_bytes = bytes.fromhex(condition_id.removeprefix("0x"))

        if neg_risk:
            data = self.neg_risk_adapter.encode_abi(
                abi_element_identifier="redeemPositions",
                args=[cid_bytes, amounts],
            )
            return (NEG_RISK_ADAPTER_ADDRESS, data)
        else:
            data = self.ctf.encode_abi(
                abi_element_identifier="redeemPositions",
                args=[
                    Web3.to_checksum_address(USDC_ADDRESS),
                    HASH_ZERO,
                    cid_bytes,
                    [1, 2],
                ],
            )
            return (CTF_ADDRESS, data)

    # ── 3. Send batch on-chain via proxy factory ──────────────────────────
    def _send_batch_tx(self, proxy_calls: list) -> Optional[str]:
        """
        Send a single proxy() transaction containing multiple calls.
        proxy_calls = list of (typeCode, to, value, data_bytes) tuples.
        Returns transaction hash or None.
        """
        if not proxy_calls:
            return None

        # Build the proxy factory transaction (with RPC retry)
        nonce = self._rpc_call_with_retry(
            lambda: self.w3.eth.get_transaction_count(self.eoa_address)
        )
        gas_price = self._rpc_call_with_retry(lambda: self.w3.eth.gas_price)
        adjusted_gas_price = int(gas_price * 1.1)

        tx = self.proxy_factory.functions.proxy(
            proxy_calls
        ).build_transaction(
            {
                "from": self.eoa_address,
                "nonce": nonce,
                "gasPrice": adjusted_gas_price,
                "chainId": 137,
            }
        )

        # Estimate gas
        try:
            estimated = self._rpc_call_with_retry(
                lambda: self.w3.eth.estimate_gas(tx)
            )
            tx["gas"] = int(estimated * 1.2)
        except Exception as e:
            print(f"[Claimer] Gas estimation fallita, uso default: {e}")
            tx["gas"] = 200000 * len(proxy_calls)

        gas_cost_pol = (tx["gas"] * adjusted_gas_price) / 10**18
        print(f"[Claimer] Gas stimato: {tx['gas']} (~{gas_cost_pol:.4f} POL)")

        # Check balance
        try:
            balance = self._rpc_call_with_retry(
                lambda: self.w3.eth.get_balance(self.eoa_address)
            )
            needed = tx["gas"] * adjusted_gas_price
            if balance < needed:
                print(
                    f"[Claimer] POL insufficiente: hai {balance / 10**18:.4f}, "
                    f"servono ~{needed / 10**18:.4f}"
                )
                return None
        except Exception:
            pass

        # Sign and send (with retry on RPC rate limit)
        signed = self.account.sign_transaction(tx)
        tx_hash = self._rpc_call_with_retry(
            lambda: self.w3.eth.send_raw_transaction(signed.raw_transaction)
        )
        tx_hash_hex = "0x" + tx_hash.hex()
        print(f"[Claimer] Tx inviata: {tx_hash_hex}")

        # Wait for receipt (with retry on RPC rate limit)
        for attempt in range(5):
            try:
                receipt = self.w3.eth.wait_for_transaction_receipt(
                    tx_hash, timeout=120
                )
                actual_cost = (receipt.gasUsed * receipt.effectiveGasPrice) / 10**18
                if receipt.status == 1:
                    print(f"[Claimer] Batch redeem OK! Gas totale: {actual_cost:.4f} POL")
                    return tx_hash_hex
                else:
                    print(f"[Claimer] Batch FALLITO on-chain. Gas: {actual_cost:.4f} POL")
                    return None
            except Exception as e:
                if "rate limit" in str(e).lower() or "too many" in str(e).lower():
                    wait = 5 * (attempt + 1)
                    print(f"[Claimer] RPC rate limit, riprovo tra {wait}s...")
                    time.sleep(wait)
                    continue
                print(f"[Claimer] Attesa receipt fallita: {e}")
                return tx_hash_hex
        print(f"[Claimer] Receipt non ottenuta, tx potrebbe essere ok: {tx_hash_hex}")
        return tx_hash_hex

    # ── Public API ──────────────────────────────────────────────────────────
    def claim_all(self) -> int:
        """
        Find and claim ALL redeemable positions in a SINGLE transaction.
        Returns number of positions claimed.
        """
        positions = self.get_redeemable_positions()
        if not positions:
            print("[Claimer] Nessuna posizione da riscattare.")
            return 0

        print(f"[Claimer] API: {len(positions)} posizioni redeemable. Verifico on-chain...")

        # Build list of proxy calls (one per real position)
        proxy_calls = []
        seen_conditions = set()
        labels = []

        for pos in positions:
            condition_id = pos.get("conditionId", "")
            if not condition_id or condition_id in seen_conditions:
                continue
            seen_conditions.add(condition_id)

            token_id = pos.get("asset", "")
            if not token_id:
                continue

            # Verify actual on-chain balance
            onchain_bal = self._get_onchain_balance(token_id)
            if onchain_bal < 0.01:
                continue

            neg_risk = pos.get("negativeRisk", False)
            outcome_index = int(pos.get("outcomeIndex", 0))
            amounts = [onchain_bal, 0.0] if outcome_index == 0 else [0.0, onchain_bal]
            int_amounts = [int(a * 1e6) for a in amounts]

            target, data = self._encode_redeem(condition_id, neg_risk, int_amounts)
            call_bytes = bytes.fromhex(data.removeprefix("0x"))
            proxy_calls.append(
                (1, Web3.to_checksum_address(target), 0, call_bytes)
            )

            title = (pos.get("title", "?") or "?")[:55]
            outcome = pos.get("outcome", "?")
            labels.append(f"  {title} | {outcome} | {onchain_bal:.2f}")

        if not proxy_calls:
            print("[Claimer] Nessuna posizione con saldo reale on-chain.")
            return 0

        print(f"[Claimer] {len(proxy_calls)} posizioni da riscattare in 1 transazione:")
        for lbl in labels:
            print(lbl)

        tx = self._send_batch_tx(proxy_calls)
        if tx:
            print(f"[Claimer] Tutte {len(proxy_calls)} posizioni riscattate!")
            return len(proxy_calls)
        return 0

    def close(self):
        """Close HTTP client."""
        try:
            self.http.close()
        except Exception:
            pass
