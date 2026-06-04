# ローカルデバッグ引き継ぎ（Cursor / エディタ AI 用）

正式リリースで「みんなが同じ HDL-Sim を使う」ための整理と、**手元の `.v` を Cursor で直すときに貼るプロンプト**です。

---

## 正式リリース vs ローカル — どっちが「良い」か

| 目的 | 向いている場所 |
|------|----------------|
| パーサ・シミュレータ・UI の **共通バグ修正**を全員に届ける | **リポジトリ（PR / Release）** ← 今回 Cloud で積んだ修正 |
| **自分の課題 RTL** が Elab/Run まで通るか確認・微調整 | **ローカル + エディタ AI** |
| 正式リリース時に ZIP/exe を配る | **Release ブランチに修正が入っていること**が必須。ローカルだけ直しても他の人には届かない |

**結論:** 「みんなで使える形」＝ **本体は GitHub Release**。ローカル AI は **その Release を使いながら、各自の 6 ファイルを通す**のに向いています。どちらか一方ではなく **Release（共通）＋ ローカル（個別 RTL）** です。

推奨フロー:

1. `cursor/dev-ui-9db8`（または main にマージ後の Release）を pull / 新 ZIP で入手
2. ローカル Cursor で **自分の正しい `.v` 一式**を開き、Elab → Run
3. まだ **ツール側**で落ちる → エラー全文を issue / Cloud に渡す（下のプロンプト）
4. **RTL 側**の typo・top 取り違え → ローカルで修正

---

## 環境の前提（2026-06 時点）

- ブランチ例: `cursor/dev-ui-9db8`（base: `cursor/hdl-sim-ui-8fe6`）
- バージョン: **0.5.18 以降** を想定（それ以前は `wait` / ANSI ポート / 波形 / top 自動解決が未入りの可能性）
- UI: Monaco の **verilog** は色付けのみ。本当の判定は **Elab / Run の Lark パーサ**
- 取得: `git pull origin cursor/dev-ui-9db8` または Release ZIP 再ビルド

### 直近で入った主な修正（再現しなくなったはずのもの）

| 症状 | 対応 |
|------|------|
| `unknown identifier: s0`（vend FSM） | モジュール parameter を function に伝播 |
| `unsupported statement: list` on `@(negedge clk)` | event_control パース・1 回待ち |
| `input wire clk` パースエラー | ANSI ポート |
| `KeyError: 'wait'` | `wait(expr)` 文 |
| `WAIT` in case / `wait_cnt` 分割 | `wait` は `(` 前だけキーワード |
| Run 成功だが波形が全部ない | VCD は全信号を出力（`$dumpvars` 範囲外も記録） |
| `unknown module: tb` | top 自動解決（`*_tp` / `*_tb` 優先） |

### まだ当たりやすい未対応

- ポート接続の **ビット選択・連結**（`.d(seg[3:0])` など）
- `assign {a,b} = fsm(...)` の **連結左辺**
- Silos PLI / 混合信号 / gate primitive ライブラリ
- 手続きキーワードの追加（`disable` 等を task と誤認する可能性）

---

## ローカル確認チェックリスト

- [ ] HDL-Sim のバージョンが **0.5.18+**（Help → About または左上バッジ）
- [ ] 6 ファイルすべてワークスペースに入っている（`include_only` は TB から `` `include `` される側）
- [ ] ツールバー **Top** が実在モジュール（例: `reflex_game_tp`）。古い `tb` のままなら Elab 前に変更 or 自動修正メッセージを確認
- [ ] **Elab** 成功後に **Run**（波形は Run 後の VCD）
- [ ] 波形: コンソールに `[wave] N signals captured`。Hierarchy クリックで追加

---

## コピペ用：Cursor ローカル引き継プロンプト

以下を **新しい Cursor チャットの最初のメッセージ**として貼り、続けて自分の状況を足してください。

```markdown
# HDL-Sim ローカルデバッグ（引き継ぎ）

あなたは HDL-Sim（Python + FastAPI + Monaco UI）のデバッグ担当です。
リポジトリ: PeRoHi/HDL-Sim、作業ブランチは `cursor/dev-ui-9db8`（なければ main / 最新 Release）。

## 役割の切り分け
- **ツール側バグ**（パーサ・elab・sim・VCD・UI）→ リポジトリを直し、テストを足し、バージョンを上げる
- **ユーザー RTL**（top 名・ファイル不足・文法ミス）→ 最小限の修正案を提示。シミュレータを無理に拡張しない

## 読むべきドキュメント（リポジトリ内）
- docs/LOCAL_DEBUG_HANDOFF.md（本ファイル）
- docs/SUPPORTED_SUBSET.md
- docs/LEGACY_EXAMPLES.md

## 既知の修正（0.5.18 以降）
ANSI `input wire`、wait(expr)、case の `wait:` / 識別子 `wait_cnt`、module parameter in function、
event_control `@(negedge)`、VCD 全信号出力、top 自動解決（tb が無いとき *_tp 優先）。

## デバッグ手順（必ず実行）
1. ユーザーが挙げた **エラー全文**と **ファイル一覧・top 名**を確認
2. 該当 `.v` を読む（ワークスペースに無ければユーザーにパスを聞く）
3. `PYTHONPATH=src python3 -m pytest tests/ -q` で関連テスト（無ければ最小 reproduction を追加）
4. 修正は最小 diff。UI 色付けではなく `src/hdl_sim/parser/` と `engine/` を直す
5. 再現手順を短くメモ

## 報告フォーマット（ユーザー向け）
- 原因（1〜2 文）
- 対処（pull バージョン / top 変更 / RTL 修正 / 待ちの未対応）
- 次に試す操作（Elab → Run、Until 推奨値など）

## 私のプロジェクト情報（以下を埋めてから送信）
- HDL-Sim バージョン: （About の表示）
- 取得方法: git pull / ZIP exe
- ファイル一覧:
- Top モジュール（UI の選択）:
- 操作: Elab / Run
- エラー全文（ログ貼り付け）:
- 期待する動作:
```

---

## プロジェクト別メモ（例）

### reaction timer（旧 tb_reaction_timer）

- ファイル: `lfsr_8bit.v`, `main_controller.v`, `reaction_timer_top.v`, `seg7_decoder.v`, `tb_reaction_timer.v`, `timer_bcd.v`
- Top: **`tb_reaction_timer`**

### reflex game（新・正しい一式）

- ファイル: `lfsr8.v`, `main_controller.v`, `reflex_game_tp.v`, `reflex_game.v`, `seg7_decoder.v`, `timer16.v`
- Top: **`reflex_game_tp`**（`tb` ではない）

---

## Cloud Agent に任せるべきこと

- 複数人で使う **本体コード変更**と PR
- 回帰テスト・バージョン bump・`docs/` 更新
- 再現用の最小 `.v` をリポジトリ `tests/` に追加

## ローカル AI に任せるべきこと

- 手元 6 ファイルの **top / ファイル名 / パス**の確認
- Run ログ・波形操作の手順
- RTL が SUPPORTED_SUBSET 外かどうかの切り分け

---

## 関連

- [UI_QUICKSTART.md](UI_QUICKSTART.md) — 起動・ZIP
- [SUPPORTED_SUBSET.md](SUPPORTED_SUBSET.md) — 対応 Verilog
- [LEGACY_EXAMPLES.md](LEGACY_EXAMPLES.md) — Silos 例の可否
