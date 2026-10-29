"""Run local OCR benchmarks on a user-supplied, sanitized screenshot manifest.

Never downloads data or sends a model request. A missing dataset is *pending*, not
an artificial claim of good recognition accuracy.
"""
import argparse
import json
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from observation import Calibration, scoped_lines
from session import GameSession

FIELDS = ('health', 'energy', 'round', 'weapon')


def evaluate(manifest, ocr=None):
    from PIL import Image
    records = manifest.get('samples', [])
    if not records:
        return {'status': 'pending_dataset', 'samples': 0, 'reason': 'No sanitized labeled game captures'}
    if not isinstance(records, list):
        raise ValueError('samples must be a list')
    if ocr is None:
        from local_ocr import LocalOCR
        ocr = LocalOCR()
    base = Path(manifest['_base'])
    duration = []
    true_positive = false_positive = false_negative = questions = 0
    for sample in records:
        file = (base / sample['image']).resolve()
        if not file.is_relative_to(base.resolve()):
            raise ValueError('Screenshot path escapes dataset folder')
        expected = sample['expected']
        if not isinstance(expected, dict) or set(expected) - set(FIELDS):
            raise ValueError('Expected keys must be recognized HUD fields')
        with Image.open(file) as im:
            image = im.convert('RGB')
        calibration = Calibration({})
        if 'calibration' in sample:
            calibration = Calibration.load(base / sample['calibration'])
        start = time.perf_counter()
        lines = ocr.recognize(image)
        scoped = scoped_lines(lines, calibration, *image.size) if calibration.regions else None
        if scoped is not None:
            for key in FIELDS:
                scoped.setdefault(key, lines)
        session = GameSession()
        session.start()
        session.observe(lines, now=100, scoped=scoped)
        duration.append((time.perf_counter() - start) * 1000)
        for field in FIELDS:
            actual = session.current(field, 100)
            truth = expected.get(field)
            if actual is not None:
                if actual == truth: true_positive += 1
                else: false_positive += 1
            if truth is not None and truth != actual:
                false_negative += 1
        session.observe([], now=101, scoped={})
        questions += int(session.clarify(101) is not None)
    duration.sort()
    count = len(duration)
    return {'status':'measured', 'samples':count, 'precision':true_positive / max(1,true_positive + false_positive),
            'false_positive':false_positive, 'false_negative':false_negative,
            'latency_ms_p50':round(statistics.median(duration),2),
            'latency_ms_p95':round(duration[max(0, (95 * count + 99)//100 - 1)], 2),
            'question_rate':round(questions/count,3)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('manifest', nargs='?', default='fixtures/manifest.json')
    parser.add_argument('--output', help='Optional output JSON path')
    args=parser.parse_args()
    path=Path(args.manifest).resolve()
    if not path.is_file():
        report={'status':'pending_dataset','samples':0,'reason':'No sanitized labeled game captures'}
    else:
        manifest=json.loads(path.read_text(encoding='utf-8'))
        manifest['_base']=str(path.parent)
        report=evaluate(manifest)
    payload=json.dumps(report,ensure_ascii=False,indent=2)
    print(payload)
    if args.output:
        Path(args.output).write_text(payload+'\n',encoding='utf-8')


if __name__=='__main__':main()