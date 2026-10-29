import tempfile
import unittest
from pathlib import Path
from PIL import Image
from local_ocr import OCRLine
from scripts.benchmark_observation import evaluate


class FakeOCR:
    def recognize(self, image):
        return [OCRLine('血量18',.99,((1,1),(20,1),(20,15),(1,15)))]


class BenchmarkTests(unittest.TestCase):
    def test_missing_data_not_fabricated(self):
        self.assertEqual(evaluate({'samples': []})['status'],'pending_dataset')

    def test_sanitized_sample_precision_and_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            Image.new('RGB',(100,40),'black').save(Path(tmp)/'synthetic.png')
            report=evaluate({'_base':tmp,'samples':[{'image':'synthetic.png','expected':{'health':'18'}}]},FakeOCR())
            self.assertEqual(report['precision'],1)
            self.assertEqual(report['samples'],1)
            self.assertEqual(report['false_positive'],0)
            self.assertIn('latency_ms_p95',report)

    def test_false_positive_is_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            Image.new('RGB',(100,40),'black').save(Path(tmp)/'synthetic.png')
            report=evaluate({'_base':tmp,'samples':[{'image':'synthetic.png','expected':{'health':'15'}}]},FakeOCR())
            self.assertEqual(report['false_positive'],1)
            self.assertEqual(report['false_negative'],1)

    def test_refuses_path_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                evaluate({'_base':tmp,'samples':[{'image':'../outside.png','expected':{}}]},FakeOCR())


if __name__=='__main__':unittest.main()