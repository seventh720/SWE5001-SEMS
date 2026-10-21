# 安全门禁与依赖适用性

PR #23 合并提交 `076f500` 的 [main 流水线](https://github.com/seventh720/SWE5001-SEMS/actions/runs/39638785624)已通过源码/依赖/secret 和运行镜像扫描，并完成镜像发布与测试环境部署。扫描结果对应当次漏洞数据库与规则版本；有期限的适用性例外和后续复核要求见下文。最终状态统一见[当前进度](progress.md)。

## 注册密码规则

新注册要求 8–16 位，允许 ASCII 英文字母、数字和英文半角符号（U+0021–U+007E），可单独使用或任意组合；拒绝空格、控制字符、中文和全角符号。前端提示和提交校验、注册 API 请求校验与应用服务入口均执行该规则。已有密码不重新校验新格式，登录仍验证原 BCrypt 哈希；bootstrap 凭据保持独立。无需数据库迁移或重置已有用户密码。验收与压测脚本生成符合新规则的测试密码。

## 执行范围

- Semgrep 1.181.0 使用 Java/TypeScript 规则集扫描源码，`--error --strict` 使发现和解析失败均阻断；规则从 registry 获取，报告记录本次规则信息，不能宣称规则库永远不变。
- Trivy 0.75.0 扫描 npm 锁文件和源码 secrets；另以 rootfs 模式检查实际构建的三个 Spring Boot JAR 的嵌套依赖。不是仅扫描无法完整解析父 BOM 的 pom.xml；缺少 JAR 时拒绝扫描。
- 每个发布镜像及 nginx/Caddy 镜像扫描 HIGH/CRITICAL 漏洞和 secrets；扫描失败不推送、不部署。没有全局 `ignore-unfixed`，没有关闭 TLS 验证，也没有失败继续发布。
- PR 可构建和扫描，但只允许 main 推送 GHCR。部署依赖安全和镜像任务成功。GitHub 的 required status checks 需要另在仓库设置中选中，workflow 本身不会修改分支保护。
- 报告作为 CI artifact 保存七天；镜像 digest 锁文件保存三十天，并随部署包保留在服务器 release 目录。scanner 报告可能含命中片段，应限制 artifact 访问；不要上传本地凭据目录或 benchmark dataset。

本地应在不含 `.env`、`.secrets` 和私有 dataset 的干净副本运行 `bash scripts/security/scan.sh source`；其中须有本轮构建的 JAR。源码扫描不覆盖 Git 历史，也不是完整渗透测试或业务权限证明。

## 2026-10-19 依赖处置

2026-10-21 补充：PR #21 的镜像扫描发现 Caddy 二进制使用的 Go 1.26.9 命中 HIGH `CVE-2026-111943`（`crypto/x509` 对不可信中间证书的处置）。构建工具链升级至同系列 1.26.10，Caddy 2.11.7、x/net 0.60.0 及现有扫描阈值保持原配置，没有新增豁免。修复依据见 [Go 公告](https://github.com/golang/go/issues/82345)与 [1.26.10 发布记录](https://go.dev/doc/devel/release#go1.26.10)；历史扫描通过仅对应当时漏洞库。

初次扫描在已打包的 Java 依赖中发现 Jackson、Tomcat、pgJDBC 以及 Spring MVC 相关记录。同系列修复版本集中在根 pom 中管理：Jackson BOM 2.21.7、Tomcat 10.1.60、pgJDBC 42.7.12。版本改动必须经过单元、真实 API/数据库和镜像扫描，不能只看依赖下载成功。Java 镜像明确采用 Temurin 21 / Ubuntu 24.04（noble）；Web/网关采用维护中的 nginx stable Alpine，PostgreSQL/Caddy 也在构建时安装 Alpine 安全更新，最终所有镜像以 digest 锁定。PostgreSQL 的入口权限切换改用 Alpine su-exec，替代附带旧 Go 运行库的 gosu；须验证全新数据库初始化。Caddy 保持 2.11.7，按官方方式重编译标准模块，更新 Go 至 1.26.9、x/net 至 0.60.0，并验证现有 Caddyfile；参考 [Caddy 官方构建说明](https://caddyserver.com/docs/build)。源码依赖扫描通过不代表基础镜像通过，必须分别检查。

Spring Framework 6.2.19 的下列两条记录按触发条件评估为**当前应用不使用受影响功能**，不是已经升级修复，也不是全局忽略：

| 记录 | 触发条件与当前依据 | 复核要求 |
|---|---|---|
| CVE-2026-47884 | Spring 官方说明要求 XsltView 与隐式视图映射；本系统后端为 REST JSON API，前端静态文件由 nginx 提供，没有 XSLT/MVC 视图 | 引入服务端视图立即移除例外并重新评估 |
| CVE-2026-47890 | Spring 官方说明要求以 SSE 传输视图片段；通知采用 JSON 轮询，无 SSE/视图片段 | 引入 SSE 立即移除例外并重新评估 |

例外在 `scripts/security/trivyignore.yaml` 中仅匹配 `spring-webmvc@6.2.19` 的指定 CVE，2026-11-17 到期，扫描报告保留 suppressed finding。`check-spring-scope.py` 在每次扫描前检查源码与配置是否出现对应功能，发现后阻断；静态关键词检查不能替代架构复核，反射/第三方配置也必须纳入人工评估。后续迁移受支持的 Spring 版本或使用正式维护补丁后应删除例外，不应无限续期。

依据：[Spring XSLT 公告](https://spring.io/security/cve-2026-47884/)、[Spring SSE 公告](https://spring.io/security/cve-2026-47890/)、[Tomcat 10 安全公告](https://tomcat.apache.org/security-10.html)、[Jackson 2.21.7](https://github.com/FasterXML/jackson/wiki/Jackson-Release-2.21.7)、[Trivy 限定例外与到期规则](https://trivy.dev/docs/latest/configuration/filtering/)。安全等级在数据库和厂商之间可能不同，本门禁采用扫描器输出并记录适用性，不通过降低整体等级绕过告警。
