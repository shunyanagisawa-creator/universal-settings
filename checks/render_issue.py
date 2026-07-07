"""status.json から月次通知 Issue の title/body を組み立てる。

stdlib のみ。`python checks/render_issue.py status.json` のように呼ぶと
title/body を標準出力に区切り線付きで出す(monthly-notify.yml から利用)。
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

STATUS_PAGE_URL = "https://shunyanagisawa-creator.github.io/universal-settings/"
STATUS_JSON_URL = "https://shunyanagisawa-creator.github.io/universal-settings/status.json"

STATUS_BADGE = {
    "ok": "🟢 ok",
    "warn": "🟡 warn",
    "drift": "🔴 drift",
    "unknown": "⚪ unknown",
}


def render_title() -> str:
    now = datetime.now(timezone.utc)
    return f"📡 共有インフラ月次レポート {now.strftime('%Y-%m')}"


def render_body(status: dict) -> str:
    lines = [
        "## 共有インフラ drift チェック結果",
        "",
        f"- 生成時刻: {status.get('generated_at', '不明')}",
        f"- Status page: {STATUS_PAGE_URL}",
        f"- status.json: {STATUS_JSON_URL}",
        "",
        "| チェック | 状態 | 概要 |",
        "|---|---|---|",
    ]
    for check in status.get("checks", []):
        badge = STATUS_BADGE.get(check.get("status"), check.get("status", "?"))
        name = check.get("name", check.get("id", "?"))
        summary = check.get("summary", "")
        lines.append(f"| {name} | {badge} | {summary} |")
    lines.append("")
    lines.append("詳細は各チェックの `details` を status.json 参照。")
    return "\n".join(lines)


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else "status.json"
    with open(path, "r", encoding="utf-8") as f:
        status = json.load(f)

    print(render_title())
    print("---BODY---")
    print(render_body(status))


if __name__ == "__main__":
    main()
