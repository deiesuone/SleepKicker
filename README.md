# SleepKicker

Discord のボイスチャンネルで、一定時間無音のメンバーを **VC から自動退出** させる Bot です。

サーバーからの追放（Kick）は行いません。`Move Members` によるボイスチャンネルからの切断のみです。

## 特徴

- 無音が続いたメンバーを VC から退出（デフォルト約 1 時間）
- 検知モード
  - **opus** … 音量（PCM RMS）。サーバー既定
  - **speaking** … Discord の発話インジケータに近い判定
- 個人設定コマンド `/sleepkicker`（有効／無効・分数・モード・音量しきい値）
- ギルドあたり同時 1 VC。人がいる部屋を見ているあいだは、空になるまで基本的に移動しない（監視リストでより優先度の高い部屋に人が入ったときだけ移る）
- `PRIORITY_VOICE_CHANNEL_ID` で監視 VC を限定可能（未設定または有効 ID なしなら全 VC）
- コマンド UI / 応答は日本語・英語対応

## 必要環境

- Python **3.11+**
- Discord Bot トークン

### 招待時のスコープ・権限

**Scopes:** `bot` / `applications.commands`

**Bot Permissions:**

| 権限 | 用途 |
|------|------|
| チャンネルを表示 | VC / チャンネルの閲覧 |
| 接続 | VC 参加 |
| 発言 | VC 滞在用（受信専用でも付与推奨） |
| メンバーを移動 | 無音ユーザーを VC から退出 |

「メンバーをキック」は不要です。監視したい VC で Bot ロールが拒否されていないことも確認してください。

## セットアップ

### 1. 取得

```bash
git clone https://github.com/<YOUR_USER>/SleepKicker.git
cd SleepKicker
```

### 2. 依存関係

```bash
pip install -r requirements.txt
```

`discord-ext-voice-recv` は DAVE（E2EE）受信対応のため、upstream マージ前の [PR #58](https://github.com/imayhaveborkedit/discord-ext-voice-recv/pull/58) コミットを Git ピン留めしています（`requirements.txt` 参照）。`git` が使える環境が必要です。

### 3. 環境変数

```powershell
Copy-Item .env.example .env
```

```bash
cp .env.example .env
```

`.env` を編集します（**トークンを公開リポジトリにコミットしないでください**）。

| キー | 説明 | デフォルト |
|------|------|------------|
| `DISCORD_TOKEN` | Bot トークン（必須） | なし |
| `SILENCE_THRESHOLD_SECONDS` | 無音とみなす秒数（個人未設定時） | `3600`（1時間） |
| `CHECK_INTERVAL_SECONDS` | 退出チェック間隔（秒） | `10` |
| `USE_MODE` | サーバー既定の検知（`opus` / `speaking`） | `opus` |
| `OPUS_VOLUME_THRESHOLD` | Opus の PCM RMS しきい値（`0` = ゲートなし） | `1000` |
| `DEBUG_LOG` | 追跡中ユーザーの残り秒などを 1 秒ごとにログ | `false` |
| `PRIORITY_VOICE_CHANNEL_ID` | 監視する VC ID（カンマ区切り・左が最優先。このサーバーに存在する ID のみ有効。有効な ID がなければ全 VC） | なし（全 VC） |

ブール値は `true` / `false` / `1` / `0` / `yes` / `no` を受け付けます。変更後は再起動が必要です。

### 4. Discord Developer Portal

1. [Discord Developer Portal](https://discord.com/developers/applications) で Application / Bot を作成
2. トークンを `.env` の `DISCORD_TOKEN` に設定
3. OAuth2 → URL Generator で上記スコープ・権限を付けてサーバーへ招待

### 5. 起動

```bash
python main.py
```

Windows では `.env` を置いたうえで `start_bot.bat` でも起動できます。

初回起動後、テキストチャンネルで `/` と入力すると `/sleepkicker` が出ます（ギルド同期のため、反映まで数十秒かかることがあります）。

## コマンド（`/sleepkicker`）

本人のみ設定でき、応答は ephemeral（自分だけに表示）です。設定はギルド別に `data/user_preferences.json` へ保存されます。変更時は無音タイマーをリセットします。

| コマンド | 内容 |
|----------|------|
| `/sleepkicker enable` | 無音退出のオン／オフ |
| `/sleepkicker timeout` | 無音何分で退出するか（1〜1440 分） |
| `/sleepkicker mode` | `opus` / `speaking` |
| `/sleepkicker volume` | Opus RMS しきい値（0〜32767。mode=opus で有効） |
| `/sleepkicker status` | 自分の設定を表示 |
| `/sleepkicker reset` | 個人設定を消し、サーバー既定に戻す |

スラッシュコマンドは通常のチャット投稿にはなりません。

## アーキテクチャ

```
Discord Bot
│
├─ on_voice_state_update   … 人がいる VC へ参加 / 空なら退出
├─ VoiceRecvClient         … Speaking / Opus 受信
├─ ActivitySink            … ユーザー実効 mode で発話判定
│   ├─ opus     … PCM RMS
│   └─ speaking … speaking start/stop
├─ VoiceActivityService    … 最終発話・閾値判定
├─ UserPreferencesStore    … 個人設定（JSON）
├─ /sleepkicker            … 個人設定コマンド
└─ SleepGuardService       … move_to(None) で退出
```

同一 VC 内で opus / speaking が混在しても、受信は両方行い判定だけ個人別に分岐します。

## プライバシー

無音判定のため、Bot が参加中の VC の音声パケットを受信します。録音・公開・聞き返し用の保存は行いません（判定と個人設定 JSON のみ）。サーバーへの導入時は、メンバーへの説明を推奨します。

## 制限

- ギルド（サーバー）につき Bot は同時に 1 VC のみ
- 監視中の VC に人がいるあいだは、ほかの部屋へは移らない。ただし `PRIORITY_VOICE_CHANNEL_ID` で並べた部屋のうち、今より左側（優先度が高い）の部屋に人が入ったときは、そちらへ移る

## 多言語

| パス | 役割 |
|------|------|
| `bot/texts/locales/ja.py` | 日本語 |
| `bot/texts/locales/en.py` | 英語（フォールバック） |
| `bot/texts/i18n.py` | `t()` / `ls()` / Discord `Translator` |

コマンド UI はクライアント言語、応答は `interaction.locale` に応じます（未対応は英語）。

## ライセンス

[MIT](LICENSE) License
