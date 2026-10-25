# Kubernetes 配置与本地验证

生产使用 [EC2 K3s](k3s.md)，应用由 [OIDC/SSM CD](k3s-cd.md)更新。这里说明共享配置、独立 kind 测试及可选环境模板。

## 配置结构

| 路径 | 用途 |
| --- | --- |
| `deployment/k8s/base/` | 三个后端、Web、Gateway、Service、ConfigMap、探针与基本调度 |
| `deployment/k8s/components/telemetry/` | K3s 后端共享 Java Agent、OTLP 环境和资源标签 |
| `deployment/k8s/overlays/local/` | `sems-local`，独立 PostgreSQL/PVC，两个 Admission 副本 |
| `deployment/k8s/overlays/k3s/` | `sems-prod`，两节点、自建 PostgreSQL、硬反亲和与生产标记 |
| `deployment/k8s/overlays/eks/` | 可选 EKS/RDS/ALB 参考模板，含未替换配置；未部署 |
| `deployment/k3s/` | 节点配置、安装辅助、Traefik HTTPS、正式 Ingress 和 IAM 策略 |
| `deployment/observability/` | 独立 `observability` namespace 的运行栈 |

各服务有独立 Deployment、Service、账号和 Secret，只有 Identity 挂载 JWT 私钥。Flyway 分服务执行，数据库角色/schema 需先存在。readiness 包含数据库检查；startup/liveness 使用应用存活 health group。调度和滚动配置由 overlay 决定，不能把 base 的策略当成 K3s 最终策略。

网关通过 [Kubernetes 启动适配](../deployment/gateway/kubernetes-entrypoint.sh)读取 Pod DNS 并使用 Service 完整域名。`event-catalog-pods` headless Service 供只读请求跨副本故障转移；Admission 调用 Gateway 的内部 8080 listener。Ingress 仅进入公开端口，服务目标仍校验内部令牌。共享路由规则不依赖生产运行 Docker daemon。

## 离线检查

```bash
kubectl kustomize deployment/k8s/overlays/local > /tmp/sems-local.yaml
kubectl kustomize deployment/k8s/overlays/k3s > /tmp/sems-k3s.yaml
kubectl kustomize deployment/k8s/overlays/eks > /tmp/sems-eks.yaml
python3 scripts/k8s/test-secrets.py
python3 scripts/k8s/test-environment-guard.py
python3 scripts/cd/test-k3s-release.py
sh -n deployment/gateway/kubernetes-entrypoint.sh
```

渲染和离线测试不验证实际 IAM、镜像拉取、数据库连通或节点资源。生产发布还需 server-side dry run 与运行校验。

## 独立 kind 环境

需要 kind、kubectl、Docker、Python 3、OpenSSL，以及 README 中的构建工具。为集群预留约 4 GiB 可用内存，并核对已有本地容器占用。所有命令从仓库根执行，使用独立凭据、kubeconfig、镜像名和数据库。

```bash
bash scripts/k8s/setup-local.sh
mvn verify
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

本地 overlay 使用 `imagePullPolicy: Never`，需先加载镜像。Secret 生成器只解析配置，不执行 shell 展开；输出含凭据，直接传给指定集群，勿保存或输出到日志。

```bash
set -o pipefail
sems_local_kubectl() {
  kubectl --kubeconfig .secrets/k8s-local/kubeconfig --context kind-sems-local "$@"
}
sems_local_kubectl create namespace sems-local --dry-run=client -o yaml \
  | sems_local_kubectl apply -f -
python3 scripts/k8s/secrets.py \
  --env-file .secrets/k8s-local/runtime.env --key-directory .secrets/k8s-local \
  --namespace sems-local --include-postgres | sems_local_kubectl apply -f -
sems_local_kubectl apply -k deployment/k8s/overlays/local
sems_local_kubectl -n sems-local rollout status statefulset/postgres --timeout=180s
for service in identity event-catalog admission web gateway; do
  sems_local_kubectl -n sems-local rollout status "deployment/$service" --timeout=300s
done
sems_local_kubectl -n sems-local get pods -o wide
sems_local_kubectl -n sems-local port-forward --address 127.0.0.1 service/gateway 18081:80
```

另开终端，使用 18081 避开 Compose 的 18080：

```bash
SEMS_BASE_URL=http://127.0.0.1:18081 bash scripts/smoke.sh
python3 scripts/k8s/local-acceptance.py \
  --kubeconfig .secrets/k8s-local/kubeconfig \
  --env-file .secrets/k8s-local/runtime.env \
  --report ci-logs/k8s-local/acceptance.json
```

该检查向两个 Admission Pod 分别发请求并核对真实数据库，覆盖库存、重放、核销、取消和隔离；不代表完成了性能对照或全部 Compose 套件的 Kubernetes 移植。若启动失败，先查日志、数据库、schema 和凭据，不用延长探针来掩盖迁移错误。

确认不需要本地测试数据后，可执行 `kind delete cluster --name sems-local`，集群内数据库同时删除。更新已初始化数据库的密码需协调库内角色和 Secret；更新 Secret 不会自动重启 Pod。

## 生产保护与其他环境

历史 `--environment k3s` 及相关故障脚本指向隔离测试 namespace，并受生产标记保护；原测试 namespace 在正式集群已删除。它们不是正式环境验收入口，不能通过改成 `sems-prod` 绕过保护。

EKS overlay 仅为参考，当前没有创建 EKS、Managed Node Group、RDS 或 ALB。选用该环境需另行准备网络、IAM、数据库 TLS/CA、证书、镜像及资源预算，并验证其部署；不应把模板中的配置写成已使用的云服务。
