# 旧库组织模型升级

本指南仅用于尚未从个人 organizer 模型迁移到组织模型的旧数据库。当前生产数据已完成该升级，日常部署不重复执行这些步骤。当前权限与治理见[业务规则](functional-guide.md)，跨服务关闭/取消协议见[架构决策](adr/0001-service-boundaries.md)。

## 数据边界

Identity 拥有组织、成员和邀请；Catalog 保存活动的组织归属与创建者；Admission 保存销售、工作人员分配和票券。旧 organizer ID 保留历史来源，业务管理权限改由实时组织成员关系决定。平台 ADMIN 和旧全局 ORGANIZER/STAFF 不替代组织角色。

[migrate-organizations.py](../scripts/migrate-organizations.py)为旧事件/销售生成稳定的组织映射，核对订单、票券和库存指纹，再分别执行服务 schema 事务。它依赖 Compose；不能直接用于 K3s 生产环境。

## 维护步骤

1. 记录旧版本/镜像，备份数据库、凭据和 JWT 密钥，并在临时库验证恢复。
2. 关闭外部写入，排空发布/修订操作。保持维护，使用兼容的三个服务版本执行各自 Flyway 迁移。
3. 为目标旧库生成计划，检查每个 owner 的存在/活跃状态、组织名称和映射。计划含业务 ID，保持私有。

```bash
umask 077
python3 scripts/migrate-organizations.py \
  --compose-file /private/path/compose.yaml --env-file /private/path/runtime.env \
  --plan .secrets/organization-upgrade/plan.json
```

4. 确认备份与停写后应用审核过的同一份计划：

```bash
python3 scripts/migrate-organizations.py \
  --compose-file /private/path/compose.yaml --env-file /private/path/runtime.env \
  --plan .secrets/organization-upgrade/plan.json --apply --maintenance-confirmed
```

5. 检查所有活动/sales 已映射、原订单/请求键/票凭证/状态/库存一致。验证组织管理员权限、跨组织拒绝及旧票可用，再开放流量。

工具拒绝 pending 操作、变化的数据指纹、冲突映射及未完成记录。中断后使用同一审核计划继续；部分失败时保持维护，不手工跳过一致性校验。

## 兼容性与验证

旧版个人 owner 授权不能安全理解组织内部可见性、暂停/取消、CLOSING/DELETED 和分页 API。应用回退不撤销 Flyway，也不能在接收组织数据后直接运行旧二进制。按[发布回退](k3s-cd.md)核对 schema 与目标镜像；数据恢复需明确同步维护后的写入。

`organization-migration-acceptance.py` 在独立测试栈核对映射、幂等重放和票券/库存；`organization-acceptance.py`、`organization-governance-acceptance.py` 和 `predeployment-fixes-acceptance.py` 覆盖组织授权、治理与关闭恢复。全部使用独立数据，原始结果见[验收证据](evidence/README.md)。
