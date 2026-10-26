"""DouZero 预训练模型适配层（推理路径完整实现）。

设计:
- 不重放对局历史，直接从单帧状态构造 InfoSet（截屏助手天然只见当前局面）
- 未见过的牌随机采样分给两家对手，采样 NUM_SAMPLES 次取动作值平均
- 历史特征(z序列/last_move_dict/played_cards)用当前可见出牌区近似，未见历史为零
  —— 核心特征(手牌/他家牌/上家动作/炸弹数/剩牌数)是准确的

权重获取: 从 https://github.com/kwai/DouZero README 的网盘下载，
将 landlord.ckpt / landlord_up.ckpt / landlord_down.ckpt 放入 models/douzero/
(放在子目录里也可以，会递归查找)。

编码映射: 内部 3..14 不变, 15(2)->17, 16(小王)->20, 17(大王)->30。
"""
from __future__ import annotations

import os
import random
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

# 内部牌值 -> DouZero env 牌值
_TO_ENV = {r: r for r in range(3, 15)}
_TO_ENV.update({15: 17, 16: 20, 17: 30})
_FROM_ENV = {v: k for k, v in _TO_ENV.items()}

# 采样次数与默认剩牌数
NUM_SAMPLES = 4
DEFAULT_COUNTS = {'landlord': 20, 'landlord_up': 17, 'landlord_down': 17}


def _to_env(cards: Sequence[int]) -> List[int]:
    return sorted(_TO_ENV[c] for c in cards)


def _stub_git_module() -> None:
    """douzero.dmc.__init__ 连带导入训练专用的 file_writer，其顶层 import git
    (GitPython) 只在训练记录元数据时用到。推理不需要，注入 stub 绕过，
    避免 pip 多装一个包。必须在首次导入 douzero 前调用。"""
    import sys
    import types
    if 'git' not in sys.modules:
        try:
            import git  # noqa: F401  用户已装 GitPython 则不注入
        except ImportError:
            stub = types.ModuleType('git')
            stub.Repo = None
            sys.modules['git'] = stub


def _from_env(move: Sequence[int]) -> List[int]:
    return sorted(_FROM_ENV[c] for c in move)


def position_map(role: str, landlord_side: str) -> Dict[str, str]:
    """物理方位('my'/'left'/'right') -> DouZero 位置名。

    出牌顺序: landlord -> landlord_down -> landlord_up -> landlord。
    """
    if role == 'landlord':
        return {'my': 'landlord', 'left': 'landlord_up', 'right': 'landlord_down'}
    if landlord_side == 'left':    # 上家是地主: landlord -> 我 -> 队友(right)
        return {'my': 'landlord_down', 'right': 'landlord_up', 'left': 'landlord'}
    else:                          # 下家是地主: 我 -> landlord(right) -> 队友(left)
        return {'my': 'landlord_up', 'left': 'landlord_down', 'right': 'landlord'}


class DouZeroAdapter:
    """加载三个位置的 checkpoint，提供 act()。加载失败 model=None 自动降级。"""

    def __init__(self, model_dir: Optional[str] = None):
        root = Path(__file__).resolve().parent.parent
        # models/ 下递归查找 ckpt，兼容 baselines/douzero_WP 等任意子目录布局
        self.model_dir = str(model_dir or (root / 'models'))
        self.models: Dict[str, object] = {}
        self.error: Optional[str] = None
        self._rng = random.Random(2026)
        self._load()

    # ------------------------------------------------------------------
    def _load(self) -> None:
        _stub_git_module()
        try:
            import torch
            from douzero.dmc.models import model_dict
        except ImportError as e:
            self.error = f'缺少依赖: {e} (pip install douzero torch)'
            return
        if not os.path.isdir(self.model_dir):
            self.error = (f'未找到权重目录 {self.model_dir}: 请下载 DouZero 预训练'
                          f'checkpoint 放入（landlord/landlord_up/landlord_down.ckpt），'
                          f'当前使用规则 AI。')
            return
        # 递归查找三个 ckpt
        found: Dict[str, str] = {}
        for dirpath, _, files in os.walk(self.model_dir):
            for fn in files:
                for pos in ('landlord', 'landlord_up', 'landlord_down'):
                    if fn == f'{pos}.ckpt':
                        found[pos] = os.path.join(dirpath, fn)
        missing = [p for p in ('landlord', 'landlord_up', 'landlord_down')
                   if p not in found]
        if missing:
            self.error = f'权重目录缺少 {missing}，当前使用规则 AI。'
            return
        try:
            for pos, path in found.items():
                model = model_dict[pos]()
                state = model.state_dict()
                pretrained = torch.load(path, map_location='cpu')
                pretrained = {k: v for k, v in pretrained.items() if k in state}
                state.update(pretrained)
                model.load_state_dict(state)
                model.eval()
                self.models[pos] = model
        except Exception as e:
            self.models = {}
            self.error = f'权重加载失败: {type(e).__name__}: {e}'

    @property
    def available(self) -> bool:
        return bool(self.models)

    # ------------------------------------------------------------------
    def act(self, my_hand: Sequence[int], other_info: dict) -> Optional[List[int]]:
        """模型推理出牌（内部编码返回）。不可用/失败返回 None。

        other_info 字段:
          last_move: 上家牌型 tuple 或 None(自由出牌)
          role: 'farmer' | 'landlord'
          landlord_side: 'left' | 'right'（我方是农民时地主方位）
          zone_plays: {'left_play': [...], 'right_play': [...], 'my_play': [...]}
        """
        if not self.available:
            return None
        import numpy as np
        import torch
        _stub_git_module()
        from douzero.env.env import get_obs

        from .core.cards import PairType, gen_moves, parse

        role = other_info.get('role', 'farmer')
        landlord_side = other_info.get('landlord_side', 'right')
        pmap = position_map(role, landlord_side)
        my_pos = pmap['my']
        other_pos = [p for p in ('landlord', 'landlord_up', 'landlord_down')
                     if p != my_pos]

        last_move = other_info.get('last_move')
        zone_plays: Dict[str, List[int]] = other_info.get('zone_plays') or {}

        # 合法走法（自己的生成器，含跟牌与炸弹; 有上家时补 PASS）
        try:
            moves = gen_moves(my_hand, last_move)
            if last_move is not None:
                moves = moves + [[]]
            legal_env = [_to_env(m) for m in moves]
        except Exception:
            return None
        if not legal_env:
            return None

        # 上家动作（env 编码）
        last_env = _to_env(last_move and _last_move_cards(other_info) or [])

        # 各位置可见出牌 -> played_cards / last_move_dict / bomb_num
        played_env: Dict[str, List[int]] = {}
        for side, pos in pmap.items():
            zone = f'{side}_play'
            played_env[pos] = _to_env(zone_plays.get(zone, []) or [])
        bomb_num = sum(1 for cards in zone_plays.values()
                       if cards and (t := parse(cards)) and
                       t[0] in (PairType.BOMB, PairType.ROCKET))

        # 采样池: 全副牌 - 我的手牌 - 可见出牌
        deck = [r for r in range(3, 16) for _ in range(4)] + [16, 17]
        used = list(my_hand) + [c for cards in zone_plays.values() for c in (cards or [])]
        pool = _remove_cards(deck, used)

        my_env = _to_env(my_hand)

        # 各对手真实剩牌数: 有 OCR 值用手牌数，否则用初始数-可见出牌估计，
        # 并 clamp 到 DouZero one-hot 编码上限（地主20/农民17）——溢出会 IndexError
        target_sizes: Dict[str, int] = {}
        hand_counts = other_info.get('hand_counts') or {}
        for p in other_pos:
            side = {v: k for k, v in pmap.items()}[p]
            if hand_counts.get(side):
                n = hand_counts[side]
            else:
                cap = 20 if p == 'landlord' else 17
                n = min(cap, DEFAULT_COUNTS[p] - len(played_env.get(p, [])))
            target_sizes[p] = max(1, min(n, 20 if p == 'landlord' else 17))

        values = np.zeros(len(legal_env), dtype=np.float64)
        valid = 0
        with torch.no_grad():
            for _ in range(NUM_SAMPLES):
                hands = self._sample_others(pool, other_pos, target_sizes)
                if hands is None:
                    continue
                other_env = sorted(hands[0] + hands[1])
                num_left = {my_pos: len(my_env)}
                for p, h in zip(other_pos, hands):
                    num_left[p] = len(h)
                infoset = self._build_infoset(
                    my_pos, my_env, other_env, legal_env, last_env,
                    played_env, num_left, bomb_num)
                try:
                    obs = get_obs(infoset)
                    z = torch.from_numpy(obs['z_batch']).float()
                    x = torch.from_numpy(obs['x_batch']).float()
                    out = self.models[my_pos].forward(z, x, return_value=True)
                    values += out['values'].detach().cpu().numpy().ravel()
                    valid += 1
                except Exception:
                    continue
        if not valid:
            return None
        best = int(values.argmax())
        best_env = legal_env[best]
        return _from_env(best_env)

    # ------------------------------------------------------------------
    @staticmethod
    def _sample_others(pool: List[int], other_pos: List[str],
                       target_sizes: Dict[str, int]):
        """把未知牌随机分给两家对手。

        pool 是内部编码（含 15/16/17），返回前转成 env 编码。
        target_sizes: 每个对手的目标手牌数（已 clamp 过）。
        池里牌不够分时按比例缩减（其余视为已打出但未见的牌）。
        返回 [env编码手牌, ...] 或 None。
        """
        rng = random.Random()
        cards = list(pool)
        rng.shuffle(cards)
        # 顺序分配: 每家 clamp 到目标值，最后一家不吞"剩余全部"
        # （池中未分配的牌视为已打出但屏幕上未显示的牌）
        out_sizes = []
        remaining = len(cards)
        for i, p in enumerate(other_pos):
            if i == len(other_pos) - 1:
                n = min(target_sizes[p], remaining)   # 最后一家不再吞"剩余全部"
            else:
                n = min(target_sizes[p], remaining)
            out_sizes.append(n)
            remaining -= n
        if any(n < 0 for n in out_sizes):
            return None
        out, idx = [], 0
        for n in out_sizes:
            out.append(_to_env(sorted(cards[idx:idx + n])))
            idx += n
        return out

    @staticmethod
    def _build_infoset(my_pos, my_env, other_env, legal_env, last_env,
                       played_env, num_left, bomb_num):
        from douzero.env.game import InfoSet
        it = InfoSet(my_pos)
        it.player_hand_cards = list(my_env)
        it.num_cards_left_dict = num_left
        it.three_landlord_cards = []
        it.card_play_action_seq = []          # 历史序列未知 -> 空为零填充
        it.other_hand_cards = list(other_env)
        it.legal_actions = legal_env
        it.last_move = list(last_env)
        it.last_two_moves = [[], []]
        it.last_move_dict = {p: list(played_env.get(p, []))
                             for p in ('landlord', 'landlord_up', 'landlord_down')}
        it.played_cards = {p: list(played_env.get(p, []))
                           for p in ('landlord', 'landlord_up', 'landlord_down')}
        it.all_handcards = {}
        it.last_pid = None
        it.bomb_num = bomb_num
        return it


def _last_move_cards(other_info: dict) -> List[int]:
    """上家出的牌: 从 zone_plays 里找与 last_move 牌型匹配的可见牌。

    last_move 只有牌型 tuple，可见区里同型可能多家——取"压过最狠"的那家
    （跟牌要压的就是当前圈最大的），与 state.decision_context 的选取一致。
    """
    from .core.cards import beats, parse
    last = other_info.get('last_move')
    zone_plays: Dict[str, List[int]] = other_info.get('zone_plays') or {}
    best: List[int] = []
    for cards in zone_plays.values():
        if not cards:
            continue
        pt = parse(cards)
        if pt and pt == last and (not best or beats(pt, parse(best))):
            best = list(cards)
    return best


def _remove_cards(deck: List[int], used: Sequence[int]) -> List[int]:
    pool = list(deck)
    for c in used:
        if c in pool:
            pool.remove(c)
    return pool
