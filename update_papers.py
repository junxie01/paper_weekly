import requests
import feedparser
import json
import os
import urllib.parse
import time
import re
from datetime import datetime, timedelta
from deep_translator import GoogleTranslator
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib3.exceptions import InsecureRequestWarning

# 禁用 SSL 警告
import warnings
warnings.filterwarnings('ignore', category=InsecureRequestWarning)

# 禁用代理设置
os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''

# 创建 session 并配置重试策略
session = requests.Session()
session.trust_env = False  # 忽略环境变量中的代理设置

# 配置重试策略：最多重试3次，间隔1秒
retry_strategy = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["HEAD", "GET", "OPTIONS"]
)
adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("https://", adapter)
session.mount("http://", adapter)

# ==========================================
# 1. 核心配置：5大专题与精准关键词
# ==========================================
TOPICS = {
    'cryoseismology': {
        'name_zh': '冰川地震学',
        'keywords': ['glacier seismology', 'icequake', 'ice shelf collapse', 'iceberg calving', 'glacial seismicity'],
        'file': 'data_cryo.json'
    },
    'das': {
        'name_zh': '分布式光纤传感',
        'keywords': ['Distributed Acoustic Sensing', 'DAS', 'distributed fiber optic sensing', 'phase-sensitive OTDR', 'fiber optic seismic monitoring'],
        'file': 'data_das.json'
    },
    'surface_wave': {
        'name_zh': '面波研究',
        'keywords': ['surface wave', 'Rayleigh wave', 'Love wave', 'surface wave detection', 'ambient noise interferometry'],
        'file': 'data_surface.json'
    },
    'imaging': {
        'name_zh': '地震成像',
        'keywords': ['seismic tomography', 'surface wave tomography', 'body wave tomography', 'full waveform inversion', 'seismic imaging'],
        'file': 'data_imaging.json'
    },
    'earthquake': {
        'name_zh': '地震研究',
        'keywords': ['earthquake source', 'microseismic monitoring', 'focal mechanism', 'source mechanism inversion', 'seismic source location'],
        'file': 'data_earthquake.json'
    },
    'ai': {
        'name_zh': '人工智能与地震学',
        'keywords': [
            'machine learning seismic',
            'deep learning earthquake',
            'neural network seismology',
            'AI earthquake prediction',
            'machine learning wave',
            'deep learning geophysics',
            'neural network seismic detection',
            'AI seismic imaging',
            'machine learning tremor',
            'deep learning fault'
        ],
        'file': 'data_ai.json'
    }
}

JOURNALS = [
    'Nature', 'Science', 'Nature Geoscience', 'Science Advances',
    'Journal of Geophysical Research: Solid Earth', 'Geophysical Research Letters',
    'Earth and Planetary Science Letters', 'Geophysical Journal International',
    'Seismological Research Letters', 'The Cryosphere', 'Bulletin of the Seismological Society of America'
]

def clean_abstract(text):
    """清洗摘要中的 XML 标签和特定词汇"""
    if not text: return ""
    # 移除 <jats:title>Abstract</jats:title> 等标签
    text = re.sub(r'<[^>]+>', '', text)
    # 移除开头或特定位置的 "Abstract", "摘要", "抽象的。"
    text = re.sub(r'^(Abstract|摘要|抽象的。|抽象的)\s*', '', text, flags=re.IGNORECASE)
    return text.strip()

def translate_text(text, max_len=2000):
    if not text or len(text) < 10: return "无摘要详情"
    try:
        translator = GoogleTranslator(source='auto', target='zh-CN')
        translated = translator.translate(text[:max_len])
        # 二次清洗翻译结果中的“抽象的。”
        return clean_abstract(translated)
    except: return "翻译失败"

def search_crossref(topic_config, max_results=10):
    print(f"正在 Crossref 检索 ({topic_config['name_zh']})...")
    query_str = " ".join(topic_config['keywords'])
    filters = [f"container-title:{j}" for j in JOURNALS] + ["type:journal-article"]
    url = f"https://api.crossref.org/works?query={urllib.parse.quote(query_str)}&filter={','.join(filters)}&sort=published&order=desc&rows={max_results}"
    
    papers = []
    try:
        # 尝试正常请求
        response = session.get(url, timeout=30)
        data = response.json()
        for item in data.get('message', {}).get('items', []):
            authors = item.get('author', [])
            first_author = f"{authors[0].get('given', '')} {authors[0].get('family', '')}".strip() if authors else "N/A"
            corr_author = f"{authors[-1].get('given', '')} {authors[-1].get('family', '')}".strip() if authors else "N/A"
            affiliation = authors[0].get('affiliation', [{}])[0].get('name', '未知机构') if (authors and authors[0].get('affiliation')) else "未知机构"

            abs_raw = clean_abstract(item.get('abstract', ''))
            if not abs_raw: abs_raw = "点击链接查看原文。"
            
            papers.append({
                'id': item.get('DOI', ''),
                'title': item.get('title', ['No Title'])[0],
                'url': f"https://doi.org/{item.get('DOI')}",
                'first_author': first_author,
                'corr_author': corr_author,
                'affiliation': affiliation,
                'abs_zh': translate_text(abs_raw),
                'source': item.get('container-title', ['Journal'])[0], 
                'published': str(item.get('created', {}).get('date-parts', [[datetime.now().year]])[0][0])
            })
    except Exception as e:
        print(f"Crossref 出错: {e}")
        # 如果失败，尝试不验证 SSL（仅作为备用）
        try:
            print(f"  尝试备用方式获取 {topic_config['name_zh']}...")
            response = session.get(url, timeout=30, verify=False)
            data = response.json()
            for item in data.get('message', {}).get('items', []):
                authors = item.get('author', [])
                first_author = f"{authors[0].get('given', '')} {authors[0].get('family', '')}".strip() if authors else "N/A"
                corr_author = f"{authors[-1].get('given', '')} {authors[-1].get('family', '')}".strip() if authors else "N/A"
                affiliation = authors[0].get('affiliation', [{}])[0].get('name', '未知机构') if (authors and authors[0].get('affiliation')) else "未知机构"
                abs_raw = clean_abstract(item.get('abstract', ''))
                if not abs_raw: abs_raw = "点击链接查看原文。"
                papers.append({
                    'id': item.get('DOI', ''),
                    'title': item.get('title', ['No Title'])[0],
                    'url': f"https://doi.org/{item.get('DOI')}",
                    'first_author': first_author,
                    'corr_author': corr_author,
                    'affiliation': affiliation,
                    'abs_zh': translate_text(abs_raw),
                    'source': item.get('container-title', ['Journal'])[0],
                    'published': str(item.get('created', {}).get('date-parts', [[datetime.now().year]])[0][0])
                })
            print(f"  备用方式成功获取 {len(papers)} 篇论文")
        except Exception as e2:
            print(f"  备用方式也失败: {e2}")
    return papers

def search_arxiv(topic_config, max_results=5):
    print(f"正在 arXiv 检索 ({topic_config['name_zh']})...")
    query = "+OR+".join([f'all:"{k}"' for k in topic_config['keywords']])
    url = f'http://export.arxiv.org/api/query?search_query={query}&sortBy=submittedDate&sortOrder=descending&max_results={max_results}'
    papers = []
    try:
        feed = feedparser.parse(session.get(url, timeout=30).content)
        for entry in feed.entries:
            papers.append({
                'id': entry.id.split('/')[-1],
                'title': entry.title.replace('\n', ' '),
                'url': entry.id,
                'first_author': entry.authors[0].name if entry.authors else "N/A",
                'corr_author': "N/A",
                'affiliation': "arXiv Preprint",
                'abs_zh': translate_text(clean_abstract(entry.summary)),
                'source': 'arXiv',
                'published': entry.published[:10]
            })
    except Exception as e: print(f"arXiv 出错: {e}")
    return papers

if __name__ == "__main__":
    target_dir = '.'
    
    # 计算日期范围
    now = datetime.now()
    seven_days_ago = (now - timedelta(days=7)).strftime('%Y-%m-%d')
    today_str = now.strftime('%Y-%m-%d')
    date_range_str = f"{seven_days_ago} 至 {today_str}"
    update_time_only = now.strftime('%H:%M')

    for tid, config in TOPICS.items():
        print(f"\n--- 正在更新: {config['name_zh']} ---")
        results = search_crossref(config) + search_arxiv(config)
        results.sort(key=lambda x: str(x.get('published', '')), reverse=True)
        
        with open(os.path.join(target_dir, config['file']), 'w', encoding='utf-8') as f:
            json.dump({
                'last_update': f"{date_range_str} {update_time_only}", 
                'topic_name': config['name_zh'], 
                'papers': results
            }, f, ensure_ascii=False, indent=2)
            
    print(f"\n✅ 地震学周报更新完成！范围: {date_range_str}")
