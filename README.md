# SleepKicker

ボイスチャンネルで一定時間無音のメンバーを VC から退出させる Discord Bot です。

## アーキテクチャ

```
Discord Bot
│
├─ on_voice_state_update   … 人がいる VC へ参加 / 空なら退出（監視中は他 VC へ移らない）
├─ VoiceRecvClient         … VC 接続（Speaking イベント / Opus 受信を常時）
├─ ActivitySink            … ユーザー実効 mode で発話判定
│   ├─ opus     … PCM RMS（音量）でタイマー更新
│   └─ speaking … 発話インジケータ start/stop でラッチ
├─ VoiceActivityService    … 最終発話時刻・無音閾値判定
├─ UserPreferencesStore    … 本人設定（JSON）
├─ /sleepkicker            … enable / timeout / mode / volume など
└─ SleepGuardService       … move_to(None) で退出
```

サーバー既定の検知方式は `USE_MODE=opus|speaking`。ユーザーは `/sleepkicker mode` で上書きできます。同一 VC 内で opus / speaking が混在しても、受信は両方行い判定だけ個人別に分岐します。

ユーザーは `/sleepkicker` で無音退出の有効／無効・無音分数・検知モード・Opus 音量しきい値を自分用に設定できます（ギルド別・`data/user_preferences.json`）。未設定時はサーバー既定（`SILENCE_THRESHOLD_SECONDS` / `USE_MODE` / `OPUS_VOLUME_THRESHOLD`）が使われます。各サブコマンドは自分の項目だけを変更します（例: `timeout` は分数のみで、enable は変えません）。

Discord のボイスは DAVE（E2EE）のため、受信には `davey` と DAVE 対応の `discord-ext-voice-recv` が必要です。現状は [PR #58](https://github.com/imayhaveborkedit/discord-ext-voice-recv/pull/58) の内容を **コミットハッシュ固定**（`requirements.txt`）で入れています。上流マージ後は通常リリースへ切り替え、それまではハッシュを動かさない方針です。`speaking` はパケット活動から合成する `voice_member_speaking_start` / `stop`（緑の丸の近似）です。`opus` はデコードした PCM の RMS で判定します（しきい値 0 なら音量ゲートなし）。監視対象は Bot が参加しているギルドの全 VC です。

| モード | 判定 |
|--------|------|
| `opus` | Opus→PCM の音量（RMS） |
| `speaking` | 発話インジケータ（外周の近似） |

## 必要要件

- Python 3.11+
- Discord Bot トークン
- Intent（Developer Portal → Bot）: **Guilds**, **Guild Voice States**（Privileged Intent は不要）

### Bot 権限・スコープ

招待時（OAuth2 → URL Generator）で、ポータル上の日本語名だと次を選びます。

**スコープ（Scopes）**

| 名前 | 用途 |
|------|------|
| `bot` | サーバーへ Bot として参加 |
| `applications.commands` | `/sleepkicker` などのスラッシュコマンド登録 |

**Bot の権限（Bot Permissions）**

| ポータル上の名前 | 用途 |
|------------------|------|
| **チャンネルを表示** | VC / テキストチャンネルの閲覧 |
| **接続** | ボイスチャンネルへ参加 |
| **発言** | VC 滞在に実質必要なことが多い（受信専用でも付与推奨） |
| **メンバーを移動** | 無音ユーザーを VC から退出させる（サーバーからの追放ではない） |

「メンバーをキック」は不要です（この Bot はサーバー追放ではなく、VC からの退出＝移動を使います）。  
「スラッシュコマンドを使用」「メッセージを送信」も必須ではありません（コマンド応答は Interaction 経由です）。  
監視したい VC では、Bot ロールがそのチャンネルを見られて接続できること（チャンネル権限で拒否されていないこと）も確認してください。

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
| `SILENCE_THRESHOLD_SECONDS` | 無音とみなす秒数（個人 `/timeout` 未設定時） | `3600`（1時間） |
| `CHECK_INTERVAL_SECONDS` | 退出チェック間隔（秒） | `10` |
| `USE_MODE` | サーバー既定の検知モード（`opus` / `speaking`） | `opus` |
| `OPUS_VOLUME_THRESHOLD` | Opus 判定の PCM RMS（0=ゲートなし。個人 `/volume` 未設定時） | `1000` |
| `DEBUG_LOG` | 追跡中ユーザーの退出まで残り秒を1秒ごとにログ | `false` |
| `PRIORITY_VOICE_CHANNEL_ID` | 優先監視チャンネル ID（カンマ区切り・左が最優先。存在しない ID は無視） | なし |

ブール値は `true` / `false` / `1` / `0` / `yes` / `no` を受け付けます。設定変更後は Bot の再起動が必要です。

`PRIORITY_VOICE_CHANNEL_ID` の例: `111,222,333`（左から順に優先）。リスト内で人がいる最左のチャンネルへ、他 VC 監視中でも移動します。人がいなければ通常どおり「監視中の人がいる VC からは動かない」です。

`.env` は Git 管理対象外です。共有用の雛形は `.env.example` のみです。

### 4. Discord Developer Portal

1. [Discord Developer Portal](https://discord.com/developers/applications) で Application / Bot を作成
2. Bot トークンを `.env` の `DISCORD_TOKEN` に設定
3. Bot ページで Intent **Guilds** / **Guild Voice States** を有効化
4. OAuth2 → URL Generator でスコープ **`bot`** + **`applications.commands`** を選び、Bot の権限に **チャンネルを表示** / **接続** / **発言** / **メンバーを移動** を付けて招待（詳細は上記「Bot 権限・スコープ」）

### 5. 起動

仮想環境を有効化した状態で:

```bash
python main.py
```

起動時に `bot/config.py` が `python-dotenv` 経由でプロジェクトルートの `.env` を読み込みます。初回起動後、テキストチャンネルで `/` と入力すると `/sleepkicker` が出ます（**ギルド単位**で同期するため、だいたい即時〜数十秒で反映されます）。

## ユーザー向けコマンド（`/sleepkicker`）

本人のみ設定でき、応答は本人にだけ見えます（ephemeral）。設定はサーバー（ギルド）ごとに `data/user_preferences.json` へ保存されます。設定変更時は無音タイマーをリセットします。

| コマンド | 内容 |
|----------|------|
| `/sleepkicker enable enabled:True` | 無音退出を有効にする |
| `/sleepkicker enable enabled:False` | 無効（無音でも退出しない） |
| `/sleepkicker timeout minutes:60` | 無音何分で退出するか（1〜1440 分）。enable は変更しない |
| `/sleepkicker mode value:opus` | 音量判定（Opus / RMS） |
| `/sleepkicker mode value:speaking` | 発話インジケータ判定 |
| `/sleepkicker volume rms:500` | 自分の Opus RMS しきい値（0〜32767。0=ゲートなし）。mode=opus で有効 |
| `/sleepkicker status` | 自分の現在設定を表示 |
| `/sleepkicker reset` | 個人設定をすべて消し、サーバー既定に戻す |

### 多言語（ユーザー向け文言）

スラッシュ説明・選択肢名・コマンド応答は `bot/texts/` のキーベースカタログで管理しています。

| パス | 役割 |
|------|------|
| `bot/texts/locales/ja.py` | 日本語 |
| `bot/texts/locales/en.py` | 英語（未対応 locale のフォールバック） |
| `bot/texts/i18n.py` | `t()` / `ls()` / Discord `Translator` |
| `bot/texts/sleepkicker.py` | キー定数と文言の組み立て |

- **用意言語**: 現状は日本語と英語のみ
- **コマンド UI**（説明など）: Discord クライアントの言語向けに `CatalogTranslator` が同期時へ翻訳を載せます（未対応言語は英語）
- **応答メッセージ**: 実行したユーザーの `interaction.locale`（未対応なら英語）
- **言語追加**: `locales/<code>.py` に `STRINGS` をコピーして翻訳 → `i18n.BUILTIN_LOCALES`（と必要なら `_LOCALE_ALIASES`）へ追記

## 制限・方針

- 特定チャンネルのみ監視するホワイトリストなし
- ギルドにつき Bot は同時に 1 VC のみ。**人がいる VC を監視中は他 VC へ移動しない**（入退室音を抑える）。例外として `PRIORITY_VOICE_CHANNEL_ID`（カンマ区切り・左が最優先）に人がいるときは、その中で最優先のチャンネルへ移動する。監視中の VC が空になったら退出し、別 VC に人がいればそちらへ入る（優先リストがあれば優先）
- 起動時は優先リスト（人がいる最左）→ それ以外で最初に見つかった人がいる VC、の順

## ライセンス

用途に合わせて各自で設定してください。
