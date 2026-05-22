# 対応 Verilog サブセット

HDL-Sim がパース・シミュレーションできる文法の一覧です。未記載は基本的に未対応です。

## モジュール・階層

| 機能 | 状態 | 備考 |
|------|------|------|
| `module` / `endmodule` | 対応 | 複数モジュール、複数ファイル |
| ポート `input` / `output` / `inout` | 対応 | inout は簡易モデル |
| `parameter` / `localparam` | 対応 | インスタンス `#(.P(v))` |
| モジュールインスタンス | 対応 | 名前付きポート `.p(sig)` |
| `--top` | 対応 | エントリモジュール指定 |
| `-D` / `-I` | 対応 | パラメータ上書き・インクルードパス |
| ANSI ポート宣言 | 未対応 | `input wire clk` など |

## 宣言・型

| 機能 | 状態 |
|------|------|
| `reg` / `wire` / `integer` | 対応 |
| ビット・パート選択 `[msb:lsb]` | 対応 |
| `genvar` + `generate` | 対応 |

## プロセス

| 機能 | 状態 |
|------|------|
| `initial` | 対応 |
| `always` 組合せ `@(*)` 相当 | 対応 |
| `always @(posedge/negedge sig)` | 対応 |
| `#delay` + 文 | 対応（`#N;` 単体は不可） |
| `forever` | 対応 |
| `fork` / `join` | 対応（`begin` 内の並列文） |
| `repeat` / `while` / `for` | 対応 |
| `if` / `case` / `casex` / `casez` | 対応 |

## 代入・四値

| 機能 | 状態 |
|------|------|
| ブロッキング `=` | 対応（四値） |
| 非ブロッキング `<=` + NBA | 対応（四値、階層ポート名解決） |
| `assign` 連続代入 | 対応（四値） |
| リテラル `1'bx` / `2'bz1` 等 | 対応 |
| `casex` / `casez` | 対応 |

## タスク・関数

| 機能 | 状態 |
|------|------|
| `task` / `endtask`（入出力ポート） | 対応 |
| `function` / `endfunction` | 対応 |

## システムタスク

| タスク | 状態 |
|--------|------|
| `$display` / `$finish` / `$stop` | 対応 |
| `$monitor` | 対応 |
| `$dumpfile` / `$dumpvars` | 対応（レベル・スコープ・個別信号） |

## 式・演算

算術・論理・比較・連結、単項 `~` `&`、三項は未対応（`?:` が文法にあれば要確認）。識別子・定数・ビット選択を中心に利用。

## 例とテスト

| 例 | 内容 |
|----|------|
| `examples/silos_regression.v` | クロック・リセット・posedge NBA・階層 DUT・PASS/FAIL 表示 |
| `examples/hierarchy.v` | 階層インスタンス |
| `examples/param_counter.v` | パラメータ付きカウンタ |
| `examples/tb_multi.v` + `lib/and2.v` | 複数ファイル |

回帰: `tests/test_silos_regression.py`（53 件中の Silos 向け 6 件）

## デバッグ

- VCD 出力（`-o path.vcd` または `$dumpfile`）
- `--verbose` / `--trace`（CLI）
- `pytest` 全体（現状 53 passed）
