# 能力与验收矩阵

当前生产为两节点 EC2 K3s，业务位于 `sems-prod`，监控位于 `observability`。最新代码和部署检查见 [main CI/CD](https://github.com/seventh720/SWE5001-SEMS/actions/workflows/ci.yml?query=branch%3Amain)，原始结果见[证据索引](evidence/README.md)。

| 能力 | 已有验证 | 限制或待补 |
| --- | --- | --- |
| 多组织业务 | 组织治理、成员角色、跨组织拒绝、活动与成员组合筛选、总览口径 | 不包含企业 SSO/层级组织；节省工时未量化 |
| API 与数据边界 | 独立 API/schema/账号/迁移、跨 schema 拒绝、内部令牌与公网路径拒绝 | 自动 OpenAPI 符合性未接入 |
| 报名闭环 | 注册、授权、发布、报名、出票、核销、统计、预约、通知与取消 | API、浏览器和设备结果分别记录 |
| 并发与幂等 | 两个 Admission 实例竞争 10 名额、同键重放/异载荷、重复核销与取消竞争；数据库核对 | 正确性不代表吞吐提升 |
| 权限与会话 | JWT、实时成员/平台角色撤权、本人订单、工作人员分配、认证限流 | 当前网关限流不是分布式配额 |
| 副本与调度 | 五个应用各两个就绪副本且跨节点；独立副本调整与 Pod 重建 | 第三个同服务副本需要更多节点或不同测试拓扑；未启用 HPA |
| 故障恢复 | Catalog 冷启动/Pod 故障下订票与回执，全副本停止后的有界失败，发布/修订/取消/关闭恢复 | 主机故障、数据库切换和业务恢复 SLO 仍需单独测量 |
| 容量与扩容收益 | [历史容量数据](evidence/2026-10-22-cloud-capacity/README.md)：250 VU 读取通过，混合服务端门禁失败 | 当前 K3s 的 1/2 副本收益、十分钟稳态和高 VU 复测未完成 |
| 安全交付 | HTTPS、扫描、同次 image lock、main-only OIDC/SSM 发布和发布后验证 | [限定依赖例外](security.md)需复核；扫描不能替代权限验收 |
| 数据与回退 | 27 表/角色/凭据一致、Retain PV、发布前备份、兼容镜像回退和临时库恢复 | 定期异地备份、PITR 和完整灾难恢复待完成 |
| 可观测性 | 两节点/Pod/控制平面/数据库/公网指标、日志、三服务追踪、Grafana 登录及 Telegram 触发/恢复 | 栈内监控单实例，无独立于集群的外部故障探测 |

[测试说明](test-coverage.md)解释覆盖边界，[扩容实验](performance-and-availability.md)定义对照方法，[工程待办](roadmap.md)记录尚未完成的工作。所有结论保留版本、环境、参数和失败结果。

## 老师反馈核对（2026-11-06）

按提供的老师反馈核对当前版本库。下表区分已有实现、已有文档和报告交付；版本库外的报告未参与核验，不能据此认定全部建议已完成。报告及缺失设计材料待内容和要求确认后再着手补齐，本次仅记录核对结果。

| 建议 | 核对结果 | 证据与剩余工作 |
| --- | --- | --- |
| 流水线及 testing artifacts | 已配置产物保存 | [CI workflow](../.github/workflows/ci.yml)上传 lint、后端 Surefire/JaCoCo、前端覆盖率、API/数据库验收、安全和镜像检查记录；常规报告保留 7 天，镜像锁与部署记录保留 30 天。长期材料保存在[证据目录](evidence/README.md)。 |
| 所有测试结果在 report 中展示 | 未完成仓库内交付 | 当前版本库没有正式报告。需将单元/组件、API/数据库、浏览器、性能、故障、安全及交付验证汇入报告，标明版本、环境、结果、失败/补测与原始材料；未执行的实验单独注明。现有证据索引不能替代报告正文。 |
| 物理架构补充网络、集群/namespace、节点组、Pod 内容与控制平面 | 已有部署图与说明 | [K3s 物理部署](k3s.md#物理部署)包含 AWS VPC/子网、server/worker、节点分组、`sems-prod`/`observability`、各应用 Pod、PostgreSQL/存储及控制平面。当前为自建 K3s，使用 AWS VPC 与节点标签；EKS managed node group 仅为参考方案。 |
| 多视角架构图与架构决策 | 部分完成 | [领域与逻辑依赖、事务及部署取舍](adr/0001-service-boundaries.md)、[物理部署](k3s.md#物理部署)和[可观测性视图](observability.md)已有；类/对象、交互及数据关系视图仍需补齐，并在报告中说明各视图对应的设计决策。 |
| 1–2 个关键用例的 class/object 与 sequence diagrams | 未完成 | 当前版本库没有类图、对象图或时序图。可选“预订与幂等出票”和“整场取消与中断恢复”，按实际类、调用、事务、重试和失败路径绘制。 |
| 补充 cloud-native elements | 已有实现与说明 | [运行架构](adr/0001-service-boundaries.md#部署与取舍)与[K3s 配置](kubernetes.md)已有容器、独立 Deployment/Service、跨节点副本、探针、Secret/ConfigMap、持久卷、CI/CD 和指标/日志/追踪。报告需引用这些实际实现；HPA、节点自动扩容及数据库 HA 尚未实现。 |
| DDD、ERD 与微服务 bounded contexts | 部分完成 | [领域边界](adr/0001-service-boundaries.md#领域边界)已说明 Identity、Event Catalog、Admission 的所有权及 schema 隔离；当前缺少 ERD。需依据各服务 Flyway 迁移绘制服务内实体关系，跨服务标识引用与数据库外键分别表示。 |
