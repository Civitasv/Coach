import unittest
from local_ocr import OCRLine
from session import GameSession
from icon_matcher import IconResult


class StructuredSessionTests(unittest.TestCase):
    def test_scoped_hud_parsing_and_provenance(self):
        s=GameSession(); s.start()
        h=OCRLine('血量18', .97)
        e=OCRLine('能量9', .97)
        s.observe([h,e],now=100,scoped={'health':[h],'energy':[e]})
        self.assertEqual(s.current('health',101),'18')
        self.assertEqual(s.ledger.snapshot(101)['health']['source'],'ocr:health')
        self.assertIsNone(s.current('energy',119))
        s.end();s.start()
        self.assertEqual(s.ledger.facts,{})

    def test_off_region_text_cannot_claim_hud_field(self):
        s=GameSession();s.start()
        s.observe([OCRLine('血量18',.99)],now=10,scoped={'health':[], 'shop':[OCRLine('血量18',.99)]})
        self.assertIsNone(s.current('health',11))

    def test_conflict_requires_clarification(self):
        s=GameSession();s.start()
        s.observe([OCRLine('血量11',.9),OCRLine('血量19',.9)],now=50)
        self.assertIsNone(s.current('health',50))
        self.assertIn('health',s.ledger.conflicts)
        s.observe([], now=51)
        self.assertEqual(s.clarify(51)[0],'health')
        s.reply('health','18',now=52)
        self.assertEqual(s.current('health',53),'18')
        s.observe([OCRLine('血量9',.99)],now=54)
        self.assertEqual(s.current('health',55),'18')

    def test_icon_snapshots_change_and_expire(self):
        s=GameSession();s.start()
        self.assertTrue(s.record_icons({'shop_slot_1':IconResult('公孙离',.96)},now=100))
        self.assertFalse(s.record_icons({'shop_slot_1':IconResult('公孙离',.96)},now=101))
        self.assertIn('公孙离',s.context(now=102))
        self.assertNotIn('公孙离',s.context(now=192))
        self.assertTrue(s.record_icons({'shop_slot_1':IconResult(None,.4)},now=103))
        self.assertEqual(s.icon_slots,{})
        s.end();s.start();self.assertEqual(s.icon_slots,{})

    def test_enemy_icon_is_fragment_not_full_lineup(self):
        s=GameSession();s.start()
        s.record_icons({'enemy_icon':IconResult('司马懿',.97)},now=5)
        self.assertEqual(s.enemy_snapshot['name'],'司马懿')
        self.assertEqual(s.match.opponents,{})
        self.assertEqual(s.match.pool,{})


if __name__=='__main__':unittest.main()