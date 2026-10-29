# Coach v0.3 — 王者万象棋孙尚香本地实时教练

只读 Windows 屏幕辅助。**本地 RapidOCR 高频识别 + 低频 AI 文字决策 + 可选按次看图**。不读取游戏进程、不抓包、不自动操作游戏，也不保证推荐正确。

## 快速启动

1. Windows 安装 Python 3.10–3.13，运行 `run.bat`，首次安装 `rapidocr` 和 `onnxruntime` 等依赖可能需要一些时间（首次模型初始化也有开销）。
2. 打开游戏、选择显示器，点击「框选监看区域」。避免框入聊天、账号和其他私人内容。
3. **每局点击「开始本局」**。默认每 0.5 秒采样图像，只在画面变化时 OCR，最短间隔 1.5 秒。OCR 运行在本地，不需要 API Key；CPU 忙时会自动串行处理，不能承诺严格每 1.5 秒出结果。
4. 程序在观察到文字并且缺失关键事实后，会在界面提出非模态问题：血量、能量、武器或主要对手阵容。你可以回答或「稍后再问」。不会抢占游戏键盘焦点。
5. 如果需要策略推理，选择模型、填写 API Key，勾选「OCR 有变化时自动请求 AI 文字建议」。首次会提示确认：**发送 OCR 文字和本局摘要，但不发送截图**。只在文字变化、冷却完成且未达调用上限时请求。Ollama 同样支持文字模式，但不上传云端。
6. 如果遇到 OCR 无法看懂的头像、阵容、图标或牌库面板，可主动点击「AI 深度看图一次」，单独授权发送截图（Ollama 本地无需云端授权）。扫描公共牌库时切换到「牌库扫描」，看对手时切换到「对手侦察」。
7. **每局点击「结束本局」**，立即停用观察并使旧的异步结果失效。记录以 JSON 保存到本地 `sessions/`（不含截图/API Key）。下一局点开始重新清空牌库、对手、计数和临时事实。

## 技术说明

- `local_ocr.py`：RapidOCR 3.x + ONNX Runtime CPU，中文/英文/数字的本地文字检测、行置信度过滤。只在画面变化时触发；不启用云端回传。
- `session.py`：显式 `idle → active → ended` 生命周期，血量/能量/回合/武器字段均使用保守的**带标签且高置信度** OCR 解析，人工补录的状态也有有效期。缺少信息时每次只问一个，至少 180 秒不重复同一问题。
- `advice.py`：有限的即时规则（例如低血量提醒），不会仅凭 OCR 文字杜撰英雄阵容或胜率。AI 文字决策的提示词明确区分已确认事实和原始 OCR；拒绝盲猜。
- `providers.py`：本地 Ollama / DeepSeek / OpenAI 的图像或纯文字调用。**默认不进行任何云端调用**；文字自动分析与看图分别授权。单局上限默认 100 次，随时暂停或结束。
- `engine.py`：既有牌库快照、对手侦察状态，只有确认的面板视觉分析才能更新精确数量；OCR 目前只提供文字线索，不会把“看到了一个数字”直接当作公共牌库精确数量。过期快照不是真实剩余牌库。

## 当前局限与后续校准

- 本地 OCR **不等于完整画面理解**：无法可靠识别没有文字的英雄头像、装备、站位和点击区域。后续需要真实游戏截图，建立 ROI（HUD/商店/牌库）、模板匹配或小型本地图标分类器。
- 0.5 秒是**截图采样目标**，不是每 0.5 秒完成一次 OCR；频率取决于 CPU、屏幕范围、帧变化及 OCR 推理耗时。建议缩小框选范围，避免背景动画误触发。
- 仅带明显字段标签的文字会转换为事实。部分游戏界面可能没有标签，因此会主动问你，而不是编造血量/能量。OCR 文字本身可能误读，必须人工核对。
- 为避免抢占输入，提问只显示在 Coach 小窗中，不弹出模态对话框；可能需要将游戏设为窗口化，以看到置顶提示。
- 默认保存的摘要里有你手动填写的对手文字及牌库快照；请注意本地文件隐私。关闭程序时不会上传摘要。不要上传 API Key 或 `sessions/` 目录。
- 尚未在实际《王者万象棋》客户端上校准 OCR 识别率、OCR 耗时或 DeepSeek 的真实账号端到端效果。实际延迟和成本需要对局实测。你需要自行确认游戏对外部实时辅助工具的规则。

## 测试

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

## 模块

```text
coach.py       GUI / 采样循环 / 显式开始结束
local_ocr.py   RapidOCR 适配，CPU OCR
session.py     局内事实及主动提问（零云端依赖）
advice.py      本地提示与文本 AI Prompt
engine.py      牌库、对手历史快照
providers.py   可选图像/文本模型接口
tests/         不依赖实际 OCR 模型的单元测试
```

## AI-native development workflow

For AI agents and human contributors, start with [`AGENTS.md`](AGENTS.md), then [`docs/architecture/overview.md`](docs/architecture/overview.md) and [`docs/process/development.md`](docs/process/development.md). Features use versioned [Specs](docs/specs/) and [Plans](docs/plans/), with evidence-backed reviews and the PR template. GitHub Actions validates both Windows and Linux; local commands are in the development guide. Changes to game-state recognition should begin with [`Spec 002`](docs/specs/002-structured-game-observation.md) (draft, not implemented).