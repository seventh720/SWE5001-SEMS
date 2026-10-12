# Smart Event Management and Ticketing Platform

[English](README.md) | [简体中文](README.zh-CN.md)

SEMS 是面向独立组织者与参与者的共享活动与票务平台，计划采用三个可独立部署的 Spring Boot 服务和一个 React Web 应用。组织者管理自己的活动，参与者通过统一目录发现活动。

## 1. 项目状态

当前仓库包含三个服务启动入口、健康检查、Dockerfile、本地网关和 Docker Compose 配置。业务 API、认证、数据库、Web 应用与云部署尚未实现，当前没有自动化业务测试。

核心流程为：发布活动 → 免费预订 → 签发个人票券 → 工作人员签到 → 出席统计。付费票、支付服务以及外部邮件和短信不在核心范围内。

## 2. 架构与目录

| 路径 | 职责 |
|---|---|
| `services/identity/` | 账号、认证与角色 |
| `services/event-catalog/` | 活动所有权、详情、发布与发现 |
| `services/admission/` | 票种、库存、订单、票券、工作人员分配与签到 |
| `apps/web/` | 计划中的 React + TypeScript 应用，目前只有说明文档 |
| `contracts/` | API 契约规划，业务 OpenAPI 规范待编写 |
| `deployment/` | 本地 Compose 配置和 Nginx 网关 |
| `docs/` | 实施计划、架构决策与验收标准 |

每个服务生成独立的可执行 JAR 和容器镜像。数据库设计要求每个服务拥有独立的 PostgreSQL schema、凭据与迁移。服务之间不得共享 JPA 实体、Repository 或执行跨 schema 查询。库存、订单与票券变更在 Admission 本地事务内完成。

## 3. 开发环境

| 工具 | 版本 |
|---|---|
| Java | 21 |
| Maven | 3.9+ |
| Docker Engine 或 Docker Desktop | 包含 Docker Compose v2 |
| Spring Boot | 3.5.16，在根 POM 中固定 |

运行当前骨架不需要 Node.js 或 PostgreSQL；Web 与持久化实现后再补充对应环境配置。

## 4. 首次启动

克隆仓库并进入目录：

```bash
git clone git@github.com:seventh720/SWE5001-SMES.git
cd SWE5001-SMES
```

已有本地代码时，直接从代码仓库根目录执行后续命令。

### 方式 A：Docker 运行

先构建 JAR，再构建镜像：

```bash
mvn verify
docker compose -f deployment/compose.yaml up --build
```

本地网关地址为 `http://localhost:8080`。检查三个服务：

```bash
curl --fail http://localhost:8080/health/identity
curl --fail http://localhost:8080/health/event-catalog
curl --fail http://localhost:8080/health/admission
```

就绪响应应显示 `UP`。根路径返回 404，因为目前没有 Web 界面与业务路由。本地 Compose 使用 HTTP，不是生产部署配置。

停止容器：

```bash
docker compose -f deployment/compose.yaml down
```

### 方式 B：本地运行服务

在三个独立终端中，分别从仓库根目录执行：

```bash
mvn -pl services/identity spring-boot:run
```

```bash
mvn -pl services/event-catalog spring-boot:run
```

```bash
mvn -pl services/admission spring-boot:run
```

| 服务 | 默认端口 | 就绪检查路径 |
|---|---|---|
| Identity | 8081 | `/actuator/health/readiness` |
| Event Catalog | 8082 | `/actuator/health/readiness` |
| Admission | 8083 | `/actuator/health/readiness` |

可使用 `SERVER_PORT` 覆盖服务端口。此方式直接运行服务，不启动网关。使用 Ctrl+C 停止对应进程。

## 5. 构建与检查

```bash
mvn verify
docker compose -f deployment/compose.yaml config --quiet
```

Platform CI 在推送 `main`、向 `main` 提交 PR 或手动触发时运行。使用 Java 21 构建三服务、验证 Compose、构建并启动容器，经网关检查三服务就绪状态。日志和成功构建的 JAR 保留7天。本地启动 Compose 后可运行 `bash scripts/smoke.sh` 进行相同检查。

Telegram 通过仓库 Actions Secrets `TELEGRAM_TOKEN` 和 `TELEGRAM_TO` 发送构建结果和运行链接。缺少配置时跳过，通知失败不影响构建结果；Fork 和 Dependabot PR 跳过通知。

云部署、镜像发布、安全扫描与业务测试仍待接入；当前验证服务骨架，不代表业务验收。详见 [CI 运维说明](docs/ci.md)。

## 6. 开发路线

1. 定义版本化 API、服务独立持久化、认证与网关路由。
2. 实现账号入驻、组织者所有权、活动草稿和目录发现。
3. 完成免费预订、库存保护、出票、取消和工作人员签到。
4. 联调 Web 应用，演示两个独立组织者共享平台能力。
5. 完成云部署、安全检查、独立扩容、并发与恢复实验。

## 7. 协作与文档

采用短期分支与 PR 集成。业务变更同时提交相关测试、API 契约和数据库迁移。密钥与本地环境配置不进入版本控制。

- [实施计划](docs/implementation-plan.zh-CN.md)
- [服务边界与一致性决策](docs/adr/0001-service-boundaries.md)
- [验收标准](docs/acceptance-matrix.md)

Proposal 与配图独立存放，不纳入代码仓库。
