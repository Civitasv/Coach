"""Coach v0.3: local OCR observer with per-game sessions and optional model reasoning.

No game-process access, network interception, automation, or automatic screenshot uploads.
"""
import io
import json
import os
import queue
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk, simpledialog

import mss
from PIL import Image, ImageChops, ImageStat, ImageTk

from advice import offline_hint, text_prompt
from engine import parse, prompt, short
from local_ocr import LocalOCR, trusted_text
from observation import Calibration, ROI, ROI_NAMES, scoped_lines
from icon_matcher import IconMatcher
from providers import analyze, analyze_text
from session import GameSession, LABELS

PROVIDERS = {'DeepSeek 云端': ('deepseek-flash', 'DEEPSEEK_API_KEY'),
             'Ollama 本地': ('gemma3:4b', ''),
             'OpenAI 云端': ('gpt-4.1-mini', 'OPENAI_API_KEY')}
MODES = ('常规建议', '牌库扫描', '对手侦察')


def grab(rect):
    with mss.mss() as screen:
        shot = screen.grab(rect)
    return Image.frombytes('RGB', shot.size, shot.rgb)


def jpeg(image):
    image = image.copy().convert('RGB')
    image.thumbnail((1920, 1600))
    stream = io.BytesIO()
    image.save(stream, 'JPEG', quality=85)
    return stream.getvalue()


def changed(image, old):
    thumb = image.convert('L').resize((128, 72))
    if old is None:
        return True, thumb
    diff = ImageStat.Stat(ImageChops.difference(thumb, old)).mean[0]
    return diff >= 2.3, thumb


class Picker(tk.Toplevel):
    def __init__(self, master, monitor, callback, min_size=(100, 70)):
        super().__init__(master)
        self.title('拖拽选择游戏区域 · Esc 取消')
        self.callback = callback
        self.monitor = monitor
        self.min_size = min_size
        shot = grab(monitor)
        self.factor = min(1, 1250 / shot.width, 720 / shot.height)
        w, h = round(shot.width * self.factor), round(shot.height * self.factor)
        self.photo = ImageTk.PhotoImage(shot.resize((w, h)))
        self.canvas = tk.Canvas(self, width=w, height=h, cursor='crosshair')
        self.canvas.pack()
        self.canvas.create_image(0, 0, image=self.photo, anchor='nw')
        self.anchor = None
        self.rectangle = None
        self.canvas.bind('<Button-1>', self.down)
        self.canvas.bind('<B1-Motion>', self.move)
        self.canvas.bind('<ButtonRelease-1>', self.up)
        self.bind('<Escape>', lambda _: self.destroy())
        self.grab_set()

    def down(self, e):
        self.anchor = (e.x, e.y)
        self.rectangle = self.canvas.create_rectangle(e.x, e.y, e.x, e.y, outline='#00ddff', width=3)

    def move(self, e):
        if self.rectangle is not None:
            self.canvas.coords(self.rectangle, *self.anchor, e.x, e.y)

    def up(self, e):
        if not self.anchor:
            return
        ax, ay = self.anchor
        x1, x2 = sorted((max(0, ax), max(0, e.x)))
        y1, y2 = sorted((max(0, ay), max(0, e.y)))
        if x2-x1 < self.min_size[0] or y2-y1 < self.min_size[1]:
            messagebox.showwarning('区域过小', '请框选更大的游戏区域', parent=self)
            return
        self.callback({'left': self.monitor['left'] + round(x1/self.factor),
                       'top': self.monitor['top'] + round(y1/self.factor),
                       'width': round((x2-x1)/self.factor),
                       'height': round((y2-y1)/self.factor)})
        self.destroy()


class Coach:
    def __init__(self, root):
        self.root = root
        root.title('Coach · 孙尚香本地实时教练 v0.4')
        root.geometry('610x825')
        root.attributes('-topmost', True)
        self.session = GameSession()
        self.events = queue.Queue()
        self.run_id = 0
        self.monitoring = False
        self.stop_event = None
        self.ai_busy = False
        self.last_text_sent = ''
        self.last_text_at = 0.0
        self.cloud_text_allowed = False
        self.rect = None
        self.config_dir = Path(__file__).resolve().parent / 'config'
        self.calibration_file = self.config_dir / 'calibration.json'
        try:
            self.calibration = Calibration.load(self.calibration_file) if self.calibration_file.exists() else Calibration()
        except (OSError, ValueError, KeyError, TypeError) as exc:
            self.calibration = Calibration()
        self.roi_name = tk.StringVar(value='health')
        self.monitors = []
        self.last_photo = None
        self.question_field = ''
        self.provider = tk.StringVar(value='DeepSeek 云端')
        self.model = tk.StringVar(value='deepseek-flash')
        self.key = tk.StringVar()
        self.mode = tk.StringVar(value=MODES[0])
        self.sample_interval = tk.StringVar(value='0.5')
        self.ocr_interval = tk.StringVar(value='1.5')
        self.text_interval = tk.StringVar(value='12')
        self.max_calls = tk.StringVar(value='100')
        self.auto_text = tk.BooleanVar(value=False)
        self.notes = tk.StringVar(value='目标：香香稳前三，争取登顶。')
        self.status = tk.StringVar(value='选择区域后点击「开始本局」，本地 OCR 无需 API Key。')
        self.build()
        self.provider.trace_add('write', self.provider_changed)
        self.root.after(160, self.drain)
        self.root.protocol('WM_DELETE_WINDOW', self.close)

    def build(self):
        f = ttk.Frame(self.root, padding=12)
        f.pack(fill='both', expand=True)
        ttk.Label(f, text='Coach / 王者万象棋 · 孙尚香',
                  font=('Microsoft YaHei UI', 15, 'bold')).pack(anchor='w', pady=(0, 8))
        self.monitor = ttk.Combobox(f, state='readonly')
        self.monitor.pack(fill='x')
        self.refresh_monitors()
        row = ttk.Frame(f); row.pack(fill='x', pady=5)
        ttk.Button(row, text='框选监看区域', command=self.pick).pack(side='left')
        ttk.Button(row, text='刷新显示器', command=self.refresh_monitors).pack(side='left', padx=6)
        self.region_label = ttk.Label(row, text='未框选')
        self.region_label.pack(side='left', padx=5)
        roi_row = ttk.Frame(f); roi_row.pack(fill='x', pady=3)
        ttk.Label(roi_row, text='校准区域').pack(side='left')
        ttk.Combobox(roi_row, textvariable=self.roi_name, values=sorted(ROI_NAMES),
                     state='readonly', width=16).pack(side='left', padx=4)
        ttk.Button(roi_row, text='框选并保存 ROI', command=self.pick_roi).pack(side='left')
        ttk.Button(roi_row, text='清除该 ROI', command=self.remove_roi).pack(side='left', padx=3)
        ttk.Button(roi_row, text='保存图标样本', command=self.save_icon_template).pack(side='left')
        self.roi_status = ttk.Label(f, text=self.roi_description(), wraplength=550)
        self.roi_status.pack(anchor='w')

        box = ttk.LabelFrame(f, text='对局控制（每局必须手动开始、结束）', padding=7)
        box.pack(fill='x', pady=6)
        row = ttk.Frame(box); row.pack(fill='x')
        self.start_btn = ttk.Button(row, text='开始本局', command=self.start_game)
        self.start_btn.pack(side='left')
        self.pause_btn = ttk.Button(row, text='暂停观察', command=self.toggle_observer, state='disabled')
        self.pause_btn.pack(side='left', padx=6)
        self.end_btn = ttk.Button(row, text='结束本局', command=self.end_game, state='disabled')
        self.end_btn.pack(side='left')
        self.phase_label = ttk.Label(box, text='状态：未开始')
        self.phase_label.pack(anchor='w', pady=3)

        row = ttk.Frame(f); row.pack(fill='x', pady=4)
        ttk.Label(row, text='采样(秒)').pack(side='left')
        ttk.Entry(row, textvariable=self.sample_interval, width=5).pack(side='left', padx=4)
        ttk.Label(row, text='OCR最短间隔(秒)').pack(side='left')
        ttk.Entry(row, textvariable=self.ocr_interval, width=5).pack(side='left', padx=4)
        ttk.Label(row, text='AI文字间隔(秒)').pack(side='left')
        ttk.Entry(row, textvariable=self.text_interval, width=5).pack(side='left', padx=4)

        row = ttk.Frame(f); row.pack(fill='x', pady=5)
        ttk.Label(row, text='AI 提供商').pack(side='left')
        ttk.Combobox(row, textvariable=self.provider, values=list(PROVIDERS),
                     state='readonly', width=14).pack(side='left', padx=5)
        ttk.Entry(row, textvariable=self.model, width=19).pack(side='left', expand=True, fill='x')
        ttk.Label(f, text='云端 API Key（仅内存；无 Key 也能本地监看）').pack(anchor='w')
        ttk.Entry(f, textvariable=self.key, show='●').pack(fill='x', pady=(2, 5))
        row = ttk.Frame(f); row.pack(fill='x')
        ttk.Checkbutton(row, variable=self.auto_text, command=self.on_auto_text,
                        text='OCR 有变化时自动请求 AI 文字建议（需单独授权）').pack(side='left')
        ttk.Label(row, text='单局模型上限').pack(side='left')
        ttk.Entry(row, textvariable=self.max_calls, width=5).pack(side='left', padx=3)
        ttk.Entry(f, textvariable=self.notes).pack(fill='x', pady=6)

        row = ttk.Frame(f); row.pack(fill='x')
        ttk.Combobox(row, textvariable=self.mode, values=MODES,
                     state='readonly', width=14).pack(side='left')
        ttk.Button(row, text='AI 深度看图一次（可选）', command=self.vision_once).pack(side='left', padx=6)
        ttk.Label(row, text='OCR 不会自动上传截图').pack(side='left')
        ttk.Label(f, textvariable=self.status, wraplength=560, foreground='#006699').pack(anchor='w', pady=5)

        self.question_frame = ttk.LabelFrame(f, text='教练需要你补充的信息（不抢占游戏焦点）', padding=8)
        self.question_label = ttk.Label(self.question_frame, wraplength=540)
        self.question_label.pack(anchor='w')
        row = ttk.Frame(self.question_frame); row.pack(fill='x', pady=5)
        self.question_input = ttk.Entry(row)
        self.question_input.pack(side='left', fill='x', expand=True)
        ttk.Button(row, text='确认', command=self.answer_question).pack(side='left', padx=5)
        ttk.Button(row, text='稍后再问', command=self.skip_question).pack(side='left')

        self.preview = ttk.Label(f, text='尚无监看画面')
        self.preview.pack(fill='x', pady=3)
        ttk.Label(f, text='本地状态 / 建议').pack(anchor='w')
        self.output = tk.Text(f, wrap='word', height=11, font=('Microsoft YaHei UI', 10))
        self.output.pack(fill='both', expand=True)
        self.show_output('本地 OCR 持续读取中文数字、回合和可见文字；复杂英雄头像、站位、武器强化仍需视觉模型或人工确认。')

    def show_output(self, message):
        self.output.delete('1.0', 'end')
        self.output.insert('end', message[:6000])

    def refresh_monitors(self):
        try:
            with mss.mss() as s:
                self.monitors = [dict(m) for m in s.monitors[1:]]
            self.monitor['values'] = [f'显示器 {i+1}: {m["width"]}×{m["height"]}'
                                      for i, m in enumerate(self.monitors)]
            if self.monitors:
                self.monitor.current(0)
        except Exception as exc:
            self.status.set('显示器获取失败：' + str(exc)[:140])

    def pick(self):
        if self.monitoring:
            self.pause_observer()
        if not self.monitors:
            return
        Picker(self.root, self.monitors[max(0, self.monitor.current())], self.set_region)

    def set_region(self, box):
        self.rect = box
        self.region_label.config(text=f'{box["width"]}×{box["height"]}')
        self.status.set('区域已更新；观察暂停时可点击继续')

    def roi_description(self):
        return '已校准：' + (', '.join(sorted(self.calibration.regions)) or '无；未校准字段使用保守全屏 OCR')

    def pick_roi(self):
        if not self.rect:
            messagebox.showwarning('先选游戏区域', '先框选游戏窗口，再校准内部区域')
            return
        if self.monitoring:
            self.pause_observer()
        name = self.roi_name.get()
        Picker(self.root, self.rect, lambda selection: self.set_roi(name, selection), min_size=(10, 10))

    def set_roi(self, name, selection):
        if name not in ROI_NAMES or not self.rect:
            return
        game = self.rect
        try:
            roi = ROI((selection['left'] - game['left']) / game['width'],
                      (selection['top'] - game['top']) / game['height'],
                      selection['width'] / game['width'], selection['height'] / game['height'])
            self.calibration.regions[name] = roi
            self.calibration.save(self.calibration_file)
        except (OSError, ValueError) as exc:
            self.status.set('ROI 保存失败：' + str(exc)[:150])
            return
        self.roi_status.config(text=self.roi_description())
        self.status.set('本地 ROI 已保存；恢复观察后生效')

    def remove_roi(self):
        if self.monitoring:
            self.pause_observer()
        self.calibration.regions.pop(self.roi_name.get(), None)
        self.calibration.save(self.calibration_file)
        self.roi_status.config(text=self.roi_description())
        self.status.set('该 ROI 已清除')

    def save_icon_template(self):
        name = self.roi_name.get()
        if not self.rect or (not name.startswith('shop_slot_') and name != 'enemy_icon'):
            messagebox.showwarning('需要图标区域', '先校准 shop_slot_1…5 或 enemy_icon')
            return
        roi = self.calibration.regions.get(name)
        if not roi:
            messagebox.showwarning('未校准', '先框选并保存对应图标区域')
            return
        hero = simpledialog.askstring('保存本地图标样本', '请输入可确认的英雄名称（保存为本机 PNG 模板）', parent=self.root)
        if not hero:
            return
        import re
        if not re.fullmatch(r'[\w\u4e00-\u9fff-]{1,30}', hero):
            messagebox.showwarning('名称无效', '仅允许中文、字母、数字、下划线和短横线')
            return
        output = self.config_dir / 'icon_templates' / f'{hero}.png'
        if output.exists() and not messagebox.askyesno('覆盖模板', f'{hero} 的本地模板已存在，覆盖？'):
            return
        if self.monitoring:
            self.pause_observer()
        try:
            img = grab(self.rect)
            output.parent.mkdir(parents=True, exist_ok=True)
            img.crop(roi.pixels(*img.size)).save(output)
            self.status.set(f'已在本机保存图标模板：{hero}；恢复观察后生效')
        except (OSError, ValueError) as exc:
            self.status.set('图标模板保存失败：' + str(exc)[:150])

    def provider_changed(self, *_):
        self.cloud_text_allowed = False
        self.auto_text.set(False)
        self.model.set(PROVIDERS[self.provider.get()][0])
        self.key.set('')
        self.status.set('已切换模型；云端发送须重新授权，本地 OCR 不受影响')

    def provider_key(self):
        return self.key.get().strip() or os.environ.get(PROVIDERS[self.provider.get()][1], '').strip()

    def max_requests(self):
        try:
            return max(1, min(2000, int(self.max_calls.get())))
        except ValueError:
            return 100

    @staticmethod
    def number(value, default, lo, hi):
        try:
            return max(lo, min(hi, float(value)))
        except ValueError:
            return default

    def authorize_text(self):
        provider = self.provider.get()
        if provider != 'Ollama 本地':
            if not self.provider_key():
                messagebox.showwarning('未配置 API Key', '先配置密钥；本地 OCR 仍可正常工作')
                return False
            if not messagebox.askyesno('授权云端文字分析',
                     f'本局将自动向 {provider} 发送当前 OCR 文字与对局摘要（不发送截图）。继续？'):
                return False
        self.cloud_text_allowed = True
        return True

    def on_auto_text(self):
        if not self.auto_text.get():
            self.cloud_text_allowed = False
            return
        if self.session.phase == 'active' and not self.authorize_text():
            self.auto_text.set(False)

    def start_game(self):
        if not self.rect:
            messagebox.showwarning('缺少监看区域', '先框选游戏窗口，确保不含个人信息')
            return
        if self.session.phase == 'active':
            return
        self.stop_worker()
        self.session.start()
        self.last_text_sent = ''
        self.last_text_at = 0
        self.ai_busy = False
        self.question_field = ''
        self.question_frame.pack_forget()
        self.start_btn.config(state='disabled')
        self.end_btn.config(state='normal')
        self.pause_btn.config(state='normal')
        if self.auto_text.get() and not self.authorize_text():
            self.auto_text.set(False)
        self.phase_label.config(text='状态：本局进行中（本地 OCR）')
        self.show_output('已开始新对局。已清空上局牌库、对手信息与请求计数；等待 OCR 首次读数。')
        self.start_observer()

    def stop_worker(self):
        self.run_id += 1
        self.monitoring = False
        self.ai_busy = False  # Late model events are ignored by the run-id guard.
        if self.stop_event is not None:
            self.stop_event.set()
        self.stop_event = None

    def start_observer(self):
        if self.session.phase != 'active' or not self.rect or self.monitoring:
            return
        self.run_id += 1
        current_id = self.run_id
        event = threading.Event()
        self.stop_event = event
        self.monitoring = True
        self.pause_btn.config(text='暂停观察')
        rect = self.rect.copy()
        sample = self.number(self.sample_interval.get(), 0.5, 0.4, 5.0)
        ocr_gap = self.number(self.ocr_interval.get(), 1.5, 0.6, 30.0)
        calibration = Calibration(dict(self.calibration.regions))
        threading.Thread(target=self.observe_worker,
                         args=(current_id, event, rect, sample, ocr_gap, calibration), daemon=True).start()
        self.status.set('本地 OCR 观察中；采样不产生 API 费用')

    def observe_worker(self, run_id, stopped, rect, sample, ocr_gap, calibration):
        try:
            engine = LocalOCR()
            matcher = IconMatcher.from_directory(self.config_dir / 'icon_templates')
            thumb = None
            next_ocr = 0.0
            refresh_at = 0.0
            while not stopped.is_set():
                start = time.monotonic()
                image = grab(rect)
                different, latest = changed(image, thumb)
                thumb = latest
                self.events.put((run_id, 'capture', None))
                if start >= next_ocr and (different or start >= refresh_at):
                    # CPU OCR is synchronous within this single worker: there can
                    # never be overlapping OCR calls for this session worker.
                    lines = engine.recognize(image)
                    scoped = scoped_lines(lines, calibration, *image.size) if calibration.regions else None
                    if scoped is not None:
                        for key in ('health', 'energy', 'round', 'weapon'):
                            scoped.setdefault(key, lines)
                    icon_results = {}
                    for name, roi in calibration.regions.items():
                        if name.startswith('shop_slot_') or name == 'enemy_icon':
                            try:
                                icon_results[name] = matcher.classify(image.crop(roi.pixels(*image.size)))
                            except ValueError:
                                continue
                    self.events.put((run_id, 'ocr', (image, lines, scoped, icon_results)))
                    next_ocr = time.monotonic() + ocr_gap
                    refresh_at = time.monotonic() + 8.0
                stopped.wait(max(0, sample - (time.monotonic() - start)))
        except Exception as exc:
            self.events.put((run_id, 'observer_error', str(exc)))

    def pause_observer(self):
        self.stop_worker()
        self.pause_btn.config(text='继续观察')
        self.status.set('已暂停本地观察，本局信息仍保留')

    def toggle_observer(self):
        if self.session.phase != 'active':
            return
        if self.monitoring:
            self.pause_observer()
        else:
            self.start_observer()

    def end_game(self):
        if not self.session.end():
            return
        self.stop_worker()
        self.auto_text.set(False)
        self.cloud_text_allowed = False
        self.question_field = ''
        self.question_frame.pack_forget()
        self.start_btn.config(state='normal')
        self.end_btn.config(state='disabled')
        self.pause_btn.config(state='disabled', text='暂停观察')
        self.phase_label.config(text='状态：本局已结束')
        try:
            folder = Path(__file__).resolve().parent / 'sessions'
            folder.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            output = folder / f'game_{stamp}.json'
            output.write_text(json.dumps(self.session.summary(), ensure_ascii=False, indent=2), encoding='utf-8')
            self.status.set(f'本局已结束，保存摘要：{output.name}（无截图、无 API Key）')
        except OSError as exc:
            self.status.set('本局已结束，但保存摘要失败：' + str(exc)[:140])

    def show_question(self, field, question):
        self.question_field = field
        self.question_label.config(text=question)
        self.question_input.delete(0, 'end')
        self.question_frame.pack(fill='x', pady=5, before=self.preview)
        # Deliberately do not grab keyboard focus during gameplay.

    def answer_question(self):
        try:
            self.session.reply(self.question_field, self.question_input.get())
        except ValueError as exc:
            messagebox.showwarning('输入无效', str(exc))
            return
        self.question_field = ''
        self.question_frame.pack_forget()
        self.status.set('已纳入本局状态；不会当作游戏画面直接识别的库存数据')
        self.last_text_sent = ''  # Newly answered facts can trigger a fresh text decision.
        self.render_hint()
        self.maybe_text_model()

    def skip_question(self):
        self.session.skip_question()
        self.question_field = ''
        self.question_frame.pack_forget()
        self.status.set('本次问题已跳过，稍后视需要再问')

    def render_hint(self, lines=None):
        if self.session.phase != 'active':
            return
        facts = '; '.join(f'{LABELS[k]}：{self.session.current(k) or "未知"}' for k in LABELS)
        icon_text = ', '.join(f'{key}={entry["name"]}' for key, entry in self.session.fresh_icons().items()) or '未知'
        text = (f'本局采样 {self.session.counts["captures"]} 次 | OCR {self.session.counts["ocr"]} 次'
                f' | AI {self.session.counts["model"]}/{self.max_requests()} 次\n'
                f'当前信息：{facts}\n\n'
                f'本地提示：{offline_hint(self.session)}\n\n'
                f'AI 最近建议：{self.session.last_decision or "未请求（本地 OCR 模式）"}\n\n'
                f'本地图标：{icon_text}\n'
                f'OCR 可见文字（不保证准确）：\n{self.session.latest_ocr[:1800] or "暂无可识别文字"}')
        self.show_output(text)

    def maybe_text_model(self):
        if not (self.auto_text.get() and self.cloud_text_allowed and not self.ai_busy):
            return
        if self.session.phase != 'active' or self.session.counts['model'] >= self.max_requests():
            return
        latest = self.session.latest_ocr
        fingerprint = (latest + '\n' + str(sorted((k, v['name']) for k,v in self.session.fresh_icons().items()))
                       + '\n' + str(sorted((k, self.session.current(k)) for k in LABELS)))
        if len(latest.strip()) < 5 and not self.session.fresh_icons():
            return
        if fingerprint == self.last_text_sent:
            return
        now = time.monotonic()
        if now - self.last_text_at < self.number(self.text_interval.get(), 12, 10, 120):
            return
        self.last_text_at = now
        self.last_text_sent = fingerprint
        self.launch_model('text')

    def vision_once(self):
        if self.session.phase != 'active':
            messagebox.showwarning('未开始对局', '先点击「开始本局」')
            return
        if self.ai_busy or self.session.counts['model'] >= self.max_requests():
            self.status.set('AI 正忙或已达单局请求上限')
            return
        provider = self.provider.get()
        if provider != 'Ollama 本地':
            if not self.provider_key():
                messagebox.showwarning('缺少 API Key', '请先配置密钥')
                return
            if not messagebox.askyesno('授权上传截图',
                    f'本次将把选定区域截图发送给 {provider}，可能包含游戏中的个人信息。确认？'):
                return
        self.launch_model('vision')

    def launch_model(self, kind):
        if self.ai_busy or self.session.phase != 'active':
            return
        if self.session.counts['model'] >= self.max_requests():
            return
        self.ai_busy = True
        self.session.counts['model'] += 1  # Reserve budget before launching the request.
        current_id = self.run_id
        provider = self.provider.get()
        model = self.model.get().strip()
        key = self.provider_key()
        mode = self.mode.get()
        request_prompt = (text_prompt(self.session, self.notes.get()) if kind == 'text'
                          else prompt(mode, self.session.match,
                                      self.notes.get() + '\n' + self.session.context()[:1500]))
        rect = self.rect.copy()
        def worker():
            try:
                if kind == 'text':
                    result = analyze_text(provider, request_prompt, model, key)
                else:
                    result = analyze(provider, jpeg(grab(rect)), request_prompt, model, key)
                self.events.put((current_id, 'model', (kind, mode, parse(result))))
            except Exception as exc:
                self.events.put((current_id, 'model_error', str(exc)))
        threading.Thread(target=worker, daemon=True).start()
        self.status.set('AI 正在生成' + ('文字建议…' if kind == 'text' else '截图分析…'))

    def drain(self):
        try:
            while True:
                run_id, kind, data = self.events.get_nowait()
                if run_id != self.run_id or self.session.phase != 'active':
                    continue
                if kind == 'capture':
                    self.session.counts['captures'] += 1
                    continue
                if kind == 'observer_error':
                    self.pause_observer()
                    self.status.set('本地观察失败：' + data[:230])
                    continue
                if kind == 'ocr':
                    image, lines, scoped, icon_results = data
                    self.session.observe(lines, scoped=scoped)
                    self.session.record_icons(icon_results)
                    if self.session.pending and self.session.current(self.session.pending) is not None:
                        self.session.skip_question()
                        self.question_field = ''
                        self.question_frame.pack_forget()
                    question = self.session.clarify()
                    if question:
                        self.show_question(*question)
                    image.thumbnail((540, 105))
                    self.last_photo = ImageTk.PhotoImage(image)
                    self.preview.config(image=self.last_photo, text='')
                    self.render_hint()
                    self.maybe_text_model()
                    self.status.set(f'本地 OCR 已更新 {time.strftime("%H:%M:%S")} | 识别 {len(lines)} 行文字')
                    continue
                if kind == 'model_error':
                    self.ai_busy = False
                    self.status.set('AI 分析失败：' + data[:220])
                    continue
                if kind == 'model':
                    self.ai_busy = False
                    model_kind, mode, result = data
                    if model_kind == 'vision':
                        self.session.match.apply(mode, result)
                    action = short(result.get('action'), 350)
                    if action:
                        self.session.last_decision = action
                    model_question = short(result.get('question'), 180)
                    if model_question:
                        extra = self.session.ask_extra(model_question)
                        if extra:
                            self.show_question(*extra)
                    self.render_hint()
                    self.status.set('AI 已更新建议 ' + time.strftime('%H:%M:%S') +
                                    (('；需补充：' + model_question) if model_question else ''))
        except queue.Empty:
            pass
        self.root.after(160, self.drain)

    def close(self):
        if self.session.phase == 'active':
            if not messagebox.askyesno('结束当前对局？',
                    '当前对局仍在进行。关闭将结束并保存无截图的对局摘要。'):
                return
            self.end_game()
        self.stop_worker()
        self.root.destroy()


if __name__ == '__main__':
    window = tk.Tk()
    Coach(window)
    window.mainloop()