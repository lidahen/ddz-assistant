"""置顶半透明建议悬浮窗 (tkinter)。显示: 我的手牌摘要 + 建议动作。"""
from __future__ import annotations

import threading
from typing import List, Optional

import tkinter as tk

from ..core.cards import cards_to_str


class SuggestWindow:
    """独立线程跑 tkinter 主循环，外部线程用 update() 安全投递。"""

    def __init__(self, offset=(320, 420)):
        self._q: Optional[tuple] = None
        self._lock = threading.Lock()
        self._offset = offset
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._ready.wait(5)

    def _run(self):
        self.root = tk.Tk()
        self.root.title('DDZ助手')
        self.root.attributes('-topmost', True)
        self.root.attributes('-alpha', 0.85)
        self.root.overrideredirect(False)  # 带边框方便拖动；要无边框改 True
        self.root.configure(bg='#1e1e2e')
        self.root.geometry(f'280x110+{self._offset[0]}+{self._offset[1]}')

        self.lbl_state = tk.Label(self.root, text='等待识别...', font=('Consolas', 10),
                                  fg='#9ca3af', bg='#1e1e2e', anchor='w')
        self.lbl_state.pack(fill='x', padx=8, pady=(6, 0))
        self.lbl_suggest = tk.Label(self.root, text='—', font=('Consolas', 20, 'bold'),
                                    fg='#4ade80', bg='#1e1e2e')
        self.lbl_suggest.pack(expand=True)
        self.lbl_detail = tk.Label(self.root, text='', font=('Consolas', 9),
                                   fg='#60a5fa', bg='#1e1e2e', anchor='w')
        self.lbl_detail.pack(fill='x', padx=8, pady=(0, 6))
        self.root.protocol('WM_DELETE_WINDOW', self.root.destroy)
        self._ready.set()
        self.root.mainloop()

    def update(self, state_text: str, suggest: str, detail: str = ''):
        with self._lock:
            self._q = (state_text, suggest, detail)
        if self._ready.is_set() and hasattr(self, 'root'):
            try:
                self.root.after(0, self._apply)
            except tk.TclError:
                pass  # 窗口已关

    def _apply(self):
        if self._q is None:
            return
        s, g, d = self._q
        self.lbl_state.config(text=s)
        self.lbl_suggest.config(text=g)
        self.lbl_detail.config(text=d)

    def close(self):
        try:
            self.root.after(0, self.root.destroy)
        except Exception:
            pass


def format_move(move: Optional[List[int]]) -> str:
    if move is None or len(move) == 0:
        return 'PASS (不要)'
    return f'{cards_to_str(move)}  ({len(move)}张)'
