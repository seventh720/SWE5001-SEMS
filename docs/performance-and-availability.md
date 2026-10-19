# 扩容收益与可用性验证

这份文档定义实验方法；实际完成状态见[当前进度](progress.md)。脚本位于 `scripts/performance/`。本地短时 smoke 只说明工具和业务路径能运行，不是云端性能结论。

## 可以证明什么

| 声明 | 必要证据 | 当前架构的边界 |
|---|---|---|
| 服务可以水平扩副本 | 1→2 后两个实例都收到业务流量，数据库一致性通过 | Docker DNS 与数据库锁已有正确性验收；仍需云端实测 |
| 扩容有收益 | 固定数据/负载/单副本资源，重复比较成功吞吐、分操作 p95、错误率和成本 | 副本增加不保证提升；数据库、Identity 同步调用和热点行锁可能成为瓶颈 |
| 服务副本故障可恢复 | 持续业务请求中停止一个实例，记录失败区间、恢复时间及数据核对 | 同一主机上的副本只能验证实例故障，不覆盖主机或数据库故障 |
| 主机/可用区级高可用 | 跨故障域部署，停止整台主机或执行数据库切换，入口和业务持续恢复 | 当前单台 Lightsail、单 PostgreSQL、单入口不满足此部署条件 |
| 自动扩容 | 指标触发副本调整，记录触发、就绪、分流和缩容全过程 | 手动 `--scale` 不等于自动扩容 |

高可用需要预先定义 SLO 和故障范围，不能由一张架构图或一次健康检查证明。两台服务器若仍依赖同一台数据库/入口，也未消除系统单点。跨可用区隔离与数据库故障切换是不同层次的措施；参考 [AWS 故障域建议](https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/rel_fault_isolation_multiaz_region_system.html) 与 [RDS Multi-AZ 切换说明](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.MultiAZ.Failover.html)。不要承诺数据库切换必然在 60 秒内完成；记录实际结果。

## 准备独立实验环境

使用与发布版相同的镜像 digest、数据库配置和网关配置。负载发生器放在另一台机器，避免抢占被测服务 CPU。先记录机器规格、CPU/内存限制、镜像、commit、数据库连接池、网络条件和副本数。当前云配置的容器内存上限合计约 3136 MiB，新增一个 Java 副本还需 768 MiB 上限；这不是实际预留值，但不能在未核对主机余量时直接加副本。

只在专门的实验组织/数据库中造数和注入故障，不对正在演示的数据运行验收链。用环境变量提供管理员登录资料，不把 token、密码、`.env` 或完整 dataset 放进证据、PR 或 CI artifact。

```bash
mkdir -p .performance
export SEMS_BASE_URL=https://your-benchmark-host
# 在当前 shell 安全加载实验环境管理员变量：SEMS_BOOTSTRAP_ADMIN_EMAIL/PASSWORD
python3 scripts/performance/seed.py --base-url "$SEMS_BASE_URL" \
  --users 1000 --events 100 --quota 100000 --output .performance/dataset.json
```

生成器通过真实 API 建立独立组织、100 个已发布活动和 1000 个账号，保持真实认证限流，完成后统一登录。密码和 token 文件权限为 0600，目录被 Git 忽略。重复执行不会覆盖旧数据；失败时保留已生成记录，另建实验或人工清理该实验组织，不自动删除数据。JWT 仍为一小时；每轮前需要时执行同一命令并加 `--refresh`。压测 setup 会验证账号有效性；完整一轮应在 token 到期前完成。

## 扩容实验矩阵

分别运行两类场景，其他参数不变：

- `MODE=catalog`：80% 按实验关键字分页检索，20% 活动详情；Catalog 1/2 副本，其他服务固定。
- `MODE=booking`：订票后读取回执，活动均匀分散；Admission 1/2 副本，其他服务固定。记录订单吞吐与 HTTP 请求吞吐，不能把两者混用。

每组 25、50、100 VU，预热 60 秒、稳定测量 600 秒，每组至少重复三次，交错执行 1/2 副本降低时间顺序影响。每副本资源相同，基础设施预算充足。订票会增长数据库，应从同一实验快照开始或明确记录数据增长差异；比较脚本要求 dataset、commit、场景及负载参数一致。RUN_ID 每次唯一，避免命中之前的幂等收据。

以下命令在安装 k6 1.3.0 的负载机运行；也可以用 `grafana/k6:1.3.0` 容器挂载脚本、私有 dataset 和结果目录。Docker Desktop 可用 BASE_URL 覆盖为 `host.docker.internal` 访问本地测试栈；不要把这个地址用于云端。

```bash
DATASET=.performance/dataset.json MODE=catalog VUS=100 \
  RUN_ID=catalog-1-repetition-1 COMMIT=full-tested-commit \
  REPLICAS=catalog1-admission1 WARMUP_SECONDS=60 DURATION_SECONDS=600 \
  SUMMARY_FILE=.performance/catalog-1.json \
  k6 run --out json=.performance/catalog-1-raw.json scripts/performance/load.js
```

`measurement` 标签的指标才是稳定期成绩，内置 HTTP 总数还包含 setup 和预热。阈值是每种操作 p95 < 3000ms、意外错误率 < 1%、成功请求数 > 0。409 单独算业务拒绝，既不算系统异常，也不算成功吞吐；性能实验中任何 409 都使容量充足性阈值失败。401、403、429、5xx、超时均是该实验的意外错误，不能忽略。失败的测试仍保存 summary/raw，不删掉失败运行后只展示成功样本。[k6 阈值与退出码](https://grafana.com/docs/k6/latest/using-k6/thresholds/)。

在被测主机同步记录（`SEMS_COMPOSE_FILE` 支持以 `:` 分隔多个 Compose 文件；设置正确 `COMPOSE_PROJECT_NAME`）：

```bash
python3 scripts/performance/record.py --seconds 720 --interval 10 --output resources.jsonl
python3 scripts/performance/audit.py --dataset .performance/dataset.json --output inventory.json
python3 scripts/performance/compare.py .performance/catalog-1.json .performance/catalog-2.json
```

资源记录是持续到指定时长的实验采样，不是长期监控/告警平台。网关日志的 upstream 地址证明两个副本实际接流量；另存容器地址映射。审计检查数据库 `reserved = confirmed quantities = active tickets` 且不超 quota。公平比较要求恢复相同数据起点；扩容系数为 `成功吞吐(2副本)/成功吞吐(1副本)`，并比较每操作 p95、资源与额外成本。只有所有门槛通过且重复结果稳定，才能据实陈述收益；结果接近 1 或更差应解释瓶颈，不把“启动成功”改写成“性能提升”。

## 故障恢复实验

确认两个健康副本且正在跑业务负载，再在被测主机执行：

```bash
python3 scripts/performance/fault.py --service admission --seconds 60 --output fault.jsonl
```

工具停止一个副本，保留另一副本；在 finally 中恢复被停止容器，并记录 UTC 时间。启动不代表 readiness，必须继续观察业务结果。进程被强制杀死或主机断电时 finally 不保证执行，应手动恢复记录中的容器。脚本不足两个运行副本时拒绝操作；实验前仍需确认两个副本健康。

从 `stop-requested` 起到连续 30 秒满足错误率/延迟目标的业务窗口起点，定义本次恢复时间；同时报告失败请求数、最长失败区间和订单一致性。Catalog、Admission 分别测，故障阶段保留原始每请求数据。客户端超时的 POST 可能已提交，用同一个 requestKey 查询/重试才能核对是否重复；现有 booking acceptance 已覆盖幂等，故障演练还需保存具体请求的重试证据。

主机级 HA 的下一层方案是：跨两台主机/可用区放置 Identity、Catalog、Admission 副本，使用有健康检查与故障切换能力的入口，数据库具备跨故障域复制/自动切换，配置和 JWT 密钥一致，数据库连接数按副本总数预算。之后分别做服务进程故障、主机故障、数据库主实例切换，持续从外部客户端验证业务并核对已提交数据的 RPO/RTO。现有单机 Compose 不能跨主机调度，迁移需要新的部署/服务发现配置；本轮没有把它声称为已完成。

## 本地工具验证口径

2 VU、2 秒预热、5 秒测量只用于 smoke。CI 会运行数据生成、两个场景及数据库一致性审计；它不跑云端 100 VU 的十分钟实验。最终成绩必须附云端环境参数、镜像 digest、完整原始数据和重复实验汇总。
