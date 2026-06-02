HDL-Sim インストール後の起動について
================================

Setup (HDL-Sim-Setup-x.x.x.exe) を実行すれば、インストールとショートカット作成まで完了します。
起動時は次のフォルダ一式が必要です（exe 単体だけでは動きません）。

  インストール先\
    HDL-Sim.exe
    _internal\   ← Python ランタイムとライブラリ

起動に失敗した場合
------------------
1. インストール先の hdl-sim-crash.log を確認
2. 同じ場所の hdl-sim-server-error.log があればそれも確認
3. Microsoft WebView2 ランタイムをインストール
   https://go.microsoft.com/fwlink/p/?LinkId=2124703
4. Visual C++ 再頒布可能パッケージ (x64) をインストール
5. ウイルス対策ソフトが HDL-Sim.exe / _internal をブロックしていないか確認

旧版からの更新
--------------
以前の 0.5.1 などを入れている場合は、一度アンインストールしてから
新しい Setup で入れ直してください。
