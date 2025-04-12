# Toy Meter for YAESU FTDX10 / FT710 / FT891 / FT991

> ⚠️ **注意：本アプリケーションは現在評価中です。**

YAESU無線機向けの簡易メーターアプリケーションです。以下のプラットフォームに対応しています：

- **Raspberry Pi OS Lite (64bit)** + 3.5inch LCD (480x320)
- **macOS 12 Monterey 以降**
- **Windows 11**

## 🎛️ 対応機能

### アナログメーター部
- `SIG`（Signal メーター）
- `PO`（Power メーター）
- `SWR`（SWR メーター）
- `ALC`（ALC メーター）

### デジタルメーター部
- `FA/FB`（周波数）
- `TIME`（UTC / JST 表示）

> ※ メーターの精度は ±10% 以内を目標としています。  
> ※ メーターの針の動作は使用するリグによって異なります。

---

## 🚀 起動手順

### 設定ファイルについて

通信異常が約20秒続くと、初期設定ファイルが自動で開きます。

```ini
# 修正後はアプリけーションの再起動を行ってください。
# After making the correction, restart the application.
#
# SCAN_SPは通信ポート読み出し周期です。0.01〜0.1の間で数字が小さいほど高速周期です。
# 推奨値: FTDX10=0.02 , FT710=xxx , FT891=0.1 , FT991=xxx
#
SERIAL_PORT=/dev/cu.usbserial-1410
BAUD_RATE=38400
SCAN_SP=0.02

# パラメータの意味
パラメータ	説明
SERIAL_PORT	通信ポート。例：
		Raspberry Pi /dev/USB0
		macOS /dev/cu.usbserial-1410
		Windows COM3
BAUD_RATE	通信速度。リグ側に合わせて設定（例：4800〜38400）
SCAN_SP		読み出し周期（0.01〜0.1）。値が小さいほど高速
