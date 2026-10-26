"""主循环: 找窗口 -> 截屏 -> 识别 -> 状态机 -> 决策 -> 悬浮窗建议。

用法:
  python -m ddz.main            # 正常运行
  python -m ddz.main --dry-run  # 无窗口/未标定时空跑，验证链路
"""
from __future__ import annotations

import argparse
import time
from collections import Counter

from .core.cards import PairType, parse
from .core.rule_ai import RuleAI
from .douzero_adapter import DouZeroAdapter
from .state import GameState
from .ui.overlay import SuggestWindow, format_move
from .vision.capture import capture_window, find_game_window
from .vision.recognizer import CardRecognizer


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true', help='空跑模式: 不截屏，用模拟手牌验证链路')
    ap.add_argument('--fps', type=float, default=2.0)
    args = ap.parse_args()

    if args.dry_run:
        return _dry_run()

    win = SuggestWindow()
    rec = CardRecognizer()
    state = GameState()
    rule_ai = RuleAI()
    dz = DouZeroAdapter()
    mode = '出牌'
    if not dz.available:
        print(f'[douzero] 降级到规则 AI: {dz.error}')

    while True:
        try:
            img = capture_window()
        except RuntimeError as e:
            win.update('错误', str(e)[:40])
            time.sleep(2)
            continue
        except Exception as e:
            win.update('截屏失败', f'{type(e).__name__}')
            time.sleep(2)
            continue

        try:
            state.update_frame(img, rec)
        except RuntimeError as e:  # 区域未标定
            win.update('未标定', '请先运行标定', str(e)[:80])
            time.sleep(5)
            continue
        except ValueError as e:  # 识别结果非法
            win.update('识别异常', str(e)[:60])
            time.sleep(1)
            continue

        ctx = state.decision_context()
        hand = ctx['my_hand']
        if not hand:
            win.update('未检测到手牌', '—', '进入对局后自动开始')
            time.sleep(1)
            continue

        # 决策: DouZero 可用则模型优先，否则规则 AI
        move, engine = None, '规则AI'
        if dz.available:
            move = dz.act(hand, ctx)
            if move is not None:
                engine = 'DouZero'
        if move is None:
            last_player = 'landlord' if ctx['last_zone'] != 'my_play' else None
            move = rule_ai.decide(hand, ctx['last_move'], last_player,
                                  'farmer', ctx['hand_counts'])
            if move:
                pt = parse(move)
                mode = f'跟牌({pt[0].name})' if ctx['last_move'] else '出牌'
        elif move:
            pt = parse(move)

        state_text = f'手牌{len(hand)}张 | {mode} | 上家: {ctx["last_zone"] or "—"}'
        win.update(state_text, format_move(move), f'引擎: {engine}')

        time.sleep(1.0 / args.fps)


def _dry_run():
    """空跑: 模拟一手牌走通 识别->状态->决策->悬浮窗 链路。"""
    from collections import Counter
    print('=== dry-run: 链路自检 ===')
    hand = [3, 4, 5, 6, 7, 8, 9, 10, 11, 15, 15, 15, 14, 17, 17, 16]
    print(f'模拟手牌: {len(hand)} 张')

    state = GameState()
    state.my_hand = hand
    ctx = state.decision_context()
    assert ctx['my_hand'] == hand

    ai = RuleAI()
    lead = ai._lead(hand, Counter(hand), 'farmer', None)
    print(f'自由出牌建议: {lead} -> {parse(lead)}')

    last = (PairType.SINGLE, 12, 1)
    from .core.cards import gen_moves
    moves = gen_moves(hand, last)
    follow = ai.decide(hand, last, 'landlord', 'farmer',
                       {'farmer_peer': 10, 'landlord': 3})
    print(f'跟单Q建议: {follow} ({len(moves)} 个可跟)')

    dz = DouZeroAdapter()
    print(f'DouZero: {"可用" if dz.available else f"降级 ({dz.error})"}')

    win = SuggestWindow()
    win.update('dry-run 手牌16张 | 出牌', format_move(lead), '链路 OK，窗口 3 秒后自动退出')
    time.sleep(3)
    win.close()
    print('OK')


if __name__ == '__main__':
    main()
