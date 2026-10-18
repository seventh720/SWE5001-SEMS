# Smart Event Management and Ticketing Platform

[English](README.md) | [简体中文](README.zh-CN.md)

SEMS 是 React + TypeScript、三个 Spring Boot 服务与 PostgreSQL 构成的共享活动票务平台。

已实现组织与成员权限、活动发布/编辑/暂停、免费预订、独立二维码票券、参与者及整场活动取消、工作人员核销、基础统计及站内通知。[Lightsail HTTPS 测试环境](docs/cloud-staging.md)已部署，已配置 main 分支的 GitHub Actions 自动部署；扩容/故障实验、镜像仓库和安全门禁仍需完成。当前进度见 [Proposal 对照与下一步](docs/implementation-plan.zh-CN.md)。

超管降权即时失效、可恢复的组织注销和成员服务端分页已修复。版本化镜像交付、安全门禁与云端实测仍需完成，详见[本轮整体检查](docs/implementation-plan.zh-CN.md)。
当前上线版本、本地完成项和待办见[项目进度](docs/progress.md)；测试范围见[覆盖情况](docs/test-coverage.md)。JWT 为 1 小时；检票窗口为开始前 15 分钟至开始后 15 分钟（截止不含，若更早结束则提前关闭）。

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

这是本地 HTTP 配置。[云端覆盖配置](docs/cloud-staging.md)已有 HTTPS 和自动部署；运行密钥目前存放于受限主机文件，尚未接入云托管密钥服务。

## 3. 验收流程 / Acceptance walkthrough

1. 注册组织管理员、成员、参与者账号；平台管理员创建两个组织并指定管理员。
2. 组织管理员邀请成员，成员在 Notifications 接受；创建 seminar 与 workshop，配置免费票种并发布。
3. 参与者浏览、预订并查看二维码/手动票码；检查他人和其他组织无法访问管理数据。
4. 为活动分配工作人员，核销票码两次，确认 attendance 仅增加一次；检查未分配人员被拒绝。
5. 取消另一笔尚未签到且未开始的订单，检查库存仅释放一次；演示暂停/恢复与第三组织无代码入驻。

## 4. Tests and CI

```bash
mvn verify
npm --prefix apps/web run test:coverage
npm --prefix apps/web run build
```

数据库/API 验收需要独立、可丢弃的 Compose 环境；部分脚本会停止服务、重启及制造故障。完整入口、隔离要求和现有流水线能力见 [CI operations](docs/ci.md)。历史证据见 [docs/evidence](docs/evidence/)。

## 5. Layout and documentation

- `services/` — backend services, migrations and tests.
- `apps/web/` — frontend and UI tests.
- `contracts/` — [OpenAPI contracts](contracts/README.md).
- `deployment/` — local Compose, gateway and database setup.
- `scripts/` — setup and reusable acceptance checks.
- [文档索引 / Documentation index](docs/README.md)
- [Proposal 对照与下一步](docs/implementation-plan.zh-CN.md)
- [当前业务规则](docs/functional-guide.md)
- [架构决策](docs/adr/0001-service-boundaries.md)
- [验收矩阵](docs/acceptance-matrix.md)

Proposal 与配图独立存放，不纳入代码仓库。

## 6. 前后端日常开发

以下命令均从仓库根目录执行。每位组员使用自己的本地数据库、`.env` 和 RSA 密钥，不共用开发数据库。运行 Compose 前先启动 Docker。本项目使用独立宿主机端口，其他应用可以继续占用 5432、8080 和 5173。

| 组件 | 宿主机地址 | 用途 |
|---|---|---|
| 前端热更新 | `http://localhost:15173` | Vite 开发服务，API 请求代理到网关 |
| 网关与构建后的前端 | `http://localhost:18080` | API 统一入口及前端构建产物 |
| Navicat 连接 PostgreSQL | `127.0.0.1:15432` | 仅在启用 `deployment/compose.dev.yaml` 时开放 |
| 后端服务 | 仅 Compose 内网 | Identity 8081、Catalog 8082、Admission 8083，不映射到宿主机 |

PostgreSQL 在 Docker **内部**仍监听 5432，服务 JDBC 地址保持 `postgres:5432`；15432 供宿主机客户端使用。Compose 项目名为 `sems-platform`，使用自己的 `platform-db` 数据卷。

**已有本地环境升级：**拉取代码后，重新执行第 2 节包含两个 Compose 文件的启动命令，应用新的端口映射并保留原数据库卷；重启 Vite，同时更新浏览器书签和 Navicat 连接。

### 前端开发

先按第 2 节启动完整服务，再另开终端：

```bash
npm --prefix apps/web ci
npm --prefix apps/web run dev
```

访问 `http://localhost:15173`，修改 `apps/web/src/` 后自动热更新。15173 被占用时会明确报错，不会悄悄换端口。登录与业务 API 使用 18080 网关后的真实服务。

提交前执行：

```bash
npm --prefix apps/web run test:coverage
npm --prefix apps/web run build
```

构建包含 TypeScript 检查，覆盖率报告为 `apps/web/coverage/index.html`。构建后如需更新 18080 上的前端页面：

```bash
docker compose --env-file .env -f deployment/compose.yaml -f deployment/compose.dev.yaml up --build -d web
docker compose --env-file .env -f deployment/compose.yaml -f deployment/compose.dev.yaml restart gateway
```

### 后端开发

根据任务修改 `services/identity`、`services/event-catalog` 或 `services/admission`。团队标准启动方式是在 Docker 中运行三个服务；IDE 修改不会自动更新容器。先生成 JAR，再重新构建服务镜像：

```bash
mvn verify
docker compose --env-file .env -f deployment/compose.yaml -f deployment/compose.dev.yaml up --build -d identity event-catalog admission
docker compose --env-file .env -f deployment/compose.yaml -f deployment/compose.dev.yaml restart gateway
bash scripts/smoke.sh
```

单模块检查可用 `mvn -pl services/event-catalog -am verify`，替换为实际修改的模块。查看运行状态和日志：

```bash
docker compose --env-file .env -f deployment/compose.yaml -f deployment/compose.dev.yaml ps
docker compose --env-file .env -f deployment/compose.yaml -f deployment/compose.dev.yaml logs --tail=100 -f identity event-catalog admission
```

Ctrl+C 退出日志跟随。接口变化应同步更新 `contracts/` 中的契约和前端调用。服务间地址及凭据由 Compose 提供，不能仅在仓库根目录执行 `mvn spring-boot:run` 来启动本项目。

## 7. Navicat 连接与数据库变更

通过本地开发覆盖配置启动 PostgreSQL（完整启动流程已包含这一步）：

```bash
docker compose --env-file .env -f deployment/compose.yaml -f deployment/compose.dev.yaml up -d postgres
```

在 Navicat 中新建 **PostgreSQL** 连接，点击**测试连接**，成功后打开数据库 `sems`。主机统一为 `127.0.0.1`，端口为 **15432**，账号如下。密码填写自己本地 `.env` 中对应变量的实际值，不是变量名。

| 建议连接名称 | 用户名 | 密码变量 | Schema |
|---|---|---|---|
| SEMS Platform - Identity | `identity_app` | `IDENTITY_DB_PASSWORD` | `identity` |
| SEMS Platform - Catalog | `catalog_app` | `CATALOG_DB_PASSWORD` | `catalog` |
| SEMS Platform - Admission | `admission_app` | `ADMISSION_DB_PASSWORD` | `admission` |
| SEMS Platform - Local admin | `postgres` | `POSTGRES_PASSWORD` | 所有 schema，仅本地维护使用 |

日常排查优先使用对应服务账号，使权限与应用一致。三个账号连接同一个数据库，但不能读取其他服务的 schema。管理员账号可查看全部 schema，不应替代应用账号。业务表在对应后端服务启动并运行 Flyway 后创建，仅启动 PostgreSQL 不会创建全部业务表。可以执行 `SELECT current_database(), current_user;` 确认当前连接。

Navicat 用于查看数据和调试查询，数据库结构以版本控制中的 Flyway 迁移为准：

1. 在所属服务的 `src/main/resources/db/migration/` 下新增 `V<版本号>__简短英文描述.sql`，版本与描述之间为两个下划线。先检查该服务已有版本，与组员协调下一个未使用的编号；不同服务独立编号。
2. 不修改已合并或已在共享环境执行的迁移，不只在 Navicat 界面改表，也不通过修改 `flyway_schema_history` 掩盖版本问题。
3. 保持 Hibernate `ddl-auto: validate`。迁移、相关 Java 映射、接口契约、测试和数据库说明一起提交。禁止跨服务外键和直接跨 schema 查询，跨服务访问走 API。
4. 重新构建并启动所属服务，自动执行迁移。合并前在独立环境验证空库初始化和已有数据升级；CI 会检查新数据库初始化。

PostgreSQL 初始化脚本仅在新数据卷首次启动时创建服务账号和 schema。修改 `.env` 不会重置已有数据库密码。连接失败时检查 Docker 状态、是否使用两个 Compose 文件启动、15432 端口及该数据卷原来的密码。普通停机使用 `down` 保留数据；`down -v` 会删除数据库，不作为日常更新步骤。不要提交数据库导出、Navicat 连接导出、`.env` 或 `.secrets/`。

## 8. 团队 Git 与 PR 协作流程

开始前约定任务或 Issue、范围和 reviewer。共同修改接口时先对齐 `contracts/`，修改数据库时与所属服务的开发者协调。统一流程为：**同步 main → 在自己的分支开发 → 测试 → push → PR → 组员 review → CI 通过 → 合并 → 再同步**。不直接向 `main` push。

### 个人分支与 Victor 分支

`victor` 是 Victor 持续使用的个人开发分支，合并后保留，仅由 Victor 推送；后续 Victor 的改动从此分支开始。切换或合并前确保工作区干净，未完成工作先提交或 stash。

```bash
# 本地已有 victor 分支
git fetch origin
git switch victor
git merge origin/main
```

新克隆的仓库执行 `git switch --track origin/victor`。其他组员从最新 main 创建自己的分支，替换示例名字：

```bash
git fetch origin
git switch -c alice origin/main
git push -u origin alice
```

需要同时处理独立任务时，从 `origin/main` 创建 `alice-event-search` 等短期任务分支。不要多人共用一个个人分支。

### 提交、推送与邀请审查

按第 6 节运行相关前后端检查；涉及数据库或服务联动时，还需在独立测试环境运行第 4 节验收。先检查差异，只暂存本任务涉及的文件：

```bash
git diff
git add README.md README.zh-CN.md  # 示例，替换为本次修改的路径
git commit -m "docs: explain team development workflow"
git fetch origin
git merge origin/main
git push -u origin victor       # 其他组员填写自己的分支
```

合并冲突时逐个处理文件，暂存后执行 `git commit` 完成合并；需要取消冲突合并时执行 `git merge --abort`。解决后重新运行相关检查，不强制推送共享历史。

在 GitHub 创建 **base 为 `main`、compare 为自己的分支** 的 PR。按模板写清任务、最终行为、测试命令与结果、数据库或配置升级步骤；界面变更附截图。邀请 **1 名其他组员**担任 reviewer，留言或邀请不等于批准。未完成的工作使用 Draft PR。根据意见在原分支修改并 push，修改后请 reviewer 再次审查。

CI 在面向 `main` 的 PR、推送至 `main` 或手动触发时运行。仅 push `victor` 而没有打开 PR，不会自动运行 CI。合并前以下三项必须通过：

- `Backend tests and build`
- `Frontend tests and build`
- `PostgreSQL and API acceptance`

同时需要 1 名其他组员批准、全部讨论解决且没有合并冲突。Telegram 通知用于告知结果，不作为合并质量门槛。

### 合并后继续使用 Victor 分支

`victor` 等长期个人分支使用 **Create a merge commit** 合并，保留共同历史，不删除分支。PR 合并后执行：

```bash
git fetch origin
git switch victor
git merge origin/main
git push
```

上一个 PR 合并后再开始下一个任务，避免同一 PR 累积无关改动。短期任务分支可以使用 **Squash and merge**，合并后删除，下个任务重新从最新 `origin/main` 创建。如果仓库仅允许 squash，则使用短期任务分支发 PR，不对长期个人分支反复 squash 合并。

以上为团队约定，README 不会自动开启 GitHub 保护。仓库管理员应给 `main` 配置分支保护或 ruleset：必须通过 PR、至少 1 名其他组员批准、更新后重新批准、解决全部讨论、通过上述三项检查，并禁止强推和删除主分支。如果开启了合并后自动删除分支，应关闭该设置或保留／恢复 `victor` 等长期个人分支。
