"""标定步骤 1: 抓一帧游戏窗口图存到 calib/，供确定坐标和切模板用。

用法: python calib/capture.py
"""
import os
import sys

import cv2

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from ddz.vision.capture import capture_window, find_game_window

out = os.path.join(os.path.dirname(__file__), 'frame.png')
rect = find_game_window()
print(f'游戏窗口: left={rect[0]} top={rect[1]} w={rect[2]} h={rect[3]}')
img = capture_window(rect)
cv2.imwrite(out, img)
print(f'已保存: {out}')
print('下一步: 用画图打开它，鼠标悬停读出各区域左上/右下角像素坐标，'
      '按 calib/README.md 填写 regions。')
