# Proposal 验收追踪

更新：2026-10-21。已部署基线为 PR #20 的 `2f169d6`，[main CI 与实际部署](https://github.com/seventh720/SWE5001-SEMS/actions/runs/39466717243/attempts/2)通过。线上业务闭环、权限验收及用户手机扫码确认已完成；[云端容量基线](evidence/2026-10-21-cloud-capacity/README.md)发现网关连接额度瓶颈，修正待部署复测。下表列出 proposal 目标及证据边界，未完成项继续保留；当前状态见[项目进度](progress.md)，展示安排见[行动清单](implementation-plan.zh-CN.md)。

| 目标 | 证据 |
|---|---|
| 组织总览与管理筛选 | PR #18：组织管理员总览、筛选前分页、已结束活动拒绝重开及 SVG 星号；本地 58 后端/119 前端测试和定向 HTTP/桌面/390px 浏览器验收通过。组织管理自动验收与线上 API 闭环现已通过，[新验证记录](evidence/2026-10-20-organization-management/verification.md)包含清理结果；手机摄像头扫码已获用户确认通过，见[覆盖范围](test-coverage.md) |
| 业务修复与本地扩缩容 | [P1/P2 验收](evidence/2026-10-19-business-fixes/verification.md)：1 小时 JWT/重登、开始后 15 分钟截止检票、管理员保护、当前地点、分页、认证限流、Admission 2→3→2 动态路由；不替代下方云端负载目标 |
| API/边界 | 三份OpenAPI、独立镜像/部署、无跨库访问验证 |
| 完整流程 | 注册→授权组织者→发布→预订→出票→签到→统计 |
| 平台复用 | seminar/workshop共享能力；跨组织隔离与同组织协作；第三组织者配置入驻，记录步骤/时间/代码变化 |
| 一致性 | 两Admission副本，100请求争10个名额；数据库确认不超售；同键重试、异载荷拒绝、取消竞争、重复签到 |
| 性能 | 本轮 1000 账号/100 普通活动已造数、核验并清理；读取 250 VU / 混合 100 VU 短时通过，更高档停测。目标仍为预热后 100 VU 稳定十分钟、p95<3秒、意外错误<1%；待网关修正部署后补测 |
| 独立扩容 | Catalog 1/2副本且其他固定；Admission 1/2副本且其他固定；25/50/100 VU；相同每副本资源和数据/请求比例 |
| 恢复 | 分别停止一个Catalog/Admission副本，目标60秒恢复，无已提交订单丢失，验证安全重试 |
| 安全 | 匿名、跨组织、他人订单、未分配staff、内部API拒绝；HTTPS及扫描 |
| DevSecOps | lint/unit/contract/PostgreSQL integration；静态/依赖/secret/image扫描阻断；失败变更被拒，成功部署 |
| 回滚 | 单服务恢复兼容旧镜像，说明迁移不随镜像自动回滚 |

记录commit、镜像、配置、时间、数据、RPS、p95、意外错误、业务拒绝、CPU/内存/数据库利用率及原始结果。报告失败目标和瓶颈，不把启动两个副本视作扩容收益。证据存 docs/evidence/<date>-<experiment>/；验收结果必须来自本平台对应版本与部署环境。
