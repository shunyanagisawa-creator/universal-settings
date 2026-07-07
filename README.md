# universal-settings

Ananda / HR-CCP / WAM の3プロジェクトが共有する **共有インフラ(litellm-proxy 等)のバージョンドリフト管理** をこの repo 1つに集約する、3プロジェクト横断・中立の器。

## 背景

3プロジェクトが litellm-proxy 等の共有インフラを持ち、バージョンドリフト(例: base image `main-latest` の無固定、Anthropic 新世代モデルの config 未登録)に誰も気づかない問題がある。これに対して2層で対策する。

- **Layer 1 = Renovate**: npm/pip 等パッケージマネージャが検知できる範囲の依存更新を、この repo の `default.json5` を各消費 repo が `extends` することで一括管理する。
- **Layer 2 = 自作チェック**: Renovate が知らない範囲(Anthropic モデル一覧の生死、Docker base image の実際の最新性)を `checks/` 配下の Python スクリプトで検知する。

## 構成図

```
universal-settings/ (この repo, 中立・横断)
├── default.json5              Layer1: Renovate shared preset(消費側が extends)
├── checks/
│   ├── check_anthropic_models.py   Layer2: Anthropic API × litellm-proxy config.yaml
│   ├── check_litellm_image.py      Layer2: litellm-proxy Dockerfile base image
│   ├── run_all.py                  上記2つを実行し status.json を書く
│   ├── render_issue.py             status.json → 月次 Issue の title/body
│   └── tests/test_checks.py        pure function の pytest(ネットワークなし)
├── status.json                 最新チェック結果(weekly workflow がコミット)
├── index.html                  status.json を表示する薄い status page(GitHub Pages)
└── .github/workflows/
    ├── weekly-check.yml         毎週チェック実行 → status.json 更新
    └── monthly-notify.yml       毎月 status.json から Issue を作成
```

## 各 repo からの参照方法

各消費 repo (Ananda / hrccp-mock / WAM-api / litellm-proxy 等) の `renovate.json` で:

```json
{
  "$schema": "https://docs.renovatebot.com/renovate-schema.json",
  "extends": ["github>shunyanagisawa-creator/universal-settings"]
}
```

Renovate は `github>owner/repo` 参照時、対象 repo の default branch ルートにある `default.json5`(または `default.json`)を自動的に preset として読む。

## Secrets

この repo 自体が持つ GitHub Actions secret は **`DOPPLER_TOKEN` の1つのみ**。実際に必要な認証情報(`ANTHROPIC_API_KEY` / `LITELLM_REPO_TOKEN`)は Doppler 側の `universal-settings` プロジェクト `prd` config に格納し、`doppler run` 経由で注入する。

| 名前 | 保管場所 | 用途 |
|---|---|---|
| `DOPPLER_TOKEN` | GitHub Actions secret | Doppler CLI 認証 |
| `ANTHROPIC_API_KEY` | Doppler (`universal-settings` / `prd`) | Anthropic `/v1/models` 取得 |
| `LITELLM_REPO_TOKEN` | Doppler (`universal-settings` / `prd`) | litellm-proxy repo の config.yaml / Dockerfile 読み取り(GitHub PAT) |

## 運用手順

1. **weekly-check.yml** が毎週月曜 05:00 JST に Layer2 チェックを実行し、`status.json` に変更があれば `github-actions[bot]` としてコミット&プッシュする。
2. **monthly-notify.yml** が毎月1日 07:00 JST に、その時点の `status.json` を元に drift の有無に関わらず GitHub Issue を1本作成する(タイトル「📡 共有インフラ月次レポート YYYY-MM」)。
3. Status page (GitHub Pages, `index.html` + `status.json`) で常時最新状態を確認できる: `https://shunyanagisawa-creator.github.io/universal-settings/`
4. drift/warn を確認したら、該当 repo(litellm-proxy 等)側で config.yaml / Dockerfile を手動修正する。**この repo 自体は他 repo のファイルを書き換えない**(読み取り専用チェックのみ)。

## Non-Goals(意図的にやらないこと)

- Renovate の automerge は設定しない(全 PR は人手レビュー)。
- 外部フレームワーク・PyYAML 等の依存導入はしない。`checks/` は Python 標準ライブラリのみで完結する(YAML パースは正規表現で必要行だけ抽出)。
- litellm-proxy 等、消費側 repo のファイルを直接書き換えることはしない。
