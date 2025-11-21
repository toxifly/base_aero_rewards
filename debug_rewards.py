
from web3 import Web3
import json

RPC_URL = "https://lb.drpc.live/base/Avibgvi26EjPsw76UtdwmsS6VEL-8F4R75KJIhIl_7lF"
REWARDS_SUGAR = "0xD4aD2EeeB3314d54212A92f4cBBE684195dEfe3E"
# Use a known active pool (e.g., vAMM-WETH/USDC or similar)
# From pools.csv, I'll pick one.
POOL_ADDRESS = "0xcDAC0d6c6C59727a65F871236188350531885C43" # vAMM-WETH/USDC

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

def debug():
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    contract = w3.eth.contract(address=REWARDS_SUGAR, abi=REWARDS_ABI)
    
    # Test 1: limit=1
    print("Testing limit=1...")
    try:
        res = contract.functions.epochsByAddress(1, 0, POOL_ADDRESS).call()
        print(f"Result (limit=1): {res}")
        if res:
            print(f"Latest Epoch TS: {res[0][0]}")
    except Exception as e:
        print(f"Error (limit=1): {e}")

    # Test 2: limit=current_timestamp (simulate epoch ID if it's a timestamp)
    # Epochs are usually timestamps (start of week).
    # Current time is ~1732166400 (Nov 2025? No, user said 2025-11-21)
    # 2025-11-21 is Friday. Epochs usually start Thursday 00:00 UTC.
    # Previous Thursday: Nov 20.
    # 1732147200 (approx)
    
    ts = 1732147200 # Example timestamp
    print(f"Testing limit={ts} (timestamp)...")
    try:
        res = contract.functions.epochsByAddress(ts, 0, POOL_ADDRESS).call()
        print(f"Result (limit={ts}): {res}")
    except Exception as e:
        print(f"Error (limit={ts}): {e}")

if __name__ == "__main__":
    debug()
