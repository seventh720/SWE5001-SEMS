# 项目文档

运行入口见根目录 [English README](../README.md) 和[中文 README](../README.zh-CN.md)。[发布状态](progress.md)维护最近已记录的版本及已知限制；历史验证结果仅适用于记录中的版本和环境。

## 使用与业务规则

- [业务规则](functional-guide.md)：角色、活动生命周期、组织总览、预订、票券、核销、预约、筛选和分页。
- [API 契约](../contracts/README.md)：三个服务的 OpenAPI 与跨服务认证。
- [发布管理](publication-management.md)：活动编辑、暂停、恢复和整场取消。
- [改期协议](schedule-revision.md)：版本化更新与跨服务状态同步。
- [站内通知](in-app-notifications.md)：业务通知、成员关系通知及升级步骤。

## 开发与架构

- [开发与数据库指南](development.md)：本地开发、容器重建、Navicat 和 Flyway 迁移。
- [贡献流程](../CONTRIBUTING.md)：分支、PR、代码审查与合并检查。
- [前端开发](../apps/web/README.md)：前端命令、页面约定与时间处理。
- [架构决策](adr/0001-service-boundaries.md)：服务边界、数据所有权、一致性协议和部署取舍。
- [技术改进计划](roadmap.md)：性能、恢复、可观察性与维护待办。

## 部署与安全

- [CI 操作](ci.md)：构建、验收、扫描、镜像交付和作业依赖。
- [云端环境](cloud-staging.md)：Lightsail、HTTPS、发布、备份和回滚。
- [组织升级](organization-upgrade.md)：已有环境的数据迁移与兼容要求。
- [安全门禁与适用性](security.md)：运行时控制、扫描范围和限时适用性例外。

## 验证与历史记录

- [验收矩阵](acceptance-matrix.md)：能力、质量目标和已完成验证的对应关系。
- [测试覆盖](test-coverage.md)：单元、组件、API、数据库和设备检查的覆盖边界。
- [性能与可用性实验](performance-and-availability.md)：数据、负载、副本对照、故障恢复和库存审计。
- [云端容量记录](evidence/2026-10-22-cloud-capacity/README.md)：已完成实验的参数、结果和清理记录。
- [原始验收证据](evidence/)：按日期保留，不替代当前发布状态。
- [阶段复查归档](archive/README.md)：历史版本的问题与检查结果。
