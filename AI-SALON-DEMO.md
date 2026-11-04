# AI 时代代码交付三道防线演示

本仓库基于 JetLinks Community `2.11` 分支制作，三个演示共用同一个业务契约：

> 设备实例导出必须分页，单次最多导出 5,000 条；5,000 本身是允许的边界值。

JetLinks 原始实现在按产品导出设备时会调用 `parameter.setPaging(false)`，这为“无上限查询”案例提供了真实业务切口。

## 演示一：Pre-commit 阻止凭据泄露

### 安装

```bash
./scripts/setup-hooks.sh
git config --get core.hooksPath
```

不需要 IDE 插件。演示 Hook 使用 Python 标准库检查暂存区中的高风险凭据和超过 5 MiB 的文件。生产仓库可以在相同 Hook 中换用 Gitleaks。

### 现场触发

创建 `demo-config/device-credentials.yml`：

```yaml
jetlinks:
  mqtt-token: example_replace_with_a_32_character_token
```

然后执行：

```bash
git add demo-config/device-credentials.yml  # 演示时先换成非 example 的长 Token
git commit -m "demo: add device credentials"
```

预期结果：提交被拒绝，输出命中文件和连接凭据。

### 讲解重点

- 这一层只做秒级、确定性、就地可修复的检查。
- Hook 可被 `--no-verify` 绕过，因此关键规则还必须在 CI 复检。

## 演示二：CI Gate 拒绝不具备合并资格的 PR

### 基线验证

```bash
export JAVA_HOME=/path/to/jdk-21
./scripts/ci/verify.sh
```

这个门禁依次产生三类证据：

1. `DeviceExportPolicy` 的 JDK 21 + JUnit 5 单元测试；
2. 设备导出接口是否关闭分页；
3. Maven 直接依赖是否符合准入清单。

### 失败 PR

`demo/ci-gate-failure` 分支会同时：

- 将设备导出改回 `parameter.setPaging(false)`；
- 在独立演示模块中增加未经准入的直接依赖。

单元测试仍然通过，但后两项门禁失败，用于证明“测试结果”不等于“合并资格”。

### GitHub 配置位置

- Actions：`.github/workflows/quality-gate.yml`。
- 触发方式：Pull Request 指向 `demo/baseline`。
- 合并条件：在分支保护中将 `Merge Gate` 设为必须通过。
- 保护分支：`Settings → Branches`，基线分支只能通过 PR 更新。

详细配置见 `GITHUB-DEMO-SETUP.md`。

## 演示三：Code Review 发现边界语义错误

`demo/code-review-boundary` 分支将：

```java
requestedRows <= MAX_EXPORT_ROWS
```

改为：

```java
requestedRows < MAX_EXPORT_ROWS
```

现有测试覆盖 4,999、5,001 和非正数，但故意没有覆盖正好 5,000，因此 CI 仍然全绿。代码 Javadoc 则明确写明“包含边界值”，为 AI 评审提供可核对的业务契约。

GitHub 上建议配置：

- 为设备管理模块指定 CodeOwner 或默认评审人；
- 至少一名评审人批准才能合并；
- AI 审查意见作为 PR 评论或审查线索，不直接充当硬门禁；
- 人工核对“最多 5,000 条”契约后拒绝该 PR，并要求补充 5,000 的精确边界测试。

## 现场稳定性

- Pre-commit 采用实时触发。
- CI Gate 展示 GitHub PR 的真实检查结果，同时保留本地日志和录屏。
- Code Review 使用真实 AI 审查输出；如平台 AI 能力不可用，使用事先保存的真实评审记录回放，不伪装为现场运行。
