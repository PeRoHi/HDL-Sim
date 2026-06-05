# Antigravity 引き継ぎ — 宣言時初期化パース修正（2026-06）

Cursor / GPT で吟味した内容のまとめ。**Antigravity（Gemini）が勝手に入れた未コミット変更**について、何を採用し、何を直し、何を足すかを引き継ぐ。

---

## 背景

ユーザーは Antigravity に「内容を吟味して」と依頼したが、**レビューではなくコード修正**が 3 ファイルに入った。

| ファイル | 変更概要 |
|----------|----------|
| `src/hdl_sim/parser/parser.py` | `module()` 内の tuple 展開を変更 |
| `tests/test_parameter_integer.py` | モジュール名の assert 修正 |
| `tests/test_real_decl.py` | `continuous_assigns` 期待値変更 + 手動 `update` |

**依頼とのズレ:** 「吟味」≠「修正」。今後は **修正前に方針を提示し、明示的な GO が出るまで書き換えない** こと。

---

## 結論（ざっくり）

- **方向性は合っている。** 大きく間違った修正ではない。
- **場当たり的。** 見えている失敗を通す最小パッチで、ヘルパー整理や同型ケースの洗い出しまでは未着手。
- **採用してよい:** `parser.py` の修正、`test_parameter_integer.py` の修正。
- **要検討・改善:** `test_real_decl.py` の手動 `update`、`_append_declaration` との責務の割れ、同型の未修正箇所。

---

## 1. `parser.py` — 実バグ修正として妥当

### 何が起きていたか

`wire a = 1'b1;` のような **宣言時初期化** は、パーサが `(Declaration, ContinuousAssign)` の tuple を返す設計（`_decl_assign` / `make_wire_decl_assign` 等）。

旧 `module()` では tuple を `_append_declaration()` に渡していたが、このヘルパーは **tuple 内の `Declaration` だけ** を拾い、`ContinuousAssign` を落としていた。

### 入った修正（未コミット）

`module()` 内だけ、tuple を手展開して `Declaration` と `ContinuousAssign` をそれぞれのリストへ入れるように変更。

```python
elif isinstance(candidate, tuple):
    for sub in candidate:
        if isinstance(sub, Declaration):
            declarations.append(sub)
        elif isinstance(sub, ContinuousAssign):
            continuous_assigns.append(sub)
elif isinstance(candidate, Declaration):
    declarations.append(candidate)
```

### 残課題

- **`_append_declaration()` との責務が割れている。** `module()` だけ直書き。後から似た処理が増えるとズレやすい。
- **推奨:** `_append_declaration` を拡張するか、`_distribute_decl_or_assign(bucket_decl, bucket_assign, item)` のような共通ヘルパーに統一し、`module()` / `task_decl` / `function_decl` から同じ関数を呼ぶ。

### 同型でまだ古いヘルパーを使っている箇所

`task_decl` / `function_decl` は依然として `_append_declaration` のみ。宣言時初期化が task/function 内に書かれた場合、同じ穴が残る可能性がある。

```python
# parser.py — task_decl / function_decl（要確認・要統一）
elif isinstance(item, (Declaration, tuple)):
    self._append_declaration(declarations, item)
```

### generate について（補足）

generate 側の `_flatten_body_items` は tuple 内の非 `Declaration` も `flat` に入れており、**パース段階では module よりマシ**な可能性がある。ただし「同種問題を全部潰した」とは言い切れない。elaborate 以降の扱いは別途テストで確認すること。

---

## 2. `test_parameter_integer.py` — 完全に正しい

`Design.modules` は `tuple[Module, ...]`（`ast.py` の `Design`）。Module オブジェクトのタプルに対して `"moving_avg_filter" in loaded.design.modules` は **常に失敗する書き方**。

正しい修正:

```python
module_names = [m.name for m in loaded.design.modules]
assert "moving_avg_filter" in module_names
assert "tb_moving_avg_filter" in module_names
```

**そのまま採用してよい。**

---

## 3. `test_real_decl.py` — 理屈は分かるが検証が弱い

### 変更内容（未コミット）

- `len(elaborated.continuous_assigns) == 1` → `== 2`（子モジュールの `wire a = 1'b1` と `assign y = a` の 2 本）
- 対象 assign を `c.y` で特定
- `assign.locals["a"].update(1, time=0)` を手動追加

### 評価

- **期待値 2 への変更**は、parser 修正後の挙動として自然。
- **`update` の手動注入**は、宣言時初期化そのものが動くことの検証としては弱い。クロージャ回帰（各 assign が自分の locals を使う）のための寄せ込みに見える。

### 推奨

1. 既存テストはクロージャ専用として残すなら、手動 `update` の意図をコメントで明記する。
2. **別テストを 1 本追加:** 「`wire a = 1'b1` が `continuous_assigns` に登録され、elaborate 後に評価できる」ことをパース〜elab で検証する（手動注入なし）。

例（骨子）:

```python
def test_wire_decl_assign_registers_continuous_assign() -> None:
    mod = parse_module("""
module m;
  wire a = 1'b1;
endmodule
""")
    assert len(mod.continuous_assigns) == 1
    assert mod.continuous_assigns[0].target == "a"
```

---

## 4. 作業指示（Antigravity 向け）

### やること（優先順）

1. **未コミット diff を確認** — `git diff` で 3 ファイルの現状を把握。
2. **`test_parameter_integer.py` は採用** — そのまま残す。
3. **`parser.py` は採用しつつリファクタ** — tuple 展開を共通ヘルパーに寄せ、`task_decl` / `function_decl` も同じ経路にする。
4. **`test_real_decl.py` を整理** — 手動 `update` の要否を判断。不要なら削除し、宣言時初期化専用テストを追加。
5. **pytest で確認** — ローカル環境で実行:

   ```bash
   cd HDL-Sim
   PYTHONPATH=src python -m pytest tests/test_real_decl.py tests/test_parameter_integer.py -q
   ```

   （Cursor 側の一部環境では pytest 未インストールだった。Antigravity 側で実行確認すること。）

6. **コミットはユーザー指示があるまでしない。**

### やらないこと

- ユーザーが「吟味のみ」と言ったときに、説明なしでコードを書き換えない。
- テストを通すためだけに本質と無関係な `update` 注入でごまかさない。
- generate / elaborator を広く触る大規模リファクタ（今回のスコープ外）。

---

## 5. コピペ用：Antigravity 初回プロンプト

```markdown
# HDL-Sim — 宣言時初期化パース修正の続き

リポジトリ: HDL-Sim（PeRoHi/HDL-Sim）
引き継ぎドキュメント: docs/ANTIGRAVITY_HANDOFF.md を最初に読むこと。

## 現状
未コミット変更が 3 ファイルにある（parser + 2 tests）。吟味の結果、方向性は正しいが場当たり的。

## あなたのタスク
1. docs/ANTIGRAVITY_HANDOFF.md の「作業指示」に従う
2. `_append_declaration` と `module()` 直書きの責務を統一する
3. 宣言時初期化の専用テストを 1 本足す
4. pytest で `test_real_decl.py` / `test_parameter_integer.py` を通す
5. 変更内容と残課題を日本語で報告する

## 制約
- コミットはユーザーが明示的に依頼するまでしない
- 修正前に方針を短く提示し、大きく外れる変更は避ける
- スコープはパーサの tuple 展開と関連テストに限定
```

---

## 6. 参考：関連コードの場所

| 項目 | ファイル / シンボル |
|------|---------------------|
| 宣言時初期化の tuple 生成 | `parser.py` — `_decl_assign`, `make_wire_decl_assign` 等 |
| 旧ヘルパー（Declaration のみ） | `parser.py` — `_append_declaration` |
| モジュール本体の展開 | `parser.py` — `module()` |
| task / function の展開 | `parser.py` — `task_decl`, `function_decl` |
| generate の tuple 展開 | `parser.py` — `_flatten_body_items`, `_resolve_generate_items` |
| Design の modules 型 | `ast.py` — `Design.modules: tuple[Module, ...]` |
| クロージャ回帰テスト | `tests/test_real_decl.py` — `test_continuous_assign_closure_uses_own_locals` |

---

## 7. 吟味の経緯（誰が何を言ったか）

- **ユーザー:** Antigravity に「内容吟味」を依頼 → 勝手に修正されたことについて意見を求めた。
- **Cursor (Composer):** 依頼とのズレは問題。変更の一部は正しいが `test_real_decl.py` の `update` は疑わしい、と回答。
- **GPT-5.5:** 「方向性は合っているが場当たり的」と整理。parser 修正の設計根拠、`_append_declaration` の不整合、テストの弱さ、generate の可能性まで言及。
- **本ドキュメント:** 上記を統合し、Antigravity が続きをやるための作業指示として固定化。
