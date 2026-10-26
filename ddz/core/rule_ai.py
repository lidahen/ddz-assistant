"""规则启发式 AI。不依赖外部模型，可作为决策引擎的降级方案。

核心思路:
1. 手牌拆分 (decompose): 把手牌拆成最少"手"，手数越少越好赢。
2. 自由出牌: 能一手出完就出完；否则出最弱的一手，优先顺子/单张小牌。
3. 跟牌: 有能压的走法时，评估出牌代价（拆炸弹/拆对/拆顺扣分），队友的牌不压。
"""
from __future__ import annotations

import functools
from collections import Counter
from typing import List, Optional, Sequence, Tuple

from .cards import PairType, beats, gen_moves, parse

PASS_MOVE: List[int] = []


# ---------------------------------------------------------------------------
# 手牌拆分
# ---------------------------------------------------------------------------

def _extract_seq(cnt: Counter, length: int, need: int, min_len: int) -> Optional[List[int]]:
    """尝试从 cnt 提取 length 组、每组 need 张的连续序列（顺子 need=1 / 连对 2 / 飞机 3）。"""
    runs = []
    r = 3
    while r <= 14:
        if cnt.get(r, 0) >= need:
            runs.append(r)
        else:
            if runs and len(runs) >= min_len:
                break_path = runs
            runs = []
        r += 1
    if runs and len(runs) >= min_len:
        pass
    # 简化: 贪心找最长的连续段
    best: Optional[List[int]] = None
    cur: List[int] = []
    for r in range(3, 15):
        if cnt.get(r, 0) >= need:
            cur.append(r)
        else:
            if best is None or len(cur) > len(best):
                best = cur if cur else None
            cur = []
    if len(cur) > (len(best) if best else 0):
        best = cur
    if best and len(best) >= min_len:
        return best[:max(min_len, len(best))]
    return None


def decompose(hand: Sequence[int]) -> List[List[int]]:
    """把手牌拆成尽量少的组。贪心 DFS + 剪枝，20 张内毫秒级。"""
    cnt = Counter(hand)

    @functools.lru_cache(maxsize=200000)
    def _best(tup) -> Tuple[int, tuple]:
        c = Counter(dict(tup))
        if not c:
            return 0, ()
        best_n, best_parts = 99, ()
        # 尝试提炸弹
        for r, n in list(c.items()):
            if n == 4:
                rest = Counter(c)
                rest[r] = 0
                rest = +rest
                sub_n, sub_parts = _best(tuple(sorted(rest.items())))
                if 1 + sub_n < best_n:
                    best_n, best_parts = 1 + sub_n, ((r, r, r, r),) + sub_parts
                # 也可以拆成对/三张，由其他分支覆盖
        # 尝试提火箭
        if c.get(16) and c.get(17):
            rest = Counter(c)
            del rest[16], rest[17]
            sub_n, sub_parts = _best(tuple(sorted((+rest).items())))
            if 1 + sub_n < best_n:
                best_n, best_parts = 1 + sub_n, ((16, 17),) + sub_parts
        # 尝试提顺子(5+)/连对(3+)/飞机(2+)
        for need, min_len in ((1, 5), (2, 3)):
            cur, start = [], None
            r = 3
            sequences = []
            while r <= 15:
                if c.get(r, 0) >= need and r <= 14:
                    if start is None:
                        start = r
                    cur.append(r)
                else:
                    if start is not None and len(cur) >= min_len:
                        sequences.append((start, len(cur)))
                    start, cur = None, []
                r += 1
            if start is not None and len(cur) >= min_len:
                sequences.append((start, len(cur)))
            for s0, slen in sequences:
                for take in range(slen, min_len - 1, -1):
                    seq = list(range(s0, s0 + take))
                    rest = Counter(c)
                    for rr in seq:
                        rest[rr] -= need
                    rest = +rest
                    sub_n, sub_parts = _best(tuple(sorted(rest.items())))
                    if 1 + sub_n < best_n:
                        parts = tuple(tuple([rr] * need for rr in seq)) if False else \
                            (tuple(rr for rr in seq for _ in range(need)),)
                        best_n, best_parts = 1 + sub_n, parts + sub_parts
        # 尝试提三张/三带一/三带二
        for r, n in sorted(c.items()):
            if n >= 3:
                rest = Counter(c)
                rest[r] -= 3
                rest = +rest
                # 纯三张
                sub_n, sub_parts = _best(tuple(sorted(rest.items())))
                if 1 + sub_n < best_n:
                    best_n, best_parts = 1 + sub_n, ((r, r, r),) + sub_parts
                # 三带一: 找最小的单张带
                singles = sorted(rr for rr, cc in rest.items() if cc == 1)
                if singles:
                    rest2 = Counter(rest)
                    rest2[singles[0]] -= 1
                    rest2 = +rest2
                    sub_n, sub_parts = _best(tuple(sorted(rest2.items())))
                    if 1 + sub_n < best_n:
                        best_n, best_parts = 1 + sub_n, ((r, r, r, singles[0]),) + sub_parts
                # 三带二
                pairs = sorted(rr for rr, cc in rest.items() if cc >= 2)
                if pairs:
                    rest2 = Counter(rest)
                    rest2[pairs[0]] -= 2
                    rest2 = +rest2
                    sub_n, sub_parts = _best(tuple(sorted(rest2.items())))
                    if 1 + sub_n < best_n:
                        best_n, best_parts = 1 + sub_n, ((r, r, r, pairs[0], pairs[0]),) + sub_parts
        # 对子
        for r, n in sorted(c.items()):
            if n >= 2:
                rest = Counter(c)
                rest[r] -= 2
                rest = +rest
                sub_n, sub_parts = _best(tuple(sorted(rest.items())))
                if 1 + sub_n < best_n:
                    best_n, best_parts = 1 + sub_n, ((r, r),) + sub_parts
        # 单张（最后手段，取最小）
        r0 = min(c)
        rest = Counter(c)
        rest[r0] -= 1
        rest = +rest
        sub_n, sub_parts = _best(tuple(sorted(rest.items())))
        if 1 + sub_n < best_n:
            best_n, best_parts = 1 + sub_n, ((r0,),) + sub_parts
        return best_n, best_parts

    n, parts = _best(tuple(sorted(cnt.items())))
    return [list(p) for p in parts]


# ---------------------------------------------------------------------------
# 决策
# ---------------------------------------------------------------------------

class RuleAI:
    """规则 AI。role: 'farmer' | 'landlord'；配合逻辑用简化身份判断。"""

    def __init__(self, role: str = 'farmer'):
        self.role = role

    def decide(self, hand: Sequence[int],
               last_move: Optional[Tuple[PairType, int, int]],
               last_player: Optional[str],
               own_role: Optional[str] = None,
               hand_counts: Optional[dict] = None) -> List[int]:
        """返回走法（空列表 = PASS）。

        last_move: 上家 (牌型, 主值, 长度)，None/牌型PASS 表示自由出牌。
        last_player: 上家身份 'landlord'/'farmer_peer'/'farmer_me' 之类由调用方映射。
        """
        role = own_role or self.role
        cnt = Counter(hand)
        free = last_move is None or last_move[0] == PairType.PASS

        if free:
            return self._lead(hand, cnt, role, hand_counts)

        # 跟牌
        is_teammate = (role == 'farmer' and last_player == 'farmer_peer')
        moves = gen_moves(hand, last_move)
        if not moves:
            return PASS_MOVE

        if is_teammate:
            # 队友出的牌：只有当队友手牌很少（快赢）或自己能小代价压且自己剩牌很少时才压
            peer_count = (hand_counts or {}).get('farmer_peer', 99)
            if peer_count > 2:
                return PASS_MOVE

        # 选代价最小的跟牌
        last_v = last_move[1]
        scored = sorted(moves, key=lambda m: (self._follow_cost(cnt, m, last_move), max(m)))
        best = scored[0]
        # 大牌保护：如果需要用 2/王 去压小单张且自己不是快赢，跳过（留给更关键时机）
        if last_move[0] == PairType.SINGLE and max(best) >= 15 and len(hand) > 6 \
                and last_v < 10 and not self._urgent(hand_counts, role):
            return PASS_MOVE
        return best

    # --- 自由出牌 ---

    def _lead(self, hand: Sequence[int], cnt: Counter, role: str,
              hand_counts: Optional[dict]) -> List[int]:
        parts = decompose(hand)
        if len(parts) == 1:
            return parts[0]  # 一手出完
        # 出完某手后若只剩一手，直接出（报单/报双场景）
        for p in parts:
            rest = Counter(hand)
            for c in p:
                rest[c] -= 1
            rest = +rest
            if len(parts) == 2 and parse(list(rest.elements())) is not None:
                # 两手牌：先出大的那手？先出对手接不住的。简化：先出强手
                return p
        # 常规：出最弱的一手（非炸），优先长顺子
        non_bomb = [p for p in parts if parse(p)[0] not in (PairType.BOMB, PairType.ROCKET)]
        pool = non_bomb or parts
        if any(parse(p)[0] == PairType.STRAIGHT for p in pool):
            straights = [p for p in pool if parse(p)[0] == PairType.STRAIGHT]
            return min(straights, key=lambda p: min(p))
        return min(pool, key=lambda p: (min(p), len(p)))

    # --- 代价评估 ---

    def _follow_cost(self, cnt: Counter, move: List[int],
                     last: Tuple[PairType, int, int]) -> float:
        """出这手牌的代价：拆炸弹极高、拆对/三张中等、顺子用整段低。"""
        t = parse(move)
        cost = 0.0
        mc = Counter(move)
        base = {PairType.SINGLE: 1, PairType.PAIR: 1, PairType.TRIO: 1}.get(t[0], 0)
        cost += base * 0.1
        for r, need in mc.items():
            have = cnt[r]
            if have == 4 and need < 4:
                cost += 50  # 拆炸弹
            elif have >= 3 and need == 1 and t[0] == PairType.SINGLE:
                cost += 6   # 拆三张
            elif have == 2 and need == 1:
                cost += 4   # 拆对子
        if t[0] in (PairType.BOMB, PairType.ROCKET):
            cost += 30 if t[0] == PairType.BOMB else 60
        # 主值越大越保守
        cost += t[1] * 0.05
        return cost

    @staticmethod
    def _urgent(hand_counts: Optional[dict], role: str) -> bool:
        """是否处于紧要关头（对手快出完）。"""
        if not hand_counts:
            return False
        if role == 'landlord':
            return min(hand_counts.get('farmer_a', 99), hand_counts.get('farmer_b', 99)) <= 2
        return hand_counts.get('landlord', 99) <= 2
