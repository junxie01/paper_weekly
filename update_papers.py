import requests
import feedparser
import json
import os
import urllib.parse
from datetime import datetime
from deep_translator import GoogleTranslator
from fpdf import FPDF

class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'Weekly Seismology Papers Report (Multi-Source)', 0, 1, 'C')
        self.ln(10)

# ==========================================
# 在这里修改你的关键词和期刊限制
# ==========================================
TOPICS = {
    'cryoseismology': {
        'name': 'Cryoseismology', # 建议 PDF 中使用英文名防止编码错误
        'name_zh': '冰川地震论文',
        'keywords': ['icequake', 'glacier', 'cryoseismology'],
        'journals': ['Journal of Geophysical Research', 'Geophysical Research Letters', 'The Cryosphere'],
        'file': 'data_cryo.json'
    },
    'das': {
        'name': 'DAS Papers',
        'name_zh': 'DAS论文',
        'keywords': ['Distributed Acoustic Sensing', 'DAS seismology'],
        'journals': [],
        'file': 'data_das.json'
    },
    'surface_wave': {
        'name': 'Surface Wave & Imaging',
        'name_zh': '面波与成像',
        'keywords': ['surface wave tomography', 'ambient noise correlation', 'full waveform inversion'],
        'journals': ['Seismological Research Letters', 'Bulletin of the Seismological Society of America'],
        'file': 'data_surface.json'
    }
}

def clean_for_pdf(text):
    """处理字符串以符合 PDF 的 latin-1 编码限制"""
    if not text: return ""
    return str(text).encode('latin-1', 'replace').decode('latin-1')

def translate_text(text, max_len=1500):
    if not text: return "No abstract available"
    try:
        # 如果你正在使用代理，可以在这里指定，或者直接依靠系统环境变量
        translator = GoogleTranslator(source='auto', target='zh-CN')
        return translator.translate(text[:max_len])
    except:
        return "Translation Failed"

def search_crossref(keywords, journals=None, max_results=10):
    print(f"正在 Crossref 搜索关键词: {keywords}...")
    query = " ".join(keywords)
    filters = ["type:journal-article"]
    if journals:
        for j in journals:
            filters.append(f"container-title:{j}")

    filter_str = ",".join(filters)
    url = f"https://api.crossref.org/works?query={urllib.parse.quote(query)}&filter={filter_str}&sort=published&order=desc&rows={max_results}"

    try:
        # 增加超时时间到 30 秒
        response = requests.get(url, timeout=30)
        data = response.json()
        items = data.get('message', {}).get('items', [])

        papers = []
        for item in items:
            title = item.get('title', ['No Title'])[0]
            doi = item.get('DOI')
            url_link = f"https://doi.org/{doi}"
            journal = item.get('container-title', ['Unknown'])[0]

            try:
                date_info = item.get('published-print') or item.get('created') or {}
                date_parts = date_info.get('date-parts', [[None]])
                published_year = str(date_parts[0][0]) if date_parts[0][0] else "N/A"
            except:
                published_year = "N/A"

            papers.append({
                'id': doi,
                'title': title,
                'abstract': f"Published in {journal}. DOI: {doi}",
                'translated_abstract': f"发表于 {journal}。点击链接查看详情。",
                'authors': [a.get('family', '') for a in item.get('author', [])],
                'published': published_year,
                'url': url_link,
                'source': 'Crossref'
            })
        return papers
    except Exception as e:
        print(f"Crossref 搜索出错: {e}")
        return []

def search_arxiv(keywords, max_results=10):
    print(f"正在 arXiv 搜索关键词: {keywords}...")
    search_terms = '+'.join([f'all:"{k}"' for k in keywords])
    url = f'http://export.arxiv.org/api/query?search_query={search_terms}&sortBy=submittedDate&sortOrder=descending&max_results={max_results}'

    try:
        # 增加超时时间并禁用潜在的干扰代理（如果需要）
        response = requests.get(url, timeout=30)
        feed = feedparser.parse(response.content)
        papers = []
        for entry in feed.entries:
            abstract = entry.summary.replace('\n', ' ')
            papers.append({
                'id': entry.id.split('/')[-1],
                'title': entry.title.replace('\n', ' '),
                'abstract': abstract,
                'translated_abstract': translate_text(abstract),
                'authors': [author.name for author in entry.authors],
                'published': entry.published,
                'url': entry.id,
                'source': 'arXiv'
            })
        return papers
    except Exception as e:
        print(f"arXiv 搜索出错: {e}")
        return []

def generate_pdf(all_results, filename='report.pdf'):
    pdf = PDF()
    pdf.add_page()
    for topic_id, papers in all_results.items():
        pdf.set_font("Arial", 'B', 14)
        # 使用 clean_for_pdf 处理专题名
        topic_name = clean_for_pdf(TOPICS[topic_id]['name'])
        pdf.cell(0, 10, f"Topic: {topic_name}", 0, 1)
        pdf.ln(5)

        for p in papers[:8]:
            pdf.set_font("Arial", 'B', 10)
            # 使用 clean_for_pdf 处理标题和来源
            safe_title = clean_for_pdf(p['title'])
            pdf.multi_cell(0, 8, f"[{p['source']}] {safe_title}")

            pdf.set_font("Arial", size=9)
            safe_url = clean_for_pdf(p['url'])
            pdf.cell(0, 6, f"Link: {safe_url}", 0, 1)
            pdf.ln(2)
        pdf.ln(5)

    try:
        pdf.output(filename)
        print(f"✅ PDF 报告已生成: {filename}")
    except Exception as e:
        print(f"❌ PDF 输出失败: {e}")

if __name__ == "__main__":
    all_results = {}
    target_dir = 'frontend'
    os.makedirs(target_dir, exist_ok=True)
    update_time = datetime.now().strftime('%Y-%m-%d %H:%M')

    for topic_id, config in TOPICS.items():
        print(f"\n--- 正在处理: {config['name_zh']} ---")

        published_papers = search_crossref(config['keywords'], config.get('journals'))
        preprint_papers = search_arxiv(config['keywords'])

        combined = published_papers + preprint_papers
        all_results[topic_id] = combined

        # 保存 JSON (网页版可以正常显示中文)
        output = {'last_update': update_time, 'topic_name': config['name_zh'], 'papers': combined}
        with open(os.path.join(target_dir, config['file']), 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

    generate_pdf(all_results)
    print("\n✅ 更新完成！现在你可以运行 bash deploy.sh 推送了。")
