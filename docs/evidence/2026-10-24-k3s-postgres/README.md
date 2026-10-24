# EC2 K3s 自建 PostgreSQL 验收

日期：2026-10-24，新加坡时间。最终验收运行于 22:05:35–22:05:57；测试数据清理后于 22:06:36 另存干净的异机备份。源提交 `d3002d10a6f515b14f2013fc89f8805837b1f8ec`，工作区含尚未提交的部署配置变更。

本记录为数据库部署阶段；后续业务与 HTTPS 已上线，见[应用验收](../2026-10-24-k3s-application/README.md)。下述“尚未完成”保留该阶段的验收边界，当前状态见[发布状态](../../progress.md)。

## 环境

PostgreSQL `17.11`，StatefulSet `sems-test/postgres`，固定在 EC2 节点 `sems-k3s-worker`。使用已有发布的镜像 `ghcr.io/seventh720/swe5001-sems/postgres@sha256:426feb67931f53faf9d8640137b59c0e4d914baf55ea5c4405e434e203970a50`；本轮没有重跑漏洞扫描。

`data-postgres-0` PVC 绑定 worker 根 EBS 上的 local-path 目录，StorageClass 和 StatefulSet 均保留数据卷。声明容量 10 GiB 不是新建独立 EBS，也不是 local-path 实际强制配额。数据库只提供 ClusterIP，TCP 连接使用 SCRAM，NetworkPolicy 限制后端和备份工具 Pod 访问。数据库连接尚未启用 TLS。

## 最终结果

| 检查 | 结果 |
|---|---|
| 数据库就绪、版本和 Retain PVC | 通过 |
| 三个真实账号认证及 schema 所有权 | 通过；6 项跨 schema USAGE 拒绝，3 项 public CREATE 拒绝；错误密码被拒绝 |
| 从 server 节点到 worker 数据库的网络策略 | 允许的工具 Pod 能登录；未允许的 Pod 收到 Connection refused |
| 删除并重建 PostgreSQL Pod | 通过；Pod UID 改变，PVC/卷不变，探针行保留 |
| 异机备份和独立数据库恢复 | 通过；恢复后的探针行一致，临时数据库及探针表已删除 |
| 完整 K3s overlay server-side dry run | 21 个对象通过真实 Kubernetes API 校验，未部署业务应用 |

恢复检查使用临时数据库和 `--no-owner --no-privileges`，只证明逻辑数据可以恢复，不代表完整凭据/ACL 重建或灾难恢复演练。三个角色及 schema 权限另外独立验证。最终五组验收均通过，清理错误列表为空。

## 初次检查与修正

1. 第一次检查发现镜像默认 `pg_hba.conf` 对 loopback TCP 使用 trust，错误密码也能连接。增加独立 `pg_hba.conf`，所有 TCP 连接显式要求 `scram-sha-256`，通过 ConfigMap 挂载并重启数据库，原卷保留。见 `postgres-acceptance-before-tcp-auth.json` 和对应 `.txt`。
2. 第二次检查中，网络策略已拒绝未允许的客户端，返回 Connection refused；测试仅接受超时错误而判为失败。修正测试识别网络拒绝及超时，见 `postgres-acceptance-before-denial-classification.json` 和对应 `.txt`。

## 记录

- [postgres-acceptance.json](postgres-acceptance.json)、[原始输出](postgres-acceptance.txt)：最终五组验收。
- [首次认证检查](postgres-acceptance-before-tcp-auth.json)、[原始输出](postgres-acceptance-before-tcp-auth.txt)。
- [网络拒绝判定检查](postgres-acceptance-before-denial-classification.json)、[原始输出](postgres-acceptance-before-denial-classification.txt)。
- [selfhost-postgres-summary.json](selfhost-postgres-summary.json)：最终 Pod、PVC、实际镜像及配置摘要。
- [selfhost-application-server-dry-run.txt](selfhost-application-server-dry-run.txt)：完整 overlay 的真实 API dry run。
- [clean-backup-metadata.json](clean-backup-metadata.json)：最终干净备份的文件大小和 SHA256，不含备份数据。
- [RDS 网络清理](../2026-10-24-k3s-bootstrap/rds-network-cleanup.json)：仅清理先前创建且未使用的对象，从未创建 RDS 实例。

备份数据、JWT 私钥、数据库密码和 kubeconfig 均仅保留在本机被忽略的 `.secrets/k3s-cloud/`，不提交。

## 尚未完成

业务应用、Flyway 业务表、原 Lightsail 数据迁移、域名和可信 HTTPS 尚未接入。当前为单控制平面、单可用区、单数据库节点；worker 丢失时，本地卷不能自动转移至另一个节点。备份目前手动执行，没有 WAL 归档、PITR 或已经测量的生产恢复时间。步骤见 [K3s 环境](../../k3s.md)。
