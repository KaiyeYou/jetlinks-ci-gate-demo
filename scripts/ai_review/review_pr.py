#!/usr/bin/env python3
"""DeepSeek advisory PR reviewer using only the Python standard library."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


MARKER = "<!-- deepseek-ai-review -->"


def run_git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    return result.stdout


def read_text(path: Path, limit: int) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except (OSError, UnicodeError):
        return ""


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def changed_files(base: str, head: str) -> list[str]:
    return [line for line in run_git("diff", "--name-only", f"{base}...{head}").splitlines() if line]


def candidate_terms(paths: list[str], diff: str) -> set[str]:
    terms = {Path(path).stem for path in paths if Path(path).suffix in {".java", ".kt"}}
    terms.update(re.findall(r"\b(?:class|interface|record|enum)\s+([A-Z][A-Za-z0-9_]*)", diff))
    return {term for term in terms if len(term) >= 4}


def collect_related_files(repo: Path, paths: list[str], diff: str, config: dict[str, Any]) -> list[dict[str, str]]:
    max_files = int(config["max_related_files"])
    per_file = int(config["max_related_file_chars"])
    changed = set(paths)
    terms = candidate_terms(paths, diff)
    scored: list[tuple[int, str]] = []

    for suffix in ("*.java", "*.kt", "*.xml", "*.md"):
        for file_path in repo.rglob(suffix):
            if any(part in {".git", ".gradle", "target", "build"} for part in file_path.parts):
                continue
            rel = file_path.relative_to(repo).as_posix()
            if rel in changed:
                continue
            text = read_text(file_path, per_file)
            score = sum(1 for term in terms if term in text)
            if score:
                scored.append((score, rel))

    related = []
    for _, rel in sorted(scored, key=lambda item: (-item[0], item[1]))[:max_files]:
        related.append({"path": rel, "content": read_text(repo / rel, per_file)})
    return related


def build_context(repo: Path, event: dict[str, Any], config: dict[str, Any], base: str, head: str) -> dict[str, Any]:
    pr = event.get("pull_request", {})
    paths = changed_files(base, head)
    diff = run_git("diff", "--unified=35", f"{base}...{head}")[: int(config["max_diff_chars"])]
    commits = run_git("log", "--format=%H%n%s%n%b%n---", f"{base}..{head}")[:20000]

    contracts = []
    for rel in config.get("contract_files", []):
        content = read_text(repo / rel, 20000)
        if content:
            contracts.append({"path": rel, "content": content})

    changed_contents = []
    for rel in paths:
        path = repo / rel
        if path.suffix.lower() in {".java", ".kt", ".xml", ".yml", ".yaml", ".md", ".json"}:
            changed_contents.append({"path": rel, "content": read_text(path, 16000)})

    return {
        "pull_request": {
            "number": pr.get("number") or event.get("number"),
            "title": pr.get("title", ""),
            "body": pr.get("body") or "",
            "author": (pr.get("user") or {}).get("login", ""),
            "base": base,
            "head": head,
        },
        "commit_messages": commits,
        "changed_files": paths,
        "diff": diff,
        "changed_file_contents": changed_contents,
        "related_repository_context": collect_related_files(repo, paths, diff, config),
        "repository_contracts": contracts,
        "review_dimensions": config.get("review_dimensions", []),
        "severity_policy": config.get("severity_policy", {}),
        "limitations": [
            "上下文由本次变更驱动检索，不等于把整个仓库一次性放入模型",
            "模型结论仅供人工评审参考，不改变确定性 Merge Gate 结果",
        ],
    }


def call_deepseek(api_key: str, base_url: str, model: str, system_prompt: str, context: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "请审查以下 PR 上下文并输出 JSON：\n" + json.dumps(context, ensure_ascii=False)},
        ],
        "response_format": {"type": "json_object"},
        "max_tokens": 4096,
        "temperature": 0.1,
        "stream": False,
    }
    request = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(f"DeepSeek API HTTP {exc.code}: {detail}") from exc
    content = raw["choices"][0]["message"]["content"]
    if not content or not content.strip():
        raise RuntimeError("DeepSeek returned empty JSON content")
    return json.loads(content)


def validate_review(review: dict[str, Any], changed: set[str]) -> dict[str, Any]:
    if review.get("risk_level") not in {"none", "low", "medium", "high", "critical"}:
        review["risk_level"] = "medium"
    review["summary"] = str(review.get("summary", "未提供总结"))[:500]
    valid_findings = []
    for finding in review.get("findings", [])[:20]:
        if not isinstance(finding, dict) or finding.get("path") not in changed:
            continue
        if finding.get("severity") not in {"low", "medium", "high", "critical"}:
            continue
        try:
            line = max(1, int(finding.get("line", 1)))
        except (TypeError, ValueError):
            line = 1
        valid_findings.append(
            {
                "severity": finding["severity"],
                "title": str(finding.get("title", "未命名问题"))[:200],
                "path": finding["path"],
                "line": line,
                "evidence": str(finding.get("evidence", ""))[:1000],
                "consequence": str(finding.get("consequence", ""))[:1000],
                "recommendation": str(finding.get("recommendation", ""))[:1000],
                "needs_human_decision": bool(finding.get("needs_human_decision", False)),
            }
        )
    review["findings"] = valid_findings
    review["context_notes"] = [str(x)[:500] for x in review.get("context_notes", [])[:10]]
    review["review_coverage"] = [str(x)[:200] for x in review.get("review_coverage", [])[:20]]
    return review


def render_markdown(review: dict[str, Any], model: str) -> str:
    level = review["risk_level"].upper()
    lines = [
        MARKER,
        "## DeepSeek AI 语义评审（建议性）",
        "",
        f"**总体风险：{level}**　|　**模型：`{model}`**",
        "",
        review["summary"],
        "",
    ]
    findings = review["findings"]
    if findings:
        lines.extend(["### 有证据的问题", ""])
        for index, finding in enumerate(findings, 1):
            human = "需要人工业务判断" if finding["needs_human_decision"] else "可按技术证据核验"
            lines.extend(
                [
                    f"{index}. **[{finding['severity'].upper()}] {finding['title']}**",
                    f"   - 位置：`{finding['path']}:{finding['line']}`",
                    f"   - 证据：{finding['evidence']}",
                    f"   - 后果：{finding['consequence']}",
                    f"   - 建议：{finding['recommendation']}",
                    f"   - 处置：{human}",
                    "",
                ]
            )
    else:
        lines.extend(["### 未发现可证实的新增语义问题", "", "这不代表代码无风险，仍需责任人完成人工审批。", ""])
    if review["context_notes"]:
        lines.extend(["### 人工关注", ""] + [f"- {item}" for item in review["context_notes"]] + [""])
    lines.extend(
        [
            "### 评审边界",
            "",
            "- 本结果综合 PR 说明、提交备注、diff、变更文件、相关工程上下文与仓库契约。",
            "- AI 评审不参与 `Merge Gate` 的 PASS/FAIL，不替代 CODEOWNERS 和人工批准。",
            "- 上下文采用变更驱动检索；大型仓库仍可能存在未召回的跨模块影响。",
        ]
    )
    return "\n".join(lines)


def github_api(method: str, url: str, token: str, body: dict[str, Any] | None = None) -> Any:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8")) if response.length != 0 else None


def publish_comment(event: dict[str, Any], token: str, markdown: str) -> None:
    api_url = os.environ.get("GITHUB_API_URL", "https://api.github.com")
    repository = os.environ["GITHUB_REPOSITORY"]
    number = event.get("number") or event["pull_request"]["number"]
    comments_url = f"{api_url}/repos/{repository}/issues/{number}/comments"
    comments = github_api("GET", comments_url, token)
    existing = next((item for item in comments if MARKER in item.get("body", "")), None)
    if existing:
        github_api("PATCH", existing["url"], token, {"body": markdown})
    else:
        github_api("POST", comments_url, token, {"body": markdown})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--config", required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--event", default=os.environ.get("GITHUB_EVENT_PATH"))
    parser.add_argument("--base")
    parser.add_argument("--head")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo = Path(args.repo).resolve()
    event = load_json(Path(args.event)) if args.event else {"pull_request": {}}
    pr = event.get("pull_request", {})
    base = args.base or (pr.get("base") or {}).get("sha")
    head = args.head or (pr.get("head") or {}).get("sha")
    if not base or not head:
        raise SystemExit("base/head SHA is required")

    config = load_json(Path(args.config))
    context = build_context(repo, event, config, base, head)
    if args.dry_run:
        print(json.dumps(context, ensure_ascii=False, indent=2))
        return 0

    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    github_token = os.environ.get("GITHUB_TOKEN", "")
    if not api_key:
        print("DEEPSEEK_API_KEY is not configured; advisory review skipped.")
        return 0
    if not github_token:
        raise SystemExit("GITHUB_TOKEN is required to publish the PR comment")

    model = os.environ.get("DEEPSEEK_MODEL", "deepseek-flash")
    base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    prompt = Path(args.prompt).read_text(encoding="utf-8")
    try:
        review = validate_review(call_deepseek(api_key, base_url, model, prompt, context), set(context["changed_files"]))
        publish_comment(event, github_token, render_markdown(review, model))
    except Exception as exc:  # advisory service failure must not become a merge gate
        print(f"AI advisory review unavailable: {exc}", file=sys.stderr)
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
