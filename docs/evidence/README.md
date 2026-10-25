# 验收证据

原始记录按测试日期、版本和环境保留。它们用于复核已执行的检查；当前部署方式见[平台现状](../progress.md)。首次失败、补测和最终结果均保留，不能把旧环境的容量或覆盖率作为当前版本成绩。

## 部署与运行

| 证据 | 范围 |
| --- | --- |
| [本地 Kubernetes](2026-10-24-kubernetes-local/README.md) | 独立 kind、业务并发和数据库隔离 |
| [K3s 节点与网络](2026-10-24-k3s-bootstrap/README.md) | 两台 EC2、控制平面、跨节点通信与入口 |
| [自建 PostgreSQL](2026-10-24-k3s-postgres/README.md) | 账号/schema/网络隔离、持久化和临时库恢复 |
| [应用与 HTTPS](2026-10-24-k3s-application/README.md) | 双节点应用、可信 TLS 和独立副本操作 |
| [K3s 完整业务回归](2026-10-24-k3s-regression/README.md) | API、跨节点并发、Catalog 故障、库存审计及浏览器 |
| [发布与回退](2026-10-25-k3s-cd/README.md) | SSM/OIDC 发布、失败候选拒绝及兼容镜像回退 |
| [原数据切换](2026-10-25-k3s-cutover/README.md) | 27 张表、账号/JWT、域名、证书和共享主机保护 |
| [可观测性](2026-10-25-observability/README.md) | 指标、日志、三服务追踪、Telegram 及 Grafana HTTPS |
| [生产 namespace](2026-10-25-production-namespace/README.md) | 数据卷重新绑定、数据/凭据一致及监控迁移 |

最新应用验证、镜像锁和发布结果从 [GitHub Actions](https://github.com/seventh720/SWE5001-SEMS/actions/workflows/ci.yml) 的对应运行与 artifacts 查阅。仓库内的历史部署记录不随新发布改写。

## 业务与质量

- [组织模型升级](2026-10-15-organization-upgrade/verification.md)、[组织治理](2026-10-17-organization-governance/verification.md)、[组织管理](2026-10-20-organization-management/verification.md)。
- [业务通知](2026-10-16-notifications/verification.md)、[成员通知](2026-10-17-membership-notifications/verification.md)。
- [整场取消](2026-10-17-event-cancellation/verification.md)、[发布前协议修正](2026-10-17-predeployment-fixes/verification.md)、[业务回归](2026-10-19-business-fixes/verification.md)。
- [历史覆盖率分子与分母](2026-10-19-coverage-review/summary.json)、[交付工具验证](2026-10-19-delivery-tooling/summary.json)。

## 性能

[2026-10-22 容量实验](2026-10-22-cloud-capacity/README.md)记录当时的测试版本、50 活动/1000 账号、已执行档位、内部 504 失败和清理情况。该轮未执行 500/1000 VU，不用于证明当前 K3s 的容量或扩容收益。新的实验方法见[性能与扩容实验](../performance-and-availability.md)。

凭据、JWT、票凭证、数据库 dump 和私有数据集不进入本目录。CI 短时 smoke、功能正确性、容量、扩容收益与恢复时间分别报告。
