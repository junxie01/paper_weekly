import requests
import feedparser
import json
import os
from datetime import datetime
from deep_translator import GoogleTranslator
from fpdf import FPDF

class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'Weekly Seismology Papers Report', 0, 1, 'C')
        self.ln(10)

# 定义不同的专题和关键词
TOPICS = {
    'cryoseismology': {
        'name': '冰川地震论文',
        'keywords': ['icequake', 'glacier', 'seismology', 'cryoseismology'],
        'file': 'data_cryo.json'
    },
    'das': {
        'name': 'DAS论文',
        'keywords': ['Distributed Acoustic Sensing', 'DAS', 'seismology'],
        'file': 'data_das.json'
    },
    'surface_wave': {
        'name': '面波论文',
        'keywords': ['surface wave', 'dispersion', 'ambient noise'],
        'file': 'data_surface.json'
    },
    'imaging': {
        'name': '地震学成像',
        'keywords': ['seismic tomography', 'full waveform inversion', 'imaging'],
        'file': 'data_imaging.json'
    },
    'earthquake': {
        'name': '地震研究',
        'keywords': ['earthquake source', 'tectonics', 'seismicity'],
        'file': 'data_earthquake.json'
    }
}

def search_arxiv(keywords, max_results=15):
    print(f"开始搜索关键词: {keywords}...")
    search_terms = '+'.join([f'all:"{k}"' for k in keywords])
    url = f'http://export.arxiv.org/api/query?search_query={search_terms}&sortBy=submittedDate&sortOrder=descending&max_results={max_results}'

    response = requests.get(url)
    feed = feedparser.parse(response.content)

    papers = []
    translator = GoogleTranslator(source='auto', target='zh-CN')

    for entry in feed.entries:
        abstract = entry.summary.replace('\n', ' ')
        try:
            # 限制翻译长度以加快速度
            translated_abstract = translator.translate(abstract[:1500])
        except:
            translated_abstract = "Translation Failed"

        paper = {
            'id': entry.id.split('/')[-1],
            'title': entry.title.replace('\n', ' '),
            'abstract': abstract,
            'translated_abstract': translated_abstract,
            'authors': [author.name for author in entry.authors],
            'published': entry.published,
            'updated': entry.updated,
            'categories': [tag.term for tag in entry.tags],
            'first_author': entry.authors[0].name if entry.authors else "N/A"
        }
        papers.append(paper)
    return papers

def generate_pdf(all_results, filename='report.pdf'):
    pdf = PDF()
    pdf.add_page()

    for topic_id, papers in all_results.items():
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(0, 10, f"Topic: {TOPICS[topic_id]['name']}", 0, 1)
        pdf.ln(5)

        for p in papers[:5]: # 每个专题取前5篇
            pdf.set_font("Arial", 'B', 10)
            pdf.multi_cell(0, 8, f"- {p['title'].encode('latin-1', 'replace').decode('latin-1')}")
            pdf.set_font("Arial", size=9)
            pdf.cell(0, 6, f"Link: https://arxiv.org/abs/{p['id']}", 0, 1)
            pdf.ln(2)
        pdf.ln(5)
    pdf.output(filename)

if __name__ == "__main__":
    try:
        all_results = {}
        target_dir = 'frontend'
        os.makedirs(target_dir, exist_ok=True)
        update_time = datetime.now().strftime('%Y-%m-%d %H:%M')

        # 循环处理每个专题
        for topic_id, config in TOPICS.items():
            print(f"\n正在处理专题: {config['name']}")
            papers = search_arxiv(config['keywords'])
            all_results[topic_id] = papers

            # 保存各专题的 JSON
            output = {'last_update': update_time, 'topic_name': config['name'], 'papers': papers}
            with open(os.path.join(target_dir, config['file']), 'w', encoding='utf-8') as f:
                json.dump(output, f, ensure_ascii=False, indent=2)

        # 生成合集 PDF
        generate_pdf(all_results)

        # 生成邮件正文
        with open('email_body.txt', 'w', encoding='utf-8') as f:
            f.write(f"地震学多专题论文周报已更新 ({update_time})\n\n")
            f.write("包含专题：\n")
            for config in TOPICS.values():
                f.write(f"- {config['name']}\n")
            f.write(f"\n在线查看: https://www.seis-jun.xyz/cryoseismology_papers/frontend/\n")
            f.write("详细内容请查看附件 PDF 或访问网站。")

    except Exception as e:
        print(f"脚本运行出错: {e}")
