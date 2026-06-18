#!/bin/bash
cd "$(dirname "$0")/.."

if [ ! -d "dist/HDL-Sim" ]; then
    echo "dist/HDL-Sim が見つかりません。先に packaging/build_mac.sh を実行してください。"
    exit 1
fi

# バージョンの取得
VER=$(python3 -c "import sys; sys.path.insert(0,'src'); from hdl_sim import __version__; print(__version__)")
ZIP="dist/HDL-Sim-${VER}-mac.zip"

# ユーザー要望のフォルダとファイルの整理
mkdir -p "dist/HDL-Sim/verilog_sources"
mkdir -p "dist/HDL-Sim/spj"

cp spj/api_demo.spj dist/HDL-Sim/spj/ 2>/dev/null || true
cp spj/silos_code_coverage.spj dist/HDL-Sim/spj/ 2>/dev/null || true
cp spj/silos_code_coverage2.spj dist/HDL-Sim/spj/ 2>/dev/null || true
cp spj/silos_gate.spj dist/HDL-Sim/spj/ 2>/dev/null || true
cp spj/silos_vending.spj dist/HDL-Sim/spj/ 2>/dev/null || true
cp spj/test4add.spj dist/HDL-Sim/spj/ 2>/dev/null || true
cp spj/testcounter.spj dist/HDL-Sim/spj/ 2>/dev/null || true
cp spj/testDFF.spj dist/HDL-Sim/spj/ 2>/dev/null || true

EX_DIR="dist/HDL-Sim/_internal/examples"
if [ ! -d "$EX_DIR" ]; then
    EX_DIR="dist/HDL-Sim/examples"
fi
rm -rf "$EX_DIR"
mkdir -p "$EX_DIR"

cp examples/and_gate.v "$EX_DIR"/ 2>/dev/null || true
cp examples/counter.v "$EX_DIR"/ 2>/dev/null || true
cp examples/tb_multi.v "$EX_DIR"/ 2>/dev/null || true
cp examples/hierarchy.v "$EX_DIR"/ 2>/dev/null || true

rm -f "$ZIP"

echo "[HDL-Sim] ZIP を作成しています: $ZIP"
cd dist/HDL-Sim || exit 1
zip -r "../../$ZIP" ./*
cd ../..

echo ""
echo "完成: $ZIP"
echo "Macユーザーは ZIP を解凍し、中の HDL-Sim 実行ファイル（または .app）を起動します。"
