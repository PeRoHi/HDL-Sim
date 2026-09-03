#!/bin/bash
cd "$(dirname "$0")/.."

echo "[HDL-Sim] Mac版をビルドします..."

# 依存ライブラリのインストール
python3 -m pip install pyinstaller pywebview fastapi uvicorn lark

# 古いビルドの削除
rm -rf dist/HDL-Sim build/hdl_sim_ui

# PyInstallerの実行
python3 -m PyInstaller packaging/hdl_sim_ui.spec --noconfirm
if [ $? -ne 0 ]; then
    echo "PyInstallerによるビルドに失敗しました。"
    exit 1
fi

echo ""
echo "完成: dist/HDL-Sim"
echo "Mac環境では、dist/HDL-Sim/ フォルダ内に実行可能ファイルが生成されます。"
echo "続いて packaging/build_mac_zip.sh を実行してZIPを作成してください。"
