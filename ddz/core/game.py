"""游戏引擎: 斗地主完整流程（发牌/叫分/出牌），用于规则 AI 自对弈测试。"""
from __future__ import annotations

import random
from collections import Counter
from typing import List, Optional, Tuple

from .cards import PairType, beats, is_valid_play, parse
from .rule_ai import RuleAI


class Game:
    """三人斗地主单局。players: ['p0','p1','p2']，p0 是地主固定为测试方便。"""

    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed)
        deck = [r for r in range(3, 16) for _ in range(4)] + [16, 17]
        self.rng.shuffle(deck)
        self.hands = {
            'p0': sorted(deck[:17] + deck[51:]),   # 地主: 17+3
            'p1': sorted(deck[17:34]),
            'p2': sorted(deck[34:51]),
        }
        self.landlord = 'p0'
        self.role = {'p0': 'landlord', 'p1': 'farmer', 'p2': 'farmer'}
        self.current = 'p0'
        self.last_move: Optional[Tuple[PairType, int, int]] = None
        self.last_player: Optional[str] = None
        self.passes = 0
        self.winner: Optional[str] = None
        self.history: List = []

    def hand_counts(self, exclude: str) -> dict:
        peer = {'p1': 'p2', 'p2': 'p1'}.get(exclude)
        d = {
            'landlord': len(self.hands[self.landlord]),
            'farmer_a': len(self.hands['p1']),
            'farmer_b': len(self.hands['p2']),
        }
        if peer:
            d['farmer_peer'] = len(self.hands[peer])
        return d

    def step(self, player: str, move: List[int]) -> None:
        assert player == self.current, f'轮到 {self.current} 不是 {player}'
        if move:
            assert is_valid_play(self.hands[player], move), \
                f'{player} 出了没有的牌: {move} vs {self.hands[player]}'
            pt = parse(move)
            assert pt is not None, f'非法牌型: {move}'
            assert beats(pt, self.last_move if self.last_player == player else None) or \
                   self.last_player == player or self.last_move is None, \
                f'{move} 压不过 {self.last_move}'
            for c in move:
                self.hands[player].remove(c)
            self.last_move = pt
            self.last_player = player
            self.passes = 0
            if not self.hands[player]:
                self.winner = player
                return
        else:
            self.passes += 1
            if self.passes == 2:
                # 两家不要 => 上一手玩家重新自由出牌
                self.last_move = None
                self.current = self.last_player
                self.passes = 0
                return
        # 轮转
        order = ['p0', 'p1', 'p2']
        self.current = order[(order.index(self.current) + 1) % 3]
        if self.current == self.last_player:
            self.last_move = None  # 绕回自己 => 自由出牌
            self.passes = 0

    def run(self, ais: dict, verbose: bool = False) -> str:
        """自对弈直到分出胜负。返回赢家。"""
        guard = 0
        while self.winner is None:
            guard += 1
            if guard > 1000:
                raise RuntimeError('死循环: 超过 1000 步未结束')
            p = self.current
            ai = ais[p]
            peer = {'p1': 'p2', 'p2': 'p1'}.get(p)
            last_player_role = None
            if self.last_player:
                last_player_role = ('farmer_peer' if self.last_player == peer
                                    else ('landlord' if self.role[self.last_player] == 'landlord'
                                          else 'farmer_peer'))
            move = ai.decide(
                hand=list(self.hands[p]),
                last_move=self.last_move,
                last_player=last_player_role,
                own_role=self.role[p],
                hand_counts=self.hand_counts(p),
            )
            if verbose:
                lm = self.last_move[0].name if self.last_move else 'FREE'
                print(f'{p}({self.role[p]}) {lm} hand={self.hands[p]} -> {move}')
            self.step(p, move)
        return self.winner
