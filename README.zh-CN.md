# Smart Event Management and Ticketing Platform


> 组织升级：已新增组织级角色、内部活动、邀请、活动工作人员与核销。已有环境必须先按[升级与验证说明](docs/organization-upgrade.md)完成维护窗口迁移，再使用本版本；下文早期增量记录保留历史背景。

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

开发前端可执行 `npm --prefix apps/web run dev`，访问15173端口，API代理到18080网关。生产构建的页面运行在网关根路径。日期输入使用应用自定义英文日历和时间选择器，统一为新加坡时间（UTC+08:00），提交为 UTC。本地开发覆盖配置仅向 `127.0.0.1:15432` 开放数据库；CI 使用的基础 Compose 文件不开放数据库端口。

这是本地HTTP配置，云端仍需HTTPS、密钥管理和部署配置。

## 3. 验收流程

1. 注册两个普通账号。
2. 以管理员登录“Manage users and roles”，为两个账号勾选 ORGANIZER 并保存。
3. 两个账号分别重新登录，进入“My events”。
4. 创建草稿，刷新后编辑；第二个账号列表不显示第一个账号的草稿。
5. 同一草稿在两个窗口编辑，后提交的旧版本返回冲突，可点击重新加载。

6. 在同一编辑页填写活动详情和票种，使用票种下方的按钮统一保存。
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
python3 scripts/registration-acceptance.py
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

## 9. 活动展示与报名信息

编辑草稿时选择 **Event category**，并独立选择 **Card background**（Lilac、Lime、Peach、Sky）。公开目录支持分类与标题组合筛选。背景图形由本地代码生成，沿用动画暂停及减少动态效果设置。

在 **Registration information** 中勾选实际需要的姓名、联系邮箱、电话、学号、护照号，或添加一个自定义问题。每笔订单填写一份联系人资料，不是每张票填写一份；发布后配置固定。参与者报名时填写对应字段，在 **My tickets** 查看历史快照；组织者从活动卡片的 **Registration list** 查看本活动报名资料。其他组织者无权访问，列表不会返回票码。

日期可用英文日历及小时/分钟控件选择，也可输入 `YYYY-MM-DD HH:mm`。活动与销售时间统一标注 Singapore time；历史 UTC 时刻保持不变，组件会校验无效日期和时间范围。

升级顺序为 Catalog（V3 迁移）、Admission（V4），再更新网关与前端；启用报名字段后不能混用旧 Admission 写入版本。已有活动默认 General/Lilac 且无必填资料；已有订单报名资料为空，不修改历史迁移。

[实现说明与语言／主题工作量评估](docs/registration-and-display.md)。本轮仅评估切换功能，未启用中英文或深浅色切换。

## 10. 个人资料、预约报名与倒计时

在 **My profile** 修改用户名，并在 **Saved registration details** 管理多份有名称的联系人资料。报名时点击 **Apply saved details** 选择一份，再核对活动要求的字段。通用联系人不保存 Student ID 或自定义回答；每笔订单仍对应一位报名联系人。活动详情与票务设置合并到一个编辑页，**Publication preview** 用于检查已保存内容并确认发布。详见[联系人与编辑流程](docs/saved-contacts-and-editor.md)。

开售前点击 **Save pre-registration**，每个用户对每场活动保存一份预约，不占名额。**My pre-registrations** 展示开售倒计时和修改入口。开售后表单切换为 **Confirm free booking**，必须手动确认，后端重新检查名额。报名成功时同一事务移除对应预约。删除预约不等于取消订单。

活动卡片分开显示分类、时间、地点和简介；详情展示活动开始、报名开放／截止倒计时，统一使用新加坡时间。倒计时用于提示，实际时间与名额由后端校验。

升级需应用 Identity V2、Admission V5；使用新构建的 JAR，先构建前端 dist 再重建 Web 容器，最后重启网关。数据库端口保持 **15432**。完整回归命令：`python3 scripts/pre-registration-acceptance.py`，仅在独立测试环境执行。见[设计与验证说明](docs/pre-registration-increment.md)。

## 11. 分角色工作台与活动复用

登录后首页展示 Dashboard，包括近期已确认行程及已保存预约。组织者、管理员按角色看到对应管理入口；工作人员检票仍待实现。Explore 调整为右侧紧凑导航面板。

**My events → Publication preview / Publication management → Edit details & tickets** 只打开当前活动。详情与票种统一保存；已发布活动自动更新，草稿和暂停状态保持不变。首次发布后仅报名信息规则锁定。发布管理支持明确暂停和恢复，已有票券保持有效。票种名额不得低于已出票名额，已有订单或预约引用的票种不能删除。详见[发布管理](docs/publication-management.md)。

[平台定位与组织者接入说明](docs/platform-positioning.md)明确了共享平台、两个组织者场景，以及账号所有权隔离与企业租户的区别。完整验收入口为 `python3 scripts/workspace-acceptance.py`，仅在独立测试环境运行。

本轮新增 Catalog V4、Admission V6 迁移，先更新 Admission，再更新 Catalog 与 Web。中断中的更新会自动恢复，见[改期规则与验证](docs/schedule-revision.md)。
