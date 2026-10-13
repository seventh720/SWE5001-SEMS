# Smart Event Management and Ticketing Platform

[English](README.md) | [简体中文](README.zh-CN.md)

SEMS 是面向独立组织者与参与者的共享活动与票务平台。采用 React + TypeScript、三个独立 Spring Boot 服务和 PostgreSQL。

本轮已实现：注册登录、RSA JWT、管理员角色授权、组织者活动草稿创建/列表/详情/编辑、所有权隔离及乐观版本冲突。本轮另已实现免费票种、配额/销售窗口校验、可重试发布和公开活动浏览。现已接入幂等免费预订、参与者取消订单，以及每名额独立的二维码/手动码票券。工作人员分配与核销、整场活动取消和组织者统计仍待实现。

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
docker compose --env-file .env -f deployment/compose.yaml -f deployment/compose.dev.yaml up --build -d
bash scripts/smoke.sh
```

访问 [本地平台](http://localhost:18080)。首次配置脚本生成 `.env` 和 `.secrets/`；重复运行会补充缺少的内部服务令牌，不覆盖已有数据库密码或 RSA 密钥。管理员邮箱默认 `admin@example.com`，随机密码见本地 `.env` 的 `SEMS_BOOTSTRAP_ADMIN_PASSWORD`，不要提交或分享该文件。首次初始化后可清空 bootstrap 配置，已存管理员仍可登录。

数据库凭据仅在新数据卷首次初始化时应用；修改 `.env` 不会自动修改已有数据库密码。普通停机保留数据：

```bash
docker compose --env-file .env -f deployment/compose.yaml -f deployment/compose.dev.yaml down
```

开发前端可执行 `npm --prefix apps/web run dev`，访问15173端口，API代理到18080网关。生产构建的页面运行在网关根路径。日期输入使用浏览器时区，提交为UTC。本地开发覆盖配置仅向 `127.0.0.1:15432` 开放数据库；CI 使用的基础 Compose 文件不开放数据库端口。

这是本地HTTP配置，云端仍需HTTPS、密钥管理和部署配置。

## 3. 验收流程

1. 注册两个普通账号。
2. 以管理员登录“Manage users and roles”，为两个账号勾选 ORGANIZER 并保存。
3. 两个账号分别重新登录，进入“My events”。
4. 创建草稿，刷新后编辑；第二个账号列表不显示第一个账号的草稿。
5. 同一草稿在两个窗口编辑，后提交的旧版本返回冲突，可点击重新加载。

6. 打开“Ticket setup & publication”，配置总配额不超过容量的免费票种并保存。开始票种配置后活动时间和容量固定。
7. 确认发布后进入公开活动页。依赖故障时活动保持发布中且不公开，恢复任务自动继续处理。
8. 参与者登录后，在已开放销售的票种下预订 1–10 个名额，从首页或 Explore 的 **My tickets** 查看每张二维码/手动码票券。
9. 活动开始前可取消尚未签到的订单，该订单全部票券作废，库存仅归还一次。网络异常后重试沿用保存的请求键；工作人员核销尚未开放。

## 4. 测试与 CI


```bash
mvn verify
npm --prefix apps/web test
npm --prefix apps/web run build
bash scripts/check-db-isolation.sh
set -a
source .env
set +a
python3 scripts/booking-acceptance.py
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

按下方团队流程通过 PR 集成，业务变更同时提交测试和契约。Proposal 与配图独立存放，不纳入代码仓库。

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

预订设计、API 规则、迁移与验证记录见 [本轮票务说明](docs/booking-increment.md)。
