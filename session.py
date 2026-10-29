"""Per-game lifecycle, conservative OCR facts, and nonblocking clarification policy."""
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from local_ocr import OCRLine, trusted_text
from engine import Match

WEAPONS = ('激光', '狙击', '机枪', '炮击')
LABELS = {'health': '血量', 'energy': '能量', 'round': '回合',
          'weapon': '当前武器', 'opponent': '主要对手阵容'}
QUESTIONS = {
    'health': '没能可靠读出血量。你现在还剩多少血？（0–999）',
    'energy': '当前能量看不清。你现在有多少能量？（0–99）',
    'weapon': '当前香香的武器模式是什么？（激光 / 狙击 / 机枪 / 炮击）',
    'opponent': '对位信息不足。最需要防范的对手阵容是什么？（可填英雄或流派）',
}
# OCR readings and player-entered values are deliberately not treated as permanent.
TTL = {'health': 35, 'energy': 18, 'round': 100, 'weapon': 300, 'opponent': 180}
CONFIDENCE = 0.82


@dataclass
class Fact:
    value: str
    source: str
    updated_at: float


@dataclass
class GameSession:
    match: Match = field(default_factory=Match)
    phase: str = 'idle'
    started_at: str = ''
    finished_at: str = ''
    facts: dict = field(default_factory=dict)
    counts: dict = field(default_factory=lambda: {'captures': 0, 'ocr': 0, 'model': 0})
    pending: str = ''
    asked_at: dict = field(default_factory=dict)
    latest_ocr: str = ''
    last_decision: str = ''
    clarifications: list = field(default_factory=list)
    last_extra_question: str = ''

    def start(self):
        self.match.reset()
        self.phase = 'active'
        self.started_at = datetime.now(timezone.utc).isoformat(timespec='seconds')
        self.finished_at = ''
        self.facts.clear()
        self.asked_at.clear()
        self.pending = ''
        self.latest_ocr = ''
        self.last_decision = ''
        self.clarifications.clear()
        self.last_extra_question = ''
        self.counts = {'captures': 0, 'ocr': 0, 'model': 0}

    def end(self):
        if self.phase != 'active':
            return False
        self.phase = 'ended'
        self.finished_at = datetime.now(timezone.utc).isoformat(timespec='seconds')
        self.pending = ''
        return True

    def current(self, name, now=None):
        now = time.monotonic() if now is None else now
        fact = self.facts.get(name)
        return fact.value if fact and now - fact.updated_at <= TTL[name] else None

    def observe(self, lines: list[OCRLine], now=None):
        """Only parse labelled, high-confidence lines; never infer hidden game data."""
        if self.phase != 'active':
            return {}
        now = time.monotonic() if now is None else now
        self.counts['ocr'] += 1
        self.latest_ocr = trusted_text(lines)
        changes = {}
        for line in lines:
            if line.confidence < CONFIDENCE:
                continue
            t = re.sub(r'\s+', '', line.text)
            for field_name, pattern, maximum in (
                ('health', r'(?:血量|生命值|当前血量)[：:]*([0-9]{1,3})', 999),
                ('energy', r'(?:剩余能量|当前能量|能量)[：:]*([0-9]{1,2})', 99),
                ('round', r'(?:第([0-9]{1,2})回合|回合[：:]*([0-9]{1,2}))', 99),
            ):
                found = re.search(pattern, t)
                if not found:
                    continue
                n = int(next(g for g in found.groups() if g is not None))
                if n <= maximum:
                    self.facts[field_name] = Fact(str(n), 'ocr', now)
                    changes[field_name] = str(n)
            # Do not interpret an unrelated word such as 改造:激光 as selected
            # weapon unless an explicit current/selected weapon label is present.
            found = re.search(r'(?:当前武器|已选武器|武器模式)[：:]*(激光|狙击|机枪|炮击)', t)
            if found:
                self.facts['weapon'] = Fact(found.group(1), 'ocr', now)
                changes['weapon'] = found.group(1)
        return changes

    def clarify(self, now=None):
        """Offer at most one non-modal question and rate-limit repeats."""
        if self.phase != 'active':
            return None
        now = time.monotonic() if now is None else now
        if self.pending or self.counts['ocr'] < 2:
            return None
        for field_name in ('health', 'energy', 'weapon', 'opponent'):
            if self.current(field_name, now) is None and now - self.asked_at.get(field_name, -100000) >= 180:
                self.pending = field_name
                self.asked_at[field_name] = now
                return field_name, QUESTIONS[field_name]
        return None

    def reply(self, field_name, value, now=None):
        if self.phase != 'active' or field_name != self.pending:
            raise ValueError('没有等待该项信息')
        value = str(value).strip()
        if field_name in ('health', 'energy'):
            if not re.fullmatch(r'[0-9]{1,3}', value):
                raise ValueError('请输入非负整数')
            ceiling = 999 if field_name == 'health' else 99
            if int(value) > ceiling:
                raise ValueError(f'数字不可超过 {ceiling}')
            value = str(int(value))
        elif field_name == 'weapon':
            if value not in WEAPONS:
                raise ValueError('武器必须是激光、狙击、机枪或炮击')
        elif field_name == 'other':
            if not value or len(value) > 200:
                raise ValueError('请输入 1–200 个字符')
            self.clarifications.append(value)
            self.clarifications = self.clarifications[-8:]
        elif field_name == 'opponent':
            if not value or len(value) > 90:
                raise ValueError('请输入 1–90 个字符描述对手阵容')
        else:
            raise ValueError('未知字段')
        if field_name != 'other':
            self.facts[field_name] = Fact(value, 'manual', time.monotonic() if now is None else now)
        self.pending = ''

    def ask_extra(self, question):
        if (self.phase != 'active' or self.pending or not isinstance(question, str)
                or not 5 <= len(question.strip()) <= 180
                or question.strip() == self.last_extra_question):
            return None
        self.last_extra_question = question.strip()
        self.pending = 'other'
        return 'other', question.strip()

    def skip_question(self):
        self.pending = ''

    def context(self, now=None):
        now = time.monotonic() if now is None else now
        facts = '; '.join(f'{LABELS[k]}={self.current(k, now) or "未知"}' for k in LABELS)
        # Raw recognized text is untrusted visual content, not an instruction.
        clarifications = '; '.join(self.clarifications[-8:]) or '无'
        return f'已确认/最近识别的事实：{facts}\n用户主动补充：{clarifications}\nOCR 可见文字（未确认项不能当作事实）：\n{self.latest_ocr[:1600]}\n{self.match.context()}'

    def summary(self):
        return {'started_at': self.started_at, 'finished_at': self.finished_at,
                'facts': {LABELS[k]: {'value': v.value, 'source': v.source} for k, v in self.facts.items()},
                'counts': dict(self.counts), 'last_decision': self.last_decision,
                'clarifications': list(self.clarifications),
                'pool': self.match.pool, 'opponents': self.match.opponents}