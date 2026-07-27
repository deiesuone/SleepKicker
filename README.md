# SleepKicker

ボイスチャンネルで一定時間無音のメンバーを VC から切断する Discord Bot のスケルトンです。

## アーキテクチャ

```
Discord Bot
│
├─ on_voice_state_update   … 入室で Bot 参加 / 無人で退出
├─ VoiceReceive            … ユーザー別 Opus パケット受信
├─ VoiceActivityService    … 最終発話時刻・無音閾値判定
└─ SleepGuardService       … move_to(None) で切断
```

スケルトン時点では PCM の音量（RMS）解析は行わず、**パケット受信＝発話** として扱います。監視対象は Bot が参加しているギルドの全 VC です。

## 必要要件

- Python 3.11+
- Discord Bot トークン
- サーバーでの権限: **Connect**, **Move Members**（View Channel も必要に応じて）
- Intent: `Guilds`, `Guild Voice States`（Privileged Intent は不要）

## セットアップ

### 1. 仮想環境（.venv）

プロジェクト直下で仮想環境を作成し、有効化します。

```powershell
# Windows (PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

```bash
# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 2. 依存関係のインストール

```bash
pip install -r requirements.txt
```

### 3. 環境変数（python-dotenv）

```powershell
# Windows
Copy-Item .env.example .env
```

```bash
# macOS / Linux
cp .env.example .env
```

`.env` を編集します。

| キー | 説明 | デフォルト |
|------|------|------------|
| `DISCORD_TOKEN` | Bot トークン（必須） | なし |
| `SILENCE_THRESHOLD_SECONDS` | 無音とみなす秒数 | `600`（10分） |
| `CHECK_INTERVAL_SECONDS` | 閾値チェック間隔（秒） | `30` |

`.env` は Git 管理対象外です。共有用の雛形は `.env.example` のみです。

### 4. Discord Developer Portal

1. [Discord Developer Portal](https://discord.com/developers/applications) で Application / Bot を作成
2. Bot トークンを `.env` の `DISCORD_TOKEN` に設定
3. OAuth2 URL Generator で `bot` スコープを選び、権限に **Connect** と **Move Members** を付与して招待

### 5. 起動

仮想環境を有効化した状態で:

```bash
python main.py
```

起動時に `bot/config.py` が `python-dotenv` 経由でプロジェクトルートの `.env` を読み込みます。

## スケルトンの制限

- PCM / RMS による音量しきい値は未実装
- 除外ロール・スラッシュコマンドによる設定変更なし
- 特定チャンネルのみ監視するホワイトリストなし
- ギルドにつき Bot は同時に 1 VC のみ（別チャンネルに人がいる場合は後から入った側へ付け替え）

## ライセンス

用途に合わせて各自で設定してください。
