# doudizhu_core.py - 斗地主核心逻辑（专家模式完整版）
import random
from collections import Counter
from enum import Enum
from typing import List, Dict, Tuple, Optional, Set
from itertools import combinations

# ============ 枚举定义 ============
class CardType(Enum):
    SINGLE = "单牌"
    PAIR = "对子"
    TRIPLE = "三张"
    TRIPLE_WITH_ONE = "三带一"
    TRIPLE_WITH_PAIR = "三带二"
    STRAIGHT = "顺子"
    DOUBLE_STRAIGHT = "连对"
    TRIPLE_STRAIGHT = "飞机"
    PLANE_WITH_ONE = "飞机带单"
    PLANE_WITH_PAIR = "飞机带对"
    FOUR_WITH_TWO = "四带二"
    FOUR_WITH_TWO_PAIRS = "四带两对"
    BOMB = "炸弹"
    ROCKET = "火箭"
    INVALID = "无效"

class Difficulty(Enum):
    EASY = "简单"
    MEDIUM = "中等"
    HARD = "困难"
    EXPERT = "专家"

class GamePhase(Enum):
    BIDDING = "叫地主"
    PLAYING = "游戏中"
    FINISHED = "已结束"

# ============ Card 类 ============
class Card:
    # 牌的大小顺序：3-2, 小王, 大王
    _RANK_ORDER = ['3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A', '2', 'Joker1', 'Joker2']
    _RANK_NAMES = {'Joker1': '小王', 'Joker2': '大王'}
    
    def __init__(self, suit: str, rank: str):
        self.suit = suit
        if rank == 'Joker':
            self.rank = 'Joker2' if suit == 'Black' else 'Joker1'
        else:
            self.rank = rank
    
    @property
    def value(self) -> int:
        return self._RANK_ORDER.index(self.rank)
    
    @property
    def display_name(self) -> str:
        if self.rank in self._RANK_NAMES:
            return self._RANK_NAMES[self.rank]
        suit_map = {'♥': '♥', '♠': '♠', '♦': '♦', '♣': '♣'}
        return f"{suit_map.get(self.suit, '')}{self.rank}"
    
    def __lt__(self, other):
        return self.value < other.value
    
    def __eq__(self, other):
        if not isinstance(other, Card):
            return False
        return self.rank == other.rank and self.suit == other.suit
    
    def __hash__(self):
        return hash((self.rank, self.suit))
    
    def __repr__(self):
        return self.display_name

# ============ 牌型检测器 ============
class PatternDetector:
    """牌型检测器"""
    
    @staticmethod
    def detect(cards: List[Card]) -> Dict:
        """检测牌型"""
        if not cards:
            return {'valid': False, 'type': CardType.INVALID, 'key': None, 'length': 0}
        
        length = len(cards)
        ranks = [c.rank for c in cards]
        rank_counter = Counter(ranks)
        values = sorted([c.value for c in cards])
        sorted_cards = sorted(cards)
        
        # 火箭（王炸）
        if length == 2 and set(ranks) == {'Joker1', 'Joker2'}:
            return {'valid': True, 'type': CardType.ROCKET, 'key': sorted_cards[-1], 'length': length, 'cards': sorted_cards}
        
        # 炸弹
        if length == 4 and len(rank_counter) == 1:
            return {'valid': True, 'type': CardType.BOMB, 'key': sorted_cards[-1], 'length': length, 'cards': sorted_cards}
        
        # 单牌
        if length == 1:
            return {'valid': True, 'type': CardType.SINGLE, 'key': cards[0], 'length': length, 'cards': cards}
        
        # 对子
        if length == 2 and len(rank_counter) == 1:
            return {'valid': True, 'type': CardType.PAIR, 'key': sorted_cards[-1], 'length': length, 'cards': sorted_cards}
        
        # 三张
        if length == 3 and len(rank_counter) == 1:
            return {'valid': True, 'type': CardType.TRIPLE, 'key': sorted_cards[-1], 'length': length, 'cards': sorted_cards}
        
        # 三带一
        if length == 4 and set(rank_counter.values()) == {1, 3}:
            triple_rank = [r for r, c in rank_counter.items() if c == 3][0]
            triple_cards = [c for c in cards if c.rank == triple_rank]
            return {'valid': True, 'type': CardType.TRIPLE_WITH_ONE, 'key': max(triple_cards), 'length': length, 'cards': sorted_cards}
        
        # 三带二
        if length == 5 and set(rank_counter.values()) == {2, 3}:
            triple_rank = [r for r, c in rank_counter.items() if c == 3][0]
            triple_cards = [c for c in cards if c.rank == triple_rank]
            return {'valid': True, 'type': CardType.TRIPLE_WITH_PAIR, 'key': max(triple_cards), 'length': length, 'cards': sorted_cards}
        
        # 四带二（两张单牌）
        if length == 6 and set(rank_counter.values()) == {1, 4}:
            four_rank = [r for r, c in rank_counter.items() if c == 4][0]
            four_cards = [c for c in cards if c.rank == four_rank]
            return {'valid': True, 'type': CardType.FOUR_WITH_TWO, 'key': max(four_cards), 'length': length, 'cards': sorted_cards}
        
        # 四带两对
        if length == 8 and 4 in rank_counter.values():
            four_rank = [r for r, c in rank_counter.items() if c == 4][0]
            four_cards = [c for c in cards if c.rank == four_rank]
            other_counts = [c for r, c in rank_counter.items() if r != four_rank]
            if sorted(other_counts) == [2, 2]:
                return {'valid': True, 'type': CardType.FOUR_WITH_TWO_PAIRS, 'key': max(four_cards), 'length': length, 'cards': sorted_cards}
        
        # 顺子（至少5张连续单牌，不含2和王）
        if length >= 5 and len(rank_counter) == length:
            if all(v < Card._RANK_ORDER.index('2') for v in values):
                if PatternDetector._is_consecutive(values):
                    return {'valid': True, 'type': CardType.STRAIGHT, 'key': sorted_cards[-1], 'length': length, 'cards': sorted_cards}
        
        # 连对（至少3对连续）
        if length >= 6 and length % 2 == 0:
            if all(c == 2 for c in rank_counter.values()):
                unique_vals = sorted(set(values))
                if all(v < Card._RANK_ORDER.index('2') for v in unique_vals):
                    if PatternDetector._is_consecutive(unique_vals):
                        return {'valid': True, 'type': CardType.DOUBLE_STRAIGHT, 'key': sorted_cards[-1], 'length': length, 'cards': sorted_cards}
        
        # 飞机（至少2个连续三张）
        triples = [r for r, c in rank_counter.items() if c >= 3]
        if len(triples) >= 2:
            triple_vals = sorted([Card._RANK_ORDER.index(r) for r in triples])
            if all(v < Card._RANK_ORDER.index('2') for v in triple_vals):
                if PatternDetector._is_consecutive(triple_vals):
                    triple_cards_count = sum(rank_counter[r] for r in triples)
                    wing_count = length - triple_cards_count
                    
                    if wing_count == 0:
                        return {'valid': True, 'type': CardType.TRIPLE_STRAIGHT, 'key': sorted_cards[-1], 'length': length, 'cards': sorted_cards}
                    elif wing_count == len(triples):
                        return {'valid': True, 'type': CardType.PLANE_WITH_ONE, 'key': sorted_cards[-1], 'length': length, 'cards': sorted_cards}
                    elif wing_count == len(triples) * 2:
                        return {'valid': True, 'type': CardType.PLANE_WITH_PAIR, 'key': sorted_cards[-1], 'length': length, 'cards': sorted_cards}
        
        return {'valid': False, 'type': CardType.INVALID, 'key': None, 'length': length, 'cards': sorted_cards}
    
    @staticmethod
    def _is_consecutive(values: List[int]) -> bool:
        """检查数值是否连续"""
        return all(values[i+1] - values[i] == 1 for i in range(len(values)-1))

# ============ 出牌比较器 ============
class PlayComparator:
    """出牌比较器"""
    
    @staticmethod
    def can_beat(play: List[Card], last: List[Card]) -> bool:
        """判断play是否能击败last"""
        if not last:
            return True
        
        play_info = PatternDetector.detect(play)
        last_info = PatternDetector.detect(last)
        
        if not play_info['valid'] or not last_info['valid']:
            return False
        
        play_type = play_info['type']
        last_type = last_info['type']
        
        # 火箭最大
        if play_type == CardType.ROCKET:
            return True
        if last_type == CardType.ROCKET:
            return False
        
        # 炸弹可以压非炸弹
        if play_type == CardType.BOMB:
            if last_type != CardType.BOMB:
                return True
            return play_info['key'].value > last_info['key'].value
        
        # 同类型同长度比较关键牌的大小
        if play_type == last_type and len(play) == len(last):
            return play_info['key'].value > last_info['key'].value
        
        return False

# ============ 发牌器 ============
class DeckManager:
    """牌堆管理器"""
    
    @staticmethod
    def create_deck() -> List[Card]:
        ranks = ['3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A', '2']
        suits = ['♥', '♠', '♦', '♣']
        deck = [Card(s, r) for r in ranks for s in suits]
        deck.append(Card('Red', 'Joker'))
        deck.append(Card('Black', 'Joker'))
        return deck
    
    @staticmethod
    def deal() -> Dict:
        deck = DeckManager.create_deck()
        random.shuffle(deck)
        return {
            "Human": sorted(deck[:17]),
            "AI1": sorted(deck[17:34]),
            "AI2": sorted(deck[34:51]),
            "Landlord": deck[51:54]
        }

# ============ 手牌分析器 ============
class HandAnalyzer:
    """手牌分析器 - 用于AI决策"""
    
    def __init__(self, cards: List[Card]):
        self.cards = sorted(cards)
        self.rank_counter = Counter(c.value for c in self.cards)
        self.suit_counter = Counter(c.suit for c in self.cards)
    
    def get_all_possible_plays(self, last_play: Optional[List[Card]] = None) -> List[List[Card]]:
        """获取所有可能的出牌组合"""
        if not last_play:
            return self._get_all_first_plays()
        else:
            return self._get_all_response_plays(last_play)
    
    def _get_all_first_plays(self) -> List[List[Card]]:
        """获取所有主动出牌的组合"""
        plays = []
        
        # 单牌
        for card in self.cards:
            plays.append([card])
        
        # 对子
        for val, count in self.rank_counter.items():
            if count >= 2:
                cards_of_val = [c for c in self.cards if c.value == val]
                for combo in combinations(cards_of_val, 2):
                    plays.append(list(combo))
        
        # 三张
        for val, count in self.rank_counter.items():
            if count >= 3:
                cards_of_val = [c for c in self.cards if c.value == val]
                for combo in combinations(cards_of_val, 3):
                    plays.append(list(combo))
        
        # 三带一
        for val, count in self.rank_counter.items():
            if count >= 3:
                triples = [c for c in self.cards if c.value == val][:3]
                other_cards = [c for c in self.cards if c.value != val]
                for single in other_cards:
                    plays.append(triples + [single])
        
        # 三带二
        for val, count in self.rank_counter.items():
            if count >= 3:
                triples = [c for c in self.cards if c.value == val][:3]
                for other_val, other_count in self.rank_counter.items():
                    if other_val != val and other_count >= 2:
                        pairs = [c for c in self.cards if c.value == other_val][:2]
                        plays.append(triples + pairs)
        
        # 顺子
        plays.extend(self._find_straights())
        
        # 连对
        plays.extend(self._find_double_straights())
        
        # 炸弹
        for val, count in self.rank_counter.items():
            if count == 4:
                plays.append([c for c in self.cards if c.value == val])
        
        # 火箭
        jokers = [c for c in self.cards if c.rank in ['Joker1', 'Joker2']]
        if len(jokers) == 2:
            plays.append(jokers)
        
        return plays
    
    def _get_all_response_plays(self, last_play: List[Card]) -> List[List[Card]]:
        """获取所有能压过上家的出牌组合"""
        last_info = PatternDetector.detect(last_play)
        if not last_info['valid']:
            return []
        
        all_plays = self._get_all_first_plays()
        return [play for play in all_plays if PlayComparator.can_beat(play, last_play)]
    
    def _find_straights(self) -> List[List[Card]]:
        """找所有顺子"""
        straights = []
        values = sorted(set(c.value for c in self.cards if c.value < Card._RANK_ORDER.index('2')))
        
        for length in range(5, len(values) + 1):
            for i in range(len(values) - length + 1):
                seq = values[i:i+length]
                if self._is_consecutive(seq):
                    straight = []
                    for val in seq:
                        straight.append(next(c for c in self.cards if c.value == val))
                    straights.append(straight)
        
        return straights
    
    def _find_double_straights(self) -> List[List[Card]]:
        """找所有连对"""
        double_straights = []
        pair_vals = [val for val, count in self.rank_counter.items() 
                    if count >= 2 and val < Card._RANK_ORDER.index('2')]
        pair_vals.sort()
        
        for length in range(3, len(pair_vals) + 1):
            for i in range(len(pair_vals) - length + 1):
                seq = pair_vals[i:i+length]
                if self._is_consecutive(seq):
                    pairs = []
                    for val in seq:
                        pairs.extend([c for c in self.cards if c.value == val][:2])
                    double_straights.append(pairs)
        
        return double_straights
    
    @staticmethod
    def _is_consecutive(values: List[int]) -> bool:
        return all(values[i+1] - values[i] == 1 for i in range(len(values)-1))
    
    def evaluate_strength(self) -> int:
        """评估手牌强度（0-100）"""
        score = 0
        
        # 炸弹
        bombs = sum(1 for count in self.rank_counter.values() if count == 4)
        score += bombs * 25
        
        # 火箭
        if all(r in [c.rank for c in self.cards] for r in ['Joker1', 'Joker2']):
            score += 35
        
        # 三张
        triples = sum(1 for count in self.rank_counter.values() if count >= 3)
        score += triples * 8
        
        # 对子
        pairs = sum(1 for count in self.rank_counter.values() if count >= 2)
        score += pairs * 3
        
        # 高价值牌（A、2）
        high_cards = sum(1 for c in self.cards if c.value >= Card._RANK_ORDER.index('A'))
        score += high_cards * 4
        
        # 顺子潜力
        values = sorted(set(c.value for c in self.cards if c.value < Card._RANK_ORDER.index('2')))
        if len(values) >= 5:
            max_consecutive = 1
            current = 1
            for i in range(1, len(values)):
                if values[i] - values[i-1] == 1:
                    current += 1
                    max_consecutive = max(max_consecutive, current)
                else:
                    current = 1
            score += max_consecutive * 2
        
        return min(score, 100)

# ============ AI玩家 ============
class ExpertAIPlayer:
    """专家级AI玩家"""
    
    def __init__(self, name: str, difficulty: Difficulty = Difficulty.EXPERT):
        self.name = name
        self.cards: List[Card] = []
        self.difficulty = difficulty
        self.is_landlord = False
        self.played_history: List[List[Card]] = []
    
    def set_cards(self, cards: List[Card]):
        self.cards = sorted(cards)
        self.played_history = []
    
    def add_cards(self, cards: List[Card]):
        self.cards.extend(cards)
        self.cards.sort()
    
    def remove_cards(self, cards: List[Card]):
        for card in cards:
            for i, my_card in enumerate(self.cards):
                if my_card == card:
                    self.cards.pop(i)
                    break
        self.played_history.append(cards)
    
    def get_play(self, last_play: List[Card]) -> List[Card]:
        """获取出牌决策"""
        if not self.cards:
            return []
        
        analyzer = HandAnalyzer(self.cards)
        
        if not last_play:
            return self._choose_first_play(analyzer)
        else:
            return self._choose_response_play(analyzer, last_play)
    
    def _choose_first_play(self, analyzer: HandAnalyzer) -> List[Card]:
        """选择主动出牌"""
        # 只剩一张牌直接出
        if len(self.cards) == 1:
            return [self.cards[0]]
        
        all_plays = analyzer.get_all_possible_plays()
        if not all_plays:
            return [min(self.cards)]
        
        # 根据难度选择策略
        if self.difficulty == Difficulty.EASY:
            return self._choose_easy_first(all_plays)
        elif self.difficulty == Difficulty.MEDIUM:
            return self._choose_medium_first(all_plays)
        else:
            return self._choose_expert_first(all_plays, analyzer)
    
    def _choose_easy_first(self, plays: List[List[Card]]) -> List[Card]:
        """简单难度：出最小的单牌"""
        singles = [p for p in plays if len(p) == 1]
        if singles:
            return min(singles, key=lambda p: p[0].value)
        return min(plays, key=len)
    
    def _choose_medium_first(self, plays: List[List[Card]]) -> List[Card]:
        """中等难度：优先出单牌"""
        singles = [p for p in plays if len(p) == 1]
        if singles:
            small_singles = [p for p in singles if p[0].value < 9]
            if small_singles:
                return min(small_singles, key=lambda p: p[0].value)
            return min(singles, key=lambda p: p[0].value)
        
        pairs = [p for p in plays if PatternDetector.detect(p)['type'] == CardType.PAIR]
        if pairs:
            return min(pairs, key=lambda p: max(c.value for c in p))
        
        return min(plays, key=len)
    
    def _choose_expert_first(self, plays: List[List[Card]], analyzer: HandAnalyzer) -> List[Card]:
        """专家难度：智能选择"""
        # 手牌少时出最小的牌
        if len(self.cards) <= 3:
            return min(plays, key=len)
        
        # 优先处理单牌
        singles = [p for p in plays if len(p) == 1 and analyzer.rank_counter[p[0].value] == 1]
        if singles:
            small_singles = [p for p in singles if p[0].value < 9]
            if small_singles:
                return min(small_singles, key=lambda p: p[0].value)
            return min(singles, key=lambda p: p[0].value)
        
        # 其次出小对子
        pairs = [p for p in plays if PatternDetector.detect(p)['type'] == CardType.PAIR]
        if pairs:
            small_pairs = [p for p in pairs if max(c.value for c in p) < 9]
            if small_pairs:
                return min(small_pairs, key=lambda p: max(c.value for c in p))
        
        # 出最小的合法牌
        return min(plays, key=lambda p: (len(p), max(c.value for c in p)))
    
    def _choose_response_play(self, analyzer: HandAnalyzer, last_play: List[Card]) -> List[Card]:
        """选择响应出牌"""
        valid_plays = analyzer.get_all_possible_plays(last_play)
        
        if not valid_plays:
            return []  # 过牌
        
        last_info = PatternDetector.detect(last_play)
        
        # 如果上家出的是炸弹或火箭，只有更大的炸弹/火箭才能压
        if last_info['type'] in [CardType.BOMB, CardType.ROCKET]:
            return self._choose_best_play(valid_plays)
        
        # 过滤掉炸弹（除非必要）
        non_bomb_plays = [p for p in valid_plays 
                         if PatternDetector.detect(p)['type'] not in [CardType.BOMB, CardType.ROCKET]]
        
        if non_bomb_plays:
            # 手牌多时保留炸弹
            if len(self.cards) > 6:
                return self._choose_smallest_beat(non_bomb_plays, last_info)
        
        # 选择最优的出牌
        return self._choose_best_play(valid_plays)
    
    def _choose_smallest_beat(self, plays: List[List[Card]], last_info: Dict) -> List[Card]:
        """选择最小的能压过的牌"""
        return min(plays, key=lambda p: (len(p), max(c.value for c in p)))
    
    def _choose_best_play(self, plays: List[List[Card]]) -> List[Card]:
        """选择最优的出牌"""
        if not plays:
            return []
        # 优先选长度短的，同长度选关键牌最小的
        return min(plays, key=lambda p: (len(p), max(c.value for c in p)))
    
    def should_become_landlord(self, landlord_cards: List[Card]) -> bool:
        """决定是否叫地主"""
        temp_cards = self.cards + landlord_cards
        analyzer = HandAnalyzer(temp_cards)
        strength = analyzer.evaluate_strength()
        
        thresholds = {
            Difficulty.EASY: 40,
            Difficulty.MEDIUM: 50,
            Difficulty.HARD: 60,
            Difficulty.EXPERT: 65
        }
        
        return strength >= thresholds[self.difficulty]

# ============ 游戏管理器 ============
class GameManager:
    """游戏管理器"""
    
    def __init__(self):
        self.players = {
            "Human": ExpertAIPlayer("玩家", Difficulty.EXPERT),
            "AI1": ExpertAIPlayer("电脑1", Difficulty.EXPERT),
            "AI2": ExpertAIPlayer("电脑2", Difficulty.HARD)
        }
        self.landlord_cards = []
        self.landlord = None
        self.current_player = None
        self.last_play = []
        self.last_player = None
        self.pass_count = 0
        self.phase = GamePhase.BIDDING
        self.game_over = False
        self.winner = None
        self.player_order = ["Human", "AI1", "AI2"]
        self.turn_count = 0
    
    def start_game(self):
        """开始新游戏"""
        dealt = DeckManager.deal()
        for player_name in self.player_order:
            self.players[player_name].set_cards(dealt[player_name])
        self.landlord_cards = dealt["Landlord"]
        self.phase = GamePhase.BIDDING
        self.game_over = False
        self.winner = None
        self.turn_count = 0
        return self
    
    def set_landlord(self, player_name: str):
        """设置地主"""
        self.landlord = player_name
        self.players[player_name].add_cards(self.landlord_cards)
        self.players[player_name].is_landlord = True
        self.current_player = player_name
        self.last_player = None
        self.last_play = []
        self.pass_count = 0
        self.phase = GamePhase.PLAYING
        self.turn_count = 0
        
        print(f"\n{'='*50}")
        print(f"地主: {player_name}")
        print(f"底牌: {self.landlord_cards}")
        print(f"游戏开始！{player_name} 先出牌")
        print(f"{'='*50}\n")
    
    def play_turn(self, player_name: str, cards: List[Card]) -> Tuple[bool, str]:
        """执行一回合出牌，返回(是否成功, 错误信息)"""
        if self.phase != GamePhase.PLAYING:
            return False, "游戏不在进行中"
        
        if player_name != self.current_player:
            return False, f"不是 {player_name} 的回合"
        
        player = self.players[player_name]
        
        # 过牌
        if not cards:
            if not self.last_play:
                return False, "首轮不能过牌"
            
            self.pass_count += 1
            print(f"⏭️ {player_name} 过牌 (过牌数: {self.pass_count})")
            
            if self.pass_count >= 2:
                print(f"\n🔄 一轮结束，{self.last_player} 重新出牌\n")
                self.last_play = []
                self.pass_count = 0
                self.current_player = self.last_player
            else:
                self._next_player()
            return True, ""
        
        # 出牌
        play_info = PatternDetector.detect(cards)
        if not play_info['valid']:
            return False, "无效的牌型"
        
        if not PlayComparator.can_beat(cards, self.last_play):
            return False, f"不能压过 {self.last_play}"
        
        if not self._has_cards(player, cards):
            return False, "手牌中没有这些牌"
        
        # 执行出牌
        player.remove_cards(cards)
        self.last_play = cards
        self.last_player = player_name
        self.pass_count = 0
        self.turn_count += 1
        
        print(f"🎴 {player_name} 出牌: {cards} [{play_info['type'].value}] (剩余: {len(player.cards)}张)")
        
        # 检查胜利
        if not player.cards:
            self._end_game(player_name)
            return True, ""
        
        self._next_player()
        return True, ""
    
    def _has_cards(self, player: ExpertAIPlayer, cards: List[Card]) -> bool:
        """检查玩家是否有这些牌"""
        temp = player.cards.copy()
        for card in cards:
            found = False
            for i, c in enumerate(temp):
                if c == card:
                    temp.pop(i)
                    found = True
                    break
            if not found:
                return False
        return True
    
    def _next_player(self):
        idx = self.player_order.index(self.current_player)
        self.current_player = self.player_order[(idx + 1) % 3]
    
    def _end_game(self, winner: str):
        self.phase = GamePhase.FINISHED
        self.game_over = True
        self.winner = winner
        is_landlord_win = (winner == self.landlord)
        print(f"\n{'='*50}")
        print(f"🎉 游戏结束！{winner} 获胜！🎉")
        print(f"地主{'胜利' if is_landlord_win else '失败'}")
        print(f"总回合数: {self.turn_count}")
        print(f"{'='*50}\n")
    
    def get_ai_play(self) -> Tuple[str, List[Card]]:
        """获取AI出牌决策"""
        if self.current_player not in ["AI1", "AI2"]:
            return "", []
        
        player = self.players[self.current_player]
        play = player.get_play(self.last_play)
        
        # 主动出牌时确保有牌可出
        if not self.last_play and not play:
            play = [min(player.cards)]
            print(f"⚠️ {self.current_player} 强制出牌")
        
        return self.current_player, play
    
    def get_state(self) -> Dict:
        """获取游戏状态"""
        return {
            "phase": self.phase,
            "current_player": self.current_player,
            "landlord": self.landlord,
            "last_play": self.last_play,
            "last_player": self.last_player,
            "pass_count": self.pass_count,
            "game_over": self.game_over,
            "winner": self.winner,
            "turn_count": self.turn_count,
            "human_cards": self.players["Human"].cards,
            "ai1_count": len(self.players["AI1"].cards),
            "ai2_count": len(self.players["AI2"].cards),
        }
    
    def get_valid_plays_for_human(self) -> List[List[Card]]:
        """获取人类玩家当前可出的牌"""
        if self.current_player != "Human":
            return []
        
        analyzer = HandAnalyzer(self.players["Human"].cards)
        return analyzer.get_all_possible_plays(self.last_play)

# ============ 游戏演示 ============
def demo_game():
    """演示游戏"""
    print("=" * 60)
    print("🃏 斗地主 - 专家模式演示 🃏")
    print("=" * 60)
    
    game = GameManager()
    game.start_game()
    
    # 随机选地主
    landlord = random.choice(["AI1", "AI2", "Human"])
    game.set_landlord(landlord)
    
    print(f"玩家手牌: {game.players['Human'].cards}")
    print(f"电脑1手牌: {len(game.players['AI1'].cards)}张")
    print(f"电脑2手牌: {len(game.players['AI2'].cards)}张\n")
    
    max_turns = 300
    
    while not game.game_over and game.turn_count < max_turns:
        state = game.get_state()
        print(f"\n--- 回合 {game.turn_count + 1} ---")
        print(f"🎯 当前玩家: {state['current_player']}")
        print(f"📋 上家出牌: {state['last_play'] if state['last_play'] else '无'}")
        
        current = state['current_player']
        player = game.players[current]
        
        play = player.get_play(state['last_play'])
        
        if not state['last_play'] and not play:
            play = [min(player.cards)]
        
        if play:
            success, error = game.play_turn(current, play)
            if not success:
                print(f"❌ 出牌失败: {error}")
                if state['last_play']:
                    game.play_turn(current, [])
                else:
                    game.play_turn(current, [min(player.cards)])
        else:
            if state['last_play']:
                game.play_turn(current, [])
            else:
                game.play_turn(current, [min(player.cards)])
        
        print(f"📊 手牌: 玩家({len(game.players['Human'].cards)}) 电脑1({len(game.players['AI1'].cards)}) 电脑2({len(game.players['AI2'].cards)})")
    
    return game

# ============ 主程序 ============
if __name__ == "__main__":
    print("=" * 50)
    print("斗地主核心引擎 v2.0 - 专家模式")
    print("=" * 50)
    
    # 测试牌型检测
    print("\n🧪 测试牌型检测...")
    test_cards = [
        Card('♥', '3'), Card('♠', '3'), Card('♦', '3'),
        Card('♥', '5'), Card('♠', '5')
    ]
    info = PatternDetector.detect(test_cards)
    print(f"  牌型: {info['type'].value}, 有效: {info['valid']}")
    
    # 运行游戏
    print("\n🎮 开始游戏演示...\n")
    game = demo_game()
    
    print(f"\n✅ 演示完成！赢家: {game.winner}")