# HDL-Sim

Silos の代替を目指す、軽量なイベント駆動型 Verilog HDL シミュレータ（Python / Poetry）。

## 機能（現状）

- Verilog サブセットのパース（Lark）
- イベントキューによる離散イベントシミュレーション
- 連続代入・`initial` / `always`・`#delay`・`forever`
- VCD 出力（GTKWave 等で波形確認）

## セットアップ

```bash
poetry install
poetry add lark==1.2.2
```

## 実行例

```bash
poetry run hdl-sim examples/clock.v --until 20 --max-events 100 -o build/clock.vcd
```

## テスト

```bash
poetry run pytest
```

## ドキュメント

- [docs/architecture.md](docs/architecture.md)


## Recent capabilities

- Verilog `task` / `endtask` with input/output ports
- Four-state `casex` / `casez` matching (x/z in sized literals)
- `$dumpvars(level, scope)` selective waveform dump
- `$monitor` system task
