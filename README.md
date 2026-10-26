# 斗地主实时助手（欢乐斗地主 H5/小程序版）

截屏识别牌面 → 状态机 → 决策引擎（DouZero 预训练 / 规则 AI 降级）→ 置顶悬浮窗出牌建议。

## 环境

```
uv venv --python 3.12 .venv
uv pip install --python .venv/Scripts/python.exe -i https://mirrors.aliyun.com/pypi/simple/ \
    numpy opencv-python pillow mss pygetwindow pywin32
.venv\Scripts\activate
```

Python 必须 3.12/3.11（3.14 尚无 torch 支持；DouZero 启用时再装 `douzero torch`）。

## 快速开始

```bash
python -m ddz.main --dry-run     # 无游戏窗口验证链路（悬浮窗弹 3 秒）
python -m ddz.main               # 正式运行（游戏需在前台）
```

## 标定（首次使用必做，约 10 分钟）

游戏里进入一局、拿到手牌后：

```bash
python calib/capture.py          # 1. 抓一帧 -> calib/frame.png
python calib/select_regions.py   # 2. 框选8个区域，生成坐标配置
python calib/make_templates.py   # 3. 手牌区点击切15种rank模板
```

标定产物：`ddz/vision/calibrated.py`（坐标）、`models/templates/rank/*.png`（模板）。

**需要你回头补的参数全部集中在这两处 + `ddz/vision/config.py` 的 `WINDOW_TITLES`。**

各区域含义（以 1080p 默认值为初稿，拖框微调即可）：

| 区域 | 内容 |
|---|---|
| my_hand | 底部我的手牌一排 |
| my_play | 我出的牌（手牌上方中央） |
| left_play / right_play | 上家(左)/下家(右)出的牌 |
| left_count / right_count | 两家剩牌数（备用） |
| pass_button | "不出"按钮（备用） |

## 启用 DouZero（可选，当前自动降级规则 AI）

1. 下载预训练权重（[DouZero README](https://github.com/kwai/DouZero) 的 Google Drive/百度网盘），
   把 `landlord.ckpt / landlord_up.ckpt / landlord_down.ckpt` 放到 `models/douzero/`
2. `pip install douzero torch`（CPU 版 torch 即可，推理毫秒级）
3. `ddz/douzero_adapter.py` 中 TODO 处补 obs 编码与采样推理

## 结构

```
ddz/
  core/cards.py        牌型解析/比较/走法生成（46 项单测）
  core/rule_ai.py      规则 AI: 拆牌最少手数 + 跟牌代价评估
  core/game.py         完整对局引擎（自对弈测试用）
  vision/capture.py    窗口定位 + 截屏（PrintWindow 兜底防截黑）
  vision/recognizer.py 模板匹配识别（多尺度 + x坐标聚类）
  state.py             帧间差异状态机
  douzero_adapter.py   DouZero 适配层（缺失自动降级）
  ui/overlay.py        置顶悬浮窗
  main.py              主循环
tests/                 单测 + 200局自对弈
calib/                 三步标定工具
```

## 已知边界

- 小程序窗口若 PrintWindow 仍截黑，把窗口拖出屏幕外再截或用窗口置顶+前台截屏
- 飞机翅膀规则按"从宽"实现（各平台规则略有差异）
- 剩牌数 OCR、身份（谁是地主）识别为预留位，标定时如需要再补 digit 模板
