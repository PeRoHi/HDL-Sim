# filter 課題の動作確認チェックリスト

リポジトリ内に課題 RTL が無い場合でも、**ローカルで Run まで通った**ことを再確認するための手順です。

## リポジトリ側で確認済み（CI 相当）

`cursor/dev-ui-9db8` / **0.5.19 以降** で以下を pytest 確認:

- `signed` / `>>>` / `$signed` / `$unsigned`
- `reg [7:0] mem [0:N]` と `mem[i]` / `mem[i][j]`
- Top 自動解決（`*_tp` 優先、存在しない `tb` は無視）
- VCD 全信号出力（波形用）
- `wait(expr)` / ANSI `input wire`

```bash
cd HDL-Sim
git pull origin cursor/dev-ui-9db8
PYTHONPATH=src python3 -m pytest tests/test_signed_ashr_memory.py tests/test_resolve_top.py -q
```

## ローカル IDE での再確認（あなたの filter 6 ファイル）

1. **バージョン** … Help → About で **0.5.19+**（古い exe は不可）
2. **Top** … `*_tp` / 課題指定の TB 名（`(auto — *_tp 優先)` でも可）
3. **Elab** … エラー無し、`top=...` が表示される
4. **Run** … `[OK] time=...` と `[wave] N signals captured`
5. **波形** … Signals タブまたは Hierarchy クリック → Wave

## よく使う RTL（filter で落ちやすい点）

| 構文 | 0.5.19 付近 |
|------|-------------|
| `reg signed [...]` / `>>>` | 対応 |
| `mem[i]`, `mem[i][bit]` | 対応 |
| `input wire` ポート | 対応 |
| `wait(sig)` | 対応 |
| ポート `.d(x[3:0])` | **未対応**のことが多い |
| `assign {a,b}=...` | **未対応** |

## 共有してもらえると Cloud でも再現できる情報

- `.v` ファイル名一覧と **Top モジュール名**
- Elab/Run の **コンソール全文**（エラー時）
- 通ったときの `time=` / `events=`

SPJ 化する場合は `spj/*.spj` 形式（`docs/UI_QUICKSTART.md`）で `top` を正しい TB 名に設定してください。
