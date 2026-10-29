"""Network backends. Cloud upload only after an explicit UI confirmation."""
import base64
import json
import urllib.request
import urllib.error
from engine import SYSTEM


def request(url, payload, token=None):
    headers = {'Content-Type':'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    req = urllib.request.Request(url, json.dumps(payload, ensure_ascii=False).encode(), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.load(r)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
        raise RuntimeError(f'模型调用失败：{e}') from e


def analyze(provider, image, prompt, model, key=''):
    if not model.strip():
        raise ValueError('模型名称不能为空')
    b64 = base64.b64encode(image).decode()
    if provider == 'Ollama 本地':
        data = request('http://127.0.0.1:11434/api/chat', {'model': model, 'stream': False,
            'format': 'json', 'messages': [{'role':'system','content':SYSTEM},
              {'role':'user','content':prompt,'images':[b64]}]})
        return data['message']['content']
    if not key.strip():
        raise ValueError('请提供相应的 API Key 或设置环境变量')
    if provider == 'DeepSeek 云端':
        data = request('https://api.deepseek.com/chat/completions', {
            'model': model, 'thinking': {'type':'disabled'}, 'max_tokens': 1000,
            'messages': [{'role':'system','content':SYSTEM}, {'role':'user','content':[
              {'type':'text','text':prompt}, {'type':'image_url','image_url':{
                  'url':'data:image/jpeg;base64,'+b64, 'detail':'high'}}]}]}, key)
        return data['choices'][0]['message']['content']
    if provider == 'OpenAI 云端':
        data = request('https://api.openai.com/v1/responses', {'model':model, 'store':False,
          'max_output_tokens':1000,'instructions':SYSTEM,'input':[{'role':'user','content':[
            {'type':'input_text','text':prompt},{'type':'input_image',
              'image_url':'data:image/jpeg;base64,'+b64,'detail':'high'}]}]}, key)
        return '\n'.join(b['text'] for item in data.get('output',[]) for b in item.get('content',[]) if b.get('type')=='output_text')
    raise ValueError('不支持的提供商')