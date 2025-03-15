import sys, os, json, re, subprocess
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QPropertyAnimation, QEasingCurve

CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".steam_simple_config.json")
STEAM_CONFIG_PATH = r"C:\Program Files (x86)\Steam\config\loginusers.vdf"

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)

def scan_games(steam_apps_path):
    games = []
    if not os.path.isdir(steam_apps_path):
        return games
    for game_folder in os.listdir(steam_apps_path):
        full_path = os.path.join(steam_apps_path, game_folder)
        if os.path.isdir(full_path):
            exe_path = None
            for root, dirs, files in os.walk(full_path):
                for file in files:
                    if file.lower().endswith(".exe"):
                        exe_path = os.path.join(root, file)
                        break
                if exe_path:
                    break
            if exe_path:
                update_available = os.path.exists(os.path.join(full_path, "update.flag"))
                games.append({
                    "name": game_folder,
                    "exe": exe_path,
                    "update": update_available
                })
    return games

def is_steam_running():
    try:
        output = subprocess.check_output("tasklist", shell=True, universal_newlines=True)
        return re.search(r"(?i)\bSteam\.exe\b", output) is not None
    except Exception as e:
        print("Error checking Steam process:", e)
        return False

def launch_steam(account):
    if is_steam_running():
        print("Steam is already running.")
        return
    steam_path = r"C:\Program Files (x86)\Steam\Steam.exe"
    if os.path.exists(steam_path):
        try:
            subprocess.Popen(
                [steam_path, '-login', account],
                shell=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception as e:
            print("Error launching Steam:", e)
    else:
        print("Steam executable not found at default path.")

def parse_loginusers_vdf(filepath):
    profiles = []
    current_user = {}
    in_user_block = False
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if re.match(r'^"\d{17}"$', line):
                    if current_user:
                        profiles.append(current_user)
                    current_user = {'SteamID': line.strip('"')}
                    in_user_block = True
                elif in_user_block and '"' in line:
                    parts = re.findall(r'"([^"]+)"', line)
                    if len(parts) >= 2:
                        key, value = parts[0], parts[1]
                        if key == "AccountName":
                            current_user["AccountName"] = value
                        elif key == "PersonaName":
                            current_user["PersonaName"] = value
                elif line == '}':
                    in_user_block = False
            if current_user:
                profiles.append(current_user)
    except Exception as e:
        print("Error parsing loginusers.vdf:", e)
    return profiles

def get_steam_profiles():
    if os.path.exists(STEAM_CONFIG_PATH):
        profiles = parse_loginusers_vdf(STEAM_CONFIG_PATH)
        if profiles:
            return sorted(profiles, key=lambda x: x.get("PersonaName", "").lower())
    return [{"AccountName": "Default", "PersonaName": "Default"}]

class AnimatedStackedWidget(QtWidgets.QStackedWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.animation_duration = 400

    def slide_in(self, direction):
        current_index = self.currentIndex()
        next_index = current_index + 1 if direction == "left" else current_index - 1
        if next_index < 0 or next_index >= self.count():
            return
        current_widget = self.widget(current_index)
        next_widget = self.widget(next_index)
        offset = QtCore.QPoint(self.width() if direction == "left" else -self.width(), 0)
        next_widget.move(current_widget.pos() - offset)
        next_widget.show()
        next_widget.raise_()
        anim = QPropertyAnimation(next_widget, b"pos")
        anim.setDuration(self.animation_duration)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.setStartValue(next_widget.pos())
        anim.setEndValue(current_widget.pos())
        self.setCurrentIndex(next_index)
        anim.start()

class ProfileCard(QtWidgets.QFrame):
    clicked = QtCore.pyqtSignal(dict)
    
    def __init__(self, profile, parent=None):
        super().__init__(parent)
        self.profile = profile
        self.setup_ui()
    
    def setup_ui(self):
        self.setFixedSize(250, 120)
        self.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1e2a38, stop:1 #3a4b5c);
                border: 2px solid #66c0f4;
                border-radius: 10px;
            }
            QLabel {
                color: #ffffff;
            }
        """)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setAlignment(QtCore.Qt.AlignCenter)
        self.lblPersona = QtWidgets.QLabel(self.profile.get("PersonaName", "Unknown"))
        self.lblPersona.setStyleSheet("font-size: 20px; font-weight: bold;")
        self.lblAccount = QtWidgets.QLabel(f"Account: {self.profile.get('AccountName', 'N/A')}")
        self.lblAccount.setStyleSheet("font-size: 16px; color: #66c0f4;")
        layout.addWidget(self.lblPersona)
        layout.addWidget(self.lblAccount)
    
    def mousePressEvent(self, event):
        self.clicked.emit(self.profile)

class ProfileSelectionPage(QtWidgets.QWidget):
    profile_selected = QtCore.pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(30, 30, 30, 30)
        header = QtWidgets.QLabel("Select Your Steam Profile")
        header.setAlignment(QtCore.Qt.AlignCenter)
        header.setStyleSheet("font-size: 32px; font-weight: bold; color: #c6d4df;")
        main_layout.addWidget(header)
        
        # Utilisation d'un scroll area pour contenir les cartes
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        container = QtWidgets.QWidget()
        grid = QtWidgets.QGridLayout(container)
        grid.setSpacing(20)
        
        profiles = get_steam_profiles()
        col_count = 3
        row = 0
        col = 0
        for profile in profiles:
            card = ProfileCard(profile)
            card.clicked.connect(self.on_card_clicked)
            grid.addWidget(card, row, col)
            col += 1
            if col >= col_count:
                col = 0
                row += 1
        
        scroll.setWidget(container)
        main_layout.addWidget(scroll)
        
        self.error_label = QtWidgets.QLabel("")
        self.error_label.setStyleSheet("color: #ff5555; font-size: 16px;")
        self.error_label.setAlignment(QtCore.Qt.AlignCenter)
        main_layout.addWidget(self.error_label)
    
    def on_card_clicked(self, profile):
        if profile.get("AccountName"):
            self.profile_selected.emit(profile)
        else:
            self.error_label.setText("Invalid profile configuration")

class SetupPage(QtWidgets.QWidget):
    configuration_done = QtCore.pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(50, 50, 50, 50)
        header = QtWidgets.QLabel("Configure Steam Path")
        header.setAlignment(QtCore.Qt.AlignCenter)
        header.setStyleSheet("font-size: 28px; font-weight: bold; color: #c6d4df;")
        layout.addWidget(header)
        
        self.path_edit = QtWidgets.QLineEdit()
        self.path_edit.setPlaceholderText("Enter path to steamapps/common...")
        self.path_edit.setStyleSheet("font-size: 16px; padding: 10px; background-color: #2a475e; border: 1px solid #66c0f4; color: #c6d4df;")
        
        browse_btn = QtWidgets.QPushButton("Browse Folder")
        browse_btn.clicked.connect(self.browse_folder)
        browse_btn.setStyleSheet("font-size: 16px; padding: 10px; background-color: #2a475e; border: 1px solid #66c0f4; color: #ffffff;")
        
        confirm_btn = QtWidgets.QPushButton("Save Configuration")
        confirm_btn.clicked.connect(self.confirm_path)
        confirm_btn.setStyleSheet("font-size: 16px; padding: 10px; background-color: #1b2838; border: 1px solid #66c0f4; color: #ffffff;")
        
        layout.addWidget(self.path_edit)
        layout.addWidget(browse_btn)
        layout.addSpacing(20)
        layout.addWidget(confirm_btn)
    
    def browse_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select SteamApps/common Folder")
        if folder:
            self.path_edit.setText(folder)
    
    def confirm_path(self):
        path = self.path_edit.text().strip()
        if os.path.isdir(path):
            self.configuration_done.emit(path)
        else:
            QtWidgets.QMessageBox.warning(self, "Error", "Please select a valid directory")

class HomePage(QtWidgets.QWidget):
    game_selected = QtCore.pyqtSignal(dict)
    
    def __init__(self, steam_apps_path, account, parent=None):
        super().__init__(parent)
        self.steam_apps_path = steam_apps_path
        self.account = account
        self.all_games = scan_games(steam_apps_path)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        header = QtWidgets.QLabel(f"Welcome, {self.account['PersonaName']}")
        header.setStyleSheet("font-size: 24px; color: #c6d4df;")
        header.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(header)
        self.search_bar = QtWidgets.QLineEdit()
        self.search_bar.setPlaceholderText("Search games...")
        self.search_bar.setStyleSheet("font-size: 16px; padding: 8px; background-color: #2a475e; border: 1px solid #66c0f4; color: #c6d4df;")
        self.search_bar.textChanged.connect(self.filter_games)
        layout.addWidget(self.search_bar)
        self.games_layout = QtWidgets.QGridLayout()
        self.load_games()
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        content = QtWidgets.QWidget()
        content.setLayout(self.games_layout)
        scroll.setWidget(content)
        layout.addWidget(scroll)
    
    def load_games(self, games_list=None):
        if games_list is None:
            games_list = self.all_games
        for i in reversed(range(self.games_layout.count())):
            widget = self.games_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        row, col = 0, 0
        for game in games_list:
            widget = GameWidget(game)
            widget.play_clicked.connect(self.game_selected.emit)
            self.games_layout.addWidget(widget, row, col)
            col += 1
            if col > 2:
                col = 0
                row += 1
    
    def filter_games(self, text):
        text = text.lower().strip()
        filtered = [g for g in self.all_games if text in g["name"].lower()] if text else self.all_games
        self.load_games(filtered)

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Steam Simple")
        self.resize(1280, 720)
        self.stack = AnimatedStackedWidget()
        self.setCentralWidget(self.stack)
        self.current_profile = None
        self.steam_apps_path = None
        if is_steam_running():
            self.current_profile = get_steam_profiles()[0]
            config = load_config()
            if 'steam_apps_path' in config and os.path.isdir(config['steam_apps_path']):
                self.show_home(config['steam_apps_path'])
            else:
                self.show_setup()
        else:
            self.show_profile_selection()
    
    def show_profile_selection(self):
        self.profile_page = ProfileSelectionPage()
        self.profile_page.profile_selected.connect(self.on_profile_selected)
        self.stack.addWidget(self.profile_page)
        self.stack.setCurrentIndex(0)
    
    def on_profile_selected(self, profile):
        self.current_profile = profile
        launch_steam(profile['AccountName'])
        config = load_config()
        if 'steam_apps_path' in config and os.path.isdir(config['steam_apps_path']):
            self.show_home(config['steam_apps_path'])
        else:
            self.show_setup()
    
    def show_setup(self):
        self.setup_page = SetupPage()
        self.setup_page.configuration_done.connect(self.on_configuration_done)
        self.stack.addWidget(self.setup_page)
        self.stack.slide_in("left")
    
    def on_configuration_done(self, path):
        save_config({'steam_apps_path': path})
        self.steam_apps_path = path
        self.show_home(path)
    
    def show_home(self, path):
        self.home_page = HomePage(path, self.current_profile)
        self.home_page.game_selected.connect(self.show_game_page)
        self.stack.addWidget(self.home_page)
        self.stack.slide_in("left")
    
    def show_game_page(self, game_info):
        if hasattr(self, 'game_page') and self.game_page:
            self.stack.removeWidget(self.game_page)
            self.game_page.deleteLater()
        self.game_page = GamePage(game_info, self.current_profile)
        self.game_page.back_to_home.connect(self.on_game_page_back)
        self.stack.addWidget(self.game_page)
        self.stack.slide_in("left")
    
    def on_game_page_back(self):
        self.stack.slide_in("right")
        if hasattr(self, 'game_page') and self.game_page:
            self.stack.removeWidget(self.game_page)
            self.game_page.deleteLater()
            self.game_page = None

class GameWidget(QtWidgets.QFrame):
    play_clicked = QtCore.pyqtSignal(dict)
    
    def __init__(self, game_info, parent=None):
        super().__init__(parent)
        self.game_info = game_info
        self.setup_ui()
        self.setFixedSize(300, 150)
        
    def setup_ui(self):
        self.setStyleSheet("""
            GameWidget {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #2a475e, stop:1 #171a21);
                border: 2px solid #66c0f4;
                border-radius: 8px;
            }
        """)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        name_label = QtWidgets.QLabel(self.game_info["name"])
        name_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #c6d4df;")
        name_label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(name_label)
        if self.game_info.get("update"):
            update_icon = QtWidgets.QLabel()
            update_icon.setPixmap(QtGui.QPixmap(":/icons/update.png").scaled(24, 24))
            update_icon.setAlignment(QtCore.Qt.AlignCenter)
            layout.addWidget(update_icon)
        play_btn = QtWidgets.QPushButton("Launch")
        play_btn.setStyleSheet("""
            QPushButton {
                background-color: #2a475e;
                color: #ffffff;
                border: 1px solid #66c0f4;
                border-radius: 4px;
                padding: 8px;
            }
            QPushButton:hover {
                background-color: #3b5a70;
            }
        """)
        play_btn.clicked.connect(lambda: self.play_clicked.emit(self.game_info))
        layout.addWidget(play_btn)

    def enterEvent(self, event):
        self.animate(True)

    def leaveEvent(self, event):
        self.animate(False)

    def animate(self, hover):
        anim = QPropertyAnimation(self, b"geometry")
        anim.setDuration(200)
        anim.setEasingCurve(QEasingCurve.OutQuad)
        curr = self.geometry()
        if hover:
            anim.setEndValue(QtCore.QRect(curr.x()-5, curr.y()-5, curr.width()+10, curr.height()+10))
        else:
            anim.setEndValue(curr)
        anim.start()

class GamePage(QtWidgets.QWidget):
    back_to_home = QtCore.pyqtSignal()
    
    def __init__(self, game_info, account, parent=None):
        super().__init__(parent)
        self.game_info = game_info
        self.account = account
        self.setup_ui()
    
    def setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        back_btn = QtWidgets.QPushButton("← Back")
        back_btn.setStyleSheet("font-size: 16px; color: #c6d4df;")
        back_btn.clicked.connect(self.back_to_home.emit)
        layout.addWidget(back_btn)
        content = QtWidgets.QVBoxLayout()
        content.setAlignment(QtCore.Qt.AlignCenter)
        name_label = QtWidgets.QLabel(self.game_info["name"])
        name_label.setStyleSheet("font-size: 32px; font-weight: bold; color: #c6d4df;")
        content.addWidget(name_label)
        params_layout = QtWidgets.QVBoxLayout()
        params_layout.addWidget(QtWidgets.QLabel("Launch Options:"))
        self.params_edit = QtWidgets.QLineEdit()
        self.params_edit.setPlaceholderText("Enter additional parameters...")
        self.params_edit.setFixedSize(400, 30)
        params_layout.addWidget(self.params_edit)
        content.addLayout(params_layout)
        advanced_group = QtWidgets.QGroupBox("Advanced Options")
        advanced_layout = QtWidgets.QVBoxLayout(advanced_group)
        self.chk_no_overlay = QtWidgets.QCheckBox("Disable Steam Overlay (-nooverlay)")
        self.chk_windowed = QtWidgets.QCheckBox("Windowed Mode (-windowed)")
        self.chk_high = QtWidgets.QCheckBox("High Performance Mode (-high)")
        self.chk_lowgfx = QtWidgets.QCheckBox("Low Graphics Mode (-lowgfx)")
        for chk in (self.chk_no_overlay, self.chk_windowed, self.chk_high, self.chk_lowgfx):
            chk.setStyleSheet("color: #c6d4df; font-size: 14px;")
            advanced_layout.addWidget(chk)
        content.addWidget(advanced_group)
        launch_btn = QtWidgets.QPushButton("Start Game")
        launch_btn.setFixedSize(200, 40)
        launch_btn.clicked.connect(self.launch_game)
        content.addWidget(launch_btn, 0, QtCore.Qt.AlignCenter)
        layout.addLayout(content)
    
    def launch_game(self):
        exe = self.game_info.get("exe")
        if not exe or not os.path.exists(exe):
            QtWidgets.QMessageBox.warning(self, "Error", "Executable not found!")
            return
        params = self.params_edit.text().strip()
        advanced_args = ""
        if self.chk_no_overlay.isChecked():
            advanced_args += " -nooverlay"
        if self.chk_windowed.isChecked():
            advanced_args += " -windowed"
        if self.chk_high.isChecked():
            advanced_args += " -high"
        if self.chk_lowgfx.isChecked():
            advanced_args += " -lowgfx"
        full_params = (params + advanced_args).strip()
        if not full_params:
            try:
                os.startfile(exe)
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", f"Failed to launch game:\n{e}")
        else:
            cmd = f'"{exe}" {full_params}'
            try:
                subprocess.Popen(cmd, shell=True)
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", f"Failed to launch game:\n{e}")

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    app.setStyleSheet("""
        QWidget {
            background-color: #171a21;
            color: #c6d4df;
            font-family: Arial, sans-serif;
            font-size: 14px;
        }
        QPushButton {
            background-color: #2a475e;
            color: #c6d4df;
            border: 1px solid #66c0f4;
            border-radius: 4px;
            padding: 6px 12px;
        }
        QPushButton:hover {
            background-color: #3b5a70;
        }
        QLineEdit {
            background-color: #2a475e;
            border: 1px solid #66c0f4;
            border-radius: 4px;
            color: #c6d4df;
            padding: 4px 8px;
        }
        QScrollArea {
            background-color: #171a21;
            border: none;
        }
        QHeaderView::section {
            background-color: #2a475e;
            color: #ffffff;
        }
    """)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
