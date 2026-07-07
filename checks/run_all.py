"""全 Layer2 チェックを実行し、repo ルートに status.json を書き出す。

`python checks/run_all.py` として実行する想定(cwd は repo ルート)。
各チェックは run() 内で例外を吸収し status "unknown" を返すため、
本スクリプト自体が env/ネットワーク不在で落ちることはない。
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

# `python checks/run_all.py` として直接実行されたときも `checks` package を import
# できるよう、repo ルートを sys.path に足しておく(pytest/`python -m checks.run_all`
# 経由では既に解決できているため実害はない)。
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from checks import check_anthropic_models
from checks import check_litellm_image

STATUS_JSON_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "status.json")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_status() -> dict:
    checks = [
        check_anthropic_models.run(),
        check_litellm_image.run(),
    ]
    return {
        "generated_at": _now_iso(),
        "checks": checks,
    }


def main() -> None:
    status = build_status()
    with open(STATUS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(json.dumps(status, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
