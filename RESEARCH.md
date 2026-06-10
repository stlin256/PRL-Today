# PRL Research Notes

Date: 2026-06-10

## Sources checked

- AlphaPool miner page: `https://pearl.alphapool.tech/#miner/prl1p2ka5l06wmq73kdsqec9k7fsv00jt76nfhk56e9nh82fn07qjualspfsxyp`
- AlphaPool JSON: `https://pearl.alphapool.tech/api/stats`
- AlphaPool miner JSON: `https://pearl.alphapool.tech/api/miner/<wallet>`
- PRL market JSON: `https://api.prlscan.com/v1/market/prl`
- PRL chain summary JSON: `https://api.prlscan.com/v1/analytics/summary`
- Hashrate.no PRL page: `https://hashrate.no/coins/PRL/`
- SafeTrade page: `https://safetrade.com/exchange/PRL-USDT?type=basic`

## Findings

- Coin: Pearl (PRL)
- Algorithm shown by Hashrate.no: `pearl-pow`
- AlphaPool mode: PPLNS
- AlphaPool fee: 3%
- AlphaPool minimum payout: 1 PRL
- AlphaPool payout cycle: every 4 hours
- AlphaPool default stratum host/port observed in API: `us2.alphapool.tech:5566`
- AlphaPool solo port observed in API: `5567`; page notes solo mining was being reintegrated.
- AlphaPool page says PPLNS uses time-weighted shares with a 65 minute half-life.
- SafeTrade web page was Cloudflare-blocked from the current network. AlphaPool's page script uses PRLScan market API, and PRLScan reports a SafeTrade PRL/USDT provider sourced through CoinPaprika, so this app uses PRLScan as the default price API.

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
