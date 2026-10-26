"""截屏与窗口定位。支持普通窗口和可能截黑的硬渲染窗口(PrintWindow 兜底)。"""
from __future__ import annotations

from typing import Optional, Tuple

import numpy as np

from .config import WINDOW_TITLES


def find_game_window() -> Tuple[int, int, int, int]:
    """找到游戏窗口，返回 (left, top, width, height)。找不到抛 RuntimeError。"""
    import win32con
    import win32gui

    def enum_handler(hwnd, results):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd)
        if not title:
            return
        for kw in WINDOW_TITLES:
            if kw in title:
                # 最小化的窗口恢复坐标无意义
                if win32gui.IsIconic(hwnd):
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                rect = win32gui.GetWindowRect(hwnd)
                results.append((hwnd, title, rect))
                return

    results: list = []
    win32gui.EnumWindows(enum_handler, results)
    if not results:
        raise RuntimeError(
            f'找不到游戏窗口。当前可见窗口标题: {_list_titles()}。'
            f'请检查 vision/config.py 的 WINDOW_TITLES。')
    hwnd, title, (l, t, r, b) = results[0]
    return l, t, r - l, b - t


def _list_titles() -> list:
    import win32gui
    titles = []
    win32gui.EnumWindows(
        lambda h, _: (win32gui.IsWindowVisible(h) and win32gui.GetWindowText(h)
                      and titles.append(win32gui.GetWindowText(h))) or True, None)
    return titles[:20]


def capture_window(window: Optional[Tuple[int, int, int, int]] = None) -> np.ndarray:
    """截取游戏窗口画面，返回 BGR ndarray。PrintWindow 兜底防截黑。"""
    import win32gui
    import win32ui
    import cv2

    if window is None:
        window = find_game_window()
    hwnd = _hwnd_from_rect(window)
    l, t, w, h = window

    # 方案1: PrintWindow (对硬件加速窗口更可靠)
    try:
        img = _print_window(hwnd, w, h)
        if img is not None and img.mean() > 2:  # 非全黑
            return img
    except Exception:
        pass
    # 方案2: mss 屏幕截取（窗口需在前台未遮挡）
    import mss
    with mss.mss() as sct:
        raw = sct.grab({'left': l, 'top': t, 'width': w, 'height': h})
        return np.asarray(raw)[:, :, :3][:, :, ::-1].copy()  # BGRA->BGR


def _hwnd_from_rect(rect) -> int:
    import win32gui
    found = [0]

    def cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowRect(hwnd) == \
                (rect[0], rect[1], rect[0] + rect[2], rect[1] + rect[3]):
            found[0] = hwnd
    win32gui.EnumWindows(cb, None)
    return found[0]


def _print_window(hwnd: int, w: int, h: int):
    import win32gui
    import win32ui
    import cv2

    try:
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        w, h = right - left, bottom - top
        hdc = win32gui.GetWindowDC(hwnd)
        mfcDC = win32ui.CreateDCFromHandle(hdc)
        saveDC = mfcDC.CreateCompatibleDC()
        bmp = win32ui.CreateBitmap()
        bmp.CreateCompatibleBitmap(mfcDC, w, h)
        saveDC.SelectObject(bmp)
        # PW_RENDERFULLCONTENT = 2 (Win8.1+ 可截 DirectComposition 内容)
        ctypes_result = _pw(hwnd, saveDC.GetSafeHdc(), w, h)
        info = bmp.GetInfo()
        data = bmp.GetBitmapBits(True)
        import numpy as np
        img = np.frombuffer(data, dtype=np.uint8).reshape(h, w, 4)
        win32gui.DeleteObject(bmp.GetHandle())
        saveDC.DeleteDC()
        mfcDC.DeleteDC()
        win32gui.ReleaseDC(hwnd, hdc)
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    except Exception:
        return None


def _pw(hwnd, hdc, w, h) -> bool:
    import ctypes
    user32 = ctypes.windll.user32
    return bool(user32.PrintWindow(hwnd, hdc, 2))
