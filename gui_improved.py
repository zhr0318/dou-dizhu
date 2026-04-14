# gui_improved.py - 改进版界面（支持单机和联机两种模式）
import sys
import json
import asyncio
import threading
from typing import List, Dict, Optional

from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *

try:
    import websockets
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False
    print("警告: websockets 未安装，联机模式不可用。安装命令: pip install websockets")

from doudizhu_core import (
    Card,
    ExpertAIPlayer,
    Difficulty,
    PatternDetector,
    PlayComparator,
    DeckManager,
    CardType,
    GamePhase
)


# ============ 联机客户端线程 ============
class NetworkClient(QThread):
    """网络客户端线程"""
    
    # 信号
    connected = Signal(str)  # player_id
    disconnected = Signal()
    error = Signal(str)
    room_created = Signal(dict)
    room_joined = Signal(dict)
    room_left = Signal()
    player_joined = Signal(dict)
    player_left = Signal(str)
    player_ready = Signal(dict)
    game_started = Signal(dict)
    your_turn_bid = Signal(list)  # landlord_cards
    landlord_set = Signal(str, list, dict)  # landlord_id, landlord_cards, room
    your_turn_play = Signal(list)  # last_play
    cards_played = Signal(str, list, str, dict)  # player_id, cards, play_type, room
    game_over = Signal(str, str)  # winner_id, winner_name
    room_list_received = Signal(list)
    chat_received = Signal(str, str)  # player_name, message
    log_message = Signal(str)
    
    def __init__(self):
        super().__init__()
        self.websocket = None
        self.server_url = "ws://localhost:8765"
        self.player_id = None
        self.player_name = ""
        self.current_room = None
        self.running = False
        self.loop = None
    
    def set_server(self, url: str):
        self.server_url = url
    
    def set_player_name(self, name: str):
        self.player_name = name
    
    def run(self):
        """在线程中运行 asyncio 事件循环"""
        self.running = True
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        try:
            self.loop.run_until_complete(self.connect_websocket())
        except Exception as e:
            self.error.emit(f"连接失败: {e}")
        finally:
            self.loop.close()
    
    async def connect_websocket(self):
        try:
            self.websocket = await websockets.connect(self.server_url)
            self.running = True
            
            # 等待连接确认
            response = await self.websocket.recv()
            data = json.loads(response)
            if data.get("action") == "connected":
                self.player_id = data["data"]["player_id"]
                self.connected.emit(self.player_id)
                self.log_message.emit(f"✅ 已连接到服务器 (ID: {self.player_id[:8]})")
            
            # 监听消息
            async for message in self.websocket:
                if not self.running:
                    break
                await self.handle_message(message)
                
        except Exception as e:
            if self.running:
                self.error.emit(str(e))
        finally:
            self.running = False
            self.disconnected.emit()
    
    async def handle_message(self, message: str):
        """处理服务器消息"""
        try:
            data = json.loads(message)
            action = data.get("action")
            payload = data.get("data", {})
            
            if action == "room_created":
                self.current_room = payload["room"]
                self.room_created.emit(payload)
                self.log_message.emit(f"✅ 房间创建成功! 房间号: {payload['room_id']}")
                
            elif action == "room_joined":
                self.current_room = payload["room"]
                self.room_joined.emit(payload)
                self.log_message.emit(f"✅ 成功加入房间: {self.current_room['room_name']}")
                
            elif action == "room_left":
                self.current_room = None
                self.room_left.emit()
                
            elif action == "player_joined":
                if self.current_room:
                    self.current_room["players"][payload["player"]["player_id"]] = payload["player"]
                self.player_joined.emit(payload)
                self.log_message.emit(f"👤 {payload['player']['name']} 加入了房间")
                
            elif action == "player_left":
                if self.current_room and payload["player_id"] in self.current_room["players"]:
                    del self.current_room["players"][payload["player_id"]]
                self.player_left.emit(payload["player_id"])
                
            elif action == "player_ready":
                if self.current_room:
                    self.current_room["players"] = payload["players"]
                self.player_ready.emit(payload)
                
            elif action == "game_started":
                self.current_room = payload["room"]
                self.game_started.emit(payload)
                self.log_message.emit("🎮 游戏开始!")
                
            elif action == "your_turn_bid":
                self.your_turn_bid.emit(payload.get("landlord_cards", []))
                
            elif action == "landlord_set":
                self.current_room = payload["room"]
                self.landlord_set.emit(
                    payload["landlord_id"],
                    payload["landlord_cards"],
                    payload["room"]
                )
                
            elif action == "bid_passed":
                self.log_message.emit(f"玩家 {payload['player_id'][:8]} 不叫地主")
                
            elif action == "your_turn_play":
                self.your_turn_play.emit(payload.get("last_play", []))
                
            elif action == "cards_played":
                self.current_room = payload["room"]
                self.cards_played.emit(
                    payload["player_id"],
                    payload["cards"],
                    payload["play_type"],
                    payload["room"]
                )
                
            elif action == "game_over":
                self.game_over.emit(payload["winner_id"], payload["winner_name"])
                self.log_message.emit(f"🏆 游戏结束! {payload['winner_name']} 获胜!")
                
            elif action == "room_list":
                self.room_list_received.emit(payload.get("rooms", []))
                
            elif action == "room_list_update":
                self.room_list_received.emit(payload.get("rooms", []))
                
            elif action == "chat_message":
                self.chat_received.emit(payload["player_name"], payload["message"])
                
            elif action == "error":
                self.error.emit(data.get("message", "未知错误"))
                
        except json.JSONDecodeError:
            self.log_message.emit(f"⚠️ 无效的JSON: {message[:100]}")
        except Exception as e:
            self.log_message.emit(f"⚠️ 处理消息错误: {e}")
    
    def send(self, action: str, data: dict = None):
        """发送消息到服务器"""
        if not self.websocket or not self.running:
            return
        
        message = {"action": action}
        if data:
            message.update(data)
        
        asyncio.run_coroutine_threadsafe(
            self._send(json.dumps(message)),
            self.loop
        )
    
    async def _send(self, message: str):
        try:
            await self.websocket.send(message)
        except Exception as e:
            self.error.emit(f"发送失败: {e}")
    
    def stop(self):
        self.running = False
        if self.websocket and self.loop:
            asyncio.run_coroutine_threadsafe(self.websocket.close(), self.loop)
        self.quit()
        self.wait()


# ============ 卡片按钮 ============
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
        if isinstance(self.card, list):
            suit, rank = self.card
        else:
            suit, rank = self.card.suit, self.card.rank
        
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
        
        avatar_container = QWidget()
        avatar_layout = QVBoxLayout(avatar_container)
        avatar_layout.setSpacing(2)
        
        avatar = QLabel()
        avatar.setFixedSize(50, 50)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setStyleSheet("background-color: #1B5E20; border-radius: 25px; font-size: 28px;")
        avatar.setText("🤖")
        avatar_layout.addWidget(avatar, alignment=Qt.AlignCenter)
        
        self.name_label = QLabel(self.name)
        self.name_label.setStyleSheet("color: white; font-size: 13px; font-weight: bold;")
        self.name_label.setAlignment(Qt.AlignCenter)
        avatar_layout.addWidget(self.name_label)
        
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
    
    def set_name(self, name: str):
        self.name = name
        self.name_label.setText(name)
    
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


class PlayerPanel(QFrame):
    """玩家面板"""
    def __init__(self):
        super().__init__()
        self.setup_ui()
    
    def setup_ui(self):
        self.setStyleSheet("background-color: transparent;")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
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
        
        self.name_label = QLabel("玩家")
        self.name_label.setStyleSheet("color: white; font-size: 12px; font-weight: bold;")
        self.name_label.setAlignment(Qt.AlignCenter)
        info_layout.addWidget(self.name_label)
        
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
        layout.addStretch()
    
    def set_name(self, name: str):
        self.name_label.setText(name)
    
    def show_action(self, action_text, is_play=True):
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
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("QWidget { background: transparent; }")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
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
        """)
        self.log_text.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.log_text.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        layout.addWidget(self.log_text)
        self.clear_log()
    
    def clear_log(self):
        self.log_text.clear()
        self.log_text.append("🎮 游戏开始！")
    
    def add_log(self, message):
        timestamp = QDateTime.currentDateTime().toString("hh:mm:ss")
        self.log_text.append(f"[{timestamp}] {message}")
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())


class PlayAreaWidget(QFrame):
    """出牌区域"""
    def __init__(self):
        super().__init__()
        self.setup_ui()
    
    def setup_ui(self):
        self.setStyleSheet("background-color: #388E3C; border-radius: 10px; border: 2px solid #FFD54F;")
        self.setMinimumHeight(150)
        
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(5)
        main_layout.setContentsMargins(10, 5, 10, 5)
        
        # AI1出牌区域
        ai1_layout = QHBoxLayout()
        self.ai1_name_label = QLabel("AI1")
        self.ai1_name_label.setStyleSheet("color: #FFD54F; font-size: 11px; font-weight: bold;")
        self.ai1_name_label.setFixedWidth(50)
        ai1_layout.addWidget(self.ai1_name_label)
        
        self.ai1_cards_layout = QHBoxLayout()
        self.ai1_cards_layout.setAlignment(Qt.AlignLeft)
        self.ai1_cards_layout.setSpacing(3)
        ai1_layout.addLayout(self.ai1_cards_layout)
        ai1_layout.addStretch()
        main_layout.addLayout(ai1_layout)
        
        # AI2出牌区域
        ai2_layout = QHBoxLayout()
        self.ai2_name_label = QLabel("AI2")
        self.ai2_name_label.setStyleSheet("color: #FFD54F; font-size: 11px; font-weight: bold;")
        self.ai2_name_label.setFixedWidth(50)
        ai2_layout.addWidget(self.ai2_name_label)
        
        self.ai2_cards_layout = QHBoxLayout()
        self.ai2_cards_layout.setAlignment(Qt.AlignLeft)
        self.ai2_cards_layout.setSpacing(3)
        ai2_layout.addLayout(self.ai2_cards_layout)
        ai2_layout.addStretch()
        main_layout.addLayout(ai2_layout)
        
        # 玩家出牌区域
        player_layout = QHBoxLayout()
        self.player_name_label = QLabel("玩家")
        self.player_name_label.setStyleSheet("color: #FFD54F; font-size: 11px; font-weight: bold;")
        self.player_name_label.setFixedWidth(50)
        player_layout.addWidget(self.player_name_label)
        
        self.player_cards_layout = QHBoxLayout()
        self.player_cards_layout.setAlignment(Qt.AlignLeft)
        self.player_cards_layout.setSpacing(3)
        player_layout.addLayout(self.player_cards_layout)
        player_layout.addStretch()
        main_layout.addLayout(player_layout)
    
    def set_player_names(self, ai1_name: str = "AI1", ai2_name: str = "AI2", player_name: str = "玩家"):
        self.ai1_name_label.setText(ai1_name[:8])
        self.ai2_name_label.setText(ai2_name[:8])
        self.player_name_label.setText(player_name[:8])
    
    def clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
    
    def update_player_cards(self, player_name, cards):
        if "AI1" in player_name or player_name == "AI1":
            self.clear_layout(self.ai1_cards_layout)
            for card in cards:
                card_label = CardLabel(card)
                self.ai1_cards_layout.addWidget(card_label)
        elif "AI2" in player_name or player_name == "AI2":
            self.clear_layout(self.ai2_cards_layout)
            for card in cards:
                card_label = CardLabel(card)
                self.ai2_cards_layout.addWidget(card_label)
        elif "Human" in player_name or "玩家" in player_name:
            self.clear_layout(self.player_cards_layout)
            for card in cards:
                card_label = CardLabel(card)
                self.player_cards_layout.addWidget(card_label)
    
    def clear_all_cards(self):
        self.clear_layout(self.ai1_cards_layout)
        self.clear_layout(self.ai2_cards_layout)
        self.clear_layout(self.player_cards_layout)


class ConnectDialog(QDialog):
    """连接服务器对话框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("连接服务器")
        self.setFixedSize(350, 200)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("服务器地址:"))
        self.url_input = QLineEdit("ws://localhost:8765")
        layout.addWidget(self.url_input)
        
        layout.addWidget(QLabel("你的名字:"))
        self.name_input = QLineEdit("玩家")
        layout.addWidget(self.name_input)
        
        layout.addSpacing(20)
        
        btn_layout = QHBoxLayout()
        self.connect_btn = QPushButton("连接")
        self.connect_btn.clicked.connect(self.accept)
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.connect_btn)
        btn_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(btn_layout)
    
    def get_server_url(self):
        return self.url_input.text().strip()
    
    def get_player_name(self):
        return self.name_input.text().strip() or "玩家"


class RoomListDialog(QDialog):
    """房间列表对话框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("房间列表")
        self.setFixedSize(400, 350)
        self.selected_room_id = None
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("可用房间:"))
        
        self.room_list_widget = QListWidget()
        self.room_list_widget.itemSelectionChanged.connect(self.on_selection_changed)
        layout.addWidget(self.room_list_widget)
        
        btn_layout = QHBoxLayout()
        self.refresh_btn = QPushButton("刷新")
        self.join_btn = QPushButton("加入房间")
        self.join_btn.setEnabled(False)
        self.create_btn = QPushButton("创建房间")
        btn_layout.addWidget(self.refresh_btn)
        btn_layout.addWidget(self.join_btn)
        btn_layout.addWidget(self.create_btn)
        
        layout.addLayout(btn_layout)
    
    def on_selection_changed(self):
        item = self.room_list_widget.currentItem()
        if item:
            self.selected_room_id = item.data(Qt.UserRole)
            self.join_btn.setEnabled(True)
        else:
            self.selected_room_id = None
            self.join_btn.setEnabled(False)
    
    def update_room_list(self, rooms: list):
        self.room_list_widget.clear()
        for room in rooms:
            item = QListWidgetItem(f"{room['room_name']} - {room['player_count']}/{room['max_players']}人")
            item.setData(Qt.UserRole, room['room_id'])
            self.room_list_widget.addItem(item)


# ============ 主窗口 ============
class DouDiZhuGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("斗地主 - 单机/联机双模式")
        self.setFixedSize(1050, 750)
        
        # 游戏模式
        self.game_mode = None  # "single" 或 "online"
        self.is_host = False
        
        # 单机模式数据
        self.game_data = None
        self.ai_players = {}
        self.landlord_cards = []
        
        # 通用数据
        self.current_player = None
        self.last_combination = []
        self.last_player = None
        self.game_running = False
        self.card_buttons = []
        self.pass_count = 0
        self.my_player_id = None
        self.players_info = {}  # player_id -> {"name": str, "card_count": int}
        self.player_names = {"AI1": "AI1", "AI2": "AI2", "Human": "玩家"}
        
        # 网络客户端
        self.network_client = None
        
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
        
        self.mode_label = QLabel("🎮 选择模式")
        self.mode_label.setStyleSheet("color: #FFD54F; font-size: 13px; font-weight: bold;")
        
        self.status_label = QLabel("🏠 请选择游戏模式")
        self.status_label.setStyleSheet("color: white; font-size: 13px; font-weight: bold;")
        
        self.turn_label = QLabel("")
        self.turn_label.setStyleSheet("color: #FFD54F; font-size: 12px;")
        
        info_layout.addWidget(self.mode_label)
        info_layout.addStretch()
        info_layout.addWidget(self.status_label)
        info_layout.addStretch()
        info_layout.addWidget(self.turn_label)
        
        main_layout.addWidget(info_frame)
        
        # 中间区域
        middle_frame = QFrame()
        middle_layout = QHBoxLayout(middle_frame)
        middle_layout.setSpacing(10)
        
        self.ai1_panel = AIPanel("AI1")
        middle_layout.addWidget(self.ai1_panel)
        
        self.play_area = PlayAreaWidget()
        middle_layout.addWidget(self.play_area, stretch=2)
        
        self.ai2_panel = AIPanel("AI2")
        middle_layout.addWidget(self.ai2_panel)
        
        main_layout.addWidget(middle_frame, stretch=2)
        
        # 悬浮日志
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
        
        self.single_btn = QPushButton("🎮 单机模式")
        self.single_btn.setFixedSize(100, 40)
        self.single_btn.setStyleSheet("background-color: #4CAF50; color: white; font-size: 14px; font-weight: bold; border-radius: 20px;")
        self.single_btn.clicked.connect(self.start_single_mode)
        
        self.online_btn = QPushButton("🌐 联机模式")
        self.online_btn.setFixedSize(100, 40)
        self.online_btn.setStyleSheet("background-color: #2196F3; color: white; font-size: 14px; font-weight: bold; border-radius: 20px;")
        self.online_btn.clicked.connect(self.start_online_mode)
        
        self.start_btn = QPushButton("▶️ 开始游戏")
        self.start_btn.setFixedSize(100, 40)
        self.start_btn.setStyleSheet("background-color: #FF9800; color: white; font-size: 14px; font-weight: bold; border-radius: 20px;")
        self.start_btn.clicked.connect(self.start_game)
        self.start_btn.setEnabled(False)
        
        self.ready_btn = QPushButton("✅ 准备")
        self.ready_btn.setFixedSize(90, 40)
        self.ready_btn.setStyleSheet("background-color: #9C27B0; color: white; font-size: 14px; font-weight: bold; border-radius: 20px;")
        self.ready_btn.clicked.connect(self.toggle_ready)
        self.ready_btn.setEnabled(False)
        self.ready_btn.hide()
        
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
        
        btn_layout.addWidget(self.single_btn)
        btn_layout.addWidget(self.online_btn)
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.ready_btn)
        btn_layout.addWidget(self.play_btn)
        btn_layout.addWidget(self.pass_btn)
        main_layout.addWidget(btn_frame)
        
        # 房间列表面板
        self.room_list_dialog = None
    
    # ============ 模式选择 ============
    def start_single_mode(self):
        """启动单机模式"""
        self.game_mode = "single"
        self.mode_label.setText("🎮 单机模式")
        self.status_label.setText("🤖 单机对战 AI")
        
        self.single_btn.setEnabled(False)
        self.online_btn.setEnabled(False)
        self.start_btn.setEnabled(True)
        self.ready_btn.hide()
        
        self.game_log.clear_log()
        self.game_log.add_log("🎮 进入单机模式")
        
        # 重置玩家名称
        self.player_names = {"AI1": "AI1", "AI2": "AI2", "Human": "玩家"}
        self.update_player_names()
    
    def start_online_mode(self):
        """启动联机模式"""
        if not WEBSOCKET_AVAILABLE:
            QMessageBox.critical(self, "错误", "联机模式需要安装 websockets 库\n请运行: pip install websockets")
            return
        
        dialog = ConnectDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return
        
        server_url = dialog.get_server_url()
        player_name = dialog.get_player_name()
        
        self.game_mode = "online"
        self.mode_label.setText("🌐 联机模式")
        self.status_label.setText(f"🔄 正在连接 {server_url}...")
        
        self.player_names["Human"] = player_name
        self.player_panel.set_name(player_name)
        
        self.single_btn.setEnabled(False)
        self.online_btn.setEnabled(False)
        
        # 创建网络客户端
        self.network_client = NetworkClient()
        self.network_client.set_server(server_url)
        self.network_client.set_player_name(player_name)
        
        # 连接信号
        self.network_client.connected.connect(self.on_connected)
        self.network_client.disconnected.connect(self.on_disconnected)
        self.network_client.error.connect(self.on_network_error)
        self.network_client.log_message.connect(self.game_log.add_log)
        self.network_client.room_created.connect(self.on_room_created)
        self.network_client.room_joined.connect(self.on_room_joined)
        self.network_client.player_joined.connect(self.on_player_joined)
        self.network_client.player_left.connect(self.on_player_left)
        self.network_client.player_ready.connect(self.on_player_ready)
        self.network_client.game_started.connect(self.on_online_game_started)
        self.network_client.your_turn_bid.connect(self.on_your_turn_bid)
        self.network_client.landlord_set.connect(self.on_landlord_set)
        self.network_client.your_turn_play.connect(self.on_your_turn_play)
        self.network_client.cards_played.connect(self.on_cards_played)
        self.network_client.game_over.connect(self.on_online_game_over)
        self.network_client.room_list_received.connect(self.on_room_list_received)
        
        self.network_client.start()
        
        self.game_log.clear_log()
        self.game_log.add_log(f"🌐 正在连接 {server_url}...")
    
    # ============ 网络回调 ============
    def on_connected(self, player_id: str):
        self.my_player_id = player_id
        self.status_label.setText(f"✅ 已连接 (ID: {player_id[:8]})")
        
        # 显示房间选择
        self.show_room_selection()
    
    def on_disconnected(self):
        self.status_label.setText("❌ 已断开连接")
        self.game_log.add_log("❌ 与服务器断开连接")
        self.reset_to_mode_selection()
    
    def on_network_error(self, error_msg: str):
        QMessageBox.warning(self, "网络错误", error_msg)
        self.game_log.add_log(f"⚠️ {error_msg}")
    
    def show_room_selection(self):
        """显示房间选择"""
        self.room_list_dialog = RoomListDialog(self)
        self.room_list_dialog.setWindowTitle("房间列表 - 联机模式")
        self.room_list_dialog.refresh_btn.clicked.connect(lambda: self.network_client.send("get_room_list"))
        self.room_list_dialog.join_btn.clicked.connect(self.join_selected_room)
        self.room_list_dialog.create_btn.clicked.connect(self.create_online_room)
        
        self.network_client.send("get_room_list")
        self.room_list_dialog.exec()
    
    def on_room_list_received(self, rooms: list):
        if self.room_list_dialog:
            self.room_list_dialog.update_room_list(rooms)
    
    def join_selected_room(self):
        if self.room_list_dialog and self.room_list_dialog.selected_room_id:
            self.network_client.send("join_room", {
                "room_id": self.room_list_dialog.selected_room_id,
                "player_name": self.player_names["Human"]
            })
            self.room_list_dialog.accept()
    
    def create_online_room(self):
        room_name, ok = QInputDialog.getText(self, "创建房间", "房间名称:", text="游戏房间")
        if ok and room_name:
            self.is_host = True
            self.network_client.send("create_room", {
                "room_name": room_name,
                "player_name": self.player_names["Human"]
            })
            if self.room_list_dialog:
                self.room_list_dialog.accept()
    
    def on_room_created(self, data: dict):
        self.game_log.add_log(f"✅ 房间创建成功! 房间号: {data['room_id']}")
        self.status_label.setText(f"📌 房间: {data['room_id']}")
        self.ready_btn.show()
        self.ready_btn.setEnabled(True)
        self.update_room_players(data["room"])
    
    def on_room_joined(self, data: dict):
        room = data["room"]
        self.game_log.add_log(f"✅ 加入房间: {room['room_name']}")
        self.status_label.setText(f"📌 房间: {room['room_id']}")
        self.ready_btn.show()
        self.ready_btn.setEnabled(True)
        self.update_room_players(room)
    
    def on_player_joined(self, data: dict):
        player = data["player"]
        self.game_log.add_log(f"👤 {player['name']} 加入了房间")
        if self.network_client.current_room:
            self.update_room_players(self.network_client.current_room)
    
    def on_player_left(self, player_id: str):
        self.game_log.add_log(f"👋 玩家离开了房间")
        if self.network_client.current_room:
            self.update_room_players(self.network_client.current_room)
    
    def on_player_ready(self, data: dict):
        self.update_room_players_from_dict(data["players"])
    
    def update_room_players(self, room: dict):
        """更新房间玩家显示"""
        players = room.get("players", {})
        self.update_room_players_from_dict(players)
    
    def update_room_players_from_dict(self, players: dict):
        """从字典更新玩家显示"""
        ai_count = 0
        for pid, pinfo in players.items():
            name = pinfo["name"]
            if pid == self.my_player_id:
                self.player_names["Human"] = name
                self.player_panel.set_name(name)
            elif "AI" in name or pinfo.get("is_ai"):
                ai_count += 1
                if ai_count == 1:
                    self.player_names["AI1"] = name
                else:
                    self.player_names["AI2"] = name
            else:
                # 其他真人玩家
                if self.player_names["AI1"] == "AI1":
                    self.player_names["AI1"] = name
                else:
                    self.player_names["AI2"] = name
        
        self.update_player_names()
    
    def update_player_names(self):
        """更新面板上的玩家名称"""
        self.ai1_panel.set_name(self.player_names["AI1"])
        self.ai2_panel.set_name(self.player_names["AI2"])
        self.play_area.set_player_names(
            self.player_names["AI1"],
            self.player_names["AI2"],
            self.player_names["Human"]
        )
    
    def toggle_ready(self):
        """切换准备状态"""
        if self.network_client:
            self.network_client.send("ready")
            self.ready_btn.setText("⏳ 等待...")
            self.ready_btn.setEnabled(False)
    
    def on_online_game_started(self, data: dict):
        """联机游戏开始"""
        self.game_running = True
        self.start_btn.setEnabled(False)
        self.ready_btn.hide()
        
        room = data["room"]
        self.landlord_cards = []  # 联机模式不需要本地存储
        
        # 更新手牌
        my_player = room["players"].get(self.my_player_id, {})
        my_cards = my_player.get("cards", [])
        self.update_hand_display(my_cards)
        
        self.game_log.add_log("🎮 游戏开始! 等待叫地主...")
    
    def on_your_turn_bid(self, landlord_cards: list):
        """轮到你叫地主"""
        self.landlord_cards = landlord_cards
        
        cards_text = " ".join(self.format_card(c) for c in landlord_cards)
        
        reply = QMessageBox.question(
            self,
            "叫地主",
            f"底牌: {cards_text}\n\n是否要当地主？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        want = (reply == QMessageBox.Yes)
        self.network_client.send("bid_landlord", {"want_landlord": want})
        
        if want:
            self.game_log.add_log("👑 你选择叫地主")
        else:
            self.game_log.add_log("⏭️ 你选择不叫地主")
    
    def on_landlord_set(self, landlord_id: str, landlord_cards: list, room: dict):
        """地主确定"""
        landlord_name = room["players"].get(landlord_id, {}).get("name", "未知")
        cards_text = " ".join(self.format_card(c) for c in landlord_cards)
        
        self.game_log.add_log(f"👑 地主是: {landlord_name}")
        self.game_log.add_log(f"📦 底牌: {cards_text}")
        
        # 更新手牌
        my_player = room["players"].get(self.my_player_id, {})
        my_cards = my_player.get("cards", [])
        self.update_hand_display(my_cards)
        
        # 更新其他玩家牌数
        self.update_other_players_count(room)
    
    def on_your_turn_play(self, last_play: list):
        """轮到你出牌"""
        self.current_player = "Human"
        self.last_combination = last_play
        
        if last_play:
            cards_text = " ".join(self.format_card(c) for c in last_play)
            self.last_label.setText(f"📋 上家牌: {cards_text}")
        else:
            self.last_label.setText("📋 上家牌: 无")
            self.play_area.clear_all_cards()
        
        self.turn_label.setText("🎯 你的回合!")
        self.play_btn.setEnabled(True)
        self.pass_btn.setEnabled(True)
        
        self.game_log.add_log("🎯 轮到你了!")
    
    def on_cards_played(self, player_id: str, cards: list, play_type: str, room: dict):
        """有玩家出牌"""
        player_name = room["players"].get(player_id, {}).get("name", "未知")
        
        if cards:
            cards_text = " ".join(self.format_card(c) for c in cards)
            self.game_log.add_log(f"🎴 {player_name} 出牌: {cards_text} [{play_type}]")
            
            # 更新出牌区显示
            if player_id == self.my_player_id:
                display_name = "Human"
            elif player_name == self.player_names.get("AI1"):
                display_name = "AI1"
            elif player_name == self.player_names.get("AI2"):
                display_name = "AI2"
            else:
                # 其他玩家
                if self.player_names["AI1"] == "AI1":
                    display_name = "AI1"
                    self.player_names["AI1"] = player_name
                else:
                    display_name = "AI2"
                    self.player_names["AI2"] = player_name
            
            self.play_area.update_player_cards(display_name, cards)
            self.last_combination = cards
        else:
            self.game_log.add_log(f"⏭️ {player_name} 过牌")
        
        # 更新手牌
        my_player = room["players"].get(self.my_player_id, {})
        my_cards = my_player.get("cards", [])
        self.update_hand_display(my_cards)
        
        # 更新其他玩家牌数
        self.update_other_players_count(room)
        
        # 如果不是自己的回合，禁用按钮
        if room.get("current_player_id") != self.my_player_id:
            self.play_btn.setEnabled(False)
            self.pass_btn.setEnabled(False)
            self.turn_label.setText(f"⏳ 等待 {room['players'].get(room.get('current_player_id', ''), {}).get('name', '其他玩家')} 出牌...")
    
    def update_other_players_count(self, room: dict):
        """更新其他玩家的牌数"""
        players = room.get("players", {})
        
        ai1_name = self.player_names["AI1"]
        ai2_name = self.player_names["AI2"]
        
        for pid, pinfo in players.items():
            if pid == self.my_player_id:
                continue
            
            name = pinfo["name"]
            count = pinfo.get("card_count", 0)
            
            if name == ai1_name:
                self.ai1_panel.update_count(count)
            elif name == ai2_name:
                self.ai2_panel.update_count(count)
    
    def on_online_game_over(self, winner_id: str, winner_name: str):
        """联机游戏结束"""
        self.game_running = False
        self.play_btn.setEnabled(False)
        self.pass_btn.setEnabled(False)
        
        if winner_id == self.my_player_id:
            QMessageBox.information(self, "游戏结束", "🎉 恭喜你赢了！🎉")
        else:
            QMessageBox.information(self, "游戏结束", f"😢 {winner_name} 赢了")
        
        self.reset_to_room()
    
    def reset_to_mode_selection(self):
        """重置到模式选择"""
        self.game_mode = None
        self.game_running = False
        
        self.single_btn.setEnabled(True)
        self.online_btn.setEnabled(True)
        self.start_btn.setEnabled(False)
        self.ready_btn.hide()
        self.play_btn.setEnabled(False)
        self.pass_btn.setEnabled(False)
        
        self.mode_label.setText("🎮 选择模式")
        self.status_label.setText("🏠 请选择游戏模式")
        self.turn_label.setText("")
    
    def reset_to_room(self):
        """重置到房间状态"""
        self.game_running = False
        self.play_btn.setEnabled(False)
        self.pass_btn.setEnabled(False)
        self.ready_btn.show()
        self.ready_btn.setEnabled(True)
        self.ready_btn.setText("✅ 准备")
    
    def format_card(self, card) -> str:
        """格式化单张卡牌"""
        if isinstance(card, Card):
            return str(card)
        elif isinstance(card, list):
            suit, rank = card
            suit_map = {'♥': '♥', '♠': '♠', '♦': '♦', '♣': '♣'}
            if rank == 'Joker1':
                return '🐱小王'
            elif rank == 'Joker2':
                return '🃏大王'
            return f"{suit_map.get(suit, suit)}{rank}"
        return str(card)
    
    # ============ 单机模式 ============
    def start_game(self):
        """开始游戏（单机模式）"""
        if self.game_mode != "single":
            return
        
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
            
            self.play_area.clear_all_cards()
            self.update_display()
            
            self.start_btn.setEnabled(False)
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
        """更新显示"""
        if self.game_mode == "single":
            cards = self.game_data.get("Human", [])
        else:
            return
        
        self.ai1_panel.update_count(len(self.game_data.get("AI1", [])))
        self.ai2_panel.update_count(len(self.game_data.get("AI2", [])))
        
        self.clear_layout(self.cards_layout)
        self.card_buttons = []
        
        for i, card in enumerate(cards):
            btn = CardButton(card, i)
            btn.clicked.connect(lambda checked, b=btn: b.toggle_select())
            self.cards_layout.addWidget(btn)
            self.card_buttons.append(btn)
        
        self.player_count_label.setText(f"{len(cards)} 张")
        
        if self.last_combination:
            self.last_label.setText(f"📋 上家牌: {' '.join(str(c) for c in self.last_combination)}")
        else:
            self.last_label.setText("📋 上家牌: 无")
    
    def update_hand_display(self, cards: list):
        """更新手牌显示（联机模式）"""
        self.clear_layout(self.cards_layout)
        self.card_buttons = []
        
        # 将卡牌数据转换为 Card 对象
        card_objects = []
        for card_data in cards:
            if isinstance(card_data, list):
                suit, rank = card_data
                card_objects.append(Card(suit, rank))
            else:
                card_objects.append(card_data)
        
        card_objects.sort()
        
        for i, card in enumerate(card_objects):
            btn = CardButton(card, i)
            btn.clicked.connect(lambda checked, b=btn: b.toggle_select())
            self.cards_layout.addWidget(btn)
            self.card_buttons.append(btn)
        
        self.player_count_label.setText(f"{len(card_objects)} 张")
    
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
        """出牌"""
        if self.game_mode == "single":
            self.play_cards_single()
        elif self.game_mode == "online":
            self.play_cards_online()
    
    def play_cards_single(self):
        """单机模式出牌"""
        if self.current_player != "Human" or not self.game_running:
            return
        
        selected = self.get_selected_cards()
        if not selected:
            QMessageBox.warning(self, "提示", "请先选择要出的牌！")
            return
        
        info = PatternDetector.detect(selected)
        if not info['valid']:
            QMessageBox.warning(self, "提示", "无效的牌型！")
            return
        
        if self.last_combination and not PlayComparator.can_beat(selected, self.last_combination):
            QMessageBox.warning(self, "提示", "不能压过上家的牌！")
            return
        
        cards_text = self.format_cards_text(selected)
        self.game_log.add_log(f"👤 玩家出牌: {cards_text} ({len(selected)}张)")
        self.player_panel.show_action(f"出牌\n{len(selected)}张", True)
        
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
    
    def play_cards_online(self):
        """联机模式出牌"""
        if self.current_player != "Human" or not self.game_running:
            return
        
        selected = self.get_selected_cards()
        if not selected:
            QMessageBox.warning(self, "提示", "请先选择要出的牌！")
            return
        
        info = PatternDetector.detect(selected)
        if not info['valid']:
            QMessageBox.warning(self, "提示", "无效的牌型！")
            return
        
        if self.last_combination:
            # 需要将 last_combination 转换为 Card 对象进行比较
            last_cards = []
            for card_data in self.last_combination:
                if isinstance(card_data, list):
                    suit, rank = card_data
                    last_cards.append(Card(suit, rank))
                else:
                    last_cards.append(card_data)
            
            if not PlayComparator.can_beat(selected, last_cards):
                QMessageBox.warning(self, "提示", "不能压过上家的牌！")
                return
        
        # 发送出牌
        cards_data = []
        for card in selected:
            cards_data.append([card.suit, card.rank])
        
        self.network_client.send("play_cards", {"cards": cards_data})
        
        self.clear_selection()
        self.play_btn.setEnabled(False)
        self.pass_btn.setEnabled(False)
        self.turn_label.setText("⏳ 等待其他玩家...")
    
    def pass_turn(self):
        """过牌"""
        if self.game_mode == "single":
            self.pass_turn_single()
        elif self.game_mode == "online":
            self.pass_turn_online()
    
    def pass_turn_single(self):
        """单机模式过牌"""
        if self.current_player != "Human" or not self.game_running:
            return
        
        if self.last_player == "Human":
            QMessageBox.information(self, "提示", "你是最后出牌的人，不能过牌！")
            return
        
        self.game_log.add_log(f"👤 玩家选择过牌")
        self.player_panel.show_action("过牌", False)
        
        self.pass_count += 1
        
        if self.pass_count >= 2:
            self.last_combination = []
            self.pass_count = 0
            self.current_player = self.last_player
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
    
    def pass_turn_online(self):
        """联机模式过牌"""
        if self.current_player != "Human" or not self.game_running:
            return
        
        if not self.last_combination:
            QMessageBox.information(self, "提示", "首轮不能过牌！")
            return
        
        self.network_client.send("play_cards", {"cards": []})
        
        self.play_btn.setEnabled(False)
        self.pass_btn.setEnabled(False)
        self.turn_label.setText("⏳ 等待其他玩家...")
        self.game_log.add_log("⏭️ 你选择过牌")
    
    def ai_play(self):
        """AI出牌"""
        if self.game_mode != "single":
            return
        
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
            
            self.current_player = "AI2" if self.current_player == "AI1" else "Human"
        else:
            self.game_log.add_log(f"🤖 {self.current_player} 选择过牌")
            panel.show_action("过牌", False)
            
            self.pass_count += 1
            panel.set_status("过牌", False)
            
            if self.pass_count >= 2:
                self.last_combination = []
                self.pass_count = 0
                self.current_player = self.last_player
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
                self.current_player = "AI2" if self.current_player == "AI1" else "Human"
        
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
    
    def format_cards_text(self, cards):
        if not cards:
            return ""
        if len(cards) <= 5:
            return " ".join(str(c) for c in cards)
        return f"{' '.join(str(c) for c in cards[:3])} ... {str(cards[-1])}"
    
    def game_over(self, winner):
        self.game_running = False
        self.play_btn.setEnabled(False)
        self.pass_btn.setEnabled(False)
        self.start_btn.setEnabled(True)
        
        if winner == "Human":
            self.game_log.add_log("🎉 恭喜！玩家获胜！")
            QMessageBox.information(self, "游戏结束", "🎉 恭喜你赢了！🎉")
        else:
            self.game_log.add_log(f"😢 {winner} 获胜！")
            QMessageBox.information(self, "游戏结束", f"😢 {winner} 赢了")
    
    def closeEvent(self, event):
        """关闭窗口时清理"""
        if self.network_client:
            self.network_client.stop()
        event.accept()
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'game_log') and hasattr(self, 'play_area'):
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