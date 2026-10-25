# CI 流水线

配置入口为 [.github/workflows/ci.yml](../.github/workflows/ci.yml)。流水线运行于 `main` push、目标为 `main` 的 PR 和手动触发；运行结果与产物见 [GitHub Actions](https://github.com/seventh720/SWE5001-SEMS/actions/workflows/ci.yml)。

## 六项检查

| 检查 | 内容 |
| --- | --- |
| Lint | ESLint、Checkstyle、actionlint 和 Shell 语法，保存 lint-report |
| Backend · Unit Tests & Build | Java 21、Maven clean verify、JaCoCo、三个服务的 JAR |
| Frontend · Tests & Build | Node 22、Vitest V8、TypeScript 和 Vite 构建 |
| Backend · Integration Tests | 部署配置检查、真实 API/PostgreSQL 回归、两个 Admission 副本、短时 k6 smoke 与库存审计 |
| Security · SAST, Dependencies & Secrets | 源码规则、secrets、npm 锁文件和实际 JAR 依赖扫描 |
| Images · Scan, Smoke Test & Publish | 构建和扫描运行镜像，再用同一批镜像执行启动/API smoke；仅 main 发布 GHCR digest |

前后端并行构建，集成和源码安全依赖这两者；镜像任务还依赖 lint。只有符合条件且仍为最新提交的 main 才部署 K3s。PR 验证不发布生产镜像或访问生产凭据。分支保护需在 GitHub 单独要求这六个检查及代码审查。

## 集成验收范围

| 入口 | 主要检查 |
| --- | --- |
| `check-db-isolation.sh` | 三个服务账号的 schema 隔离 |
| `business-fixes-acceptance.py`、`gateway-scaling-acceptance.py` | 基础业务、并发和网关多副本路径 |
| `organization-acceptance.py` | 组织、发布/编辑、订票、核销及其前置验收链 |
| `catalog-read-acceptance.py`、`event-directory-acceptance.py`、`visibility-acceptance.py` | 读取投影、搜索/分页、内部可见性及即时权限 |
| `organization-security-acceptance.py`、`organization-management-acceptance.py` | 组织隔离、角色变化、总览和组合筛选 |
| `notifications-acceptance.py`、`membership-notifications-acceptance.py` | 通知幂等、成员关系通知和个人已读状态 |
| `organization-governance-acceptance.py`、`event-cancellation-acceptance.py` | 组织关闭、整场取消、并发与中断恢复 |
| `predeployment-fixes-acceptance.py`、`organization-migration-acceptance.py` | 旧 token 撤权、关闭围栏、旧库迁移与重放 |
| `catalog-recovery-acceptance.py` | 冷启动期间订票/重放/回执、全副本停止后的有界失败和恢复 |

流水线还离线检查 release 范围、K3s 生产保护、监控配置/告警规则和性能工具。准确执行顺序以 workflow 为准。部分验收脚本会嵌套调用前置套件，必须使用独立数据和环境；不要指向 `sems-prod`。

## 本地运行

先按 [README](../README.md#2-local-setup)构建并启动独立测试栈。测试项目需要独立的凭据、数据卷、网络和主机端口；仅改 Compose project name 无法覆盖显式命名的资源。

```bash
mvn verify
npm --prefix apps/web run lint
npm --prefix apps/web run test:coverage
npm --prefix apps/web run build
bash scripts/ci/lint.sh
```

真实 API 套件还需要测试环境的 bootstrap 管理员变量。`SEMS_BASE_URL`、`SEMS_ENV_FILE`、`SEMS_COMPOSE_FILE` 和 `COMPOSE_PROJECT_NAME` 必须一致地指向同一测试栈；多份 Compose 文件用系统路径分隔符连接。先检查渲染配置，再按 workflow 顺序执行。`business-fixes-acceptance.py` 需要新数据库并先于其他套件。

`organization-management-acceptance.py --report ci-logs/organization-management.json` 可单独验证组织总览。其可选 live 模式会在真实 API 创建记录，不能作为普通生产健康探测。生产只读验证使用 [CD 检查](k3s-cd.md)和[监控验证](observability.md)。

## 交付、产物与通知

main 使用同次测试 JAR/web-dist 构建镜像，保存不可变 image lock，经 GitHub OIDC 换取 AWS 临时身份，再通过 SSM 调用发布器。应用 rollout、数据库备份和 HTTPS/登录检查通过后才推进成功指针。流程见 [K3s 发布与回退](k3s-cd.md)。

一般报告和失败诊断保存七天，release-image-lock 保存三十天。单元/组件覆盖率与真实 API/数据库验收分别统计；缺失报告显示 N/A，当前没有覆盖率百分比门槛。发布材料和长期需要的实测数据应按[证据规范](evidence/README.md)保存。

CI Telegram 使用 Actions secrets `TELEGRAM_TOKEN` 和 `TELEGRAM_TO`，与运行时 Alertmanager 的 Telegram Secret 分开。通知区分成功、失败、取消和跳过，也区分 PR 镜像验证与 main 发布；通知不是合并门禁。

IDE 中的 Checkstyle `<?m2e ignore?>` 仅跳过自动构建映射，不关闭 Maven CLI 或 CI 检查。依赖及镜像扫描范围见[安全说明](security.md)。
