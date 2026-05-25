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

## Python なしで配布する場合

Windows PC で一度だけ `packaging/build_windows.bat` を実行すると `dist/HDL-Sim.exe` ができます。
この exe を配るだけで、受け取った人は Python もターミナルも不要です。

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
