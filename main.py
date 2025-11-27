"""
Pull Aerodrome vote data straight from the onchain sugar contracts and
write a CSV with rewards (fees + bribes) priced in USD plus a rewards/votes ratio.

Notes
-----
- The LP sugar `all()` response is still used for static pool/meta fields.
- Rewards (fees + bribes) now come from the rewards sugar `epochsByAddress`
  endpoint instead of the lp sugar `token{0,1}_fees` fields.
- A simple token price map is used to convert amounts to USD. Populate
  `token_prices.json` to extend prices beyond the built-in stablecoins.
"""

from __future__ import annotations

import csv
import functools
import json
import math
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List

import requests
from web3 import Web3

from fetch_prices import fetch_prices, update_price_map


RPC_URL = "https://lb.drpc.live/base/Avibgvi26EjPsw76UtdwmsS6VEL-8F4R75KJIhIl_7lF"
SUGAR = "0x9DE6Eab7a910A288dE83a04b6A43B52Fd1246f1E"
REWARDS_SUGAR = "0xD4aD2EeeB3314d54212A92f4cBBE684195dEfe3E"
ABI_PATH = Path("sugar_abi.abi")
_WEB3 = None
_SUGAR_CONTRACT = None
_REWARDS_CONTRACT = None
_VOTER_CONTRACT = None
STRUCT_KEYS = [
    "lp",
    "symbol",
    "decimals",
    "liquidity",
    "type",
    "tick",
    "sqrt_ratio",
    "token0",
    "reserve0",
    "staked0",
    "token1",
    "reserve1",
    "staked1",
    "gauge",
    "gauge_liquidity",
    "gauge_alive",
    "fee",
    "bribe",
    "factory",
    "emissions",
    "emissions_token",
    "emissions_cap",
    "pool_fee",
    "unstaked_fee",
    "token0_fees",
    "token1_fees",
    "locked",
    "emerging",
    "created_at",
    "nfpm",
    "alm",
    "root",
]
REWARDS_ABI = [
    {
        "name": "epochsByAddress",
        "type": "function",
        "stateMutability": "view",
        "inputs": [
            {"name": "_limit", "type": "uint256"},
            {"name": "_offset", "type": "uint256"},
            {"name": "_address", "type": "address"},
        ],
        "outputs": [
            {
                "name": "",
                "type": "tuple[]",
                "components": [
                    {"name": "ts", "type": "uint256"},
                    {"name": "lp", "type": "address"},
                    {"name": "votes", "type": "uint256"},
                    {"name": "emissions", "type": "uint256"},
                    {
                        "name": "bribes",
                        "type": "tuple[]",
                        "components": [
                            {"name": "token", "type": "address"},
                            {"name": "amount", "type": "uint256"},
                        ],
                    },
                    {
                        "name": "fees",
                        "type": "tuple[]",
                        "components": [
                            {"name": "token", "type": "address"},
                            {"name": "amount", "type": "uint256"},
                        ],
                    },
                ],
            }
        ],
    }
]
VOTER_ABI = [
    {"name": "totalWeight", "inputs": [], "outputs": [{"type": "int256"}], "stateMutability": "view", "type": "function"},
    {"name": "weights", "inputs": [{"type": "address"}], "outputs": [{"type": "int256"}], "stateMutability": "view", "type": "function"},
]
ZERO_ADDR = "0x0000000000000000000000000000000000000000"
PRICE_MAP_PATH = Path("token_prices.json")
DEFAULT_PRICE_MAP = {
    # Base USDC (bridge + native)
    "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913": 1.0,
    "0xd9aaec86b65d86f6a7b5b1b0c42ffa531710b6ca": 1.0,
}
_UNPRICED_TOKENS: set[str] = set()


def _timestamped_csv_path(prefix: str = "pools", suffix: str = ".csv") -> Path:
    """
    Build a timestamped CSV path (UTC) and avoid collisions by appending a counter.
    """
    ts = datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
    base = Path(f"{prefix}_{ts}{suffix}")
    path = base
    counter = 1
    while path.exists():
        path = base.with_name(f"{base.stem}_{counter}{base.suffix}")
        counter += 1
    return path


@dataclass
class PoolRow:
    address: str
    name: str
    token0: str
    token1: str
    gauge: str
    emissions_token: str
    emissions_decimals: int
    token0_decimals: int
    token1_decimals: int
    token0_fees_raw: int
    token1_fees_raw: int
    token0_fees: float  # token amount (scaled by token0 decimals)
    token1_fees: float  # token amount (scaled by token1 decimals)
    fees_raw: int  # sum of token0_fees + token1_fees from sugar all()
    tvv_raw: int  # legacy field; mirrors emissions_raw for compatibility
    votes_raw: int  # use locked field as proxy for votes
    votes: float
    ratio: float
    tfv: float  # total fees value in USD
    tbv: float  # total bribes value in USD
    tvv: float  # total rewards value in USD (fees + bribes)
    votes_per_tvv: float  # ratio of votes to TVV (efficiency metric)
    rewards_epoch_ts: int
    emissions_raw: int  # emissions from LP sugar all()


def _web3() -> Web3:
    """
    Shared Web3 provider to avoid reconnecting for each contract call.
    """
    global _WEB3
    if _WEB3 is None:
        _WEB3 = Web3(Web3.HTTPProvider(RPC_URL))
        if not _WEB3.is_connected():
            raise RuntimeError("Unable to connect to RPC endpoint")
    return _WEB3


def _normalize_pool(struct) -> dict:
    pool = struct if isinstance(struct, dict) else {key: struct[idx] for idx, key in enumerate(STRUCT_KEYS)}
    # Standardize address casing for consistent lookups and encoding.
    for key in ("lp", "gauge", "emissions_token", "token0", "token1"):
        try:
            pool[key] = Web3.to_checksum_address(pool[key])
        except Exception:
            # Leave as-is if it cannot be checksummed (unlikely for valid addresses).
            pass
    return pool


def _abi_type(entry: dict) -> str:
    """
    Convert an ABI entry with potential tuple components into a canonical type string.
    """
    typ = entry.get("type", "")
    if not typ.startswith("tuple"):
        return typ

    suffix = typ[len("tuple") :]  # includes [] if present
    components = entry.get("components", [])
    inner = ",".join(_abi_type(c) for c in components)
    return f"({inner}){suffix}"


def _decode_int256(hex_str: str) -> int:
    val = int(hex_str, 16)
    if val >= 2**255:
        val -= 2**256
    return val


@functools.lru_cache(maxsize=4096)
def _token_decimals(address: str) -> int:
    """
    Resolve ERC20 decimals; default to 18 if the call fails or for pseudo-native addresses.
    """
    if not address or str(address).lower() == ZERO_ADDR:
        return 18
    if str(address).lower() == "0x4200000000000000000000000000000000000006":
        return 18
    try:
        erc20 = _web3().eth.contract(
            address=Web3.to_checksum_address(address),
            abi=[{"name": "decimals", "inputs": [], "outputs": [{"type": "uint8"}], "stateMutability": "view", "type": "function"}],
        )
        return int(erc20.functions.decimals().call())
    except Exception:
        return 18


def _rpc_batch(payload: list) -> list:
    resp = requests.post(RPC_URL, json=payload, headers={"Content-Type": "application/json"})
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict) and "error" in data:
        raise RuntimeError(data["error"])
    return data


def _fetch_weights(addresses: List[str], voter_address: str, chunk_size: int = 120) -> dict:
    """
    Batch-fetch weights from the voter contract to avoid serial RPC calls.
    """
    weights = {}
    voter = _voter()
    for start in range(0, len(addresses), chunk_size):
        batch = addresses[start : start + chunk_size]
        id_map = {}
        payload = []
        for idx, addr in enumerate(batch):
            call_id = start + idx
            id_map[call_id] = addr
            data = voter.functions.weights(addr)._encode_transaction_data()
            payload.append(
                {"jsonrpc": "2.0", "id": call_id, "method": "eth_call", "params": [{"to": voter_address, "data": data}, "latest"]}
            )
        responses = _rpc_batch(payload)
        for item in responses:
            if "result" not in item:
                continue
            addr = id_map[item["id"]]
            weights[addr] = _decode_int256(item["result"])
    return weights


def _contract():
    """
    Lazy-load the sugar contract so Web3 handles ABI decoding for us.
    """
    global _SUGAR_CONTRACT
    if _SUGAR_CONTRACT is not None:
        return _SUGAR_CONTRACT

    with open(ABI_PATH, "r") as f:
        abi = json.load(f)

    web3 = _web3()

    _SUGAR_CONTRACT = web3.eth.contract(address=Web3.to_checksum_address(SUGAR), abi=abi)
    return _SUGAR_CONTRACT


def _rewards_contract():
    """
    Minimal rewards sugar contract used for epochsByAddress.
    """
    global _REWARDS_CONTRACT
    if _REWARDS_CONTRACT is not None:
        return _REWARDS_CONTRACT

    _REWARDS_CONTRACT = _web3().eth.contract(address=Web3.to_checksum_address(REWARDS_SUGAR), abi=REWARDS_ABI)
    return _REWARDS_CONTRACT


def _voter():
    """
    Minimal voter contract used solely to read gauge weights (votes).
    """
    global _VOTER_CONTRACT
    if _VOTER_CONTRACT is not None:
        return _VOTER_CONTRACT

    voter_addr = _contract().functions.voter().call()
    _VOTER_CONTRACT = _web3().eth.contract(address=Web3.to_checksum_address(voter_addr), abi=VOTER_ABI)
    return _VOTER_CONTRACT


def get_pool_count() -> int:
    return _contract().functions.count().call()


def fetch_chunk(limit: int, offset: int) -> List[dict]:
    # filter = 0 => no filter on pools
    return _contract().functions.all(limit, offset, 0).call()


def _load_price_map(path: Path = PRICE_MAP_PATH) -> dict:
    """
    Load token -> usd price mapping. Uses defaults for stables and allows a local
    token_prices.json override (keys are addresses, values are USD floats).
    """
    price_map = {addr.lower(): float(price) for addr, price in DEFAULT_PRICE_MAP.items()}
    if path.exists():
        try:
            with open(path, "r") as f:
                user_map = json.load(f)
            price_map.update({addr.lower(): float(price) for addr, price in user_map.items()})
        except Exception as exc:
            print(f"Warning: failed to read {path}: {exc}")
    return price_map


def _usd_amount(token: str, amount: int, price_map: dict) -> float:
    price = price_map.get(str(token).lower())
    if price is None:
        _UNPRICED_TOKENS.add(str(token).lower())
        return 0.0
    decimals = _token_decimals(token)
    return (amount / (10**decimals)) * price


def _normalize_reward_entry(entry) -> dict:
    keys = ["ts", "lp", "votes", "emissions", "bribes", "fees"]
    data = entry if isinstance(entry, dict) else {key: entry[idx] for idx, key in enumerate(keys)}
    data["ts"] = int(data.get("ts", 0))
    data["votes"] = int(data.get("votes", 0))
    data["emissions"] = int(data.get("emissions", 0))
    data["lp"] = data.get("lp")
    data["bribes"] = [{"token": b[0], "amount": int(b[1])} for b in data.get("bribes", [])]
    data["fees"] = [{"token": f[0], "amount": int(f[1])} for f in data.get("fees", [])]
    return data


def _fetch_rewards_map(addresses: List[str], limit: int = 1, offset: int = 0, chunk_size: int = 100) -> dict:
    """
    Batch-fetch rewards (fees + bribes) for each pool.
    """
    rewards = {}
    if not addresses:
        return rewards

    contract = _rewards_contract()
    fn = contract.get_function_by_name("epochsByAddress")
    output_types = [_abi_type(o) for o in fn.abi["outputs"]]
    for start in range(0, len(addresses), chunk_size):
        batch = addresses[start : start + chunk_size]
        payload = []
        id_map = {}
        for idx, addr in enumerate(batch):
            call_id = start + idx
            call_data = fn(limit, offset, addr)._encode_transaction_data()
            payload.append({"jsonrpc": "2.0", "id": call_id, "method": "eth_call", "params": [{"to": contract.address, "data": call_data}, "latest"]})
            id_map[call_id] = addr

        responses = _rpc_batch(payload)
        for item in responses:
            if "result" not in item:
                continue
            addr = id_map.get(item["id"])
            try:
                # Manually decode outputs (web3 <6 lacks decode_function_output).
                decoded = _web3().codec.decode(output_types, bytes.fromhex(item["result"][2:]))
            except Exception as exc:
                print(f"Failed decoding rewards for {addr}: {exc}")
                continue
            epochs = decoded[0] if decoded else []
            rewards[addr] = [_normalize_reward_entry(e) for e in epochs]
    return rewards


def parse_pool(struct, votes_raw: int = 0, reward: dict | None = None, price_map: dict | None = None) -> PoolRow:
    if isinstance(struct, dict):
        pool = struct
    else:
        pool = {key: struct[idx] for idx, key in enumerate(STRUCT_KEYS)}

    lp = pool["lp"]
    symbol = pool["symbol"]
    if not symbol or not str(symbol).strip() or not str(symbol).isprintable():
        symbol = lp  # fallback when sugar returns empty symbol
    decimals = int(pool["decimals"])
    token0 = pool["token0"]
    token1 = pool["token1"]
    gauge = pool["gauge"]
    emissions_token = pool["emissions_token"]
    token0_decimals = _token_decimals(token0)
    token1_decimals = _token_decimals(token1)
    token0_fees_raw = int(pool.get("token0_fees", 0))
    token1_fees_raw = int(pool.get("token1_fees", 0))
    fees_raw = token0_fees_raw + token1_fees_raw
    votes_raw = int(votes_raw)
    emissions_raw = int(pool["emissions"])
    reward = reward or {}
    price_map = price_map or {}
    fees = reward.get("fees", [])
    bribes = reward.get("bribes", [])
    tfv = sum(_usd_amount(item["token"], int(item["amount"]), price_map) for item in fees)
    tbv = sum(_usd_amount(item["token"], int(item["amount"]), price_map) for item in bribes)
    tvv = tfv + tbv
    ratio = (tvv / votes_raw) if votes_raw else math.nan
    votes_per_tvv = (votes_raw / 1e18) / tvv if tvv > 0 else math.nan
    return PoolRow(
        address=lp,
        name=symbol,
        token0=token0,
        token1=token1,
        gauge=gauge,
        emissions_token=emissions_token,
        emissions_decimals=decimals,
        token0_decimals=token0_decimals,
        token1_decimals=token1_decimals,
        token0_fees_raw=token0_fees_raw,
        token1_fees_raw=token1_fees_raw,
        token0_fees=token0_fees_raw / (10**token0_decimals) if token0_decimals else math.nan,
        token1_fees=token1_fees_raw / (10**token1_decimals) if token1_decimals else math.nan,
        fees_raw=fees_raw,
        tvv_raw=emissions_raw,
        votes_raw=votes_raw,
        votes=votes_raw / 1e18,
        ratio=ratio,
        tfv=tfv,
        tbv=tbv,
        tvv=tvv,
        votes_per_tvv=votes_per_tvv,
        rewards_epoch_ts=int(reward.get("ts", 0)) if reward else 0,
        emissions_raw=emissions_raw,
    )


def iter_pools(batch_size: int = 187, price_map: dict | None = None) -> Iterable[PoolRow]:
    total = get_pool_count()
    voter = _voter()
    print(f"Discovered {total} pools")

    pools = []
    for offset in range(0, total, batch_size):
        limit = min(batch_size, total - offset)
        print(f"Fetching pools {offset}..{offset+limit-1}")
        pools.extend(_normalize_pool(struct) for struct in fetch_chunk(limit, offset))

    # Collect tokens and fetch missing prices
    if price_map is not None:
        all_tokens = set()
        for p in pools:
            if p.get("token0"): all_tokens.add(str(p["token0"]).lower())
            if p.get("token1"): all_tokens.add(str(p["token1"]).lower())
            if p.get("emissions_token"): all_tokens.add(str(p["emissions_token"]).lower())
        
        # We also need to check reward tokens, but we haven't fetched rewards yet.
        # We can do a two-pass or just fetch for pool tokens first.
        # Reward tokens (bribes/fees) might be different.
        # But let's start with pool tokens.
        
        missing = {t for t in all_tokens if t not in price_map}
        if missing:
            print(f"Fetching prices for {len(missing)} missing tokens...")
            try:
                new_prices = fetch_prices(missing)
                update_price_map(new_prices)
                price_map.update(new_prices)
            except Exception as e:
                print(f"Failed to auto-fetch prices: {e}")

    print("Fetching voter weights in batches")
    weight_map = _fetch_weights([p["lp"] for p in pools], voter.address)
    print("Fetching rewards (fees + bribes) in batches")
    reward_map = _fetch_rewards_map([p["lp"] for p in pools], limit=1, offset=0)

    kept = 0
    for pool_dict in pools:
        votes_raw = int(weight_map.get(pool_dict["lp"], 0))
        if votes_raw <= 0:
            continue

        name = pool_dict["symbol"]
        gauge = pool_dict["gauge"]
        emissions_token = pool_dict["emissions_token"]
        token0 = pool_dict["token0"]
        token1 = pool_dict["token1"]

        bad_token0 = str(token0).lower() == ZERO_ADDR
        bad_token1 = str(token1).lower() == ZERO_ADDR
        # Also drop known garbage token patterns (uint max, or obviously non-address padding).
        junk_tokens = {
            "0xffffffffffffffffffffffffffffffffffffffff",
            "0x000000000000000000000000016345785d8a0000",
            "0x00000000000000000000000000000000000003e8",
        }
        if (
            bad_token0
            or bad_token1
            or str(token0).lower() in junk_tokens
            or str(token1).lower() in junk_tokens
        ):
            continue

        reward_entries = reward_map.get(pool_dict["lp"], [])
        reward = reward_entries[0] if reward_entries else None
        pool = parse_pool(pool_dict, votes_raw=votes_raw, reward=reward, price_map=price_map)
        kept += 1
        yield pool
    print(f"Kept {kept} pools with >0 votes")


def write_csv(rows: Iterable[PoolRow], path: str = "pools.csv") -> None:
    fieldnames = [
        "name",
        "vote_pct",
        "address",
        "gauge",
        "token0",
        "token1",
        "emissions_token",
        "emissions_decimals",
        "token0_decimals",
        "token1_decimals",
        "token0_fees_raw",
        "token1_fees_raw",
        "token0_fees",
        "token1_fees",
        "fees_raw",
        "emissions_raw",
        "votes_raw",
        "votes",
        "ratio",
        "tfv",
        "tbv",
        "tvv",
        "votes_per_tvv",
        "rewards_epoch_ts",
    ]
    rows = [r for r in rows]
    total_votes = sum(r.votes_raw for r in rows)
    total_token0_fees = sum(r.token0_fees_raw for r in rows)
    total_token1_fees = sum(r.token1_fees_raw for r in rows)
    total_fees = sum(r.fees_raw for r in rows)
    total_emissions = sum(r.emissions_raw for r in rows)
    total_tfv = sum(r.tfv for r in rows)
    total_tbv = sum(r.tbv for r in rows)
    total_tvv = sum(r.tvv for r in rows)
    total_token0_fees_norm = sum(r.token0_fees for r in rows if not math.isnan(r.token0_fees))
    total_token1_fees_norm = sum(r.token1_fees for r in rows if not math.isnan(r.token1_fees))

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
            quoting=csv.QUOTE_MINIMAL,
            escapechar="\\",
        )
        writer.writeheader()
        for r in rows:
            vote_pct = (r.votes_raw / total_votes * 100) if total_votes else math.nan
            writer.writerow(
                {
                    "name": r.name,
                    "vote_pct": vote_pct,
                    "address": r.address,
                    "gauge": r.gauge,
                    "token0": r.token0,
                    "token1": r.token1,
                    "emissions_token": r.emissions_token,
                    "emissions_decimals": r.emissions_decimals,
                    "token0_decimals": r.token0_decimals,
                    "token1_decimals": r.token1_decimals,
                    "token0_fees_raw": r.token0_fees_raw,
                    "token1_fees_raw": r.token1_fees_raw,
                    "token0_fees": r.token0_fees,
                    "token1_fees": r.token1_fees,
                    "fees_raw": r.fees_raw,
                    "emissions_raw": r.emissions_raw,
                    "votes_raw": r.votes_raw,
                    "votes": r.votes,
                    "ratio": r.ratio,
                    "tfv": r.tfv,
                    "tbv": r.tbv,
                    "tvv": r.tvv,
                    "votes_per_tvv": r.votes_per_tvv,
                    "rewards_epoch_ts": r.rewards_epoch_ts,
                }
            )
        # Summary row with totals and 100% vote share.
        summary_ratio = (total_tvv / total_votes) if total_votes else math.nan
        if rows:
            writer.writerow(
                {
                    "name": "TOTAL",
                    "vote_pct": 100.0,
                    "address": "",
                    "gauge": "",
                    "token0": "",
                    "token1": "",
                    "emissions_token": "",
                    "emissions_decimals": "",
                    "token0_decimals": "",
                    "token1_decimals": "",
                    "token0_fees_raw": total_token0_fees,
                    "token1_fees_raw": total_token1_fees,
                    "token0_fees": total_token0_fees_norm,
                    "token1_fees": total_token1_fees_norm,
                    "fees_raw": total_fees,
                    "emissions_raw": total_emissions,
                    "votes_raw": total_votes,
                    "ratio": summary_ratio,
                    "tfv": total_tfv,
                    "tbv": total_tbv,
                    "tvv": total_tvv,
                    "votes_per_tvv": (total_votes / 1e18) / total_tvv if total_tvv > 0 else math.nan,
                }
            )
    print(f"Wrote {len(rows)} pools to {path}")
    print(f"Total token0_fees_raw: {total_token0_fees}")
    print(f"Total token1_fees_raw: {total_token1_fees}")
    print(f"Total token0_fees (normalized): {total_token0_fees_norm}")
    print(f"Total token1_fees (normalized): {total_token1_fees_norm}")
    print(f"Total fees_raw: {total_fees}")
    print(f"Total emissions_raw: {total_emissions}")
    print(f"Total tfv (USD): {total_tfv}")
    print(f"Total tbv (USD): {total_tbv}")
    print(f"Total tvv (USD): {total_tvv}")
    print(f"Total votes_raw: {total_votes}")
    if _UNPRICED_TOKENS:
        tokens = ", ".join(sorted(_UNPRICED_TOKENS))
        print(f"Tokens missing prices (treated as $0): {tokens}")


if __name__ == "__main__":
    price_map = _load_price_map()
    snapshot_path = _timestamped_csv_path()
    write_csv(iter_pools(price_map=price_map), path=snapshot_path)

    # Keep a rolling "latest" copy for downstream scripts while preserving dated snapshots.
    shutil.copy(snapshot_path, "pools.csv")
    print(f"Copied latest snapshot to pools.csv (source: {snapshot_path.name})")

    try:
        from generate_pools_html import generate_html

        generate_html(source_csv=snapshot_path)
    except Exception as exc:
        print(f"Warning: failed to generate pools.html: {exc}")
