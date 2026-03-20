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
                <p>可能该专题在本周尚未更新，或关键词未搜到结果。</p>
            </div>
        `;
    } finally {
        hideLoading();
    }
}

function renderPapersList() {
    const container = document.getElementById('papers-list');
    
    if (!papers || papers.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <h2>📚 暂无论文</h2>
                <p>目前没有找到相关的论文。</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = papers.map(paper => `
        <div class="paper-card" onclick="loadPaperDetail('${paper.id}')">
            <h3>${escapeHtml(paper.title)}</h3>
            <div class="paper-meta">
                <span>📅 ${formatDate(paper.published)}</span>
                <span>👥 ${paper.authors.length} 位作者</span>
            </div>
            <div class="paper-authors">
                ${paper.authors.slice(0, 3).map(a => escapeHtml(a)).join(', ')}${paper.authors.length > 3 ? ' 等' : ''}
            </div>
            <div class="paper-abstract">${escapeHtml(paper.translated_abstract ? paper.translated_abstract.substring(0, 200) : paper.abstract.substring(0, 200))}...</div>
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
        <div class="analysis-section">
            <h3>📄 摘要（中文翻译）</h3>
            <p>${escapeHtml(paper.translated_abstract || '暂无翻译')}</p>
        </div>
        <div class="analysis-section">
            <h3>📋 所有作者</h3>
            <p>${paper.authors.map(a => escapeHtml(a)).join('; ')}</p>
        </div>
        <div class="analysis-section">
            <h3>🔗 原文链接</h3>
            <p><a href="https://arxiv.org/abs/${paper.id}" target="_blank" rel="noopener noreferrer">https://arxiv.org/abs/${paper.id}</a></p>
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

function formatDate(dateStr) {
    if (!dateStr) return 'N/A';
    const date = new Date(dateStr);
    return date.toLocaleDateString('zh-CN', {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    });
}
