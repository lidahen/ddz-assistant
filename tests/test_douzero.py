"""DouZero 适配层端到端测试。无权重时验证降级路径与 obs 构造逻辑;
有权重时（models/douzero/ 存在）验证真实推理。

另外独立验证 _build_infoset + get_obs 的字段契约（无权重也能跑）。
"""
import sys
sys.path.insert(0, r'D:\load\zcode\ddz-assistant')

from ddz.core.cards import PairType, parse
from ddz.douzero_adapter import DouZeroAdapter, _to_env, _from_env, _TO_ENV

ok = fail = 0


def check(name, cond):
    global ok, fail
    if cond:
        ok += 1
    else:
        fail += 1
        print(f'FAIL: {name}')


# --- 编码映射 ---
check('env_map_2', _TO_ENV[15] == 17)
check('env_map_x', _TO_ENV[16] == 20)
check('env_map_d', _TO_ENV[17] == 30)
check('env_roundtrip', _from_env(_to_env([3, 15, 16, 17])) == [3, 15, 16, 17])

# --- InfoSet 契约: 用 douzero 的 get_obs 验证字段齐全 ---
import numpy as np
from douzero.env.env import get_obs

hand_env = _to_env([3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 15, 15])
other_env = _to_env([3, 3, 4, 4, 5, 5, 16, 17, 17, 17])
legal = [_to_env(m) for m in ([16], [17], [16, 17], [15], [])]
it = DouZeroAdapter._build_infoset(
    'landlord_down', hand_env, other_env, legal,
    _to_env([12, 12]),                       # 上家出对Q
    {'landlord': _to_env([12, 12]), 'landlord_up': [9], 'landlord_down': []},
    {'landlord': 17, 'landlord_up': 16, 'landlord_down': 15},
    bomb_num=1)
try:
    obs = get_obs(it)
    check('get_obs_ok', True)
    check('x_batch_shape', obs['x_batch'].shape[0] == len(legal))
    check('z_batch_shape', obs['z_batch'].shape == (len(legal), 5, 162))
    check('legal_actions_kept', obs['legal_actions'] == legal)
except Exception as e:
    check(f'get_obs_ok ({type(e).__name__}: {e})', False)

# --- act() 降级路径 ---
dz = DouZeroAdapter()
if dz.available:
    print('权重已就绪，跑真实推理...')
    move = dz.act([3, 4, 5, 6, 7, 8, 9, 10, 11, 15, 15, 15, 14, 17, 17, 16], {
        'last_move': (PairType.SINGLE, 12, 1),
        'role': 'farmer', 'landlord_side': 'right',
        'zone_plays': {'left_play': [12, 12], 'right_play': [], 'my_play': []},
    })
    check('act_returns', move is not None)
    print(f'DouZero 建议跟单Q: {move}')
else:
    check('degrade_to_none', dz.act([3], {}) is None)
    print(f'无权重，降级路径 OK: {dz.error}')

print(f'\n{ok} passed, {fail} failed')
sys.exit(1 if fail else 0)
