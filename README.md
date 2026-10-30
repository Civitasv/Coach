# Coach · 孙尚香实时教练

Windows 桌面只读辅助，采用 **PySide6 双栏 UI**：左侧持续显示游戏截图与可信 HUD/商店牌，右侧为聊天式教练。截图在本机采集；**默认不会自动发送到云端**。

## 启动：项目自管理 .venv

安装 **Python 3.11+**，随后直接启动即可（无需提前手动安装 pip 依赖）：

- **Windows**：双击 `run.bat`（也可在 PowerShell 中运行 `.\\run.bat`）。
- **macOS / Linux**：运行 `./run.sh`。

启动器用系统 Python 的标准库在**仓库目录**创建 `.venv/`，只通过 `.venv` 的 Python 安装 `requirements.txt`，最后使用相同的 venv Python 启动 `coach.py`。**不会安装包到全局 Python。** 首次需要联网下载 PySide6、RapidOCR 和 ONNX Runtime，之后检测到依赖清单和 Python 版本没有变化且包仍在时直接复用。修改 requirements 或缺包会自动补装。

需要只准备环境、不打开窗口时：

```powershell
.\\run.bat --prepare
```

macOS/Linux 对应 `./run.sh --prepare`；手动运行可使用 `.venv/Scripts/python.exe coach.py`（Windows）或 `.venv/bin/python coach.py`（macOS/Linux）。可用 `COACH_PYTHON` 指定创建 venv 所用的宿主 Python。

如果 Python 版本更新导致已有 venv 损坏，删除项目下的 `.venv/` 再运行启动器。**项目自管理不等于打包 Python 运行时或完全离线安装**；普通本地监看不需要 API Key。

## 每局操作

1. 点击「框选游戏区域」选择游戏画面。
2. 点击「开始本局」启动本地监看；画面更新目标每 0.5 秒，OCR 最短每 1.5 秒（实际与 CPU 有关）。
3. 左侧可看到实时画面、血量、能量、回合、武器和商店 5 个槽位的可信图标结果；未知图标只显示“未知”，不会使用 OCR 文本猜测英雄。
4. 右侧 Chat 可随时提问。Coach 在缺信息时出现非模态问题卡片，可直接回答或跳过；聊天输入与问题回答是不同通道。
5. 在「设置与校准」中选择 DeepSeek、Ollama 或 OpenAI，输入 API Key；勾选「自动建议」前须授权发送 **OCR 文字**。手动「深度看图」会额外单独请求截图授权。Ollama 本地请求无需云端上传。
6. 点击「暂停」可停止观察而保留本局数据；点击「结束本局」停止全部观察并把不含截图/密钥的摘要存入 `sessions/`。下局点击开始重新清空。

## 校准与识别

展开「设置与校准」，选择 ROI 并框选：health, energy, round, weapon, shop, shop_slot_1…5, enemy_board, enemy_icon, pool。ROI 会保存至 `config/calibration.json`（可随时删除）。对于图标，需要玩家人工确认英雄名称并使用「保存英雄模板」建立本地模板；没有模板、相似度不足或存在冲突时不会编造结果。

公共牌库库存仍只能由用户指定的已确认面板深度扫描或人工确认写入，并非后台精确同步。未知/过期字段必须重新观察或由用户确认。

## 边界

- 仅抓取选定的屏幕区域，不读游戏内存、不抓包、不自动操作游戏；请自行确认游戏平台的第三方辅助规则。
- 本地截图以“最新帧”存在内存，默认不保存；聊天记录仅保留在当前窗口，不写入 `sessions/` 摘要；OCR 文本和手动输入的事实会进入本机摘要。
- 截图可能包含昵称等信息，手动上传前会再次确认。不要上传敏感信息，不要把 `.env`、`config/`、`sessions/` 提交到公开仓库。
- UI 测试使用 Qt offscreen 驱动，不代表已经经过真实 Windows 客户端实测或量化 OCR 准确率。

## 开发

```bash
python scripts/verify_ai_workflow.py
python -m compileall -q coach.py desktop_ui.py qt_widgets.py observer.py engine.py local_ocr.py session.py advice.py providers.py observation.py icon_matcher.py scripts tests
python -m unittest discover -s tests -v
```

分层：`coach.py` 入口，`desktop_ui.py` Qt 控制器，`qt_widgets.py` 纯展示部件，`observer.py` 带队列上限的本地采集/OCR；原有 `session.py`、`engine.py`、`observation.py`、`icon_matcher.py`、`providers.py` 原样负责可信局面状态和推理。