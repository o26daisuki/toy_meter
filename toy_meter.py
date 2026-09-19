#!/usr/bin/env python3

# Toy_Meter Ver 2.0 - rigctld TCP/NET対応版
#
# toy_meter.py
#
# toy_meter - Radio Signal Power Meter
#
# Copyright (c) 2026 JP1RXQ
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Toy_Meter は rigctld (Hamlib) を利用して
# Hamlib対応機種からメーター情報と周波数情報を取得します。
#
# 設計開発: JP1RXQ
# 評価協力者: JR2ANC, 7K1AEU


import sys, time, os, socket, subprocess, signal, atexit
import shutil, math, threading, logging
import inspect

from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QDialog
)

from PyQt6.QtGui import (
    QPixmap,
    QPainter,
    QPen,
    QColor,
    QFont,
    QMouseEvent
)
from PyQt6.QtCore import Qt, QTimer, QDateTime
from pathlib import Path
from toy_meter_setup import SetupDialog

# ==========================================
# Logging
# ==========================================
log_dir = Path.home() / "toy_meter_logs"
log_dir.mkdir(exist_ok=True)

log_file = log_dir / "toy_meter.log"

#---------- 10MBを超えたら削除
MAX_LOG_SIZE = 10 * 1024 * 1024      # 10MB

try:
    if log_file.exists():
        if log_file.stat().st_size > MAX_LOG_SIZE:
            log_file.unlink()
except Exception:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

logger.info("========== toy_meter started ==========")

#---------- ディレクトリ情報
BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

# =====================================
# 設定ファイル読み込み
# =====================================
def load_config():

    config_path = os.path.join(
        BASE_DIR,
        "toy_meter.conf"
    )

    config = {}

    with open(
        config_path,
        "r",
        encoding="utf-8"
    ) as f:

        for line in f:

            line = line.strip()

            if "=" in line and not line.startswith("#"):

                key, value = line.split("=", 1)

                config[key.strip()] = value.strip()

    return config

# =====================================
# ALC REFERENCE保存
# =====================================
def save_alc_reference(reference):

    global ALC_REFERENCE

    # メモリ上の値も更新
    ALC_REFERENCE = reference

    config_path = os.path.join(
        BASE_DIR,
        "toy_meter.conf"
    )

    config = load_config()

    config["ALC_REFERENCE"] = f"{reference:.3f}"

    with open(
        config_path,
        "w",
        encoding="utf-8"
    ) as f:

        for key, value in config.items():
            f.write(f"{key}={value}\n")
 
# =====================================
# RF REFERENCE保存
# =====================================
def save_rf_reference(reference):

    global RF_REFERENCE

    RF_REFERENCE = reference

    config_path = os.path.join(
        BASE_DIR,
        "toy_meter.conf"
    )

    config = load_config()

    config["RF_REFERENCE"] = f"{reference:.3f}"

    with open(
        config_path,
        "w",
        encoding="utf-8"
    ) as f:

        for key, value in config.items():
            f.write(f"{key}={value}\n")
            
# =====================================
# FNC解析
# =====================================
def parse_fnc_entry(entry: str):

    if not entry:
        return "", ""

    parts = entry.split(",", 1)

    if len(parts) != 2:
        return entry.strip(), ""

    return (
        parts[0].strip(),
        parts[1].strip()
    )

#---------- config読み込み
config = load_config()

#---------- RF POWER RANGE
RF_POWER_RANGE = int(
    config.get("RF_POWER_RANGE", "100")
)

#---------- OPERATING MODE
OPERATING_MODE = config.get(
    "OPERATING_MODE",
    "Normal",
)

#---------- ALC REFERENCE
ALC_REFERENCE = float(
    config.get(
        "ALC_REFERENCE",
        "0.6"
    )
)

#---------- RF REFERENCE
RF_REFERENCE = float(
    config.get(
        "RF_REFERENCE",
        "0.25"
    )
)
#---------- 接続方式
CONNECTION = config.get(
    "CONNECTION",
    "NET"
).upper()

SCAN_SP = float(
    config.get("SCAN_SP", "0.2")
)

RIGCTLD_HOST = config.get(
    "RIGCTLD_HOST",
    "127.0.0.1"
)

RIGCTLD_PORT = int(
    config.get("RIGCTLD_PORT", "4532")
)
#-------------------------------------------------
# rigctld TCP ports
#-------------------------------------------------
RIGCTLD_PORTS = [4532, 4534, 4536, 4538]

SERIAL_PORT = config.get(
    "SERIAL_PORT",
    ""
)

RIG_MODEL = int(
    config.get("RIG_MODEL", "1022")
)

BAUD_RATE = int(
    config.get("BAUD_RATE", "38400")
)

FNC1_label, FNC1_param = parse_fnc_entry(
    config.get("FNC1", "")
)

FNC2_label, FNC2_param = parse_fnc_entry(
    config.get("FNC2", "")
)

FNC3_label, FNC3_param = parse_fnc_entry(
    config.get("FNC3", "")
)

FNC4_label, FNC4_param = parse_fnc_entry(
    config.get("FNC4", "")
)

#---------- WINDOW POSITION
WINDOW_X = int(
    config.get("WINDOW_X", "100")
)

WINDOW_Y = int(
    config.get("WINDOW_Y", "100")
)

# =====================================
# rigctld 実行ファイル探索
# =====================================
def find_rigctld():

    #---------- PyInstaller同梱版を優先
    if getattr(sys, "frozen", False):

        bundled = os.path.join(
            sys._MEIPASS,
            "rigctld"
        )

        if os.path.exists(bundled):

            logger.info(
                f"Using bundled rigctld: {bundled}"
            )

            return bundled

    #---------- PATHから探索
    path = shutil.which("rigctld")

    if path:

        logger.info(
            f"Using PATH rigctld: {path}"
        )

        return path

    #---------- Windows
    if sys.platform == "win32":

        candidates = [

            r"C:\Program Files\hamlib-w64-4.7.1\bin\rigctld.exe",
            r"C:\Program Files\Hamlib\bin\rigctld.exe",
        ]

    #---------- macOS / Linux
    else:

        candidates = [

            "/opt/homebrew/bin/rigctld",
            "/usr/local/bin/rigctld",
            "/usr/bin/rigctld",
        ]

    #---------- 実在確認
    for candidate in candidates:

        if os.path.exists(candidate):

            logger.info(
                f"Using installed rigctld: {candidate}"
            )

            return candidate

    logger.error(
        "rigctld not found"
    )

    return None

# =====================================
# rigctld起動
# =====================================
def start_rigctld():

    global RIGCTLD_PORT

    caller = inspect.stack()[1]

    logger.info(
        f"start_rigctld() called from "
        f"{caller.function}:{caller.lineno}"
    )

    #-------------------------------------------------
    # NET接続時はrigctldを起動しない
    #-------------------------------------------------

    if CONNECTION == "NET":

        logger.info(
            f"🌐 NETWORK MODE "
            f"{RIGCTLD_HOST}:{RIGCTLD_PORT}"
        )

        return None

    #-------------------------------------------------
    # USB接続
    #-------------------------------------------------

    rigctld_path = find_rigctld()

    if rigctld_path is None:

        logger.warning(
            "❌ rigctld not found"
        )

        sys.exit(1)

    logger.info(
        f"Using rigctld: {rigctld_path}"
    )

    #-------------------------------------------------
    # 既存rigctld確認
    #-------------------------------------------------

    logger.info(
        "🔎 checking existing rigctld..."
    )

    existing_pids = []

    #-------------------------------------------------
    # Windows
    #-------------------------------------------------

    if sys.platform == "win32":

        result = subprocess.run(
            [
                "tasklist",
                "/FI",
                "IMAGENAME eq rigctld.exe",
                "/FO",
                "CSV",
                "/NH"
            ],
            capture_output=True,
            text=True
        )

        if result.stdout:

            for line in result.stdout.splitlines():

                parts = line.split(",")

                if len(parts) < 2:
                    continue

                pid_text = (
                    parts[1]
                    .strip()
                    .strip('"')
                )

                if pid_text.isdigit():

                    existing_pids.append(
                        int(pid_text)
                    )

    #-------------------------------------------------
    # Linux / macOS / Raspberry Pi
    #-------------------------------------------------

    else:

        result = subprocess.run(
            [
                "pgrep",
                "-x",
                "rigctld"
            ],
            capture_output=True,
            text=True
        )

        if result.stdout:

            for pid in result.stdout.splitlines():

                pid = pid.strip()

                if pid.isdigit():

                    existing_pids.append(
                        int(pid)
                    )

    #-------------------------------------------------
    # 自分のPID
    #-------------------------------------------------

    my_pid = os.getpid()

    if existing_pids:

        logger.info(
            f"toy_meter PID={my_pid}"
        )

    #-------------------------------------------------
    # 使用中のSerial / TCPポート
    #-------------------------------------------------
    used_serial_ports = []

    used_tcp_ports = []

    #-------------------------------------------------
    # 既存rigctldを調査
    #-------------------------------------------------

    for rig_pid in existing_pids:

        logger.info(
            f"existing rigctld PID={rig_pid}"
        )

        command_line = ""

        parent_pid = None

        #-------------------------------------------------
        # Windows
        #-------------------------------------------------

        if sys.platform == "win32":

            #---------- コマンドライン取得

            try:

                ps_result = subprocess.run(
                    [
                        "powershell",
                        "-NoProfile",
                        "-Command",
                        (
                            "Get-CimInstance Win32_Process "
                            f"-Filter \"ProcessId = {rig_pid}\" "
                            "| Select-Object -ExpandProperty CommandLine"
                        )
                    ],
                    capture_output=True,
                    text=True
                )

                command_line = (
                    ps_result.stdout.strip()
                )

            except Exception as e:

                logger.warning(
                    f"⚠️ command line check failed: {e}"
                )

            #---------- 親PID取得

            try:

                parent_result = subprocess.run(
                    [
                        "wmic",
                        "process",
                        "where",
                        f"ProcessId={rig_pid}",
                        "get",
                        "ParentProcessId",
                        "/value"
                    ],
                    capture_output=True,
                    text=True
                )

                for line in (
                    parent_result.stdout.splitlines()
                ):

                    if line.startswith(
                        "ParentProcessId="
                    ):

                        value = line.split(
                            "=",
                            1
                        )[1].strip()

                        if value.isdigit():

                            parent_pid = int(
                                value
                            )

                        break

            except Exception:

                pass

        #-------------------------------------------------
        # Linux / macOS / Raspberry Pi
        #-------------------------------------------------

        else:

            #---------- コマンドライン取得

            try:

                ps_result = subprocess.run(
                    [
                        "ps",
                        "-p",
                        str(rig_pid),
                        "-o",
                        "args="
                    ],
                    capture_output=True,
                    text=True
                )

                command_line = (
                    ps_result.stdout.strip()
                )

            except Exception as e:

                logger.warning(
                    f"⚠️ command line check failed: {e}"
                )

            #---------- 親PID取得

            try:

                parent_result = subprocess.run(
                    [
                        "ps",
                        "-o",
                        "ppid=",
                        "-p",
                        str(rig_pid)
                    ],
                    capture_output=True,
                    text=True
                )

                parent_text = (
                    parent_result.stdout.strip()
                )

                if parent_text.isdigit():

                    parent_pid = int(
                        parent_text
                    )

            except Exception:

                pass

        #-------------------------------------------------
        # コマンドライン表示
        #-------------------------------------------------

        if command_line:

            logger.info(
                f"rigctld PID={rig_pid} "
                f"command line:"
            )

            logger.info(
                command_line
            )

        #-------------------------------------------------
        # 自分が起動したrigctld
        #-------------------------------------------------

        if parent_pid == my_pid:

            logger.info(
                f"✅ existing rigctld PID={rig_pid} "
                f"is owned by this toy_meter"
            )

            #---------- 既存rigctldのSerialを確認

            existing_serial = None

            command_parts = (
                command_line.split()
            )

            for index, part in enumerate(
                command_parts
            ):

                if part == "-r":

                    if (
                        index + 1
                        < len(command_parts)
                    ):

                        existing_serial = (
                            command_parts[index + 1]
                        )

                    break

            if existing_serial:

                logger.info(
                    f"existing rigctld "
                    f"SERIAL_PORT={existing_serial}"
                )

                #---------- 自分のrigctldを再利用

                RIGCTLD_PORT = (
                    RIGCTLD_PORT
                )

                return None

        #-------------------------------------------------
        # 既存rigctldのSerial / TCPポート取得
        #-------------------------------------------------

        command_parts = (
            command_line.split()
        )

        existing_serial = None
        existing_port = None

        for index, part in enumerate(
            command_parts
        ):

            #---------- Serial

            if part == "-r":

                if (
                    index + 1
                    < len(command_parts)
                ):

                    existing_serial = (
                        command_parts[index + 1]
                    )

            #---------- TCP port

            elif part == "-t":

                if (
                    index + 1
                    < len(command_parts)
                ):

                    port_text = (
                        command_parts[index + 1]
                    )

                    if port_text.isdigit():

                        existing_port = int(
                            port_text
                        )

        #-------------------------------------------------
        # 取得結果
        #-------------------------------------------------

        if existing_serial:

            logger.info(
                f"existing rigctld PID={rig_pid} "
                f"SERIAL_PORT={existing_serial}"
            )

            used_serial_ports.append(
                existing_serial
            )

        if existing_port is not None:

            logger.info(
                f"existing rigctld PID={rig_pid} "
                f"RIGCTLD_PORT={existing_port}"
            )

            used_tcp_ports.append(
                existing_port
            )

        #-------------------------------------------------
        # 同じSerial Portなら起動禁止
        #-------------------------------------------------

        if (
            existing_serial is not None
            and existing_serial == SERIAL_PORT
        ):

            logger.warning(
                f"❌ SERIAL_PORT already in use: "
                f"{SERIAL_PORT}"
            )

            logger.warning(
                f"❌ existing rigctld PID={rig_pid}"
            )

            logger.warning(
                "❌ toy_meter startup cancelled"
            )

            return False

    #-------------------------------------------------
    # 利用可能なTCPポートを選択
    #-------------------------------------------------

    selected_port = None

    for port in RIGCTLD_PORTS:

        #---------- 既存rigctldが使用中

        if port in used_tcp_ports:

            logger.info(
                f"⚠️ RIGCTLD TCP port "
                f"{port} already in use"
            )

            continue

        #---------- OS上で使用中か確認

        test_sock = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM
        )

        try:

            test_sock.bind(
                ("127.0.0.1", port)
            )

            selected_port = port

            logger.info(
                f"✅ RIGCTLD TCP port "
                f"{port} available"
            )

            break

        except OSError:

            logger.info(
                f"⚠️ RIGCTLD TCP port "
                f"{port} occupied by another application"
            )

        finally:

            test_sock.close()

    #-------------------------------------------------
    # 利用可能ポートなし
    #-------------------------------------------------

    if selected_port is None:

        logger.warning(
            "❌ All RIGCTLD TCP ports are in use"
        )

        logger.warning(
            f"❌ available ports: "
            f"{RIGCTLD_PORTS}"
        )

        logger.warning(
            "❌ toy_meter startup cancelled"
        )

        return False

    #-------------------------------------------------
    # 今回使用するポートを決定
    #-------------------------------------------------

    RIGCTLD_PORT = selected_port

    logger.info(
        f"🎯 selected RIGCTLD TCP port="
        f"{RIGCTLD_PORT}"
    )

    #-------------------------------------------------
    # rigctld 新規起動
    #-------------------------------------------------

    logger.info(
        "🚀 starting rigctld..."
    )

    logger.info(
        f"RIG_MODEL={RIG_MODEL}, "
        f"SERIAL_PORT={SERIAL_PORT}, "
        f"BAUD_RATE={BAUD_RATE}, "
        f"RIGCTLD_PORT={RIGCTLD_PORT}"
    )

    listen_host = "0.0.0.0"

    cmd = [

        rigctld_path,

        "-m",
        str(RIG_MODEL),

        "-r",
        SERIAL_PORT,

        "-s",
        str(BAUD_RATE),

        "-T",
        listen_host,

        "-t",
        str(RIGCTLD_PORT),

        "-C",
        "timeout=250",

        "-C",
        "dtr_state=OFF",
    ]

    flags = 0

    if os.name == "nt":

        flags = (
            subprocess.CREATE_NO_WINDOW
        )

    proc = subprocess.Popen(

        cmd,

        stdout=subprocess.DEVNULL,

        stderr=subprocess.DEVNULL,

        creationflags=flags
    )

    #-------------------------------------------------
    # rigctld起動待ち
    #-------------------------------------------------

    for i in range(20):

        try:

            test_sock = socket.socket(
                socket.AF_INET,
                socket.SOCK_STREAM
            )

            test_sock.connect(
                (
                    "127.0.0.1",
                    RIGCTLD_PORT
                )
            )

            test_sock.close()

            logger.info(
                "✅ rigctld started"
            )

            return proc

        except Exception:

            test_sock.close()

            time.sleep(0.5)

    #-------------------------------------------------
    # 起動タイムアウト
    #-------------------------------------------------

    logger.warning(
        "❌ rigctld start timeout"
    )

    return proc

# =====================================
# rigctld停止
# =====================================

def stop_rigctld(proc):

    caller = inspect.stack()[1]

    logger.info(
        f"stop_rigctld() called from "
        f"{caller.function}:{caller.lineno}"
    )

    if proc is None:
        logger.info(
            "ℹ️ No rigctld process owned by this toy_meter"
        )
        return

    try:

        #---------- rigctld停止
        proc.terminate()

        proc.wait(timeout=3)

        logger.info(
            "🛑 rigctld stopped"
        )

        #=================================================
        # Serial Port Reset / Release
        #=================================================

        reset_serial_port(
            SERIAL_PORT
        )

    except Exception as e:

        logger.error(
            f"rigctld stop error: {e}"
        )

# =====================================
# Serial Port Reset / Release
# =====================================

def reset_serial_port(serial_port):
    """
    Reset and safely release the serial port after rigctld stops.

    Windows:
        Use pyserial to open the COM port temporarily and force
        RTS/DTR to OFF.

    Linux / macOS:
        Use pyserial to open the device temporarily and force
        RTS/DTR to OFF.
    """

    logger.info(
        f"🔄 reset_serial_port() called: {serial_port}"
    )

    if not serial_port:
        logger.warning(
            "⚠️ No serial port specified"
        )
        return

    try:
        import serial

        #---------- Serial portを一時的にOpen
        ser = serial.Serial(
            port=serial_port,
            baudrate=9600,
            timeout=0.5,
            write_timeout=0.5
        )

        logger.info(
            f"🔓 Serial port opened for reset: {serial_port}"
        )

        #---------- RTS OFF
        try:
            ser.rts = False
            logger.info(
                "✅ RTS OFF"
            )
        except Exception as e:
            logger.warning(
                f"⚠️ RTS OFF failed: {e}"
            )

        #---------- DTR OFF
        try:
            ser.dtr = False
            logger.info(
                "✅ DTR OFF"
            )
        except Exception as e:
            logger.warning(
                f"⚠️ DTR OFF failed: {e}"
            )

        #---------- Input buffer / Output bufferを破棄
        try:
            ser.reset_input_buffer()
            ser.reset_output_buffer()

            logger.info(
                "✅ Serial buffers reset"
            )

        except Exception as e:
            logger.warning(
                f"⚠️ Serial buffer reset failed: {e}"
            )

        #---------- Serial port close
        ser.close()

        logger.info(
            f"🔒 Serial port released: {serial_port}"
        )

    except Exception as e:
        logger.error(
            f"❌ Serial port reset error: {e}"
        )
        
# =====================================
# rigctld TCP通信クラス
# =====================================
class HamlibRigTCP:

    def __init__(
        self,
        host="127.0.0.1",
        port=4532
    ):

        self.host = host
        self.port = port

        self.sock = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM
        )

        self.sock.settimeout(0.5)

        #---------- RFPOWERエラー時スキップカウンタ
        self.rfpower_error_skip = 0

        try:

            self.sock.connect(
                (host, port)
            )

            self.lock = threading.Lock()

            logger.info(
                f"✅ connected to rigctld "
                f"{host}:{port}"
            )

        except Exception as e:

            logger.error(
                f"❌ rigctld connection failed: {e}"
            )

            raise

    #---------- rigctld command
    def command(self, cmd):

        with self.lock:

            try:

                #----- ソケットが無ければ再接続
                if self.sock is None:
                    self.connect()

                self.sock.settimeout(0.5)

                #---------- send
                self.sock.sendall(
                    (cmd + "\n").encode()
                )

                data = b""

                while not data.endswith(b"\n"):

                    chunk = self.sock.recv(1024)

                    if not chunk:
                        break

                    data += chunk

                response = data.decode().strip()

                return response

            except socket.timeout:

                try:
                    self.sock.close()
                except Exception:
                    pass

                self.sock = None

                return ""

            except Exception as e:
            
                try:
                    self.sock.close()
                except Exception:
                    pass

                self.sock = None

                logger.error(
                    f"TCP command error: {e}"
                )

                return ""

    #---------- 無線機接続
    def connect(self):

        self.sock = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM
        )

        self.sock.settimeout(0.5)

        self.sock.connect(
            (self.host, self.port)
        )
    
    #---------- TUNE開始
    def start_tune(self):

        self.command("G TUNE")

    #---------- FNCコマンド送信（CAT raw command）
    def send_raw_cat(self, cmd):

        logger.info(
            f"FNC_CMD={cmd}"
        )

        self.command(f"w {cmd}")

    #---------- 周波数取得
    def get_freq(self):
    
        try:
        
            return float(self.command("f"))
            
        except Exception as e:
        
            logger.error(f"get_freq error: {e}")
            
            return 0.0
        
    #---------- Sメータ
    def get_strength(self):

        try:

            val = self.command(
                "l STRENGTH"
            )

            return float(val)

        except Exception:

            return -54.0

    #---------- RF POWER
    def get_rfpower(self):

        #---------- エラー後のスキップ期間
        if self.rfpower_error_skip > 0:

            self.rfpower_error_skip -= 1

            return 0.0

        try:

            #---------- 実送信出力(0.0-1.0)
            val = self.command(
                "l RFPOWER_METER"
            )

            rf = float(val)

            if rf < 0.0:
                return 0.0

            if rf > 1.0:
                rf = 1.0

            return rf

        except Exception as e:

            #---------- 次回から50回スキップ
            self.rfpower_error_skip = 50

            return 0.0

    #---------- ALC
    def get_alc(self):

        try:

            val = self.command("l ALC")

            alc = float(val)

            # 負値だけ除去
            return max(
                0.0,
                alc
            )

        except Exception as e:

            logger.error(
                f"ALC ERROR: {e}"
            )

            return 0.0
        
    #---------- SWR
    def get_swr(self):
        try:
            return float(self.command("l SWR"))

        except Exception as e:
            logger.error(f"SWR error: {e}")
            return 0.0
                
    #---------- PTT状態
    def get_ptt(self):

        try:

            val = self.command("t")

            return int(val)

        except Exception:

            return 0

# =====================================
# Main Window
# =====================================
class SignalPowerMeter(QWidget):

    def __init__(self):

        super().__init__()

        self.last_touch_time = 0

        #---------- rigctld start

        self.rigctld_proc = start_rigctld()

        #---------- 他のtoy_meterがrigctldを使用中

        if self.rigctld_proc is False:

            logger.warning(
                "❌ Another toy_meter is already using "
                "the same rigctld"
            )
            
            #---------- rigctldは自分のプロセスではない
            self.rigctld_proc = None

            QTimer.singleShot(
                0,
                QApplication.instance().quit
            )

            return

        #---------- rigctld connect

        try:

            if CONNECTION == "USB":

                self.rig = HamlibRigTCP(
                    host="127.0.0.1",
                    port=RIGCTLD_PORT
                )

            else:

                self.rig = HamlibRigTCP(
                    host=RIGCTLD_HOST,
                    port=RIGCTLD_PORT
                )

        except Exception as e:

            logger.warning(
                f"Hamlib connection failed: {e}"
            )

            self.rig = None

        #---------- NET connection retry

        self.net_retry_timer = None

        #=================================================
        # NET retry counter
        #=================================================
        self.net_retry_count = 0

        if (
            CONNECTION == "NET"
            and self.rig is None
        ):

            self.net_retry_timer = QTimer(self)

            self.net_retry_timer.timeout.connect(
                self.retry_net_connection
            )

            #---------- 1秒間隔
            self.net_retry_timer.start(1000)

            logger.info(
                "🌐 NET connection retry started"
            )

        #---------- Window Title

        if CONNECTION == "USB":
            self.setWindowTitle(
                f"ToyMeter V2.0 [USB:{RIGCTLD_PORT}]"
            )
        else:
            self.setWindowTitle(
                f"ToyMeter V2.0 [{CONNECTION}]"
            )

        self.setGeometry(
            WINDOW_X,
            WINDOW_Y,
            320,
            480
        )

        self.meter_image = QPixmap(
            os.path.join(
                BASE_DIR,
                "meter-img",
                "ALL-meter.png"
            )
        ).scaled(
            320,
            480,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        #---------- PO meter scale setting
        base_scale = [
        
            (10, 65, 85),
            (25, 100, 80),
            (50, 144, 78),
            (75, 200, 82),
            (100, 245, 87),
        ]
        
        # RF_POWER_RANGE読込み
        self.rf_power_range = RF_POWER_RANGE

        self.po_meter_scale = []

        for value, x, y in base_scale:

            scaled_value = (
                value * self.rf_power_range / 100
            )

            self.po_meter_scale.append(
                (scaled_value, x, y)
            )
    
        #---------- meter init
        self.signal_strength = -20
        self.power_level = -18
        self.swr_level = -20
        self.alc_level = -20
        self.swr_angle = -20

        self.vfo = "000.000.000 MHz"

        self.utc_time = "00:00:00"
        self.local_time = "00:00:00"

        #---------- timer
        self.timer = QTimer(self)

        self.timer.timeout.connect(
            self.update_meter
        )

        self.timer.start(
            int(SCAN_SP * 1000)
        )

        #---------- ptt
        self.is_transmitting = False
        self.off_count = 0

        #---------- setup画面自動起動
        self.freq_error_count = 0
        self.setup_launched = False

        #----- Meter Status
        self.sig_raw = ""
        self.swr_raw = ""
        self.po_raw  = ""
        self.alc_raw = ""

        if self.rig is not None:

            self.sig_raw = self.rig.command(
                "l STRENGTH"
            )

            self.swr_raw = self.rig.command(
                "l SWR"
            )

            self.po_raw = self.rig.command(
                "l RFPOWER_METER"
            )

            self.alc_raw = self.rig.command(
                "l ALC"
            )

        self.status_counter = 0

        # 定期画面リフレッシュ
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(
            self.full_refresh
        )
        self.refresh_timer.start(60000)   # 60秒

        #---------- rigctld接続失敗時
        if self.rig is None:
        
            if CONNECTION == "NET":
                # リトライ開始
                pass
                
            else:
                # 今まで通りSetup

                QTimer.singleShot(
                    0,
                    self.launch_setup
                )
   
    #---------- 周波数表示
    def format_freq(
        self,
        freq_hz: float
    ) -> str:

        if freq_hz <= 0:

            return "000.000.000 MHz"

        freq_int = int(freq_hz)

        mhz_part = freq_int // 1_000_000

        khz_part = (
            (freq_int % 1_000_000) // 1000
        )

        hz_part = freq_int % 1000

        return (
            f"{mhz_part:03d}."
            f"{khz_part:03d}."
            f"{hz_part:03d} MHz"
        )

    #---------- STRENGTH normalize
    def normalize_strength(
        self,
        strength
    ):

        strength = max(
            -54.0,
            min(strength, 60.0)
        )

        #---------- S0 ～ S9
        if strength <= 0:

            return (
                (strength + 54.0) / 108.0
            )

        #---------- S9 ～ +60
        else:

            return 0.5 + (
                strength / 120.0
            )

    #---------- SWR angle convert
    def swr_to_angle(self, swr):

        #---------- invalid
        if swr <= 1.0:
            return -20.0

        #---------- lookup table
        table = [
            (1.0, -20),
            (1.2, -16),
            (1.5, -10),
            (2.0,  -2),
            
            (3.0, 3),
            (5.0, 5),
            
            #---------- high SWR
            (10.0, 8),
            (25.0, 15),

            #---------- infinity
            (100.0, 26),
        ]

        #---------- linear interpolation
        for i in range(len(table) - 1):

            swr1, ang1 = table[i]
            swr2, ang2 = table[i + 1]

            if swr1 <= swr <= swr2:

                ratio = (
                    (swr - swr1)
                    /
                    (swr2 - swr1)
                )

                return ang1 + (
                    (ang2 - ang1) * ratio
                )

        return 60.0

    #---------- meter update
    def update_meter(self):
    
        if self.rig is None:
            return

        #---------- PTT読み出し
        ptt_raw = self.rig.get_ptt()

        #---------- PTT先読み
        ptt = (
            ptt_raw != 0
        )

        if ptt:

            self.off_count = 0
            self.is_transmitting = True

        else:

            self.off_count += 1

            if self.off_count >= 2:

                self.is_transmitting = False

        #---------- RX meter
        strength = self.rig.get_strength()

        #---------- TX meter default
        rfpower = 0.0
        alc = 0.0
        swr = 0.0

        #---------- TX時のみ読む
        if self.is_transmitting:

            rfpower = self.rig.get_rfpower()
            alc = self.rig.get_alc()
            swr = self.rig.get_swr()

        #---------- 周波数更新間引き
        if not hasattr(
            self,
            "freq_counter"
        ):

            self.freq_counter = 0

        self.freq_counter += 1

        if self.freq_counter >= 3:
        
            self.freq_counter = 0
            freq = self.rig.get_freq()

            #---------- 通信確認
            if freq <= 0:

                self.freq_error_count += 1

                logger.warning(
                    f"⚠️ freq read error "
                    f"({self.freq_error_count}/3)"
                )

            else:

                self.freq_error_count = 0

                self.vfo = self.format_freq(
                    freq
                )

            #---------- 3回連続失敗
            if (
                self.freq_error_count >= 3
                and not self.setup_launched
            ):

                self.setup_launched = True

                logger.warning(
                    "❌ Rig communication lost"
                )

                self.launch_setup()
                return

        if OPERATING_MODE == "Debug":
            logger.info(
                f"SIG={strength:.3f}, "
                f"PO={rfpower:.3f}, "
                f"ALC={alc:.3f}, "
                f"SWR={swr:.3f}, "
                f"PTT={self.is_transmitting}, "
                f"VFO={self.vfo}, "
            )

        #---------- Power meter
        if RF_REFERENCE > 0:
            ratio = rfpower / RF_REFERENCE

        else:
            ratio = 0.0

        # RF_REFERENCEを25%位置へ合わせる
        ratio *= 0.25
        ratio = max(
            0.0,
            min(ratio, 1.0)
        )

        self.power_level = (
            ratio * 36.0
        ) - 18.0

        #---------- RX mode
        if not self.is_transmitting:

            sig_norm = (
                self.normalize_strength(
                    strength
                )
            )

            self.signal_strength = (
                (sig_norm * 40.0) - 20.0
            )

            self.swr_level = -20.0
            self.alc_level = -20.0

        #---------- TX mode
        else:

            self.signal_strength = -20.0

            #---------- SWR
            target_angle = self.swr_to_angle(swr)

            #---------- damping
            self.swr_angle += (
                target_angle - self.swr_angle
            ) * 0.25

            self.swr_level = self.swr_angle

            #---------- ALC
            if ALC_REFERENCE > 0:

                ratio = alc / ALC_REFERENCE

            else:

                ratio = 0.0

            # 基準値を55%位置にする(toy_meterの針の位置)
            ratio *= (0.55 / 1.00)

            ratio = max(0.0, min(ratio, 1.0))

            self.alc_level = (
                ratio * 40.0
            ) - 20.0

        #---------- clock
        now_local = (
            QDateTime.currentDateTime()
        )

        self.local_time = (
            now_local.toString(
                "hh:mm:ss"
            )
        )

        self.utc_time = (
            now_local.toUTC().toString(
                "hh:mm:ss"
            )
        )

        self.repaint()

        #---------- Meter Status更新（2回に1回）
        if OPERATING_MODE != "Normal":
        
            self.status_counter += 1

            if self.status_counter >= 2:

                self.status_counter = 0
    
                self.sig_raw = self.rig.command("l STRENGTH")
                self.swr_raw = self.rig.command("l SWR")
                self.po_raw  = self.rig.command("l RFPOWER_METER")
                self.alc_raw = self.rig.command("l ALC")

    #---------- Paint Event

    def paintEvent(self, event):

        #-------------------------------------------------
        # 二重起動などで初期化がキャンセルされた場合
        #-------------------------------------------------
        if not hasattr(self, "meter_image"):
            return

        painter = QPainter(self)

        painter.drawPixmap(
            0,
            0,
            self.meter_image
        )

        self.draw_needle(painter)

        self.draw_swr_needle(painter)

        self.draw_alc_needle(painter)

        #---------- PO scale draw
        self.draw_po_scale(painter)

        self.draw_digital_meter(
            painter
        )
    
    #---------- SIG / PO meter
    def draw_needle(
        self,
        painter
    ):

        painter.save()

        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing
        )

        pen_color = (
            "yellow"
            if self.is_transmitting
            else "red"
        )

        pen = QPen(
            QColor(pen_color),
            3
        )

        painter.translate(160, 400)

        painter.rotate(

            self.power_level
            if self.is_transmitting
            else self.signal_strength
        )

        painter.setPen(pen)

        painter.drawLine(
            0,
            -300,
            0,
            -390
        )

        painter.restore()

    #---------- SWR meter
    def draw_swr_needle(
        self,
        painter
    ):

        painter.save()

        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing
        )

        pen = QPen(
            QColor("red"),
            3
        )

        painter.translate(160, 520)

        painter.rotate(
            self.swr_level
        )

        painter.setPen(pen)

        painter.drawLine(
            0,
            -300,
            0,
            -390
        )

        painter.restore()

    #---------- ALC meter
    def draw_alc_needle(
        self,
        painter
    ):

        painter.save()

        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing
        )

        pen = QPen(
            QColor("lightblue"),
            3
        )

        painter.translate(160, 640)

        painter.rotate(
            self.alc_level
        )

        painter.setPen(pen)

        painter.drawLine(
            0,
            -300,
            0,
            -390
        )

        painter.restore()

    #---------- PO Scale Draw
    def draw_po_scale(
        self,
        painter
    ):

        painter.save()

        painter.setPen(
            QColor("white")
        )

        font = QFont()

        if sys.platform == "darwin":

            font.setPointSize(20)

        elif sys.platform == "win32":

            font.setPointSize(18)

        else:

            font.setPointSize(16)

        painter.setFont(font)

        #---------- scale draw
        for value, x, y in self.po_meter_scale:

            if value >= 10:
                # 10W以上：整数に四捨五入
                text = str(int(value + 0.5))

            else:
                # 10W未満：小数1桁に四捨五入
                text = f"{value:.1f}"

            painter.drawText(
                x,
                y,
                text
            )
        painter.restore()
    
    #---------- Digital Meter
    def draw_digital_meter(
        self,
        painter
    ):

        # ----- STATUS
        if OPERATING_MODE != "Normal":
            font = QFont()

            if sys.platform == "darwin":
                font.setPointSize(14)
            elif sys.platform == "win32":
                font.setPointSize(12)
            else:
                font.setPointSize(10)

            painter.setFont(font)

            y_label = 365
            y_value = 380

            # SIG
            painter.setPen(self.meter_color(self.sig_raw))
            painter.drawText(85, y_label, "SIG:")
            painter.drawText(90, y_value, self.meter_value(self.sig_raw, digits=0))

            # SWR
            painter.setPen(self.meter_color(self.swr_raw))
            painter.drawText(140, y_label, "SWR:")
            painter.drawText(145, y_value, self.meter_value(self.swr_raw))

            # PO
            painter.setPen(self.meter_color(self.po_raw))
            painter.drawText(195, y_label, "PO:")
            painter.drawText(200, y_value, self.meter_value(self.po_raw))

            # ALC
            painter.setPen(self.meter_color(self.alc_raw))
            painter.drawText(245, y_label, "ALC:")
            painter.drawText(250, y_value, self.meter_value(self.alc_raw))

            painter.setPen(QColor("white"))

        else:
            painter.setPen(QColor("white"))

    #----- Digital Meter
        font = QFont()

        if sys.platform == "darwin":

            font.setPointSize(24)

        elif sys.platform == "win32":

            font.setPointSize(20)

        else:

            font.setPointSize(18)

        painter.setFont(font)
        
        #----- VFO
        painter.drawText(80, 410, f"{self.vfo}")

        #----- TIME
        painter.drawText(80, 435, f"{self.utc_time} / "f"{self.local_time}")

        painter.setPen(QColor("white"))

        font = QFont()

        if sys.platform == "darwin":

            font.setPointSize(10)

        elif sys.platform == "win32":

            font.setPointSize(8)

        else:

            font.setPointSize(6)

        painter.setFont(font)
        
        painter.drawText(13, 458, f"{FNC1_label}")
        painter.drawText(76, 458, f"{FNC2_label}")
        painter.drawText(138, 458, f"{FNC3_label}")
        painter.drawText(200, 458, f"{FNC4_label}")

    #--------- Meter Staus Read
    def meter_color(self, raw):
        if raw in (None, "", "RPRT -1"):
            return QColor("orange")
        return QColor("green")
    
    #---------- Mouse Press
    def mousePressEvent(
        self,
        event: QMouseEvent
    ):

        raw_x = event.position().x()
        raw_y = event.position().y()
        screen_x, screen_y = raw_x, raw_y

        self.handle_screen_touch(
            screen_x,
            screen_y
        )

    #---------- Touch Handler
    def handle_screen_touch(
        self,
        screen_x,
        screen_y
    ):

        #---------- Exit (S)
        if (
            0 <= screen_x <= 15
            and
            25 <= screen_y <= 40
        ):

            logger.info("Exit touched")

            QApplication.instance().quit()
            return

        #---------- Config (JP1RXQ)
        if 265 <= screen_x <= 320 and 450 <= screen_y <= 480:
        
            self.launch_setup()
            return

        #---------- Auto Tune (W)
        elif (
            280 <= screen_x <= 320
            and
            75 <= screen_y <= 105
        ):

            try:

                self.rig.start_tune()

            except Exception as e:

                logger.error(
                    f"Auto-Tune send failed: {e}"
                )

            time.sleep(0.05)
            
        #---------- ALC Calibration
        elif (
            OPERATING_MODE != "Normal"
            and
            245 <= screen_x <= 285
            and
            365 <= screen_y <= 385
        ):
            self.calibrate_alc()
            
        #---------- RF Calibration
        elif (
            OPERATING_MODE != "Normal"
            and
            195 <= screen_x <= 235
            and
            365 <= screen_y <= 385
        ):

            self.calibrate_rf()
    
        #---------- FNC-1
        elif (
            10 <= screen_x <= 65
            and
            450 <= screen_y <= 480
        ):

            if FNC1_param:

                try:

                    self.rig.send_raw_cat(
                        FNC1_param
                    )

                except Exception as e:

                    logger.error(
                        f"FNC1 failed: {e}"
                    )

                time.sleep(0.05)

        #---------- FNC-2
        elif (
            70 <= screen_x <= 125
            and
            450 <= screen_y <= 480
        ):

            if FNC2_param:

                try:

                    self.rig.send_raw_cat(
                        FNC2_param
                    )

                except Exception as e:

                    logger.error(
                        f"FNC2 failed: {e}"
                    )

                time.sleep(0.05)

        #---------- FNC-3
        elif (
            135 <= screen_x <= 190
            and
            450 <= screen_y <= 480
        ):

            if FNC3_param:

                try:

                    self.rig.send_raw_cat(
                        FNC3_param
                    )

                except Exception as e:

                    logger.error(
                        f"FNC3 failed: {e}"
                    )

                time.sleep(0.05)

        #---------- FNC-4
        elif (
            200 <= screen_x <= 255
            and
            450 <= screen_y <= 480
        ):

            if FNC4_param:

                try:

                    self.rig.send_raw_cat(
                        FNC4_param
                    )

                except Exception as e:

                    logger.error(
                        f"FNC4 failed: {e}"
                    )

                time.sleep(0.05)

    #---------- get ALC data
    def calibrate_alc(self):

        if not self.is_transmitting:
            return

        alc = self.rig.get_alc()

        if alc <= 0:
            return

        save_alc_reference(alc)

    #---------- get RF data
    def calibrate_rf(self):

        if not self.is_transmitting:
            return

        rf = self.rig.get_rfpower()

        if rf <= 0:
            return

        save_rf_reference(rf)

    #---------- Setup & close
    def launch_setup(self):

        logger.info("Setup requested")

        #---------- メーター更新停止

        if hasattr(self, "timer"):
            self.timer.stop()

        self.setUpdatesEnabled(False)

        #-------------------------------------------------
        # Setup Dialog
        #-------------------------------------------------

        dlg = SetupDialog(self)

        result = dlg.exec()

        self.setUpdatesEnabled(True)

        #-------------------------------------------------
        # OK
        #-------------------------------------------------

        if result:

            #---------------------------------------------
            # Serial Port
            #---------------------------------------------

            original_serial = (
                dlg.original_serial_port
            )

            new_serial = (
                dlg.serial_combo.currentText()
            )

            logger.info(
                f"Setup original SERIAL_PORT="
                f"{original_serial}"
            )

            logger.info(
                f"Setup new SERIAL_PORT="
                f"{new_serial}"
            )

            if original_serial != new_serial:

                logger.info(
                    "⚠️ SERIAL_PORT changed"
                )

            else:

                logger.info(
                    "✅ SERIAL_PORT unchanged"
                )

            #-------------------------------------------------
            # 全設定の変更確認
            #-------------------------------------------------

            current_config_text = (
                dlg.build_config_text()
            )

            config_changed = (
                current_config_text
                != dlg.original_config_text
            )

            #-------------------------------------------------
            # 設定変更あり
            #-------------------------------------------------

            if config_changed:

                logger.info(
                    "⚠️ Configuration changed"
                )

                #---------------------------------------------
                # rigctld停止
                #---------------------------------------------

                stop_rigctld(
                    self.rigctld_proc
                )

                #---------------------------------------------
                # ToyMeter再起動
                #---------------------------------------------

                logger.info(
                    "🔄 Restarting ToyMeter"
                )

                os.execv(
                    sys.executable,
                    [
                        sys.executable,
                        "toy_meter.py"
                    ]
                )

            #-------------------------------------------------
            # 設定変更なし
            #-------------------------------------------------

            else:

                logger.info(
                    "▶️ Continue ToyMeter"
                )

                self.freq_error_count = 0
                self.setup_launched = False
                self.timer.start(
                    int(SCAN_SP * 1000)
                )

        #-------------------------------------------------
        # Cancel
        #-------------------------------------------------

        else:

            logger.info(
                "Setup cancelled"
            )

            self.freq_error_count = 0
            self.setup_launched = False
            self.timer.start(
                int(SCAN_SP * 1000)
            )
            
    #---------- close event
    def closeEvent(self, event):
        logger.info("closing application...")

        #---------- Window Position保存
        config_path = os.path.join(
            BASE_DIR,
            "toy_meter.conf"
        )

        config = load_config()

        geometry = self.frameGeometry()
        config["WINDOW_X"] = str(geometry.x())
        config["WINDOW_Y"] = str(geometry.y())

        with open(
            config_path,
            "w",
            encoding="utf-8"
        ) as f:
            for key, value in config.items():
                f.write(f"{key}={value}\n")

        #---------- タイマー停止
        if hasattr(self, "timer"):
            self.timer.stop()

        #---------- USB時のみ停止
        if CONNECTION == "USB":
            logger.info("🛑 rigctld stopped. call from USB")
            stop_rigctld(
                self.rigctld_proc
            )

        event.accept()
    
    #---------- Meter Value Format
    def meter_value(self, value, digits=2):

        try:
            return f"{float(value):.{digits}f}"

        except (ValueError, TypeError):

            if isinstance(value, str) and value.startswith("RPRT"):
                return "N/A"

            return "---"

    #--------- Meter refresh
    def full_refresh(self):
        self.repaint()

    #--------- NET RECONNECTION
    def retry_net_connection(self):

        if CONNECTION != "NET":
            return

        if self.rig is not None:

            if self.net_retry_timer is not None:
                self.net_retry_timer.stop()

            self.net_retry_count = 0

            return

        #-------------------------------------------------
        # retry count
        #-------------------------------------------------

        self.net_retry_count += 1

        logger.info(
            f"🔄 NET connection retry "
            f"{RIGCTLD_HOST}:{RIGCTLD_PORT} "
            f"({self.net_retry_count}/3)"
        )

        try:

            self.rig = HamlibRigTCP(
                host=RIGCTLD_HOST,
                port=RIGCTLD_PORT
            )

            logger.info(
                "✅ NET rigctld connected"
            )

            #---------- 接続成功
            if self.net_retry_timer is not None:
                self.net_retry_timer.stop()

            self.net_retry_count = 0

        except Exception as e:

            self.rig = None

            logger.info(
                f"⏳ NET rigctld not ready: {e}"
            )

            #-------------------------------------------------
            # 3回失敗
            #-------------------------------------------------

            if self.net_retry_count >= 3:

                logger.warning(
                    "❌ NET connection failed 3 times"
                )

                if self.net_retry_timer is not None:
                    self.net_retry_timer.stop()

                self.net_retry_count = 0

                #---------- Setupを開く
                self.launch_setup()

# =====================================
# main
# =====================================
def main():

    app = QApplication(sys.argv)

    window = SignalPowerMeter()

    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":

    main()
