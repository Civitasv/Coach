import unittest
from unittest.mock import patch

from engine import Match, parse, prompt
from providers import analyze


class EngineTests(unittest.TestCase):
    def test_invalid_json(self):
        self.assertEqual(parse('oops'), {})
        self.assertEqual(parse('```json\n{"action":"升本"}\n```')['action'], '升本')

    def test_pool_only_from_confirmed_panel(self):
        state = Match()
        good = {'scene':'pool_panel','panel_readable':True,'pool_cards':[
            {'name':'公孙离','remaining':2,'tier':3,'confidence':'high'}]}
        self.assertEqual(state.apply('常规建议',good),0)
        self.assertEqual(state.apply('牌库扫描',good),1)
        self.assertEqual(state.pool['公孙离']['remaining'],2)

    def test_bad_counts_do_not_override(self):
        s=Match()
        def scan(value):
            return {'scene':'pool_panel','panel_readable':True,'pool_cards':[
               {'name':'虞姬','remaining':value,'tier':2,'confidence':'high'}]}
        s.apply('牌库扫描',scan(6))
        for x in [-1,12,'0',True]:
            self.assertEqual(s.apply('牌库扫描',scan(x)),0)
        self.assertEqual(s.pool['虞姬']['remaining'],6)
        self.assertEqual(s.apply('牌库扫描',scan(0)),1)
        self.assertEqual(s.pool['虞姬']['remaining'],0)

    def test_low_confidence_and_unreadable_are_ignored(self):
        s=Match()
        x={'scene':'pool_panel','panel_readable':False,'pool_cards':[
             {'name':'张良','remaining':0,'confidence':'high'}]}
        self.assertEqual(s.apply('牌库扫描',x),0)
        x['panel_readable']=True
        x['pool_cards'][0]['confidence']='low'
        self.assertEqual(s.apply('牌库扫描',x),0)

    def test_opponents_only_on_scout(self):
        s=Match()
        o={'scene':'opponent_panel','panel_readable':True,'opponents':[
            {'player':'玩家A','heroes':['司马懿','吕布'],'threat':'切后排','confidence':'high'}]}
        self.assertEqual(s.apply('牌库扫描',o),0)
        self.assertEqual(s.apply('对手侦察',o),1)
        self.assertIn('玩家A',s.context())
        s.reset()
        self.assertEqual(len(s.opponents),0)

    def test_prompt_marks_staleness(self):
        p=prompt('常规建议',Match(),'低血量')
        self.assertIn('可能过期',p)
        self.assertIn('低血量',p)

    def test_deepseek_vision_payload(self):
        sample={'choices':[{'message':{'content':'{}'}}]}
        with patch('providers.request',return_value=sample) as r:
            self.assertEqual(analyze('DeepSeek 云端',b'abc','你好','deepseek-flash','secret'),'{}')
            url,payload,key=r.call_args.args
            self.assertEqual(url,'https://api.deepseek.com/chat/completions')
            self.assertEqual(payload['thinking']['type'],'disabled')
            self.assertEqual(payload['messages'][1]['content'][1]['type'],'image_url')
            self.assertEqual(key,'secret')

    def test_cloud_key_required(self):
        with self.assertRaises(ValueError):
            analyze('DeepSeek 云端',b'a','p','deepseek-flash','')

if __name__=='__main__':unittest.main()