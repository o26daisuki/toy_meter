# Toy_Meter Ver 1.0 (Raspiberry Pi , macOS(Sequoia 15.4.1)) , Windows11
#
# Toy_Meter は YAESU無線・新CATインターフェース向けです。
# 利用にあたってはLICENSEおよびREADMEを確認してください。
# 設計開発: JP1RXQ（権利保有者）、評価協力者:7K1AEU,JR2ANC,JR8URP,JE8CRA

import sys
import serial
import time
import re
import os
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor, QFont, QImage
from PyQt6.QtCore import Qt, QTimer, QDateTime, QTimeZone
#---------- GUI操作用
import subprocess
from PyQt6.QtGui import QMouseEvent

#--------- タッチGUI操作用
if sys.platform == "linux":  # Raspberry Pi (Linux) の場合のみ適用
    from evdev import InputDevice, categorize, ecodes, list_devices
    import threading

#---------- デレクトリ情報
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

#---------- タッチスクリーン実装確認(Raspberry Pi ADS7846専用)
def find_touch_device(name_keyword="ADS7846"):
    for path in list_devices():
        dev = InputDevice(path)
        if name_keyword in dev.name:
            return dev
    raise RuntimeError("Touchscreen device not found")

#---------- 設定ファイルの読み込み処理
def load_config():
    config_path = os.path.join(BASE_DIR, "toy_meter.conf")
    config = {}
    with open(config_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                config[key.strip()] = value.strip()
    return config

def parse_fnc_entry(entry: str):
    if not entry:
        return "", ""
    parts = entry.split(",", 1)  # ← 1回だけ分割（名前, コマンド）
    if len(parts) != 2:
        return entry.strip(), ""
    return parts[0].strip(), parts[1].strip()  # ← .rstrip(";") は削除！

#---------- 設定ファイルを読み込んで値を取得
config = load_config()
SERIAL_PORT = config.get("SERIAL_PORT")
SERIAL_PORT_DL = config.get("SERIAL_PORT_DL", SERIAL_PORT)
BAUD_RATE = int(config.get("BAUD_RATE"))
SCAN_SP = float(config.get("SCAN_SP"))
FNC1_label, FNC1_param = parse_fnc_entry(config.get("FNC1"))
FNC2_label, FNC2_param = parse_fnc_entry(config.get("FNC2"))
FNC3_label, FNC3_param = parse_fnc_entry(config.get("FNC3"))
FNC4_label, FNC4_param = parse_fnc_entry(config.get("FNC4"))

#---------- Raspiのフレームバッファクリア
if sys.platform == "linux":  # Raspberry Pi (Linux) の場合のみ適用
    os.system('dd if=/dev/zero of=/dev/fb0 > /dev/null 2>&1')

#---------- 開通試験(御呪い)
def test_serial_connection(ser):
    try:
        ser.reset_input_buffer()
        ser.write(b"RM1;\r\n")  # CRLF を送信
        time.sleep(0.1)
        response = ser.read_until(b";").decode("utf-8").strip()
        return bool(re.match(r"^[A-Z]{2}\d{4}(000)?;$", response))
    except Exception as e:
        return False

#---------- シリアルポートオープン
def open_serial_port():
    serial_port = SERIAL_PORT
    ser = None
    for attempt in range(2):
        try:
            ser = serial.Serial(serial_port, BAUD_RATE, timeout=SCAN_SP)
            if not test_serial_connection(ser):
                raise serial.SerialException("RM1 コマンドの応答が無効です")
            return ser
        except serial.SerialException as e:
            if ser:
                try:
                    ser.close()
                except:
                    pass
            ser = None
            serial_port = SERIAL_PORT_DL
            time.sleep(1) # 1sec

    print("❌ シリアルポートの接続に失敗しました。configの修正を行ってください。")

    config_path = os.path.join(BASE_DIR, "toy_meter.conf")
    if sys.platform == "darwin":  # macOS
        subprocess.run(["open", "-t", config_path])
    elif sys.platform == "linux": # Linux (Raspberry Piなど)
        subprocess.run(["nano", config_path])
    elif sys.platform == "win32": # Windows
        subprocess.run(["notepad", config_path])

    sys.exit(1)  # 異常終了

#---------- Class
class SignalPowerMeter(QWidget):
    def __init__(self):
        super().__init__()

        self.last_touch_time = 0 # タッチスクリーン初期化

        if sys.platform == "linux":  # Raspberry Pi (Linux) の場合のみ適用
            threading.Thread(target=self.touch_monitor, daemon=True).start()
            self.touch_dev = self.find_touch_device()  # ← Linux のときだけ呼ぶ

        self.port_error = False
        self.serial = open_serial_port()  # シリアルポート成功するまで待つ

        self.setWindowTitle("YAESU ToyMeter V1.0") # バージョン表示
        self.setGeometry(100, 100, 320, 480)
        self.meter_image = QPixmap(os.path.join(BASE_DIR, "meter-img", "ALL-meter.png")).scaled(
            320, 480,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        # 各メーターの初期値
        self.signal_strength = -20
        self.power_level = -18
        self.swr_level = -20
        self.alc_level = -20
        self.is_transmitting = False
        self.vfo_a = "000.000.000 MHz"
        self.vfo_b = "000.000.000 MHz"
        self.utc_time = "00:00:00"
        self.jst_time = "00:00:00"
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_meter)
        self.timer.start(10)
        self.rig_type = 0

#---------- メーター情報読み込み
    def update_meter(self):
        power_raw = self.get_raw_value(b"RM5;")
        self.power_level = (power_raw / 255) * 36 - 18
        self.is_transmitting = power_raw > 0

        if power_raw == 0:
            # 受信時: RM1; を読み取る, RM4; & RM6; はデフォルト値
            self.signal_strength = self.get_meter_angle(b"RM1;", scale=40, offset=-20)
            self.swr_level = -20  # デフォルト値
            self.alc_level = -20  # デフォルト値
        else:
            # 送信時: RM4; & RM6; を読み取る, RM1; はデフォルト値
            self.signal_strength = -20  # デフォルト値
            self.swr_level = self.get_meter_angle(b"RM6;", scale=40, offset=-20)
            if self.rig_type == 0: # FTDX10系列
                self.alc_level = self.get_meter_angle(b"RM4;", scale=40, offset=-20, divisor=36)
            else:
                self.alc_level = self.get_meter_angle(b"RM4;", scale=40, offset=-20)

        self.vfo_a = self.get_vfo_frequency(b"FA;")
        self.vfo_b = self.get_vfo_frequency(b"FB;")
        current_time = QDateTime.currentDateTimeUtc()
        jst_timezone = QTimeZone(b"Asia/Tokyo")
        self.utc_time = current_time.toString("hh:mm:ss")
        self.jst_time = current_time.toTimeZone(jst_timezone).toString("hh:mm:ss")

        self.update()

#---------- RMコマンド送信
    def get_raw_value(self, command):
        self.serial.reset_input_buffer()
        self.serial.write(command + b"\n")
        response = self.serial.readline().decode("utf-8").strip()

        # RM系コマンド応答でFT991A のフォーマットを FTDX10 に変換
        if re.match(r"(RM\d{4});\?;$", response):  # "RM1123;?;" のような形式のみマッチ
            response = response[:-3] + "000;?;"  # ";?; -> 000;?;" を追加
            self.rig_type = 1
        match = re.search(r"[A-Z]{2}\d(\d{3})000;", response)
        return int(match.group(1)) if match else 0

#---------- アナログメーター情報編集(読み取りデータ -> 0-255)
    def get_meter_angle(self, command, scale=40, offset=-20, divisor=255):
        raw_value = self.get_raw_value(command)
        return (raw_value / divisor) * scale + offset

#---------- VFOデータ編集
    def get_vfo_frequency(self, command):
        self.serial.write(command + b"\n")
        response = self.serial.readline().decode("utf-8").strip()
        if response.startswith(command[:2].decode()):
            freq_str = response[2:11]
            mhz = freq_str[:3]
            khz1 = freq_str[3:6]
            khz2 = freq_str[6:]
            return f"{mhz}.{khz1}.{khz2} MHz"
        return "000.000.000 MHz"

#---------- 各種メーターペイント
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self.meter_image)
        self.draw_needle(painter)
        self.draw_swr_needle(painter)
        self.draw_alc_needle(painter)
        self.draw_digital_meter(painter)

#---------- SIG & PO meter 表示
    def draw_needle(self, painter):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen_color = "yellow" if self.is_transmitting else "red"
        pen = QPen(QColor(pen_color), 3)
        painter.translate(160, 400)
        painter.rotate(self.power_level if self.is_transmitting else self.signal_strength)
        painter.setPen(pen)
        painter.drawLine(0, -300, 0, -390)
        painter.restore()

#---------- SWR meter 表示
    def draw_swr_needle(self, painter):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor("red"), 3)
        painter.translate(160, 520)
        painter.rotate(self.swr_level)
        painter.setPen(pen)
        painter.drawLine(0, -300, 0, -390)
        painter.restore()

#---------- ALC meter 表示
    def draw_alc_needle(self, painter):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor("lightblue"), 3)
        painter.translate(160, 640)
        painter.rotate(self.alc_level)
        painter.setPen(pen)
        painter.drawLine(0, -300, 0, -390)
        painter.restore()

#---------- VFO & TIME 表示
    def draw_digital_meter(self, painter):
        painter.setPen(QColor("white"))
        font = QFont()
        if sys.platform == "linux":
            font.setPointSize(18) # Linux Font size
        elif sys.platform == "darwin":
            font.setPointSize(24) # macOS Font size
        elif sys.platform == "win32":
            font.setPointSize(20) # win32 Font size
        painter.setFont(font)
        painter.drawText(100, 390, f"{self.vfo_a}")
        painter.drawText(100, 415, f"{self.vfo_b}")
        painter.drawText(80, 442, f"{self.utc_time} / {self.jst_time}")

        painter.setPen(QColor("white"))
        font = QFont()
        if sys.platform == "linux":
            font.setPointSize(9)
        elif sys.platform == "darwin":
            font.setPointSize(12)
        elif sys.platform == "win32":
            font.setPointSize(10)
        painter.setFont(font)
        painter.drawText(15, 470, f"{FNC1_label}")
        painter.drawText(78, 470, f"{FNC2_label}")
        painter.drawText(140, 470, f"{FNC3_label}")
        painter.drawText(202, 470, f"{FNC4_label}")

#---------- FNCキー機能と裏機能
#   JP1RXQクリック  ：toy_meter.conf設定画面
#   Wクリック       ：Auto-Tune起動
#   FNC-1からFNC-4 : 利用者設定機能

    def touch_monitor(self):
        if sys.platform != "linux":
            return

        touch_dev = self.find_touch_device()
        if touch_dev is None:
            print("タッチデバイスが見つかりません")
            return

        self.touch_dev = touch_dev

        for event in self.touch_dev.read_loop():
            if event.type == ecodes.EV_ABS:
                self.last_touch_time = time.time()

    def find_touch_device(self, name_keyword="ADS7846"):
        from evdev import list_devices, InputDevice
        for dev_path in list_devices():
            dev = InputDevice(dev_path)
            if name_keyword in dev.name:
                return dev
        return None
    
    def mousePressEvent(self, event):
        raw_x = event.position().x()
        raw_y = event.position().y()

        is_touch_input = (time.time() - self.last_touch_time < 0.3)
        if is_touch_input:
            screen_x, screen_y = self.convert_touch_to_screen(raw_x, raw_y)
        else:
            screen_x, screen_y = raw_x, raw_y

        self.handle_screen_touch(screen_x, screen_y)

    # 補正処理
    def convert_touch_to_screen(self, touch_x, touch_y):
        scale_x = 320 / (299 - 33)
        scale_y = 480 / (447 - 36)
        offset_x = 33
        offset_y = 36
        screen_x = (touch_x - offset_x) * scale_x
        screen_y = (touch_y - offset_y) * scale_y
        return screen_x, screen_y

    # 画面上でのクリック処理
    def handle_screen_touch(self, screen_x, screen_y):
        if 265 <= screen_x <= 320 and 450 <= screen_y <= 480: # Config Set Up
            config_path = os.path.join(BASE_DIR, "toy_meter.conf")
            if sys.platform == "darwin":
                subprocess.run(["open", "-t", config_path])
            elif sys.platform == "linux":
                subprocess.run(["nano", config_path])
            elif sys.platform == "win32":
                subprocess.run(["notepad", config_path])

        elif 280 <= screen_x <= 320 and 75 <= screen_y <= 105: # Auto-Tune
            self.serial.write(b"AC002;\r\n")
            time.sleep(0.05)

        elif 10 <= screen_x <= 65 and 450 <= screen_y <= 480: # FNC-1
            self.serial.write((FNC1_param + "\r\n").encode())
            time.sleep(0.05)
        elif 70 <= screen_x <= 125 and 450 <= screen_y <= 480: # FNC-2
            self.serial.write((FNC2_param + "\r\n").encode())
            time.sleep(0.05)
        elif 135 <= screen_x <= 190 and 450 <= screen_y <= 480: # FNC-3
            self.serial.write((FNC3_param + "\r\n").encode())
            time.sleep(0.05)
        elif 200 <= screen_x <= 255 and 450 <= screen_y <= 480: # FNC-4
            self.serial.write((FNC4_param + "\r\n").encode())
            time.sleep(0.05)

#---------- main
    def main():
        if sys.platform == "linux":  # Raspberry Pi (Linux) の場合のみ適用
            app = QApplication(sys.argv + ['-platform', 'linuxfb:fb=/dev/fb1'])
        else:  # macOSや他のOSの場合
            app = QApplication(sys.argv)

        meter = SignalPowerMeter()
        meter.showFullScreen()
        sys.exit(app.exec())

#---------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SignalPowerMeter()
    window.show()
    sys.exit(app.exec())
