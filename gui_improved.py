# gui_improved.py - 改进版界面
import sys
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *

from doudizhu_core import (
    Card,
    ExpertAIPlayer,
    Difficulty,
    PatternDetector,
    PlayComparator,
    DeckManager,
    CardType
)


class CardButton(QPushButton):
    def __init__(self, card, index):
        super().__init__()
        self.card = card
        self.index = index
        self.selected = False
        self.setFixedSize(65, 85)
        self.update_style()
    
    def update_style(self):
        rank = self.card.rank
        suit = self.card.suit
        
        is_red = suit in ['♥', '♦']
        if rank == 'Joker1':
            is_red = True
        color = "#FF4444" if is_red else "#000000"
        
        if rank == 'Joker1':
            display = "🐱\n小王"
        elif rank == 'Joker2':
            display = "🃏\n大王"
        else:
            display = f"{suit}\n{rank}"
        
        if self.selected:
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: #FFE082;
                    border: 3px solid #FF9800;
                    border-radius: 6px;
                    font-size: 13px;
                    font-weight: bold;
                    color: {color};
                    margin-top: -15px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: white;
                    border: 2px solid #333;
                    border-radius: 6px;
                    font-size: 13px;
                    font-weight: bold;
                    color: {color};
                }}
                QPushButton:hover {{
                    background-color: #f0f0f0;
                    border: 2px solid #FF9800;
                }}
            """)
        self.setText(display)
    
    def toggle_select(self):
        self.selected = not self.selected
        self.update_style()


class CardLabel(QLabel):
    """用于显示出牌区卡牌的标签"""
    def __init__(self, card):
        super().__init__()
        self.card = card
        self.setup_display()
    
    def setup_display(self):
        rank = self.card.rank
        suit = self.card.suit
        
        is_red = suit in ['♥', '♦']
        if rank == 'Joker1':
            is_red = True
        color = "#FF4444" if is_red else "#000000"
        
        if rank == 'Joker1':
            display = "🐱\n小王"
        elif rank == 'Joker2':
            display = "🃏\n大王"
        else:
            display = f"{suit}\n{rank}"
        
        self.setText(display)
        self.setFixedSize(60, 80)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(f"""
            QLabel {{
                background-color: white;
                border: 2px solid #333;
                border-radius: 6px;
                font-size: 12px;
                font-weight: bold;
                color: {color};
            }}
        """)


class AIPanel(QFrame):
    def __init__(self, name, position="top"):
        super().__init__()
        self.name = name
        self.position = position
        self.setFixedWidth(140)
        self.setup_ui()
    
    def setup_ui(self):
        self.setStyleSheet("background-color: #2E7D32; border-radius: 10px;")
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(5)
        
        # 头像和出牌指示器
        avatar_container = QWidget()
        avatar_layout = QVBoxLayout(avatar_container)
        avatar_layout.setSpacing(2)
        
        avatar = QLabel()
        avatar.setFixedSize(50, 50)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setStyleSheet("background-color: #1B5E20; border-radius: 25px; font-size: 28px;")
        avatar.setText("🤖")
        avatar_layout.addWidget(avatar, alignment=Qt.AlignCenter)
        
        name_label = QLabel(self.name)
        name_label.setStyleSheet("color: white; font-size: 13px; font-weight: bold;")
        name_label.setAlignment(Qt.AlignCenter)
        avatar_layout.addWidget(name_label)
        
        # 出牌状态标签（在头像旁边）
        self.action_label = QLabel("")
        self.action_label.setStyleSheet("""
            background-color: #FF9800; 
            color: white; 
            font-size: 10px; 
            font-weight: bold;
            border-radius: 8px;
            padding: 3px 6px;
        """)
        self.action_label.setAlignment(Qt.AlignCenter)
        self.action_label.setWordWrap(True)
        self.action_label.hide()
        avatar_layout.addWidget(self.action_label)
        
        layout.addWidget(avatar_container)
        
        self.stack_label = QLabel()
        self.stack_label.setFixedSize(60, 55)
        self.stack_label.setAlignment(Qt.AlignCenter)
        self.stack_label.setStyleSheet("background-color: #1565C0; border: 2px solid #0D47A1; border-radius: 6px; font-size: 24px;")
        self.stack_label.setText("🃟")
        layout.addWidget(self.stack_label, alignment=Qt.AlignCenter)
        
        self.count_label = QLabel("0 张")
        self.count_label.setStyleSheet("color: #FFD54F; font-size: 14px; font-weight: bold;")
        self.count_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.count_label)
        
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #FF9800; font-size: 10px;")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)
    
    def update_count(self, count):
        self.count_label.setText(f"{count} 张")
        if count == 0:
            self.stack_label.setText("✅")
        elif count <= 3:
            self.stack_label.setText("🃟")
        else:
            self.stack_label.setText("🃟\n🃟")
    
    def set_status(self, text, is_play=True):
        self.status_label.setText(text)
        color = "#4CAF50" if is_play else "#FF9800"
        self.status_label.setStyleSheet(f"color: {color}; font-size: 10px;")
    
    def show_action(self, action_text, is_play=True):
        """显示出牌动作"""
        self.action_label.setText(action_text)
        self.action_label.setStyleSheet(f"""
            background-color: {'#4CAF50' if is_play else '#FF5722'}; 
            color: white; 
            font-size: 10px; 
            font-weight: bold;
            border-radius: 8px;
            padding: 3px 6px;
        """)
        self.action_label.show()
        # 2秒后自动隐藏
        QTimer.singleShot(2000, self.action_label.hide)


class PlayerPanel(QFrame):
    """玩家面板，包含出牌状态显示"""
    def __init__(self):
        super().__init__()
        self.setup_ui()
    
    def setup_ui(self):
        self.setStyleSheet("background-color: transparent;")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 左侧玩家信息
        info_widget = QWidget()
        info_widget.setFixedWidth(100)
        info_layout = QVBoxLayout(info_widget)
        info_layout.setAlignment(Qt.AlignCenter)
        
        avatar = QLabel()
        avatar.setFixedSize(40, 40)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setStyleSheet("background-color: #1B5E20; border-radius: 20px; font-size: 22px;")
        avatar.setText("👤")
        info_layout.addWidget(avatar, alignment=Qt.AlignCenter)
        
        name_label = QLabel("玩家")
        name_label.setStyleSheet("color: white; font-size: 12px; font-weight: bold;")
        name_label.setAlignment(Qt.AlignCenter)
        info_layout.addWidget(name_label)
        
        # 玩家出牌状态标签
        self.action_label = QLabel("")
        self.action_label.setStyleSheet("""
            background-color: #4CAF50; 
            color: white; 
            font-size: 10px; 
            font-weight: bold;
            border-radius: 8px;
            padding: 3px 6px;
        """)
        self.action_label.setAlignment(Qt.AlignCenter)
        self.action_label.setWordWrap(True)
        self.action_label.hide()
        info_layout.addWidget(self.action_label)
        
        layout.addWidget(info_widget)
        
        # 右侧留空（手牌区域）
        layout.addStretch()
    
    def show_action(self, action_text, is_play=True):
        """显示出牌动作"""
        self.action_label.setText(action_text)
        self.action_label.setStyleSheet(f"""
            background-color: {'#4CAF50' if is_play else '#FF5722'}; 
            color: white; 
            font-size: 10px; 
            font-weight: bold;
            border-radius: 8px;
            padding: 3px 6px;
        """)
        self.action_label.show()
        QTimer.singleShot(2000, self.action_label.hide)


class FloatingLogWidget(QWidget):
    """透明悬浮日志窗口"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        # 设置透明背景
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("""
            QWidget {
                background: transparent;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 日志文本框
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(100)
        self.log_text.setMinimumWidth(400)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: rgba(27, 94, 32, 0.85);
                color: #FFD54F;
                border: 2px solid rgba(255, 152, 0, 0.6);
                border-radius: 8px;
                padding: 8px;
                font-size: 11px;
                font-family: "Microsoft YaHei", sans-serif;
            }
            QScrollBar:vertical {
                background: rgba(46, 125, 50, 0.5);
                width: 6px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255, 152, 0, 0.8);
                border-radius: 3px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        self.log_text.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.log_text.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        layout.addWidget(self.log_text)
        self.clear_log()
    
    def clear_log(self):
        self.log_text.clear()
        self.log_text.append("🎮 游戏开始！")
    
    def add_log(self, message):
        """添加日志"""
        timestamp = QDateTime.currentDateTime().toString("hh:mm:ss")
        self.log_text.append(f"[{timestamp}] {message}")
        # 自动滚动到底部
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())


class PlayAreaWidget(QFrame):
    """出牌区域，分别显示三方出的牌"""
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.player_cards = {}  # 存储每个玩家当前出的牌
    
    def setup_ui(self):
        self.setStyleSheet("background-color: #388E3C; border-radius: 10px; border: 2px solid #FFD54F;")
        self.setMinimumHeight(150)
        
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(5)
        main_layout.setContentsMargins(10, 5, 10, 5)
        
        # AI1出牌区域（上方）
        ai1_layout = QHBoxLayout()
        ai1_label = QLabel("AI1")
        ai1_label.setStyleSheet("color: #FFD54F; font-size: 11px; font-weight: bold;")
        ai1_label.setFixedWidth(40)
        ai1_layout.addWidget(ai1_label)
        
        self.ai1_cards_layout = QHBoxLayout()
        self.ai1_cards_layout.setAlignment(Qt.AlignLeft)
        self.ai1_cards_layout.setSpacing(3)
        ai1_layout.addLayout(self.ai1_cards_layout)
        ai1_layout.addStretch()
        main_layout.addLayout(ai1_layout)
        
        # AI2出牌区域（下方）
        ai2_layout = QHBoxLayout()
        ai2_label = QLabel("AI2")
        ai2_label.setStyleSheet("color: #FFD54F; font-size: 11px; font-weight: bold;")
        ai2_label.setFixedWidth(40)
        ai2_layout.addWidget(ai2_label)
        
        self.ai2_cards_layout = QHBoxLayout()
        self.ai2_cards_layout.setAlignment(Qt.AlignLeft)
        self.ai2_cards_layout.setSpacing(3)
        ai2_layout.addLayout(self.ai2_cards_layout)
        ai2_layout.addStretch()
        main_layout.addLayout(ai2_layout)
        
        # 玩家出牌区域（中间）
        player_layout = QHBoxLayout()
        player_label = QLabel("玩家")
        player_label.setStyleSheet("color: #FFD54F; font-size: 11px; font-weight: bold;")
        player_label.setFixedWidth(40)
        player_layout.addWidget(player_label)
        
        self.player_cards_layout = QHBoxLayout()
        self.player_cards_layout.setAlignment(Qt.AlignLeft)
        self.player_cards_layout.setSpacing(3)
        player_layout.addLayout(self.player_cards_layout)
        player_layout.addStretch()
        main_layout.addLayout(player_layout)
    
    def clear_layout(self, layout):
        """清空布局"""
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
    
    def update_player_cards(self, player_name, cards):
        """更新指定玩家出的牌"""
        if player_name == "AI1":
            self.clear_layout(self.ai1_cards_layout)
            for card in cards:
                card_label = CardLabel(card)
                self.ai1_cards_layout.addWidget(card_label)
        elif player_name == "AI2":
            self.clear_layout(self.ai2_cards_layout)
            for card in cards:
                card_label = CardLabel(card)
                self.ai2_cards_layout.addWidget(card_label)
        elif player_name == "Human":
            self.clear_layout(self.player_cards_layout)
            for card in cards:
                card_label = CardLabel(card)
                self.player_cards_layout.addWidget(card_label)
    
    def clear_all_cards(self):
        """清空所有出牌"""
        self.clear_layout(self.ai1_cards_layout)
        self.clear_layout(self.ai2_cards_layout)
        self.clear_layout(self.player_cards_layout)


class DouDiZhuGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("斗地主 - 增强版")
        self.setFixedSize(1050, 750)
        
        self.game_data = None
        self.ai_players = {}
        self.current_player = "Human"
        self.last_combination = []
        self.last_player = None
        self.game_running = False
        self.card_buttons = []
        self.landlord_cards = []
        self.pass_count = 0
        
        self.setup_ui()
    
    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(8, 8, 8, 8)
        
        # 顶部信息栏
        info_frame = QFrame()
        info_frame.setStyleSheet("background-color: #1B5E20; border-radius: 8px;")
        info_frame.setFixedHeight(45)
        info_layout = QHBoxLayout(info_frame)
        
        self.status_label = QLabel("🏠 点击开始游戏")
        self.status_label.setStyleSheet("color: #FFD54F; font-size: 13px; font-weight: bold;")
        
        self.turn_label = QLabel("")
        self.turn_label.setStyleSheet("color: white; font-size: 12px;")
        
        info_layout.addWidget(self.status_label)
        info_layout.addStretch()
        info_layout.addWidget(self.turn_label)
        info_layout.addStretch()
        
        main_layout.addWidget(info_frame)
        
        # 中间区域（出牌区）
        middle_frame = QFrame()
        middle_layout = QHBoxLayout(middle_frame)
        middle_layout.setSpacing(10)
        
        self.ai1_panel = AIPanel("AI1")
        middle_layout.addWidget(self.ai1_panel)
        
        # 出牌区域
        self.play_area = PlayAreaWidget()
        middle_layout.addWidget(self.play_area, stretch=2)
        
        self.ai2_panel = AIPanel("AI2")
        middle_layout.addWidget(self.ai2_panel)
        
        main_layout.addWidget(middle_frame, stretch=2)
        
        # 悬浮日志区域（覆盖在出牌区上方）
        self.game_log = FloatingLogWidget(self.play_area)
        self.game_log.setGeometry(10, 5, 400, 100)
        
        # 玩家手牌区
        player_frame = QFrame()
        player_frame.setStyleSheet("background-color: #2E7D32; border-radius: 10px;")
        player_frame.setMinimumHeight(120)
        player_layout = QVBoxLayout(player_frame)
        player_layout.setSpacing(5)
        
        header_layout = QHBoxLayout()
        self.player_panel = PlayerPanel()
        header_layout.addWidget(self.player_panel)
        
        player_count_container = QWidget()
        player_count_layout = QVBoxLayout(player_count_container)
        player_label = QLabel("👤 你的手牌")
        player_label.setStyleSheet("color: white; font-size: 13px; font-weight: bold;")
        self.player_count_label = QLabel("17 张")
        self.player_count_label.setStyleSheet("color: #FFD54F; font-size: 12px;")
        player_count_layout.addWidget(player_label)
        player_count_layout.addWidget(self.player_count_label)
        header_layout.addWidget(player_count_container)
        header_layout.addStretch()
        
        # 添加上家牌显示
        self.last_label = QLabel("📋 上家牌: 无")
        self.last_label.setStyleSheet("color: #FFD54F; font-size: 11px; padding-right: 10px;")
        header_layout.addWidget(self.last_label)
        
        player_layout.addLayout(header_layout)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea { background-color: transparent; border: none; }
            QScrollBar:horizontal { background: #1B5E20; height: 8px; border-radius: 4px; }
            QScrollBar::handle:horizontal { background: #FF9800; border-radius: 4px; }
        """)
        
        self.cards_container = QWidget()
        self.cards_layout = QHBoxLayout(self.cards_container)
        self.cards_layout.setAlignment(Qt.AlignCenter)
        self.cards_layout.setSpacing(4)
        
        scroll.setWidget(self.cards_container)
        player_layout.addWidget(scroll)
        
        main_layout.addWidget(player_frame, stretch=1)
        
        # 控制按钮
        btn_frame = QFrame()
        btn_layout = QHBoxLayout(btn_frame)
        btn_layout.setAlignment(Qt.AlignCenter)
        btn_layout.setSpacing(15)
        
        self.start_btn = QPushButton("🎮 开始")
        self.start_btn.setFixedSize(100, 40)
        self.start_btn.setStyleSheet("background-color: #FF9800; color: white; font-size: 14px; font-weight: bold; border-radius: 20px;")
        self.start_btn.clicked.connect(self.start_game)
        
        self.play_btn = QPushButton("🎯 出牌")
        self.play_btn.setFixedSize(90, 40)
        self.play_btn.setStyleSheet("background-color: #4CAF50; color: white; font-size: 14px; font-weight: bold; border-radius: 20px;")
        self.play_btn.clicked.connect(self.play_cards)
        self.play_btn.setEnabled(False)
        
        self.pass_btn = QPushButton("⏭️ 过牌")
        self.pass_btn.setFixedSize(90, 40)
        self.pass_btn.setStyleSheet("background-color: #757575; color: white; font-size: 14px; font-weight: bold; border-radius: 20px;")
        self.pass_btn.clicked.connect(self.pass_turn)
        self.pass_btn.setEnabled(False)
        
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.play_btn)
        btn_layout.addWidget(self.pass_btn)
        main_layout.addWidget(btn_frame)
    
    def format_cards_text(self, cards):
        """格式化卡牌显示文本"""
        if not cards:
            return ""
        if len(cards) <= 5:
            return " ".join(str(c) for c in cards)
        return f"{' '.join(str(c) for c in cards[:3])} ... {str(cards[-1])}"
    
    def is_valid_combination(self, cards):
        """检查牌型是否有效"""
        info = PatternDetector.detect(cards)
        return info['valid']
    
    def can_beat(self, play_cards, last_cards):
        """判断是否能压过上家"""
        return PlayComparator.can_beat(play_cards, last_cards)
    
    def start_game(self):
        try:
            self.game_data = DeckManager.deal()
            
            self.ai_players = {
                "AI1": ExpertAIPlayer("AI1", Difficulty.HARD),
                "AI2": ExpertAIPlayer("AI2", Difficulty.MEDIUM)
            }
            self.ai_players["AI1"].cards = self.game_data["AI1"]
            self.ai_players["AI2"].cards = self.game_data["AI2"]
            
            self.landlord_cards = self.game_data["Landlord"]
            self.current_player = "Human"
            self.last_combination = []
            self.last_player = None
            self.game_running = True
            self.pass_count = 0
            
            self.game_log.clear_log()
            self.game_log.add_log("🎲 开始新游戏！")
            self.game_log.add_log(f"📦 地主牌: {' '.join(str(c) for c in self.landlord_cards)}")
            
            # 清空出牌区
            self.play_area.clear_all_cards()
            
            self.update_display()
            self.show_landlord_choice()
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"开始游戏失败：{e}")
    
    def show_landlord_choice(self):
        cards_text = "  ".join(str(c) for c in self.landlord_cards)
        msg = QMessageBox(self)
        msg.setWindowTitle("叫地主")
        msg.setText(f"地主牌: {cards_text}\n\n是否要当地主？")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        
        if msg.exec() == QMessageBox.Yes:
            self.game_data["Human"].extend(self.landlord_cards)
            self.game_data["Human"] = sorted(self.game_data["Human"])
            self.status_label.setText("👑 你是地主！")
            self.game_log.add_log("👑 玩家成为地主！")
        else:
            self.game_data["AI1"].extend(self.landlord_cards)
            self.game_data["AI1"] = sorted(self.game_data["AI1"])
            self.ai_players["AI1"].cards = self.game_data["AI1"]
            self.status_label.setText("🤖 AI1是地主")
            self.game_log.add_log("🤖 AI1 成为地主！")
        
        self.update_display()
        self.play_btn.setEnabled(True)
        self.pass_btn.setEnabled(True)
        
        if self.current_player != "Human":
            QTimer.singleShot(500, self.ai_play)
    
    def update_display(self):
        if not self.game_data:
            return
        
        self.ai1_panel.update_count(len(self.game_data.get("AI1", [])))
        self.ai2_panel.update_count(len(self.game_data.get("AI2", [])))
        
        self.clear_layout(self.cards_layout)
        self.card_buttons = []
        
        for i, card in enumerate(self.game_data.get("Human", [])):
            btn = CardButton(card, i)
            btn.clicked.connect(lambda checked, b=btn: b.toggle_select())
            self.cards_layout.addWidget(btn)
            self.card_buttons.append(btn)
        
        self.player_count_label.setText(f"{len(self.game_data.get('Human', []))} 张")
        
        # 更新上家牌显示
        if self.last_combination:
            self.last_label.setText(f"📋 上家牌: {' '.join(str(c) for c in self.last_combination)}")
        else:
            self.last_label.setText("📋 上家牌: 无")
    
    def clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
    
    def get_selected_cards(self):
        return [btn.card for btn in self.card_buttons if btn.selected]
    
    def clear_selection(self):
        for btn in self.card_buttons:
            btn.selected = False
            btn.update_style()
    
    def play_cards(self):
        if self.current_player != "Human" or not self.game_running:
            return
        
        selected = self.get_selected_cards()
        if not selected:
            QMessageBox.warning(self, "提示", "请先选择要出的牌！")
            return
        
        if not self.is_valid_combination(selected):
            QMessageBox.warning(self, "提示", "无效的牌型！")
            return
        
        if self.last_combination and not self.can_beat(selected, self.last_combination):
            QMessageBox.warning(self, "提示", "不能压过上家的牌！")
            return
        
        # 记录出牌
        cards_text = self.format_cards_text(selected)
        self.game_log.add_log(f"👤 玩家出牌: {cards_text} ({len(selected)}张)")
        self.player_panel.show_action(f"出牌\n{len(selected)}张", True)
        
        # 更新出牌区显示
        self.play_area.update_player_cards("Human", selected)
        
        for card in selected:
            self.game_data["Human"].remove(card)
        
        self.last_combination = selected
        self.last_player = self.current_player
        self.pass_count = 0
        self.clear_selection()
        
        if len(self.game_data["Human"]) == 0:
            self.game_over("Human")
            return
        
        self.current_player = "AI1"
        self.update_display()
        self.turn_label.setText("🤖 AI1 的回合")
        
        self.play_btn.setEnabled(False)
        self.pass_btn.setEnabled(False)
        QTimer.singleShot(500, self.ai_play)
    
    def pass_turn(self):
        if self.current_player != "Human" or not self.game_running:
            return
        
        if self.last_player == "Human":
            QMessageBox.information(self, "提示", "你是最后出牌的人，不能过牌！")
            return
        
        # 记录过牌
        self.game_log.add_log(f"👤 玩家选择过牌")
        self.player_panel.show_action("过牌", False)
        
        self.pass_count += 1
        
        if self.pass_count >= 2:
            self.last_combination = []
            self.pass_count = 0
            self.current_player = self.last_player
            # 新回合开始，清空出牌区
            self.play_area.clear_all_cards()
            self.update_display()
            self.turn_label.setText("👤 你的回合（重新出牌）")
            self.game_log.add_log("🔄 新回合开始，可以任意出牌")
            self.play_btn.setEnabled(True)
            self.pass_btn.setEnabled(True)
            return
        
        self.current_player = "AI1"
        self.update_display()
        self.turn_label.setText("🤖 AI1 的回合")
        
        self.play_btn.setEnabled(False)
        self.pass_btn.setEnabled(False)
        QTimer.singleShot(500, self.ai_play)
    
    def ai_play(self):
        if not self.game_running or self.current_player not in self.ai_players:
            return
        
        QApplication.processEvents()
        
        ai = self.ai_players[self.current_player]
        selected = ai.get_play(self.last_combination)
        
        panel = self.ai1_panel if self.current_player == "AI1" else self.ai2_panel
        
        if selected:
            cards_text = self.format_cards_text(selected)
            self.game_log.add_log(f"🤖 {self.current_player} 出牌: {cards_text} ({len(selected)}张)")
            panel.show_action(f"出牌\n{len(selected)}张", True)
            
            # 更新出牌区显示
            self.play_area.update_player_cards(self.current_player, selected)
            
            for card in selected:
                self.game_data[self.current_player].remove(card)
            
            self.last_combination = selected
            self.last_player = self.current_player
            ai.cards = self.game_data[self.current_player]
            self.pass_count = 0
            
            panel.set_status(f"出了 {len(selected)} 张", True)
            
            if len(self.game_data[self.current_player]) == 0:
                self.game_over(self.current_player)
                return
            
            if self.current_player == "AI1":
                self.current_player = "AI2"
            else:
                self.current_player = "Human"
        else:
            self.game_log.add_log(f"🤖 {self.current_player} 选择过牌")
            panel.show_action("过牌", False)
            
            self.pass_count += 1
            panel.set_status("过牌", False)
            
            if self.pass_count >= 2:
                self.last_combination = []
                self.pass_count = 0
                self.current_player = self.last_player
                # 新回合开始，清空出牌区
                self.play_area.clear_all_cards()
                self.update_display()
                self.game_log.add_log("🔄 新回合开始，可以任意出牌")
                
                if self.current_player == "Human":
                    self.turn_label.setText("👤 你的回合（重新出牌）")
                    self.play_btn.setEnabled(True)
                    self.pass_btn.setEnabled(True)
                else:
                    self.turn_label.setText(f"🤖 {self.current_player} 的回合")
                    QTimer.singleShot(500, self.ai_play)
                return
            else:
                if self.current_player == "AI1":
                    self.current_player = "AI2"
                else:
                    self.current_player = "Human"
        
        self.update_display()
        
        if self.game_running:
            if self.current_player == "Human":
                self.play_btn.setEnabled(True)
                self.pass_btn.setEnabled(True)
                self.turn_label.setText("👤 你的回合")
            else:
                self.play_btn.setEnabled(False)
                self.pass_btn.setEnabled(False)
                QTimer.singleShot(600, self.ai_play)
    
    def game_over(self, winner):
        self.game_running = False
        self.play_btn.setEnabled(False)
        self.pass_btn.setEnabled(False)
        
        if winner == "Human":
            self.game_log.add_log("🎉 恭喜！玩家获胜！")
            QMessageBox.information(self, "游戏结束", "🎉 恭喜你赢了！🎉")
        else:
            self.game_log.add_log(f"😢 {winner} 获胜！")
            QMessageBox.information(self, "游戏结束", f"😢 {winner} 赢了")
    
    def resizeEvent(self, event):
        """窗口大小改变时重新定位悬浮日志"""
        super().resizeEvent(event)
        if hasattr(self, 'game_log') and hasattr(self, 'play_area'):
            # 将日志窗口定位在出牌区顶部中央
            log_width = min(450, self.play_area.width() - 20)
            log_x = (self.play_area.width() - log_width) // 2
            self.game_log.setGeometry(log_x, 5, log_width, 100)


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = DouDiZhuGUI()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()