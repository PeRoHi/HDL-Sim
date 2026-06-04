# HDL-Sim UI かんたん起動

## Windows（おすすめ・ターミナル不要）

1. **Python 3.12** を [python.org](https://www.python.org/downloads/) からインストール
   - インストール時に **Add python.exe to PATH** にチェック
2. 次のどれかをダブルクリック
   - **`start-ui.vbs`** … 黒い画面を出さずに起動（いちばん簡単）
   - **`start_ui_gui.pyw`** … 小さな起動ウィンドウが開く
   - **`start-ui.bat`** … うまくいかないときの代替

初回だけ GUI の **「依存関係をインストール」** ボタンを押してください。
ターミナルは不要です。

## Python なしで配布する場合（ZIP 推奨）

Windows PC で一度だけ:

```bat
packaging\build_windows.bat
packaging\build_zip.bat
```

- 実行物: `dist\HDL-Sim\` フォルダ一式（`HDL-Sim.exe` + `_internal\`）
- 配布物: `dist\HDL-Sim-x.x.x-windows-x64.zip`（解凍して `HDL-Sim.exe` を起動）
- **exe は Chrome ではなく専用ウィンドウで IDE が開きます**（WebView2 未導入時は [ランタイム](https://go.microsoft.com/fwlink/p/?LinkId=2124703)）

### バージョン更新の通知（利用者）

起動して IDE を開くと、GitHub の **最新 Release**（`PeRoHi/HDL-Sim`）と同梱 exe のバージョンを比較します。新しい版があれば画面上部にバナーが出ます（**自動ダウンロード・自動更新はしません**）。ZIP を取得してフォルダごと入れ替えてください。

### バージョンの確認（`HDL-Sim.exe`）

1. **起動ウィンドウ** … 起動直後の小さな GUI に `Ver x.x.x` と表示
2. **IDE** … 左上メニューバーの `Ver x.x.x` バッジ（サーバー `/api/version` と同期）
3. **Help → About** … ダイアログでバージョン表示

### 課題 RTL をローカルでデバッグするとき

Cursor などエディタ AI に渡す引き継ぎ文は [LOCAL_DEBUG_HANDOFF.md](LOCAL_DEBUG_HANDOFF.md)（コピペ用プロンプト付き）を参照してください。正式リリース用の修正は GitHub の Release / PR、手元の 6 ファイル確認はローカル、の役割分担を書いてあります。

### リリース時のバージョン上げ（開発者）

1. `src/hdl_sim/__init__.py` の `__version__` を更新（ここが exe の正）
2. 同じ番号を `pyproject.toml`・`src/hdl_sim/web/app.py` の `UI_BUILD`・`ui/index.html` の `?v=` とバッジに反映
3. `packaging\build_windows.bat` → `packaging\build_zip.bat`
4. GitHub Release に `HDL-Sim-x.x.x-windows-x64.zip` を添付し、タグ `vx.x.x` を付ける

### インストーラー版（当面は使用停止）

Inno Setup 版（`build_installer.bat`）はスクリプトは残していますが、**フリー配布の主経路は ZIP** です。署名・スマート アプリ コントロールの都合で再開する場合は `packaging/SIGNING.md` を参照。

## macOS / Linux

`start-ui.command` または `./start-ui.sh` をダブルクリック

## 使い方

1. ブラウザが自動で開く
2. 中央のエディタで Verilog を編集
3. **▶ 実行**（F5）
4. 左: 階層 / 右: 波形 / 下: コンソール

## 終了

起動ウィンドウの **終了** を押す（VBS 起動の場合はウィンドウを閉じる）

## うまくいかないとき

| 症状 | 対処 |
|------|------|
| 一瞬黒画面が出て消える | `start-ui.vbs` または `start_ui_gui.pyw` を使う |
| Python がない | python.org 版 3.12 をインストール |
| 依存関係エラー | GUI の「依存関係をインストール」を押す |
