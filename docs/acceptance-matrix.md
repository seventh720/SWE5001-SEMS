# Proposal 验收追踪

截至 2026-10-19：业务实现包含工作人员分配、核销与基础统计；历史本地证据见 [组织验收](evidence/2026-10-15-organization-upgrade/verification.md)及[通知验收](evidence/2026-10-16-notifications/verification.md)。[整场活动取消](evidence/2026-10-17-event-cancellation/verification.md)已实现并完成本地双实例并发与故障恢复验收，平台复用计时、云实验、安全门禁及回滚证据仍待补齐。取消验收覆盖 100 个并发报名请求与签到/退票/重复取消竞争、晚期事务失败回滚、Admission 停机、Catalog 重启和确认丢失恢复。已完成云端部署、HTTPS/健康检查和 JWT 有效期检查；云端负载、扩容收益及故障恢复目标实验尚未完成。当前版本进度和测试数字见[项目进度](progress.md)与[覆盖情况](test-coverage.md)。下面是目标清单，不是全部通过的结果。完整差距见[下一步计划](implementation-plan.zh-CN.md)。

| 目标 | 证据 |
|---|---|
| 业务修复与本地扩缩容 | [P1/P2 验收](evidence/2026-10-19-business-fixes/verification.md)：1 小时 JWT/重登、开始后 15 分钟截止检票、管理员保护、当前地点、分页、认证限流、Admission 2→3→2 动态路由；不替代下方云端负载目标 |
| API/边界 | 三份OpenAPI、独立镜像/部署、无跨库访问验证 |
| 完整流程 | 注册→授权组织者→发布→预订→出票→签到→统计 |
| 平台复用 | seminar/workshop共享能力；跨组织隔离与同组织协作；第三组织者配置入驻，记录步骤/时间/代码变化 |
| 一致性 | 两Admission副本，100请求争10个名额；数据库确认不超售；同键重试、异载荷拒绝、取消竞争、重复签到 |
| 性能 | ≥100活动/1000账号；预热后100 VU稳定10分钟；目标p95<3秒、意外错误<1%；业务拒绝单列 |
| 独立扩容 | Catalog 1/2副本且其他固定；Admission 1/2副本且其他固定；25/50/100 VU；相同每副本资源和数据/请求比例 |
| 恢复 | 分别停止一个Catalog/Admission副本，目标60秒恢复，无已提交订单丢失，验证安全重试 |
| 安全 | 匿名、跨组织、他人订单、未分配staff、内部API拒绝；HTTPS及扫描 |
| DevSecOps | lint/unit/contract/PostgreSQL integration；静态/依赖/secret/image扫描阻断；失败变更被拒，成功部署 |
| 回滚 | 单服务恢复兼容旧镜像，说明迁移不随镜像自动回滚 |

记录commit、镜像、配置、时间、数据、RPS、p95、意外错误、业务拒绝、CPU/内存/数据库利用率及原始结果。报告失败目标和瓶颈，不把启动两个副本视作扩容收益。证据存 docs/evidence/<date>-<experiment>/；验收结果必须来自本平台对应版本与部署环境。
