# 当前平台状态

正式入口：[swe5001.seventh720.com](https://swe5001.seventh720.com)。运维入口：[Grafana](https://grafana.seventh720.com/d/sems-operations)，需要登录。代码与部署状态以 [main CI/CD](https://github.com/seventh720/SWE5001-SEMS/actions/workflows/ci.yml?query=branch%3Amain) 和实际运行镜像为准。

## 当前实现

| 范围 | 状态 |
| --- | --- |
| 业务 | 组织与成员治理、活动发布/修订/取消、免费报名、二维码票券、核销、预约、通知及组织总览 |
| 服务边界 | Identity、Event Catalog、Admission 独立部署，分别拥有 schema、凭据和迁移 |
| 生产运行 | 新加坡区域两台 EC2，K3s/containerd，单控制平面、单可用区 |
| 应用副本 | 五个应用各两个副本，分布在两个节点；业务 namespace 为 `sems-prod` |
| 数据 | 自建 PostgreSQL 单实例，worker 本地 Retain 卷；原账号和业务数据保留 |
| 交付 | main CI/CD 已验证：六项检查、GHCR digest、GitHub OIDC、AWS SSM、备份及发布后校验 |
| 可观测性 | `observability` 中的指标、日志、链路追踪、Grafana 和 Telegram 触发/恢复通知 |
| 访问 | 公网 HTTPS；内部 API、数据库与监控后端仅内部访问；集群管理经 SSH 隧道 |

正式数据和 JWT 密钥已完成迁移，旧 `sems-test` namespace 及过渡 Ingress 已清理。旧 Lightsail 仍承载 SWE5006，并保留 SEMS 的缓存过渡代理；不再作为 SEMS 应用发布目标。部署细节见 [K3s 运维](k3s.md)。

## 验证范围

main 的构建、集成、安全、镜像和实际 K3s 发布均已通过。业务回归覆盖权限、并发库存、重放、核销、取消和跨服务中断恢复。Catalog 只读调用对瞬态 502/503/504 最多重试一次，写操作依赖业务幂等协议。完整结果和首次失败记录见[验收证据](evidence/README.md)。

历史容量实验曾通过 250 VU 读取，混合负载的服务端门禁失败；这些结果属于当时版本和 Lightsail 环境。当前 K3s 尚未完成相同负载复测、十分钟稳态或受控 1/2 副本收益对照。功能回归通过不代表这些容量目标已达成。

## 已知限制

- 单控制平面、单可用区、单 PostgreSQL；本地卷依赖原节点。入口和监控也存在单点。
- 未配置 HPA、节点自动扩容、数据库自动切换、定期异地备份或 PITR。
- 同一服务使用节点硬反亲和；当前两个节点最多放置两个副本，第三个副本需要额外可调度节点或另行设计测试拓扑。
- 库存热点由同一 sales 行锁串行化，服务副本增加后的收益需要实测。
- 未接入自动 OpenAPI 符合性门禁；设备覆盖和数据库灾难恢复仍有待补充。

后续工作见[工程待办](roadmap.md)，测试计划见[性能与扩容实验](performance-and-availability.md)。
