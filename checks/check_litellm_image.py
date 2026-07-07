"""Layer2 チェック: litellm-proxy の Dockerfile base image 固定/陳腐化検知。

- litellm-proxy repo の Dockerfile を GET し FROM 行から tag を取り出す
- tag が main-latest/latest/main なら無固定として warn
- 固定タグなら BerriAI/litellm の最新 release tag_name と比較し、古ければ warn

stdlib のみ(urllib)。
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Optional

CHECK_ID = "litellm-base-image"
CHECK_NAME = "litellm-proxy base image 固定/陳腐化"

DOCKERFILE_URL = (
    "https://api.github.com/repos/shunyanagisawa-creator/litellm-proxy/contents/Dockerfile"
)
LITELLM_RELEASES_URL = "https://api.github.com/repos/BerriAI/litellm/releases/latest"

UNPINNED_TAGS = {"main-latest", "latest", "main"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_from_line(line: str) -> Optional[str]:
    """`FROM image:tag [AS stage]` から tag を取り出す。FROM 行でなければ None。

    tag 省略時(コロン無し)は暗黙の "latest" を返す。
    """
    stripped = line.strip()
    if not stripped[:4].upper() == "FROM":
        return None
    parts = stripped.split()
    if len(parts) < 2:
        return None
    image_ref = parts[1]
    if ":" in image_ref:
        return image_ref.split(":", 1)[1]
    return "latest"


def judge_tag(tag: str, latest_release_tag: Optional[str]) -> dict:
    """tag の固定度・鮮度を判定する pure function。"""
    if tag in UNPINNED_TAGS:
        return {
            "status": "warn",
            "summary": f"base image tag '{tag}' は無固定(unpinned) — 明示バージョンに固定推奨",
        }

    if latest_release_tag is None:
        return {
            "status": "unknown",
            "summary": f"base image tag '{tag}' だが最新リリースタグを取得できず比較不可",
        }

    norm_tag = tag.lstrip("vV")
    norm_latest = latest_release_tag.lstrip("vV")
    if norm_tag == norm_latest:
        return {
            "status": "ok",
            "summary": f"base image tag '{tag}' は最新({latest_release_tag})",
        }
    return {
        "status": "warn",
        "summary": f"base image tag '{tag}' は最新({latest_release_tag})より古い可能性",
    }


def fetch_dockerfile(repo_token: str) -> str:
    req = urllib.request.Request(
        DOCKERFILE_URL,
        headers={
            "Authorization": f"Bearer {repo_token}",
            "Accept": "application/vnd.github.raw+json",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8")


def fetch_latest_litellm_release_tag(repo_token: Optional[str] = None) -> Optional[str]:
    headers = {"Accept": "application/vnd.github+json"}
    if repo_token:
        headers["Authorization"] = f"Bearer {repo_token}"
    req = urllib.request.Request(LITELLM_RELEASES_URL, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        return payload.get("tag_name")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError):
        return None


def extract_from_tag(dockerfile_text: str) -> Optional[str]:
    for line in dockerfile_text.splitlines():
        tag = parse_from_line(line)
        if tag is not None:
            return tag
    return None


def run() -> dict:
    """fetch -> parse/judge -> dict。失敗しても例外を外に出さず status unknown を返す。"""
    checked_at = _now_iso()
    try:
        repo_token = os.environ["LITELLM_REPO_TOKEN"]

        dockerfile_text = fetch_dockerfile(repo_token)
        tag = extract_from_tag(dockerfile_text)
        if tag is None:
            return {
                "id": CHECK_ID,
                "name": CHECK_NAME,
                "status": "unknown",
                "summary": "Dockerfile に FROM 行が見つからない",
                "details": [],
                "checked_at": checked_at,
            }

        latest_release_tag = fetch_latest_litellm_release_tag(repo_token)
        result = judge_tag(tag, latest_release_tag)
        result["id"] = CHECK_ID
        result["name"] = CHECK_NAME
        result["details"] = [f"Dockerfile FROM tag: {tag}", f"最新 BerriAI/litellm release: {latest_release_tag}"]
        result["checked_at"] = checked_at
        return result
    except KeyError as e:
        return {
            "id": CHECK_ID,
            "name": CHECK_NAME,
            "status": "unknown",
            "summary": f"環境変数が未設定: {e}",
            "details": [],
            "checked_at": checked_at,
        }
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError) as e:
        return {
            "id": CHECK_ID,
            "name": CHECK_NAME,
            "status": "unknown",
            "summary": f"チェック実行時にエラー: {e}",
            "details": [],
            "checked_at": checked_at,
        }
    except Exception as e:  # noqa: BLE001 - Guardrail: 例外で死なず unknown を返す
        return {
            "id": CHECK_ID,
            "name": CHECK_NAME,
            "status": "unknown",
            "summary": f"想定外のエラー: {e}",
            "details": [],
            "checked_at": checked_at,
        }


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
