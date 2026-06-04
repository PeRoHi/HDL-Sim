# Windows コード署名（スマート アプリ コントロール対策）

## こちらでできること / できないこと

| できる | できない |
|--------|----------|
| ビルド時に `signtool` で署名するスクリプト | 信頼される **コードサイニング証明書の購入・発行** |
| Inno Setup で Setup / `unins000.exe` に署名 | あなたの PC 上の **秘密鍵・PFX の保管** |
| 環境変数があれば `build_*.bat` から自動署名 | 署名なしで SAC を「信頼済み」にする |

**根本対策 = Authenticode 署名**です。証明書は **配布者（PeRoHi / 組織）** が CA から取得する必要があります。

## 証明書の例

- 商用 OV / EV コードサイニング証明書（DigiCert, Sectigo など）
- [Azure Trusted Signing](https://learn.microsoft.com/azure/trusted-signing/)（クラウド署名）
- 自己署名証明書 → **SAC 対策にはならない**（テスト用のみ）

## ビルド前の準備

1. Windows SDK を入れ、`signtool.exe` が使えること
2. 証明書を次のいずれかで用意:
   - **PFX ファイル** + パスワード
   - 証明書ストアにインポートし **サムプリント（SHA1）** を控える

## 環境変数

| 変数 | 説明 |
|------|------|
| `HDL_SIM_SIGN_PFX` | `.pfx` のフルパス |
| `HDL_SIM_SIGN_PASSWORD` | PFX パスワード（省略時は対話なしで失敗する場合あり） |
| `HDL_SIM_SIGN_THUMBPRINT` | ストア内証明書の SHA1（PFX の代わりに指定可） |
| `HDL_SIM_TIMESTAMP_URL` | 省略時 `http://timestamp.digicert.com` |

PowerShell（ビルド PC で一度設定）:

```powershell
$env:HDL_SIM_SIGN_PFX = "C:\certs\hdl-sim-codesign.pfx"
$env:HDL_SIM_SIGN_PASSWORD = "********"
```

## ビルド手順（署名あり）

```bat
set HDL_SIM_SIGN_PFX=C:\certs\your-codesign.pfx
set HDL_SIM_SIGN_PASSWORD=your-password

packaging\build_windows.bat
packaging\build_installer.bat
```

- `HDL-Sim.exe` … PyInstaller 直後に署名
- `HDL-Sim-Setup-x.x.x.exe` … Inno コンパイル時に署名
- `unins000.exe` … `SignedUninstaller=yes` でインストール時に署名付き削除プログラムを展開

## 署名の確認

```bat
signtool verify /pa dist\HDL-Sim-Setup-0.5.5.exe
```

エクスプローラーで exe の **デジタル署名** タブに発行元名が出れば OK です。

## CI（任意）

GitHub Actions などでは PFX を **Secrets** に入れ、ビルドジョブ内で上記環境変数を設定してから `build_installer.bat` を実行します。証明書をリポジトリにコミットしないでください。
