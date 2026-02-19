
import concurrent.futures
import csv
import json
import requests
import time
from pathlib import Path

POOLS_CSV = "pools.csv"
PRICE_MAP_PATH = "token_prices.json"
# DefiLlama coins API
# https://coins.llama.fi/prices/current/base:0x...,base:0x...
API_URL = "https://coins.llama.fi/prices/current/"

def get_tokens_from_csv():
    tokens = set()
    if not Path(POOLS_CSV).exists():
        print(f"{POOLS_CSV} not found.")
        return tokens

    with open(POOLS_CSV, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("token0"): tokens.add(row["token0"].lower())
            if row.get("token1"): tokens.add(row["token1"].lower())
            if row.get("emissions_token"): tokens.add(row["emissions_token"].lower())
    return tokens


def _fetch_chunk(chunk, idx, total):
    """Fetch prices for a single chunk from DefiLlama."""
    query = ",".join([f"base:{t}" for t in chunk])
    url = f"{API_URL}{query}"
    prices = {}
    for attempt in range(3):
        try:
            resp = requests.get(url, timeout=(5, 15))
            resp.raise_for_status()
            data = resp.json()
            coins = data.get("coins", {})
            for key, info in coins.items():
                addr = key.split(":")[1].lower()
                prices[addr] = info.get("price", 0)
            return prices
        except Exception as e:
            if attempt == 2:
                print(f"Error fetching price chunk {idx}: {e}")
            else:
                time.sleep(1)
    return prices


def fetch_prices(tokens):
    if not tokens:
        return {}

    chunk_size = 80  # DefiLlama handles large batches well
    tokens_list = list(tokens)
    chunks = []
    for i in range(0, len(tokens_list), chunk_size):
        chunks.append(tokens_list[i:i + chunk_size])

    total = len(chunks)
    print(f"Fetching prices: {len(tokens_list)} tokens in {total} chunks (4 concurrent workers)")
    prices = {}
    done = [0]

    def worker(args):
        idx, chunk = args
        result = _fetch_chunk(chunk, idx, total)
        done[0] += 1
        if done[0] % 20 == 0 or done[0] == total:
            print(f"  Prices: {done[0]}/{total} chunks", flush=True)
        return result

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        results = executor.map(worker, enumerate(chunks))
        for result in results:
            prices.update(result)

    return prices

def update_price_map(new_prices):
    current_map = {}
    if Path(PRICE_MAP_PATH).exists():
        try:
            with open(PRICE_MAP_PATH, "r") as f:
                current_map = json.load(f)
        except:
            pass
    
    # Update with new prices
    current_map.update(new_prices)
    
    # Ensure keys are lowercase
    final_map = {k.lower(): v for k, v in current_map.items()}
    
    with open(PRICE_MAP_PATH, "w") as f:
        json.dump(final_map, f, indent=2)
    
    print(f"Updated {PRICE_MAP_PATH} with {len(final_map)} prices.")

if __name__ == "__main__":
    tokens = get_tokens_from_csv()
    print(f"Found {len(tokens)} unique tokens in {POOLS_CSV}")
    
    # Add some known reward tokens that might not be in token0/1 of listed pools yet
    # WETH, AERO, USDC, USDbC are likely in pools.
    # But maybe some bribe tokens are not.
    # For now, just use what we have.
    
    prices = fetch_prices(tokens)
    update_price_map(prices)
