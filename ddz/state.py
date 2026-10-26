"""游戏状态机: 把每帧的识别结果合成一致的游戏状态。

核心职责:
- 维护我的手牌、三家出牌区快照、轮到谁
- 差异检测: 出牌区变化 => 那是刚发生的动作（谁出了什么 / PASS）
- 给决策层提供 (手牌, 上家牌型, 上家身份, 各家剩牌数)
"""
from __future__ import annotations

from collections import Counter
from typing import Dict, List, Optional, Tuple

from .core.cards import PairType, beats, is_valid_play, parse
from .vision.recognizer import CardRecognizer, dedup_hand


class GameState:
    """单局状态。轮次判断基于出牌区差异，无需点击检测。"""

    def __init__(self):
        self.my_hand: List[int] = []
        # 三个出牌区当前显示的牌（识别快照）
        self.play_snapshot: Dict[str, List[int]] = {'my_play': [], 'left_play': [], 'right_play': []}
        # 玩家身份: left/right/my 相对地主。识别后填 ('landlord'|'farmer'|None)
        self.roles: Dict[str, Optional[str]] = {'my': None, 'left': None, 'right': None}
        self.last_action: Optional[Dict] = None  # {'who':..,'move':List[int]|None(PASS)}

    # ------------------------------------------------------------------
    def update_frame(self, window_img, rec: CardRecognizer,
                     pass_visible: bool = False) -> Optional[Dict]:
        """喂入一帧窗口图像，更新状态。返回发生的新动作（若无变化返回 None）。

        pass_visible: UI 层检测到"不出"按钮/文字可见。
        """
        new_hand = dedup_hand(rec.recognize_hand(window_img))
        plays = {k: rec.recognize_play(window_img, k) for k in self.play_snapshot}

        # 手牌直接替换（识别为准）
        hand_changed = Counter(new_hand) != Counter(self.my_hand)
        self.my_hand = new_hand

        # 出牌区差异 => 新动作
        action = None
        for zone, now in plays.items():
            prev = self.play_snapshot[zone]
            if Counter(now) != Counter(prev):
                if not now and prev:
                    # 清空: 可能是新一轮开始或 PASS 闪烁，记录 PASS 事件
                    action = {'who': zone, 'move': None}
                elif now:
                    pt = parse(now)
                    if pt is not None:  # 识别出合法牌型才算出牌
                        action = {'who': zone, 'move': now, 'type': pt}
                self.play_snapshot[zone] = now
        self.last_action = action
        return action

    # ------------------------------------------------------------------
    def decision_context(self) -> Dict:
        """给决策引擎的上下文。"""
        # 轮到我 = 我的出牌区为空 且 手牌数 > 0（简化判断，主循环结合按钮检测确认）
        last_move, last_zone = None, None
        # 找"活"的出牌区：非空的最新的（简化：三区取时间上最近变化的非空区）
        for zone, cards in self.play_snapshot.items():
            if cards:
                pt = parse(cards)
                if pt and (last_move is None or beats(pt, last_move)):
                    last_move, last_zone = pt, zone
        return {
            'my_hand': list(self.my_hand),
            'last_move': last_move,
            'last_zone': last_zone,
            'hand_counts': self._est_counts(),
        }

    def _est_counts(self) -> Dict[str, int]:
        """各家剩牌估算: 17(或20) - 已见出牌。细化需记牌，先给区块快照大小。"""
        return {
            'my': len(self.my_hand),
            'left': None,   # 由 UI 层的剩牌数 OCR 填充
            'right': None,
        }
