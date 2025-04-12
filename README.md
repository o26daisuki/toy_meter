# Toy Meter for YAESU FTDX10 / FT710 / FT891 / FT991

本ソフトウェアは、YAESU FTDX10 / FT710 / FT891 / FT991 向けの簡易メーターです。

本ソフトウェアの使用条件については、リポジトリ内の `LICENSE` ファイルをご参照ください。

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
```
```makedown
| パラメータ	| 説明                               		|
|---------------+-----------------------------------------------+
| SERIAL_PORT	| 通信ポート。例：                          	|
|              	| - Raspberry Pi: `/dev/USB0`               	|
|              	| - macOS: `/dev/cu.usbserial-1410`         	|
|              	| - Windows: `COM3`                         	|
| BAUD_RATE    	| 通信速度。リグ側に合わせて設定            		|
|              	| 例：4800〜38400                           	|
| SCAN_SP      	| 読み出し周期（0.01〜0.1）。値が小さいほど高速 	|
+---------------+-----------------------------------------------+
```

## 🍓 Raspberry Pi での利用
起動手順

1.アプリケーションをダウンロードして展開
```ini
unzip toy_meter_vx.x_rpi.zip
cd toy_meter
./toy_meter
```
2.自動起動を設定したい場合は以下を参照：
```ini
sudo nano /etc/systemd/system/toy_meter.service

[Unit]
Description=Toy Meter for YAESU FTDX10
[Service]
ExecStart=/home/pi/toy_meter/toy_meter -platform linuxfb
Environment=QT_QPA_PLATFORM=linuxfb
Restart=always
User=pi
Group=pi
[Install]
WantedBy=default.target

sudo systemctl enable toy_meter

```

## 🍎 macOS での利用
起動手順

1.ToyMeter_vx.x_mac.dmg をダウンロードしてインストール

2.USB接続ポートの確認（ターミナルで以下を実行）：
```ini
ls -l /dev/cu.*

/dev/cu.usbserial-1410
/dev/cu.SLAB_USBtoUART
→ 対象デバイスのポート名を確認してください。
```

## 🪟 Windows 11 での利用
起動手順

1.Toy_Meter_for_YAESU_vx.x_win.zip をダウンロード・展開し、実行ファイルを起動

2.デバイスマネージャーでポート番号（COMポート）を確認
```ini
Windowsツール → コンピュータの管理 → デバイスマネージャー → ポート（COMとLPT）
→ 対象デバイスのポート名を確認してください。
```

## 📩 お問い合わせ・バグ報告
現在はお受けしていません。

## 📝 ライセンス
MIT License（予定）


