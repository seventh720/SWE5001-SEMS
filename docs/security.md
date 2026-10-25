# 安全控制与扫描门禁

扫描入口为 [scan.sh](../scripts/security/scan.sh)，版本和镜像以 [CI](../.github/workflows/ci.yml)、[扫描配置](../scripts/security/)和根 [pom.xml](../pom.xml)为准。每次报告只对应当次代码、镜像、规则与漏洞数据库；旧扫描通过不能作为长期安全保证。

## 运行时控制

- 公网使用 HTTPS；内部 API 不经公开路由开放，并校验方向独立的服务令牌。
- JWT 有效期一小时，业务操作校验当前组织权限，平台 ADMIN 也校验数据库中仍有效的角色。活动核销另需分配和时间窗口。
- 每个服务使用独立 PostgreSQL schema/凭据，应用不跨 schema 查询；数据库、Kubernetes API 和监控后端不对公网开放。
- Kubernetes Secret、私有密钥及 bootstrap 配置不进入 Git 或镜像。只有 Identity 挂载 JWT 私钥；集群管理使用受限 SSH/kubeconfig。
- Grafana 关闭匿名与自行注册，使用安全会话；数据库监控角色默认只读，未授予业务 schema 查询权。
- 内部 HTTP 与数据库连接尚无 mTLS/数据库 TLS；当前依赖私网、NetworkPolicy、令牌和 SCRAM。部署限制见 [K3s](k3s.md)。

新注册密码为 8–16 位可打印 ASCII 字符 U+0021–U+007E，允许字母、数字、符号任意组合，拒绝空格和非 ASCII。前后端均校验；已有账号仍验证原 BCrypt 哈希，bootstrap 配置独立处理。

## CI 扫描

Semgrep 使用严格源码规则；Trivy 检查源码 secrets、npm 锁文件、实际 Spring Boot JAR 的嵌套依赖及运行镜像。缺少 JAR、规则解析或扫描失败均阻断对应任务。镜像 HIGH/CRITICAL 和 secrets 门禁没有全局 ignore-unfixed；源码与基础镜像分开检查。

只有合格 main 才发布 digest 和部署。required checks 由 GitHub 仓库设置单独配置。报告一般保存七天，image lock 保存三十天；命中片段可能含敏感信息，不上传工作区私有目录和测试凭据。

本地扫描应在排除 `.env`、`.secrets/` 与私有 dataset 的干净副本运行，并包含当次构建的 JAR。扫描不覆盖全部 Git 历史、渗透路径或业务权限；真实 API 验收仍独立执行。

## 有限定期限的依赖例外

[trivyignore.yaml](../scripts/security/trivyignore.yaml)只对指定的 `spring-webmvc@6.2.19` CVE 保留适用性例外，到期日为 **2026-11-17**。例外表示当前架构未使用对应受影响功能，不表示依赖已修复。

| 记录 | 当前适用性依据 | 重新评估条件 |
| --- | --- | --- |
| CVE-2026-47884 | REST JSON API，无 XSLT/MVC 服务端视图 | 引入服务端视图或相关配置 |
| CVE-2026-47890 | 通知使用 JSON 轮询，无 SSE 视图片段 | 引入 SSE 或相关传输 |

[check-spring-scope.py](../scripts/security/check-spring-scope.py)在扫描前检查相关源码/配置并阻断不符合项。静态关键词不替代对反射或第三方配置的复核。引入相关功能、升级依赖或到期时须重新评估并移除不再成立的例外，不能自动延长。

运行密钥、数据库备份和漏洞命中详情保持受限。测试与安全检查的适用范围见[测试说明](test-coverage.md)。
