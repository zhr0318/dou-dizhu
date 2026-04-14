# doudizhu_client.py - 斗地主联机客户端（终端版）
import asyncio
import json
import sys
import os
from typing import List, Dict, Optional
from dataclasses import dataclass
from enum import Enum

try:
    import websockets
except ImportError:
    print("请安装 websockets: pip install websockets")
    sys.exit(1)

# 尝试导入游戏核心
try:
    from doudizhu_core import Card, PatternDetector, HandAnalyzer
except ImportError:
    print("警告: 未找到 doudizhu_core.py，将使用简化模式")


class ClientState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    IN_ROOM = "in_room"
    READY = "ready"
    PLAYING = "playing"
    BIDDING = "bidding"
    MY_TURN = "my_turn"


@dataclass
class GameState:
    """游戏状态"""
    room_id: str = None
    room_name: str = None
    player_id: str = None
    player_name: str = None
    players: Dict = None
    my_cards: List = None
    landlord_id: str = None
    landlord_cards: List = None
    current_player_id: str = None
    last_play: List = None
    phase: str = None
    game_over: bool = False
    winner_id: str = None


class DoudizhuClient:
    """斗地主客户端"""
    
    def __init__(self, server_url: str = "ws://localhost:8765"):
        self.server_url = server_url
        self.websocket = None
        self.state = ClientState.DISCONNECTED
        self.game = GameState()
        self.callbacks = {}
        self.running = True
        
        # 注册默认回调
        self.on("connected", self._on_connected)
        self.on("error", self._on_error)
        self.on("room_created", self._on_room_created)
        self.on("room_joined", self._on_room_joined)
        self.on("room_left", self._on_room_left)
        self.on("player_joined", self._on_player_joined)
        self.on("player_left", self._on_player_left)
        self.on("player_ready", self._on_player_ready)
        self.on("game_started", self._on_game_started)
        self.on("your_turn_bid", self._on_your_turn_bid)
        self.on("landlord_set", self._on_landlord_set)
        self.on("your_turn_play", self._on_your_turn_play)
        self.on("cards_played", self._on_cards_played)
        self.on("game_over", self._on_game_over)
        self.on("room_list", self._on_room_list)
        self.on("room_list_update", self._on_room_list)
        self.on("chat_message", self._on_chat_message)
    
    # ============ 事件回调 ============
    def on(self, action: str, callback):
        """注册事件回调"""
        self.callbacks[action] = callback
    
    async def _trigger(self, action: str, data: dict):
        """触发事件回调"""
        if action in self.callbacks:
            await self.callbacks[action](data)
    
    async def _on_connected(self, data: dict):
        self.state = ClientState.CONNECTED
        self.game.player_id = data.get("player_id")
        print(f"✅ 已连接到服务器 (ID: {self.game.player_id[:8]})")
    
    async def _on_error(self, data: dict):
        print(f"❌ 错误: {data}")
    
    async def _on_room_created(self, data: dict):
        self.state = ClientState.IN_ROOM
        self.game.room_id = data["room_id"]
        self._update_room_state(data["room"])
        print(f"✅ 房间创建成功! 房间号: {self.game.room_id}")
        print(f"   等待其他玩家加入...")
    
    async def _on_room_joined(self, data: dict):
        self.state = ClientState.IN_ROOM
        self._update_room_state(data["room"])
        print(f"✅ 成功加入房间: {self.game.room_name}")
        self._print_room_info()
    
    async def _on_room_left(self, data: dict):
        self.state = ClientState.CONNECTED
        self.game = GameState()
        print(f"已离开房间")
    
    async def _on_player_joined(self, data: dict):
        player = data["player"]
        self.game.players[player["player_id"]] = player
        print(f"👤 {player['name']} 加入了房间 ({len(self.game.players)}/3)")
    
    async def _on_player_left(self, data: dict):
        player_id = data["player_id"]
        if player_id in self.game.players:
            name = self.game.players[player_id]["name"]
            del self.game.players[player_id]
            print(f"👋 {name} 离开了房间")
    
    async def _on_player_ready(self, data: dict):
        self.game.players = data["players"]
        ready_count = sum(1 for p in self.game.players.values() if p["status"] == "ready")
        print(f"✅ 玩家准备 ({ready_count}/{len(self.game.players)})")
    
    async def _on_game_started(self, data: dict):
        self.state = ClientState.PLAYING
        self._update_room_state(data["room"])
        print(f"\n{'='*50}")
        print(f"🎮 游戏开始!")
        print(f"{'='*50}")
        print(f"你的手牌: {self._format_cards(self.game.my_cards)}")
    
    async def _on_your_turn_bid(self, data: dict):
        self.state = ClientState.BIDDING
        self.game.landlord_cards = data.get("landlord_cards", [])
        print(f"\n🎯 轮到你了!")
        print(f"底牌: {self._format_cards(self.game.landlord_cards)}")
        print(f"你的手牌: {self._format_cards(self.game.my_cards)}")
        print(f"是否叫地主? (输入 y/n): ", end="", flush=True)
    
    async def _on_landlord_set(self, data: dict):
        self.game.landlord_id = data["landlord_id"]
        self.game.landlord_cards = data["landlord_cards"]
        self._update_room_state(data["room"])
        
        landlord_name = self.game.players[self.game.landlord_id]["name"]
        print(f"\n👑 地主是: {landlord_name}")
        print(f"底牌: {self._format_cards(self.game.landlord_cards)}")
        if self.game.landlord_id == self.game.player_id:
            print(f"你的新手牌: {self._format_cards(self.game.my_cards)}")
    
    async def _on_your_turn_play(self, data: dict):
        self.state = ClientState.MY_TURN
        self.game.last_play = data.get("last_play", [])
        
        print(f"\n🎯 轮到你了!")
        print(f"你的手牌: {self._format_cards(self.game.my_cards)}")
        if self.game.last_play:
            print(f"上家出牌: {self._format_cards(self.game.last_play)}")
            print(f"输入出牌 (格式: 0 1 2 或 pass): ", end="", flush=True)
        else:
            print(f"输入出牌 (格式: 0 1 2): ", end="", flush=True)
    
    async def _on_cards_played(self, data: dict):
        player_id = data["player_id"]
        cards = data["cards"]
        play_type = data["play_type"]
        self._update_room_state(data["room"])
        
        player_name = self.game.players[player_id]["name"]
        if cards:
            print(f"\n🎴 {player_name} 出牌: {self._format_cards(cards)} [{play_type}]")
        else:
            print(f"\n⏭️ {player_name} 过牌")
        
        if player_id != self.game.player_id:
            self._print_game_status()
    
    async def _on_game_over(self, data: dict):
        self.state = ClientState.IN_ROOM
        winner_id = data["winner_id"]
        winner_name = data["winner_name"]
        
        print(f"\n{'='*50}")
        print(f"🏆 游戏结束! {winner_name} 获胜!")
        print(f"{'='*50}")
        
        is_winner = (winner_id == self.game.player_id)
        is_landlord_win = (winner_id == self.game.landlord_id)
        
        if is_winner:
            print(f"🎉 恭喜你赢了!")
        else:
            print(f"😢 你输了")
    
    async def _on_room_list(self, data: dict):
        rooms = data.get("rooms", [])
        print(f"\n📋 可用房间:")
        if rooms:
            for room in rooms:
                print(f"  {room['room_id']}: {room['room_name']} ({room['player_count']}/{room['max_players']})")
        else:
            print(f"  暂无房间")
    
    async def _on_chat_message(self, data: dict):
        print(f"\n💬 {data['player_name']}: {data['message']}")
    
    # ============ 辅助方法 ============
    def _update_room_state(self, room_data: dict):
        """更新房间状态"""
        self.game.room_name = room_data.get("room_name")
        self.game.phase = room_data.get("phase")
        self.game.landlord_id = room_data.get("landlord_id")
        self.game.current_player_id = room_data.get("current_player_id")
        self.game.last_play = room_data.get("last_play", [])
        self.game.game_over = room_data.get("game_over", False)
        self.game.winner_id = room_data.get("winner_id")
        
        players = room_data.get("players", {})
        self.game.players = {}
        for pid, pdata in players.items():
            self.game.players[pid] = pdata
            if pid == self.game.player_id and "cards" in pdata:
                self.game.my_cards = pdata["cards"]
    
    def _format_cards(self, cards: List) -> str:
        """格式化卡牌显示"""
        if not cards:
            return "[]"
        
        suit_map = {'♥': '♥', '♠': '♠', '♦': '♦', '♣': '♣'}
        rank_names = {'Joker1': '小王', 'Joker2': '大王'}
        
        result = []
        for card in cards:
            if isinstance(card, list):
                suit, rank = card
                if rank in rank_names:
                    result.append(rank_names[rank])
                else:
                    result.append(f"{suit_map.get(suit, suit)}{rank}")
            else:
                result.append(str(card))
        return " ".join(result)
    
    def _print_room_info(self):
        """打印房间信息"""
        print(f"\n📌 房间: {self.game.room_name} ({self.game.room_id})")
        print(f"玩家列表:")
        for pid, player in self.game.players.items():
            status_icon = "✅" if player["status"] == "ready" else "⏳"
            landlord_icon = "👑" if player["is_landlord"] else ""
            you_icon = "(你)" if pid == self.game.player_id else ""
            print(f"  {status_icon} {player['name']} {landlord_icon} {you_icon}")
    
    def _print_game_status(self):
        """打印游戏状态"""
        print(f"\n📊 当前状态:")
        for pid, player in self.game.players.items():
            name = player["name"]
            cards_count = player["card_count"]
            landlord_icon = "👑" if player["is_landlord"] else ""
            turn_icon = "🎯" if pid == self.game.current_player_id else ""
            you_icon = "(你)" if pid == self.game.player_id else ""
            print(f"  {turn_icon} {name} {landlord_icon}: {cards_count}张牌 {you_icon}")
    
    def _parse_card_input(self, input_str: str) -> List:
        """解析出牌输入"""
        if input_str.lower() == "pass":
            return []
        
        try:
            indices = [int(i) for i in input_str.split()]
            cards = []
            for idx in indices:
                if 0 <= idx < len(self.game.my_cards):
                    cards.append(self.game.my_cards[idx])
            return cards
        except ValueError:
            return None
    
    # ============ 网络方法 ============
    async def connect(self):
        """连接服务器"""
        try:
            self.websocket = await websockets.connect(self.server_url)
            self.running = True
            asyncio.create_task(self._listen())
            return True
        except Exception as e:
            print(f"❌ 连接失败: {e}")
            return False
    
    async def _listen(self):
        """监听服务器消息"""
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    action = data.get("action")
                    await self._trigger(action, data.get("data", {}))
                except json.JSONDecodeError:
                    print(f"无效的JSON: {message}")
        except websockets.exceptions.ConnectionClosed:
            print("与服务器断开连接")
            self.state = ClientState.DISCONNECTED
            self.running = False
    
    async def send(self, action: str, data: dict = None):
        """发送消息"""
        if self.websocket:
            message = {"action": action}
            if data:
                message.update(data)
            await self.websocket.send(json.dumps(message))
    
    async def create_room(self, room_name: str, player_name: str):
        await self.send("create_room", {"room_name": room_name, "player_name": player_name})
    
    async def join_room(self, room_id: str, player_name: str):
        await self.send("join_room", {"room_id": room_id, "player_name": player_name})
    
    async def leave_room(self):
        await self.send("leave_room")
    
    async def ready(self):
        await self.send("ready")
        print("已准备，等待其他玩家...")
    
    async def start_game(self):
        await self.send("start_game")
    
    async def bid_landlord(self, want_landlord: bool):
        await self.send("bid_landlord", {"want_landlord": want_landlord})
    
    async def play_cards(self, cards: List):
        await self.send("play_cards", {"cards": cards})
    
    async def get_room_list(self):
        await self.send("get_room_list")
    
    async def chat(self, message: str):
        await self.send("chat", {"message": message})
    
    async def close(self):
        self.running = False
        if self.websocket:
            await self.websocket.close()


# ============ 命令行界面 ============
class CLI:
    """命令行界面"""
    
    def __init__(self):
        self.client = DoudizhuClient()
        self.input_task = None
    
    async def run(self):
        """运行客户端"""
        print("=" * 50)
        print("🃏 斗地主联机客户端")
        print("=" * 50)
        
        # 连接服务器
        server_url = input("服务器地址 (默认 ws://localhost:8765): ").strip()
        if not server_url:
            server_url = "ws://localhost:8765"
        
        self.client.server_url = server_url
        print(f"正在连接 {server_url}...")
        
        if not await self.client.connect():
            print("连接失败，请检查服务器是否运行")
            return
        
        # 设置玩家名称
        player_name = input("请输入你的名字: ").strip()
        if not player_name:
            player_name = f"玩家_{self.client.game.player_id[:6]}"
        self.client.game.player_name = player_name
        
        # 主菜单
        await self.show_main_menu()
        
        # 启动输入监听
        self.input_task = asyncio.create_task(self.input_loop())
        
        # 等待客户端运行
        while self.client.running:
            await asyncio.sleep(0.1)
    
    async def show_main_menu(self):
        """显示主菜单"""
        print(f"\n{'='*50}")
        print(f"👤 {self.client.game.player_name}")
        print(f"{'='*50}")
        print("1. 创建房间")
        print("2. 加入房间")
        print("3. 刷新房间列表")
        print("4. 退出")
        print(f"{'='*50}")
        print("输入选项: ", end="", flush=True)
    
    async def show_room_menu(self):
        """显示房间菜单"""
        print(f"\n{'='*50}")
        print(f"📌 房间: {self.client.game.room_name}")
        print(f"{'='*50}")
        print("1. 准备")
        print("2. 开始游戏 (房主)")
        print("3. 离开房间")
        print(f"{'='*50}")
        print("输入选项: ", end="", flush=True)
    
    async def input_loop(self):
        """输入循环"""
        while self.client.running:
            try:
                line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
                line = line.strip()
                
                if self.client.state == ClientState.CONNECTED:
                    await self.handle_menu_input(line)
                elif self.client.state == ClientState.IN_ROOM:
                    await self.handle_room_input(line)
                elif self.client.state == ClientState.BIDDING:
                    await self.handle_bidding_input(line)
                elif self.client.state == ClientState.MY_TURN:
                    await self.handle_play_input(line)
                elif line.startswith("/"):
                    await self.handle_command(line)
                    
            except EOFError:
                break
    
    async def handle_menu_input(self, line: str):
        """处理主菜单输入"""
        if line == "1":
            room_name = input("房间名称: ").strip() or "游戏房间"
            await self.client.create_room(room_name, self.client.game.player_name)
        elif line == "2":
            await self.client.get_room_list()
            room_id = input("输入房间号: ").strip().upper()
            if room_id:
                await self.client.join_room(room_id, self.client.game.player_name)
        elif line == "3":
            await self.client.get_room_list()
            await self.show_main_menu()
        elif line == "4":
            self.client.running = False
            await self.client.close()
            print("再见!")
            sys.exit(0)
    
    async def handle_room_input(self, line: str):
        """处理房间内输入"""
        if line == "1":
            await self.client.ready()
        elif line == "2":
            await self.client.start_game()
        elif line == "3":
            await self.client.leave_room()
            await self.show_main_menu()
    
    async def handle_bidding_input(self, line: str):
        """处理叫地主输入"""
        want = line.lower() == "y" or line.lower() == "yes"
        await self.client.bid_landlord(want)
    
    async def handle_play_input(self, line: str):
        """处理出牌输入"""
        cards = self.client._parse_card_input(line)
        if cards is None:
            print("无效输入，请重新输入: ", end="", flush=True)
        else:
            await self.client.play_cards(cards)
    
    async def handle_command(self, line: str):
        """处理命令"""
        cmd = line[1:].lower()
        if cmd == "cards":
            print(f"你的手牌: {self.client._format_cards(self.client.game.my_cards)}")
        elif cmd == "status":
            self.client._print_game_status()
        elif cmd == "quit":
            await self.client.leave_room()
            self.client.running = False
            await self.client.close()
            sys.exit(0)
        elif cmd == "help":
            print("命令: /cards, /status, /quit")
        elif cmd.startswith("chat "):
            message = line[6:]
            await self.client.chat(message)


# ============ 主程序 ============
async def main():
    cli = CLI()
    await cli.run()


if __name__ == "__main__":
    asyncio.run(main())