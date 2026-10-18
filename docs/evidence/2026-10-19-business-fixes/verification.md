# P1/P2 业务修复验收

日期：2026-10-19，新加坡时间。本记录对应推送前工作区验证；推送/云端状态见[发布复查](../../release-review-2026-10-19.md)。初次独立 Compose 项目 `sems-business-review` 使用 18084 端口；最终复查用全新 `sems-final-review` / 18085 重跑业务、扩缩容及完整组织链路。均使用独立数据库卷和测试凭据，验收后停止。未制作展示数据。

## 修复与验证

| 项目 | 实现及验证 |
|---|---|
| JWT 与重登 | 新签发令牌 exp−iat=3600、expiresIn=3600。已有令牌不会自动延长。前端处理定时到期、刷新时过期和匹配当前 token 的 401；保留 pathname/search/hash 和用户隔离的待确认订票 requestKey/payload。403 不退出，旧请求迟到的 401 不影响新登录。重新登录后回原页面，由用户确认重试。 |
| 检票结束边界 | 首次检票仅允许 startsAt−15min ≤ now < min(startsAt+15min, endsAt)，检查位于数据库锁内。已核销票重复请求返回原时间；取消和授权检查仍优先执行。前端显示已关闭。 |
| 当前活动信息 | 已有票券/预约按页批量读取 Catalog 当前标题、地点、时刻、状态；支持暂停/开始后的活动，保留原订单标题/地点快照。Catalog 故障返回 currentEvent=null，页面明确提示旧信息，票码仍可查看。 |
| 最后平台管理员 | 事务级 PostgreSQL advisory lock 串行化角色变更，禁止移除最后一名 ACTIVE ADMIN。真实并发降权最多一个成功。Bootstrap 重启只创建不存在的账号，不恢复撤销角色；新增启动回归测试。 |
| 分页与调用次数 | 用户、平台组织、治理记录、检票任务使用有上限的服务器分页；用户/组织支持搜索。批量查当前活动替代逐活动调用。目录按每批最多 100 个相关组织查询实时状态，未引入授权缓存。 |
| 路由与认证限流 | nginx Docker DNS 每 5 秒刷新，显式 Host、连接/读取超时。登录和注册共享 5 请求/秒、burst=10 限制，429 附 Retry-After。其他业务请求不消耗该认证预算。 |
| 诊断 | 网关 JSON 日志提供请求耗时、状态、上游和 request ID，不记录请求体/查询参数。发布与修改失败保留 event/operation ID。observe-platform.py 输出请求统计、瞬时容器 CPU/内存及 DB 连接/锁等待。 |

## 已完成检查

- Java 21 Maven clean verify：40 个后端测试（Identity 12、Catalog 11、Admission 17），零失败。
- Vitest：92 个前端测试、21 个文件全部通过；TypeScript 检查与 Vite 生产构建通过。
- nginx 配置检查通过；OpenAPI JSON、security scheme 引用和 git diff 空白检查通过。
- `business-fixes-acceptance.py`：JWT 时长、并发管理员保护、分页边界/搜索、当前地点、所有权、结束检票、Catalog 停机降级及恢复、认证限流及恢复。详见 [business.txt](business.txt)。
- `organization-acceptance.py` 全链回归：发布故障恢复、100 请求争抢 10 票、请求幂等、取消、报名字段、预约、资料、活动修改/暂停、组织隔离及核销。详见 [regression.txt](regression.txt)。
- `gateway-scaling-acceptance.py`：Admission 2→3 时观察到三个不同上游；3→2 后 30/30 路由成功；网关容器未重启、订单数不变。详见 [scaling.txt](scaling.txt)。
- 治理审批及关闭恢复验收通过，包含 Identity/Catalog 重启与 Admission 故障、撤销权限、通知幂等、保留历史核销。详见 [governance.txt](governance.txt)、[closure.txt](closure.txt)。
- 浏览器访问独立站点的登录页，页面正常加载。重登和到期交互主要由上述前端自动化用例验证，未实际等待一小时。
- 新增业务与路由验收已接入 CI；远端 CI 通过草稿 PR #12 运行；首次发现的 Java 21 注解包名遮蔽问题已修复，最新结果见 PR。

## 使用与边界

在选定 Compose 环境设置 SEMS_ENV_FILE、SEMS_COMPOSE_FILE 后运行 `python3 scripts/observe-platform.py 10m`。本次 [observation.json](observation.json) 包含故意停机、非法请求和恢复探测，不能当作稳态性能结果；CPU/内存/数据库数据是瞬时快照，不是连续监控。

分页接口从数组变为 page 对象，且增加内部批量接口，需协调更新三个服务、Web 和网关。没有新增数据库迁移。登录限流是网关实例内共享预算，若将网关本身扩为多副本，预算会按副本增加；不是账号锁定或分布式限流。

本轮本地手动扩缩容不等于云端自动扩容、高可用或 proposal 性能目标达标。云端负载/恢复实验、持续监控和展示证据留待下一阶段。公开目录仍聚合匹配组织 ID；超大组织规模的查询成本尚未测定。
