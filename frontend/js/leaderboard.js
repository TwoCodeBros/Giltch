/**
 * leaderboard.js
 * Leaderboard Logic
 */

const Leaderboard = {
    // Data
    data: [],
    selectedLevel: 1,
    totalQuestions: 0,

    async init() {
        this.setupSearch();
        this.setupLevelSelect();
        await this.loadData();

        // Auto-refresh
        setInterval(() => this.loadData(), 5000);
    },

    setupLevelSelect() {
        const select = document.getElementById('level-select');
        if (!select) return;

        // Populate Levels (assuming 5 for now, or dynamic?)
        // Let's hardcode 1 to 5 as per "Level 1, Level 2, etc."
        let html = '';
        for (let i = 1; i <= 5; i++) {
            html += `<option value="${i}">Level ${i}</option>`;
        }
        select.innerHTML = html;

        // Restore prev selection if exists
        const stored = localStorage.getItem('lb_level');
        if (stored) {
            this.selectedLevel = parseInt(stored);
            select.value = this.selectedLevel;
        }

        select.addEventListener('change', (e) => {
            this.selectedLevel = parseInt(e.target.value);
            localStorage.setItem('lb_level', this.selectedLevel);
            this.loadData();
        });
    },

    async loadData() {
        try {
            const data = await API.request(`/leaderboard/?level=${this.selectedLevel}`);
            this.data = data.leaderboard || [];
            this.totalQuestions = data.total_questions || 0;
            this.render(document.getElementById('search-input').value);

            // Update timestamp
            const now = new Date();
            document.getElementById('last-updated').textContent = now.toLocaleTimeString();
        } catch (e) {
            console.error(e);
        }
    },

    render(filter = '') {
        const tbody = document.getElementById('lb-body');
        if (!tbody) return;

        // Data is already sorted by backend
        let displayData = [...this.data];

        if (filter) {
            const f = filter.toLowerCase();
            displayData = displayData.filter(p =>
                p.name.toLowerCase().includes(f) ||
                p.id.toLowerCase().includes(f)
            );
        }

        tbody.innerHTML = displayData.map((p) => {
            let rowClass = 'lb-row';
            if (p.rank <= 3) rowClass += ` rank-${p.rank}`;

            return `
                <tr class="${rowClass}">
                    <td>
                        <div class="rank-badge">${p.rank}</div>
                    </td>
                    <td>
                        <div style="font-weight: 600;">${p.name}</div>
                        <div style="font-size: 0.75rem; color: var(--text-tertiary); font-family: var(--font-mono);">${p.id}</div>
                    </td>
                    <td>
                        <div style="font-size: 0.85rem; color: var(--text-secondary);">${p.department || '-'}</div>
                        <div style="font-size: 0.75rem; color: var(--text-tertiary);">${p.college || '-'}</div>
                    </td>
                    <td class="score-cell">${p.score}</td>
                    <td style="font-family: var(--font-mono);">${p.time}</td>
                    <td>
                        <span class="badge badge-success">${p.solved || 0}/${this.totalQuestions || '-'}</span>
                    </td>
                </tr>
            `;
        }).join('');
    },

    setupSearch() {
        const input = document.getElementById('search-input');
        if (input) {
            input.addEventListener('input', (e) => this.render(e.target.value));
        }
    },

    downloadReport() {
        window.open(`${API.BASE_URL}/leaderboard/report?level=${this.selectedLevel}&format=csv`, '_blank');
    },

    logout() {
        if (confirm('Logout from Leaderboard?')) {
            localStorage.removeItem('leader_token');
            localStorage.removeItem('leader_info');
            window.location.href = 'leader_login.html';
        }
    }
};

document.addEventListener('DOMContentLoaded', () => {
    Leaderboard.init();
});
