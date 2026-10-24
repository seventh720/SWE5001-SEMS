# EC2 K3s 发布与应用回退

目标为 `sems-k3s/sems-test` 和正式入口 `https://swe5001.seventh720.com`。PR #29 已将 `.github/workflows/ci.yml` 的部署阶段接到 K3s；[main run 40126181288](https://github.com/seventh720/SWE5001-SEMS/actions/runs/40126181288) 已实际通过 GitHub OIDC 认证及 SSM 发布，部署提交为 `7a97828`。同日正式域名和原数据已完成[切换](evidence/2026-10-25-k3s-cutover/README.md)；旧 API 停写，旧 IP 通过共享代理临时转发到新环境，SWE5006 保留。

## 流水线

PR 运行质量检查，不发布镜像或部署。main push 或 main 上的手动运行依次完成 lint、Java、前端、真实数据库/API、安全和镜像检查，发布同次构建的 GHCR digest 锁，再进入 K3s 部署阶段。本分支将 job 名称和发布后验证入口改为 `Deploy · EC2 K3s` / 正式域名，已在当前现场只读验证；需 PR 合并后成为默认配置。

部署使用 GitHub OIDC 换取短期 AWS 身份，通过 SSM Run Command 在现有 server 执行发布脚本。runner 使用 `kubectl kustomize` 生成配置，不连接集群管理 API，也不持有 kubeconfig、SSH 私钥或数据库密码。K3s 节点使用 containerd，发布主机不运行 Docker Compose。

namespace/environment 的 sems-test/k3s-test 是历史名称，现已承载原站数据；保留 production 标记。正式 Ingress sems-public 独立于应用 CD，配置见 [sems-public.yaml](../deployment/k3s/sems-public.yaml)。

发布资源只包含五个应用 Deployment、六个 Service、三个 ConfigMap 和应用 Ingress。PostgreSQL、数据库凭据、PVC/StorageClass、NetworkPolicy 和 Traefik 独立管理；数据库 Flyway 迁移仍由各后端启动时执行。当前 GHCR 应用镜像允许匿名拉取；改成私有包需要先单独配置集群拉取凭据。

发布过程：

1. 核对源提交、同次 image lock、五个 digest 和 namespace/资源范围。
2. 集群 server-side dry run，保存应用快照及此前已验证的发布指针。
3. 导出 PostgreSQL custom-format dump 和不含密码的角色定义，记录大小和 SHA256。
4. 依次更新 Identity、Catalog、Admission、Web、Gateway，并等待各自完成滚动更新。
5. 验证五个应用各 2 个副本、实际镜像和跨节点分布；验证可信 HTTPS、内部接口 404、管理员登录及 JWT；确认 PostgreSQL Pod/PVC UID 未变。
6. 全部通过后才更新 `/var/lib/sems-cd/current.json`，结果上传 Actions artifact `k3s-deployment`。

两个节点使用同服务 Pod 的硬反亲和：通过稳定的 `app.kubernetes.io/name` 标签匹配，`topologyKey` 为 `kubernetes.io/hostname`。滚动策略为 `maxSurge: 0`、`maxUnavailable: 1`，逐个释放并替换副本。最初只有 topology spread 的演练出现最终副本同节点；增加反亲和后，发布器也显式检查最终节点分布。此策略要求两节点可调度，不提供节点自动扩容或数据库高可用。

## 已配置权限

经维护者授权配置：

- GitHub environment：`k3s-test`，仅允许 `main` 分支部署。
- 变量：`K3S_DEPLOY_ROLE_ARN`、`K3S_INSTANCE_ID`，目标 instance 为 `i-061d2aa2de119a95d`。
- GitHub 角色：`swe5001-github-k3s-deploy`，仅信任该仓库 `k3s-test` 的 OIDC subject 和 `sts.amazonaws.com` audience。该仓库创建于 2026-10-12，使用包含 owner/repository ID 的 subject。
- 部署权限：只对该 server 和 AWS `AWS-RunShellScript` 文档允许 `ssm:SendCommand`，并允许读取命令结果。它能在该 server 上执行管理员级发布命令；代码写入及 main 审查权限属于这条信任边界。
- server 实例角色/instance profile：`swe5001-k3s-ssm`，使用 `AmazonSSMManagedInstanceCore`。worker 未关联该角色。

具体策略见 [GitHub 信任](../deployment/k3s/cd/github-trust.json)、[部署权限](../deployment/k3s/cd/github-permissions.json)、[实例角色信任](../deployment/k3s/cd/instance-trust.json)。GitHub 未保存长期 AWS access key。旧 `staging` 环境与其 SSH 配置保留，当前公网 SSH 范围未扩大。

## 发布文件与备份

server 的 `/var/lib/sems-cd/` 由 root 管理，权限受限：

- `releases/<commit>-<run>-<attempt>/`：候选资源、发布前应用快照、此前指针、最终结果。
- `backups/`：发布前 dump、无密码角色定义和校验元数据。
- `current.json`：最近通过检查的版本；`previous.json`：此前已验证指针。
- `deploy.lock`：序列化 Actions 与手动发布。

数据库在 worker，以上备份在 server，是跨数据库节点的逻辑备份。还应按 [K3s 数据库步骤](k3s.md#自建-postgresql)保存本机副本；这不是完整 ACL/凭据重建、PITR 或主机灾难恢复演练。

## 显式应用回退

失败时停止发布，保留备份、快照和诊断，不推进成功指针。已经更新的组件可能仍在运行候选版本，需要检查实际状态。数据库迁移不自动撤销。

确认目标版本与当前 schema 兼容后，使用该次发布 `before-pointer.json` 指向的已验证资源回退应用。`before.json` 只作现场诊断，可能包含此前失败发布的部分状态，不能把它当作已验证版本。没有已验证前驱时，应显式发布经过审阅的基线。例如本机已完成 `aws login --profile sems --region ap-southeast-1` 时：

```bash
AWS_PROFILE=sems python3 scripts/cd/submit-k3s.py \
  --instance-id i-061d2aa2de119a95d \
  --rollback <commit-run-attempt> --database-compatible \
  --report ci-logs/k3s-rollback.json
```

该操作先备份当前数据库，再恢复目标发布前的应用资源、等待就绪并检查 HTTPS/登录。它不会恢复数据库，也不应把已有问题的旧部署配置重新引入。密钥、账号密码、数据库卷和 Traefik 不在应用回退范围。

## 已完成演练

[2026-10-25 发布与回退记录](evidence/2026-10-25-k3s-cd/README.md)包含正常发布、失败候选拒绝、兼容旧镜像切换和回退至已验证前驱，最终九组核心业务通过。先由本机身份经 SSM 完成演练；随后首次 GitHub main 发布也成功，现场确认五个应用各 2/2、镜像与同次发布报告一致、数据库 Pod/PVC 和既有测试数据保留。

## 剩余验证

- 正式域名、原数据和原 JWT 已迁移；后续根据缓存/访问情况清理过渡代理及旧 SEMS 闲置容器，保留共享项目和备份。
- 高 VU、十分钟稳态、实体手机相机、完整数据库灾难恢复和主机故障仍按各自计划验证。

依据：[GitHub AWS OIDC](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws)、[SSM 实例权限](https://docs.aws.amazon.com/systems-manager/latest/userguide/setup-instance-permissions.html)、[Kubernetes Pod 反亲和](https://kubernetes.io/docs/concepts/scheduling-eviction/assign-pod-node/)。
