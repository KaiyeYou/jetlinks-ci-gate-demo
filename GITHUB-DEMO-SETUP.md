# GitHub 三道防线演示配置

## 一、Pre-commit 在哪里配置

仓库统一管理：

- `.githooks/pre-commit`：Hook 入口；
- `scripts/quality/check_staged_commit.py`：秒级确定性规则；
- `scripts/setup-hooks.sh`：每个本地克隆的安装命令。

开发者在每次新克隆后执行一次：

```bash
./scripts/setup-hooks.sh
```

Git 不会自动执行仓库中的 Hook，因为 `.git/hooks` 不纳入版本控制。本项目通过 `core.hooksPath=.githooks` 让本地 Git 调用仓库统一管理的脚本。

Hook 可被 `--no-verify` 绕过，所以秘密检测在 GitHub Actions 中还会再执行一次。

## 二、CI Gate 在哪里配置

GitHub Actions 定义：

```text
.github/workflows/quality-gate.yml
```

Pull Request 指向 `demo/baseline` 时并行运行：

1. `Unit tests`：Java 17 编译和 JUnit 5 测试；
2. `Secret scan`：集中复检跟踪文件中的凭据；
3. `Export safety`：禁止设备导出关闭分页；
4. `Dependency admission`：新增直接依赖必须在准入清单内；
5. `Merge Gate`：汇总前四项结果。

GitHub 仓库页面的配置位置：

```text
Settings → Branches → Add branch protection rule
```

目标分支填写 `demo/baseline`，建议开启：

- Require a pull request before merging；
- Require status checks to pass before merging；
- 必选检查 `Merge Gate`；
- Require conversation resolution before merging；
- Do not allow bypassing the above settings（企业实施时开启）。

## 三、Code Review 在哪里配置

- `.github/CODEOWNERS`：按目录分配责任人；
- `.github/pull_request_template.md`：要求开发者声明依赖变更、AI使用和人工评审重点；
- `docs/ai-review-contract.md`：AI 评审输出契约。

个人演示仓库不强制“他人批准”，因为提交者无法自己批准自己的 PR。企业落地时应指定团队 CodeOwner，并要求至少一名非提交者批准。

AI 意见只作为 Review Comment，不配成 Required Status Check。

## 四、现场演示顺序

1. 本地基线分支触发 Pre-commit 拦截；
2. 打开 CI Gate 失败 PR：单测绿，导出安全和依赖准入红，`Merge Gate` 红；
3. 打开 Code Review PR：全部 Actions 为绿，但 AI Review Comment 指出 5,000 边界错误；
4. 人工核对 Javadoc 的“inclusive”契约，选择 Request changes，不合并该 PR。
