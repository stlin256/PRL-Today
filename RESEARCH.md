# PRL Research Notes

Date: 2026-06-10

Latest fee preset check: 2026-06-13

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
- SafeTrade is the default PRL/USD source in the app. PRLScan remains available as a fallback source.

## Fee preset check on 2026-06-13

- Hashrate.no PRL pools page was rechecked for pool fees, payout schemes, and pool share metadata.
- Current bundled pool fees: Kryptex 1.00%, Pearlhash 3.00%, Luckypool 1.00%, AlphaPool 3.00%, BaikalMine 0.50%, JETSKI 1.00%, akoya 2.00%, Himpool SOLO 2.00%, Mineprl 4.40%, Himpool PPLNS 1.00%, NushyPool PPS 1.00%, HeroMiners 0.00%, NushyPool SOLO 1.00%.
- Hashrate.no PRL miners page still lists AlphaMiner as 1.00%, but AlphaMiner's official latest GitHub release, v1.7.7, states the developer fee was removed and is now 0%.
- lpminer's public miner page lists Pearl at 0% fees.
- BzMiner's v25.0.0b2 beta release notes list Pearl with a 2% dev fee and CPU-only support for that beta.
- SRBMiner's official README lists `pearlhash` at 3.00%, matching Hashrate.no.
- The app now treats AlphaMiner official release metadata as the source of truth for AlphaMiner, adds lpminer and BzMiner presets, and keeps SRBMiner at 3.00%.

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
