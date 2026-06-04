# HDL-Sim プロジェクト (`.spj`)

このフォルダに **HDL-Sim 形式** のプロジェクト JSON を置きます。IDE の **SPJ** ドロップダウンと **Open .spj** はここを参照します（開発時はリポジトリ直下の `spj/`、配布 exe ではインストール先の `spj/`）。

## 形式

```json
{
  "format": "hdl-sim-project",
  "version": 1,
  "name": "saikoro",
  "top": "sai_test",
  "label": "説明（任意）",
  "files": [
    { "path": "sai.v", "content": "..." }
  ]
}
```

Silos 由来の INI 形式 `.spj` は **ここには置かない** です。例の Verilog は `examples/examples/` に残し、プロジェクト定義だけをこのフォルダに集約しています。

## 一覧（Silos 例から変換）

| ファイル | Top | 内容 |
|----------|-----|------|
| `saikoro.spj` | `sai_test` | sai.v + saitest.v |
| `test4add.spj` | `mul_ts` | 4add + testbench |
| `testcounter.spj` | `counter_reset_tp` | カウンタ + TB |
| `testDFF.spj` | `DFF_tp` | DFF + TB |
| `testTFF.spj` | `TFF_tp` | TFF + TB |
| `watch.spj` | `DFF_tp` | watch + TB |
| `silos_code_coverage.spj` | `testbench` | カバレッジ例 1 |
| `silos_code_coverage2.spj` | `testbench` | カバレッジ例 2 |
| `silos_vending.spj` | `stimulus` | vending_testbench + `include` vending.v |
| `silos_gate.spj` | `stimulus` | vendtest + vend.v（HDL-Sim 向けに assign 分割） |
| `api_demo.spj` | `tb` | API 用ミニ例 |

**Silos 専用で HDL-Sim 未対応**（`.spj` には含めていません）: `faulttst.v`（`$fs_strobe`）、`analog.v`（`!con` / 混合信号）など。ソースは `examples/examples/新しいフォルダー/` に残っています。

再生成: `python3 scripts/seed_spj_from_examples.py`

## 例フォルダとの関係

- **`.v` ソース**: `examples/examples/`（ツールバー「例」や手動 Open）
- **`.spj` プロジェクト**: この `spj/`（複数ファイル + top をまとめて開く）
