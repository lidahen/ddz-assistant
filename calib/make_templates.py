"""标定步骤 3: 从 my_hand 区域切出 15 种 rank 模板。

用法: python calib/make_templates.py frame.png
对手牌区每张牌取左上角 rank 数字区域。为省事：交互式点击每张牌左上角，
自动切以点击点为左上角的固定大小块，按键输入该牌的 rank 字符。
"""
import os
import sys

import cv2

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from ddz.vision.config import REGIONS, TEMPLATE_DIR

TPL_W, TPL_H = 34, 40   # 模板尺寸: 覆盖手牌左上角的 rank 数字（1080p 参考值，可在下密调）


def main():
    img_path = sys.argv[1] if len(sys.argv) > 1 else \
        os.path.join(os.path.dirname(__file__), 'frame.png')
    img = cv2.imread(img_path)
    if img is None:
        print(f'无法读取 {img_path}，先运行 capture.py')
        return 1

    r = REGIONS.my_hand
    if r is None:
        print('my_hand 未标定，先运行 select_regions.py')
        return 1
    x, y, w, h = r
    hand_img = img[y:y + h, x:x + w]

    os.makedirs(os.path.join(TEMPLATE_DIR, 'rank'), exist_ok=True)
    print(f'在弹窗里单击每张牌的 rank 数字左上角，然后在终端输入牌面(如 3 J 2 X D 10)，回车确认; q 结束')
    clicks = []

    def on_mouse(event, mx, my, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            clicks.append((mx, my))

    cv2.namedWindow('hand', cv2.WINDOW_NORMAL)
    cv2.imshow('hand', hand_img)
    cv2.setMouseCallback('hand', on_mouse)
    n_saved = 0
    while True:
        key = cv2.waitKey(50) & 0xFF
        if key == ord('q'):
            break
        if clicks:
            cx, cy = clicks.pop(0)
            tpl = hand_img[cy:cy + TPL_H, cx:cx + TPL_W]
            if tpl.size == 0:
                continue
            cv2.imshow('tpl', cv2.resize(tpl, (TPL_W * 4, TPL_H * 4)))
            label = input(f'点击({cx},{cy}) 的牌面: ').strip().upper()
            if label:
                out = os.path.join(TEMPLATE_DIR, 'rank', f'{label}.png')
                cv2.imwrite(out, tpl)
                n_saved += 1
                print(f'  已保存 {out}')
    cv2.destroyAllWindows()
    print(f'共保存 {n_saved} 个模板。对局截图里每种 rank 至少切一次；'
          f'大小王和 2 建议多角度各切一次(同名覆盖)。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
