#!/usr/bin/env python3

# Toy_Meter Ver 2.0 - rigctld TCP/NET対応版
#
# toy_meter_setup.py
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

import sys, subprocess, shutil, os, logging

from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QWidget,
    QListWidget,
    QStackedWidget,
    QLabel,
    QLineEdit,
    QComboBox,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QGroupBox,
    QRadioButton,
    QScrollArea,
    QTextEdit,
    QTextBrowser,
)

from PyQt6.QtCore import Qt, QUrl, QLocale
from PyQt6.QtGui import QIntValidator, QDoubleValidator, QPixmap
from serial.tools import list_ports
from pathlib import Path

# ==========================================
# Logging
# ==========================================

log_dir = Path.home() / "toy_meter_logs"
log_dir.mkdir(exist_ok=True)

log_file = log_dir / "toy_meter.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# =========================================
# PATH
# =========================================
def resource_path(relative_path):

    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(
            os.path.abspath(__file__)
        )

    return os.path.join(
        base_path,
        relative_path
    )
    
# =========================================
# Config Load
# =========================================
def load_config():

    config = {}

    try:

        with open(
            resource_path("toy_meter.conf"),
            "r",
            encoding="utf-8"
        ) as file:

            for line in file:

                line = line.strip()

                if (
                    not line
                    or line.startswith("#")
                    or "=" not in line
                ):
                    continue

                key, value = line.split(
                    "=",
                    1
                )

                config[key.strip()] = value.strip()

    except FileNotFoundError:

        logger.warning(
            "toy_meter.conf not found"
        )

    return config

# =========================================
# Get Serial Ports
# =========================================
def get_serial_ports():

    ports = []

    for port in list_ports.comports():

        ports.append(port.device)

    return ports
    
# =========================================
# Get Hamlib Rig List
# =========================================
def get_hamlib_rigs():

    rigs = {}

    try:

        rigctl_path = find_rigctl()

        if not rigctl_path:

            logger.warning("rigctl not found")
            return rigs

        logger.info("Loading Hamlib rig list...")

        cmd = [rigctl_path, "-l"]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )

        logger.info(
            f"rigctl stderr:\n"
            f"{result.stderr}"
        )

        lines = result.stdout.splitlines()

        for line in lines:

            line = line.strip()

            if not line:
                continue

            parts = line.split()

            if len(parts) < 3:
                continue

            rig_id = parts[0]
            mfg = parts[1]
            model = parts[2]

            if mfg not in rigs:
                rigs[mfg] = {}

            rigs[mfg][model] = rig_id

    except subprocess.TimeoutExpired as e:

        logger.exception(
            f"TimeoutExpired: {e}"
        )

    except Exception as error:

        logger.exception(
            f"Hamlib read error: {error}"
        )

    logger.info(
        f"Loaded rigs={len(rigs)}"
    )

    return rigs

#---------- rigctl 実行ファイル探索
def find_rigctl():

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

#---------- Rasberry Pi 判定
def is_raspberry_pi():
    try:
        with open(
            "/sys/firmware/devicetree/base/model",
            "r"
        ) as f:
            return "Raspberry Pi" in f.read()
    except:
        return False
        
# =========================================
# Main Window
# =========================================
class SetupDialog(QDialog):

    def __init__(self, parent=None):

        super().__init__(parent)

        # Raspberry Pi判定
        self.is_raspi = is_raspberry_pi()

        self.setWindowTitle(
            "toy_meter Configation"
        )

        # Window Size
        if self.is_raspi:
            self.setFixedSize(320, 480)
            self.setStyleSheet("""
            QWidget {
                font-size: 8pt;
            }
        """)

        else:
            self.resize(800, 640)

        #---------- config load

        self.config = load_config()
        self.rigs = get_hamlib_rigs()

        self.init_ui()
        self.apply_config()

        #=================================================
        # Setupを開いた時点の設定を保存
        #=================================================

        self.original_config_text = (
            self.build_config_text()
        )

        # Serial Portだけ個別に保存
        # ログ表示およびSerial変更判定用

        self.original_serial_port = (
            self.serial_combo.currentText()
        )

        logger.info(
            f"Setup original SERIAL_PORT="
            f"{self.original_serial_port}"
        )

    # =====================================
    # UI
    # =====================================
    def init_ui(self):

        # ---------------------------------
        # Main Layout
        # ---------------------------------
        main_layout = QVBoxLayout()

        if self.is_raspi:

            main_layout.setContentsMargins(
                6, 6, 6, 6
            )

            main_layout.setSpacing(4)

        else:

            main_layout.setContentsMargins(
                12, 12, 12, 12
            )

            main_layout.setSpacing(8)

        # ---------------------------------
        # Center Layout
        # ---------------------------------
        if self.is_raspi:

            # 左メニューなし
            self.pages = QStackedWidget()

            self.pages.addWidget(
                self.create_rig_page()
            )

            main_layout.addWidget(
                self.pages
            )

        else:

            center_layout = QHBoxLayout()

            # ---------------------------------
            # Left Menu
            # ---------------------------------
            self.menu_list = QListWidget()

            self.menu_list.setFixedWidth(140)

            self.menu_list.addItem(
                "Radio Parameters"
            )

            self.menu_list.addItem(
                "About toy_meter"
            )
            
            self.menu_list.addItem(
                "Configuration Diagram"
            )

            self.menu_list.currentRowChanged.connect(
                self.change_page
            )

            center_layout.addWidget(
                self.menu_list
            )

            # ---------------------------------
            # Pages
            # ---------------------------------
            self.pages = QStackedWidget()

            self.pages.addWidget(
                self.create_rig_page()
            )

            self.pages.addWidget(
                self.create_about_page()
            )

            self.pages.addWidget(
                self.create_diagram_page()
            )

            center_layout.addWidget(
                self.pages
            )

            main_layout.addLayout(
                center_layout
            )

        # ---------------------------------
        # Bottom Buttons
        # ---------------------------------
        button_layout = QHBoxLayout()

        button_layout.addStretch()

        self.ok_button = QPushButton("OK")

        self.cancel_button = QPushButton(
            "Cancel"
        )

        self.ok_button.setFixedWidth(120)

        self.cancel_button.setFixedWidth(
            120
        )

        self.cancel_button.clicked.connect(
            self.reject
        )
        
        self.ok_button.clicked.connect(
            self.save_and_close
        )

        button_layout.addWidget(
            self.ok_button
        )

        button_layout.addWidget(
            self.cancel_button
        )

        main_layout.addLayout(
            button_layout
        )

        self.setLayout(main_layout)

        # 初期ページ
        if not self.is_raspi:
            self.menu_list.setCurrentRow(0)

    # =====================================
    # 無線機設定 PAGE
    # =====================================
    def create_rig_page(self):

        page = QWidget()

        layout = QVBoxLayout()

        # ---------------------------------
        # Connection Type
        # ---------------------------------
        conn_group = QGroupBox(
            "Connection Type"
        )

        conn_layout = QHBoxLayout()

        self.usb_radio = QRadioButton(
            "USB Serial"
        )

        self.net_radio = QRadioButton(
            "Network rigctld"
        )

        # default
        self.usb_radio.setChecked(True)

        self.usb_radio.toggled.connect(
            self.update_connection_mode
        )
        self.net_radio.toggled.connect(
            self.update_connection_mode
        )

        conn_layout.addWidget(
            self.usb_radio
        )

        conn_layout.addWidget(
            self.net_radio
        )

        conn_group.setLayout(
            conn_layout
        )

        layout.addWidget(
            conn_group
        )

        # ---------------------------------
        # Rig Group
        # ---------------------------------
        self.rig_group = QGroupBox(
            "Radio Settings"
        )

        rig_grid = QGridLayout()

        # ---------------------------------
        # MFG
        # ---------------------------------
        self.mfg_label = QLabel("MFG")

        rig_grid.addWidget(
            self.mfg_label,
            0, 0
        )

        self.mfg_combo = QComboBox()

        self.mfg_combo.addItems(
            sorted(self.rigs.keys())
        )

        self.mfg_combo.currentTextChanged.connect(
            self.update_models
        )

        rig_grid.addWidget(
            self.mfg_combo,
            0, 1
        )

        # ---------------------------------
        # MODEL
        # ---------------------------------
        self.model_label = QLabel("MODEL")

        rig_grid.addWidget(
            self.model_label,
            1, 0
        )

        self.model_combo = QComboBox()

        rig_grid.addWidget(
            self.model_combo,
            1, 1
        )

        # ---------------------------------
        # RF POWER RANGE
        # ---------------------------------
        rig_grid.addWidget(
            QLabel("RF POWER RANGE"),
            2, 0
        )

        self.rf_power_combo = QComboBox()

        self.rf_power_combo.addItems([
            "5",
            "10",
            "20",
            "50",
            "100",
            "200",
        ])

        rig_grid.addWidget(
            self.rf_power_combo,
            2, 1
        )

        # ---------------------------------
        # OPERATING MODE
        # ---------------------------------
        rig_grid.addWidget(
            QLabel("OPERATING MODE"),
            3, 0
        )

        self.operating_mode_combo = QComboBox()

        self.operating_mode_combo.addItems([
            "Normal",
            "Monitor",
            "Debug",
        ])

        rig_grid.addWidget(
            self.operating_mode_combo,
            3, 1
        )

        # ---------------------------------
        # RF REFERENCE
        # ---------------------------------
        rig_grid.addWidget(
            QLabel("RF REFERENCE"),
            4, 0
        )

        self.rf_reference_edit = QLineEdit()

        rig_grid.addWidget(
            self.rf_reference_edit,
            4, 1
        )

        # ---------------------------------
        # ALC REFERENCE
        # ---------------------------------
        rig_grid.addWidget(
            QLabel("ALC REFERENCE"),
            5, 0
        )

        self.alc_reference_edit = QLineEdit()

        rig_grid.addWidget(
            self.alc_reference_edit,
            5, 1
        )

        # ---------------------------------
        # Validator（共通）
        # ---------------------------------
        validator = QDoubleValidator(
            0.001,
            1000.0,
            3
        )

        validator.setNotation(
            QDoubleValidator.Notation.StandardNotation
        )

        self.rf_reference_edit.setValidator(
            validator
        )

        self.alc_reference_edit.setValidator(
            validator
        )

        # ---------------------------------
        # Layout
        # ---------------------------------
        self.rig_group.setLayout(
            rig_grid
        )

        layout.addWidget(
            self.rig_group
        )
        
        # ---------------------------------
        # Serial Group
        # ---------------------------------
        self.serial_group = QGroupBox(
            "Serial Port Settings"
        )

        grid = QGridLayout()

        # ---------------------------------
        # SERIAL PORT
        # ---------------------------------
        self.serial_label = QLabel(
            "SERIAL PORT"
        )

        grid.addWidget(
            self.serial_label,
            0, 0
        )

        self.serial_combo = QComboBox()

        ports = get_serial_ports()

        if not ports:
            ports = ["No Serial Device"]

        self.serial_combo.addItems(
            ports
        )

        grid.addWidget(
            self.serial_combo,
            0, 1
        )

        # ---------------------------------
        # BAUD RATE
        # ---------------------------------
        self.baud_label = QLabel(
            "BAUD RATE(bps)"
        )

        grid.addWidget(
            self.baud_label,
            1, 0
        )

        self.baud_combo = QComboBox()

        self.baud_combo.addItems([
            "4800",
            "9600",
            "19200",
            "38400",
            "57600",
            "115200",
        ])

        grid.addWidget(
            self.baud_combo,
            1, 1
        )

        # ---------------------------------
        # DATA BITS
        # ---------------------------------
        self.data_bits_label = QLabel(
            "DATA BITS"
        )

        grid.addWidget(
            self.data_bits_label,
            2, 0
        )

        self.data_bits_combo = QComboBox()

        self.data_bits_combo.addItems([
            "7",
            "8",
        ])

        grid.addWidget(
            self.data_bits_combo,
            2, 1
        )

        # ---------------------------------
        # PARITY
        # ---------------------------------
        self.parity_label = QLabel(
            "PARITY"
        )

        grid.addWidget(
            self.parity_label,
            3, 0
        )

        self.parity_combo = QComboBox()

        self.parity_combo.addItems([
            "NONE",
            "EVEN",
            "ODD",
        ])

        grid.addWidget(
            self.parity_combo,
            3, 1
        )

        # ---------------------------------
        # STOP BITS
        # ---------------------------------
        self.stop_bits_label = QLabel(
            "STOP BITS"
        )

        grid.addWidget(
            self.stop_bits_label,
            4, 0
        )

        self.stop_bits_combo = QComboBox()

        self.stop_bits_combo.addItems([
            "1",
            "2",
        ])

        grid.addWidget(
            self.stop_bits_combo,
            4, 1
        )

        # ---------------------------------
        # FLOW CONTROL
        # ---------------------------------
        self.flow_label = QLabel(
            "FLOW CONTROL"
        )

        grid.addWidget(
            self.flow_label,
            5, 0
        )

        self.flow_combo = QComboBox()

        self.flow_combo.addItems([
            "NONE",
            "RTSCTS",
            "XONXOFF",
        ])

        grid.addWidget(
            self.flow_combo,
            5, 1
        )

        # ---------------------------------
        # SCAN SP
        # ---------------------------------
        self.scan_label = QLabel(
            "SCAN SP(sec)"
        )

        grid.addWidget(
            self.scan_label,
            6, 0
        )

        self.scan_combo = QComboBox()

        self.scan_combo.addItems([
            "0.1",
            "0.2",
            "0.3",
            "0.4",
            "0.5",
        ])

        grid.addWidget(
            self.scan_combo,
            6, 1
        )

        # ---------------------------------
        # Layout
        # ---------------------------------
        self.serial_group.setLayout(
            grid
        )

        layout.addWidget(
            self.serial_group
        )

        # ---------------------------------
        # Network Group
        # ---------------------------------
        self.network_group = QGroupBox(
            "Network rigctld"
        )

        net_grid = QGridLayout()

        # ---------------------------------
        # HOST
        # ---------------------------------
        self.host_label = QLabel(
            "HOST"
        )

        net_grid.addWidget(
            self.host_label,
            0, 0
        )

        self.host_edit = QLineEdit()

        self.host_edit.setText(
            "127.0.0.1"
        )

        net_grid.addWidget(
            self.host_edit,
            0, 1
        )

        # ---------------------------------
        # PORT
        # ---------------------------------
        self.port_label = QLabel(
            "PORT"
        )

        net_grid.addWidget(
            self.port_label,
            1, 0
        )

        self.port_edit = QLineEdit()

        self.port_edit.setText(
            "4532"
        )

        net_grid.addWidget(
            self.port_edit,
            1, 1
        )

        # ---------------------------------
        # Layout
        # ---------------------------------
        self.network_group.setLayout(
            net_grid
        )

        layout.addWidget(
            self.network_group
        )
        
        # ---------------------------------
        # Custom Function Group
        # ---------------------------------
        fnc_group = QGroupBox(
            "Custom Functions"
        )

        fnc_grid = QGridLayout()

        # FNC1
        fnc_grid.addWidget(
            QLabel("FNC1"),
            0, 0
        )

        self.fnc1_name = QLineEdit()

        self.fnc1_name.setMaxLength(7)

        self.fnc1_cmd = QLineEdit()

        self.fnc1_cmd.setMaxLength(16)

        fnc_grid.addWidget(
            self.fnc1_name,
            0, 1
        )

        fnc_grid.addWidget(
            self.fnc1_cmd,
            0, 2
        )

        # FNC2
        fnc_grid.addWidget(
            QLabel("FNC2"),
            1, 0
        )

        self.fnc2_name = QLineEdit()

        self.fnc2_name.setMaxLength(7)

        self.fnc2_cmd = QLineEdit()

        self.fnc2_cmd.setMaxLength(16)

        fnc_grid.addWidget(
            self.fnc2_name,
            1, 1
        )

        fnc_grid.addWidget(
            self.fnc2_cmd,
            1, 2
        )

        # FNC3
        fnc_grid.addWidget(
            QLabel("FNC3"),
            2, 0
        )

        self.fnc3_name = QLineEdit()

        self.fnc3_name.setMaxLength(7)

        self.fnc3_cmd = QLineEdit()

        self.fnc3_cmd.setMaxLength(16)

        fnc_grid.addWidget(
            self.fnc3_name,
            2, 1
        )

        fnc_grid.addWidget(
            self.fnc3_cmd,
            2, 2
        )

        # FNC4
        fnc_grid.addWidget(
            QLabel("FNC4"),
            3, 0
        )

        self.fnc4_name = QLineEdit()

        self.fnc4_name.setMaxLength(7)

        self.fnc4_cmd = QLineEdit()

        self.fnc4_cmd.setMaxLength(16)

        fnc_grid.addWidget(
            self.fnc4_name,
            3, 1
        )

        fnc_grid.addWidget(
            self.fnc4_cmd,
            3, 2
        )

        fnc_group.setLayout(
            fnc_grid
        )

        layout.addWidget(
            fnc_group
        )

        layout.addStretch()

        page.setLayout(layout)

        scroll = QScrollArea()

        scroll.setWidgetResizable(
            True
        )

        scroll.setWidget(
            page
        )

        return scroll

    # =====================================
    # ABOUT PAGE
    # =====================================
    def create_about_page(self):

        page = QWidget()

        layout = QVBoxLayout()

        text = QTextBrowser()

        #---------- Get system language
        language = QLocale.system().name().split("_")[0]

        #---------- Select About HTML
        about_dir = Path(__file__).parent / "about"

        html_file = (
            about_dir / f"toy_meter_{language}.html"
        )

        #---------- Fallback to English
        if not html_file.exists():
            html_file = (
                about_dir / "toy_meter_en.html"
            )

        text.setSource(
            QUrl.fromLocalFile(str(html_file))
        )

        text.setReadOnly(True)

        text.setOpenExternalLinks(True)

        layout.addWidget(text)

        page.setLayout(layout)

        return page
        
    # =====================================
    # Configuration Diagram PAGE
    # =====================================
    def create_diagram_page(self):

        page = QWidget()

        layout = QVBoxLayout()

        about_dir = Path(__file__).parent / "about"
        image_path = about_dir / "toy_meter_v2.0_diagram.png"

        #---------- 画像表示用 QLabel
        image_label = QLabel()
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        pixmap = QPixmap(str(image_path))

        if not pixmap.isNull():

            #---------- 元画像サイズで表示
            image_label.setPixmap(pixmap)

            #---------- 画像サイズを固定
            image_label.setFixedSize(pixmap.size())

        else:
    
            image_label.setText(
                f"Diagram image not found.\n\n{image_path}"
            )

        #---------- スクロールエリア
        scroll_area = QScrollArea()
        scroll_area.setWidget(image_label)
        scroll_area.setWidgetResizable(False)

        layout.addWidget(scroll_area)

        page.setLayout(layout)

        return page

    # =====================================
    # Apply Config
    # =====================================
    def apply_config(self):

        config = self.config

        # Connection Type
        connection = config.get("CONNECTION", "USB")

        if connection == "NET":
            self.net_radio.setChecked(True)
        else:
            self.usb_radio.setChecked(True)

        self.update_connection_mode()

        # MFG
        self.mfg_combo.setCurrentText(
            config.get(
                "MFG",
                "YAESU"
            )
        )

        # MODEL
        self.model_combo.setCurrentText(
            config.get(
                "MODEL",
                "FTDX10"
            )
        )

        # SERIAL PORT
        self.serial_combo.setCurrentText(
            config.get(
                "SERIAL_PORT",
                ""
            )
        )

        # BAUD RATE
        self.baud_combo.setCurrentText(
            config.get(
                "BAUD_RATE",
                "38400"
            )
        )

        # DATA BITS
        self.data_bits_combo.setCurrentText(
            config.get(
                "DATA_BITS",
                "8"
            )
        )

        # PARITY
        self.parity_combo.setCurrentText(
            config.get(
                "PARITY",
                "NONE"
            )
        )

        # STOP BITS
        self.stop_bits_combo.setCurrentText(
            config.get(
                "STOP_BITS",
                "1"
            )
        )

        # FLOW CONTROL
        self.flow_combo.setCurrentText(
            config.get(
                "FLOW_CONTROL",
                "NONE"
            )
        )

        # RIGCTLD HOST
        self.host_edit.setText(
            config.get(
                "RIGCTLD_HOST",
                "127.0.0.1"
            )
        )

        # RIGCTLD PORT
        self.port_edit.setText(
            config.get(
                "RIGCTLD_PORT",
                "4532"
            )
        )

        # SCAN SP
        self.scan_combo.setCurrentText(
            config.get(
                "SCAN_SP",
                "0.2"
            )
        )

        # RF POWER RANGE
        self.rf_power_combo.setCurrentText(
            config.get(
                "RF_POWER_RANGE",
                "100"
            )
        )

        # OPERATING MODE
        self.operating_mode_combo.setCurrentText(
            config.get(
                "OPERATING_MODE",
                "Normal",
            )
        )

        # RF REFERENCE
        self.rf_reference_edit.setText(
            config.get(
                "RF_REFERENCE",
                "0.25"
            )
        )

        # ALC REFERENCE
        self.alc_reference_edit.setText(
            config.get(
                "ALC_REFERENCE",
                "0.6"
            )
        )

        # FNC1
        self.load_fnc(
            "FNC1",
            self.fnc1_name,
            self.fnc1_cmd
        )

        # FNC2
        self.load_fnc(
            "FNC2",
            self.fnc2_name,
            self.fnc2_cmd
        )

        # FNC3
        self.load_fnc(
            "FNC3",
            self.fnc3_name,
            self.fnc3_cmd
        )

        # FNC4
        self.load_fnc(
            "FNC4",
            self.fnc4_name,
            self.fnc4_cmd
        )

    # =====================================
    # Load FNC
    # =====================================
    def load_fnc(
        self,
        key,
        name_widget,
        cmd_widget
    ):

        value = self.config.get(
            key,
            ""
        )

        if "," in value:

            name, cmd = value.split(
                ",",
                1
            )

            name_widget.setText(name)

            cmd_widget.setText(cmd)

    # =====================================
    # Change Page
    # =====================================
    def change_page(self, index):

        self.pages.setCurrentIndex(index)

    # =====================================
    # Build Config Text
    # =====================================
    def build_config_text(self):

        lines = []

        # =================================
        # USB MODE
        # =================================
        if self.usb_radio.isChecked():

            lines.append(
                "CONNECTION=USB"
            )

            lines.append(
                f"RIGCTLD_HOST={self.host_edit.text()}"
            )

            lines.append(
                f"RIGCTLD_PORT={self.port_edit.text()}"
            )

            lines.append("")

            # MFG
            lines.append(
                f"MFG={self.mfg_combo.currentText()}"
            )

            # MODEL
            lines.append(
                f"MODEL={self.model_combo.currentText()}"
            )

            # RIG MODEL
            mfg = self.mfg_combo.currentText()

            model = self.model_combo.currentText()

            rig_model = self.rigs.get(
                mfg,
                {}
            ).get(
                model,
                "0"
            )

            lines.append(
                f"RIG_MODEL={rig_model}"
            )

            lines.append("")

            # SERIAL
            lines.append(
                f"SERIAL_PORT={self.serial_combo.currentText()}"
            )

            lines.append(
                f"BAUD_RATE={self.baud_combo.currentText()}"
            )

            lines.append(
                f"DATA_BITS={self.data_bits_combo.currentText()}"
            )

            lines.append(
                f"PARITY={self.parity_combo.currentText()}"
            )

            lines.append(
                f"STOP_BITS={self.stop_bits_combo.currentText()}"
            )

            lines.append(
                f"FLOW_CONTROL={self.flow_combo.currentText()}"
            )

        # =================================
        # NET MODE
        # =================================
        else:

            lines.append(
                "CONNECTION=NET"
            )

            lines.append(
                f"RIGCTLD_HOST={self.host_edit.text()}"
            )

            lines.append(
                f"RIGCTLD_PORT={self.port_edit.text()}"
            )

        lines.append("")

        # =================================
        # その他設定
        # =================================
        # SCAN SP
        lines.append(
            f"SCAN_SP={self.scan_combo.currentText()}"
        )

        # RF POWER RANGE
        lines.append(
            f"RF_POWER_RANGE={self.rf_power_combo.currentText()}"
        )

        # OPERATING MODE
        lines.append(
            f"OPERATING_MODE={self.operating_mode_combo.currentText()}"
        )

        # RF REFERENCE
        lines.append(
            f"RF_REFERENCE={self.rf_reference_edit.text()}"
        )

        # ALC REFERENCE
        lines.append(
            f"ALC_REFERENCE={self.alc_reference_edit.text()}"
        )

        lines.append("")
        
        # FNC1
        lines.append(
            f"FNC1={self.fnc1_name.text()},{self.fnc1_cmd.text()}"
        )

        # FNC2
        lines.append(
            f"FNC2={self.fnc2_name.text()},{self.fnc2_cmd.text()}"
        )

        # FNC3
        lines.append(
            f"FNC3={self.fnc3_name.text()},{self.fnc3_cmd.text()}"
        )

        # FNC4
        lines.append(
            f"FNC4={self.fnc4_name.text()},{self.fnc4_cmd.text()}"
        )

        return "\n".join(lines)

    # =====================================
    # Save and Close
    # =====================================
    def save_and_close(self):

        #---------- Connection Type
        connection = self.config.get(
            "CONNECTION",
            "USB"
        )

        #---------- USB Serial check
        if connection == "USB":

            new_serial_port = (
                self.serial_combo.currentText()
            )

            logger.info(
                f"Setup original SERIAL_PORT="
                f"{self.original_serial_port}"
            )

            logger.info(
                f"Setup new SERIAL_PORT="
                f"{new_serial_port}"
            )

            if (
                self.original_serial_port
                == new_serial_port
            ):
                logger.info(
                    "✅ SERIAL_PORT unchanged"
                )
            else:
                logger.info(
                    "⚠️ SERIAL_PORT changed"
                )

        else:

            logger.info(
                "🌐 NETWORK MODE: "
                "SERIAL_PORT check skipped"
            )

        #---------- 設定保存
        config_text = self.build_config_text()

        self.save_config(config_text)

        logger.info("Config Saved")

        #---------- EXPERIMENT
        # execv() はここでは行わない
        self.accept()
        
    # =====================================
    # Save Config
    # =====================================
    def save_config(self, config_text):

        with open(
            resource_path("toy_meter.conf"),
            "w",
            encoding="utf-8"
        ) as file:

            file.write(config_text)

    # =====================================
    # Update Model List
    # =====================================
    def update_models(self):

        mfg = self.mfg_combo.currentText()

        self.model_combo.clear()

        if mfg in self.rigs:

            models = sorted(
                self.rigs[mfg].keys()
            )

            self.model_combo.addItems(
                models
            )

    # =====================================
    # Update Connection Mode
    # =====================================
    def update_connection_mode(self):

        is_net = self.net_radio.isChecked()

        # ---------------------------------
        # Radio Settings
        # ---------------------------------

        self.mfg_label.setVisible(
            not is_net
        )

        self.mfg_combo.setVisible(
            not is_net
        )

        self.model_label.setVisible(
            not is_net
        )

        self.model_combo.setVisible(
            not is_net
        )

        # ---------------------------------
        # Serial Port Settings
        # ---------------------------------

        self.serial_label.setVisible(
            not is_net
        )

        self.serial_combo.setVisible(
            not is_net
        )

        self.baud_label.setVisible(
            not is_net
        )

        self.baud_combo.setVisible(
            not is_net
        )

        self.data_bits_label.setVisible(
            not is_net
        )

        self.data_bits_combo.setVisible(
            not is_net
        )

        self.parity_label.setVisible(
            not is_net
        )

        self.parity_combo.setVisible(
            not is_net
        )

        self.stop_bits_label.setVisible(
            not is_net
        )

        self.stop_bits_combo.setVisible(
            not is_net
        )

        self.flow_label.setVisible(
            not is_net
        )

        self.flow_combo.setVisible(
            not is_net
        )

        # SCAN SP
        self.scan_label.setVisible(
            True
        )

        self.scan_combo.setVisible(
            True
        )

        # ---------------------------------
        # Network rigctld
        # ---------------------------------

        self.network_group.setVisible(
            is_net
        )
 
# =========================================
# Main
# =========================================
if __name__ == "__main__":

    app = QApplication(sys.argv)

    window = SetupDialog()

    window.show()

    sys.exit(app.exec())
