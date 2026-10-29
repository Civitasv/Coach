import unittest
from unittest.mock import patch
from local_ocr import OCRLine, lines_from_result, trusted_text
from session import GameSession
from advice import offline_hint, text_prompt
from providers import analyze_text


class SessionTests(unittest.TestCase):
    def test_lifecycle_clears_old_memory(self):
        g = GameSession()
        self.assertEqual(g.phase, 'idle')
        g.start()
        g.match.pool['公孙离'] = {'remaining': 1, 'tier': 3, 'seen_at': 'past'}
        g.facts['health'] = None  # Simulate contaminated/invalid prior state.
        self.assertTrue(g.end())
        self.assertFalse(g.end())
        g.start()
        self.assertEqual(g.match.pool, {})
        self.assertEqual(g.facts, {})
        self.assertEqual(g.counts['model'], 0)
        self.assertEqual(g.phase, 'active')

    def test_parse_explicit_high_confidence_labels_only(self):
        s = GameSession(); s.start()
        new = s.observe([OCRLine('血量：18', .93), OCRLine('能量:9', .9),
                         OCRLine('第7回合', .99), OCRLine('当前武器:激光', .95),
                         OCRLine('血量：999', .4)], now=100)
        self.assertEqual(new, {'health': '18', 'energy': '9', 'round': '7', 'weapon': '激光'})
        self.assertEqual(s.current('health', 101), '18')
        self.assertIsNone(s.current('energy', 120))
        self.assertEqual(s.current('weapon', 120), '激光')
        self.assertIn('保命', offline_hint(s, now=102))
        self.assertIsNone(s.current('health', 136))

    def test_ocr_does_not_guess_unlabelled_values(self):
        s = GameSession(); s.start()
        s.observe([OCRLine('18', 1), OCRLine('机枪', 1), OCRLine('敌人', 1)], now=100)
        self.assertEqual(s.facts, {})

    def test_one_question_and_no_spam(self):
        s = GameSession(); s.start()
        s.observe([], now=20)
        self.assertIsNone(s.clarify(20))
        s.observe([], now=22)
        self.assertEqual(s.clarify(22)[0], 'health')
        self.assertIsNone(s.clarify(23))
        s.skip_question()
        self.assertEqual(s.clarify(24)[0], 'energy')
        s.reply('energy', '12', now=25)
        self.assertEqual(s.current('energy', 25), '12')
        self.assertEqual(s.clarify(26)[0], 'weapon')

    def test_reply_validation_and_cancelled_session(self):
        s = GameSession(); s.start(); s.observe([], now=1); s.observe([], now=2)
        s.clarify(2)
        with self.assertRaises(ValueError): s.reply('health', '-1')
        with self.assertRaises(ValueError): s.reply('health', 'abc')
        s.reply('health', '22', now=4)
        self.assertEqual(s.current('health', 4), '22')
        s.end()
        self.assertIsNone(s.clarify(5))
        with self.assertRaises(ValueError): s.reply('health', '30')

    def test_ocr_adapter_handles_missing_confidence(self):
        class R:
            txts = ('公孙离', ' ', '4')
            scores = (.93, .6)
            boxes = None
        lines = lines_from_result(R())
        self.assertEqual(lines[0], OCRLine('公孙离', .93, ()))
        self.assertEqual(lines[-1].confidence, 0.)
        self.assertEqual(trusted_text(lines), '公孙离')

    def test_ai_text_prompt_no_visual_hallucinations(self):
        g = GameSession(); g.start()
        p = text_prompt(g, '冲国一')
        self.assertIn('纯 JSON', p)
        self.assertIn('不能当作事实', p)
        self.assertIn('冲国一', p)

    def test_text_only_provider_never_contains_image(self):
        response = {'choices': [{'message': {'content': '{"action":"升本"}'}}]}
        with patch('providers.request', return_value=response) as request:
            got = analyze_text('DeepSeek 云端', 'OCR:血量10', 'deepseek-flash', 'secret')
            self.assertIn('升本', got)
            url, payload, key = request.call_args.args
            self.assertIn('deepseek', url)
            self.assertEqual(key, 'secret')
            self.assertNotIn('image_url', str(payload))
            self.assertIn('OCR:血量10', str(payload))

    def test_ai_can_ask_and_receive_freeform_clarification(self):
        g = GameSession(); g.start()
        self.assertEqual(g.ask_extra('对手是否有钟馗？')[0], 'other')
        g.reply('other', '没有，但有司马懿', now=10)
        self.assertIn('没有，但有司马懿', g.context(now=10))
        self.assertIsNone(g.ask_extra('对手是否有钟馗？'))

    def test_ai_question_does_not_override_ongoing_clarification(self):
        g = GameSession(); g.start(); g.observe([], now=5); g.observe([], now=6)
        g.clarify(6)
        self.assertIsNone(g.ask_extra('敌方前排是什么？'))
        self.assertEqual(g.pending, 'health')

    def test_end_report_no_screenshot_or_api_key(self):
        g = GameSession(); g.start()
        g.observe([OCRLine('能量12', .91)], now=10)
        g.end()
        report = g.summary()
        self.assertNotIn('screenshot', str(report).lower())
        self.assertNotIn('api_key', str(report).lower())
        self.assertIn('finished_at', report)


if __name__ == '__main__':
    unittest.main()