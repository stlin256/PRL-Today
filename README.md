# PRL-Today

Windows 桌面悬浮窗，用于查看 Pearl (PRL) 当天实时收益，显示美元和人民币数值，保留 6 位小数并按拟合/平滑函数持续滚动。

## 功能

- 默认监控钱包：`prl1p2ka5l06wmq73kdsqec9k7fsv00jt76nfhk56e9nh82fn07qjualspfsxyp`
- 默认矿池：AlphaPool PRL，自动从 `https://pearl.alphapool.tech/api/stats` 读取 PPLNS 手续费、出块奖励、最低支付和 stratum 信息。
- 默认价格：`https://api.prlscan.com/v1/market/prl`，该接口包含 SafeTrade PRL/USDT provider 数据。
- 价格源可选：PRLScan、SafeTrade、SafeTrade mirror；SafeTrade 优先读取 `https://safetrade.com/api/v2/trade/public/tickers/prlusdt`，并保留 `https://safetrade.com/exchange/PRL-USDT?type=basic` 页面解析兜底，都会走代理配置。
- 默认汇率：`https://open.er-api.com/v6/latest/USD` 的 USD/CNY。
- 默认代理：`http://127.0.0.1:7897`，也会写入 `HTTP_PROXY` 和 `HTTPS_PROXY`。
- 设置页仓库链接：`https://github.com/stlin256/prl-today`。
- Qt 悬浮窗风格参考 `minimax_moniter`：无边框置顶、半透明容器、悬停显示设置/关闭、同窗配置页、托盘菜单、拖拽和右下角缩放。
- Qt 绑定优先尝试 PyQt6，当前机器的 PyQt6 `QtWidgets` DLL 加载失败时会自动回退到 Anaconda 已可用的 PyQt5。
- 配置页支持改钱包、矿池、代理、矿池手续费、挖矿工具抽水、手动价格、手动汇率、刷新间隔、算力模式、显示层级和默认货币。
- 内置 hashrate.no PRL 预置：AlphaPool、Kryptex、Pearlhash、Luckypool 等矿池，以及 AlphaMiner 1% 和 SRBMiner 3% 挖矿软件抽水。
- 默认货币为 `auto`：系统语言为中文时主数字显示 CNY，其他语言显示 USD。

## 刷新频率

- 主收益数字：每 1 秒用平滑函数滚动一次。
- 钱包矿工数据：每 30 秒刷新。
- 矿池统计：每 30 秒刷新。
- PRL/USD 市场价格：每 30 秒刷新。
- 链摘要/全网算力：每 60 秒刷新。
- USD/CNY 汇率：每 3600 秒刷新。

显示层级：

- `lite`：只显示 CNY、USD、PRL 和当天进度条。
- `standard`：增加矿工算力、价格和矿池费率。
- `detail`：增加 24h 预计、全网算力、区块参数、各数据源刷新频率和最后更新时间。

## 运行

```powershell
cd F:\PROJECT\PRL-Today
py run.py
```

也可以双击：

```text
start_prl_today.bat
```

首次运行会从 `config.example.json` 生成 `config.json`。之后设置窗口保存的内容都写入 `config.json`，该文件默认不进 Git。

不打开悬浮窗，只检查实时接口和收益计算：

```powershell
py run.py --check
```

## 收益口径

悬浮窗主数字是“今天到当前时刻”的估算收益：

```text
预计 24h PRL = 矿工算力 / 全网算力 * (86400 / 平均出块秒数) * 当前区块奖励 * (1 - 矿池费率) * (1 - 挖矿工具抽水)
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

## 打包

本机已使用 Anaconda Python + PyInstaller 打包。重新打包可执行：

```powershell
python -m PyInstaller --noconfirm --clean --windowed --name PRL-Today --paths src --hidden-import prl_profit_float.qt_app --hidden-import PyQt5.QtWidgets --exclude-module PyQt6 --add-data "config.example.json;." --add-data "assets/prl_logo.svg;assets" run.py
```
