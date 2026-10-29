"""Spec 002 contract tests, using synthetic local-only assets (not game evidence)."""
import tempfile
import unittest
from pathlib import Path
from PIL import Image, ImageDraw

from observation import Calibration, Observation, ROI, FactLedger, scoped_lines
from icon_matcher import IconMatcher
from local_ocr import OCRLine


class ROIContract(unittest.TestCase):
    def test_resolution_independent_crop_and_reject_invalid(self):
        roi = ROI(0.25, 0.1, 0.5, 0.4)
        self.assertEqual(roi.pixels(1920, 1080), (480, 108, 1440, 540))
        self.assertEqual(roi.pixels(960, 540), (240, 54, 720, 270))
        for args in ((-0.1, 0, .2, .2), (.7, .5, .4, .3), (0,0,0,.3)):
            with self.assertRaises(ValueError): ROI(*args)

    def test_calibration_is_opt_in_and_roundtrips(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'calibration.json'
            self.assertFalse(path.exists())
            c=Calibration({'health':ROI(0,0,.2,.2), 'shop_slot_1':ROI(.2,.7,.1,.1)})
            c.save(path)
            self.assertEqual(Calibration.load(path),c)
            self.assertFalse(list(Path(tmp).glob('*.tmp')))
            with self.assertRaises(ValueError):Calibration({'not_a_region':ROI(0,0,.1,.1)})

    def test_line_coordinates_are_scoped(self):
        lines=[OCRLine('血量18', .99, ((20,5),(65,5),(65,24),(20,24))),
               OCRLine('能量12', .99, ((140,5),(190,5),(190,24),(140,24))),
               OCRLine('无定位', .99)]
        c=Calibration({'health':ROI(0,0,.45,.4), 'energy':ROI(.6,0,.4,.4)})
        scoped=scoped_lines(lines,c,200,100)
        self.assertEqual([v.text for v in scoped['health']], ['血量18'])
        self.assertEqual([v.text for v in scoped['energy']], ['能量12'])
        self.assertNotIn('无定位', str(scoped))


class LedgerContract(unittest.TestCase):
    def test_confidence_source_ttl_and_conflict(self):
        ledger=FactLedger()
        self.assertFalse(ledger.accept('health', Observation('health','12',.5,'ocr:health',100,130)))
        self.assertTrue(ledger.accept('health', Observation('health','12',.96,'ocr:health',100,130)))
        self.assertEqual(ledger.get('health',120).value,'12')
        self.assertIsNone(ledger.get('health',131))
        self.assertEqual(ledger.snapshot(120)['health']['source'],'ocr:health')
        ledger.accept('health',Observation('health','12',.9,'ocr:health',150,180))
        ledger.accept('health',Observation('health','19',.93,'ocr:health',150,180))
        self.assertIsNone(ledger.get('health',150))
        self.assertIn('health',ledger.conflicts)
        self.assertTrue(ledger.accept('health',Observation('health','19',1,'manual',151,200)))
        self.assertEqual(ledger.get('health',160).value,'19')
        self.assertFalse(ledger.accept('health',Observation('health','20',.99,'ocr:health',152,190)))
        self.assertEqual(ledger.get('health',160).value,'19')

    def test_stale_evidence_cannot_replace_fresh(self):
        ledger=FactLedger()
        ledger.accept('energy',Observation('energy','10',1,'ocr:energy',200,210))
        self.assertFalse(ledger.accept('energy',Observation('energy','20',1,'ocr:energy',180,220)))
        self.assertEqual(ledger.get('energy',201).value,'10')


class IconContract(unittest.TestCase):
    @staticmethod
    def img(kind):
        img=Image.new('RGB',(32,32),'black')
        pen=ImageDraw.Draw(img)
        if kind=='circle':pen.ellipse((5,5,26,26),fill='white')
        elif kind=='square':pen.rectangle((5,5,26,26),fill='white')
        return img

    def test_calibrated_match_and_unknown(self):
        matcher=IconMatcher({'圆形':self.img('circle'),'方形':self.img('square')}, min_score=.92, min_margin=.02)
        self.assertEqual(matcher.classify(self.img('circle')).name,'圆形')
        self.assertIsNone(matcher.classify(self.img('other')).name)
        self.assertIsNone(IconMatcher({}).classify(self.img('circle')).name)

    def test_ambiguous_template_is_unknown(self):
        img=self.img('circle')
        matcher=IconMatcher({'A':img,'B':img},min_score=.8,min_margin=.05)
        self.assertIsNone(matcher.classify(img).name)


if __name__=='__main__':unittest.main()