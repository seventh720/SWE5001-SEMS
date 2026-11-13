# 本地 Kubernetes 压测与扩容实验

本指南覆盖流程预检、数据库热点诊断及 Admission 1→2 副本的本地受控对照。使用本机 `kind-sems-local` 集群的专用 `sems-benchmark` namespace，独立 PostgreSQL/PVC、账号和 JWT。生产 `sems-prod`、已有 `sems-local` 和本地 Compose 数据都不参与。

这些实验不创建 AWS 资源、不配置 HPA，也不改变正式环境副本数。单节点 kind、共享 Docker VM、端口转发和现有容器竞争限制了性能解释；结果反映相应本地条件下的行为。正式云端对照需再确定独立测试资源、节点布局和费用。

四轮短时预检及下述本地对照的原始记录已随报告离线归档，保存方式见[验证索引](evidence/README.md)。

2026-10-26 完成四轮 50 VU、十分钟测量的 Admission 单/双副本对照：分散组吞吐增加 55.5%，热门组增加 26.1%；客户端、Gateway 门槛和库存审计逐轮通过，测试前数据库及配置已恢复。参数、资源瓶颈与结果边界见[扩容实测报告](evidence/README.md)。

## 环境准备

需要 Java 21、Node.js 22、kubectl、kind、Docker 和 Python 3。已有 `sems-local` 集群可以复用；首次创建见 [Kubernetes 指南](kubernetes.md)。检查 VM 可用内存，额外测试栈最多运行四个 JVM Pod，每个沿用 base 的 1 CPU / 768MiB limit 和 512MiB memory request。不要为了腾空间停止含实际数据的其他环境。

```bash
bash scripts/k8s/setup-local.sh .secrets/k8s-benchmark benchmark-admin@example.invalid
mvn -DskipTests package
npm --prefix apps/web ci
npm --prefix apps/web run build
docker compose --env-file .secrets/k8s-benchmark/runtime.env \
  -p sems-benchmark -f deployment/compose.yaml build
kind load docker-image --name sems-local \
  sems-benchmark-identity:latest sems-benchmark-event-catalog:latest \
  sems-benchmark-admission:latest sems-benchmark-web:latest \
  sems-benchmark-gateway:latest sems-benchmark-postgres:latest
```

Compose 在这里用于构建镜像；工作负载由 Kubernetes/containerd 运行。镜像 ID、JAR 哈希和构建 source commit 应随实验一起记录，不能仅凭当前 HEAD 推断镜像内容。

只对首次创建的新测试 namespace 执行以下准备；若名称已存在，先核对其标记和用途，保留原数据与证据：

```bash
set -o pipefail
sems_benchmark_kubectl() {
  kubectl --kubeconfig .secrets/k8s-local/kubeconfig \
    --context kind-sems-local -n sems-benchmark "$@"
}
sems_benchmark_kubectl create namespace sems-benchmark
sems_benchmark_kubectl annotate namespace sems-benchmark \
  sems.seventh720.com/environment=benchmark
python3 scripts/k8s/secrets.py --env-file .secrets/k8s-benchmark/runtime.env \
  --key-directory .secrets/k8s-benchmark --namespace sems-benchmark \
  --include-postgres | sems_benchmark_kubectl apply -f -
sems_benchmark_kubectl apply -k deployment/k8s/overlays/benchmark
sems_benchmark_kubectl rollout status statefulset/postgres --timeout=180s
for service in identity event-catalog admission web gateway; do
  sems_benchmark_kubectl rollout status "deployment/$service" --timeout=300s
done
```

## 短时对照

先检查空闲的本机 18087 端口。脚本自行建立和关闭到测试 Gateway 的转发，不接受外部 base URL 或 namespace 参数。

```bash
python3 scripts/performance/test-k8s-experiment.py
kubectl kustomize deployment/k8s/overlays/benchmark > /tmp/sems-benchmark.yaml
python3 scripts/performance/k8s-experiment.py \
  --kubeconfig .secrets/k8s-local/kubeconfig \
  --env-file .secrets/k8s-benchmark/runtime.env \
  --output .performance/k8s-preflight-unique-run
```

默认 20 账号、10 活动、10 VU、30 秒预热、60 秒测量、一次重复，共四轮：Catalog 1/2 副本、Admission 1/2 副本。CLI 中 `booking` 表示 Admission 场景。Catalog 轮仅改变 Catalog；订票轮仅改变 Admission，其他部署固定 1 副本。

## 数据库热点对照

2026-10-26 已完成两组 50 VU、十分钟稳态及测试前数据库还原，见[数据库热点实测](evidence/README.md)。首次热门组因本机睡眠中断而排除，补跑结果单独保存。

用同一批 10 个活动分别测试 `hot`（只订第一个活动）与 `spread`（分散到全部活动），固定应用副本、用户数、库存和请求节奏。以下命令为两组各 60 秒预热、600 秒测量的本地诊断，准备和恢复另计；闭环 VU 不等于固定到达率，也不代表云端容量。

```bash
python3 scripts/performance/k8s-experiment.py \
  --kubeconfig .secrets/k8s-local/kubeconfig \
  --env-file .secrets/k8s-benchmark/runtime.env \
  --output .performance/db-contention-unique-run \
  --modes booking --users 50 --events 10 --quota 1000000 --vus 50 \
  --replica-counts 1 --distributions hot spread --think-seconds 0 \
  --warmup 60 --duration 600 --repeats 1
```

`--replica-counts` 支持固定 1 或 2，也可沿用默认 1/2 对照；`--distributions` 默认 `spread`，`hot` 仅允许订票场景。`--think-seconds` 默认 0.1，设为 0 可持续发起业务迭代。热点轮名称带 `-hot`。副本比较拒绝将不同分布或等待时间的 summary 配对。

macOS 长时间运行时，可在上述命令前加 `caffeinate -i`，仅在进程运行期间阻止闲置系统睡眠。即便 k6 阈值通过，睡眠中断的轮次也不能算连续十分钟稳态；保留异常记录并补跑。脚本在相邻资源采样时间倒退或间隔超过 15 秒时停止该轮。

每轮 `database.jsonl` 约每 5 秒记录一次 PostgreSQL 会话状态、角色、等待事件、阻塞 PID、事务年龄和数据库累计统计，不包含 SQL 文本或业务字段。采样包含预热和收尾，分析稳态时需按 k6 原始样本的 `scenario:measurement` 时间窗口过滤；一次没采到锁等待不能证明没有短时争用。将等待、各 Pod CPU/内存、Gateway 上游错误与端到端吞吐一起分析。`track_io_timing=off` 时，读写计时为零不能用于证明 I/O 没有压力。

数据库热点报告中的旧轮次在结束后读取 Gateway stdout，仅保留轮转后的片段。当前 benchmark overlay 改为将访问日志与错误日志写入测试 Pod 的 `/tmp/sems-gateway/`；每轮前清空文件，结束后保存到本地，不受 kubelet stdout 轮转影响。旧测试栈需要先更新 Gateway 的 benchmark command/args；不会对生产 overlay 启用该日志方式。

负载请求携带非敏感的轮次与阶段标记。`gateway-evidence.json` 核对 Gateway 测量请求数与 k6 测量 Rate 的 `passes + fails` 完全相等；缺失日志、无法解析的行会使该轮无效。分别记录入口状态、内部请求状态、`upstream_status` 中被重试掩盖的 5xx 和多上游尝试。完整日志门槛要求覆盖通过且没有 5xx 或重试；客户端阈值与服务端门槛分别报告。预热被 k6 主动中止的请求可能在 Gateway 记录为 499，单列预热阶段。

数据库快照在造数后创建，含测试前已有数据；每轮恢复它，结束默认只恢复副本数。若需完全恢复测试前的库，先为已标记的隔离 namespace 另存造数前备份，结束后停止三个测试后端、还原备份、恢复副本并确认 PVC UID。不要把该流程用于生产 namespace。

每轮停止测试环境的三个后端，恢复同一初始数据库快照，再启动所需副本、等待全部 Ready 和 DNS 缓存刷新、更新 JWT。负载由独立 k6 容器发起，固定 1 CPU / 256MiB；服务实际运行在 kind 的 containerd 中。

## 数据库 CPU 对照

2026-10-26 已完成固定 Admission 双副本的四轮数据库 1/2 核对照。分散组吞吐基本持平，热门组本轮增加 9.7%；CPU 配额、数据与 Gateway 配置均已恢复。实际资源限制、样本边界与后续定位方向见[数据库 CPU 实测报告](evidence/README.md)。

`--postgres-cpu-limits 1 2` 将对照变量切换为 PostgreSQL CPU limit，要求 `--modes booking --replica-counts 2`，避免同时改变应用副本与数据库配额。数据库内存、CPU request 和各应用单副本资源不变：

```bash
caffeinate -i python3 scripts/performance/k8s-experiment.py \
  --kubeconfig .secrets/k8s-local/kubeconfig \
  --env-file .secrets/k8s-benchmark/runtime.env \
  --output .performance/postgres-cpu-unique-run \
  --modes booking --users 50 --events 10 --quota 1000000 --vus 50 \
  --replica-counts 2 --postgres-cpu-limits 1 2 \
  --distributions spread hot --think-seconds 0 \
  --warmup 60 --duration 600 --repeats 1
```

每轮停止三个测试后端，通过测试轮次 annotation 确保 PostgreSQL 都重新启动，再恢复相同快照并启动应用。等待 StatefulSet rollout、数据库 Ready 和实际 Pod CPU limit 校验完成后才开始负载；原 PVC 保留。每轮名称带 `-db1cpu` / `-db2cpu`，summary 与运行记录包含实际 `postgresCpuLimit`。CPU 对照使用 `compare.py --varying postgresCpuLimit`，要求两份 summary 的应用副本一致；普通副本对照也会拒绝混入不同的数据库 CPU 配额。

正常结束和可捕获失败会恢复 PostgreSQL 原资源配置与模板 annotation，再恢复应用副本。数据库内容恢复仍遵循前文的独立备份流程。Gateway 测试日志配置同样需要预先启用；已有 Gateway 更新后必须等待 Deployment rollout 完成，不能仅凭仍在运行的旧 Ready Pod 判断新配置已就绪。

## 证据与判定

| 文件 | 内容 |
| --- | --- |
| `environment.json` | 镜像 ID、Pod 资源、版本、节点、数据量、数据库快照哈希与限制 |
| `runs.json`、`completion.json` | 每轮状态、退出码和最终清理状态 |
| `*/summary.json`、`*/raw.json` | k6 阈值及逐点样本；读取 `scenario:measurement` 数据 |
| `*/pods.json`、`*/resources.jsonl` | Pod/节点映射、kubelet CPU/内存/磁盘采样、重启检查 |
| `*/traffic.json` | 各目标 Pod 实际业务请求状态分布，含预热；健康探针不计入 |
| `*/inventory.json` | reserved、已确认数量、有效票数相等，且未超过 quota |
| `*-comparison.json` | 成功请求吞吐和逐操作指标的本地对照，不作为云端容量结论 |

测试专用 Tomcat access log 只记录方法、路径、状态和时长，不记录凭据、请求体或查询字符串。两副本必须分别收到业务流量；Pod 数量和 Ready 状态不能证明有效分流。端到端阈值、Gateway 原始日志中的上游重试、业务一致性分别报告。

任何 Pod 身份/镜像/重启数变化、采样失败、转发丢失、节点可用内存低于 512MiB、磁盘余量低于 10% 或库存不一致都会停止对照，保留失败证据。k6 阈值失败仍保存结果，不将其改写为通过。

正常结束和可捕获的失败都会恢复测试前的 1 副本，并确认 PVC 未变。强杀、断电或 Kubernetes 不可用时仍需人工检查；脚本不会删除 namespace/PVC，也不会把最终数据库自动回滚为初始快照。所有完整输出都在忽略目录 `.performance/`，其中含账号、JWT 和数据库备份，不能直接提交。

预检通过后，较长矩阵可用 `--vus 25 50 100 --users 1000 --events 100 --warmup 60 --duration 600 --repeats 3`，交错运行 1/2 与 2/1。当前脚本只接受本地 kind；云端需要另行适配独立测试上下文和环境保护，不能改指向生产。先完成云端环境规划，再决定执行该长时矩阵。本地通过不等于 AWS 吞吐翻倍、HPA 生效或主机高可用。
