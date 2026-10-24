# Lightsail → EC2 K3s 正式切换验收

日期：2026-10-25（新加坡时间，原始 JSON 使用 UTC）。正式入口为 [swe5001.seventh720.com](https://swe5001.seventh720.com)，DNS 已指向 `13.229.121.219`。当前应用镜像对应 PR #29 / `7a97828`；此前 [main CI/CD](https://github.com/seventh720/SWE5001-SEMS/actions/runs/40126181288) 已通过真实 GitHub OIDC 和 SSM 发布。本轮迁入原站数据和签名密钥，完成正式域名证书及 DNS 切换。

维护前确认当前无人使用；维护与最终恢复约 3 分钟。旧站三个后端停止后才采集最终备份，避免 API 或后台任务继续写入。共享 Caddy 和 SWE5006 保持运行。

## 检查结果

| 检查 | 结果及记录 |
|---|---|
| 两边备份 | 原站数据库、无密码角色定义、密钥/环境配置、共享代理及新环境测试数据/配置均备份到本机受限目录；公开文件只有元数据，[pre-cutover-backups.json](pre-cutover-backups.json) |
| 隔离恢复 | 原备份在新 PostgreSQL 内临时数据库完整恢复，27 张表数据指纹、关系所有者和表权限一致，6 组跨 schema 拒绝及 viewer 只读通过；结束后删除临时库/临时角色，[restore-rehearsal.json](restore-rehearsal.json) |
| 最终同步 | 停止旧站写入后重新导出并恢复，全部 27 张表的 SHA256/行数一致；7 用户、7 活动、3 订单、4 票券，[source-table-fingerprints.json](source-table-fingerprints.json)、[restored-table-fingerprints.json](restored-table-fingerprints.json) |
| 数据与凭据 | 保留原用户密码散列、角色/组织关系、订单和票券记录，迁入原 JWT 密钥；应用继续使用新环境数据库密码，viewer 登录 verifier 保留。新管理员登录和迁移前 JWT 均通过，[cutover.json](cutover.json) |
| 入口与服务 | 新节点直接 SNI/TLS 和公共域名各 7 条只读检查通过：首页、四个健康路径、内部接口 404、原 JWT `/auth/me`；五个应用各 2 副本、跨两节点，PG Pod/PVC UID 未变，[post-cutover-check.json](post-cutover-check.json)、[formal-cd-verification.json](formal-cd-verification.json) |
| DNS | Cloudflare 权威、1.1.1.1、8.8.8.8 均为新 IP，未残留 AAAA；本机 HTTPS 已直达新节点。`sems-test` 保留新 IP，`swe5006` 保留旧 IP，[dns-verification.json](dns-verification.json) |
| 共享项目 | 三个旧 SEMS 后端保持停止；共享 Caddy 与 SWE5006 三个容器运行，SWE5006 HTTPS 200。Caddy 中该站配置块逐字保留 |
| 迁移后备份 | 数据库在 worker，新的 dump 同时保存在 server 受限备份目录和本机；文件大小/SHA256 见 [cutover.json](cutover.json) 与 [post-cutover-check.json](post-cutover-check.json) |
| 防止误测正式数据 | namespace 标记为 production；5 个夹具/故障脚本入口在任何写入、缩放或删 Pod 前拒绝执行。3 项测试与真实 namespace 拒绝检查通过；9 项发布检查和 actionlint 也通过，[validation.json](validation.json) |

## 当前运行边界

集群仍为 `sems-k3s`，namespace 与 GitHub environment 保留历史名称 `sems-test` / `k3s-test`；它们已承载原站数据。`sems-test.seventh720.com` 是同一套业务的过渡别名，不能作为可破坏的测试站。正式域名 Ingress `sems-public` 和 production 标记独立管理，见 [sems-public.yaml](../../../deployment/k3s/sems-public.yaml)。本分支把日常 CD 的发布后验证和 Actions 展示入口改为正式域名；这项代码变更需 PR 合并后成为 main 默认配置，已在当前现场只读验证成功。

此前的测试数据库保留为 `sems_test_before_cutover_20261025`，没有与原站数据混合。原 Lightsail 数据卷/备份仍保留，旧三个 API 后端停写。旧 IP 的 SEMS 路由临时代理至新环境，使仍缓存旧 DNS 的请求也使用新数据库；共享 Caddy 继续服务 SWE5006。未删除旧数据卷或整台 Lightsail。

## 回退与后续清理

旧 IP 过渡代理开放后，新数据库可能已经有新写入。不能把 DNS 或代理直接改回冻结的旧数据库；需要再次维护、备份当前新库并反向同步，核对数据后才恢复旧应用。兼容镜像的应用回退与数据库回迁是两项独立操作。

待旧 DNS 缓存和访问情况确认后，再清理旧 SEMS 的闲置容器及过渡路由，保留备份；共享代理、SWE5006 和它的数据不在清理范围。当前没有执行高 VU 或故障注入，不把历史容量/恢复测试标成新正式数据库上的复测。首次只读验证脚本打包传输遇到不可 seek 的 stdin，修复后成功，未触发应用变更；完整边界见 [validation.json](validation.json)。

恢复依据：[PostgreSQL 17 pg_restore](https://www.postgresql.org/docs/17/app-pgrestore.html)、[Caddy 配置校验与重载](https://caddyserver.com/docs/command-line)、[Kubernetes Secret 卷更新](https://kubernetes.io/docs/concepts/configuration/secret/#using-secrets-as-files-from-a-pod)。私钥、密码、备份内容和登录 token 不进入公开记录。
