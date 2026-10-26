"""牌面识别: 模板匹配 + 非极大值抑制。

模板来源: calib/make_templates.py 从标定截图切出，命名规范:
  - 手牌主数字: rank/rank_3.png ... rank/2.png, rank/X.png, rank/D.png
  - 出牌区小牌: small/rank_3.png 等（两套模板区分大小牌面）
识别思路: 欢乐斗地主手牌每张牌左上角有 rank 数字，按 x 坐标聚类定位每张牌。
"""
from __future__ import annotations

import os
from collections import Counter
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from .config import (MATCH_SCALES, MATCH_THRESHOLD, NMS_DISTANCE, TEMPLATE_DIR)

_CHAR_BY_RANK = {3: '3', 4: '4', 5: '5', 6: '6', 7: '7', 8: '8', 9: '9', 10: '10',
                 11: 'J', 12: 'Q', 13: 'K', 14: 'A', 15: '2', 16: 'X', 17: 'D'}


class CardRecognizer:
    def __init__(self, template_dir: str = TEMPLATE_DIR):
        self.template_dir = template_dir
        self._templates: Dict[str, List[Tuple[str, np.ndarray]]] = {}

    def load_templates(self, subdir: str = 'rank') -> None:
        """加载 rank/ 下所有模板。文件名: 3.png...10.png, J.png, 2.png, X.png, D.png"""
        path = os.path.join(self.template_dir, subdir)
        if not os.path.isdir(path):
            raise FileNotFoundError(
                f'模板目录不存在: {path}\n'
                f'请先运行 calib/make_templates.py 生成模板。')
        self._templates[subdir] = []
        for fn in sorted(os.listdir(path)):
            if not fn.endswith('.png'):
                continue
            img = cv2.imread(os.path.join(path, fn), cv2.IMREAD_GRAYSCALE)
            if img is not None:
                self._templates[subdir].append((fn[:-4], img))

    def recognize_hand(self, window_img: np.ndarray) -> List[int]:
        """识别我的手牌区，返回去重合并后的牌值列表（按 x 排序，含同点数多张）。"""
        region = self._crop_by_key(window_img, 'my_hand')
        hits = self._match_all(region, 'rank')
        return self._cluster_to_cards(hits)

    def recognize_play(self, window_img: np.ndarray, which: str) -> List[int]:
        """识别某个出牌区。which: my_play / left_play / right_play。空区返回 []。"""
        region = self._crop_by_key(window_img, which)
        if region is None or region.size == 0:
            return []
        hits = self._match_all(region, 'small')
        return self._cluster_to_cards(hits)

    # --- 内部 ---

    def _crop_by_key(self, img: np.ndarray, region_key: str) -> Optional[np.ndarray]:
        from .config import REGIONS
        r = getattr(REGIONS, region_key, None)
        if r is None:
            raise RuntimeError(f'区域 {region_key} 未标定，请先运行标定流程。')
        x, y, w, h = r
        return img[y:y + h, x:x + w]

    def _match_all(self, region: np.ndarray, subdir: str) -> List[Tuple[int, int, float, str]]:
        """多尺度模板匹配，返回命中 (cx, cy, score, name) 列表。"""
        if subdir not in self._templates:
            self.load_templates(subdir)
        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
        hits = []
        for name, tpl in self._templates[subdir]:
            th, tw = tpl.shape
            for scale in MATCH_SCALES:
                if scale != 1.0:
                    t2 = cv2.resize(tpl, None, fx=scale, fy=scale,
                                    interpolation=cv2.INTER_AREA)
                else:
                    t2 = tpl
                if t2.shape[0] >= gray.shape[0] or t2.shape[1] >= gray.shape[1]:
                    continue
                res = cv2.matchTemplate(gray, t2, cv2.TM_CCOEFF_NORMED)
                ys, xs = np.where(res >= MATCH_THRESHOLD)
                for y, x in zip(ys, xs):
                    hits.append((int(x + t2.shape[1] / 2), int(y + t2.shape[0] / 2),
                                 float(res[y, x]), name))
        return hits

    def _cluster_to_cards(self, hits: List[Tuple[int, int, float, str]]) -> List[int]:
        """按 x 坐标聚类成一张张牌，每簇取最高分模板作为该牌 rank。"""
        if not hits:
            return []
        hits.sort(key=lambda h: h[0])
        clusters: List[List] = []
        for h in hits:
            if clusters and h[0] - clusters[-1][-1][0] <= NMS_DISTANCE:
                clusters[-1].append(h)
            else:
                clusters.append([h])
        cards = []
        for cl in clusters:
            best = max(cl, key=lambda h: h[2])
            cards.append(_char_to_rank(best[3]))
        return cards  # 已按 x 升序 = 牌面从左到右

    def count_from_region(self, window_img: np.ndarray, which: str) -> Optional[int]:
        """识别剩余牌数（OCR 数字简化版：单/双位数模板匹配）。标定后补充。"""
        # 预留：用 digit 模板匹配实现，标定时生成 digit/ 模板
        return None


def _char_to_rank(ch: str) -> int:
    rev = {v: k for k, v in _CHAR_BY_RANK.items()}
    if ch not in rev:
        raise ValueError(f'未知模板名: {ch}')
    return rev[ch]


def dedup_hand(cards: List[int]) -> List[int]:
    """识别结果一致性校验用：每张牌最多 4 份、王各 1 份，非法则上抛。"""
    c = Counter(cards)
    problems = []
    if c.get(16, 0) > 1:
        problems.append('小王超过1张')
    if c.get(17, 0) > 1:
        problems.append('大王超过1张')
    for r, n in c.items():
        if r not in (16, 17) and n > 4:
            problems.append(f'{_CHAR_BY_RANK[r]} 超过4张({n})')
    if problems:
        raise ValueError(f'识别结果非法: {"; ".join(problems)} (raw={cards})')
    return cards
