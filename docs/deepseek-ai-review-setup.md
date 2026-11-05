# DeepSeek AI 语义评审配置

本配置属于第三层“语义评审与责任审批”，只在 Pull Request 中提供建议，不加入 `Merge Gate`，也不替代 CODEOWNERS 和人工批准。

## GitHub 侧一次性配置

1. 打开仓库 **Settings → Secrets and variables → Actions → Secrets**。
2. 新建 Repository secret：`DEEPSEEK_API_KEY`。Key 只在 GitHub 页面录入，不写入代码、PR、日志或聊天。
3. 可选：在同一页面的 **Variables** 中创建：
   - `DEEPSEEK_BASE_URL=https://api.deepseek.com`
   - `DEEPSEEK_MODEL=deepseek-flash`
4. 在 **Settings → Actions → General → Workflow permissions** 中允许工作流创建 PR 评论；工作流本身只申请 `contents: read` 与 `pull-requests: write`。

官方入口：

- Secrets：<https://github.com/KaiyeYou/jetlinks-ci-gate-demo/settings/secrets/actions>
- Actions 权限：<https://github.com/KaiyeYou/jetlinks-ci-gate-demo/settings/actions>
- DeepSeek API：<https://api-docs.deepseek.com/api/create-chat-completion/>

## 模型实际读取的内容

- PR 标题、说明、作者；
- base 到 head 的全部提交备注；
- 变更文件列表、diff 和变更文件正文；
- 根据 Java/Kotlin 类型名检索到的相关源码、测试、XML 与文档；
- `docs/ai-review-contract.md`、PR 模板和 CODEOWNERS；
- `.ai-review/config.json` 定义的评审维度与严重度口径。

这属于“变更驱动的工程上下文”，不是把整个仓库无差别塞给模型。对于大型企业工程，应由统一评审服务建设代码索引、依赖图、规则库和历史缺陷库，再按 PR 检索相关上下文。

## 安全与门禁边界

- API Key 仅对同仓库 PR 可用；来自 fork 的 PR 不执行此工作流。
- 评审器脚本从 PR 的 base commit 检出，避免 PR 修改脚本后窃取密钥；PR 代码只作为只读输入分析。
- 调用外部模型前先用基线中的受信任脚本扫描 PR 工作区；疑似凭据命中时不向 DeepSeek 发送内容。
- DeepSeek 不执行 PR 代码。
- API 或模型故障返回成功跳过，不影响确定性 CI Gate。
- 模型只允许报告本次变更文件中的 finding；结论以固定评论形式更新，避免重复刷屏。

## 企业数据边界

DeepSeek API 是仓库外部服务。正式接入企业代码前，需要由安全、法务或数据治理责任人确认哪些代码、注释、提交备注和 PR 描述允许出域。含客户数据、生产配置、商业秘密或受限算法的仓库，不应直接复用本演示配置；应改接企业内网部署的兼容模型服务，或先建设脱敏与出域审批策略。

## 演示验证

1. 将本配置合并到 `demo/baseline`。
2. 打开或更新 `demo/code-review-boundary` 对应的 PR。
3. 在 Actions 中看到 **DeepSeek AI Advisory Review**。
4. PR Conversation 出现 **DeepSeek AI 语义评审（建议性）** 评论。
5. 预期模型识别：代码使用 `< 5000`，而仓库契约规定“最大同步导出 5,000 行，含 5,000”；CI 仍全绿，AI 给出语义警告，最终由人工决定。

本地可先检查上下文采集，不调用 API：

```bash
python3 scripts/ai_review/review_pr.py \
  --repo . \
  --config .ai-review/config.json \
  --prompt .ai-review/system-prompt.md \
  --base demo/baseline \
  --head demo/code-review-boundary \
  --dry-run
```
