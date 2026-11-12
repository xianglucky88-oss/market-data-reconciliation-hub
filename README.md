# Market Data Reconciliation Hub

一个面向金融市场数据工程的本地可运行样例：接收多个供应商的行情和公司行为事件，进行规范化、幂等去重、时态快照和交叉供应商对账，并将拒绝记录保留下来供后续修复。

## 数据链路

`fixture/API records -> normalization -> quality gate -> idempotent event store -> point-in-time reconciliation -> SQLite serving tables`

核心能力：供应商优先级、事件时间与处理时间、价格差异对账、版本化事件、拒绝原因和可重跑导入。

## 运行

```bash
PYTHONPATH=src python3 -m market_data_reconciliation.cli \
  --fixture fixtures/sample.json \
  --database /tmp/market-data-reconciliation-hub.sqlite3
```

## 外部依赖类型与版本

- Python 3.11+
- SQLite 3.x
- pytest 8.3.x（测试）

不需要账号、真实连接串、token 或密钥；生产数据源可以通过环境变量接入。

## 验证

```bash
PYTHONPATH=src python3 -m pytest --import-mode=importlib tests
PYTHONPATH=src python3 -m compileall -q src
```
