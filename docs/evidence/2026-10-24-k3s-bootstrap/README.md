# EC2 K3s 基础设施验收

日期：2026-10-24，新加坡时间。主网络检查为 21:45:23–21:46:13；HTTP 状态码另有补充记录。源提交为 `d3002d10a6f515b14f2013fc89f8805837b1f8ec`，工作区有未提交的部署配置变更。

后续环境调整：数据库采用集群内自建 PostgreSQL；本记录中为 RDS 临时准备的网络对象已清理，未创建 RDS 实例，见 [rds-network-cleanup.json](rds-network-cleanup.json)。下述状态与原始 JSON 保留为基础设施验收当时的记录，当前状态见 [K3s 环境](../../k3s.md)。

## 环境与结果

两台 `ap-southeast-1a` 的 EC2 t3.medium，Ubuntu 24.04 x86_64、各 30 GiB gp3。`sems-k3s-server` 为单控制平面并可调度工作负载，`sems-k3s-worker` 为 agent。两者安装 `v1.36.5+k3s1`、containerd `2.3.4-k3s1.36`，均 Ready。控制平面使用 K3s 内嵌 SQLite；节点间使用私网和 Flannel VXLAN，管理 API 通过本机 SSH 隧道访问。

| 检查 | 结果 |
|---|---|
| 两个真实节点 Ready | 通过 |
| 临时客户端和 HTTP Pod 就绪，分别固定在 server / worker | 通过 |
| server 上的 Pod 解析 Service DNS | 通过 |
| server 上的 Pod 经 ClusterIP Service 访问 worker 上的 HTTP Pod | 通过，响应 `SEMS_K3S_NETWORK_OK` |
| 分别访问两个 EC2 的公网 HTTP 入口，使用临时 Ingress Host | 通过，HTTP 200 且响应匹配 |
| 两个节点的 Metrics API | 通过，`kubectl top nodes` 可读取 |
| K3s 应用 overlay 的 server-side dry run | 16 个对象通过真实 Kubernetes API 校验 |
| RDS 网络 | 两个私有子网、仅 local 路由、安全组 5432 仅允许节点安全组、DB subnet group Complete |

临时 BusyBox 实际镜像 digest 为 `sha256:bdf57e528e45e4433820e045b29b4597825a1c9e38353532d90a01445013f82e`。测试 namespace 在检查后删除；`sems-test` 只创建了 namespace，尚无业务 Deployment、Pod 或 Ingress。网络资源标识见 `rds-network.json`。检查时新加坡区域 RDS 实例数量为 0。

## 记录

- [cluster-summary.json](cluster-summary.json)：节点、系统 Pod、实际镜像、应用配置摘要与状态边界。
- [network-smoke.json](network-smoke.json)：网络检查结果、节点/测试 Pod 分布及临时资源清理结果。
- [network-smoke.txt](network-smoke.txt)：主网络检查命令与原始输出。
- [public-http-status-check.txt](public-http-status-check.txt)：两个入口实际 HTTP 状态码与清理输出。
- [application-server-dry-run.txt](application-server-dry-run.txt)：应用配置的真实 API dry run 输出。
- [server-install.txt](server-install.txt)、[worker-install.txt](worker-install.txt)：固定版本下载、SHA256 校验和服务启动输出。
- [rds-network.json](rds-network.json)：独立数据库网络对象及创建后验证结果。
- [rds-network-cleanup.json](rds-network-cleanup.json)：切换到自建 PostgreSQL 后清理上述闲置对象的记录。

## 边界

这份记录验证云端 Kubernetes 基础设施与网络，不验证 SEMS 业务、可信 HTTPS、吞吐、独立扩容收益、故障恢复时间或回滚。RDS 数据库实例和应用尚未部署；既有 Lightsail 应用未切换。单控制平面、单可用区、默认单副本 Traefik 和未来 Single-AZ RDS 的单点仍需如实描述。

部署步骤和后续准备见 [K3s 环境](../../k3s.md)。密钥、加入 token、管理员 kubeconfig 和 AWS 临时凭据不包含在本记录中。
