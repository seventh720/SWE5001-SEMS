# 项目文档

产品介绍与本地启动见 [English README](../README.md) 或[中文 README](../README.zh-CN.md)。本文按业务、架构、运行和验证组织项目文档。

## 使用与业务

| 文档 | 内容 |
| --- | --- |
| [业务规则](functional-guide.md) | 角色、组织、活动生命周期、订单、票券、核销与统计口径 |
| [API 契约](../contracts/README.md) | 三个服务的 OpenAPI 和内部认证 |
| [发布管理](publication-management.md) | 统一编辑、暂停、恢复和整场取消 |
| [改期协议](schedule-revision.md) | 版本化修订和跨服务恢复 |
| [站内通知](in-app-notifications.md) | 业务通知、成员关系通知和组织关闭 |

## 开发与架构

| 文档 | 内容 |
| --- | --- |
| [开发与数据库](development.md) | 本地开发、服务重建、Navicat 和 Flyway |
| [前端开发](../apps/web/README.md) | 页面、时间输入与前端命令 |
| [架构决策](adr/0001-service-boundaries.md) | 服务边界、数据所有权、事务和重试取舍 |
| [Kubernetes 配置](kubernetes.md) | 配置结构、离线渲染和独立 kind 环境 |
| [旧库组织升级](organization-upgrade.md) | 个人 organizer 模型旧库的迁移与版本兼容 |
| [贡献流程](../CONTRIBUTING.md) | 分支、审查、合并与凭据规则 |

## 生产与验证

| 文档 | 内容 |
| --- | --- |
| [EC2 K3s 运维](k3s.md) | 网络、控制平面、Pod、存储和日常命令 |
| [CI 流水线](ci.md) | 六项检查、测试入口与产物 |
| [发布与回退](k3s-cd.md) | OIDC/SSM、digest、备份、验证和回退 |
| [监控与追踪](observability.md) | Grafana、Prometheus、Loki、Tempo、Telegram |
| [安全](security.md) | 访问控制、扫描与限定依赖例外 |
| [测试覆盖](test-coverage.md) | 单元、API、数据库、浏览器及覆盖率边界 |
| [验收矩阵](acceptance-matrix.md) | 业务、架构与运行能力的验证范围及限制 |
| [性能与扩容实验](performance-and-availability.md) | 负载场景、副本对照、恢复指标和判定方法 |
| [云端验证结果](evidence/2026-11-06-cloud-validation/README.md) | 十分钟混合负载、扩容对照、并发库存、Pod 故障及数据恢复检查 |
| [验收证据索引](evidence/README.md) | 按环境和版本保留的原始结果 |
