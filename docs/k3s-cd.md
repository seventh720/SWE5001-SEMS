# K3s 发布与回退

应用发布目标为 `sems-k3s/sems-prod`，正式入口为 <https://swe5001.seventh720.com>。配置入口：[workflow](../.github/workflows/ci.yml)、[release 渲染器](../scripts/cd/k3s_release.py)、[SSM 提交器](../scripts/cd/submit-k3s.py)和[主机发布器](../scripts/cd/deploy-k3s.py)。

## 发布流程

1. main 的六项质量检查通过，构建并扫描实际运行镜像，发布同次构建的 GHCR digest 锁。
2. runner 通过 GitHub OIDC 获取短期 AWS 身份，经 SSM Run Command 在已有 K3s server 执行发布；不向 runner 提供 kubeconfig、SSH 私钥或数据库密码。
3. 校验源提交、image lock、五个应用 digest、`sems-prod` 和资源允许列表；保存现场应用快照及此前已验证指针，执行 server-side dry run。
4. 导出 PostgreSQL custom-format dump 和不含密码的角色定义，记录大小与 SHA256。
5. 依次滚动 Identity、Catalog、Admission、Web、Gateway；每个服务最多等待 600 秒，包含两个副本依次拉取镜像、运行 Java Agent 和启动就绪的时间。
6. 核对镜像、两个就绪副本及跨节点分布，验证 HTTPS、健康接口、管理员登录/JWT、内部 API 404，并确认数据库 Pod/PVC UID 未改变。
7. 全部通过后更新 `/var/lib/sems-cd/current.json`；报告上传 `k3s-deployment` artifact。

同服务 Pod 使用 hostname 硬反亲和，滚动策略为 `maxSurge: 0`、`maxUnavailable: 1`。两节点都需可调度；该策略逐副本替换，不增加临时第三个副本。它不提供节点自动扩容、数据库 HA 或入口故障切换。

主机的 kubectl 子进程上限为 630 秒，整次 SSM 执行上限仍为 1,200 秒。等待超时会保留失败结果，不放宽应用 startup/readiness 探针，也不自动推进成功指针。SSM 失败的 stderr 会显示在 Actions 日志中，详细调用结果仍保存在 artifact。

## 管理边界

| 应用 CD 更新 | 独立管理 |
| --- | --- |
| 五个 Deployment、六个应用 Service、运行/数据库地址/gateway ConfigMap | Namespace、Secret、PostgreSQL StatefulSet、PVC/StorageClass、NetworkPolicy |
| 后端的共享 Java Agent component | Traefik/ACME、正式站点 Ingress、Grafana Ingress、监控后端 |

Flyway 在对应后端启动时执行。数据库迁移、凭据轮换和数据库恢复须按兼容性单独协调。不要直接 apply 带旧 bootstrap 镜像摘要的完整生产 overlay 来更新应用；日常发布使用同次 CI 的 image lock。

正式入口使用 [sems-public.yaml](../deployment/k3s/sems-public.yaml)，监控入口使用 [grafana-public.yaml](../deployment/observability/grafana-public.yaml)。Release 不包含 Ingress，也不能重建旧 namespace。

## AWS 与 GitHub 身份

- GitHub environment 名为 `k3s-test`，仅允许 main；这是既有 OIDC/IAM 身份，实际业务 namespace 为 `sems-prod`。
- 环境变量为 `K3S_DEPLOY_ROLE_ARN` 和 `K3S_INSTANCE_ID`，目标为现有 server。
- `swe5001-github-k3s-deploy` 只信任此仓库指定 environment 的 OIDC subject，允许对指定实例执行 `AWS-RunShellScript` 及查询结果。
- server 的 `swe5001-k3s-ssm` 实例角色具有 SSM managed-instance 权限；worker 不需要 GitHub 发布权限。

策略源文件位于 [deployment/k3s/cd](../deployment/k3s/cd/)。该角色能在 server 执行管理员级发布命令，main 的代码审查属于信任边界。修改 environment 名称必须同步 IAM trust，不能仅改显示名。

## 发布状态与备份

server 的 `/var/lib/sems-cd/` 由 root 管理：

| 路径 | 内容 |
| --- | --- |
| `releases/<commit>-<run>-<attempt>/` | 候选资源、应用快照、此前指针和验证结果 |
| `current.json` / `previous.json` | 当前和此前已验证的发布指针 |
| `backups/` | 发布前 dump、角色定义及校验元数据 |
| `deploy.lock` | 串行化 CD 和手动应用修改 |

数据库在 worker，以上备份在 server。另用[数据库备份命令](k3s.md#数据库与备份)保存异机副本和独立凭据；当前尚无自动周期、WAL 归档或 PITR。

## 应用回退

失败发布不会推进成功指针；已更新的服务可能仍运行候选镜像，应先检查现场状态。`before.json` 仅用于诊断，可能包含未完整发布的资源。回退只选取 `before-pointer.json` 指向且验证通过的前驱，不撤销数据库迁移。

维护者确认目标镜像与当前 schema 兼容，并完成 AWS 登录后执行：

```bash
AWS_PROFILE=sems python3 scripts/cd/submit-k3s.py \
  --instance-id i-061d2aa2de119a95d \
  --rollback <commit-run-attempt> --database-compatible \
  --report ci-logs/k3s-rollback.json
```

此命令恢复所指定 release 的已验证前驱，并在操作前再次备份。无已验证前驱时须显式发布审核后的基线；迁移前 `sems-test` 的 release 不能直接回放。需要旧应用镜像时，将兼容的 digest 渲染为 `sems-prod` 的新 release。

原站数据库已停止接收 SEMS 写入。把 DNS 指回旧库不能替代数据库回迁；任何数据回迁都需维护、备份、同步和业务核对。历史实测材料见[证据索引](evidence/README.md)。
