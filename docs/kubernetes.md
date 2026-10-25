# Kubernetes 配置与验证

配置分为公共资源、本地验证和云端环境，使用 kubectl 内置的 Kustomize。[2026-10-24 本地 Kubernetes 验收](evidence/2026-10-24-kubernetes-local/README.md)已完成。正式域名和原数据现已迁到 [EC2 自建 K3s 与 PostgreSQL](k3s.md)，[应用 CD](k3s-cd.md)使用 GitHub OIDC/SSM；[Grafana、告警与追踪](observability.md)已接入。过渡测试域名入口已退休，正式入口为 `https://swe5001.seventh720.com`。EKS 模板保留为另一种环境的参考。

## 配置结构

```text
deployment/k8s/
  base/                 三个后端、Web、Gateway、Service、ConfigMap、健康探针
  kind.yaml             固定 Kubernetes 1.36.4 镜像的独立本地单节点集群
  overlays/local/       sems-local；独立 PostgreSQL StatefulSet/PVC；Admission 两副本
  overlays/k3s/         sems-prod；双节点 EC2 K3s；自建 PostgreSQL/PVC、Traefik HTTPS
  overlays/eks/         sems-test；RDS TLS、ALB HTTPS、每个应用两副本
deployment/k3s/          K3s 节点配置示例与一次性网络检查
deployment/gateway/     Compose/Kubernetes 共用路由规则及 Kubernetes 启动适配
scripts/k8s/secrets.py   从指定配置生成按服务分开的 Secret；不连接集群
scripts/k8s/setup-local.sh 生成独立本地测试凭据，不修改原开发配置
scripts/k8s/local-acceptance.py 两个 Admission Pod 的真实 API/PostgreSQL 验收
scripts/k8s/postgres-acceptance.py 云端自建 PostgreSQL 权限、持久化与恢复验收
scripts/k8s/backup-postgres.py 云端数据库异机逻辑备份
scripts/k8s/service-lifecycle.py Admission 独立扩缩容与单 Pod 恢复检查
```

Identity、Event Catalog、Admission 分别拥有 Deployment、Service、数据库账号和 Secret；只有 Identity 挂载 JWT 私钥。三个后端沿用独立 Flyway 迁移，数据库角色和 schema 必须在应用启动前存在。Admission 的库存、订单、出票仍在同一本地事务中。

后端每副本 requests 为 250m CPU / 512Mi，limits 为 1 CPU / 768Mi，JVM 堆上限 384Mi。当前值用于初始验证，尚未证明满足云端容量目标。readiness 包含数据库检查；startup/liveness 使用仅反映应用存活的 health group，避免数据库故障引发重启循环。应用启用优雅关闭，滚动更新配置 maxUnavailable=0；这不等于已经证明零中断。

网关共用现有 `nginx.conf`，启动时读取 Pod 的 DNS 服务器并改用 Service 完整域名，不使用 Docker 的 `127.0.0.11`。`event-catalog-pods` 是额外的 headless Service，只返回就绪 Pod，用于保留网关对可安全重试的 Catalog 只读请求的跨副本重试；Java 客户端仍使用普通 `event-catalog` Service。业务写请求继续保留原重试限制。Gateway 的 8080 端口只通过 ClusterIP Service 提供，Ingress 仅转发 80；公网 `/internal/` 返回 404。`/health/gateway` 仅表示网关进程可处理请求，不替代三个后端的 readiness。

## 离线检查

在仓库根目录执行；不需要连接集群，也不读取业务密钥：

```bash
kubectl kustomize deployment/k8s/overlays/local > /private/tmp/sems-local.yaml
kubectl kustomize deployment/k8s/overlays/k3s > /private/tmp/sems-k3s.yaml
kubectl kustomize deployment/k8s/overlays/eks > /private/tmp/sems-eks.yaml
python3 scripts/k8s/test-secrets.py
sh -n deployment/gateway/kubernetes-entrypoint.sh
```

使用 kubeconform 对渲染文件进行严格 schema 检查（以下固定工具镜像及 1.34 schema）：

```bash
for environment in local k3s eks; do
  docker run --rm -i \
    ghcr.io/yannh/kubeconform@sha256:faffaf43f95aa6425306e1ab8d6fcad72acb9049158f38e574c085ea1ec0f64e \
    -strict -summary -kubernetes-version 1.34.0 < "/private/tmp/sems-$environment.yaml"
done
```

最终使用的 Kubernetes 版本需与实际目标集群一致；云端模板的拓扑分布配置要求支持 `minDomains` 的 Kubernetes 版本（1.30+）。离线渲染/schema 检查无法验证 IAM、数据库可达性、镜像拉取、探针响应或实际调度。

## 在独立本地集群运行

需要 Docker、kind、kubectl、Python 3、OpenSSL，以及 README 中的 Java/Maven/Node 构建工具。本地集群至少预留约 4GiB 可用内存和足够磁盘空间；与已有容器同时运行时，建议 Docker 总内存至少 8GiB。以下命令创建全新的数据库，不连接 Lightsail。固定使用 `kind-sems-local` context，避免对当前选中的其他集群执行操作。

生成独立测试凭据并构建六个本地镜像。初始化脚本仅写入忽略的 `.secrets/k8s-local/`，重复执行保留已有凭据；镜像使用独立的 `sems-k8s-local` 项目名，不覆盖现有 Compose 镜像。请确认 Maven 实际使用 Java 21。kind 配置固定节点镜像及 digest；集群 kubeconfig 也单独保存，不修改日常使用的默认 kubeconfig。

```bash
bash scripts/k8s/setup-local.sh
mvn -B -ntp verify
npm --prefix apps/web ci
npm --prefix apps/web run build
docker compose --env-file .secrets/k8s-local/runtime.env -p sems-k8s-local -f deployment/compose.yaml build
kind create cluster --name sems-local --config deployment/k8s/kind.yaml \
  --kubeconfig .secrets/k8s-local/kubeconfig
kind load docker-image --name sems-local \
  sems-k8s-local-identity:latest sems-k8s-local-event-catalog:latest \
  sems-k8s-local-admission:latest sems-k8s-local-web:latest \
  sems-k8s-local-gateway:latest sems-k8s-local-postgres:latest
```

本地配置使用 `imagePullPolicy: Never`，镜像必须先加载到 kind。构建命令的 `-p sems-k8s-local` 与本地 overlay 的镜像映射配套。重新构建同名本地镜像后，需重新加载并重启对应 Deployment 才会生效。

创建命名空间及 Secrets，再部署应用。Secret 生成器输出包含敏感数据，只通过管道传入 kubectl，不保存到仓库、不上传日志；不要开启 shell `set -x`。脚本只读取简单的 `KEY=value` 配置，支持外层引号，不执行 shell 展开或命令。

```bash
set -o pipefail
sems_kubectl() {
  kubectl --kubeconfig .secrets/k8s-local/kubeconfig --context kind-sems-local "$@"
}
sems_kubectl create namespace sems-local --dry-run=client -o yaml \
  | sems_kubectl apply -f -
python3 scripts/k8s/secrets.py \
  --env-file .secrets/k8s-local/runtime.env --key-directory .secrets/k8s-local \
  --namespace sems-local --include-postgres | sems_kubectl apply -f -
sems_kubectl apply -k deployment/k8s/overlays/local
sems_kubectl -n sems-local rollout status statefulset/postgres --timeout=180s
for service in identity event-catalog admission web gateway; do
  sems_kubectl -n sems-local rollout status "deployment/$service" --timeout=300s
done
sems_kubectl -n sems-local get pods -o wide
sems_kubectl -n sems-local port-forward service/gateway 18081:80
```

另开终端验证，使用 18081 避开现有 Compose 的 18080：

```bash
SEMS_BASE_URL=http://127.0.0.1:18081 bash scripts/smoke.sh
curl --fail http://127.0.0.1:18081/health/gateway
curl --silent --output /dev/null --write-out '%{http_code}\n' \
  http://127.0.0.1:18081/internal/v1/events/details
```

最后一个请求应为 404。运行关键业务验收：

```bash
python3 scripts/k8s/local-acceptance.py \
  --kubeconfig .secrets/k8s-local/kubeconfig \
  --env-file .secrets/k8s-local/runtime.env \
  --report ci-logs/k8s-local/acceptance.json
```

脚本默认固定使用本地 kind 的 context/namespace；显式 `--environment k3s` 才选择 `sems-k3s/sems-test`，并要求两个 Admission Pod 位于不同主机。它自动创建并关闭随机本地端口的 Gateway 和两个 Admission Pod 转发，创建唯一测试账号和活动。并发实验明确向两个 Pod 各发一半请求，再用 PostgreSQL 独立核对；还覆盖重复核销、个人取消、整场取消和 schema 隔离。输出仅保存测试结果及运行镜像标识，不保存密码、JWT 或票凭证。此脚本不表示现有所有 Compose 验收均已移植；含 `docker compose exec/stop` 的其他脚本仍需适配。

首次同时启动全新数据库和后端时，数据库就绪前 headless Service 可能尚无 DNS 地址，Flyway 会使应用退出；Kubernetes 重启后恢复，后端通过 readiness 前不接收流量。本次初始启动观察到每个后端重启一次，随后正常就绪。这不替代数据库迁移失败的诊断，也不表示 startupProbe 会替应用重试 Flyway。

PVC 依赖集群默认 StorageClass。数据库密码只在首次初始化时生效，改 Secret 不会自动改数据库密码；envFrom 的 Secret 更新也不会自动重启 Pod。恢复数据库、轮换凭据与重启应用须协调执行。此集群仅用于可丢弃验证；验证结束并确认不需要其中数据后，可用 `kind delete cluster --name sems-local` 清理，集群内数据库也会删除。

## EC2 K3s 路线

节点安装、私网通信、SSH 管理隧道、Traefik、自建 PostgreSQL、持久化和费用边界见 [K3s 部署说明](k3s.md)。当前路线使用 `overlays/k3s`；下面的 EKS 步骤只用于选择托管 EKS 的环境，不是当前需要创建的资源清单。

## 可选：补齐 EKS 模板

先准备 AWS 本地访问。AWS CLI 2.32.0+ 支持通过浏览器使用现有控制台登录会话获取临时凭据：

```bash
aws login --profile sems --region ap-southeast-1
aws sts get-caller-identity --profile sems --region ap-southeast-1
```

IAM 用户/角色使用该登录流程需要 `SignInLocalDevelopmentAccess` 权限；该权限只允许登录，不额外授予 EKS 等服务的创建权限。IAM Identity Center 使用其 SSO 配置流程。详见 [AWS CLI 登录说明](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sign-in.html)。本地 kind 验证不依赖 AWS 登录。

2026-10-24 的只读检查确认 `sems` profile 可用，新加坡区域支持 1.36 标准支持版本；后续仍需检查会话是否过期。资源创建阶段再统一准备 VPC、EKS/Managed Node Group、RDS、ALB 控制器、应用专属 IAM 和证书；EC2 由节点组管理。模板采用普通 Managed Node Group，手动建集群时选择 Custom configuration 并关闭 EKS Auto Mode，参照 [AWS 创建说明](https://docs.aws.amazon.com/eks/latest/userguide/getting-started-console.html)。HTTPS 证书的 DNS 验证需要域名管理权限，届时使用实际 ACM 生成的记录。

`overlays/eks` 故意保留不可解析的 `.invalid` 地址和证书占位值。先准备以下真实信息，再修改并审核渲染结果；不要直接部署原样模板。

| 配置 | 位置与要求 |
|---|---|
| 五个应用镜像 | `overlays/eks/kustomization.yaml` 的 images；将 newName 改为真实仓库，移除 newTag，添加已扫描验证的 `digest: sha256:…` |
| RDS endpoint | 同一文件中的三个 JDBC URL；保持对应 currentSchema 和 `sslmode=verify-full` |
| 数据库初始化 | 独立准备 `sems` 数据库、三个应用账号/schema、PUBLIC 权限限制；EKS 不部署本地 PostgreSQL |
| RDS CA | 从 AWS 官方下载 CA bundle，在 `sems-test` 创建 `rds-ca` ConfigMap，key 必须为 `global-bundle.pem` |
| HTTPS 入口 | `ingress.yaml` 中的真实测试域名、与 ALB 同区域的 ACM 证书 ARN |
| 镜像拉取 | 私有仓库须配置可供未来 Pod 重建使用的认证；ECR 可使用节点 IAM，私有 GHCR 需配置 imagePullSecrets；一次 CI 的短期 GITHUB_TOKEN 不适合作为长期凭据 |
| 节点与网络 | 至少两台可调度 Linux 节点；按实际分布核验可用区；RDS 安全组只允许应用所需来源访问 5432；节点可访问镜像仓库 |
| ALB 控制器 | 本模板采用 Managed Node Group + AWS Load Balancer Controller，须先安装控制器、配置 IAM、IngressClass 和子网发现 |

EKS 镜像架构必须匹配 EC2；Apple Silicon 上构建的本地 arm64 镜像不能直接当作 amd64 节点的发布镜像。继续复用 CI 已验证的对应架构镜像。

三个后端挂载 `/run/rds/global-bundle.pem`。云端 Secrets 使用环境专属的安全配置文件及密钥目录，通过同一生成器准备，**不传 `--include-postgres`**；不要上传开发环境的 `.env`、数据库管理员密码或整目录 `.secrets`。迁移现有用户数据时需单独规划应用数据库凭据、JWT 密钥和内部令牌的保留或轮换。Secret 生成器不执行 RDS 角色初始化，也不执行数据迁移。

每个应用默认两个副本；同一应用通过 `minDomains: 2`、`maxSkew: 1` 要求分布到至少两台主机。第二台节点不可用或资源不足时，额外 Pod 可能保持 Pending；先修正节点容量，不应据此声称自动扩容已经实现。此配置约束的是主机分布，跨可用区情况仍须实际检查。RDS 单可用区仍是数据层单点。HPA、节点自动扩容、监控告警和 PodDisruptionBudget 尚未配置。

## 单服务更新与后续验收

配置支持分别更新三个服务。真实云端环境就绪后，可通过指定 context/namespace 的 `kubectl set image deployment/admission admission=<已验证仓库>@sha256:<digest>` 更新 Admission，然后等待该 Deployment 的 rollout 并验证相关业务。Identity、Catalog 的镜像和 Pod 不应变化。随后将该 digest 写回环境配置，使下一次 `apply -k` 保持一致。

公共 ConfigMap、密钥或网关规则的变化可能同时影响多个服务，应单独审核；网关 ConfigMap 使用内容哈希命名，规则变化会触发 Gateway 更新。Secret、数据库 URL 和 JVM 配置的变更需显式协调重启相关服务。当前文件尚未接入 GitHub Actions 的 Kubernetes 发布任务，现有 Lightsail CI/CD 保持原行为。

后续分别验证独立更新、固定负载下的 1/2 副本对照、Pod 故障恢复、并发库存和请求键重放、跨 schema 拒绝访问、兼容镜像回滚。保留镜像 digest、配置、请求结果、Pod/节点分布和数据库核对。数据库迁移不会随镜像回滚撤销；所有失败结果也需记录。具体业务边界见 [ADR](adr/0001-service-boundaries.md)。

参考：[Kustomize](https://kubernetes.io/docs/tasks/manage-kubernetes-objects/kustomization/)、[健康探针](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)、[ALB 注解](https://kubernetes-sigs.github.io/aws-load-balancer-controller/latest/guide/ingress/annotations/)、[RDS TLS](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.SSL.html)。
