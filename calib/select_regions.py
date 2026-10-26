"""标定步骤 2: 交互式框选区域，自动写入 ddz/vision/calibrated.py。

用法: python calib/select_regions.py frame.png
弹出 frame.png，鼠标拖框，每框一个区域，按顺序提示区域名；ESC 跳过，q 退出保存。
"""
import os
import sys

import cv2

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

REGIONS = ['my_hand', 'my_play', 'right_play', 'left_play',
           'left_count', 'right_count', 'landlord_badge', 'pass_button']

# 1080p 欢乐斗地主的典型区域比例（作为预填初始值，可用拖框覆盖）:
# my_hand: 底部手牌条  my_play: 手牌上方中央  left/right_play: 中部两侧
DEFAULTS = {
    'my_hand': (0.10, 0.82, 0.80, 0.17),
    'my_play': (0.30, 0.55, 0.40, 0.18),
    'right_play': (0.62, 0.38, 0.25, 0.16),
    'left_play': (0.13, 0.38, 0.25, 0.16),
    'left_count': (0.02, 0.28, 0.10, 0.08),
    'right_count': (0.88, 0.28, 0.10, 0.08),
}


def main():
    img_path = sys.argv[1] if len(sys.argv) > 1 else \
        os.path.join(os.path.dirname(__file__), 'frame.png')
    img = cv2.imread(img_path)
    if img is None:
        print(f'无法读取 {img_path}，先运行 capture.py')
        return 1
    H, W = img.shape[:2]
    result = {}

    print('拖框选区域; 回车确认当前区域, s 跳过, q 结束保存')
    for name in REGIONS:
        disp = img.copy()
        if name in DEFAULTS:
            fx, fy, fw, fh = DEFAULTS[name]
            x0, y0 = int(fx * W), int(fy * H)
            cv2.rectangle(disp, (x0, y0),
                          (x0 + int(fw * W), y0 + int(fh * H)), (0, 255, 0), 2)
            cv2.putText(disp, f'{name} (default)', (x0, y0 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.imshow('select', disp)
        print(f'>> {name}: 回车=用默认{"有" if name in DEFAULTS else "无"}/拖框, s=跳过, q=保存退出')
        key = cv2.waitKey(0) & 0xFF
        if key == ord('q'):
            break
        if key == ord('s'):
            continue
        if key == 13:  # Enter: 用默认或跳过
            if name in DEFAULTS:
                fx, fy, fw, fh = DEFAULTS[name]
                result[name] = (int(fx * W), int(fy * H), int(fw * W), int(fh * H))
            continue
        roi = cv2.selectROI(f'drag: {name}', img, showCrosshair=True)
        cv2.destroyWindow(f'drag: {name}')
        if roi[2] > 0 and roi[3] > 0:
            result[name] = tuple(int(v) for v in roi)

    out = os.path.join(os.path.dirname(__file__), 'calibrated.py')
    with open(out, 'w', encoding='utf-8') as f:
        f.write('"""自动生成的标定结果。由 calib/select_regions.py 生成。"""\n')
        f.write('from .config import Regions\n\n')
        f.write('REGIONS = Regions(\n')
        for k, v in result.items():
            f.write(f'    {k}={v},\n')
        f.write(')\n')
    # 同时拷到包内
    pkg = os.path.join(os.path.dirname(__file__), '..', 'ddz', 'vision', 'calibrated.py')
    with open(out, encoding='utf-8') as f:
        with open(pkg, 'w', encoding='utf-8') as g:
            g.write(f.read())
    print(f'已写入 {out} 和 {pkg}')
    print('区域:', result)
    return 0


if __name__ == '__main__':
    sys.exit(main())
