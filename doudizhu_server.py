# doudizhu_server.py - 斗地主联机服务器
import asyncio
import json
import random
import uuid
import sys
import os
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

# 尝试导入 websockets，如果失败则给出友好提示
try:
    import websockets
    from websockets.server import WebSocketServerProtocol
except ImportError:
    print("=" * 50)
    print("错误：未安装 websockets 库")
    print("请运行以下命令安装：")
    print("  pip install websockets")
    print("=" * 50)
    sys.exit(1)

# 导入游戏核心逻辑
try:
    from doudizhu_core import (
        Card, DeckManager, PatternDetector, PlayComparator,
        HandAnalyzer, GamePhase, CardType, ExpertAIPlayer, Difficulty
    )
except ImportError:
    print("=" * 50)
    print("错误：未找到 doudizhu_core.py")
    print("请确保 doudizhu_core.py 在同一目录下")
    print("=" * 50)
    sys.exit(1)


# ============ 数据模型 ============
class PlayerStatus(Enum):
    WAITING = "waiting"
    READY = "ready"
    PLAYING = "playing"
    DISCONNECTED = "disconnected"


@dataclass
class RoomPlayer:
    """房间内的玩家"""
    player_id: str
    name: str
    websocket: Optional[WebSocketServerProtocol] = None
    status: PlayerStatus = PlayerStatus.WAITING
    cards: Optional[List[Card]] = None
    is_landlord: bool = False
    is_ai: bool = False
    
    def to_dict(self, hide_cards: bool = True) -> dict:
        result = {
            "player_id": self.player_id,
            "name": self.name,
            "status": self.status.value,
            "is_landlord": self.is_landlord,
            "is_ai": self.is_ai,
            "card_count": len(self.cards) if self.cards else 0
        }
        if not hide_cards and self.cards:
            result["cards"] = [[c.suit, c.rank] for c in self.cards]
        return result


@dataclass
class GameRoom:
    """游戏房间"""
    room_id: str
    room_name: str
    players: Dict[str, RoomPlayer]
    max_players: int = 3
    landlord_cards: Optional[List[Card]] = None
    landlord_id: Optional[str] = None
    current_player_id: Optional[str] = None
    last_play: Optional[List[Card]] = None
    last_player_id: Optional[str] = None
    pass_count: int = 0
    phase: GamePhase = GamePhase.BIDDING
    game_over: bool = False
    winner_id: Optional[str] = None
    player_order: Optional[List[str]] = None
    ai_difficulty: str = "hard"
    
    def to_dict(self, player_id: str = None) -> dict:
        """转换为字典，根据请求者决定是否隐藏手牌"""
        result = {
            "room_id": self.room_id,
            "room_name": self.room_name,
            "phase": self.phase.value,
            "landlord_id": self.landlord_id,
            "current_player_id": self.current_player_id,
            "last_play": [[c.suit, c.rank] for c in self.last_play] if self.last_play else [],
            "last_player_id": self.last_player_id,
            "pass_count": self.pass_count,
            "game_over": self.game_over,
            "winner_id": self.winner_id,
            "player_order": self.player_order,
            "landlord_cards": [[c.suit, c.rank] for c in self.landlord_cards] if self.landlord_cards and self.phase == GamePhase.BIDDING else [],
            "players": {}
        }
        
        for pid, player in self.players.items():
            hide_cards = (pid != player_id)
            result["players"][pid] = player.to_dict(hide_cards=hide_cards)
        
        return result


# ============ 游戏逻辑处理器 ============
class GameLogicHandler:
    """游戏逻辑处理器"""
    
    @staticmethod
    def validate_play(room: GameRoom, player_id: str, cards: List[Card]) -> Tuple[bool, str]:
        """验证出牌是否合法"""
        if room.phase != GamePhase.PLAYING:
            return False, "游戏不在进行中"
        
        if player_id != room.current_player_id:
            return False, "不是你的回合"
        
        player = room.players[player_id]
        
        # 过牌
        if not cards:
            if not room.last_play:
                return False, "首轮不能过牌"
            return True, ""
        
        # 检查牌型
        play_info = PatternDetector.detect(cards)
        if not play_info['valid']:
            return False, "无效的牌型"
        
        # 检查是否能压过上家
        if not PlayComparator.can_beat(cards, room.last_play):
            return False, "不能压过上家的牌"
        
        # 检查手牌
        if not GameLogicHandler._has_cards(player, cards):
            return False, "手牌中没有这些牌"
        
        return True, ""
    
    @staticmethod
    def _has_cards(player: RoomPlayer, cards: List[Card]) -> bool:
        """检查玩家是否有这些牌"""
        temp = player.cards.copy()
        for card in cards:
            found = False
            for i, c in enumerate(temp):
                if c.rank == card.rank and c.suit == card.suit:
                    temp.pop(i)
                    found = True
                    break
            if not found:
                return False
        return True
    
    @staticmethod
    def execute_play(room: GameRoom, player_id: str, cards: List[Card]):
        """执行出牌"""
        player = room.players[player_id]
        
        if cards:
            # 出牌
            GameLogicHandler._remove_cards(player, cards)
            room.last_play = cards
            room.last_player_id = player_id
            room.pass_count = 0
            
            # 检查胜利
            if not player.cards:
                room.phase = GamePhase.FINISHED
                room.game_over = True
                room.winner_id = player_id
                return
        else:
            # 过牌
            room.pass_count += 1
            
            if room.pass_count >= 2:
                # 一轮结束
                room.last_play = []
                room.pass_count = 0
                room.current_player_id = room.last_player_id
                return
        
        # 下一个玩家
        GameLogicHandler._next_player(room)
    
    @staticmethod
    def _remove_cards(player: RoomPlayer, cards: List[Card]):
        """移除打出的牌"""
        for card in cards:
            for i, c in enumerate(player.cards):
                if c.rank == card.rank and c.suit == card.suit:
                    player.cards.pop(i)
                    break
    
    @staticmethod
    def _next_player(room: GameRoom):
        """轮到下一个玩家"""
        if not room.player_order:
            return
        idx = room.player_order.index(room.current_player_id)
        room.current_player_id = room.player_order[(idx + 1) % 3]
    
    @staticmethod
    def start_bidding(room: GameRoom):
        """开始叫地主阶段"""
        room.phase = GamePhase.BIDDING
        room.current_player_id = random.choice(list(room.players.keys()))
    
    @staticmethod
    def set_landlord(room: GameRoom, landlord_id: str):
        """设置地主"""
        room.landlord_id = landlord_id
        landlord = room.players[landlord_id]
        landlord.is_landlord = True
        landlord.cards.extend(room.landlord_cards)
        landlord.cards.sort()
        
        room.phase = GamePhase.PLAYING
        room.current_player_id = landlord_id
        room.last_play = []
        room.pass_count = 0
        
        # 设置出牌顺序
        all_players = list(room.players.keys())
        landlord_idx = all_players.index(landlord_id)
        room.player_order = []
        for i in range(3):
            room.player_order.append(all_players[(landlord_idx + i) % 3])
    
    @staticmethod
    def add_ai_player(room: GameRoom, position: int = None) -> str:
        """添加AI玩家"""
        ai_id = f"AI_{uuid.uuid4().hex[:6]}"
        ai_name = f"电脑{len([p for p in room.players.values() if p.is_ai]) + 1}"
        
        room.players[ai_id] = RoomPlayer(
            player_id=ai_id,
            name=ai_name,
            is_ai=True,
            status=PlayerStatus.READY
        )
        return ai_id
    
    @staticmethod
    def get_ai_play(room: GameRoom, ai_id: str) -> List[Card]:
        """获取AI出牌决策"""
        ai_player = room.players[ai_id]
        if not ai_player.cards:
            return []
        
        difficulty = getattr(Difficulty, room.ai_difficulty.upper(), Difficulty.HARD)
        temp_ai = ExpertAIPlayer(ai_player.name, difficulty)
        temp_ai.cards = ai_player.cards.copy()
        
        play = temp_ai.get_play(room.last_play)
        
        if not room.last_play and not play:
            play = [min(ai_player.cards)]
        
        return play


# ============ 房间管理器 ============
class RoomManager:
    """房间管理器"""
    
    def __init__(self):
        self.rooms: Dict[str, GameRoom] = {}
        self.player_rooms: Dict[str, str] = {}
    
    def create_room(self, room_name: str, creator_id: str, creator_name: str) -> GameRoom:
        """创建房间"""
        room_id = uuid.uuid4().hex[:8].upper()
        room = GameRoom(
            room_id=room_id,
            room_name=room_name,
            players={},
            player_order=[]
        )
        
        player = RoomPlayer(
            player_id=creator_id,
            name=creator_name,
            status=PlayerStatus.WAITING
        )
        room.players[creator_id] = player
        
        self.rooms[room_id] = room
        self.player_rooms[creator_id] = room_id
        
        return room
    
    def join_room(self, room_id: str, player_id: str, player_name: str) -> Optional[GameRoom]:
        """加入房间"""
        room = self.rooms.get(room_id)
        if not room:
            return None
        
        if len(room.players) >= room.max_players:
            return None
        
        player = RoomPlayer(
            player_id=player_id,
            name=player_name,
            status=PlayerStatus.WAITING
        )
        room.players[player_id] = player
        self.player_rooms[player_id] = room_id
        
        return room
    
    def leave_room(self, player_id: str) -> Optional[GameRoom]:
        """离开房间"""
        room_id = self.player_rooms.get(player_id)
        if not room_id:
            return None
        
        room = self.rooms.get(room_id)
        if room:
            if player_id in room.players:
                del room.players[player_id]
            
            if not room.players:
                del self.rooms[room_id]
        
        del self.player_rooms[player_id]
        return room
    
    def get_player_room(self, player_id: str) -> Optional[GameRoom]:
        """获取玩家所在的房间"""
        room_id = self.player_rooms.get(player_id)
        return self.rooms.get(room_id) if room_id else None
    
    def fill_with_ai(self, room: GameRoom):
        """用AI填充房间空位"""
        while len(room.players) < room.max_players:
            ai_id = GameLogicHandler.add_ai_player(room)
            self.player_rooms[ai_id] = room.room_id


# ============ WebSocket 服务器 ============
class DoudizhuServer:
    """斗地主WebSocket服务器"""
    
    def __init__(self, host: str = "localhost", port: int = 8765):
        self.host = host
        self.port = port
        self.room_manager = RoomManager()
        self.connections: Dict[str, WebSocketServerProtocol] = {}
    
    async def handle_connection(self, websocket: WebSocketServerProtocol):
        """处理客户端连接"""
        player_id = str(uuid.uuid4())
        self.connections[player_id] = websocket
        
        # 发送连接成功消息
        await self.send_response(websocket, "connected", {"player_id": player_id})
        
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    await self.handle_message(player_id, websocket, data)
                except json.JSONDecodeError:
                    await self.send_error(websocket, "无效的JSON格式")
                except Exception as e:
                    print(f"处理消息错误: {e}")
                    await self.send_error(websocket, str(e))
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            await self.handle_disconnect(player_id)
    
    async def handle_message(self, player_id: str, websocket: WebSocketServerProtocol, data: dict):
        """处理客户端消息"""
        action = data.get("action")
        
        handlers = {
            "create_room": self.handle_create_room,
            "join_room": self.handle_join_room,
            "leave_room": self.handle_leave_room,
            "ready": self.handle_ready,
            "start_game": self.handle_start_game,
            "bid_landlord": self.handle_bid_landlord,
            "play_cards": self.handle_play_cards,
            "get_room_list": self.handle_get_room_list,
            "chat": self.handle_chat,
        }
        
        handler = handlers.get(action)
        if handler:
            await handler(player_id, websocket, data)
        else:
            await self.send_error(websocket, f"未知操作: {action}")
    
    async def handle_create_room(self, player_id: str, websocket: WebSocketServerProtocol, data: dict):
        room_name = data.get("room_name", "游戏房间")
        player_name = data.get("player_name", f"玩家{player_id[:6]}")
        
        room = self.room_manager.create_room(room_name, player_id, player_name)
        
        await self.send_response(websocket, "room_created", {
            "room_id": room.room_id,
            "room": room.to_dict(player_id)
        })
        
        await self.broadcast_room_list()
    
    async def handle_join_room(self, player_id: str, websocket: WebSocketServerProtocol, data: dict):
        room_id = data.get("room_id")
        player_name = data.get("player_name", f"玩家{player_id[:6]}")
        
        room = self.room_manager.join_room(room_id, player_id, player_name)
        if not room:
            await self.send_error(websocket, "房间不存在或已满")
            return
        
        await self.send_response(websocket, "room_joined", {
            "room": room.to_dict(player_id)
        })
        
        await self.broadcast_to_room(room.room_id, "player_joined", {
            "player": room.players[player_id].to_dict()
        }, exclude_player=player_id)
        
        await self.broadcast_room_list()
    
    async def handle_leave_room(self, player_id: str, websocket: WebSocketServerProtocol, data: dict):
        room = self.room_manager.leave_room(player_id)
        
        await self.send_response(websocket, "room_left", {})
        
        if room:
            await self.broadcast_to_room(room.room_id, "player_left", {
                "player_id": player_id
            })
            await self.broadcast_room_list()
    
    async def handle_ready(self, player_id: str, websocket: WebSocketServerProtocol, data: dict):
        room = self.room_manager.get_player_room(player_id)
        if not room:
            await self.send_error(websocket, "不在房间中")
            return
        
        player = room.players.get(player_id)
        if player:
            player.status = PlayerStatus.READY
        
        await self.broadcast_to_room(room.room_id, "player_ready", {
            "player_id": player_id,
            "players": {pid: p.to_dict() for pid, p in room.players.items()}
        })
    
    async def handle_start_game(self, player_id: str, websocket: WebSocketServerProtocol, data: dict):
        room = self.room_manager.get_player_room(player_id)
        if not room:
            await self.send_error(websocket, "不在房间中")
            return
        
        all_ready = all(p.status == PlayerStatus.READY for p in room.players.values())
        if not all_ready:
            await self.send_error(websocket, "还有玩家未准备")
            return
        
        self.room_manager.fill_with_ai(room)
        
        dealt = DeckManager.deal()
        for i, pid in enumerate(room.players.keys()):
            player_cards = dealt[["Human", "AI1", "AI2"][i]]
            room.players[pid].cards = player_cards
            room.players[pid].status = PlayerStatus.PLAYING
        
        room.landlord_cards = dealt["Landlord"]
        GameLogicHandler.start_bidding(room)
        
        await self.broadcast_to_room(room.room_id, "game_started", {
            "room": room.to_dict()
        })
        
        await self.send_to_player(room.current_player_id, "your_turn_bid", {
            "landlord_cards": [[c.suit, c.rank] for c in room.landlord_cards]
        })
        
        await self.process_ai_bidding(room)
    
    async def handle_bid_landlord(self, player_id: str, websocket: WebSocketServerProtocol, data: dict):
        room = self.room_manager.get_player_room(player_id)
        if not room or room.phase != GamePhase.BIDDING:
            await self.send_error(websocket, "不在叫地主阶段")
            return
        
        want_landlord = data.get("want_landlord", False)
        
        if want_landlord:
            GameLogicHandler.set_landlord(room, player_id)
            
            await self.broadcast_to_room(room.room_id, "landlord_set", {
                "landlord_id": player_id,
                "landlord_cards": [[c.suit, c.rank] for c in room.landlord_cards],
                "room": room.to_dict()
            })
            
            await self.send_to_player(player_id, "your_turn_play", {
                "last_play": []
            })
            
            await self.process_ai_play(room)
        else:
            GameLogicHandler._next_player(room)
            
            await self.broadcast_to_room(room.room_id, "bid_passed", {
                "player_id": player_id,
                "current_player_id": room.current_player_id
            })
            
            if room.pass_count >= 2:
                await self.redeal(room)
            else:
                await self.send_to_player(room.current_player_id, "your_turn_bid", {
                    "landlord_cards": [[c.suit, c.rank] for c in room.landlord_cards]
                })
                await self.process_ai_bidding(room)
    
    async def handle_play_cards(self, player_id: str, websocket: WebSocketServerProtocol, data: dict):
        room = self.room_manager.get_player_room(player_id)
        if not room or room.phase != GamePhase.PLAYING:
            await self.send_error(websocket, "不在出牌阶段")
            return
        
        cards_data = data.get("cards", [])
        
        # 解析卡牌
        cards = []
        if cards_data:
            for card_info in cards_data:
                suit, rank = card_info
                for c in room.players[player_id].cards:
                    if c.suit == suit and c.rank == rank:
                        cards.append(c)
                        break
        
        valid, error = GameLogicHandler.validate_play(room, player_id, cards)
        if not valid:
            await self.send_error(websocket, error)
            return
        
        GameLogicHandler.execute_play(room, player_id, cards)
        
        play_type = PatternDetector.detect(cards)['type'].value if cards else "过牌"
        
        await self.broadcast_to_room(room.room_id, "cards_played", {
            "player_id": player_id,
            "cards": [[c.suit, c.rank] for c in cards],
            "play_type": play_type,
            "room": room.to_dict()
        })
        
        if room.game_over:
            await self.broadcast_to_room(room.room_id, "game_over", {
                "winner_id": room.winner_id,
                "winner_name": room.players[room.winner_id].name
            })
            return
        
        await self.send_to_player(room.current_player_id, "your_turn_play", {
            "last_play": [[c.suit, c.rank] for c in room.last_play] if room.last_play else []
        })
        
        await self.process_ai_play(room)
    
    async def handle_get_room_list(self, player_id: str, websocket: WebSocketServerProtocol, data: dict):
        rooms = []
        for room in self.room_manager.rooms.values():
            rooms.append({
                "room_id": room.room_id,
                "room_name": room.room_name,
                "player_count": len(room.players),
                "max_players": room.max_players,
                "phase": room.phase.value
            })
        
        await self.send_response(websocket, "room_list", {"rooms": rooms})
    
    async def handle_chat(self, player_id: str, websocket: WebSocketServerProtocol, data: dict):
        room = self.room_manager.get_player_room(player_id)
        if not room:
            return
        
        message = data.get("message", "")
        player = room.players.get(player_id)
        
        await self.broadcast_to_room(room.room_id, "chat_message", {
            "player_id": player_id,
            "player_name": player.name if player else "未知",
            "message": message
        })
    
    async def handle_disconnect(self, player_id: str):
        if player_id in self.connections:
            del self.connections[player_id]
        
        room = self.room_manager.leave_room(player_id)
        if room:
            await self.broadcast_to_room(room.room_id, "player_disconnected", {
                "player_id": player_id
            })
            await self.broadcast_room_list()
    
    async def process_ai_bidding(self, room: GameRoom):
        current_player = room.players.get(room.current_player_id)
        if current_player and current_player.is_ai:
            await asyncio.sleep(1)
            
            temp_ai = ExpertAIPlayer(current_player.name, Difficulty.HARD)
            temp_ai.cards = current_player.cards.copy()
            
            want_landlord = temp_ai.should_become_landlord(room.landlord_cards)
            
            await self.handle_bid_landlord(room.current_player_id, None, {
                "want_landlord": want_landlord
            })
    
    async def process_ai_play(self, room: GameRoom):
        current_player = room.players.get(room.current_player_id)
        if current_player and current_player.is_ai and not room.game_over:
            await asyncio.sleep(0.5)
            
            play = GameLogicHandler.get_ai_play(room, room.current_player_id)
            cards_data = [[c.suit, c.rank] for c in play] if play else []
            
            await self.handle_play_cards(room.current_player_id, None, {
                "cards": cards_data
            })
    
    async def redeal(self, room: GameRoom):
        dealt = DeckManager.deal()
        for i, pid in enumerate(room.players.keys()):
            room.players[pid].cards = dealt[["Human", "AI1", "AI2"][i]]
        
        room.landlord_cards = dealt["Landlord"]
        room.pass_count = 0
        GameLogicHandler.start_bidding(room)
        
        await self.broadcast_to_room(room.room_id, "game_redealt", {
            "room": room.to_dict()
        })
        
        await self.send_to_player(room.current_player_id, "your_turn_bid", {
            "landlord_cards": [[c.suit, c.rank] for c in room.landlord_cards]
        })
    
    async def send_response(self, websocket: WebSocketServerProtocol, action: str, data: dict):
        await websocket.send(json.dumps({
            "action": action,
            "success": True,
            "data": data
        }))
    
    async def send_error(self, websocket: WebSocketServerProtocol, message: str):
        await websocket.send(json.dumps({
            "action": "error",
            "success": False,
            "message": message
        }))
    
    async def send_to_player(self, player_id: str, action: str, data: dict):
        websocket = self.connections.get(player_id)
        if websocket:
            await websocket.send(json.dumps({
                "action": action,
                "data": data
            }))
    
    async def broadcast_to_room(self, room_id: str, action: str, data: dict, exclude_player: str = None):
        room = self.room_manager.rooms.get(room_id)
        if not room:
            return
        
        for player_id in room.players.keys():
            if player_id == exclude_player:
                continue
            if room.players[player_id].is_ai:
                continue
            await self.send_to_player(player_id, action, data)
    
    async def broadcast_room_list(self):
        rooms = []
        for room in self.room_manager.rooms.values():
            if room.phase == GamePhase.BIDDING:
                rooms.append({
                    "room_id": room.room_id,
                    "room_name": room.room_name,
                    "player_count": len(room.players),
                    "max_players": room.max_players
                })
        
        for player_id, websocket in self.connections.items():
            if player_id not in self.room_manager.player_rooms:
                await self.send_response(websocket, "room_list_update", {"rooms": rooms})
    
    async def start(self):
        print(f"🃏 斗地主服务器启动中...")
        print(f"📡 监听地址: ws://{self.host}:{self.port}")
        
        async with websockets.serve(self.handle_connection, self.host, self.port):
            print(f"✅ 服务器已启动！")
            await asyncio.Future()


# ============ 主程序 ============
async def main():
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "server":
        server = DoudizhuServer(host="0.0.0.0", port=8765)
        await server.start()
    else:
        print("=" * 50)
        print("🃏 斗地主联机服务器")
        print("=" * 50)
        print("使用方法:")
        print("  python doudizhu_server.py server  # 启动服务器")
        print("=" * 50)
        print("\n确保已安装依赖:")
        print("  pip install websockets")
        print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())