
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
            # Also check for reward tokens if we had them in CSV, but we don't yet fully.
            # We can add known ones.
    return tokens

def fetch_prices(tokens):
    if not tokens:
        return {}
    
    # Chunk tokens to avoid URL length limits
    chunk_size = 30 # DefiLlama might handle more, but safe side
    tokens_list = list(tokens)
    prices = {}
    
    for i in range(0, len(tokens_list), chunk_size):
        chunk = tokens_list[i:i+chunk_size]
        query = ",".join([f"base:{t}" for t in chunk])
        url = f"{API_URL}{query}"
        
        try:
            print(f"Fetching chunk {i}...")
            resp = requests.get(url)
            resp.raise_for_status()
            data = resp.json()
            coins = data.get("coins", {})
            for key, info in coins.items():
                # key is like "base:0x..."
                addr = key.split(":")[1].lower()
                prices[addr] = info.get("price", 0)
        except Exception as e:
            print(f"Error fetching chunk {i}: {e}")
        
        time.sleep(0.5) # Rate limit nice
        
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
