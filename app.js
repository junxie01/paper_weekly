let papers = [];
let currentTopic = 'cryo';
let map = null;
let markers = [];

const topicFiles = {
    'cryo': 'data_cryo.json',
    'das': 'data_das.json',
    'surface': 'data_surface.json',
    'imaging': 'data_imaging.json',
    'earthquake': 'data_earthquake.json',
    'ai': 'data_ai.json',
    'citations': 'data_citations.json'
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

        // 处理 citations 的特殊显示
        const citationStats = document.getElementById('citation-stats');
        const citationMap = document.getElementById('citation-map');
        if (topic === 'citations') {
            citationStats.classList.remove('hidden');
            citationMap.classList.add('visible');
            document.getElementById('total-citations').textContent = data.total_citations || 0;
            document.getElementById('weekly-citations').textContent = data.weekly_citations || 0;
            renderCitationMap(data.papers || [], data.weekly_papers || []);
            papers = data.papers || [];
        } else {
            citationStats.classList.add('hidden');
            citationMap.classList.remove('hidden');
            citationMap.classList.remove('visible');
            clearCitationMap();
            papers = data.papers;
        }

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
        const emptyMsg = currentTopic === 'citations'
            ? `<div class="empty-state"><h2>暂无引用数据</h2><p>如果这是首次初始化，请先运行一次完整引用扫描；之后每周更新会保留历史引用并标记新增引用。</p></div>`
            : `<div class="empty-state"><h2>📚 暂无论文</h2><p>目前没有找到相关的论文。</p></div>`;
        container.innerHTML = emptyMsg;
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

        ${paper.cited_paper ? `
        <div class="analysis-section">
            <h3>📌 引用的文章</h3>
            <div class="abs-content">${escapeHtml(paper.cited_paper)}</div>
        </div>` : ''}

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

function renderCitationMap(allPapers, weeklyPapers) {
    const mapContainer = document.getElementById('citation-map');
    const weeklyIds = new Set(weeklyPapers.map(p => p.id));

    if (map) {
        map.remove();
        map = null;
    }
    markers = [];

    map = L.map('citation-map').setView([20, 0], 2);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);

    const hasCoords = allPapers.filter(p => p.coordinates && p.coordinates.lat && p.coordinates.lon);

    if (hasCoords.length === 0) {
        mapContainer.innerHTML = '<div style="height:400px;display:flex;align-items:center;justify-content:center;background:#f5f5f5;border-radius:12px;color:#666;">暂无地理坐标数据</div>';
        return;
    }

    hasCoords.forEach(paper => {
        const isWeekly = weeklyIds.has(paper.id) || paper.is_new_this_week;
        const color = isWeekly ? '#e74c3c' : '#f39c12';
        const radius = isWeekly ? 10 : 6;

        const circle = L.circleMarker([paper.coordinates.lat, paper.coordinates.lon], {
            color: color,
            fillColor: color,
            fillOpacity: 0.6,
            radius: radius,
            weight: 2
        });

        if (isWeekly) {
            circle.setStyle({ className: 'blink-animation' });
        }

        const popupContent = `
            <div class="citation-popup">
                <h4>${escapeHtml(paper.title)}</h4>
                <p><b>${escapeHtml(paper.first_author)}</b></p>
                <p>${escapeHtml(paper.affiliation !== 'N/A' ? paper.affiliation : '未知单位')}</p>
                <p>发表: ${paper.published || '未知'}</p>
                ${isWeekly ? '<p style="color:#e74c3c;font-weight:bold;">🆕 本周新增</p>' : ''}
            </div>
        `;

        circle.bindPopup(popupContent);
        circle.addTo(map);
        markers.push(circle);
    });

    const group = L.featureGroup(markers);
    if (group.getBounds().isValid()) {
        map.fitBounds(group.getBounds().pad(0.1));
    }
}

function clearCitationMap() {
    if (map) {
        map.remove();
        map = null;
    }
    markers = [];
}
