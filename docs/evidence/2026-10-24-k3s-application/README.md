# EC2 K3s 应用与 HTTPS 验收

日期：2026-10-24，新加坡时间。业务检查 22:17:06–22:17:28，Admission 运维检查 22:20:13–22:21:11。测试地址：[https://sems-test.seventh720.com](https://sems-test.seventh720.com)。

源提交 `d3002d10a6f515b14f2013fc89f8805837b1f8ec`，工作区有部署配置变更。应用和数据库使用既有 `fb27bbf52142700351318ba18c83bb51a9783298` 发布的 amd64 镜像 digest，运行代码与当前工作区一致，本轮未重新扫描。网关配置由 Kubernetes ConfigMap 提供。实际 imageID、配置 SHA256、Pod/节点分布及 PVC 见 [application-summary.json](application-summary.json)。

## 部署

两台 t3.medium、Ubuntu 24.04、各 30 GiB gp3，位于同一可用区。Identity、Event Catalog、Admission、Web、Gateway 各两个副本，分别落在两个 EC2 节点。PostgreSQL 单副本位于 worker，数据使用现有 EBS 上的 Retain local-path PVC。Traefik 单副本位于 server，ACME 状态使用另一 Retain local-path PVC，文件权限 0600。

DNS A 记录指向 server 公网地址，Cloudflare 使用 DNS only。Let's Encrypt 证书、HTTPS、HTTP 重定向已验证；自动续期已配置，未实际经历续期周期。正式域名仍在 Lightsail，原数据未迁入测试库。

## 业务检查

九组检查均通过，原始结构化结果见 [business-acceptance.json](business-acceptance.json)：

| 检查 | 结果 |
|---|---|
| Gateway 与三个后端就绪、内部接口阻断 | 通过 |
| 注册、登录、RSA、组织权限、草稿并发修改 | 通过 |
| 发布、订票、私有资源、重试载荷匹配 | 通过 |
| 同一请求键跨两个 Admission Pod，20 请求 | 1 个订单，重复调用返回同一结果 |
| 100 个不同请求竞争 10 名额，每节点 50 请求 | 10×200，90×409；库存/确认数量/有效票数为 10/10/10 |
| 工作人员权限与 10 次并发核销 | 仅 1 次首次核销，核销时间一致 |
| 重复个人取消 | 库存只释放一次 |
| 整场取消 | 库存/确认/有效票清零，已核销历史和取消回执保留 |
| schema 隔离 | 6 项跨 schema USAGE 拒绝、3 项 public CREATE 拒绝，实际越界查询被拒绝 |

测试通过独立 API 端口转发把请求明确分配到两个不同主机上的 Admission Pod，并用 PostgreSQL 独立核对持久化结果。它证明该负载下的一致性，不证明更大并发容量。

## 独立服务运维

[service-lifecycle.json](service-lifecycle.json) 记录：

- Admission 单独从 2 副本减到 1，再恢复为跨节点 2 副本。
- 删除一个 Admission Pod 后由 Kubernetes 重建，单次观察到替代 Pod Ready 用时 26.503 秒。
- Identity 和 Catalog Pod UID 全程不变，订单/票券数量保留。
- 首页、公开活动读取和三个后端健康接口共 205 次可信 HTTPS 采样全部成功。

这轮为低负载、单次手动扩缩容/Pod 故障检查，没有更换应用镜像，不证明独立版本升级、兼容回滚、性能扩容收益或主机故障恢复 SLO。

## 公网检查与备份

[public-https.json](public-https.json) 验证首页、网关及三个后端健康接口为 200，证书验证结果为 0，内部接口为 404，HTTP 为 301 重定向到 HTTPS。[public-auth-assets.json](public-auth-assets.json) 验证公网管理员登录、JWT 请求和前端 CSS/JS。

业务验收后的数据库和不含密码的角色定义已导出到本机受限目录；[application-backup-metadata.json](application-backup-metadata.json) 仅记录备份大小和 SHA256，备份数据不提交。登录凭据、JWT 私钥、数据库密码、ACME 私钥和 kubeconfig 不包含在本记录中。

[application-deploy.txt](application-deploy.txt)、[traefik-https-apply.txt](traefik-https-apply.txt)、[https-ingress-apply.txt](https-ingress-apply.txt) 保留部署输出。

## 边界与后续

测试库保留唯一的验收账号、组织、活动和订单，不是原 Lightsail 用户数据。正式数据迁移、正式域名证书/DNS 切换和旧 SEMS 清理尚未执行；共享 Lightsail 主机上的其他项目和 Caddy 继续使用。当前仍有控制平面、单可用区、数据库节点和入口单点；HPA、节点自动扩容、独立镜像发布流水线、持续性能容量验证和完整回滚演练尚待完成。

操作步骤见 [K3s 环境](../../k3s.md)。
