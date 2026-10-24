# Smart Event Management and Ticketing Platform

[English](README.md) | [简体中文](README.zh-CN.md)

SEMS 是 React + TypeScript、三个 Spring Boot 服务与 PostgreSQL 构成的共享活动票务平台。

已实现多组织权限、活动发布/编辑/暂停/取消、免费预订、独立二维码票券、工作人员核销、预约、站内通知，以及组织管理员总览。活动和成员管理支持服务端检索、组合筛选与分页；已结束活动不能编辑后重开。

[发布状态](docs/progress.md)记录最近发布和已知限制；[业务规则](docs/functional-guide.md)说明权限与统计口径；[测试覆盖](docs/test-coverage.md)区分单元测试、API 验收和历史覆盖率。JWT 为 1 小时；检票窗口为开始前 15 分钟至开始后 15 分钟（截止不含，若更早结束则提前关闭）。

## 1. 架构与权限

Identity 管理账号、组织、成员及邀请；Event Catalog 管理活动、可见性、发布及修订；Admission 管理库存、订单、票券、签到及通知。三服务有独立 schema、凭据和迁移，通过认证 HTTP 协作。

平台 ADMIN 管理平台账号及组织；组织内 ORG_ADMIN、ORGANIZER、MEMBER 决定业务权限；检票还要求活动分配。旧全局 ORGANIZER/STAFF 不再授予业务访问。已有环境先阅读[组织升级](docs/organization-upgrade.md)与[通知升级](docs/in-app-notifications.md)。

## 2. 本地启动

需要 Java 21、Maven 3.9+、Node.js 22、npm、OpenSSL、Python 3 和 Docker Compose v2。用 `mvn -version` 确认 Maven 实际使用 Java 21；高版本编译器的 `--release 21` 不等同于 CI 的 Java 21 编译器。

```bash
git clone git@github.com:seventh720/SWE5001-SEMS.git
cd SWE5001-SEMS
bash scripts/setup-local.sh
mvn verify
npm --prefix apps/web ci
npm --prefix apps/web test
npm --prefix apps/web run build
docker compose --env-file .env -f deployment/compose.yaml -f deployment/compose.dev.yaml up --build -d
bash scripts/smoke.sh
```

访问 [本地平台](http://localhost:18080)。首次配置脚本生成 `.env` 和 `.secrets/`；重复运行会补充缺少的内部服务令牌，不覆盖已有数据库密码或 RSA 密钥。管理员邮箱默认 `admin@example.com`，随机密码见本地 `.env` 的 `SEMS_BOOTSTRAP_ADMIN_PASSWORD`，不要提交或分享该文件。首次初始化后可清空 bootstrap 配置，已存管理员仍可登录。

数据库凭据仅在新数据卷首次初始化时应用；修改 `.env` 不会自动修改已有数据库密码。普通停机保留数据：

```bash
docker compose --env-file .env -f deployment/compose.yaml -f deployment/compose.dev.yaml down
```

开发前端可执行 `npm --prefix apps/web run dev`，访问15173端口，API代理到18080网关。生产构建的页面运行在网关根路径。日期输入使用应用自定义英文日历和时间选择器，统一为新加坡时间（UTC+08:00），提交为 UTC。本地开发覆盖配置仅向 `127.0.0.1:15432` 开放数据库；CI 使用的基础 Compose 文件不开放数据库端口。

这是本地 HTTP 配置。[swe5001.seventh720.com](https://swe5001.seventh720.com)现运行于 [EC2 K3s 环境](docs/k3s.md)，原账号与业务数据已迁入。[K3s 发布流程](docs/k3s-cd.md)说明 main 自动交付，[切换记录](docs/evidence/2026-10-25-k3s-cutover/README.md)包含数据、证书和 DNS 验收。[Lightsail 指南](docs/cloud-staging.md)保留历史步骤。运行凭据使用受限主机文件和 Kubernetes Secret。

## 3. 验收流程

1. 注册组织管理员、成员、参与者账号；平台管理员创建两个组织并指定管理员。
2. 组织管理员邀请成员，成员在 Notifications 接受；创建 seminar 与 workshop，配置免费票种并发布。
3. 参与者浏览、预订并查看二维码/手动票码；检查他人和其他组织无法访问管理数据。
4. 为活动分配工作人员，核销票码两次，确认 attendance 仅增加一次；检查未分配人员被拒绝。
5. 取消另一笔尚未签到且未开始的订单，检查库存仅释放一次；验证暂停/恢复，以及新组织通过配置入驻。
6. 以组织管理员查看活动数、有效票数、签到数和签到率；组合活动状态/时间/可见性及成员角色/状态筛选，翻页后进入活动详情。验证普通组织者不能访问组织总览，已结束活动不能改期重开。

## 4. 测试与 CI

```bash
mvn verify
npm --prefix apps/web run lint
npm --prefix apps/web run test:coverage
npm --prefix apps/web run build
```

数据库/API 验收需要隔离的测试环境；部分脚本会停止服务、重启及制造故障。Compose 入口见 [CI operations](docs/ci.md)，Kubernetes 适配器见 [K3s 操作](docs/k3s.md)。历史证据见 [docs/evidence](docs/evidence/)。

## 5. 目录与文档

- `services/` — 后端服务、迁移和测试。
- `apps/web/` — 前端和界面测试。
- `contracts/` — [OpenAPI 契约](contracts/README.md)。
- `deployment/` — Compose、Kubernetes 环境配置、网关和数据库配置。
- `scripts/` — 环境初始化和可重用验收脚本。
- [文档索引 / Documentation index](docs/README.md)
- [开发与数据库指南](docs/development.md)
- [Kubernetes 配置与云端模板](docs/kubernetes.md)
- [EC2 K3s 环境](docs/k3s.md)
- [贡献流程](CONTRIBUTING.md)
- [技术改进计划](docs/roadmap.md)
- [当前业务规则](docs/functional-guide.md)
- [架构决策](docs/adr/0001-service-boundaries.md)
- [验收矩阵](docs/acceptance-matrix.md)
