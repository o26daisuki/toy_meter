# Toy Meter for YAESU FTDX10 / FT710 / FT891 / FT991

本ソフトウェアは、YAESU FTDX10 / FT710 / FT891 / FT991 向けの簡易メーターです。

本ソフトウェアの使用条件については、リポジトリ内の `LICENSE` ファイルをご参照ください。

> ⚠️ **注意：本アプリケーションは現在評価中です。**

YAESU無線機向けの簡易メーターアプリケーションです。以下のプラットフォームに対応しています：

- **Raspberry Pi OS Lite (64bit)** + 3.5inch LCD (480x320) タッチスクリーン機能使う場合、ドライバーはADS7846に限る
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

### ボタン部
- CATコマンドを最大4つまで自由に登録可能(ただし、応答を期待するコマンドは使えない)
- POメータ横のWを押すとAuto-Tune開始
- 右下JP1RXQを押すとConfig設定開始

> ※ メーターの精度は ±10% 以内を目標としています。  
> ※ メーターの針の動作速度は使用する無線機と利用環境によって異なります。

---

## 🚀 起動手順

### 設定ファイルについて

最初にアプリ起動後、通信異常が数秒続くと初期設定ファイルが自動で開きます。

メーター運用中に設定を変えたい場合は右下のJP1RXQをクリックしてください。

```ini
# 修正後はアプリけーションの再起動を行ってください。
# After making the correction, restart the application.
#
# SERIAL_PORTはリグおよびPCの設定を一致させてください。N82フロー無しです。
#	Raspi /dev/ttyUSB0など、 macOS /dev/cu.xxxxxxなど、 Win32 COMxなど
# SERIAL_PORT_DLはDual UART用に準備された物ですが、2つ目のポートとして指定できます。
#	macOS /dev/cu.SLAB_USBtoUART または /dev/cu.SLAB_USBtoUART1など
#       同時に２つのポートは使えません。
# SCAN_SPは通信ポート読み出し周期です。0.01〜0.1の間で数字が小さいほど高速周期です。
# 	推奨値:FTDX10=0.02 , FT770=xxx , FT891=0.1 , FT991=0.1
# FNCxはCATコマンド発行機能です。
#	第1パラメーターはLabel(6文字)、第2パラメーターはCommandになっています。
#	CAT仕様書が理解できる方のみ使ってください。設定ミスは設備の破損に繋がります！！
#	ご自身でリグに合わせて４つまで設定可能です。
#	Read系のCATコマンド発行できても応答は拾えません(使えません)。
#	サンプル情報はFTDX10で行っています。
#
SERIAL_PORT=/dev/cu.usbserial-1410
SERIAL_PORT_DL=/dev/cu.SLAB_USBtoUART1
BAUD_RATE=38400
SCAN_SP=0.02
FNC1=_MAIN_,BD0;
FNC2=_SUB__,BD1;
FNC3=__FM__,MD04;
FNC4=DT_USB,MD0C;
```
```makedown
| パラメータ      | 説明                             	        |
|---------------+-----------------------------------------------+
| SERIAL_PORT	| 通信ポート。例：                              	|
|              	| - Raspberry Pi: `/dev/ttyUSB0`               	|
|              	| - macOS: `/dev/cu.usbserial-1410`         	|
|              	| - Windows: `COM3`                         	|
| SERIAL_PORT_DL| Dual UART用第二通信ポートまたは第二無線設備など     |
| BAUD_RATE    	| 通信速度。リグ側に合わせて設定            		|
|              	| 例：4800〜38400                           	|
| SCAN_SP      	| 読み出し周期（0.01〜0.1）。値が小さいほど高速 	|
| FNC1 - FNC4   | CATコマンド発行機能(機種に合わせて自由設定)         |
|               | - 第1パラメーターはLabel(6文字)                   |
|               | - 第2パラメーターはCommand                       |
+---------------+-----------------------------------------------+
```

## 🍓 Raspberry Pi で利用
起動手順

0.Raspberry Piの準備
```ini
【ターゲット設備(指定以外は動作保証なし)】
	Raspberry 3B+
	3.5inch LCD 480x320タッチパネル・ディスプレイ(ADS7846ドライバー)
	microSD 16GB以上

【OSインストール】
	Raspberry Pi OS Lite(64bit) 0.4GB版　　←　Desktop版は使わない 
	OSをmicroSDに焼く前に初期設定を行う。設定は全て任意です。
	raspberry pi imager(macOS版) の場合は下記の通り
	ホスト名：toymeter 
	SSHを有効化する
		パスワード認証を使う
	ユーザー名とパスワードを設定する
		ユーザー名：pi
		パスワード：raspberry
	Wi-Fiを設定する
		SSID:　利用環境に合わせて設定
		パスワード: 　利用環境に合わせて設定
	ロケーションの設定
		タイムゾーン：　Asia/Tokyo
		キーボード：　jp
	
【環境更新】
	sudo apt update
	apt list --upgradable
	sudo apt upgrade

【Gitインストール】
	sudo apt install git

【3.5inch LCDの実装】
	https://www.instructables.com/Raspberry-Pi-4B3B-35-Inch-LCD-Touch-DisplayScreen-/
	sudo rm -rf LCD-show
	git clone  https://github.com/goodtft/LCD-show.git  
	chmod -R 755 LCD-show 
	cd LCD-show/
	sudo ./LCD35-show
	# ディスプレイを回転させる
	sudo nano /boot/config.txt
		dtoverlay=tft35a:rotate=0
		hdmi_cvt 320 480 60 6 0 0 0
	# 環境設定
	nano .bashrc
		# カスタム
		export QT_QPA_PLATFORM=linuxfb
		export QT_QPA_EGLFS_FB=/dev/fb0
		export QT_QPA_EVDEV_TOUCHSCREEN_PARAMETERS="/dev/input/event0"
		export PATH=$HOME/.local/bin:$PATH

```
1.アプリケーションをダウンロードして展開
```ini
cd
sudo systemctl stop toy_meter
sudo rm -r toy_meter
wget https://github.com/o26daisuki/toy_meter/releases/download/vx.x/toy_meter_vx.x_rpi.zip
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
3.ソースコードで動かしたい場合は以下を参照：
```ini
sudo apt update
	sudo apt install -y python3 python3-pyqt6 python3-serial python3-pip libqt6gui6 libqt6core6 libqt6widgets6 qt6-qpa-plugins libegl1-mesa

cd
git clone 現在調整中
cd toy_meter
nano toy_meter.conf
python3 toy_meter.py

sudo nano /etc/systemd/system/toy_meter.service
[Unit]
Description=Toy Meter for YAESU FTDX10
[Service]
ExecStart=/usr/bin/python3 /home/pi/toy_meter/toy_meter.py -platform linuxfb
Environment=QT_QPA_PLATFORM=linuxfb
Restart=always
User=pi
Group=pi
[Install]
WantedBy=default.target

sudo systemctl enable toy_meter

```

## 🍎 macOS で利用
起動手順

1.toy_meter_vx.x_mac.dmg をダウンロードしてインストール

2.USB接続ポートの確認（ターミナルで以下を実行）：
```ini
ls -l /dev/cu.*

/dev/cu.usbserial-1410
/dev/cu.SLAB_USBtoUART
→ 対象デバイスのポート名を確認してください。
```

## 🪟 Windows 11 で利用
起動手順

1.toy_meter_vx.x_win.zip をダウンロード・展開し、実行ファイルを起動

2.デバイスマネージャーでポート番号（COMポート）を確認
```ini
Windowsツール → コンピュータの管理 → デバイスマネージャー → ポート（COMとLPT）
→ 対象デバイスのポート名を確認してください。
```

## 📩 お問い合わせ・バグ報告
現在はお受けしていません。

## 📝 ライセンス
LICENSE ファイル参照

## 🎁謝意
7K1AEU , JR2ANC , JR8URP , JE8CRA 評価試験ありがとうございます。
