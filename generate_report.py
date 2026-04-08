#!/usr/bin/env python3
"""
生成论文周报 PDF 和邮件内容
文件名格式: paper_report_YYYYMMDD_YYYYMMDD.pdf
"""

import json
import os
from datetime import datetime, timedelta
from fpdf import FPDF

# 计算日期范围（最近7天）
end_date = datetime.now()
start_date = end_date - timedelta(days=7)
start_str = start_date.strftime('%Y%m%d')
end_str = end_date.strftime('%Y%m%d')
date_range_display = f"{start_date.strftime('%Y%m%d')}-{end_date.strftime('%Y%m%d')}"

# 专题配置文件
TOPICS = [
    ('data_cryo.json', 'Cryoseismology'),
    ('data_das.json', 'DAS'),
    ('data_surface.json', 'Surface Wave'),
    ('data_imaging.json', 'Seismic Imaging'),
    ('data_earthquake.json', 'Earthquake Research'),
    ('data_ai.json', 'AI')
]

class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, f'Paper Weekly Report ({date_range_display})', 0, 1, 'C')
        self.ln(5)
    
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

def load_papers():
    """加载所有专题的论文数据"""
    all_papers = []
    for filename, topic_name in TOPICS:
        if os.path.exists(filename):
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for paper in data.get('papers', []):
                        paper['topic'] = topic_name
                        all_papers.append(paper)
            except Exception as e:
                print(f"Error loading {filename}: {e}")
    return all_papers

def generate_pdf(papers, output_file):
    """生成 PDF 报告"""
    pdf = PDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # 尝试使用支持中文的字体
    try:
        pdf.add_font('DejaVu', '', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', uni=True)
        pdf.add_font('DejaVu', 'B', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', uni=True)
        font_name = 'DejaVu'
    except:
        font_name = 'Arial'
    
    if not papers:
        pdf.set_font(font_name, '', 12)
        pdf.cell(0, 10, 'No papers found for this period.', 0, 1)
        pdf.output(output_file)
        return
    
    # 按专题分组
    papers_by_topic = {}
    for paper in papers:
        topic = paper.get('topic', 'Other')
        if topic not in papers_by_topic:
            papers_by_topic[topic] = []
        papers_by_topic[topic].append(paper)
    
    for topic, topic_papers in papers_by_topic.items():
        pdf.set_font(font_name, 'B', 14)
        pdf.cell(0, 10, f'[{topic}]', 0, 1)
        pdf.ln(2)
        
        for i, paper in enumerate(topic_papers[:5], 1):  # 每个专题最多显示5篇
            pdf.set_font(font_name, 'B', 11)
            title = paper.get('title', 'No Title')[:80]
            pdf.multi_cell(0, 6, f"{i}. {title}")
            
            pdf.set_font(font_name, '', 10)
            authors = paper.get('first_author', 'N/A')
            if paper.get('corr_author') and paper.get('corr_author') != 'N/A':
                authors += f", {paper.get('corr_author')}"
            
            source = paper.get('source', 'Unknown Journal')
            pdf.cell(0, 5, f"Authors: {authors}", 0, 1)
            pdf.cell(0, 5, f"Journal: {source}", 0, 1)
            
            # 摘要（前200字符）- 只使用英文摘要或跳过中文
            abs_text = paper.get('abstract', '') or paper.get('abs_zh', '')
            if abs_text and abs_text != '无摘要详情' and len(abs_text) > 10:
                pdf.set_font(font_name, '', 9)
                # 只使用 ASCII 字符
                abs_clean = abs_text[:200].encode('ascii', 'ignore').decode('ascii')
                if abs_clean:
                    pdf.multi_cell(0, 5, f"Abstract: {abs_clean}...")
            
            pdf.ln(3)
        
        pdf.ln(5)
    
    pdf.output(output_file)
    print(f"PDF generated: {output_file}")

if __name__ == "__main__":
    papers = load_papers()
    
    # 生成带日期范围的文件名
    pdf_filename = f"paper_report_{start_str}_{end_str}.pdf"
    
    generate_pdf(papers, pdf_filename)
    
    print(f"\nReport generated!")
    print(f"PDF file: {pdf_filename}")
    print(f"日期范围: {date_range_display}")
