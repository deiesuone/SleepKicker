# SleepKicker

ボイスチャンネルで一定時間無音のメンバーを VC から切断する Discord Bot のスケルトンです。

## アーキテクチャ

```
Discord Bot
│
├─ on_voice_state_update   … 人がいる VC へ参加 / 空なら退出（監視中は他 VC へ移らない）
├─ VoiceRecvClient         … VC 接続（Speaking WS / Opus 受信）
├─ 発話ソース（独立フラグ・OR）
│   ├─ USE_SPEAKING … speaking start/stop（パケット合成・外周近似）
│   └─ USE_OPUS     … ユーザー別 Opus パケット受信
├─ VoiceActivityService    … 最終発話時刻・無音閾値判定
└─ SleepGuardService       … move_to(None) で切断
```

`USE_SPEAKING` と `USE_OPUS` は独立して ON/OFF でき、**どちらかが発話とみなせば**無音タイマーがリセットされます（OR）。

Discord のボイスは DAVE（E2EE）のため、受信には `davey` と DAVE 対応の `discord-ext-voice-recv`（現状は PR #58）が必要です。`USE_SPEAKING` はライブラリがパケット活動から合成する `voice_member_speaking_start` / `stop`（緑の丸の近似）で発話中ラッチを張ります。あわせて Opus パケット受信中も最終発話時刻を更新します。PCM の音量（RMS）解析は未実装です。監視対象は Bot が参加しているギルドの全 VC です。

| フラグ | 判定 |
|--------|------|
| `USE_SPEAKING` | パケット合成の speaking start/stop（外周の近似） |
| `USE_OPUS` | Opus パケット受信 |

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
| `USE_OPUS` | Opus パケットで発話判定 | `true` |
| `USE_SPEAKING` | speaking start/stop（外周近似）で発話判定 | `false` |
| `DEBUG_LOG` | 追跡中ユーザーのキックまで残り秒を1秒ごとにログ | `false` |
| `PRIORITY_VOICE_CHANNEL_ID` | 優先監視チャンネル ID（カンマ区切り・左が最優先。存在しない ID は無視） | なし |

ブール値は `true` / `false` / `1` / `0` / `yes` / `no` を受け付けます。`USE_OPUS` と `USE_SPEAKING` が両方 `false` は起動エラーです。フラグ変更後は Bot の再起動が必要です。

`PRIORITY_VOICE_CHANNEL_ID` の例: `111,222,333`（左から順に優先）。リスト内で人がいる最左のチャンネルへ、他 VC 監視中でも移動します。人がいなければ通常どおり「監視中の人がいる VC からは動かない」です。

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
- ギルドにつき Bot は同時に 1 VC のみ。**人がいる VC を監視中は他 VC へ移動しない**（入退室音を抑える）。例外として `PRIORITY_VOICE_CHANNEL_ID`（カンマ区切り・左が最優先）に人がいるときは、その中で最優先のチャンネルへ移動する。監視中の VC が空になったら退出し、別 VC に人がいればそちらへ入る（優先リストがあれば優先）
- 起動時は優先リスト（人がいる最左）→ それ以外で最初に見つかった人がいる VC、の順

## ライセンス

用途に合わせて各自で設定してください。
