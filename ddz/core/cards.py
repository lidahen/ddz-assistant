"""牌型识别与走法生成。斗地主规则核心，无外部依赖。

牌值编码: 3..10=3..10, J=11, Q=12, K=13, A=14, 2=15, 小王=16, 大王=17
"""
from __future__ import annotations

from collections import Counter
from enum import IntEnum
from typing import Iterable, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

RANK_MIN = 3
RANK_MAX = 17
STRAIGHT_MAX = 14  # 顺子/连对/飞机中最大只能是 A(14)，2 和王不能入顺

CARD_CHARS = {3: '3', 4: '4', 5: '5', 6: '6', 7: '7', 8: '8', 9: '9', 10: '10',
              11: 'J', 12: 'Q', 13: 'K', 14: 'A', 15: '2', 16: 'X', 17: 'D'}
CHAR_CARDS = {v: k for k, v in CARD_CHARS.items()}


def cards_to_str(cards: Iterable[int]) -> str:
    """[3,4,5,11,15,17] -> '345J2D'"""
    return ''.join(CARD_CHARS[c] for c in cards)


def str_to_cards(s: str) -> List[int]:
    """'345J2D' -> [3,4,5,11,15,17]。X=小王 D=大王"""
    out, i = [], 0
    while i < len(s):
        ch = s[i].upper()
        if ch == '1':  # '10'
            out.append(10)
            i += 2
            continue
        if ch not in CHAR_CARDS:
            raise ValueError(f'非法牌字符: {ch!r} in {s!r}')
        out.append(CHAR_CARDS[ch])
        i += 1
    return out


class PairType(IntEnum):
    """牌型。值同时用于比较同型大小（仅在同型同长时比较主值）。"""
    PASS = 0
    SINGLE = 1
    PAIR = 2
    TRIO = 3
    TRIO_SINGLE = 4   # 三带一
    TRIO_PAIR = 5     # 三带二
    STRAIGHT = 6
    PAIR_STRAIGHT = 7
    PLANE = 8
    PLANE_SINGLE = 9  # 飞机带单
    PLANE_PAIR = 10   # 飞机带对
    FOUR_TWO = 11           # 四带二（两单或一对，按平台规则，此处按两单/两对都算四带二变体）
    FOUR_TWO_PAIR = 12
    BOMB = 13
    ROCKET = 14


# ---------------------------------------------------------------------------
# 牌型解析
# ---------------------------------------------------------------------------

def _is_seq(ranks: Sequence[int]) -> bool:
    """是否连续且未越界（2 和王不可入顺）。"""
    return max(ranks) <= STRAIGHT_MAX and \
        sorted(ranks) == list(range(min(ranks), min(ranks) + len(ranks)))


def parse(cards: Sequence[int]) -> Optional[Tuple[PairType, int, int]]:
    """解析一手牌。返回 (牌型, 主值, 长度组数) 或 None(非法)。

    主值: 决定同型大小的关键 rank。长度: 顺子/连对/飞机的组数，其他为 1。
    比较: 同牌型同长度且主值更大 => 压制。BOMB 压一切非炸非王，ROCKET 最大。
    """
    if not cards:
        return None
    n = len(cards)
    cnt = Counter(cards)
    ranks = sorted(cnt)

    if any(r < RANK_MIN or r > RANK_MAX for r in ranks):
        return None

    # 王炸
    if n == 2 and ranks == [16, 17]:
        return PairType.ROCKET, 17, 1
    # 炸弹
    if n == 4 and len(cnt) == 1:
        return PairType.BOMB, ranks[0], 1
    # 单张
    if n == 1:
        return PairType.SINGLE, ranks[0], 1
    # 对子
    if n == 2 and len(cnt) == 1 and ranks[0] <= 15:
        return PairType.PAIR, ranks[0], 1
    # 三张
    if n == 3 and len(cnt) == 1:
        return PairType.TRIO, ranks[0], 1
    # 三带一 / 三带二
    if n == 4 and len(cnt) == 2:
        trio = [r for r, c in cnt.items() if c == 3]
        if trio:
            return PairType.TRIO_SINGLE, trio[0], 1
    if n == 5 and len(cnt) == 2:
        trio = [r for r, c in cnt.items() if c == 3]
        pair = [r for r, c in cnt.items() if c == 2]
        if trio and pair:
            return PairType.TRIO_PAIR, trio[0], 1
    # 顺子
    if 5 <= n and all(c == 1 for c in cnt.values()) and _is_seq(ranks):
        return PairType.STRAIGHT, ranks[0], n
    # 连对
    if n >= 6 and n % 2 == 0 and all(c == 2 for c in cnt.values()) and _is_seq(ranks):
        return PairType.PAIR_STRAIGHT, ranks[0], n // 2
    # 飞机（纯飞机/带单/带对），翅膀判定从宽：带单允许任意单张（含王、炸拆单），
    # 带对允许任意对。需要小心 XXXYYYY 这类歧义（333444555 中 444555 可当翅膀也可当机体）。
    trio_ranks = [r for r, c in cnt.items() if c >= 3]
    if trio_ranks and n % 4 == 0 and n >= 8:      # 飞机带单: m组三张 + m单
        body = _plane_body(cnt, n // 4)
        if body:
            return PairType.PLANE_SINGLE, body[0], body[1]
    if trio_ranks and n % 5 == 0 and n >= 10:     # 飞机带对: m组三张 + m对
        body = _plane_body(cnt, n // 5)
        if body:
            return PairType.PLANE_PAIR, body[0], body[1]
    if n >= 6 and n % 3 == 0:                      # 纯飞机
        body = _plane_body(cnt, n // 3, pure=True)
        if body:
            return PairType.PLANE, body[0], body[1]
    # 四带二
    if n == 6:
        four = [r for r, c in cnt.items() if c == 4]
        if four:
            return PairType.FOUR_TWO, four[0], 1
    if n == 8:
        four = [r for r, c in cnt.items() if c == 4]
        if four and len(cnt) == 3:                 # 4+2+2
            return PairType.FOUR_TWO_PAIR, four[0], 1
    return None


def _plane_body(cnt: Counter, m: int, pure: bool = False) -> Optional[Tuple[int, int]]:
    """从计数中找连续 m 组三张作为飞机主体。返回 (最小主值, 组数) 或 None。

    pure=True 时整手牌必须恰好由这 m 组三张构成。
    策略：枚举所有可能的连续三张区间，检查剩余部分是否合法翅膀。
    """
    trio_ranks = sorted(r for r, c in cnt.items() if c >= 3 and r <= STRAIGHT_MAX)
    n_cnt = sum(cnt.values())
    # 候选区间: [i, i+m-1] 连续
    for start in range(RANK_MIN, STRAIGHT_MAX - m + 2):
        seq = list(range(start, start + m))
        if any(cnt.get(r, 0) < 3 for r in seq):
            continue
        if pure:
            # 纯飞机：总数恰好 3m，且区间内每组恰好用 3 张
            if n_cnt == 3 * m and all(cnt[r] == 3 for r in seq):
                return start, m
            # 处理 XXXYYYY 歧义留给带翅膀场景；纯牌必须整齐
            continue
        rest = Counter(cnt)
        for r in seq:
            rest[r] -= 3
            if rest[r] == 0:
                del rest[r]
        rest_n = sum(rest.values())
        if rest_n == 0:
            continue
        if m * 1 == rest_n:  # 带单
            return start, m
        if m * 2 == rest_n and all(c == 2 for c in rest.values()):
            return start, m
    return None


def beats(move: Optional[Tuple[PairType, int, int]],
          last: Optional[Tuple[PairType, int, int]]) -> bool:
    """move 能否压过 last。last=None 表示自由出牌。"""
    if move is None:
        return False
    if last is None:
        return True
    t1, v1, l1 = move
    t2, v2, l2 = last
    if t1 == PairType.ROCKET:
        return True
    if t2 == PairType.ROCKET:
        return False
    if t1 == PairType.BOMB:
        return t2 != PairType.BOMB or v1 > v2
    if t2 == PairType.BOMB:
        return False
    return t1 == t2 and l1 == l2 and v1 > v2


# ---------------------------------------------------------------------------
# 走法生成
# ---------------------------------------------------------------------------

def _take(cnt: Counter, cards: List[int]) -> None:
    for c in cards:
        cnt[c] -= 1
        if cnt[c] == 0:
            del cnt[c]


def _wings(cnt: Counter, m: int, as_pairs: bool, exclude: set) -> List[List[int]]:
    """从 cnt 中取 m 个单张/对子作为翅膀（不与 exclude 中的 rank 混用可选）。"""
    pool = sorted(r for r, c in cnt.items() if c >= (2 if as_pairs else 1) and r not in exclude)
    results: List[List[int]] = []

    def dfs(i: int, left: int, cur: List[int]) -> None:
        if left == 0:
            results.append(list(cur))
            return
        for j in range(i, len(pool)):
            r = pool[j]
            need = 2 if as_pairs else 1
            if cnt[r] >= need:
                cur.extend([r] * need)
                dfs(j + 1, left - 1, cur)
                del cur[-need:]

    dfs(0, m, [])
    return results


def gen_moves(hand: Sequence[int],
              last: Optional[Tuple[PairType, int, int]]) -> List[List[int]]:
    """生成所有合法走法（含 PASS 由调用方决定是否追加）。

    last=None: 自由出牌，枚举所有牌型。
    last 给定: 枚举同型更大的走法 + 炸弹 + 王炸。
    结果按"消耗从小到大"大致排序（供规则 AI 使用）。
    """
    cnt = Counter(hand)
    moves: List[List[int]] = []
    if last is None or last[0] == PairType.PASS:
        return _gen_free(cnt)
    t, v, l = last
    gen = _GENERATORS.get(t)
    if gen:
        moves.extend(gen(cnt, v, l))
    # 炸弹 & 王炸兜底
    if t != PairType.BOMB and t != PairType.ROCKET or t == PairType.BOMB:
        moves.extend(_gen_bombs(cnt, v if t == PairType.BOMB else 0,
                                only_bigger=(t == PairType.BOMB)))
    if t != PairType.ROCKET and cnt.get(16, 0) and cnt.get(17, 0):
        moves.append([16, 17])
    # 校验 + 去重
    seen, out = set(), []
    for m in moves:
        key = tuple(sorted(m))
        if key not in seen and parse(m) is not None and beats(parse(m), last):
            seen.add(key)
            out.append(sorted(m))
    return sorted(out, key=lambda m: (len(m), max(m)))


# --- 各牌型跟牌生成器 ---

def _f_single(cnt, v, l):
    return [[r] for r in sorted(cnt) if r > v]


def _f_pair(cnt, v, l):
    return [[r, r] for r in sorted(cnt) if cnt[r] >= 2 and r > v]


def _f_trio(cnt, v, l):
    return _f_trio_with(cnt, v, l, 0)


def _f_trio_single(cnt, v, l):
    return _f_trio_with(cnt, v, l, 1)


def _f_trio_pair(cnt, v, l):
    return _f_trio_with(cnt, v, l, 2)


def _f_trio_with(cnt, v, l, wing_kind):
    out = []
    trios = [r for r in sorted(cnt) if cnt[r] >= 3 and r > v]
    for tr in trios:
        rest = Counter(cnt)
        _take(rest, [tr] * 3)
        if wing_kind == 0:
            out.append([tr] * 3)
        elif wing_kind == 1:
            for w in _wings(rest, 1, False, {tr}):
                out.append([tr] * 3 + w)
        else:
            for w in _wings(rest, 1, True, {tr}):
                out.append([tr] * 3 + w)
    return out


def _f_straight(cnt, v, l):
    out = []
    for start in range(v + 1, STRAIGHT_MAX - l + 2):
        if all(cnt.get(r, 0) >= 1 for r in range(start, start + l)):
            out.append(list(range(start, start + l)))
    return out


def _f_pair_straight(cnt, v, l):
    out = []
    for start in range(v + 1, STRAIGHT_MAX - l + 2):
        if all(cnt.get(r, 0) >= 2 for r in range(start, start + l)):
            out.append([r for r in range(start, start + l) for _ in range(2)])
    return out


def _f_plane(cnt, v, l):
    return _f_plane_with(cnt, v, l, 0)


def _f_plane_single(cnt, v, l):
    return _f_plane_with(cnt, v, l, 1)


def _f_plane_pair(cnt, v, l):
    return _f_plane_with(cnt, v, l, 2)


def _f_plane_with(cnt, v, l, wing_kind):
    out = []
    for start in range(v + 1, STRAIGHT_MAX - l + 2):
        seq = range(start, start + l)
        if any(cnt.get(r, 0) < 3 for r in seq):
            continue
        rest = Counter(cnt)
        for r in seq:
            _take(rest, [r] * 3)
        if wing_kind == 0:
            out.append([r for r in seq for _ in range(3)])
        elif wing_kind == 1:
            for w in _wings(rest, l, False, set(seq)):
                out.append([r for r in seq for _ in range(3)] + w)
        else:
            for w in _wings(rest, l, True, set(seq)):
                out.append([r for r in seq for _ in range(3)] + w)
    return out


def _f_four_two(cnt, v, l):
    out = []
    for r in sorted(cnt):
        if cnt[r] == 4 and r > v:
            rest = Counter(cnt)
            _take(rest, [r] * 4)
            for w in _wings(rest, 2, False, {r}):
                out.append([r] * 4 + w)
    return out


def _f_four_two_pair(cnt, v, l):
    out = []
    for r in sorted(cnt):
        if cnt[r] == 4 and r > v:
            rest = Counter(cnt)
            _take(rest, [r] * 4)
            for w in _wings(rest, 2, True, {r}):
                out.append([r] * 4 + w)
    return out


def _gen_bombs(cnt, v, only_bigger):
    return [[r] * 4 for r in sorted(cnt)
            if cnt[r] == 4 and (r > v or not only_bigger)]


_GENERATORS = {
    PairType.SINGLE: _f_single,
    PairType.PAIR: _f_pair,
    PairType.TRIO: _f_trio,
    PairType.TRIO_SINGLE: _f_trio_single,
    PairType.TRIO_PAIR: _f_trio_pair,
    PairType.STRAIGHT: _f_straight,
    PairType.PAIR_STRAIGHT: _f_pair_straight,
    PairType.PLANE: _f_plane,
    PairType.PLANE_SINGLE: _f_plane_single,
    PairType.PLANE_PAIR: _f_plane_pair,
    PairType.FOUR_TWO: _f_four_two,
    PairType.FOUR_TWO_PAIR: _f_four_two_pair,
}


def _gen_free(cnt: Counter) -> List[List[int]]:
    """自由出牌：枚举全部牌型。"""
    out: List[List[int]] = []
    ranks = sorted(cnt)
    out.extend([r] for r in ranks)                                   # 单张
    out.extend([r, r] for r in ranks if cnt[r] >= 2)                 # 对子
    for r in ranks:                                                   # 三张/三带
        if cnt[r] >= 3:
            out.append([r] * 3)
            rest = Counter(cnt)
            _take(rest, [r] * 3)
            for w in _wings(rest, 1, False, {r}):
                out.append([r] * 3 + w)
            for w in _wings(rest, 1, True, {r}):
                out.append([r] * 3 + w)
    for r in ranks:                                                   # 炸弹
        if cnt[r] == 4:
            out.append([r] * 4)
            rest = Counter(cnt)
            _take(rest, [r] * 4)
            for w in _wings(rest, 2, False, {r}):
                out.append([r] * 4 + w)
            for w in _wings(rest, 2, True, {r}):
                out.append([r] * 4 + w)
    # 顺子
    for length in range(5, 13):
        for start in range(RANK_MIN, STRAIGHT_MAX - length + 2):
            if all(cnt.get(r, 0) >= 1 for r in range(start, start + length)):
                out.append(list(range(start, start + length)))
    # 连对
    for length in range(2, 21):
        for start in range(RANK_MIN, STRAIGHT_MAX - length + 2):
            if all(cnt.get(r, 0) >= 2 for r in range(start, start + length)):
                out.append([r for r in range(start, start + length) for _ in range(2)])
    # 飞机
    for length in range(2, 7):
        for start in range(RANK_MIN, STRAIGHT_MAX - length + 2):
            seq = range(start, start + length)
            if any(cnt.get(r, 0) < 3 for r in seq):
                continue
            rest = Counter(cnt)
            for r in seq:
                _take(rest, [r] * 3)
            out.append([r for r in seq for _ in range(3)])
            for w in _wings(rest, length, False, set(seq)):
                out.append([r for r in seq for _ in range(3)] + w)
            for w in _wings(rest, length, True, set(seq)):
                out.append([r for r in seq for _ in range(3)] + w)
    if cnt.get(16) and cnt.get(17):
        out.append([16, 17])
    # 校验去重
    seen, out2 = set(), []
    for m in out:
        key = tuple(sorted(m))
        if key not in seen and parse(m) is not None:
            seen.add(key)
            out2.append(sorted(m))
    return sorted(out2, key=lambda m: (len(m), max(m)))


def is_valid_play(hand: Sequence[int], move: Sequence[int]) -> bool:
    """move 是否是 hand 的子集。"""
    hc, mc = Counter(hand), Counter(move)
    return all(hc[r] >= c for r, c in mc.items())
