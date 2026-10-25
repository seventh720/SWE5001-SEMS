# Smart Event Management and Ticketing Platform

[English](README.md) | [简体中文](README.zh-CN.md)

SEMS 把组织成员、活动信息、报名要求、订单、票券和出席记录整合到一个共享平台中。组织者管理活动全流程，参与者保留自己的报名与二维码票券，工作人员使用同一份最新信息核销，减少多方信息分散和重复核对。

- **正式网站：**[swe5001.seventh720.com](https://swe5001.seventh720.com)
- **运维面板：**[Grafana](https://grafana.seventh720.com/d/sems-operations)，需要账号登录。
- **文档：**[文档索引](docs/README.md)、[业务规则](docs/functional-guide.md)、[平台现状](docs/progress.md)。

## 1. 架构与权限

前端使用 React/TypeScript。三个独立部署的 Spring Boot 服务分别维护 API、数据库凭据和 Flyway 迁移：

| 服务 | 职责 | PostgreSQL schema |
| --- | --- | --- |
| Identity | 账号、组织、成员、邀请与组织治理 | `identity` |
| Event Catalog | 活动、可见性、发布和修订 | `catalog` |
| Admission | 库存、订单、票券、工作人员分配、核销与通知 | `admission` |

服务之间通过认证 HTTP 协作。共用 PostgreSQL 实例，但各自使用独立 schema 和账号，应用不跨服务直接查库。库存由数据库锁和唯一请求键保护，跨服务操作使用持久化操作与幂等收据恢复。详见[架构决策](docs/adr/0001-service-boundaries.md)。

生产运行在两台 AWS EC2 上，采用 K3s/containerd。Identity、Catalog、Admission、Web 和 Gateway 在 `sems-prod` 各有两个副本，PostgreSQL 使用 Retain 本地卷。Prometheus、Grafana、Loki、Tempo 和 Telegram 告警位于独立的 `observability`。部署拓扑及运行限制见 [K3s 指南](docs/k3s.md)。

平台 ADMIN 创建组织、管理平台账号；组织内 `ORG_ADMIN`、`ORGANIZER`、`MEMBER` 决定业务权限，核销另需活动分配。已实现公开/组织内活动、版本化编辑、暂停/恢复/取消、免费报名、独立二维码票券、预约、通知及组织总览。具体权限和生命周期见[业务规则](docs/functional-guide.md)。

## 2. 本地启动

需要 Java 21、Maven 3.9+、Node.js 22、npm、OpenSSL、Python 3 和 Docker Compose v2 或更新版本。先启动 Docker，并用 `mvn -version` 确认 Maven 实际使用 Java 21。

```bash
git clone git@github.com:seventh720/SWE5001-SEMS.git
cd SWE5001-SEMS
bash scripts/setup-local.sh
mvn verify
npm --prefix apps/web ci
npm --prefix apps/web run build
docker compose --env-file .env -f deployment/compose.yaml -f deployment/compose.dev.yaml up --build -d
bash scripts/smoke.sh
```

访问 [localhost:18080](http://localhost:18080)。初始化生成私有 `.env` 和 `.secrets/`，默认管理员邮箱为 `admin@example.com`，随机密码见自己的 `.env`。不要提交凭据。重复初始化保留已有数据库密码和 RSA 密钥；修改环境变量不会自动修改已初始化的数据库密码。

前端热更新使用 `npm --prefix apps/web run dev`，端口为 **15173**，API 经 **18080** 网关访问。开发覆盖配置仅在 `127.0.0.1:15432` 开放 PostgreSQL，后端端口保持内部访问。服务重建、Navicat 与数据库迁移见[开发指南](docs/development.md)。

停机并保留本地数据库：

```bash
docker compose --env-file .env -f deployment/compose.yaml -f deployment/compose.dev.yaml down
```

## 3. 测试与交付

```bash
mvn verify
npm --prefix apps/web run lint
npm --prefix apps/web run test:coverage
npm --prefix apps/web run build
```

[CI](docs/ci.md)覆盖 lint、前后端测试、真实 API/数据库验收、源码安全与实际运行镜像检查。造数和故障注入只能使用独立测试环境。[测试说明](docs/test-coverage.md)区分各类检查的证明范围，[验收证据](docs/evidence/README.md)保留实测结果及失败记录。

符合条件的 `main` 流水线通过后，发布 GHCR 不可变镜像摘要，经 GitHub OIDC 和 AWS SSM 部署到 K3s。PR 检查不部署正式环境。[发布与回退](docs/k3s-cd.md)说明操作边界。GitHub Release 可记录带标签的稳定版本并附网站链接，网站继续由 AWS 托管。

## 4. 文档与目录

- [业务规则](docs/functional-guide.md) · [API 契约](contracts/README.md)
- [开发](docs/development.md) · [贡献流程](CONTRIBUTING.md) · [本地 Kubernetes](docs/kubernetes.md)
- [生产部署](docs/k3s.md) · [CI/CD](docs/k3s-cd.md) · [监控与追踪](docs/observability.md)
- [安全](docs/security.md) · [验收矩阵](docs/acceptance-matrix.md) · [性能实验](docs/performance-and-availability.md)
- [平台现状](docs/progress.md) · [待办](docs/roadmap.md) · [完整文档索引](docs/README.md)

`services/` 为后端，`apps/web/` 为前端，`contracts/` 为 API，`deployment/` 为运行配置，`scripts/` 为初始化、交付和验收工具。
