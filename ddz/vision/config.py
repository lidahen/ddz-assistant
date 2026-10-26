"""配置: 所有依赖游戏画面的参数集中在此，标定后回填。

使用流程:
1. 先跑 calib/capture.py 截一张对局图
2. 按 calib/README 说明填 REGIONS 的坐标
3. 跑 calib/make_templates.py 切牌面模板
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

# 窗口标题关键字（按顺序匹配，找到第一个含该关键字的可见窗口）
WINDOW_TITLES = ['欢乐斗地主', '斗地主', '微信', 'QQ']

# 模板库目录（相对项目根）
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), '..', 'models', 'templates')

# 匹配阈值
MATCH_THRESHOLD = 0.80   # 模板匹配置信度
NMS_DISTANCE = 12        # 非极大值抑制的最小间距(像素)

# 多尺度匹配: (相对模板的缩放因子)。标定完主尺度后可只留 [1.0]
MATCH_SCALES = [1.0, 0.9, 1.1]


@dataclass
class Regions:
    """游戏画面关键区域，均为窗口内相对坐标 (x, y, w, h)，按 1080p 设计。

    标定方法见 calib/README.md。None 表示尚未标定。
    """
    # 我的手牌区（底部一排牌）
    my_hand: Optional[Tuple[int, int, int, int]] = None
    # 我出的牌区（手牌上方中央）
    my_play: Optional[Tuple[int, int, int, int]] = None
    # 下家（右）出牌区
    right_play: Optional[Tuple[int, int, int, int]] = None
    # 上家（左）出牌区
    left_play: Optional[Tuple[int, int, int, int]] = None
    # 上家剩余牌数显示区
    left_count: Optional[Tuple[int, int, int, int]] = None
    # 下家剩余牌数显示区
    right_count: Optional[Tuple[int, int, int, int]] = None
    # 地主标识附近（判断谁地主）
    landlord_badge: Optional[Tuple[int, int, int, int]] = None
    # "不出/不要"按钮区域（判断 PASS）
    pass_button: Optional[Tuple[int, int, int, int]] = None

    def all_regions(self) -> Dict[str, Optional[Tuple[int, int, int, int]]]:
        return {
            'my_hand': self.my_hand, 'my_play': self.my_play,
            'right_play': self.right_play, 'left_play': self.left_play,
            'left_count': self.left_count, 'right_count': self.right_count,
            'landlord_badge': self.landlord_badge, 'pass_button': self.pass_button,
        }

    def missing(self) -> list:
        return [k for k, v in self.all_regions().items() if v is None]


# 标定结果存这里（calib/calibrated.py 会生成并覆盖此默认值）
REGIONS = Regions()

try:  # 加载标定结果
    from .calibrated import REGIONS as _CAL  # type: ignore
    REGIONS = _CAL
except ImportError:
    pass
