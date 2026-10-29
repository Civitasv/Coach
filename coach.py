"""Coach: read-only screen observer. Python 3.10+; Windows-oriented Tk desktop app."""
import io
import os
import queue
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

from PIL import Image, ImageChops, ImageStat, ImageTk
import mss

from engine import Match, parse, prompt, short
from providers import analyze

PROVIDERS = {'DeepSeek 云端':('deepseek-flash','DEEPSEEK_API_KEY'),
             'Ollama 本地':('gemma3:4b',''), 'OpenAI 云端':('gpt-4.1-mini','OPENAI_API_KEY')}
MODES = ('常规建议','牌库扫描','对手侦察')


def grab(box):
    with mss.mss() as s:
        shot = s.grab(box)
    return Image.frombytes('RGB', shot.size, shot.rgb)


def jpeg(image):
    image = image.convert('RGB')
    if image.width > 1920:
        image.thumbnail((1920, 1600))
    b = io.BytesIO()
    image.save(b, 'JPEG', quality=85)
    return b.getvalue()


def changed(image, previous):
    thumb = image.convert('L').resize((128,72))
    if previous is None:
        return True, thumb
    diff = ImageStat.Stat(ImageChops.difference(thumb, previous)).mean[0]
    return diff >= 2.3, thumb


class Picker(tk.Toplevel):
    def __init__(self, master, monitor, callback):
        super().__init__(master)
        self.title('拖拽选择游戏区域 · Esc 取消')
        self.callback = callback
        self.monitor = monitor
        shot = grab(monitor)
        self.factor = min(1, 1250 / shot.width, 720 / shot.height)
        w, h = round(shot.width*self.factor), round(shot.height*self.factor)
        self.photo = ImageTk.PhotoImage(shot.resize((w,h)))
        self.canvas = tk.Canvas(self, width=w, height=h, cursor='crosshair')
        self.canvas.pack()
        self.canvas.create_image(0,0,image=self.photo,anchor='nw')
        self.anchor = None
        self.rectangle = None
        self.canvas.bind('<Button-1>', self.down)
        self.canvas.bind('<B1-Motion>', self.move)
        self.canvas.bind('<ButtonRelease-1>', self.up)
        self.bind('<Escape>', lambda _:self.destroy())
        self.grab_set()

    def down(self, e):
        self.anchor = (e.x,e.y)
        self.rectangle = self.canvas.create_rectangle(e.x,e.y,e.x,e.y,outline='#00ddff',width=3)

    def move(self,e):
        if self.rectangle:
            self.canvas.coords(self.rectangle,*self.anchor,e.x,e.y)

    def up(self,e):
        if not self.anchor: return
        ax,ay = self.anchor
        x1,x2 = sorted((max(0,ax), max(0,e.x)))
        y1,y2 = sorted((max(0,ay), max(0,e.y)))
        if x2-x1 < 100 or y2-y1 < 70:
            messagebox.showwarning('区域过小','请框选更大的游戏区域',parent=self)
            return
        f = self.factor
        self.callback({'left':self.monitor['left']+round(x1/f),
          'top':self.monitor['top']+round(y1/f), 'width':round((x2-x1)/f),
          'height':round((y2-y1)/f)})
        self.destroy()


class Coach:
    def __init__(self, root):
        self.root = root
        root.title('Coach · 香香实时教练')
        root.geometry('550x760')
        root.attributes('-topmost', True)
        self.state = Match()
        self.events = queue.Queue()
        self.run_id = 0
        self.monitoring = False
        self.busy = False
        self.request_count = 0
        self.last_thumb = None
        self.rect = None
        self.next_at = 0
        self.provider = tk.StringVar(value='DeepSeek 云端')
        self.model = tk.StringVar(value='deepseek-flash')
        self.mode = tk.StringVar(value=MODES[0])
        self.interval = tk.StringVar(value='20')
        self.max_calls = tk.StringVar(value='100')
        self.key = tk.StringVar()
        self.notes = tk.StringVar(value='目标：香香稳前三，争取登顶。')
        self.status = tk.StringVar(value='请选择显示器和监看区域；默认不上传任何画面。')
        self.monitors = []
        self.build()
        self.provider.trace_add('write',self.provider_changed)
        self.root.after(250,self.drain)
        self.root.after(500,self.tick)
        self.root.protocol('WM_DELETE_WINDOW',self.close)

    def build(self):
        f = ttk.Frame(self.root,padding=14)
        f.pack(fill='both',expand=True)
        ttk.Label(f,text='Coach / 王者万象棋 · 孙尚香',font=('Microsoft YaHei UI',16,'bold')).pack(anchor='w',pady=(0,12))
        self.monitor = ttk.Combobox(f,state='readonly')
        self.monitor.pack(fill='x')
        self.refresh_monitors()
        row = ttk.Frame(f)
        row.pack(fill='x',pady=6)
        ttk.Button(row,text='选取屏幕区域',command=self.pick).pack(side='left')
        ttk.Button(row,text='刷新显示器',command=self.refresh_monitors).pack(side='left',padx=6)
        self.region_label=ttk.Label(row,text='未框选')
        self.region_label.pack(side='left')

        row=ttk.Frame(f);row.pack(fill='x',pady=6)
        ttk.Label(row,text='视觉模型').pack(side='left')
        ttk.Combobox(row,textvariable=self.provider,values=list(PROVIDERS),state='readonly',width=16).pack(side='left',padx=6)
        ttk.Entry(row,textvariable=self.model,width=20).pack(side='left',fill='x',expand=True)
        ttk.Label(f,text='API Key（只在内存中，或通过 DEEPSEEK_API_KEY / OPENAI_API_KEY 环境变量提供）').pack(anchor='w')
        ttk.Entry(f,textvariable=self.key,show='●').pack(fill='x',pady=(3,7))
        row=ttk.Frame(f);row.pack(fill='x')
        ttk.Label(row,text='分析模式').pack(side='left')
        ttk.Combobox(row,textvariable=self.mode,values=MODES,state='readonly',width=14).pack(side='left',padx=6)
        ttk.Label(row,text='间隔(秒)').pack(side='left')
        ttk.Entry(row,textvariable=self.interval,width=5).pack(side='left',padx=5)
        ttk.Label(row,text='单局最大请求').pack(side='left')
        ttk.Entry(row,textvariable=self.max_calls,width=5).pack(side='left')
        ttk.Entry(f,textvariable=self.notes).pack(fill='x',pady=(8,5))
        row=ttk.Frame(f);row.pack(fill='x',pady=5)
        self.toggle_btn=ttk.Button(row,text='开始监看',command=self.toggle)
        self.toggle_btn.pack(side='left')
        ttk.Button(row,text='分析一次',command=self.once).pack(side='left',padx=6)
        ttk.Button(row,text='新开一局（清空记录）',command=self.reset).pack(side='left')
        ttk.Label(f,textvariable=self.status,wraplength=510,foreground='#006699').pack(anchor='w',pady=6)
        self.preview=ttk.Label(f,text='无截图预览')
        self.preview.pack(fill='x',pady=5)
        self.output=tk.Text(f,wrap='word',height=20,font=('Microsoft YaHei UI',10))
        self.output.pack(fill='both',expand=True)
        self.output.insert('end','提示：普通对局选择「常规建议」；打开牌库页面后切换「牌库扫描」；查看对手时切换「对手侦察」。\n')
        self.last_photo=None

    def refresh_monitors(self):
        with mss.mss() as s:
            self.monitors=[dict(m) for m in s.monitors[1:]]
        self.monitor['values']=[f'显示器 {i+1}: {m["width"]}×{m["height"]}' for i,m in enumerate(self.monitors)]
        if self.monitors: self.monitor.current(0)

    def pick(self):
        if self.monitoring: self.stop()
        if not self.monitors: return
        Picker(self.root,self.monitors[max(0,self.monitor.current())],self.set_region)

    def set_region(self, box):
        self.rect = box
        self.last_thumb = None
        self.region_label.config(text=f'{box["width"]}×{box["height"]}')
        self.status.set('已选择画面范围')

    def provider_changed(self,*_):
        self.stop()
        self.model.set(PROVIDERS[self.provider.get()][0])
        self.key.set('')
        self.status.set('模型已切换；需要重新确认云端截图发送')

    def stop(self):
        self.monitoring=False
        self.busy=False
        self.run_id+=1
        self.toggle_btn.config(text='开始监看')

    def prepare(self):
        if not self.rect:
            messagebox.showwarning('缺少区域','先选择屏幕上的游戏区域');return False
        provider=self.provider.get()
        if provider != 'Ollama 本地':
            env_key=PROVIDERS[provider][1]
            if not (self.key.get().strip() or os.environ.get(env_key,'')):
                messagebox.showwarning('缺少密钥',f'请输入 API Key 或设置 {env_key}');return False
            if not messagebox.askyesno('确认上传截图',f'即将发送所选区域截图和局面文字至 {provider}。确认区域无隐私内容？'):
                return False
        return True

    def limit(self):
        try:return max(1,min(int(self.max_calls.get()),2000))
        except ValueError:return 100

    def seconds(self):
        try:return max(8,min(int(self.interval.get()),120))
        except ValueError:return 20

    def toggle(self):
        if self.monitoring:
            self.stop();self.status.set('监看已暂停');return
        if not self.prepare():return
        self.run_id+=1
        self.monitoring=True
        self.toggle_btn.config(text='暂停监看')
        self.last_thumb=None
        self.next_at=0
        self.status.set('已开始监看')

    def once(self):
        if not self.prepare() or self.busy:return
        self.launch(force=True)

    def tick(self):
        if self.monitoring and not self.busy and time.monotonic() >= self.next_at:
            self.launch(force=False)
        self.root.after(500,self.tick)

    def launch(self,force):
        if not self.rect or self.busy:return
        if self.request_count >= self.limit():
            self.stop();self.status.set('已达到单局调用上限，请新开一局以重置');return
        self.busy=True
        self.next_at=time.monotonic()+self.seconds()
        current_id=self.run_id
        mode,provider,model=self.mode.get(),self.provider.get(),self.model.get()
        key=self.key.get() or os.environ.get(PROVIDERS[provider][1],'')
        request_prompt=prompt(mode,self.state,self.notes.get())
        old_thumb=self.last_thumb
        rect=self.rect.copy()

        def worker():
            try:
                im=grab(rect)
                different,thumb=changed(im,old_thumb)
                if not force and not different:
                    self.events.put((current_id,'skip',(im,thumb)));return
                self.events.put((current_id,'sent',None))
                result=parse(analyze(provider,jpeg(im),request_prompt,model,key))
                self.events.put((current_id,'ok',(im,thumb,mode,result)))
            except Exception as exc:
                self.events.put((current_id,'error',str(exc)))
        threading.Thread(target=worker,daemon=True).start()
        self.status.set('正在分析截图…')

    def drain(self):
        try:
            while True:
                run_id,kind,data=self.events.get_nowait()
                if run_id!=self.run_id:continue
                if kind=='sent':
                    self.request_count+=1;continue
                self.busy=False
                if kind=='skip':
                    self.status.set('画面未变化，本次没有调用模型')
                    continue
                if kind=='error':
                    self.stop();self.status.set('分析失败：'+data[:180]);continue
                im,thumb,mode,ans=data
                self.last_thumb=thumb
                updated=self.state.apply(mode,ans)
                im.thumbnail((500,115));self.last_photo=ImageTk.PhotoImage(im)
                self.preview.config(image=self.last_photo,text='')
                summary=(f'模式：{mode} | 本局请求 {self.request_count}/{self.limit()} | 新确认记录 {updated}\n\n'
                    f'建议：{short(ans.get("action")) or "截图无法可靠识别，请调整框选区域"}\n\n'
                    f'依据：{short(ans.get("observed"))}\n备选：{short(ans.get("alternative"))}\n'
                    f'风险：{short(ans.get("risk"))}\n置信度：{short(ans.get("confidence"))}\n\n'
                    f'牌库记录 {len(self.state.pool)} 项；对手记录 {len(self.state.opponents)} 人。\n'
                    f'{self.state.context()[:1600]}')
                self.output.delete('1.0','end');self.output.insert('end',summary)
                self.status.set('分析完成 '+time.strftime('%H:%M:%S'))
        except queue.Empty:
            pass
        self.root.after(250,self.drain)

    def reset(self):
        if self.monitoring:self.stop()
        self.state.reset();self.request_count=0;self.last_thumb=None
        self.output.delete('1.0','end');self.output.insert('end','新局已清空牌库和对手快照。')
        self.status.set('新局初始化完成')

    def close(self):
        self.stop();self.root.destroy()


if __name__=='__main__':
    r=tk.Tk();Coach(r);r.mainloop()