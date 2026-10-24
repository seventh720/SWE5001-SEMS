# EC2 上的 K3s 环境

当前云端 Kubernetes 路线为两台 EC2、自建 K3s、Traefik 入口和集群内自建 PostgreSQL。当前路线不创建 EKS、RDS、NAT Gateway 或 ALB。应用仍通过独立 Deployment、Service、Secret 和数据库账号/schema 划分边界；EKS overlay 仅保留为另一种部署环境的参考模板。

2026-10-24 测试环境已上线：[https://sems-test.seventh720.com](https://sems-test.seventh720.com)。五个应用各两个副本，分别位于两个节点；业务闭环、两个 Admission Pod 的并发一致性、独立扩缩容和单 Pod 恢复已验证，见[应用验收记录](evidence/2026-10-24-k3s-application/README.md)。该环境使用独立测试数据库，正式域名和原 Lightsail 数据尚未迁移。

## 节点与网络

| 节点 | 配置 | 职责 |
|---|---|---|
| `sems-k3s-server` | Ubuntu 24.04 x86_64；t3.medium；30 GiB gp3 | K3s 控制平面、内嵌 SQLite 集群状态库、containerd 和应用工作负载 |
| `sems-k3s-worker` | 同上 | K3s agent、containerd、PostgreSQL 持久化与应用工作负载 |

两台位于 `ap-southeast-1a` 的同一公有子网，节点间通过私有 IP 通信，使用公网 IPv4 经 Internet Gateway 拉取镜像。K3s 的 API server、scheduler、controller manager 等由 server 进程承载，不能根据 `kube-system` 的 Pod 列表断言控制平面不存在。默认 Pod 网段为 `10.42.0.0/16`，Service 网段为 `10.43.0.0/16`，Flannel 使用 VXLAN。

节点共用安全组：TCP 22 仅允许管理者的公网 IP；TCP 80/443 允许网站访问；TCP 6443/10250、UDP 8472 仅允许节点安全组自身。默认允许出站。Kubernetes API 不开放公网访问，本机通过 SSH 隧道管理。

这是单控制平面、单可用区环境，PostgreSQL 也是单实例。两个应用副本不能消除控制平面、可用区或数据库节点的故障风险。Traefik 默认一个副本，ServiceLB 在两个节点监听入口端口；单域名指向一个节点时，该节点仍是域名入口单点。HPA、节点自动扩容、入口故障切换尚未配置。

## 安装

固定版本 `v1.36.5+k3s1`。先将 [server 配置](../deployment/k3s/server.yaml.example) 替换为实际私有 IP，作为 root-only 的 `/etc/rancher/k3s/config.yaml`，再在 server 执行：

```bash
sudo sh /tmp/install-k3s-node.sh server
```

脚本来自仓库的 [install-k3s-node.sh](../scripts/k8s/install-k3s-node.sh)，从固定 release tag 获取官方 installer；installer 对 K3s 二进制核对 release SHA256。版本和配置应一起变更，不能无记录地跟随 `latest` 升级。

通过 SSH 安全读取 server 的 `/var/lib/rancher/k3s/server/agent-token`，写入 worker 的 `/etc/rancher/k3s/agent-token`，root 所有、权限 0600。将 [agent 配置](../deployment/k3s/agent.yaml.example) 的私有 IP 替换后写入 worker，再执行：

```bash
sudo sh /tmp/install-k3s-node.sh agent
```

不要将 token 放入命令参数、操作日志或版本库。server 的 `/etc/rancher/k3s/k3s.yaml` 含集群管理员凭据；本机副本独立保存在被忽略的 `.secrets/k3s-cloud/kubeconfig`，不覆盖默认 kubeconfig。SSH 私钥也仅在该忽略目录中保留权限 0600 的副本。

本机管理隧道（把 `<server-public-ip>` 替换为实例当前地址）：

```bash
ssh -i .secrets/k3s-cloud/ssh.pem \
  -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes \
  -o UserKnownHostsFile=.secrets/k3s-cloud/known_hosts \
  -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 \
  -N -L 127.0.0.1:16443:127.0.0.1:6443 ubuntu@<server-public-ip>
```

`known_hosts` 应使用 AWS 实例控制台输出中的主机公钥核对。独立 kubeconfig 的 server 为 `https://127.0.0.1:16443`，context 为 `sems-k3s`。用显式参数访问：

```bash
kubectl --kubeconfig .secrets/k3s-cloud/kubeconfig --context sems-k3s \
  --cache-dir .secrets/k3s-cloud/cache get nodes -o wide
```

## 网络验证

[network-smoke.yaml](../deployment/k3s/network-smoke.yaml) 创建一次性 namespace、server 节点客户端 Pod、worker 节点 HTTP Pod、ClusterIP Service 和临时 HTTP Ingress。等待两个 Pod Ready 后验证：

1. server 节点 Pod 能解析 `bootstrap-http.sems-bootstrap-check.svc.cluster.local`。
2. 通过该 Service 能从 server 节点访问 worker 节点 Pod，返回 `SEMS_K3S_NETWORK_OK`。
3. 分别向两个 EC2 公网 IP 发 HTTP 请求，Host 为 `bootstrap.sems-test.example.invalid`，均得到同样响应。
4. `kubectl top nodes` 能获取两个节点的指标。

测试结束删除整个 `sems-bootstrap-check` namespace。这个检查使用 BusyBox 临时镜像；实际运行 digest 要随结果保存。它只验证基础设施连通性，不代表 SEMS 业务、HTTPS、负载容量或故障恢复验收。

上述临时 HTTP Ingress 检查用于初始阶段。启用全局 HTTPS 重定向后，公网检查应改用真实测试域名的 HTTPS，而不是继续期待 IP 地址上的 HTTP 直接返回测试正文。

## 自建 PostgreSQL

[数据库配置](../deployment/k8s/overlays/k3s/postgres/kustomization.yaml) 使用一个 PostgreSQL 17 StatefulSet，固定在 `sems-k3s-worker`，数据通过 `data-postgres-0` PVC 保存在 worker 的现有 EBS 根磁盘上。独立 StorageClass `sems-postgres-local` 使用 K3s local-path provisioner、WaitForFirstConsumer 和 Retain 回收策略；StatefulSet 删除/缩容时也保留 PVC。

PVC 声明为 10 GiB，但 local-path 使用节点目录，未单独创建或收费一块 10 GiB EBS，也不强制执行容量配额。数据库文件和镜像缓存共用 worker 的 30 GiB 磁盘，需监测实际剩余空间。Pod 重建会重新挂载同一份数据；worker 丢失时，不能自动把这个本地卷挂载到 server，需要恢复原节点或从异机备份重建。Retain 不保护 EC2 根盘被终止删除的情况。

镜像固定为既有 `fb27bbf52142700351318ba18c83bb51a9783298` 发布中的 PostgreSQL digest，沿用该次 CI 扫描与真实镜像验收，未在本轮重新扫描。镜像内初始化脚本创建 `sems` 数据库、三个应用角色和独立 schema，并限制 PUBLIC 和跨 schema 权限。容器使用 PostgreSQL Alpine 的 UID/GID 70，管理员密码只进入数据库 Pod；后端使用各自的独立 Secret。

数据库只通过 ClusterIP `postgres:5432` 提供服务。NetworkPolicy 仅允许同 namespace 的三个后端和 `postgres-backup` 标签工具 Pod 访问；EC2 安全组不开放 5432。当前集群内数据库连接未启用 PostgreSQL TLS；它依赖私网、Pod 网络隔离和数据库认证，不能标为 RDS `verify-full` 连接。

准备独立凭据及密钥（脚本默认仍生成本地 kind 环境，以下显式指定云端目录）：

```bash
bash scripts/k8s/setup-local.sh .secrets/k3s-cloud k3s-admin@example.invalid
```

使用 [Secret 生成器](../scripts/k8s/secrets.py) 时传 `--include-postgres`，把输出直接通过管道交给显式 context 的 kubectl，不写入日志。已有凭据不会被初始化脚本覆盖；PostgreSQL init 脚本只在空数据目录执行，更新 Secret 也不会自动修改库内密码。

在 `sems-test` namespace 已存在且 Secret 已创建后，可只部署数据库：

```bash
kubectl --kubeconfig .secrets/k3s-cloud/kubeconfig --context sems-k3s \
  --cache-dir .secrets/k3s-cloud/cache apply -k deployment/k8s/overlays/k3s/postgres
```

异机逻辑备份保存到本机的忽略目录，权限 0600，角色导出不包含密码；应另行保留受限的 `runtime.env` 供凭据恢复：

```bash
python3 scripts/k8s/backup-postgres.py \
  --kubeconfig .secrets/k3s-cloud/kubeconfig \
  --output-directory .secrets/k3s-cloud/backups
```

这提供手动备份，尚无自动周期、WAL 归档或时间点恢复。数据库验收脚本会检查真实账号认证、schema/网络隔离、Pod 重建数据保留，并把备份恢复到一次性数据库；不写入业务表：

```bash
python3 scripts/k8s/postgres-acceptance.py \
  --kubeconfig .secrets/k3s-cloud/kubeconfig \
  --report ci-logs/k3s-cloud/postgres-acceptance.json
```

之前准备但未使用的 RDS 子网组、两个私有子网、路由表和数据库安全组已删除，未创建过 RDS 实例；历史网络记录及清理记录保留在[基础设施记录](evidence/2026-10-24-k3s-bootstrap/README.md)。

## 应用与 HTTPS

[K3s overlay](../deployment/k8s/overlays/k3s/kustomization.yaml) 包含上述数据库和通用应用配置，五个应用各两个副本。同服务 Pod 使用 hostname 硬反亲和，滚动策略为 maxSurge 0、maxUnavailable 1，确保更新后仍分布在两节点。数据库 URL 指向 `postgres:5432`。初始化应用镜像固定到 `52df21f34a5f181683f273ae053bf5dc18c08e08` 发布的 amd64 digest；其业务运行代码与 `fb27bbf` 一致。日常 [CD 发布器](k3s-cd.md)从同次 CI 的 image lock 覆盖五个应用引用，数据库镜像独立管理。网关通过 ConfigMap 使用 Kubernetes DNS 适配配置。

三个后端启动时运行各自的 Flyway 迁移。测试管理员凭据保存在本机被忽略的 `.secrets/k3s-cloud/login.txt`；密码和 token 不进入部署记录。原 Lightsail 账号和数据尚未迁入，不应期待旧账号直接登录测试环境。

DNS：Cloudflare 的 `sems-test` A 记录指向 server 当前公网 IPv4，使用 DNS only。HTTPS 配置位于 [traefik-https.yaml](../deployment/k3s/traefik-https.yaml)，需将 `CONFIGURE_ACME_EMAIL` 替换成环境联系人邮箱后以集群管理员身份单独部署；本机实际配置保存在忽略的 `.secrets/k3s-cloud/traefik-https.json`。

Traefik 通过 Let's Encrypt HTTP-01 自动签发并配置自动续期，HTTP 重定向到 HTTPS。`traefik-acme` PVC 使用 server 现有 EBS 上的 local-path 目录，Retain 回收策略，保存 `/data/acme.json`，实际文件权限 0600。该 PVC 的 1 GiB 请求也不代表另建 EBS。Traefik 保持单副本并使用 Recreate 更新策略，避免多个实例同时写 ACME 状态；更新时可能短暂中断入口。证书续期流程已配置，尚未经历实际续期周期。

Ingress 使用 `traefik`、真实域名和 `letsencrypt` resolver，证书由 Traefik 的 ACME 状态管理，不需要手工创建 `sems-test-tls` Secret。后续应用更新使用：

```bash
kubectl --kubeconfig .secrets/k3s-cloud/kubeconfig --context sems-k3s \
  --cache-dir .secrets/k3s-cloud/cache apply -k deployment/k8s/overlays/k3s
```

云端业务验收显式选择环境，默认行为仍为本地 kind：

```bash
python3 scripts/k8s/local-acceptance.py --environment k3s \
  --kubeconfig .secrets/k3s-cloud/kubeconfig \
  --env-file .secrets/k3s-cloud/runtime.env \
  --report ci-logs/k3s-cloud/business-acceptance.json
```

该检查会创建唯一的测试账号、组织、活动和订单，测试数据保留在独立测试库；不要把该测试库当作已经迁入原站数据的正式环境。

[service-lifecycle.py](../scripts/k8s/service-lifecycle.py) 验证 Admission 手动 2→1→2 扩缩容和单 Pod 重建，同时采样公网读取/健康接口，并比较 Identity/Catalog Pod UID 与订单/票券数量。它不验证新版本镜像升级、兼容回滚、性能扩容收益或主机级故障恢复。当前九组业务验收和该轮运维检查通过，完整结果见[应用验收记录](evidence/2026-10-24-k3s-application/README.md)。

扩展业务回归使用 [business-regression.py](../scripts/k8s/business-regression.py)，依次复用现有业务断言，将测试数据 SQL、服务停启和重启操作转换为真实的 `kubectl exec`、Deployment 缩放和滚动重启。执行环境不需要 Docker daemon 或 Compose。每个套件在独立进程中运行，保存日志、脚本 SHA256、Kubernetes 操作和结果，结束时恢复原副本数。

```bash
python3 scripts/k8s/business-regression.py \
  --kubeconfig .secrets/k3s-cloud/kubeconfig \
  --env-file .secrets/k3s-cloud/runtime.env \
  --output ci-logs/k3s-regression/full

python3 scripts/k8s/catalog-recovery.py \
  --kubeconfig .secrets/k3s-cloud/kubeconfig \
  --env-file .secrets/k3s-cloud/runtime.env \
  --report ci-logs/k3s-regression/catalog-recovery.json
```

这两项只允许独立的 `sems-k3s/sems-test` 测试环境，串行执行；先备份数据库。它们创建测试数据并故意中断服务，不用于共享正式环境。后者在持续订票、同键重放和读取回执期间强制删除一个 Catalog Pod，再验证全部 Catalog 副本停止时的有界失败及恢复后的幂等性、库存审计，全程不重启 Gateway。历史数据迁移验收和 Docker DNS 拓扑验收不在上述业务适配器范围内。

## 后续数据与域名迁移

正式域名仍由 Lightsail 提供服务。切换需先备份原库，在停止业务写入的窗口完成最终数据恢复和环境凭据/密钥协调，再在新集群配置 `swe5001.seventh720.com` 及证书，修改 DNS 并验证登录、订票和核销。通过后清理旧 SEMS 部署并保留回退备份；原 Lightsail 主机还有其他项目和共享 Caddy，不在 SEMS 切换中整机删除。

未来也可迁到 RDS PostgreSQL：保留三个 schema/角色所有权，通过 pg_dump/pg_restore 恢复，协调连接地址、账号 Secret、可信 CA 和 `verify-full` TLS，再验证后切换。当前自建 PostgreSQL 的本地卷保留供回退，不代表已经创建或接入 RDS。当前范围不承诺零停机数据库迁移。

## 启停与费用

暂停测试时停止两台 EC2 可结束实例计算费，但 EBS 和保留的 Elastic IP 仍计费。自动分配的公网 IP 在停止/启动后可能变化，需要同步管理隧道、SSH 主机记录和 DNS；节点私网 IP 是集群配置的一部分。恢复时先启动 server，再启动 worker，检查节点与系统组件就绪。

PostgreSQL 随 worker 停止和恢复，不产生单独的 RDS 实例费。停机前完成备份并正常停库；现有 EBS 和保留的公网 IP 仍有独立计费。当前方案避免 EKS、RDS、NAT 和 ALB 的实例/网关小时费用。

参考：[K3s 版本说明](https://docs.k3s.io/release-notes/v1.36.X)、[配置文件](https://docs.k3s.io/installation/configuration)、[网络要求](https://docs.k3s.io/installation/requirements)、[Traefik 与 ServiceLB](https://docs.k3s.io/networking/networking-services)、[StatefulSet](https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/)、[PostgreSQL 逻辑备份](https://www.postgresql.org/docs/17/backup-dump.html)。
