# 生产 namespace 迁移验收 · 2026-10-25

业务及正式数据库从 `sems-test` 迁入 `sems-prod`，旧 namespace 已删除；`observability` 保持独立。正式入口仍为 <https://swe5001.seventh720.com>，Grafana 仍为 <https://grafana.seventh720.com>。维护窗口为新加坡时间 17:55:36–17:59:44，约 248 秒，期间返回 503 和 Retry-After。

## 数据与发布

- 停止全部旧应用副本后，导出三个数据库及包含密码验证器的全局角色定义，校验 custom archive 目录。敏感文件只存放于本机 `.secrets/namespace-migration-20261025/` 和 server 的 root-only 备份归档，未提交到仓库。
- 正常停止 PostgreSQL，删除旧 namespace 的 PVC，再把 Retain PV 预绑定至 `sems-prod/data-postgres-0`。PV UID、worker、本地目录及数据库 cluster identifier 均保持；PVC 和 Pod 随 namespace 迁移重新创建。目录名称中的历史 `sems-test` 字样不代表旧 namespace 仍存在。
- 27 张表行数及 SHA256、角色与 SCRAM 验证器在新库启动前后完全一致；应用和监控启动后再次核对仍一致。保留 7 用户、7 活动、3 订单和 4 票券。原 JWT、公私钥、六个业务 Secret、Grafana、Telegram 和数据库监控凭据均保留。
- 五个应用使用原生产 digest，每个两个就绪副本，分布在两节点。未新建 EC2、EBS、RDS、EKS 或负载均衡器。旧 namespace 已清理，正式 Ingress 只位于 `sems-prod`。
- server-side dry run 及真实 host CD 验证器通过，确认镜像、跨节点分布、可信 HTTPS、原 JWT、管理员登录、活动/订单读取和内部接口 404。未在生产库执行夹具、订票写入或故障注入。

发布基线为 `48c28b1ca3ad362cf420e8b1ef65982271b8ee19-20261025100157-1`，应用镜像源提交仍为 `48c28b1ca3ad362cf420e8b1ef65982271b8ee19`。这是人工配置迁移基线，数字后缀为迁移时间，未宣称对应 GitHub Actions run。记录 `deploymentOrigin=namespace-migration`。旧发布指针作为审计记录保留，新基线没有可自动回退的跨 namespace 前任。

本次 namespace 迁移 PR 合并后，main CD 才会渲染并更新 `sems-prod`。旧 main 的资源不含 Namespace，旧 namespace 删除后，发布器会在应用快照校验阶段拒绝更新，不能重建旧 namespace。迁移前 release 不能直接回放到新环境；需要旧镜像时，应审核数据库兼容性并在 `sems-prod` 渲染新的 release。

## 可观测性

数据库 exporter、kube-state-metrics、cAdvisor 筛选、文件日志路径、Agent 资源属性、OTLP NetworkPolicy、Prometheus 规则和 Grafana 面板均指向 `sems-prod`。验证六个后端 Pod 的 JVM/HTTP 指标、17 个采集目标、数据库只读采集和公网探测；真实只读请求得到 Admission → Catalog → Identity 三服务的同一 trace，span 明确带 `k8s.namespace.name=sems-prod`。Grafana 原账号、可信 HTTPS、匿名拒绝与 Secure/HttpOnly/SameSite 会话通过。

首次验收的采集和追踪检查通过，但 Alertmanager 尚保留维护期的 `PostgresUnavailable`，因此整体验收按失败保存。现场复核 `pg_up=1` 且 Prometheus 无活动告警；等待原告警的 endsAt 后再次验收，最终 Prometheus 与 Alertmanager 均无活动告警，完整验收通过；告警规则保持正常启用。

## 记录

| 记录 | 内容 |
| --- | --- |
| [migration.json](migration.json) | 迁移时间、数据计数、凭据保留及 namespace 清理 |
| [source-fingerprints.json](source-fingerprints.json)、[target-fingerprints.json](target-fingerprints.json) | 全部 27 张表的行数与 SHA256 |
| [final-backup-metadata.json](final-backup-metadata.json)、[after-backup-metadata.json](after-backup-metadata.json) | 最终停写备份及迁移后备份的大小与摘要，不含备份内容 |
| [deployer-verification.json](deployer-verification.json) | 实际 host CD 验证器 |
| [grafana-https.json](grafana-https.json) | 固定 HTTPS、原账号和登录保护 |
| [observability-first-pass.json](observability-first-pass.json)、[alert-before-recovery.json](alert-before-recovery.json)、[alert-recovery.json](alert-recovery.json) | 初次失败与维护告警状态 |
| [observability.json](observability.json) | 告警恢复后的最终可观测性验收 |

PostgreSQL 仍为 worker 上的单实例 local-path 存储，现有备份可用于恢复；namespace 调整没有增加数据库或控制平面高可用能力。
