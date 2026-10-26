"""cards / rule_ai / game 的快速自测。"""
import sys
sys.path.insert(0, r'D:\load\zcode\ddz-assistant')

from ddz.core.cards import (PairType, beats, cards_to_str, gen_moves,
                            is_valid_play, parse, str_to_cards)
from ddz.core.rule_ai import RuleAI, decompose

P = PairType
ok = fail = 0


def check(name, cond):
    global ok, fail
    if cond:
        ok += 1
    else:
        fail += 1
        print(f'FAIL: {name}')


# --- parse 基本牌型 ---
check('single', parse([7]) == (P.SINGLE, 7, 1))
check('pair', parse([7, 7]) == (P.PAIR, 7, 1))
check('trio', parse([7, 7, 7]) == (P.TRIO, 7, 1))
check('trio1', parse([7, 7, 7, 3]) == (P.TRIO_SINGLE, 7, 1))
check('trio2', parse([7, 7, 7, 3, 3]) == (P.TRIO_PAIR, 7, 1))
check('straight5', parse([3, 4, 5, 6, 7]) == (P.STRAIGHT, 3, 5))
check('straightJQKA', parse([11, 12, 13, 14]) is None)  # 4张不是顺子
check('straight10JQKA', parse([10, 11, 12, 13, 14]) == (P.STRAIGHT, 10, 5))
check('no2instraight', parse([13, 14, 15, 16, 17]) is None)
check('pairstraight', parse([4, 4, 5, 5, 6, 6]) == (P.PAIR_STRAIGHT, 4, 3))
check('plane2', parse([3, 3, 3, 4, 4, 4]) == (P.PLANE, 3, 2))
check('plane2s', parse([3, 3, 3, 4, 4, 4, 5, 6]) == (P.PLANE_SINGLE, 3, 2))
check('plane2p', parse([3, 3, 3, 4, 4, 4, 5, 5, 6, 6]) == (P.PLANE_PAIR, 3, 2))
check('bomb', parse([5, 5, 5, 5]) == (P.BOMB, 5, 1))
check('rocket', parse([16, 17]) == (P.ROCKET, 17, 1))
check('four2', parse([5, 5, 5, 5, 3, 4]) == (P.FOUR_TWO, 5, 1))
check('four2pair', parse([5, 5, 5, 5, 3, 3, 4, 4]) == (P.FOUR_TWO_PAIR, 5, 1))
check('invalid', parse([3, 3, 4, 4, 5]) is None)
check('plane_amb_333444555', parse([3, 3, 3, 4, 4, 4, 5, 5, 5]) in
      ((P.PLANE, 3, 3), (P.PLANE, 4, 3)))  # 两种解释都合法

# --- beats ---
check('bomb_beats_straight', beats((P.BOMB, 5, 1), (P.STRAIGHT, 3, 5)))
check('rocket_beats_bomb', beats((P.ROCKET, 17, 1), (P.BOMB, 15, 1)))
check('bomb_no_beat_bigger_bomb', not beats((P.BOMB, 5, 1), (P.BOMB, 8, 1)))
check('same_type', beats((P.PAIR, 6, 1), (P.PAIR, 5, 1)))
check('diff_type', not beats((P.PAIR, 9, 1), (P.SINGLE, 3, 1)))
check('length_mismatch', not beats((P.STRAIGHT, 3, 5), (P.STRAIGHT, 3, 6)))
check('free', beats((P.SINGLE, 3, 1), None))

# --- gen_moves 跟牌 ---
hand = str_to_cards('334455667JQKA2D')  # 2=15 D=大王
mv = gen_moves(hand, (P.SINGLE, 9, 1))
check('follow_single_has_J', [11] in mv)
check('follow_single_has_A', [14] in mv)
check('follow_single_no_below', all(m[0] > 9 for m in mv))
check('follow_single_no_rocket_no_doubleking', [16, 17] not in mv)  # 只有单王

mv = gen_moves(hand, (P.PAIR, 5, 1))
check('follow_pair_66', [6, 6] in mv)
check('follow_pair_no_33_below', [3, 3] not in mv)

mv = gen_moves(hand, (P.STRAIGHT, 3, 5))
check('follow_straight_none_without_8', mv == [])  # 手牌 4-7 只有四连

# 有炸弹的手牌跟牌
hand2 = str_to_cards('334444JQKA2D')
mv = gen_moves(hand2, (P.SINGLE, 9, 1))
check('bomb_hand_follow', [11] in mv)
check('follow_single_bomb', [4, 4, 4, 4] in mv)

# 顺子跟牌（手牌含 45678910）
hand3 = str_to_cards('45678910JQ')
mv = gen_moves(hand3, (P.STRAIGHT, 3, 5))
check('follow_straight_45678', [4, 5, 6, 7, 8] in mv)
check('follow_straight_56789', [5, 6, 7, 8, 9] in mv)
check('follow_straight_678910', [6, 7, 8, 9, 10] in mv)

mv = gen_moves(hand, (P.BOMB, 8, 1))
check('bomb_over_bomb', [4, 4, 4, 4] not in mv)

mv = gen_moves(str_to_cards('33345'), (P.SINGLE, 3, 1))
check('solo_has_all', all(m in mv for m in ([4], [5])))

# --- decompose ---
d = decompose(str_to_cards('334455667'))
check('decompose_seq', len(d) <= 3)
d = decompose(str_to_cards('333444555666777888'))
check('decompose_planes', len(d) <= 5)
d = decompose(str_to_cards('3'))
check('decompose_single', d == [[3]])
# 拆分应覆盖整手牌
import itertools
h = str_to_cards('34567JQKA2XD')
flat = sorted(itertools.chain(*decompose(h)))
check('decompose_covers', flat == sorted(h))

# --- is_valid_play ---
check('valid_play', is_valid_play([3, 4, 5], [3, 4]))
check('invalid_play', not is_valid_play([3, 4], [3, 4, 5]))

print(f'\n{ok} passed, {fail} failed')
sys.exit(1 if fail else 0)
