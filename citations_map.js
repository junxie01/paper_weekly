let papers = [];
let mapData = [];
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
    loadPapers('citations');
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
    if (topic === 'citations') {
        window.location.href = 'citations.html';
        return;
    }
    window.location.href = 'index.html';
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
        papers = data.papers || [];
        mapData = data.map_data || [];

        document.getElementById('last-update').textContent = data.last_update || '未知';
        document.getElementById('current-topic-name').textContent = data.topic_name || '文章引用';

        if (data.total_citations !== undefined) {
            document.getElementById('total-citations').textContent = data.total_citations;
            document.getElementById('weekly-citations').textContent = data.weekly_citations;
            document.getElementById('citation-stats').classList.remove('hidden');

            const countries = new Set();
            mapData.forEach(p => {
                if (p.affiliation && p.affiliation !== 'N/A') {
                    countries.add(p.affiliation.split(',').pop().trim());
                }
            });
            document.getElementById('country-count').textContent = countries.size || mapData.length;
        }

        initMap();
        document.getElementById('map-container').classList.remove('hidden');

        renderPapersList();
    } catch (error) {
        console.error('加载论文失败:', error);
        const container = document.getElementById('papers-list');
        container.innerHTML = `
            <div class="empty-state">
                <h2>❌ 该专题暂无数据</h2>
                <p>请运行 python3 update_citations.py 生成最新数据。</p>
            </div>
        `;
    } finally {
        hideLoading();
    }
}

function initMap() {
    if (map) {
        map.remove();
        map = null;
    }

    map = L.map('citation-map').setView([20, 0], 2);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 18
    }).addTo(map);

    mapData.forEach(paper => {
        if (paper.lat && paper.lon) {
            const icon = createMarkerIcon(paper.is_new_this_week);
            const marker = L.marker([paper.lat, paper.lon], { icon: icon });

            const popupContent = `
                <div style="min-width: 200px;">
                    <h4 style="margin: 0 0 10px 0; color: #007bff;">${escapeHtml(paper.title)}</h4>
                    <p><b>👤 ${escapeHtml(paper.author)}</b></p>
                    <p style="font-size: 0.9em; color: #666;">🏢 ${escapeHtml(paper.affiliation)}</p>
                    <p style="font-size: 0.85em;">📅 ${paper.published}</p>
                    <p style="font-size: 0.85em; color: ${paper.is_new_this_week ? '#dc3545' : '#666'};">
                        ${paper.is_new_this_week ? '🆕 本周新增' : '📎 历史引用'}
                    </p>
                    <a href="${paper.url}" target="_blank" style="color: #007bff;">访问原文 →</a>
                </div>
            `;

            marker.bindPopup(popupContent);
            markers.push(marker);
            marker.addTo(map);
        }
    });

    if (markers.length > 0) {
        const group = L.featureGroup(markers);
        map.fitBounds(group.getBounds().pad(0.1));
    }
}

function createMarkerIcon(isNewThisWeek) {
    if (isNewThisWeek) {
        return L.divIcon({
            className: 'custom-marker',
            html: '<div class="marker-pin pulse red"></div>',
            iconSize: [20, 20],
            iconAnchor: [10, 10]
        });
    } else {
        return L.divIcon({
            className: 'custom-marker',
            html: '<div class="marker-pin yellow"></div>',
            iconSize: [15, 15],
            iconAnchor: [7, 7]
        });
    }
}

function renderPapersList() {
    const container = document.getElementById('papers-list');
    const weeklyPapers = papers.filter(p => p.is_new_this_week);
    const historicalPapers = papers.filter(p => !p.is_new_this_week);

    if (papers.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <h2>暂无引用数据</h2>
                <p>如果这是首次初始化，请先运行一次完整引用扫描；之后每周更新会保留历史引用并标记新增引用。</p>
            </div>
        `;
        return;
    }

    let html = '';

    if (weeklyPapers.length > 0) {
        html += `
            <div class="section-header">
                <h2>🆕 本周新增引用 (${weeklyPapers.length})</h2>
            </div>
        `;
        html += weeklyPapers.map(paper => createPaperCard(paper, true)).join('');
    }

    if (historicalPapers.length > 0) {
        html += `
            <div class="section-header" style="margin-top: 40px;">
                <h2>📎 历史引用 (${historicalPapers.length})</h2>
            </div>
        `;
        html += historicalPapers.slice(0, 20).map(paper => createPaperCard(paper, false)).join('');

        if (historicalPapers.length > 20) {
            html += `
                <div class="show-more">
                    <p>显示前 20 条历史引用，共 ${historicalPapers.length} 条</p>
                </div>
            `;
        }
    }

    container.innerHTML = html;
}

function createPaperCard(paper, isNew) {
    const cardClass = isNew ? 'paper-card highlight-card' : 'paper-card';
    const badge = isNew ? '<span class="new-badge">🆕 本周新增</span>' : '';

    return `
        <div class="${cardClass}" onclick="loadPaperDetail('${paper.id}')">
            ${badge}
            <span class="source-tag ${paper.source.toLowerCase()}">${paper.source}</span>
            <h3>${escapeHtml(paper.title)}</h3>
            <div class="paper-meta">
                <span>👤 <b>${escapeHtml(paper.first_author)}</b> (${escapeHtml(paper.affiliation)})</span>
            </div>
            <div class="paper-abstract-preview">${escapeHtml(paper.abs_zh ? paper.abs_zh.substring(0, 150) : "无摘要预览")}...</div>
            <div class="view-detail-btn">查看详细信息 →</div>
        </div>
    `;
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
