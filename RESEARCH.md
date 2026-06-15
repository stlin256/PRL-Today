# PRL Research Notes

Date: 2026-06-10

Latest fee preset check: 2026-06-15

## Sources checked

- AlphaPool miner page: `https://pearl.alphapool.tech/#miner/prl1p2ka5l06wmq73kdsqec9k7fsv00jt76nfhk56e9nh82fn07qjualspfsxyp`
- AlphaPool JSON: `https://pearl.alphapool.tech/api/stats`
- AlphaPool miner JSON: `https://pearl.alphapool.tech/api/miner/<wallet>`
- PRL market JSON: `https://api.prlscan.com/v1/market/prl`
- PRL chain summary JSON: `https://api.prlscan.com/v1/analytics/summary`
- Hashrate.no PRL page: `https://hashrate.no/coins/PRL/`
- SafeTrade page: `https://safetrade.com/exchange/PRL-USDT?type=basic`
- Official pool pages rechecked on 2026-06-15: `https://pearl.alphapool.tech/`, `https://pool.kryptex.com/prl`, `https://pearlhash.xyz/`, `https://pearl.luckypool.io/`, `https://pearl.jetskipool.ai/info`, `https://baikalmine.com/pools/pplns/pearl/dashboard`, `https://akoyapool.com/`, `https://himpool.com/pools/prl`, `https://nushypool.com/prl/pool`, `https://nushypool.com/prl_solo/pool`, `https://mineprl.com/`, and `https://pearl.herominers.com/`.
- Official miner/tool pages rechecked on 2026-06-15: `https://github.com/AlphaMine-Tech/alpha-miner/releases`, `https://miner.download/en/lpminer`, `https://github.com/bzminer/bzminer/releases/tag/v25.0.0b2`, and `https://github.com/doktor83/SRBMiner-Multi/blob/master/Readme`.

## Findings

- Coin: Pearl (PRL)
- Algorithm shown by Hashrate.no: `pearl-pow`
- AlphaPool mode: PPLNS
- AlphaPool fee: 0% on the official frontend. Its `/api/stats` endpoint still reports `feePercent: 3`, so the app pins the official displayed fee and ignores that API fee field for AlphaPool.
- AlphaPool minimum payout: 1 PRL
- AlphaPool payout cycle: every 4 hours
- AlphaPool default stratum host/port observed in API: `us2.alphapool.tech:5566`
- AlphaPool solo port observed in API: `5567`; page notes solo mining was being reintegrated.
- AlphaPool page says PPLNS uses time-weighted shares with a 65 minute half-life.
- SafeTrade is the default PRL/USD source in the app. PRLScan remains available as a fallback source.

## Fee preset check on 2026-06-15

- Hashrate.no is no longer treated as the source of truth for bundled fee presets; each bundled pool and mining tool was rechecked against its official website, release page, or official README.
- Current bundled pool fees from official sources: AlphaPool PPLNS 0.00%, Kryptex PROP 1.00%, Pearlhash PPLNS 0.00%, Luckypool PPLNS 1.00%, JETSKI PROP 1.00%, BaikalMine PPLNS 0.50%, akoya PPLNS-N 2.00%, Himpool SOLO 2.00%, Himpool PPLNS 1.00%, NushyPool FPPS 1.00%, NushyPool SOLO 1.00%, Mineprl PPLNS 4.40%, HeroMiners PROP 0.00% until 2026-08-01.
- AlphaPool official frontend shows Pool Fee `0%` and `PPLNS - 0% fee`, while the official JSON endpoint still reports `feePercent: 3`; the calculation uses the official frontend fee for AlphaPool.
- Pearlhash official homepage now says `0% miner fee 0% pool fee`, so the bundled Pearlhash pool fee is 0.00%.
- NushyPool's official PRL page now labels the pooled mode as `1.0% FPPS`, so the preset payout scheme is FPPS rather than PPS.
- Official miner/tool fees: AlphaMiner 0.00%, lpminer 0.00%, BzMiner Pearl beta 2.00%, SRBMiner `pearlhash` 3.00%.

Observed live values during research:

- AlphaPool `/api/stats`: feePercent `3`, reward about `2625.605 PRL`, minimum payout `1 PRL`.
- AlphaPool miner API for the configured wallet: mode `PPLNS`, 1h hashrate about `130.57 TH/s`, 24h hashrate about `137.53 TH/s`, workers `b85-miner`, `rog-g14`, `ubuntu-v100`, `win-5060ti`.
- PRLScan market API: PRL/USD about `0.5201`; provider list included SafeTrade PRL/USDT around `0.4996786559`.
- PRLScan chain summary: average block time about `228.08s`, estimated network hashrate about `20.799 EH/s`.
- USD/CNY from `open.er-api.com`: about `6.785295`.

## Calculation notes

The pool's own page warns that pool `/api/stats` network hash can be on a different scale than card TH/s values. The app therefore prefers PRLScan `estimated_hashrate_hps` for the denominator. If unavailable, it falls back to the pool `network_hash` string.

For the displayed moving value, the app combines:

- actual today payments or pending shares from the miner API;
- estimated 24 hour PRL based on fitted hashrate and chain data;
- a cubic smoothing function so the six decimal display moves continuously between API refreshes.
