HDL-Sim インストール後の起動について
================================

Setup (HDL-Sim-Setup-x.x.x.exe) を実行すれば、インストールとショートカット作成まで完了します。
起動時は次のフォルダ一式が必要です（exe 単体だけでは動きません）。

  インストール先\
    HDL-Sim.exe
    _internal\   ← Python ランタイムとライブラリ

WebView2 について
-----------------
Setup では「Microsoft WebView2 ランタイムをインストール」にチェックを入れると、
未導入 PC では HDL-Sim と同時に WebView2 が入ります（専用ウィンドウに必要）。
既に Edge / WebView2 がある PC ではスキップされます。

起動に失敗した場合
------------------
1. インストール先の hdl-sim-crash.log を確認
2. 同じ場所の hdl-sim-server-error.log があればそれも確認
3. WebView2 を手動インストール: https://go.microsoft.com/fwlink/p/?LinkId=2124703
4. Visual C++ 再頒布可能パッケージ (x64) をインストール
5. ウイルス対策ソフトが HDL-Sim.exe / _internal をブロックしていないか確認

旧版からの更新
--------------
以前の 0.5.1 などを入れている場合は、一度アンインストールしてから
新しい Setup で入れ直してください。
