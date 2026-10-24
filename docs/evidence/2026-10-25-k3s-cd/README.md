# EC2 K3s 发布与回退验收

文本日志仅清理行尾空白，保留命令、输出和首次失败记录。

日期：2026-10-25（新加坡时间；JSON 时间为 UTC）。环境为 `sems-k3s/sems-test`，入口为 [sems-test.seventh720.com](https://sems-test.seventh720.com)。先通过本机已登录 AWS 身份完成 SSM 发布与回退演练；PR #29 合并后，**真实 GitHub OIDC → SSM → K3s 的 main 自动发布已通过**。本节记录迁移前的发布阶段；同日随后已完成[正式切换](../2026-10-25-k3s-cutover/README.md)。

## 结果

| 检查 | 结果与记录 |
|---|---|
| 首次 PR CI 与修复 | run 40123205313 的 Lint 失败：Linux runner 的 0700 临时目录无法由容器默认 guest 读取；其他四项已执行质量检查通过，镜像检查因依赖跳过。已在 Linux 容器内复现退出 3，改用主机 UID/GID 后同一夹具及实际函数通过；见 [ci-lint-fix.json](ci-lint-fix.json)。后续 [run 40124975667](https://github.com/seventh720/SWE5001-SEMS/actions/runs/40124975667) 六项质量检查全部通过 |
| 发布边界与静态检查 | 9 项发布测试、既有发布测试、Python/Bash 语法、actionlint 1.7.7、diff 检查通过；见 [static-checks.json](static-checks.json) |
| 权限与 SSM agent | 仅 server 可接收该角色的 SSM 命令；worker、终止实例和创建 IAM 角色为隐式拒绝；environment 仅 main；见 [permission-checks.json](permission-checks.json)、[ssm-agent.json](ssm-agent.json)、[setup.json](setup.json) |
| 初次发布发现问题 | [deploy.json](deploy.json) 保留首次失败：网关实际健康响应为纯文本 `ok`，检查器原先误按 JSON 解析；成功指针未推进。另发现仅 topology spread 无法保证滚动后同服务副本始终分居两节点 |
| 修正后发布 | 加入同服务硬反亲和及 maxSurge 0 / maxUnavailable 1，修正健康检查；五个应用发布 `52df21f` 成功，2 副本/2 节点、HTTPS、登录/JWT、内部接口 404、数据库 Pod/PVC 未变；见 [deploy-placement.json](deploy-placement.json) |
| 无效候选拒绝 | 故意修改不可变 Deployment selector，被 server dry run 拒绝，成功指针保持不变；见 [preflight-check.json](preflight-check.json)、[preflight-invocation.json](preflight-invocation.json) |
| 兼容旧镜像发布 | 显式发布既有 `fb27bbf` 镜像通过；见 [prior-version-deploy.json](prior-version-deploy.json) |
| 显式回退 | 从该次发布回退至其已验证前驱 `52df21f`，五个应用检查通过，数据库未恢复/撤销迁移；见 [rollback-to-latest.json](rollback-to-latest.json) |
| 回退后业务 | 9 组通过：认证/权限、发布/订票、20 次同键仅一单、100 请求争 10 名额为 10×200/90×409、10 次核销仅一次首次成功、取消与 schema 隔离；见 [post-release-acceptance.json](post-release-acceptance.json) |
| 手动演练最终现场 | 五个应用各 2/2 且分居两个节点，成功指针为 `52df21f`；此前故障回归夹具仍为库存/确认数量/有效票 708/708/708，重复请求键 0；见 [final-state.json](final-state.json) |

## 首次 main 自动发布

PR #29 合并提交 `7a978286920d9362739afaf41c5645f2ecf39d88` 的 [main run 40126181288](https://github.com/seventh720/SWE5001-SEMS/actions/runs/40126181288) 六项质量检查、镜像发布和 `Deploy · EC2 K3s Test` 均成功。OIDC 认证步骤实际通过，SSM 命令 `4e544d1c-0d3f-48cb-a740-6ef8deb58b6e` 发布五个同次构建的 digest 镜像。部署完成时间为 2026-10-25 03:56:50 新加坡时间。

[github-main-deploy.json](github-main-deploy.json) 提取实际 job 结果：发布前 dump 为 303223 字节，角色定义为 1199 字节，均含 SHA256；五个应用就绪、可信 HTTPS、管理员登录/JWT 和内部接口 404 通过，数据库 Pod/PVC 未变。[github-main-final-state.json](github-main-final-state.json) 独立读取现场确认成功指针为 `7a97828`、五个应用镜像与 job 报告完全一致，每个应用各 2 副本分居两节点；既有 708/708/708 数据和零重复键保持，数据库 Pod/PVC UID 与手动演练后相同。

本次自动发布执行的是发布器内建就绪、边界、登录与持久化检查，并核对既有数据；上述九组跨节点业务结果仍归属手动演练的 `52df21f`，没有把它们冒称为在新镜像上重新执行。此时尚未迁移原站数据；随后正式切换见独立记录。

## 备份与回退边界

每次正常发布及回退前均导出 PostgreSQL custom-format dump 和不含密码的角色定义。正常发布报告包含文件大小与 SHA256；回退的备份元数据保存在 server 受限目录。数据库运行于 worker，逻辑备份位于 server。公开证据仅记录元数据，不包含备份内容、密码、SSH 私钥或 kubeconfig。

回退选择目标发布 `before-pointer.json` 指向的已验证发布资源，拒绝使用可能混合失败候选的现场 `before.json`。本轮两套镜像源提交间，应用/数据库/网关路径差异只有 `apps/web/README.md`，不存在运行代码或迁移差异，因此显式确认 schema 兼容。此结果不证明不兼容迁移可自动撤销，也不替代完整凭据/ACL 重建或主机灾难恢复。

## 适用范围

本轮在 2026-10-24 [完整业务与故障回归](../2026-10-24-k3s-regression/README.md)之后验证发布机制，并在最终镜像上补跑核心跨节点业务；没有重跑全部浏览器/故障套件。新发布保留六项 CI 质量门禁和同次构建的 digest 锁，真实 GitHub 认证与部署链路已在上述 main run 确认。SSM 在指定 server 上执行管理员命令，main 审查及代码写入权限属于其信任边界。

随后原数据/账号/权限与正式域名证书/DNS 已完成独立切换验收。高 VU、十分钟稳态、实体相机复测与主机级 HA 不在本轮通过范围；单控制平面、单数据库、单 AZ 和单入口副本限制保留。[summary.json](summary.json) 给出机器可读状态。
