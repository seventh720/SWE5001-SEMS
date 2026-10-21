# 项目文档

当前状态只在[项目进度](progress.md)维护。以下说明按用途组织；历史检查和原始证据不替代当前发布状态。

## 当前系统与展示

- [项目进度与下一步](progress.md)：上线版本、本地修改、仓库与云端待办。
- [业务规则](functional-guide.md)：角色、活动生命周期、组织总览统计口径、预订/票券/检票、预约、筛选和分页。
- [架构决策](adr/0001-service-boundaries.md)：服务边界、一致性协议、扩容能力与部署限制。
- [课程要求和展示行动清单](implementation-plan.zh-CN.md)：课程/proposal 对照、展示结构和时间安排。
- [验收矩阵](acceptance-matrix.md)：目标与证据对应，未达到的目标保留为待办。

## 测试与运维

- [组织管理及线上 API 验收](evidence/2026-10-20-organization-management/verification.md)：总览、筛选、生命周期、闭环与临时数据清理。
- [测试覆盖](test-coverage.md)：实测数字、回归范围、覆盖边界。
- [CI](ci.md)：验收入口、独立测试环境和流水线。
- [云端环境](cloud-staging.md)：部署、备份和回滚注意事项。
- [发布管理](publication-management.md)、[改期协议](schedule-revision.md)：活动更新和跨服务同步。
- [组织升级](organization-upgrade.md)、[站内通知](in-app-notifications.md)：已有环境迁移与兼容边界。

- [扩容收益与可用性实验](performance-and-availability.md)：数据生成、负载、故障恢复、库存审计及 HA 声明边界。
- [pre前最终50活动复测](evidence/2026-10-22-cloud-capacity/README.md)：`f69d49d`在50场活动下的分档读取/混合结果、剩余504与冻结决定、库存审计与清理。
- [安全门禁与适用性](security.md)：扫描范围、依赖修复和有期限的 Spring 功能例外。

## 历史记录

- [阶段复查归档](archive/README.md)：保留当时版本、发现及结果，不作为当前待办清单。
- [原始验收证据](evidence/)：按日期保留；结果仅适用于记录中的版本和环境。

运行及团队协作见根目录 README。课程 PDF、proposal 和配图在仓库外维护，不复制进仓库。
