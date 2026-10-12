# Smart Event Management and Ticketing Platform

[English](README.md) | [简体中文](README.zh-CN.md)

SEMS 是面向独立组织者与参与者的共享活动与票务平台。采用 React + TypeScript、三个独立 Spring Boot 服务和 PostgreSQL。

本轮已实现：注册登录、RSA JWT、管理员角色授权、组织者活动草稿创建/列表/详情/编辑、所有权隔离及乐观版本冲突。本轮另已实现免费票种、配额/销售窗口校验、可重试发布和公开活动浏览。预订、取消、出票和签到仍待实现。

## 1. 架构与角色

| Service | Data ownership | Status |
|---|---|---|
| Identity | Accounts, passwords, roles | Implemented |
| Event Catalog | Organizer-owned event drafts | Implemented |
| Admission | Inventory, bookings, tickets, check-in | Free ticket inventory and sales activation |

三服务分别拥有 schema、数据库账号和 Flyway 迁移，无跨服务外键或查询。Identity 持 RSA 私钥，另外两个服务只持公钥；令牌校验签名、issuer、audience 和有效期。

角色为 `ATTENDEE`、`ORGANIZER`、`STAFF`、`ADMIN`。注册默认 ATTENDEE；管理员可分配角色。ADMIN 不绕过活动所有权。角色变更后重新登录；已有令牌最多继续有效30分钟，本轮无即时撤销机制。

## 2. 本地启动

需要 Java 21、Maven 3.9+、Node.js 22、npm、OpenSSL、Python 3 和 Docker Compose v2。

```bash
git clone git@github.com:seventh720/SWE5001-SMES.git
cd SWE5001-SMES
bash scripts/setup-local.sh
mvn verify
npm --prefix apps/web ci
npm --prefix apps/web test
npm --prefix apps/web run build
docker compose --env-file .env -f deployment/compose.yaml up --build -d
bash scripts/smoke.sh
```

访问 [本地平台](http://localhost:8080)。首次配置脚本生成 `.env` 和 `.secrets/`；重复运行会补充缺少的内部服务令牌，不覆盖已有数据库密码或 RSA 密钥。管理员邮箱默认 `admin@example.com`，随机密码见本地 `.env` 的 `SEMS_BOOTSTRAP_ADMIN_PASSWORD`，不要提交或分享该文件。首次初始化后可清空 bootstrap 配置，已存管理员仍可登录。

数据库凭据仅在新数据卷首次初始化时应用；修改 `.env` 不会自动修改已有数据库密码。普通停机保留数据：

```bash
docker compose --env-file .env -f deployment/compose.yaml down
```

开发前端可执行 `npm --prefix apps/web run dev`，访问5173端口，API代理到8080网关。生产构建的页面运行在网关根路径。日期输入使用浏览器时区，提交为UTC；数据库无需向主机暴露端口。

这是本地HTTP配置，云端仍需HTTPS、密钥管理和部署配置。

## 3. 验收流程

1. 注册两个普通账号。
2. 以管理员登录“Manage users and roles”，为两个账号勾选 ORGANIZER 并保存。
3. 两个账号分别重新登录，进入“My events”。
4. 创建草稿，刷新后编辑；第二个账号列表不显示第一个账号的草稿。
5. 同一草稿在两个窗口编辑，后提交的旧版本返回冲突，可点击重新加载。

6. 打开“Ticket setup & publication”，配置总配额不超过容量的免费票种并保存。开始票种配置后活动时间和容量固定。
7. 确认发布后进入公开活动页。依赖故障时活动保持发布中且不公开，恢复任务自动继续处理。

## 4. 测试与 CI


```bash
mvn verify
npm --prefix apps/web test
npm --prefix apps/web run build
bash scripts/check-db-isolation.sh
set -a
source .env
set +a
python3 scripts/publication-acceptance.py
```

最后两项需要运行中的 Compose 环境；发布验收会主动停止/重启测试容器，务必使用独立测试环境；验收脚本会创建带唯一后缀的测试账号与草稿，建议使用独立测试数据卷。CI 分别展示后端、前端和集成验收状态，生成 JaCoCo/Vitest 行与分支覆盖率，并在临时环境运行同样检查，涵盖认证、权限、schema隔离、输入校验、持久化和并发版本冲突。构建结果经已有Telegram通知发送，日志/JAR保留7天。详见 [CI说明](docs/ci.md)。

## 5. 目录与文档

- `services/`: independent backend services and migrations.
- `apps/web/`: React application and UI tests.
- `contracts/`: current OpenAPI specifications.
- `deployment/`: gateway, database initialization and Compose.
- `scripts/`: local setup, readiness and acceptance checks.
- [Implementation plan](docs/implementation-plan.zh-CN.md)
- [API contracts](contracts/README.md)
- [Architecture](docs/adr/0001-service-boundaries.md)
- [Acceptance targets](docs/acceptance-matrix.md)

通过短分支与PR集成，业务变更同时提交测试和契约。Proposal与配图独立存放，不纳入代码仓库。
