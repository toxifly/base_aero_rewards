## Context
- Repo path: `/home/adrd/skrypty/temp/base_aero_rewards`
- Goal: Build `pools.csv` with vote totals and rewards/vote ratio for Aerodrome pools.
- Data source: LP sugar contract on Base: `0x9DE6Eab7a910A288dE83a04b6A43B52Fd1246f1E` (ABI now present in `sugar_abi.abi`).

## Current State
- `main.py` pulls pools with web3 using the sugar ABI and now writes token-level fees (`token0_fees_raw`, `token1_fees_raw`) from sugar `all()`. Votes are from the voter contract's `weights`, rewards proxy is `emissions`.
- CSV columns include: name, vote_pct, address, gauge, token0/1, emissions_token, emissions_decimals, token0/1 fee raws, fees_raw, tvv_raw, votes_raw, votes, ratio.
#"]]***

## Pending Work
1. Align fees/rewards with the UI:
   - The site uses a rewards sugar `epochsByAddress` call (not `token{0,1}_fees` from sugar `all()`).
   - Fetch `fees` and `bribes` per pool for the current epoch and price them to USD to produce tfv/tbv/tvv like the UI.
2. Keep CSV generation but swap the rewards source to the data above; `emissions` can stay as emissions-only if needed.
3. Token prices: mirror the dApp’s token list with prices or provide an alternate price feed.

## Notes
- Sugar ABI file: `sugar_abi.abi`.
- RPC used: `https://lb.drpc.live/base/Avibgvi26EjPsw76UtdwmsS6VEL-8F4R75KJIhIl_7lF`.
- Contract functions seen: `all(limit, offset, filter)`, `forSwaps`, `tokens`, `positions*`, etc.
- When you fix decode, regenerate CSV via `python main.py`.
