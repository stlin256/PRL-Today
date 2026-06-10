# PRL Profit Float

Windows 桌面悬浮窗，用于查看 Pearl (PRL) 当天实时收益，显示美元和人民币数值，保留 6 位小数并按拟合/平滑函数持续滚动。

## 功能

- 默认监控钱包：`prl1p2ka5l06wmq73kdsqec9k7fsv00jt76nfhk56e9nh82fn07qjualspfsxyp`
- 默认矿池：AlphaPool PRL，自动从 `https://pearl.alphapool.tech/api/stats` 读取 PPLNS 手续费、出块奖励、最低支付和 stratum 信息。
- 默认价格：`https://api.prlscan.com/v1/market/prl`，该接口包含 SafeTrade PRL/USDT provider 数据。
- 默认汇率：`https://open.er-api.com/v6/latest/USD` 的 USD/CNY。
- 默认代理：`http://127.0.0.1:7897`，也会写入 `HTTP_PROXY` 和 `HTTPS_PROXY`。
- 设置窗口支持改钱包、矿池、代理、手续费、手动价格、手动汇率、刷新间隔和算力模式。

## 运行

```powershell
cd F:\PROJECT\prl-profit-float
py run.py
```

也可以双击：

```text
start_prl_profit_float.bat
```

首次运行会从 `config.example.json` 生成 `config.json`。之后设置窗口保存的内容都写入 `config.json`，该文件默认不进 Git。

不打开悬浮窗，只检查实时接口和收益计算：

```powershell
py run.py --check
```

## 收益口径

悬浮窗主数字是“今天到当前时刻”的估算收益：

```text
预计 24h PRL = 矿工算力 / 全网算力 * (86400 / 平均出块秒数) * 当前区块奖励 * (1 - 矿池费率)
当天当前 PRL = max(今天已入账/待结算 PRL, 预计 24h PRL * 今天已过秒数 / 86400)
USD = PRL * PRL/USD
RMB = USD * USD/CNY
```

算力模式默认是 `fit`：用矿工最近 hashrate series 做线性拟合并限制极端值，再估算收益。你也可以在设置里切换为 `miner_1h`、`miner_24h` 或 `worker_live`。

## 调试

```powershell
py -m unittest discover -s tests
py -m compileall src tests
```
