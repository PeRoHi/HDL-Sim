# HDL-Sim

Silos の代替を目指す、軽量なイベント駆動型 Verilog HDL シミュレータ（Python / Poetry）。

## できること

- 離散イベントシミュレーション（`#delay`、NBA リージョン、デルタサイクル）
- モジュール階層・パラメータ・複数ファイル・`--top` / `-D` / `-I`
- `initial` / `always`（組合せ・`posedge` / `negedge`）、`fork` / `join`、`task` / `function`
- `generate for` / `if`、inout ポート、階層 VCD（`$dumpfile` / `$dumpvars`）
- 四値リテラル、`casex` / `casez`、連続代入・非ブロッキング代入への X/Z 伝播

詳細な文法一覧は [docs/SUPPORTED_SUBSET.md](docs/SUPPORTED_SUBSET.md) を参照してください。

## セットアップ

```bash
poetry install
```

Lark のみ手動で入れる場合:

```bash
pip install lark==1.2.2 pytest
```

## 実行例

```bash
# 単一ファイル
poetry run hdl-sim examples/clock.v --until 20 -o build/clock.vcd

# 階層 + トップ指定（Silos 回帰例）
PYTHONPATH=src python3 -m hdl_sim examples/silos_regression.v \
  --top silos_regression_tb --until 50 --max-events 500
```

## テスト

```bash
poetry run pytest -q
# または
PYTHONPATH=src python3 -m pytest -q
```

Silos 代替の信頼感向け統合テスト:

```bash
PYTHONPATH=src python3 -m pytest tests/test_silos_regression.py -v
```

## ドキュメント

- [docs/architecture.md](docs/architecture.md) — パイプラインと主要コンポーネント
- [docs/SUPPORTED_SUBSET.md](docs/SUPPORTED_SUBSET.md) — 対応文法・制約

## 既知の制約（抜粋）

- ANSI ポート（`input wire clk`）は未対応 → `input clk` 形式を使用
- `#N;` の単体 delay は不可。`#N <文>` が必要（例: `#12 rst = 0;`）
- UI / 波形ビューアは未実装（VCD + GTKWave 等を利用）

## ロードマップ

- UI は最後。現状は VCD・`--verbose` / `--trace`・pytest で検証
