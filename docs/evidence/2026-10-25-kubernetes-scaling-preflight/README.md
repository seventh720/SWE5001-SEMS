# Kubernetes 扩容工具短时预检

2026-10-25 在本机 `kind-sems-local/sems-benchmark` 完成四轮对照。源代码 `f33bf83168a44841895d074e917f01ff6ed5d70b`；准确镜像 ID、JAR 哈希、Pod 资源、逐操作统计与库存核对见 [results.json](results.json)。[准备与复现入口](../../kubernetes-scaling-experiment.md)。

独立 PostgreSQL/PVC、JWT、20 个测试账号、10 个公开活动；每轮恢复同一数据库快照。10 VU、30 秒预热、60 秒测量、一次重复；仅改变当前被测服务的副本数，其余部署固定 1。单副本 limit 为 1 CPU / 768MiB，Catalog 连接池每副本 10。

| 场景 | 副本 | 测量成功 HTTP 请求 | 成功请求/秒 | 操作 p95（毫秒） | 意外错误 / 业务拒绝 | 库存审计 |
| --- | --- | --- | --- | --- | --- | --- |
| Catalog | 1 | 5,440 | 90.67 | 列表 18.41；详情 18.16 | 0 / 0 | 通过 |
| Catalog | 2 | 5,428 | 90.47 | 列表 16.71；详情 16.69 | 0 / 0 | 通过 |
| Admission | 1 | 9,922 | 165.37 | 订票 19.00；回执 8.46 | 0 / 0 | 通过 |
| Admission | 2 | 9,886 | 164.77 | 订票 19.93；回执 9.73 | 0 / 0 | 通过 |

Admission 每次业务迭代有订票和读取回执两次请求，测量成功订单数分别为 4,961 和 4,943；不能把 HTTP 吞吐当作订单吞吐。请求/秒采用测量窗口计数除以 60 秒；k6 summary 中 Counter 的原始 `rate` 使用整轮时间，不能直接代替该值。

双副本的实际业务流量：Catalog 两 Pod 各 4,066 次；Admission 两 Pod 分别 7,286 和 7,262 次。这些 Pod 计数包含预热，健康探针不计入，不能与表中的测量计数直接比较。所有记录的业务状态均为 200。

Admission 单副本轮结束时，预留库存、已确认订单数量、有效票数均为 7,102；双副本轮均为 7,274，包含预热，10 项库存均未超过 quota。两轮来自同一初始快照，数量不同反映完成的实际请求数。没有发生 Pod 重启、采样中断或资源保护停止；每轮的 k6 退出码均为 0。

结论：本机 Kubernetes 上的独立副本控制、数据库恢复、JWT 更新、请求分流、资源采样、负载与一致性核对已跑通。该闭环低负载含每次迭代 100ms 的 think time，吞吐基本相同，未建立容量收益结论。测试为单节点 kind，负载机和既有容器共享 Docker VM，经由 port-forward；未测试 AWS 容量、HPA、节点扩容或主机故障恢复。

结束后五个测试应用恢复为各 1 个 Ready 副本，PostgreSQL 为 1 个 Ready 副本，原 PVC UID 保持不变。原 `sems-local` Pod 与本地业务 Compose 容器保持运行。没有创建 AWS 资源或修改正式环境。

完整原始样本、Gateway 日志、资源时序、数据集和数据库快照保留在本机忽略目录 `.performance/k8s-preflight-20261025-01/`。该目录含凭据，不能整体提交。以下四份脱敏 summary 保留全部实际轮次及阈值结果：

- [Catalog 单副本](catalog-r1-vu10-repeat1-summary.json)
- [Catalog 双副本](catalog-r2-vu10-repeat1-summary.json)
- [Admission 单副本](booking-r1-vu10-repeat1-summary.json)
- [Admission 双副本](booking-r2-vu10-repeat1-summary.json)
