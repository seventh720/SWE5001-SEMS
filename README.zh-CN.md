# Smart Event Management and Ticketing Platform

[English](README.md) | [简体中文](README.zh-CN.md)

SEMS 是面向多组织的活动管理与票务平台，覆盖活动发布、免费报名、二维码票券与签到核销，支持成员角色、活动修订与取消、预约、通知和出席统计。

[正式网站](https://swe5001.seventh720.com) · [Grafana](https://grafana.seventh720.com/d/sems-operations)（需要登录）· [文档索引](docs/README.md)

## 系统架构

前端使用 React/TypeScript。三个独立部署的 Spring Boot 服务分别维护 API、数据库凭据和 Flyway 迁移：

| 服务 | 职责 | PostgreSQL schema |
| --- | --- | --- |
| Identity | 账号、组织、成员、邀请与组织治理 | `identity` |
| Event Catalog | 活动、可见性、发布和修订 | `catalog` |
| Admission | 库存、订单、票券、工作人员分配、核销与通知 | `admission` |

服务通过认证 HTTP 协作，使用独立的 PostgreSQL schema 和账号。数据库锁与唯一请求键保护库存，持久化操作与幂等收据支持跨服务恢复。详见[架构决策](docs/adr/0001-service-boundaries.md)和 [API 契约](contracts/README.md)。

生产运行在两台 AWS EC2 上，采用 K3s/containerd。Identity、Catalog、Admission、Web 和 Gateway 在 `sems-prod` 各有两个副本，PostgreSQL 使用 Retain 本地卷。Prometheus、Grafana、Loki、Tempo 和 Telegram 告警位于独立的 `observability`。部署拓扑及运行限制见 [K3s 指南](docs/k3s.md)。

平台 ADMIN 创建组织并管理平台账号；组织内 `ORG_ADMIN`、`ORGANIZER`、`MEMBER` 决定业务权限，核销另需活动分配。具体权限和活动生命周期见[业务规则](docs/functional-guide.md)。

## 本地启动

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

访问 [localhost:18080](http://localhost:18080)。初始化生成私有 `.env` 和 `.secrets/`，默认管理员邮箱为 `admin@example.com`，随机密码见本地 `.env`。

前端热更新使用 `npm --prefix apps/web run dev`，端口为 **15173**。数据库访问、服务重建、凭据管理与迁移见[开发指南](docs/development.md)。

停机并保留本地数据库：

```bash
docker compose --env-file .env -f deployment/compose.yaml -f deployment/compose.dev.yaml down
```

## 验证结果

```bash
mvn verify
npm --prefix apps/web run lint
npm --prefix apps/web run test:coverage
npm --prefix apps/web run build
```

[CI](docs/ci.md)覆盖 lint、前后端测试、API/数据库验收、源码安全与运行镜像检查。云端验证使用已部署的应用及独立测试数据：

| 测试 | 结果 |
| --- | --- |
| 100 VU 混合负载持续十分钟 | 稳态 178959 次请求，无客户端意外错误；最慢操作 p95 约 525 ms |
| 并发库存 | 100 个账号竞争 10 个名额：10 单成功、90 个售罄响应，SQL 数量一致 |
| 单/双副本对照 | Catalog 25/50/100 VU、Admission 25/50 VU |
| 分别删除 Catalog、Admission 一个 Pod | 业务恢复目标通过，已确认订单无丢失 |

每个云端条件只有一次样本。Admission 100 VU 单副本在预热时出现 16 次内部 504，服务端检查未通过，该档双副本未执行。参数和结果摘要见[云端验证记录](docs/evidence/2026-11-06-cloud-validation/README.md)；各类验证范围见[测试说明](docs/test-coverage.md)和[验收矩阵](docs/acceptance-matrix.md)。

## 部署与文档

符合条件的 `main` CI 发布 GHCR 不可变镜像摘要，经 GitHub OIDC 和 AWS SSM 部署到 K3s，并执行数据库备份和发布后检查。版本发布见[发布与回退](docs/k3s-cd.md)，指标、日志、追踪和告警见[可观测性](docs/observability.md)。

- [业务规则](docs/functional-guide.md) · [API 契约](contracts/README.md)
- [开发](docs/development.md) · [贡献流程](CONTRIBUTING.md) · [本地 Kubernetes](docs/kubernetes.md)
- [生产部署](docs/k3s.md) · [CI/CD](docs/k3s-cd.md) · [监控与追踪](docs/observability.md)
- [安全](docs/security.md) · [验收矩阵](docs/acceptance-matrix.md) · [性能实验](docs/performance-and-availability.md)
- [验收证据](docs/evidence/README.md) · [完整文档索引](docs/README.md)

`services/` 为后端，`apps/web/` 为前端，`contracts/` 为 API，`deployment/` 为运行配置，`scripts/` 为初始化、交付和验收工具。
