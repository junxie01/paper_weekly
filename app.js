let papers = [];
let currentTopic = 'cryo';

const topicFiles = {
    'cryo': 'data_cryo.json',
    'das': 'data_das.json',
    'surface': 'data_surface.json',
    'imaging': 'data_imaging.json',
    'earthquake': 'data_earthquake.json'
};

document.addEventListener('DOMContentLoaded', () => {
    loadPapers('cryo');
    setupEventListeners();
});

function setupEventListeners() {
    document.getElementById('close-modal').addEventListener('click', closeModal);
    document.getElementById('paper-modal').addEventListener('click', (e) => {
        if (e.target.id === 'paper-modal') {
            closeModal();
        }
    });
}

function switchTopic(topic) {
    if (topic === currentTopic) return;

    // 更新按钮状态
    document.querySelectorAll('.topic-btn').forEach(btn => {
        btn.classList.remove('active');
        if (btn.getAttribute('onclick').includes(`'${topic}'`)) {
            btn.classList.add('active');
        }
    });

    currentTopic = topic;
    loadPapers(topic);
}

async function loadPapers(topic) {
    showLoading();
    const fileName = topicFiles[topic];

    try {
        const response = await fetch(`./${fileName}`);
        if (!response.ok) {
            throw new Error('无法加载该专题的数据文件');
        }
        const data = await response.json();
        papers = data.papers;

        // 更新最后更新时间
        document.getElementById('last-update').textContent = data.last_update || '未知';
        document.getElementById('current-topic-name').textContent = data.topic_name || '专题';

        renderPapersList();
    } catch (error) {
        console.error('加载论文失败:', error);
        const container = document.getElementById('papers-list');
        container.innerHTML = `
            <div class="empty-state">
                <h2>❌ 该专题暂无数据</h2>
                <p>请运行 python3 update_papers.py 生成最新数据。</p>
            </div>
        `;
    } finally {
        hideLoading();
    }
}

function renderPapersList() {
    const container = document.getElementById('papers-list');
    
    if (!papers || papers.length === 0) {
        container.innerHTML = `<div class="empty-state"><h2>📚 暂无论文</h2><p>目前没有找到相关的论文。</p></div>`;
        return;
    }
    
    container.innerHTML = papers.map(paper => `
        <div class="paper-card" onclick="loadPaperDetail('${paper.id}')">
            <span class="source-tag ${paper.source.toLowerCase()}">${paper.source}</span>
            <h3>${escapeHtml(paper.title)}</h3>
            <div class="paper-meta">
                <span>👤 <b>${escapeHtml(paper.first_author)}</b> (${escapeHtml(paper.affiliation)})</span>
            </div>
            <div class="paper-abstract-preview">${escapeHtml(paper.abs_zh ? paper.abs_zh.substring(0, 150) : "无摘要预览")}...</div>
            <div class="view-detail-btn">查看详细信息 &rarr;</div>
        </div>
    `).join('');
}

function loadPaperDetail(paperId) {
    const paper = papers.find(p => p.id === paperId);
    if (paper) {
        showModal(paper);
    }
}

function showModal(paper) {
    document.getElementById('modal-title').textContent = paper.title;
    const modalBody = document.getElementById('modal-body');
    
    modalBody.innerHTML = `
        <div class="modal-grid">
            <div class="analysis-card">
                <h3>👥 作者信息</h3>
                <p><b>第一作者:</b> ${escapeHtml(paper.first_author)}</p>
                <p><b>通讯作者:</b> ${escapeHtml(paper.corr_author)}</p>
                <p><b>单位:</b> ${escapeHtml(paper.affiliation)}</p>
            </div>
        </div>

        <div class="analysis-section">
            <h3>📖 摘要翻译</h3>
            <div class="abs-content">${escapeHtml(paper.abs_zh || "暂无翻译内容")}</div>
        </div>

        <div class="modal-footer">
            <a href="${paper.url}" target="_blank" class="primary-btn">🔗 访问原文链接 (DOI/arXiv)</a>
        </div>
    `;
    
    document.getElementById('paper-modal').classList.remove('hidden');
    document.body.style.overflow = 'hidden';
}

function closeModal() {
    document.getElementById('paper-modal').classList.add('hidden');
    document.body.style.overflow = 'auto';
}

function showLoading() {
    document.getElementById('loading').classList.remove('hidden');
}

function hideLoading() {
    document.getElementById('loading').classList.add('hidden');
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
