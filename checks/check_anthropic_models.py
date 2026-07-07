"""Layer2 チェック: Anthropic モデル一覧 x litellm-proxy config.yaml の drift 検知。

- Anthropic API `/v1/models` から現存モデル slug 一覧を取得
- litellm-proxy repo の config.yaml から `anthropic/<slug>` 参照を正規表現で抽出
- diff_models() で突合し、config が参照するのに API に無いモデルを drift、
  API にあるが config 未参照の claude-* モデルを warn として返す。

stdlib のみ(urllib)。PyYAML 等の外部依存は使わない。
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Optional

CHECK_ID = "anthropic-models"
CHECK_NAME = "Anthropic モデル一覧 × litellm-proxy config"

ANTHROPIC_MODELS_URL = "https://api.anthropic.com/v1/models?limit=100"
LITELLM_CONFIG_URL = (
    "https://api.github.com/repos/shunyanagisawa-creator/litellm-proxy/contents/config.yaml"
)

# config.yaml 中の `model: anthropic/<slug>` 形式を拾う。gemini/openai 等 anthropic/ 以外は無視。
MODEL_LINE_RE = re.compile(r"model:\s*anthropic/([A-Za-z0-9\-.]+)")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def diff_models(referenced: list[str], available: list[str]) -> dict:
    """config が参照する slug と API 一覧の slug を突合する pure function。

    判定優先度: drift(参照先が存在しない) > warn(未参照の新モデルがある) > ok
    """
    referenced_set = set(referenced)
    available_set = set(available)

    missing = sorted(referenced_set - available_set)
    new_claude = sorted(
        m for m in (available_set - referenced_set) if m.startswith("claude-")
    )

    details: list[str] = []
    for m in missing:
        details.append(f"missing: config が参照する '{m}' は Anthropic API 一覧に存在しない")
    for m in new_claude:
        details.append(f"new: API 一覧にある '{m}' は config 未参照(新モデルの可能性)")

    if missing:
        status = "drift"
        summary = f"config参照だがAPI一覧に無いモデルあり: {', '.join(missing)}"
    elif new_claude:
        status = "warn"
        summary = f"新しいAnthropicモデルを検知(config未参照): {', '.join(new_claude)}"
    else:
        status = "ok"
        summary = "config参照モデルは全てAPI一覧に存在、新モデルなし"

    return {"status": status, "summary": summary, "details": details}


def fetch_available_models(api_key: str) -> list[str]:
    req = urllib.request.Request(
        ANTHROPIC_MODELS_URL,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return [item["id"] for item in payload.get("data", [])]


def fetch_config_yaml(repo_token: str) -> str:
    req = urllib.request.Request(
        LITELLM_CONFIG_URL,
        headers={
            "Authorization": f"Bearer {repo_token}",
            "Accept": "application/vnd.github.raw+json",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8")


def extract_referenced_models(config_yaml_text: str) -> list[str]:
    return sorted(set(MODEL_LINE_RE.findall(config_yaml_text)))


def run() -> dict:
    """fetch -> diff -> dict。失敗しても例外を外に出さず status unknown を返す。"""
    checked_at = _now_iso()
    try:
        api_key = os.environ["ANTHROPIC_API_KEY"]
        repo_token = os.environ["LITELLM_REPO_TOKEN"]

        available = fetch_available_models(api_key)
        config_yaml_text = fetch_config_yaml(repo_token)
        referenced = extract_referenced_models(config_yaml_text)

        result = diff_models(referenced, available)
        result["id"] = CHECK_ID
        result["name"] = CHECK_NAME
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
