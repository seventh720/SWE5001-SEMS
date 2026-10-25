# 性能、扩容与恢复实验

本指南定义如何测试当前三服务架构。生产运行方式见 [K3s 运维](k3s.md)，功能正确性与历史实测见[验收矩阵](acceptance-matrix.md)和[证据索引](evidence/README.md)。测试准备与计划不表示已取得性能成绩。

## 当前可以开展的测试

| 测试 | 条件与判定 |
| --- | --- |
| 手动副本调整 | 独立环境中执行 1→2，确认就绪、两个副本实际接流量及数据一致性 |
| 扩容收益 | 固定版本、数据、单副本资源及负载，比较 1/2 副本的成功吞吐、分操作 p95 和错误率 |
| 故障恢复 | 两个健康副本持续接流量时删除一个，核对失败区间、业务恢复及订单/库存 |
| 自动扩容 | 另行配置和验证指标触发、就绪、分流及缩容；当前未启用 HPA |
| 主机或数据库 HA | 需要明确故障域、复制/切换和外部验证；当前单控制平面与单 PostgreSQL 不具备这些条件 |

当前生产只有两个节点，应用使用同服务 hostname 硬反亲和，第三个同服务 Pod 无法调度。增加 replicas 不会自动增加 EC2。1→2 对照可以验证当前支持的水平扩容范围；生产副本为 2，不应把临时调为 1 当作无影响的操作。

## 测试环境与工具准备

优先使用独立的本地 Kubernetes 集群验证测试流程；云端性能结论需独立云端测试环境。使用同一批应用 digest、单独的数据库/账号/JWT 和测试入口。先记录节点 CPU/内存、Pod requests/limits、数据库连接池、网络、镜像及 source commit。

两台生产节点还承载控制平面和监控。测试前执行 `kubectl top nodes`、`kubectl top pods` 并检查 requests、磁盘和数据库连接余量；不能依据 CPU 空闲就再部署一套 JVM。新 EC2、节点池或其他收费资源需要单独规划。配置和造数不得覆盖正式数据。

| 工具 | 适用范围 |
| --- | --- |
| `scripts/performance/seed.py`、`load.js` | 通过 HTTP 造数和 k6 负载，可用于独立 Compose/Kubernetes 入口 |
| `compare.py` | 比较匹配的场景、数据集、版本、资源和负载结果 |
| `local-experiment.py` | 固定的独立 Compose 项目、端口和数据库快照；当前不控制 Kubernetes |
| `record.py`、`fault.py`、`audit.py` | 依赖 Compose/Docker 的采样、故障和 SQL 审计 |
| `cloud-capacity.py` / `cloud-guard.py` | 历史 Lightsail 环境的负载及主机保护；不能直接用于当前 K3s |
| `scripts/k8s/local-acceptance.py` | 独立 kind 的跨 Pod 正确性检查；不测量扩容收益 |
| `scripts/k8s/catalog-recovery.py` | 历史隔离 K3s 故障入口，保留生产保护；当前生产数据不可使用 |

在 K3s 跑完整对照前，需补齐或选择独立测试用的副本控制、逐 Pod readiness、资源采样、PostgreSQL 快照恢复/审计和失败清理适配。不要将旧工具的 namespace 替换成 `sems-prod` 来绕过保护。`load.js` 本身不要求 Docker 运行时，可由原生 k6 或专用负载机执行。

## 实验顺序

1. **预检与基线：**验证测试栈独立、备份可读、两个实例可接流量、日志/指标可采集。保存初始数据库快照和资源配置。
2. **短时验证：**先用 10 VU、30 秒预热、60 秒测量跑一组 1/2 副本，确认认证、分流、计时、恢复和库存审计链路可用。它用于检查工具与业务，不作正式容量结论。
3. **正式对照：**分别比较 Catalog 和 Admission 的 1/2 副本，运行 25、50、100 VU，每组预热 60 秒、测量 600 秒，至少三次交错重复。
4. **故障实验：**在两副本持续流量中删除一个副本，恢复后继续观察稳定业务窗口。全副本停止是另一项有界失败/恢复检查。
5. **清理与复核：**恢复测试副本、核对数据库、保存失败及成功结果，再清理本次专用数据和资源。

正式矩阵为 2 类场景 × 2 种副本数 × 3 档 VU × 3 次重复，共 36 轮；仅负载时间约 6.6 小时，造数、镜像启动和数据库恢复另计。可以先选择一档完成完整对照，但报告必须注明实际执行范围。

## 数据、场景和负载

使用测试环境管理员变量，数据集含凭据并保持私有：

```bash
mkdir -p .performance
python3 scripts/performance/seed.py --base-url https://your-benchmark-host \
  --users 50 --events 10 --quota 100000 --output .performance/dataset.json
```

上例用于较小的初始数据集。正式实验可固定为 1000 账号、100 活动；报告实际值，避免混用旧的 50 活动实验。JWT 为一小时，必要时使用同一 dataset 加 `--refresh`；每轮保持足够票额，避免容量不足被误当作系统性能下降。

- **Catalog 场景：**80% 按实验关键字分页检索，20% 活动详情。仅改变 Catalog 副本数，其他服务固定。
- **Admission 场景：**订票后读取回执，活动分布固定。仅改变 Admission 副本数，单独统计成功订单吞吐和 HTTP 请求吞吐。

同一数据库快照、镜像和单副本资源用于每组；交错测试顺序，并记录单副本所在节点，避免控制平面负载或数据库本地性影响结论。负载发生器尽量独立于被测服务；本机共享 Docker VM 的竞争要记入限制。

```bash
DATASET=.performance/dataset.json MODE=catalog VUS=25 \
  RUN_ID=catalog-1-repetition-1 COMMIT=full-tested-commit \
  REPLICAS=catalog1-admission1 WARMUP_SECONDS=60 DURATION_SECONDS=600 \
  SUMMARY_FILE=.performance/catalog-1.json \
  k6 run --out json=.performance/catalog-1-raw.json scripts/performance/load.js
```

`measurement` 标签才是稳态测量；setup、预热和收尾分别处理。每轮使用唯一 RUN_ID；匹配的两份 summary 才可交给 `scripts/performance/compare.py`。

## 指标与判定

| 范围 | 保存内容 |
| --- | --- |
| 客户端 | 每操作成功数、吞吐、p50/p95/p99、错误状态、预热/测量时间和负载机资源 |
| 服务 | 各副本实际流量、CPU/内存、重启/OOM、JVM/GC、Hikari 等待、请求与依赖耗时 |
| 数据库 | 连接数、锁等待、业务快照及 `reserved = confirmed quantities = active tickets`，库存不超 quota |
| 扩容收益 | 成功吞吐 2 副本 / 1 副本、逐操作 p95、资源增加与重复样本差异 |

负载工具的待验证目标为每操作 p95 < 3 秒、意外错误率 < 1%。401、403、429、5xx 和超时均记录为意外错误；409 业务拒绝单列，不计成功吞吐，容量充足性实验也不能把售罄当成成功。失败阈值和原始样本保留；API 失败、客户端重试、内部只读重试和端到端结果分别统计。

Catalog 的受保护内部 diagnostics 和 Grafana 提供读取、Identity 依赖、连接池及系统指标；公网不开放 `/internal/`。计时最大值不是 p95，累计指标须以同一进程前后快照求差；不要把重叠的数据库与应用计时相加。

## 恢复时间与运行保护

恢复时间从故障请求起算，直到业务连续 30 秒满足预定延迟/错误目标的窗口起点。另报失败请求数、最长失败区间、Pod Ready 时间及数据核对；Pod Ready 不能代替业务恢复。客户端超时的订票请求使用同一个 requestKey 验证最终提交状态。

预先定义资源保护阈值，发生节点/容器 OOM、非预期重启、磁盘危险、持续内存压力、采集失联或健康检查异常时停止该组并保存失败记录。故障脚本的 finally 不保证能抵御进程强杀或断电，测试结束必须检查副本与数据状态。

## 已有结果的边界

[历史容量报告](evidence/2026-10-22-cloud-capacity/README.md)属于当时的 Lightsail 版本：250 VU 读取通过，混合负载出现内部 504，500/1000 VU 未执行。K3s 的跨节点并发、Pod 故障和 CI 冷启动回归已验证功能正确性，尚无当前 K3s 的受控吞吐收益或十分钟稳态容量结论。

负载数据、JWT、数据库快照和完整请求记录保存在忽略目录。对外证据只提交脱敏结果、参数、时间、版本和库存审计；所有实验保留实际执行范围与失败结果。
