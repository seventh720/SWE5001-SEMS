# 扩容收益与可用性验证

已完成的本地正式实验与补测见[结果和图表](evidence/2026-10-19-local-architecture/README.md)。

2026-10-21 [最新云端实验](evidence/2026-10-21-cloud-capacity/README.md)运行已部署 PR #22 / `1413622`：池10/16各三次固定历史的250 VU读取客户端检查通过，16无吞吐收益且内部超时更多；16下混合250出现14次订票503，严格验收失败。默认保留10，未继续500/1000。CPU完整采样后，复用分组总数与公开字段投影的本地候选未证明整体收益，已撤回，未部署。十分钟稳态及独立扩容/故障实验仍待完成。

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

使用与发布版相同的镜像 digest、数据库配置和网关配置。负载发生器放在另一台机器，避免抢占被测服务 CPU。先记录机器规格、CPU/内存限制、镜像、commit、数据库连接池、网络条件和副本数。仓库默认云配置的容器内存上限合计约 3136 MiB；本次共享 Caddy 实际为 256 MiB，SWE5001 合计约 3264 MiB，另有 SWE5006。新增一个 Java 副本还需 768 MiB 上限；这不是实际预留值，但不能在未核对主机余量时直接加副本。

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

### Catalog 读取计时与连接池对照

已部署的读取修正结束仓库只读事务后再调用 Identity，内部详情采用六字段投影。`catalog.read` 按组织发现、公开列表/详情、发布/成员快照和内部详情分别计时；`catalog.identity` 区分批量组织状态与成员查询。Hikari 自带 `connections.acquire` / `connections.usage` 分别记录连接获取和占用时间，包含在 `hikaricp` 指标中。

`GET /internal/v1/diagnostics/catalog` 返回上述计时的累计次数、总毫秒和滚动最大值，以及连接池 active/idle/pending/total/max 瞬时值。必须使用现有 `ADMISSION_TO_CATALOG_TOKEN` 服务凭据；公开网关仍返回404，不额外暴露 Actuator metrics。累计计时应以同一进程前后快照求差计算均值；最大值为 Micrometer 时间窗口值，不能当成某一档的 p95，也不能跨服务重建直接相减。读取总计时包含连接等待、JDBC和映射，与Hikari计时重叠，不能直接相加。请求保持期 p95 仍由负载机测量。

Catalog 的 `CATALOG_DB_POOL_SIZE` 可从部署 `.env` 传入，默认保持10。隔离环境对照10/16/20时，其他服务池、CPU/内存、数据与负载必须固定；更改该值后仅重建 Catalog，等待 readiness 和网关 DNS 刷新。至少三次交错重复，同时保留获取/占用、吞吐、状态检查及逐接口延迟。双核 CPU 已饱和时，扩大连接池不能预先视为优化；应按测量结果选择，线上配置另行通过部署流程生效。最新诊断、读取验证和适用范围见[容量实验记录](evidence/2026-10-21-cloud-capacity/README.md)。

### 云端容量阶梯（独立于扩容对照）

`cloud-capacity.js` 和 `cloud-capacity.py` 借鉴 SWE5006 的容量验证方法，使用独立负载机访问已部署的 HTTPS 入口，保持真实鉴权与限流。先运行 1 VU 读取/混合预检，再分别执行 50→100→250→500→1000 VU；每档爬升 30 秒，低档保持 30 秒，500/1000 档各保持 180 秒，档间恢复 10 秒。500 VU 也有独立的三分钟成绩，不把爬升或收尾阶段计入保持阶段。最后使用独立的 100 票活动做一次库存竞争。

读取迭代依次请求活动分页、活动详情、本人资料、本人订单，然后等待 1 秒。混合场景每五轮增加订票→读取回执→取消，每 VU 最多 60 次。1000 个账号、100 场普通活动和 1 场库存竞争活动均属于本轮独立组织；注册/登录准备不计入压测成绩。与下面原有 0.1 秒思考时间的扩容负载不同，不能仅凭相同 VU 数比较吞吐。

```bash
python3 scripts/performance/cloud-fixture.py prepare-hot --dataset .performance/dataset.json
caffeinate -i python3 scripts/performance/cloud-capacity.py \
  --dataset .performance/dataset.json --reports .performance/cloud-capacity-run \
  --identity-file .secrets/cd/staging_ed25519 --known-hosts /path/to/trusted-known-hosts \
  --commit <actual-deployed-sha> --max-vus 1000
```

`cloud-guard.py` 在主机采样两套系统的六项健康检查、容器 CPU/内存、重启/OOM、主机可用内存与数据库连接/锁等待。健康失败或超过 5 秒、可用内存低于 384 MiB、任一容器内存超过 95% 连续三次即停测；容器退出、重启、OOM 或监控断线也停测。负载生成器限制 4 CPU/2 GiB，并记录资源。任何一档未通过即停止后续档位，保留失败结果，不放宽阈值继续评分。

整体与逐接口 p95＜3 秒、意外错误率＜1%，同时要求所有状态和内容检查通过。混合场景的 409 为失败；库存竞争只允许明确的余票不足 409，并另外记录成功数、售罄数及数据库库存审计。JWT、密码和完整原始记录留在 `.performance/`；对外证据仅提交脱敏指标。实验后通过 `cloud-fixture.py cleanup` 取消本轮活动、关闭本轮组织并撤销组织者角色；账号及审计历史的物理清理由受控的精确 ID 事务另行执行，工具不会批量删除其他数据。

可参考 SWE5006 的 Nginx 每 worker 4096 连接、8192 文件额度及上游连接复用配置，但先记录当前版本基线，再根据日志验证瓶颈。Nginx 的连接额度同时覆盖客户端和上游连接，仍受文件额度约束；连接复用池只限制空闲连接，不限制全部上游连接。参见 [Nginx 连接额度](https://nginx.org/en/docs/ngx_core_module.html#worker_connections)和[上游 keepalive](https://nginx.org/en/docs/http/ngx_http_upstream_module.html#keepalive)。

这组实验回答当前部署在指定业务模型下能否达标，不能代替下述 1→2 副本收益、十分钟稳态重复测量和故障恢复实验，也不证明主机级高可用。

### 副本扩容对照

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

## 本地完整实验执行器

`local-experiment.py` 仅接受独立的 `sems-architecture` Compose JSON 环境和 `127.0.0.1:18087` 数据集，避免误恢复演示/云端数据库。运行前必须设置 Catalog、Admission 的 CPU/内存上限。每轮停止应用、恢复同一份私有数据库快照、等待所有副本就绪并刷新 JWT；故障实验先运行，之后按两种场景、25/50/100 VU、三次重复、交错 1/2 副本顺序运行。默认预热 60 秒、测量 600 秒，36 轮纯负载约 6.6 小时，数据库恢复和故障测试另计。

```bash
python3 scripts/performance/local-experiment.py \
  --compose /private/path/compose.json \
  --dataset /private/path/dataset.json \
  --output /private/path/unique-results-directory
```

输出 `progress.json`、环境及镜像 ID、每轮 k6 summary/raw 压缩包、资源采样、网关 upstream、库存审计。故障实验额外记录同一 requestKey 重复提交的响应与最终数据库订单数，以及基于业务流量的连续 30 秒恢复窗口。恢复时间可能为零（剩余副本始终满足目标），也可能为空（观察期没有满足目标）；均不得用容器启动时间替代。

本地执行需要电脑开机、Docker 运行且避免休眠；镜像已缓存后，运行请求走本地网络，不依赖持续互联网连接。负载发生器与服务共享 Docker 虚拟机，其他本地应用也可能竞争资源，必须作为实验限制记录。运行完成或捕获异常后停止专用实验容器；强制终止时仍需人工确认容器状态。原始 dataset、数据库快照和 Compose 中的凭据不能提交。状态为 `complete` 前不应把计划中的 36 轮写成已完成。

补测使用 `--baseline 原始快照 --only-runs 具体轮次...`，必须保留原样本。`summarize-local.py` 会检查每轮真实请求时间连续性；参数写着 600 秒、k6 阈值通过，不足以证明连续测量已完成。用 `--replacement-source 补测目录` 合并经过环境和快照哈希核对的补测，旧结果保留在 `supersededRuns`。`plot-local.py` 从核验后的摘要生成 PNG/PDF 图表，依赖 Matplotlib。
