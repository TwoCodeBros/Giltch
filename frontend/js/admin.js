/**
 * admin.js
 * Admin Dashboard Logic with Real API Integration
 */

const Admin = {
    // State
    currentView: 'dashboard',
    socket: null,
    activeContestId: null,

    init() {
        this.bindNavigation();

        // Check if logged in
        if (localStorage.getItem('admin_token')) {
            this.initSocketIO();
            this.loadDashboard(); // Default view is Dashboard
            this.toggleAdminView(true); // Show Dashboard
        } else {
            // Ensure Login is shown
            this.toggleAdminView(false);
        }

        // Auto-refresh stats occasionally
        setInterval(() => {
            if (this.currentView === 'dashboard' && this.activeContestId && localStorage.getItem('admin_token')) {
                this.updateDashboardStats();
            }
        }, 5000);
    },

    toggleAdminView(showDashboard) {
        const login = document.getElementById('admin-login');
        const dash = document.getElementById('admin-dashboard');
        if (showDashboard) {
            if (login) login.style.display = 'none';
            if (dash) dash.style.display = 'flex'; // sidebar layout
        } else {
            if (login) login.style.display = 'flex';
            if (dash) dash.style.display = 'none';
        }
    },

    initSocketIO() {
        // Connect to Socket.IO server (using current host)
        this.socket = io();

        // Listen for contest events
        this.socket.on('contest:started', (data) => {
            console.log('Contest started:', data);
            this.showNotification(`Contest "${data.title || 'Marathon'}" has started!`, 'success');
            if (this.currentView === 'dashboard') this.loadDashboard();
        });

        this.socket.on('contest:paused', (data) => {
            console.log('Contest paused:', data);
            this.showNotification('Contest has been paused', 'warning');
            if (this.currentView === 'dashboard') this.loadDashboard();
        });

        this.socket.on('contest:ended', (data) => {
            console.log('Contest ended:', data);
            this.showNotification('Contest has ended', 'info');
            if (this.currentView === 'dashboard') this.loadDashboard();
        });

        // Level Status Events
        this.socket.on('contest:updated', (data) => {
            console.log('Contest updated:', data);
            if (this.currentView === 'dashboard') this.loadDashboard();
        });

        this.socket.on('level:activated', (data) => {
            this.showNotification(`Level ${data.level} Live!`, 'success');
            if (this.currentView === 'dashboard') this.loadDashboard();
        });

        this.socket.on('level:completed', (data) => {
            this.showNotification(`Level ${data.level} Completed`, 'success');
            if (this.currentView === 'dashboard') this.loadDashboard();
        });

        this.socket.on('level:paused', (data) => {
            this.showNotification(`Level ${data.level} Paused`, 'warning');
            if (this.currentView === 'dashboard') this.loadDashboard();
        });

        this.socket.on('participant:joined', (data) => {
            this.addActivityFeedItem(`${data.name} joined the contest`, 'join');
            if (this.currentView === 'dashboard') this.updateDashboardStats();
        });

        this.socket.on('participant:submitted', (data) => {
            this.addActivityFeedItem(`${data.name || data.participant_id} submitted solution for ${data.question}`, 'submit');
            this.updateDashboardStats();
        });

        // New Participant Level Events
        this.socket.on('participant:started_level', (data) => {
            this.addActivityFeedItem(`${data.participant_id} started Level ${data.level}`, 'join');
            this.updateDashboardStats();
        });

        this.socket.on('participant:level_start', (data) => {
            // Redundant handler if name differs, catching both
            this.updateDashboardStats();
        });

        this.socket.on('participant:level_complete', (data) => {
            this.addActivityFeedItem(`${data.user_id} completed Level ${data.level}`, 'success');
            this.updateDashboardStats();
        });

        // GENERIC STATS UPDATE (Counters)
        this.socket.on('admin:stats_update', () => {
            this.updateDashboardStats();
        });

        this.socket.on('contest:stats_update', () => {
            this.updateDashboardStats();
        });

        // PROCTORING LIVE UPDATES
        this.socket.on('proctoring:violation', (data) => {
            this.addActivityFeedItem(`${data.participant_id}: ${data.violation_type}`, 'violation');
            this.updateDashboardStats(); // Update violations counter
            // Also refresh proctoring view if active
            if (this.currentView === 'proctoring') {
                this.refreshProctoringData(); // Assumed function if viewing proctoring
            }
        });

        this.socket.on('proctoring:disqualified', (data) => {
            this.addActivityFeedItem(`${data.participant_id} DISQUALIFIED: ${data.reason}`, 'violation');
            this.updateDashboardStats();
        });
    },

    bindNavigation() {
        document.querySelectorAll('.menu-item').forEach(item => {
            item.addEventListener('click', (e) => {
                // Determine view from text content or data attribute
                const text = item.innerText.trim().toLowerCase(); // innerText better for visible text
                let view = 'dashboard';

                if (text.includes('dashboard')) view = 'dashboard';
                else if (text.includes('participants')) view = 'participants';
                else if (text.includes('questions')) view = 'questions';
                else if (text.includes('proctoring')) view = 'proctoring';
                else if (text.includes('leaders')) view = 'leaders';
                else if (text.includes('pending')) view = 'pending_admins';
                else if (text.includes('logout')) {
                    this.logout();
                    return;
                }

                this.switchView(view);

                // Active class
                document.querySelectorAll('.menu-item').forEach(i => i.classList.remove('active'));
                item.classList.add('active');
            });
        });
    },

    switchView(view) {
        this.currentView = view;
        const main = document.querySelector('.admin-main');

        // Show Loading State
        main.innerHTML = `<div style="padding: 2rem; text-align: center;"><h2><i class="fa-solid fa-spinner fa-spin"></i> Loading...</h2></div>`;

        // Slight delay to prevent flickering if fast, or just call directly
        if (view === 'dashboard') this.loadDashboard();
        else if (view === 'participants') this.loadParticipantsView();
        else if (view === 'questions') this.loadQuestionsView();
        else if (view === 'proctoring') this.loadProctoringView();
        else if (view === 'leaders') this.loadLeadersView();
        else if (view === 'pending_admins') this.loadPendingAdminsView();
        else main.innerHTML = `<h1>${view.charAt(0).toUpperCase() + view.slice(1)}</h1><p>Module under construction.</p>`;
    },

    // ================= CONTEST CONTROL (WIZARD) =================
    async loadContestView() {
        // In a real app, you might fetch existing contests to list them first.
        // For this task, we go straight to "Create Contest" wizard or List view.
        // Let's implement the List View with a "Create" button that opens the Wizard.
        try {
            const data = await API.request('/contest'); // Get list
            const contests = data ? (data.contests || []) : [];

            const html = `
                <div class="admin-header">
                    <h1>Contest Management</h1>
                    <button class="btn btn-primary" onclick="Admin.renderContestWizard()">
                        <i class="fa-solid fa-plus"></i> New Contest
                    </button>
                </div>

                <div class="bg-white rounded-xl shadow-sm" style="background: white; border-radius: var(--radius-xl); padding: var(--space-6);">
                    <table class="admin-table">
                        <thead>
                            <tr>
                                <th>Title</th>
                                <th>Start Time</th>
                                <th>Status</th>
                                <th>Action</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${contests.length > 0 ? contests.map(c => `
                            <tr>
                                <td>${c.title}</td>
                                <td>${new Date(c.start_time).toLocaleString()}</td>
                                <td><span class="badge badge-${c.status === 'live' ? 'success' : 'secondary'}">${c.status}</span></td>
                                <td>
                                    <button class="btn btn-secondary" onclick="Admin.loadContestDetail('${c.id}')">Manage</button>
                                </td>
                            </tr>
                            `).join('') : '<tr><td colspan="4" style="text-align:center; padding: 2rem;">No contests found. Create one!</td></tr>'}
                        </tbody>
                    </table>
                </div>
            `;
            document.querySelector('.admin-main').innerHTML = html;
        } catch (e) {
            document.querySelector('.admin-main').innerHTML = `<h2 style="color:red">Error loading contests: ${e.message}</h2>`;
        }
    },

    renderContestWizard() {
        const html = `
            <div class="admin-header">
                <h1>Create New Contest</h1>
                <button class="btn btn-secondary" onclick="Admin.loadContestView()">Back to List</button>
            </div>
            
            <div class="glass-card" style="background:white; padding: 2rem; max-width: 800px; margin: 0 auto; color: black;">
                <!-- Stepper -->
                <div class="steps-container" style="display:flex; justify-content:space-between; margin-bottom: 2rem; border-bottom: 1px solid #eee; padding-bottom: 1rem;">
                    <div class="step active" id="step-ind-1">1. Details</div>
                    <div class="step" id="step-ind-2">2. Description</div>
                    <div class="step" id="step-ind-3">3. Settings</div>
                </div>

                <form id="contest-form" onsubmit="event.preventDefault();">
                    <!-- Step 1: Basic Details -->
                    <div class="step-content" id="step-1">
                        <div class="form-group" style="margin-bottom: 1rem;">
                            <label>Contest Title</label>
                            <input type="text" class="input" id="c-title" style="width:100%" required>
                        </div>
                        <div class="form-group" style="margin-bottom: 1rem; display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
                            <div>
                                <label>Start Time</label>
                                <input type="datetime-local" class="input" id="c-start" style="width:100%" required>
                            </div>
                            <div>
                                <label>End Time</label>
                                <input type="datetime-local" class="input" id="c-end" style="width:100%" required>
                            </div>
                        </div>
                         <div style="text-align: right;">
                            <button class="btn btn-primary" onclick="Admin.wizardNext(2)">Next <i class="fa-solid fa-arrow-right"></i></button>
                        </div>
                    </div>

                    <!-- Step 2: Description -->
                    <div class="step-content" id="step-2" style="display:none;">
                        <div class="form-group" style="margin-bottom: 1rem;">
                            <label>Description</label>
                            <div id="editor-container" style="height: 200px; background: white;"></div>
                        </div>
                        <div style="display:flex; justify-content: space-between;">
                            <button class="btn btn-secondary" onclick="Admin.wizardNext(1)"><i class="fa-solid fa-arrow-left"></i> Back</button>
                            <button class="btn btn-primary" onclick="Admin.wizardNext(3)">Next <i class="fa-solid fa-arrow-right"></i></button>
                        </div>
                    </div>

                    <!-- Step 3: Settings & Save -->
                    <div class="step-content" id="step-3" style="display:none;">
                         <div class="form-group" style="margin-bottom: 1rem;">
                            <label>Scoring Mode</label>
                            <select id="c-scoring" class="input" style="width:100%">
                                <option value="standard">Standard (Points per Question)</option>
                                <option value="weighted">Weighted (Difficulty based)</option>
                            </select>
                        </div>
                        <div class="form-group" style="margin-bottom: 1rem;">
                             <label style="display:flex; align-items:center; gap: 10px;">
                                <input type="checkbox" id="c-proctoring" checked> Enable Proctoring
                             </label>
                        </div>
                        <div style="display:flex; justify-content: space-between;">
                            <button class="btn btn-secondary" onclick="Admin.wizardNext(2)"><i class="fa-solid fa-arrow-left"></i> Back</button>
                            <button class="btn btn-primary" style="background: var(--success);" onclick="Admin.submitContest()">Create Contest <i class="fa-solid fa-check"></i></button>
                        </div>
                    </div>
                </form>
            </div>
        `;
        document.querySelector('.admin-main').innerHTML = html;

        // Init Quill
        setTimeout(() => {
            this.quill = new Quill('#editor-container', {
                theme: 'snow'
            });
        }, 100);
    },

    wizardNext(step) {
        // Hide all steps
        [1, 2, 3].forEach(i => {
            document.getElementById(`step-${i}`).style.display = 'none';
            document.getElementById(`step-ind-${i}`).style.fontWeight = 'normal';
            document.getElementById(`step-ind-${i}`).style.color = 'var(--text-secondary)';
        });

        // Show target
        document.getElementById(`step-${step}`).style.display = 'block';
        const ind = document.getElementById(`step-ind-${step}`);
        ind.style.fontWeight = 'bold';
        ind.style.color = 'var(--primary-600)';
    },

    async submitContest() {
        const title = document.getElementById('c-title').value;
        const start = document.getElementById('c-start').value;
        const end = document.getElementById('c-end').value;

        if (!title || !start || !end) return alert("Please fill details in Step 1");

        const description = this.quill.root.innerHTML;
        const scoring = document.getElementById('c-scoring').value;

        // Calculate duration logic if needed
        const payload = {
            title,
            description,
            start_time: new Date(start).toISOString(),
            end_time: new Date(end).toISOString(),
            status: 'draft',
            scoring_config: { mode: scoring }
        };

        try {
            const res = await API.request('/contest/', 'POST', payload);
            if (res && res.success) {
                alert("Contest Created Successfully!");
                this.loadContestView();
            } else {
                alert("Failed to create contest");
            }
        } catch (e) {
            console.error(e);
            alert("Error creating contest");
        }
    },

    // ================= CONTEST DETAIL & ROUNDS =================
    async loadContestDetail(contestId) {
        this.currentView = 'contest-detail';
        this.activeContestId = contestId;

        const main = document.querySelector('.admin-main');
        main.innerHTML = `<div style="padding: 2rem; text-align: center;"><h2><i class="fa-solid fa-spinner fa-spin"></i> Loading Details...</h2></div>`;

        try {
            // Fetch Contest and Rounds
            const cRes = await API.request(`/contest/${contestId}`);
            const contest = cRes.contest;

            const rRes = await API.request(`/contest/${contestId}/rounds`);
            const rounds = rRes.rounds || [];

            const html = `
                <div class="admin-header">
                    <div>
                        <h1>${contest.title} <span class="badge badge-secondary" style="font-size:0.5em; vertical-align:middle">${contest.status}</span>
                            <button class="btn btn-sm btn-secondary" style="margin-left: 1rem;" onclick="Admin.editContestSettings('${contest.id}')"><i class="fa-solid fa-pen"></i> Edit</button>
                        </h1>
                        <p style="color: var(--text-secondary);">Manage Rounds & Questions</p>
                    </div>
                    <button class="btn btn-secondary" onclick="Admin.loadContestView()"><i class="fa-solid fa-arrow-left"></i> Back</button>
                </div>
                
                <div style="display: grid; grid-template-columns: 1fr 2fr; gap: 2rem;">
                    <!-- Rounds List -->
                    <div>
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 1rem;">
                            <h3>Rounds</h3>
                            <button class="btn btn-sm btn-primary" onclick="Admin.addRound('${contestId}')"><i class="fa-solid fa-plus"></i> Add</button>
                        </div>
                        <div id="rounds-list" class="list-group">
                            ${rounds.map(r => `
                                <div class="list-item" data-id="${r.id}" onclick="Admin.loadRoundDetail('${contestId}', '${r.id}')" style="background:white; padding:1rem; margin-bottom:0.5rem; border-radius:8px; border:1px solid #eee; cursor:pointer; display:flex; justify-content:space-between; align-items:center;">
                                    <div>
                                        <strong>${r.title}</strong><br>
                                        <small class="text-secondary"><i class="fa-regular fa-clock"></i> ${r.time_limit} mins &bull; <i class="fa-solid fa-code"></i> ${r.allowed_language || 'python'}</small>
                                    </div>
                                    <div style="display:flex; gap:5px;">
                                        <button class="btn-icon" title="Configure Round" onclick="event.stopPropagation(); Admin.editRoundSettings('${contestId}', '${r.id}', '${r.round_number || r.id.replace('level_', '')}', '${r.time_limit}', '${r.allowed_language || 'python'}')">
                                            <i class="fa-solid fa-cog" style="color:var(--primary-600)"></i>
                                        </button>
                                        <button class="btn-icon" title="Delete Round" onclick="event.stopPropagation(); Admin.deleteRound('${contestId}', '${r.id}')">
                                            <i class="fa-solid fa-trash" style="color:var(--danger)"></i>
                                        </button>
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                         ${rounds.length === 0 ? '<p style="color:gray">No rounds yet.</p>' : ''}
                    </div>
                    
                    <!-- Detail / Question Assignment Area -->
                    <div id="round-detail-area" style="background: white; padding: 2rem; border-radius: 1rem; border: 1px solid #eee; min-height: 400px; display:flex; flex-direction:column; color: #333;">
                        <div style="text-align:center; color:#888; margin-top: 100px;">
                            <i class="fa-solid fa-arrow-left"></i> Select a round to manage its questions
                        </div>
                    </div>
                </div>
            `;
            main.innerHTML = html;

            // Init Sortable
            const el = document.getElementById('rounds-list');
            if (el) {
                new Sortable(el, {
                    animation: 150,
                    onEnd: function (evt) {
                        Admin.saveRoundOrder(contestId);
                    }
                });
            }
        } catch (e) {
            main.innerHTML = `<h2 style="color:red">Error: ${e.message}</h2>`;
        }
    },

    async addRound(contestId) {
        const title = prompt("Round Title:");
        if (!title) return;

        await API.request(`/contest/${contestId}/rounds`, 'POST', {
            title: title,
            sequence_order: 999, // Backend should handle
            time_limit: 60
        });
        this.loadContestDetail(contestId);
    },

    async deleteRound(contestId, roundId) {
        if (confirm("Delete this round?")) {
            await API.request(`/contest/${contestId}/rounds/${roundId}`, 'DELETE');
            this.loadContestDetail(contestId);
        }
    },

    editRoundSettings(contestId, roundId, roundNum, duration, lang) {
        // Create Modal for Round Configuration
        const modalHtml = `
            <div class="modal-overlay" id="round-edit-modal" style="display:flex; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.5); z-index:9000; justify-content:center; align-items:center;">
                <div style="background:white; padding:2rem; border-radius:12px; width:500px; box-shadow:0 10px 25px rgba(0,0,0,0.2);">
                    <h3 style="margin-top:0;">Edit Level ${roundNum} Configuration</h3>
                    
                    <div style="display:grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-top:1.5rem;">
                        <div>
                            <label style="font-weight:600; font-size:0.9rem;">Time Duration (Minutes)</label>
                            <input type="number" id="edit-r-time" class="input" style="width:100%; margin-top:0.5rem;" value="${duration}">
                        </div>
                        <div>
                            <label style="font-weight:600; font-size:0.9rem;">Allowed Language</label>
                            <select id="edit-r-lang" class="input" style="width:100%; margin-top:0.5rem;">
                                <option value="python" ${lang === 'python' ? 'selected' : ''}>Python</option>
                                <option value="javascript" ${lang === 'javascript' ? 'selected' : ''}>JavaScript</option>
                                <option value="c" ${lang === 'c' ? 'selected' : ''}>C</option>
                                <option value="cpp" ${lang === 'cpp' ? 'selected' : ''}>C++</option>
                                <option value="java" ${lang === 'java' ? 'selected' : ''}>Java</option>
                            </select>
                        </div>
                    </div>

                    <div style="margin-top: 2rem; display:flex; justify-content:flex-end; gap:10px;">
                        <button class="btn btn-secondary" onclick="document.getElementById('round-edit-modal').remove()">Cancel</button>
                        <button class="btn btn-primary" onclick="Admin.saveRoundSettings('${contestId}', '${roundNum}')">Save Changes</button>
                    </div>
                </div>
            </div>
        `;
        document.body.insertAdjacentHTML('beforeend', modalHtml);
    },

    async saveRoundSettings(contestId, roundNum) {
        const duration = document.getElementById('edit-r-time').value;
        const lang = document.getElementById('edit-r-lang').value;

        try {
            await API.request(`/contest/${contestId}/rounds/${roundNum}`, 'PUT', {
                time_limit: parseInt(duration),
                allowed_language: lang
            });
            document.getElementById('round-edit-modal').remove();
            Admin.showNotification("Round Configuration Saved", "success");
            this.loadContestDetail(contestId); // Refresh list
        } catch (e) {
            console.error(e);
            alert("Error saving configuration: " + e.message);
        }
    },

    async saveRoundOrder(contestId) {
        const items = document.querySelectorAll('#rounds-list .list-item');
        const orderMap = {};
        items.forEach((item, index) => {
            orderMap[item.getAttribute('data-id')] = index;
        });

        await API.request(`/contest/${contestId}/rounds/reorder`, 'PATCH', orderMap);
    },

    async loadRoundDetail(contestId, roundId) {
        const area = document.getElementById('round-detail-area');
        area.innerHTML = `<p>Loading round questions...</p>`;

        try {
            // Fetch All Questions (Bank)
            const allQRes = await API.request('/contest/questions');
            const allQuestions = allQRes.questions || [];

            // Fetch Assigned Questions
            const assignedRes = await API.request(`/contest/${contestId}/rounds/${roundId}/questions`);
            const assignedQuestions = assignedRes.questions || [];
            const assignedIds = new Set(assignedQuestions.map(q => q.id));

            // Filter bank: remove already assigned
            const bankQuestions = allQuestions.filter(q => !assignedIds.has(q.id));

            const html = `
                <h3>Manage Questions for Round</h3>
                <div style="display:grid; grid-template-columns: 1fr 1fr; gap: 1rem; height: 100%;">
                    
                    <!-- Bank -->
                    <div style="border: 1px solid #eee; padding: 1rem; border-radius:8px;">
                        <h4>Question Bank</h4>
                        <div id="q-bank-list" class="list-group" style="min-height: 200px;">
                             ${bankQuestions.map(q => `
                                 <div class="list-item" data-id="${q.id}" style="padding:0.5rem; border:1px solid #eee; margin-bottom:5px; background:#f9f9f9; cursor:move;">
                                    ${q.title} <span class="badge badge-secondary" style="font-size:0.6em">${q.difficulty}</span>
                                 </div>
                             `).join('')}
                        </div>
                    </div>

                    <!-- Assigned -->
                    <div style="border: 1px solid #eee; padding: 1rem; border-radius:8px; background: #f0f7ff;">
                        <h4>Assigned to Round</h4>
                        <div id="q-assigned-list" class="list-group" style="min-height: 200px;">
                            ${assignedQuestions.map(q => `
                                 <div class="list-item" data-id="${q.id}" style="padding:0.5rem; border:1px solid #eee; margin-bottom:5px; background:white; cursor:move; display:flex; justify-content:space-between;">
                                    <span>${q.title}</span>
                                    <i class="fa-solid fa-times" style="color:red; cursor:pointer;" onclick="Admin.unassignQuestion('${contestId}', '${roundId}', '${q.id}')"></i>
                                 </div>
                            `).join('')}
                        </div>
                    </div>
                </div>
            `;
            area.innerHTML = html;

            // Init Drag and Drop
            new Sortable(document.getElementById('q-bank-list'), {
                group: 'questions',
                animation: 150,
                sort: false
            });

            new Sortable(document.getElementById('q-assigned-list'), {
                group: 'questions',
                animation: 150,
                onAdd: function (evt) {
                    const qId = evt.item.getAttribute('data-id');
                    Admin.assignQuestion(contestId, roundId, qId);
                }
            });
        } catch (e) {
            area.innerHTML = `<p style="color:red">Error: ${e.message}</p>`;
        }
    },

    async assignQuestion(contestId, roundId, questionId) {
        try {
            await API.request(`/contest/${contestId}/rounds/${roundId}/questions`, 'POST', { question_id: questionId });
            // Refresh to ensure Sync
            this.loadRoundDetail(contestId, roundId);
        } catch (e) {
            console.error(e);
            alert("Failed to assign question");
            this.loadRoundDetail(contestId, roundId); // Revert UI
        }
    },

    async unassignQuestion(contestId, roundId, questionId) {
        if (confirm("Remove question from this round?")) {
            try {
                await API.request(`/contest/${contestId}/rounds/${roundId}/questions/${questionId}`, 'DELETE');
                this.loadRoundDetail(contestId, roundId);
            } catch (e) {
                console.error(e);
            }
        }
    },

    async editContestSettings(contestId) {
        try {
            const cRes = await API.request(`/contest/${contestId}`);
            const c = cRes.contest;

            // Simple Prompt-based edit for now or a modal
            // Let's use a cleaner approach: a temporary form injection
            const modalHtml = `
                <div class="modal-overlay" id="edit-modal" style="display:flex; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.5); z-index:9000; justify-content:center; align-items:center;">
                    <div style="background:white; padding:2rem; border-radius:8px; width:400px; box-shadow:0 4px 12px rgba(0,0,0,0.2);">
                        <h3>Edit Contest Settings</h3>
                        <label>Title</label>
                        <input type="text" id="edit-c-title" class="input" style="width:100%; margin-bottom:1rem;" value="${c.title}">
                        
                        <label>Start Time</label>
                        <input type="datetime-local" id="edit-c-start" class="input" style="width:100%; margin-bottom:1rem;" value="${c.start_time.slice(0, 16)}">
                        
                        <label>End Time</label>
                        <input type="datetime-local" id="edit-c-end" class="input" style="width:100%; margin-bottom:1rem;" value="${c.end_time.slice(0, 16)}">
                        
                        <div style="text-align:right; gap:10px;">
                            <button class="btn btn-secondary" onclick="document.getElementById('edit-modal').remove()">Cancel</button>
                            <button class="btn btn-primary" onclick="Admin.saveContestSettings('${contestId}')">Save</button>
                        </div>
                    </div>
                </div>
             `;
            document.body.insertAdjacentHTML('beforeend', modalHtml);

        } catch (e) {
            alert('Error loading settings');
        }
    },

    async saveContestSettings(contestId) {
        const title = document.getElementById('edit-c-title').value;
        const start = document.getElementById('edit-c-start').value;
        const end = document.getElementById('edit-c-end').value;

        try {
            await API.request(`/contest/${contestId}`, 'PUT', {
                title,
                start_time: new Date(start).toISOString(),
                end_time: new Date(end).toISOString()
            });

            document.getElementById('edit-modal').remove();
            this.showNotification('Contest settings saved', 'success');

            // Silent Update Header
            const headerTitle = document.querySelector('.admin-header h1');
            if (headerTitle) {
                // Keep the badge, update text
                const badge = headerTitle.querySelector('.badge');
                headerTitle.childNodes[0].nodeValue = title + " ";
            }
            // this.loadContestDetail(contestId); // REMOVE THIS to prevent reload
        } catch (e) {
            alert('Error saving settings');
        }
    },

    async loadLeadersView() {
        try {
            const data = await API.request('/admin/leaders');
            const leaders = data.leaders || [];

            const html = `
                <div class="admin-header">
                    <h1>Leader Management</h1>
                    <button class="btn btn-primary" onclick="Admin.addLeader()">
                        <i class="fa-solid fa-plus"></i> Add Leader
                    </button>
                </div>

                <div class="bg-white rounded-xl shadow-sm" style="background: white; border-radius: 8px; padding: 1.5rem;">
                    <table class="admin-table">
                        <thead>
                            <tr>
                                <th>Name</th>
                                <th>Username (User ID)</th>
                                <th>Action</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${leaders.length > 0 ? leaders.map(l => `
                            <tr>
                                <td>${l.full_name || l.name}</td>
                                <td>${l.username || l.user_id}</td>
                                <td>
                                    <button class="btn btn-sm btn-secondary" onclick="Admin.deleteLeader('${l.leader_id || l.user_id}')" style="background-color:#fee2e2; color:#b91c1c; border:none;">
                                        <i class="fa-solid fa-trash"></i> Delete
                                    </button>
                                </td>
                            </tr>
                            `).join('') : '<tr><td colspan="3" style="text-align:center; padding: 2rem;">No leaders yet.</td></tr>'}
                        </tbody>
                    </table>
                </div>
            `;
            document.querySelector('.admin-main').innerHTML = html;
        } catch (e) {
            document.querySelector('.admin-main').innerHTML = `<h2 style="color:red">Error loading leaders: ${e.message}</h2>`;
        }
    },

    async addLeader() {
        const username = prompt("Enter Leader Username/ID:");
        if (!username) return;
        const name = prompt("Enter Leader Full Name:");
        if (!name) return;
        const password = prompt("Enter Leader Password:");
        if (!password) return;

        try {
            const res = await API.request('/admin/leaders', 'POST', {
                user_id: username, // Matching API expectation
                name: name,
                password: password
            });
            if (res.success) {
                this.showNotification("Leader added successfully", "success");
                this.loadLeadersView();
            }
        } catch (e) {
            alert("Failed to add leader: " + e.message);
        }
    },

    async deleteLeader(id) {
        if (!confirm("Are you sure you want to delete this leader?")) return;
        try {
            await API.request(`/admin/leaders/${id}`, 'DELETE');
            this.showNotification("Leader deleted", "success");
            this.loadLeadersView();
        } catch (e) {
            alert("Failed to delete leader");
        }
    },

    // ================= NEW LEVEL CONTROLS =================
    async activateLevel(level) {
        if (!confirm(`Set Level ${level} as ACTIVE? This will enable it for participants.`)) return;
        try {
            await API.request(`/contest/${this.activeContestId}/level/${level}/activate`, 'POST');
            Toast.show(`Level ${level} Activated`, 'success');
            this.loadDashboard();
        } catch (e) { console.error(e); Toast.show("Failed to activate", "error"); }
    },

    async completeLevel(level) {
        if (!confirm(`Mark Level ${level} as COMPLETE?`)) return;
        try {
            await API.request(`/contest/${this.activeContestId}/level/${level}/complete`, 'POST');
            Toast.show(`Level ${level} Completed`, 'success');
            this.loadDashboard();
        } catch (e) { console.error(e); Toast.show("Failed to complete", "error"); }
    },

    async toggleCountdown() {
        // Fetch fresh state first to be sure
        try {
            const res = await API.request(`/contest/${this.activeContestId}/countdown`);
            const isActive = res.active === true;

            // Toggle
            const action = isActive ? 'stop' : 'start';
            const sel = document.getElementById('wait-time-selector');
            const duration = sel ? sel.value : 15;

            let targetLevel = null;
            const levelSel = document.getElementById('selection-level-select');
            if (levelSel) {
                targetLevel = levelSel.value;
            }

            const toggleRes = await API.request(`/contest/${this.activeContestId}/countdown`, 'POST', { action, duration, target_level: targetLevel });

            if (toggleRes.success) {
                this.loadDashboard(); // Refresh UI fully
                Toast.show(`Countdown ${action.toUpperCase()}ED`, 'success');
            }
        } catch (e) {
            console.error(e);
            Toast.show("Failed to toggle countdown", "error");
        }
    },

    async controlContest(contestId, action) {
        // Requirements: 
        // Start -> Activate Level
        // Pause -> Pause Level
        // End -> Complete Level (or Contest)

        // We need to know the *Active Level* to target.
        // We can find it from local this.currentRounds or fetch it.
        // Let's assume we fetch current status to be safe.

        try {
            let targetLevel = 1;

            // Just for Start logic, we try to find the "Pending" level or currently "Active" level?
            // "The Start ... buttons must change the current level state"
            // If nothing is active, maybe we start Level 1?
            // Or we check which one is "Next"?

            // Simplification: Start button at top operates on the **Current Active Round** or **Next Pending Round**.

            if (!this.currentRounds) {
                const rRes = await API.request(`/contest/${contestId}/rounds`);
                this.currentRounds = rRes.rounds || [];
            }

            // Find active or first pending
            let current = this.currentRounds.find(r => r.status === 'active');
            if (!current && action === 'start') {
                // Try to find first pending/paused
                current = this.currentRounds.find(r => r.status === 'pending' || r.status === 'paused');
            }
            // If End, target active
            if (!current && action === 'end') {
                // Maybe contest end? "End buttons must change the current level state ... to COMPLETED"
                // If no level active, maybe just End Contest?
            }

            if (current) {
                targetLevel = current.round_number;
            } else if (action === 'start') {
                // Default to 1
                targetLevel = 1;
            }

            let endpoint = '';
            let method = 'POST';

            if (action === 'start') {
                endpoint = `/contest/${contestId}/level/${targetLevel}/activate`;
            } else if (action === 'pause') {
                endpoint = `/contest/${contestId}/level/${targetLevel}/pause`; // New endpoint we added
            } else if (action === 'end') {
                endpoint = `/contest/${contestId}/level/${targetLevel}/complete`;
            }

            if (confirm(`Are you sure you want to ${action.toUpperCase()} Level ${targetLevel}?`)) {
                await API.request(endpoint, method);
                Toast.show(`Level ${targetLevel} ${action.toUpperCase()}ED`, 'success');
                this.loadDashboard();
            }

        } catch (e) {
            console.error(e);
            Toast.show(`Failed to ${action}`, 'error');
        }
    },

    // ================= DASHBOARD =================
    async loadDashboard() {
        try {
            // Fetch contests to select active one
            const contestsRes = await API.request('/contest');
            if (!contestsRes) throw new Error("Failed to fetch contests. API may be down.");

            const contests = contestsRes.contests || [];
            const activeContest = contests.find(c => c.status === 'live') || contests[0];

            if (activeContest) {
                this.activeContestId = activeContest.id;
            }

            // Fetch real-time stats
            let stats = {};
            let countdown = { active: false };
            if (this.activeContestId) {
                stats = await API.request(`/contest/${this.activeContestId}/stats`);
                const rRes = await API.request(`/contest/${this.activeContestId}/rounds`);
                this.currentRounds = (rRes && rRes.rounds) ? rRes.rounds : [];

                // Fetch Countdown State using separate endpoint or extracting from stats if added
                // We added a route: GET /contest/:id/countdown
                try {
                    countdown = await API.request(`/contest/${this.activeContestId}/countdown`);
                } catch (e) { }
            }

            const html = `
                <div class="admin-header">
                    <div>
                        <h1>Contest Control Dashboard</h1>
                        <p style="color: var(--text-secondary);">Real-time monitoring and control</p>
                    </div>
                    ${this.activeContestId ? `
                    <div style="display: flex; gap: var(--space-3);">
                        <button class="btn btn-primary" onclick="Admin.controlContest('${this.activeContestId}', 'start')" title="Start Next/Current Level">
                            <i class="fa-solid fa-play"></i> Start
                        </button>
                        <button class="btn btn-secondary" onclick="Admin.controlContest('${this.activeContestId}', 'pause')" title="Pause Current Level">
                            <i class="fa-solid fa-pause"></i> Pause
                        </button>
                        <button class="btn btn-primary" style="background-color: var(--error); border: none;" onclick="Admin.controlContest('${this.activeContestId}', 'end')" title="Complete Current Level">
                            <i class="fa-solid fa-stop"></i> End Level
                        </button>
                    </div>
                    ` : ''}
                </div>



                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-label">Total Participants</div>
                        <div class="stat-value" id="stat-total">${stats.total_participants || 0}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Active Contestants</div>
                        <div class="stat-value" style="color: var(--success);" id="stat-active">${stats.active_participants || 0}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Violations Detected</div>
                        <div class="stat-value" style="color: var(--error);" id="stat-violations">${stats.violations_detected || 0}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Questions Solved</div>
                        <div class="stat-value" style="color: var(--primary-500);" id="stat-solved">${stats.questions_solved || 0}</div>
                    </div>
                </div>

                <!-- 5 LEVELS CONTEST PROGRESSION -->
                <div style="margin-top: 2rem; background: white; padding: var(--space-8); border-radius: var(--radius-xl); border: 1px solid var(--border-light); box-shadow: var(--shadow-sm);">
                    <div style="display:flex; justify-content: space-between; align-items: center; margin-bottom: 2rem;">
                        <div>
                            <h2 style="margin:0; font-size: 1.5rem;"><i class="fa-solid fa-trophy" style="color: #f59e0b; margin-right: 0.75rem;"></i> Contest Progression Roadmap</h2>
                            <p style="color: var(--text-secondary); margin-top: 0.25rem;">Monitor and control the 5 elimination levels of the marathon</p>
                        </div>
                        <div style="display:flex; gap: 1rem; align-items: center; background: var(--bg-secondary); padding: 0.75rem 1.25rem; border-radius: var(--radius-lg);">
                             <label style="font-size: 0.9rem; font-weight: 600; color: var(--text-primary);">Configured Wait Time:</label>
                             <select id="wait-time-selector" class="input" style="padding: 6px 12px; width: 140px; border: 1px solid var(--border-light); font-weight: 500;">
                                <option value="5">5 Minutes</option>
                                <option value="10">10 Minutes</option>
                                <option value="15" selected>15 Minutes</option>
                                <option value="20">20 Minutes</option>
                                <option value="30">30 Minutes</option>
                             </select>
                        </div>
                    </div>

                    <!-- Levels Grid -->
                    <div style="display: grid; grid-template-columns: repeat(5, 1fr); gap: 1rem; margin-bottom: 2rem;">
                        ${(() => {
                    const rounds = this.currentRounds || [];

                    return [1, 2, 3, 4, 5].map(lv => {
                        const round = rounds.find(r => r.round_number == lv);
                        const status = round ? round.status : 'pending';
                        const isActive = status === 'active';
                        const isCompleted = status === 'completed';

                        const borderColor = isCompleted ? '#10b981' : (isActive ? '#3b82f6' : '#f3f4f6');
                        const bgColor = isCompleted ? '#ecfdf5' : (isActive ? '#eff6ff' : '#fff');
                        const dotColor = isCompleted ? '#10b981' : (isActive ? '#3b82f6' : '#64748b');

                        const isLocked = (status === 'pending' || status === 'paused');
                        // Use lock for pending/paused, clock for active, check for completed
                        const statusIcon = isCompleted ? '<i class="fa-solid fa-circle-check"></i>' : (isActive ? '<i class="fa-solid fa-clock"></i>' : '<i class="fa-solid fa-lock"></i>');
                        const statusColor = isCompleted ? '#10b981' : (isActive ? '#3b82f6' : '#9ca3af');

                        return `
                <div class="level-card" style="padding: 1.25rem; border-radius: var(--radius-lg); border: 3px solid ${borderColor}; text-align: center; background: ${bgColor}; transition: all 0.3s ease; position: relative; cursor: ${isCompleted ? 'default' : 'pointer'}; box-shadow: ${isActive ? '0 0 15px rgba(59, 130, 246, 0.3)' : 'none'};">
                    <div style="position: absolute; top: 8px; right: 8px; color: ${statusColor}; font-size: 1.1rem;">${statusIcon}</div>
                    
                    <button class="btn-icon" style="position:absolute; top:8px; left:8px; color: #64748b; background:none; border:none; cursor:pointer;" onclick="event.stopPropagation(); Admin.showEditLevelModal(${lv})" title="Edit Level">
                        <i class="fa-solid fa-pen"></i>
                    </button>

                                        <div style="width: 40px; height: 40px; background: ${isActive ? '#3b82f6' : '#f3f4f6'}; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto 1rem; font-weight: 700; color: ${isActive ? 'white' : '#64748b'};">
                                            ${lv}
                                        </div>
                                        <h4 style="margin-bottom: 0.25rem;">Level ${lv}</h4>
                                        <span style="font-size: 0.75rem; color: ${dotColor}; text-transform: uppercase; font-weight: 700;">${status.toUpperCase()}</span>
                                        
                                        <div style="margin-top: 10px; display: flex; gap: 5px; justify-content: center;">
                                            <button class="btn btn-sm btn-primary" style="font-size: 0.7rem; padding: 2px 8px;" onclick="event.stopPropagation(); Admin.activateLevel(${lv})">Start</button>
                                            <button class="btn btn-sm btn-secondary" style="font-size: 0.7rem; padding: 2px 8px; color: #059669; border-color: #059669;" onclick="event.stopPropagation(); Admin.completeLevel(${lv})">Complete</button>
                                        </div>
                                    </div>
    `;
                    }).join('');
                })()}
                    </div>

                    <!-- Control Actions -->
                    <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 1.5rem;">
                        <div style="background: var(--primary-50); padding: 1.5rem; border-radius: var(--radius-xl); border: 1px solid var(--primary-100);">
                            <h4 style="color: var(--primary-700); margin-bottom: 0.5rem;"><i class="fa-solid fa-lock"></i> 1. Lock Responses</h4>
                            <p style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 1.25rem;">Disable further submissions for the current level.</p>
                            <button class="btn btn-primary" onclick="Admin.finalizeCurrentRound()" style="width: 100%;">Finalize Round</button>
                        </div>

                        <div style="background: #ecfdf5; padding: 1.5rem; border-radius: var(--radius-xl); border: 1px solid #d1fae5;">
                            <h4 style="color: #047857; margin-bottom: 0.5rem;"><i class="fa-solid fa-user-check"></i> 2. Selection</h4>
                            <p style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 1rem;">Rank participants and select who qualifies for the next level.</p>
                            
                            <!-- Level Selector -->
                            <div style="margin-bottom: 1rem;">
                                <select id="selection-level-select" class="input" style="width: 100%; border-color: #10b981; font-weight: 600; color: #047857;">
                                    ${(() => {
                    const rounds = this.currentRounds || [];
                    // Find highest completed level
                    let maxCompleted = 0;
                    rounds.forEach(r => {
                        if (r.status === 'completed') maxCompleted = Math.max(maxCompleted, r.round_number);
                    });
                    const defaultTarget = maxCompleted + 1;

                    return [1, 2, 3, 4, 5].map(lv => {
                        const round = rounds.find(r => r.round_number == lv);
                        const isDone = round && round.status === 'completed';
                        // Disable if completed (cannot re-select)
                        // Default to next available level
                        const selected = lv === defaultTarget ? 'selected' : '';
                        const disabled = isDone ? 'disabled' : '';
                        const label = isDone ? `Level ${lv} (Completed)` : `Qualifiers for Level ${lv}`;
                        return `<option value="${lv}" ${selected} ${disabled}>${label}</option>`;
                    }).join('');
                })()}
                                </select>
                            </div>

                            <div style="display:flex; gap: 0.75rem;">
                                <button class="btn btn-secondary" onclick="Admin.showSelectionModal()" style="flex:1; border-color: #047857; color: #047857;">Select Top</button>
                                <button class="btn btn-primary" onclick="Admin.sendProgressionNotifications()" style="flex:1; background: #047857; border: none;">Notify All</button>
                            </div>
                        </div>

                        <div style="background: #fffbeb; padding: 1.5rem; border-radius: var(--radius-xl); border: 1px solid #fef3c7;">
                            <h4 style="color: #b45309; margin-bottom: 0.5rem;"><i class="fa-solid fa-hourglass-start"></i> 3. Progression</h4>
                            <p style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 1.25rem;">Trigger wait time for the qualifying participants.</p>
                            <button id="btn-countdown" class="btn btn-primary" onclick="Admin.toggleCountdown()" 
                                style="width: 100%; border: none; font-weight: 600; ${countdown.active ? 'background-color: var(--error);' : 'background-color: #d97706;'}">
                                <i class="fa-solid ${countdown.active ? 'fa-stop' : 'fa-clock'}"></i> 
                                ${countdown.active ? 'Stop Countdown' : 'Start Countdown'}
                            </button>
                            ${countdown.active ? `
                                <div style="margin-top:0.5rem; text-align:center; font-weight:bold; color: #d97706;">
                                    Ends at: ${new Date(countdown.end_time).toLocaleTimeString()}
                                    ${countdown.target_level ? `<br><small>Target: Level ${countdown.target_level}</small>` : ''}
                                </div>
                            ` : ''}
                        </div>
                    </div>

                    <div style="margin-top: 2rem; display: flex; justify-content: space-between; align-items: center; border-top: 1px solid var(--border-light); padding-top: 1.5rem;">
                        <div style="display:flex; gap: 1rem;">
                            <button class="btn btn-secondary" onclick="Admin.downloadRoundReport()">
                                <i class="fa-solid fa-file-export"></i> Export Level Results
                            </button>
                            <button class="btn" style="background: #f8fafc; border: 1px solid var(--border-light); color: var(--text-secondary); font-weight: 600;" onclick="Admin.resetLevelStats()">
                                <i class="fa-solid fa-rotate-right"></i> Reset Level Counters
                            </button>
                        </div>
                        
                        </div>
                    </div>
                
                <div style="margin-top: 2rem;">
                    <h3>Live Activity Feed</h3>
                    <div class="feed-container" id="activity-feed" style="background: white; padding: 1rem; border-radius: 8px; max-height: 400px; overflow-y: auto;">
                        <p style="color:gray; text-align:center;">Waiting for activity...</p>
                    </div>
                </div>
            `;
            document.querySelector('.admin-main').innerHTML = html;
        } catch (e) {
            document.querySelector('.admin-main').innerHTML = `<h2 style="color:red">Error loading dashboard: ${e.message}</h2>`;
        }
    },

    async updateDashboardStats() {
        if (!this.activeContestId) return;

        try {
            const stats = await API.request(`/contest/${this.activeContestId}/stats`);
            if (stats) {
                if (document.getElementById('stat-total')) document.getElementById('stat-total').innerText = stats.total_participants || 0;
                if (document.getElementById('stat-active')) document.getElementById('stat-active').innerText = stats.active_participants || 0;
                if (document.getElementById('stat-violations')) document.getElementById('stat-violations').innerText = stats.violations_detected || 0;
                if (document.getElementById('stat-solved')) document.getElementById('stat-solved').innerText = stats.questions_solved || 0;
                if (document.getElementById('stat-submissions')) document.getElementById('stat-submissions').innerText = stats.total_submissions || 0;
                if (document.getElementById('stat-avg-score')) document.getElementById('stat-avg-score').innerText = stats.average_score || 0;
            }
        } catch (e) {
            console.error('Failed to update stats:', e);
        }
    },

    // Toggle Countdown
    async startWaitCountdown(e) {
        const btn = document.getElementById('btn-countdown');
        if (!btn) return;

        const isRunning = btn.innerText.includes('Stop');
        const action = isRunning ? 'stop' : 'start';

        try {
            await API.request(`/contest/${this.activeContestId}/countdown`, 'POST', { action });
            if (action === 'start') {
                btn.innerHTML = '<i class="fa-solid fa-stop"></i> Stop Countdown';
                btn.style.backgroundColor = 'var(--error)';
                Toast.show("Countdown Started", "success");
            } else {
                btn.innerHTML = '<i class="fa-solid fa-clock"></i> Start Wait Countdown';
                btn.style.backgroundColor = '#d97706';
                Toast.show("Countdown Stopped", "info");
            }
        } catch (err) {
            Toast.show("Failed to toggle countdown", "error");
        }
    },

    async unlockNextLevel() {
        if (!confirm("Unlock next level for shortlisted participants?")) return;
        // Logic: This could either be a general unlock signal or just part of 'advance-level'
        // For now, assume it's just a signal or effectively same as advance-level but without wait time?
        // Let's call advance-level with 0 wait time
        await API.request(`/contest/${this.activeContestId}/advance-level`, 'POST', { wait_time: 0 });
        Toast.show("Next level unlocked.", "success");
    },

    async controlContest(contestId, action) {
        try {
            const res = await API.request(`/contest/${contestId}/control/${action}`, 'POST');
            if (res && res.success) {
                this.showNotification(`Contest ${action}ed successfully`, 'success');
                this.loadDashboard(); // Reload to update button states
            }
        } catch (e) {
            console.error(e);
            alert(`Failed to ${action} contest`);
        }
    },

    switchContest(contestId) {
        this.activeContestId = contestId;
        this.loadDashboard();
    },

    showNotification(message, type = 'info') {
        // Simple notification - could be enhanced with a toast library
        const colors = {
            success: 'var(--success)',
            warning: 'var(--warning)',
            error: 'var(--error)',
            info: 'var(--primary-600)'
        };

        const notification = document.createElement('div');
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: ${colors[type] || colors.info};
            color: white;
            padding: 1rem 1.5rem;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            z-index: 10000;
            animation: slideIn 0.3s ease-out;
        `;
        notification.textContent = message;
        document.body.appendChild(notification);

        setTimeout(() => {
            notification.style.animation = 'slideOut 0.3s ease-in';
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    },

    addActivityFeedItem(message, type = 'info') {
        const feed = document.getElementById('activity-feed');
        if (!feed) return;

        // Clear placeholder if exists
        if (feed.querySelector('p[style*="gray"]')) {
            feed.innerHTML = '';
        }

        const icons = {
            join: 'fa-user-plus',
            submit: 'fa-code',
            violation: 'fa-exclamation-triangle',
            info: 'fa-info-circle'
        };

        const item = document.createElement('div');
        item.style.cssText = 'padding: 0.75rem; border-bottom: 1px solid #eee; display: flex; align-items: center; gap: 0.75rem;';
        item.innerHTML = `
            <i class="fa-solid ${icons[type] || icons.info}" style="color: var(--primary-600);"></i>
            <span>${message}</span>
            <small style="margin-left: auto; color: #888;">${new Date().toLocaleTimeString()}</small>
        `;

        feed.insertBefore(item, feed.firstChild);

        // Keep only last 50 items
        while (feed.children.length > 50) {
            feed.removeChild(feed.lastChild);
        }
    },

    // ================= PARTICIPANTS =================
    async loadParticipantsView() {
        try {
            const data = await API.request('/admin/participants');
            if (!data) throw new Error("Failed to fetch participants");

            const participants = data.participants || [];

            // Explicitly sort by ID for this view
            participants.sort((a, b) => {
                const idA = (a.participant_id || '').toLowerCase();
                const idB = (b.participant_id || '').toLowerCase();
                return idA.localeCompare(idB);
            });

            const html = `
                <div class="admin-header">
                    <h1>Participant Management</h1>
                    <div style="display:flex; gap:10px;">
                        <input type="file" id="upload-excel" accept=".xlsx, .xls" style="display:none" onchange="Admin.handleFileUpload(this)">
                        <button class="btn btn-secondary" onclick="document.getElementById('upload-excel').click()">
                            <i class="fa-solid fa-file-excel"></i> Import Excel
                        </button>
                        <button class="btn btn-primary" onclick="Admin.showAddParticipantModal()">
                            <i class="fa-solid fa-user-plus"></i> Add Participant
                        </button>
                    </div>
                </div>

                <div class="bg-white rounded-xl shadow-sm" style="background: white; border-radius: var(--radius-xl); padding: var(--space-6); overflow-x: auto;">
                    <table class="admin-table">
                        <thead>
                            <tr>
                                <th>S.No</th>
                                <th>ID</th>
                                <th>Name</th>
                                <th>College</th>
                                <th>Dept</th>
                                <th class="center">Status</th>
                                <th>Action</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${participants.length > 0 ? participants.map((p, idx) => `
                            <tr>
                                <td>${idx + 1}</td>
                                <td><span style="font-family:'Fira Code'; font-size:0.9em; font-weight:600;">${p.participant_id}</span></td>
                                <td>
                                    <div style="font-weight:600;">${p.name}</div>
                                    <div style="font-size:0.75rem; color:gray;">${p.email || '-'}</div>
                                </td>
                                <td><small>${p.college || '-'}</small></td>
                                <td><small>${p.department || '-'}</small></td>
                                <td class="center">
                                    <span class="badge ${p.status === 'active' ? 'badge-success' : 'badge-gray'}" style="text-transform:uppercase; font-size:0.7em;">${p.status}</span>
                                </td>
                                <td>
                                    <button class="btn btn-secondary" onclick="Admin.deleteParticipant('${p.participant_id}')" style="color: red; border-color: red; padding: 2px 8px; font-size: 0.8em;">Delete</button>
                                </td>
                            </tr>
                            `).join('') : '<tr><td colspan="7" style="text-align:center; padding: 2rem; color:gray;">No participants yet. Import Excel or Add Manually.</td></tr>'}
                        </tbody>
                    </table>
                </div>

                <!-- MODAL: ADD PARTICIPANT -->
                <div id="add-p-modal" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.5); z-index:1000; align-items:center; justify-content:center;">
                    <div class="glass-card" style="background:white; padding:2rem; width:450px; color: black; display:flex; flex-direction:column; max-height:90vh; overflow-y:auto;">
                        <h3 style="margin-bottom: 1rem; color: var(--primary-700);">Add New Participant</h3>
                        
                        <label style="font-weight:600; font-size:0.85rem; margin-top:0.5rem;">Full Name <span style="color:red">*</span></label>
                        <input type="text" id="new-p-name" class="input" placeholder="e.g. John Doe" style="width:100%;">
                        
                        <label style="font-weight:600; font-size:0.85rem; margin-top:1rem;">College <span style="color:red">*</span></label>
                        <input type="text" id="new-p-college" class="input" placeholder="e.g. SAC Sacred Heart College" style="width:100%;">
                        
                        <label style="font-weight:600; font-size:0.85rem; margin-top:1rem;">Department <span style="color:red">*</span></label>
                        <input type="text" id="new-p-dept" class="input" placeholder="e.g. CS" style="width:100%;">
                        
                        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:1rem; margin-top:1rem;">
                            <div>
                                <label style="font-weight:600; font-size:0.85rem;">Phone</label>
                                <input type="text" id="new-p-phone" class="input" placeholder="Optional" style="width:100%;">
                            </div>
                            <div>
                                <label style="font-weight:600; font-size:0.85rem;">Email</label>
                                <input type="email" id="new-p-email" class="input" placeholder="Optional" style="width:100%;">
                            </div>
                        </div>

                        <div style="background:#f0f9ff; padding:1rem; border-radius:8px; margin-top:1.5rem; font-size:0.8rem; color:#0369a1;">
                            <i class="fa-solid fa-info-circle"></i> Participant ID will be auto-generated (e.g. <b>SHCCSGF001</b>).
                        </div>

                        <div style="display:flex; justify-content: flex-end; gap: 1rem; margin-top: 1.5rem;">
                            <button class="btn btn-secondary" onclick="document.getElementById('add-p-modal').style.display='none'">Cancel</button>
                            <button class="btn btn-primary" onclick="Admin.submitNewParticipant()">Create Participant</button>
                        </div>
                    </div>
                </div>
            `;
            document.querySelector('.admin-main').innerHTML = html;
        } catch (e) {
            document.querySelector('.admin-main').innerHTML = `<h2 style="color:red">Error loading participants: ${e.message}</h2>`;
        }
    },

    showAddParticipantModal() {
        const modal = document.getElementById('add-p-modal');
        if (modal) modal.style.display = 'flex';
    },

    async submitNewParticipant() {
        const name = document.getElementById('new-p-name').value;
        const college = document.getElementById('new-p-college').value;
        const dept = document.getElementById('new-p-dept').value;
        const phone = document.getElementById('new-p-phone').value;
        const email = document.getElementById('new-p-email').value;

        if (!name || !college || !dept) return alert("FullName, College, and Department are required.");

        try {
            await API.request('/admin/participants', 'POST', {
                name,
                college,
                department: dept,
                phone,
                email,
                participant_id: null // Backend generates SHCCSGF... ID
            });
            document.getElementById('add-p-modal').style.display = 'none';
            this.showNotification("Participant Added Successfully", "success");
            this.loadParticipantsView(); // Refresh
        } catch (e) {
            console.error(e);
            alert("Failed to create participant: " + e.message);
        }
    },

    async deleteParticipant(pid) {
        if (confirm(`Delete user ${pid}? This action cannot be undone.`)) {
            await API.request(`/admin/participants/${pid}`, 'DELETE');
            this.showNotification("Participant Deleted", "info");
            this.loadParticipantsView();
        }
    },

    async handleFileUpload(input) {
        const file = input.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = async (e) => {
            try {
                const data = new Uint8Array(e.target.result);
                const workbook = XLSX.read(data, { type: 'array' });
                const firstSheet = workbook.Sheets[workbook.SheetNames[0]];
                const jsonData = XLSX.utils.sheet_to_json(firstSheet);

                if (jsonData.length === 0) {
                    alert("Excel file is empty or invalid.");
                    return;
                }

                let successCount = 0;
                let failCount = 0;

                const btn = document.querySelector('.admin-header .btn-secondary');
                const originalText = btn.innerHTML;
                btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Processing...';
                btn.disabled = true;

                for (const row of jsonData) {
                    // Try to map various column name possibilities
                    const pid = row['Participant ID'] || row['ID'] || row['id'] || row['User ID'] || row['participant_id'];
                    const name = row['Full Name'] || row['Name'] || row['Student Name'] || row['name'];
                    const college = row['College'] || row['Institution'] || row['College Name'] || row['college'];
                    const dept = row['Department'] || row['Dept'] || row['Branch'] || row['department'];
                    const phone = row['Phone'] || row['Mobile'] || row['Contact'] || row['phone'];
                    const email = row['Email'] || row['Email Address'] || row['Mail'] || row['email'];

                    if (pid && name) {
                        try {
                            const res = await API.request('/admin/participants', 'POST', {
                                participant_id: String(pid).trim(),
                                name: String(name).trim(),
                                college: college ? String(college).trim() : '',
                                department: dept ? String(dept).trim() : '',
                                phone: phone ? String(phone).trim() : '',
                                email: email ? String(email).trim() : '',
                                update_existing: true
                            });
                            if (res && res.success) {
                                successCount++;
                            } else {
                                console.warn(`Failed to add ${name}: ${res?.error || 'Unknown error'}`);
                                failCount++;
                            }
                        } catch (err) {
                            console.error("Failed to add", name, err);
                            failCount++;
                        }
                    } else {
                        // Skip row logic or count as fail?
                        if (name || pid) failCount++; // Count as fail if at least something was there but insufficient
                    }
                }

                alert(`Import Complete!\nSuccess: ${successCount}\nFailed/Skipped: ${failCount}`);
                this.loadParticipantsView();
                input.value = '';
                btn.innerHTML = originalText;
                btn.disabled = false;
            } catch (err) {
                console.error("Error parsing Excel:", err);
                alert("Error parsing Excel file. Ensure columns: 'Participant ID', 'Full Name', 'College', 'Department'");
            } finally {
                input.value = '';
                const btn = document.querySelector('.admin-header .btn-secondary');
                if (btn) {
                    // Restore button text strictly if it was changed
                    if (btn.innerHTML.includes('Processing')) {
                        btn.innerHTML = '<i class="fa-solid fa-file-excel"></i> Import Excel';
                        btn.disabled = false;
                    }
                }
            }
        };
        reader.readAsArrayBuffer(file);
    },
    // ================= LEADERS =================
    async loadLeadersView() {
        try {
            const data = await API.request('/admin/leaders');
            const leaders = data ? (data.leaders || []) : [];

            const html = `
                <div class="admin-header">
                    <h1>Leader Management</h1>
                    <button class="btn btn-primary" onclick="Admin.showAddLeaderModal()">
                        <i class="fa-solid fa-plus"></i> Add Leader
                    </button>
                </div>
                
                 <div class="bg-white rounded-xl shadow-sm" style="background: white; border-radius: var(--radius-xl); padding: var(--space-6);">
                    <table class="admin-table">
                        <thead>
                            <tr>
                                <th>Name</th>
                                <th>User ID</th>
                                <th>Dept / College</th>
                                <th>Status</th>
                                <th>Action</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${leaders.length > 0 ? leaders.map(l => `
                            <tr>
                                <td>
                                    <div style="font-weight:600;">${l.name}</div>
                                </td>
                                <td>${l.user_id}</td>
                                <td>
                                    <div style="font-size:0.85rem;">${l.department || '-'}</div>
                                    <div style="font-size:0.75rem; color:gray;">${l.college || '-'}</div>
                                </td>
                                <td>
                                    <span class="badge ${l.status === 'APPROVED' ? 'badge-success' : 'badge-gray'}">${l.status}</span>
                                </td>
                                 <td>
                                    <button class="btn btn-secondary" onclick="Admin.deleteLeader('${l.leader_id}')" style="color: red; border-color: red;">Delete</button>
                                </td>
                            </tr>
                            `).join('') : '<tr><td colspan="5" style="text-align:center; padding: 2rem;">No leaders yet.</td></tr>'}
                        </tbody>
                    </table>
                 </div>

                 <!-- MODAL -->
                <div id="add-l-modal" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.5); z-index:1000; align-items:center; justify-content:center;">
                    <div class="glass-card" style="background:white; padding:2rem; width:400px; color: black;">
                        <h3 style="margin-bottom: 1rem;">Add Leader</h3>
                        <input type="text" id="new-l-name" class="input" placeholder="Name" style="width:100%; margin: 0.5rem 0;">
                        <input type="text" id="new-l-userid" class="input" placeholder="User ID" style="width:100%; margin-bottom: 0.5rem;">
                        <input type="password" id="new-l-password" class="input" placeholder="Password" style="width:100%; margin-bottom: 0.5rem;">
                        <input type="text" id="new-l-dept" class="input" placeholder="Department" style="width:100%; margin-bottom: 0.5rem;">
                        <input type="text" id="new-l-college" class="input" placeholder="College" style="width:100%; margin-bottom: 1rem;">
                        
                        <div style="display:flex; justify-content: flex-end; gap: 1rem;">
                            <button class="btn btn-secondary" onclick="document.getElementById('add-l-modal').style.display='none'">Cancel</button>
                            <button class="btn btn-primary" onclick="Admin.submitNewLeader()">Create</button>
                        </div>
                    </div>
                </div>
            `;
            document.querySelector('.admin-main').innerHTML = html;
        } catch (e) {
            document.querySelector('.admin-main').innerHTML = `<h2 style="color:red">Error loading leaders: ${e.message}</h2>`;
        }
    },

    showAddLeaderModal() {
        const modal = document.getElementById('add-l-modal');
        if (modal) modal.style.display = 'flex';
    },

    async submitNewLeader() {
        const name = document.getElementById('new-l-name').value;
        const userId = document.getElementById('new-l-userid').value;
        const password = document.getElementById('new-l-password').value;
        const department = document.getElementById('new-l-dept').value;
        const college = document.getElementById('new-l-college').value;

        if (!userId || !password) return alert("User ID and Password are required");

        await API.request('/admin/leaders', 'POST', { name, user_id: userId, password, department, college });
        document.getElementById('add-l-modal').style.display = 'none';
        this.loadLeadersView();
    },

    async deleteLeader(lid) {
        if (confirm('Delete this leader?')) {
            await API.request(`/admin/leaders/${lid}`, 'DELETE');
            this.loadLeadersView();
        }
    },

    // ================= QUESTIONS =================
    async loadQuestionsView() {
        try {
            const data = await API.request('/admin/questions'); // Use Admin endpoint to see ALL levels
            const questions = data ? (data.questions || []) : [];

            const html = `
                <div class="admin-header">
                    <h1>Question Bank</h1>
                    <div style="display:flex; gap:10px;">
                        <input type="file" id="upload-questions-excel" accept=".xlsx, .xls" style="display:none" onchange="Admin.handleQuestionUpload(this)">
                        <button class="btn btn-secondary" onclick="document.getElementById('upload-questions-excel').click()">
                            <i class="fa-solid fa-file-excel"></i> Import Excel
                        </button>
                        <button class="btn btn-primary" onclick="Admin.showAddQuestionModal()">
                            <i class="fa-solid fa-plus"></i> Add Question
                        </button>
                    </div>
                </div>
                
                 <div class="bg-white rounded-xl shadow-sm" style="background: white; border-radius: var(--radius-xl); padding: var(--space-6);">
                    <table class="admin-table">
                        <thead>
                            <tr>
                                <th>S.No</th>
                                <th>Title</th>
                                <th class="center">Level</th>
                                <th>Expected Output</th>
                                <th>Action</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${questions.length > 0 ? questions.map((q, index) => `
                            <tr>
                                <td>${index + 1}</td>
                                <td>${q.title}</td>
                                <td class="center"><span class="badge badge-gray">Level ${q.round_number || '?'}</span></td>
                                <td><code style="font-size:0.8em">${q.expected_output ? q.expected_output.substring(0, 30) + '...' : ''}</code></td>
                                 <td>
                                    <button class="btn btn-secondary" onclick="Admin.showEditQuestionModal('${q.id}')" style="margin-right: 0.5rem;">Edit</button>
                                    <button class="btn btn-secondary" onclick="Admin.deleteQuestion('${q.id}')" style="color: red; border-color: red;">Delete</button>
                                </td>
                            </tr>
                            `).join('') : '<tr><td colspan="5" style="text-align:center; padding: 2rem;">No questions added yet.</td></tr>'}
                        </tbody>
                    </table>
                 </div>

                 <!--MODAL -->
            `;
            document.querySelector('.admin-main').innerHTML = html;
        } catch (e) {
            document.querySelector('.admin-main').innerHTML = `< h2 style = "color:red" > Error loading questions: ${e.message}</h2 > `;
        }
    },

    showAddQuestionModal(level = null) {
        let modal = document.getElementById('add-q-modal');
        if (!modal) {
            const modalHtml = `
            <div id="add-q-modal" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.5); z-index:9999; align-items:center; justify-content:center;">
                    <div class="glass-card" style="background:white; padding:2rem; width:600px; color: black; max-height: 90vh; overflow-y: auto;">
                        <h3 style="margin-bottom: 1rem;">Add Debugging Question</h3>
                        <div style="margin-bottom: 1rem;">
                            <label style="display:block; margin-bottom: 0.5rem; font-weight: 600;">Question Title</label>
                            <input type="text" id="new-q-title" class="input" placeholder="e.g. Broken Fibonacci" style="width:100%;">
                        </div>
                        
                            <div>
                                <label style="display:block; margin-bottom: 0.5rem; font-weight: 600;">Level</label>
                                <select id="new-q-level" class="input" style="width:100%;">
                                    <option value="1">Level 1</option>
                                    <option value="2">Level 2</option>
                                    <option value="3">Level 3</option>
                                    <option value="4">Level 4</option>
                                    <option value="5">Level 5</option>
                                </select>
                            </div>
                            <div>
                                <label style="display:block; margin-bottom: 0.5rem; font-weight: 600;">Language</label>
                                <select id="new-q-lang" class="input" style="width:100%;">
                                    <option value="python">Python</option>
                                    <option value="c">C</option>
                                    <option value="java">Java</option>
                                    <option value="javascript">JavaScript</option>
                                    <option value="cpp">C++</option>
                                </select>
                            </div>
                        
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1rem;">
                                <div>
                                <label style="display:block; margin-bottom: 0.5rem; font-weight: 600;">Expected Input (Optional)</label>
                                <textarea id="new-q-input" class="input" placeholder="Inputs for the code..." style="width:100%; height: 80px; font-family: 'Fira Code', monospace;"></textarea>
                                </div>
                                <div>
                                <label style="display:block; margin-bottom: 0.5rem; font-weight: 600;">Expected Output (Required)</label>
                                <textarea id="new-q-output" class="input" placeholder="Correct output..." style="width:100%; height: 80px; font-family: 'Fira Code', monospace;"></textarea>
                                </div>
                        </div>

                        <div style="margin-bottom: 1rem;">
                            <label style="display:block; margin-bottom: 0.5rem; font-weight: 600;">Buggy Code (This will appear in the participant's editor)</label>
                            <textarea id="new-q-buggy" class="input" placeholder="Paste the code with errors here..." style="width:100%; height: 150px; font-family: 'Fira Code', monospace;"></textarea>
                        </div>

                        <div style="display:flex; justify-content: flex-end; gap: 1rem; margin-top: 1rem;">
                            <button class="btn btn-secondary" onclick="document.getElementById('add-q-modal').style.display='none'">Cancel</button>
                            <button class="btn btn-primary" onclick="Admin.submitNewQuestion()">Create Question</button>
                        </div>
                    </div>
                </div>
            `;
            document.body.insertAdjacentHTML('beforeend', modalHtml);
            modal = document.getElementById('add-q-modal');
        }

        if (modal) {
            modal.style.display = 'flex';
            if (level) {
                const sel = document.getElementById('new-q-level');
                if (sel) sel.value = level;
            }
        }
    },

    async submitNewQuestion() {
        const title = document.getElementById('new-q-title').value;
        const level = document.getElementById('new-q-level').value; // Changed from diff
        const language = document.getElementById('new-q-lang').value;
        const expInput = document.getElementById('new-q-input').value;
        const expOutput = document.getElementById('new-q-output').value;
        const buggyCode = document.getElementById('new-q-buggy').value;

        if (!title || !expOutput || !buggyCode) {
            alert("Title, Expected Output and Buggy Code are required");
            return;
        }

        // We use the level-specific endpoint now to ensure valid linking
        // Endpoint: /contest/<id>/rounds/<level>/question
        try {
            const res = await API.request(`/contest/${this.activeContestId}/rounds/${level}/question`, 'POST', {
                title,
                difficulty: 'medium', // Default for DB enum compatibility
                language,
                expected_input: expInput,
                expected_output: expOutput,
                boilerplate: { [language]: buggyCode }
            });

            if (res && res.success) {
                document.getElementById('add-q-modal').style.display = 'none';
                this.loadQuestionsView();
                this.showNotification("Question Added Successfully", "success");
            } else {
                throw new Error(res && res.error ? res.error : "Unknown backend error");
            }

        } catch (e) {
            alert("Failed: " + e.message);
        }
    },

    async deleteQuestion(qid) {
        if (confirm('Delete this question?')) {
            await API.request(`/admin/questions/${qid}`, 'DELETE');
            this.loadQuestionsView();
        }
    },

    async showEditQuestionModal(questionId) {
        try {
            // Fetch question data
            const response = await API.request(`/admin/questions/${questionId}`);
            const question = response.question;

            // Create or get edit modal
            let modal = document.getElementById('edit-q-modal');
            if (!modal) {
                const modalHtml = `
                <div id="edit-q-modal" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.5); z-index:9999; align-items:center; justify-content:center;">
                    <div class="glass-card" style="background:white; padding:2rem; width:600px; color: black; max-height: 90vh; overflow-y: auto;">
                        <h3 style="margin-bottom: 1rem;">Edit Question</h3>
                        <input type="hidden" id="edit-q-id">
                        <div style="margin-bottom: 1rem;">
                            <label style="display:block; margin-bottom: 0.5rem; font-weight: 600;">Question Title</label>
                            <input type="text" id="edit-q-title" class="input" placeholder="e.g. Broken Fibonacci" style="width:100%;">
                        </div>
                        
                        <div>
                            <label style="display:block; margin-bottom: 0.5rem; font-weight: 600;">Level</label>
                            <select id="edit-q-level" class="input" style="width:100%;">
                                <option value="1">Level 1</option>
                                <option value="2">Level 2</option>
                                <option value="3">Level 3</option>
                                <option value="4">Level 4</option>
                                <option value="5">Level 5</option>
                            </select>
                        </div>
                        <div>
                            <label style="display:block; margin-bottom: 0.5rem; font-weight: 600;">Language</label>
                            <select id="edit-q-lang" class="input" style="width:100%;">
                                <option value="python">Python</option>
                                <option value="c">C</option>
                                <option value="java">Java</option>
                                <option value="javascript">JavaScript</option>
                                <option value="cpp">C++</option>
                            </select>
                        </div>
                        
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1rem;">
                            <div>
                                <label style="display:block; margin-bottom: 0.5rem; font-weight: 600;">Expected Input (Optional)</label>
                                <textarea id="edit-q-input" class="input" placeholder="Inputs for the code..." style="width:100%; height: 80px; font-family: 'Fira Code', monospace;"></textarea>
                            </div>
                            <div>
                                <label style="display:block; margin-bottom: 0.5rem; font-weight: 600;">Expected Output (Required)</label>
                                <textarea id="edit-q-output" class="input" placeholder="Correct output..." style="width:100%; height: 80px; font-family: 'Fira Code', monospace;"></textarea>
                            </div>
                        </div>

                        <div style="margin-bottom: 1rem;">
                            <label style="display:block; margin-bottom: 0.5rem; font-weight: 600;">Buggy Code (This will appear in the participant's editor)</label>
                            <textarea id="edit-q-buggy" class="input" placeholder="Paste the code with errors here..." style="width:100%; height: 150px; font-family: 'Fira Code', monospace;"></textarea>
                        </div>

                        <div style="display:flex; justify-content: flex-end; gap: 1rem; margin-top: 1rem;">
                            <button class="btn btn-secondary" onclick="document.getElementById('edit-q-modal').style.display='none'">Cancel</button>
                            <button class="btn btn-primary" onclick="Admin.submitEditQuestion()">Save Changes</button>
                        </div>
                    </div>
                </div>
                `;
                document.body.insertAdjacentHTML('beforeend', modalHtml);
                modal = document.getElementById('edit-q-modal');
            }

            // Populate fields with existing data
            document.getElementById('edit-q-id').value = questionId;
            document.getElementById('edit-q-title').value = question.title || '';
            document.getElementById('edit-q-level').value = question.round_number || '1';
            document.getElementById('edit-q-lang').value = question.language || 'python';
            document.getElementById('edit-q-input').value = question.expected_input || '';
            document.getElementById('edit-q-output').value = question.expected_output || '';
            document.getElementById('edit-q-buggy').value = question.buggy_code || '';

            // Show modal
            modal.style.display = 'flex';
        } catch (error) {
            console.error('Error fetching question:', error);
            alert('Failed to load question data: ' + error.message);
        }
    },

    async submitEditQuestion() {
        const questionId = document.getElementById('edit-q-id').value;
        const title = document.getElementById('edit-q-title').value;
        const level = document.getElementById('edit-q-level').value;
        const language = document.getElementById('edit-q-lang').value;
        const expInput = document.getElementById('edit-q-input').value;
        const expOutput = document.getElementById('edit-q-output').value;
        const buggyCode = document.getElementById('edit-q-buggy').value;

        if (!title || !expOutput || !buggyCode) {
            alert("Title, Expected Output and Buggy Code are required");
            return;
        }

        try {
            const res = await API.request(`/admin/questions/${questionId}`, 'PUT', {
                title,
                round_number: level,
                language,
                expected_input: expInput,
                expected_output: expOutput,
                buggy_code: buggyCode
            });

            if (res && res.success) {
                document.getElementById('edit-q-modal').style.display = 'none';
                this.loadQuestionsView();
                this.showNotification("Question Updated Successfully", "success");
            } else {
                throw new Error(res && res.error ? res.error : "Unknown error");
            }
        } catch (e) {
            alert("Failed to update question: " + e.message);
        }
    },


    async handleQuestionUpload(input) {
        const file = input.files[0];
        if (!file) return;

        // Find the button adjacent to the input
        const btn = input.nextElementSibling;
        const originalText = btn.innerHTML;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Processing...';
        btn.disabled = true;

        const reader = new FileReader();
        reader.onload = async (e) => {
            try {
                const data = new Uint8Array(e.target.result);
                const workbook = XLSX.read(data, { type: 'array' });
                const firstSheet = workbook.Sheets[workbook.SheetNames[0]];
                const jsonData = XLSX.utils.sheet_to_json(firstSheet);
                if (jsonData.length === 0) { alert("Excel file is empty."); return; }

                const questions = [];
                for (const row of jsonData) {
                    const title = row['Title'] || row['title'] || row['Name'] || row['name'];
                    // Description removed
                    const expInput = row['Expected Input'] || row['expected_input'] || row['Input'] || row['input'] || "";
                    const expOutput = row['Expected Output'] || row['expected_output'] || row['Output'] || row['output'];

                    const buggy = row['BuggyCode'] || row['buggy_code'] || row['Code'] || row['code'] || "";
                    const difficulty = row['Difficulty'] || row['difficulty'] || 'Level 1';

                    if (title && expOutput) {
                        questions.push({
                            title,
                            difficulty: difficulty, // Assume Excel has correct 'Level X' format or we normalize
                            expected_input: expInput,
                            expected_output: expOutput,
                            boilerplate: { python: buggy, javascript: buggy, java: buggy, cpp: buggy }
                        });
                    }
                }

                if (questions.length > 0) {
                    const res = await API.request('/admin/questions/bulk', 'POST', { questions });
                    if (res && res.success) {
                        alert(`Successfully imported ${res.count} questions.`);
                    } else {
                        alert("Import failed on server.");
                    }
                }
                this.loadQuestionsView();
            } catch (err) {
                console.error(err);
                alert("Error parsing Excel.");
            }
            input.value = '';

            // Restore Button State
            if (btn) {
                btn.innerHTML = originalText;
                btn.disabled = false;
            }
        };
        reader.readAsArrayBuffer(file);
    },

    async finalizeCurrentRound() {
        if (!confirm("This will lock the current round and calculate final rankings. Proceed?")) return;
        Toast.show("Finalizing round and calculating rankings...", "success");
        // Backend logic to set current round status to 'completed'
        await API.request(`/contest/${this.activeContestId}/finalize-round`, 'POST');
        this.loadDashboard();
    },

    async showSelectionModal() {
        // Requirement: "Fetch saved shortlisted participants... Pre-check those"
        // Dynamically Determine "Next Level".
        let level = 2; // Default

        // Find current active level or laster completed
        if (this.currentRounds) {
            const active = this.currentRounds.find(r => r.status === 'active');
            if (active) level = active.round_number + 1;
            else {
                // If no active, maybe find last completed
                const completed = this.currentRounds.filter(r => r.status === 'completed');
                if (completed.length > 0) level = completed[completed.length - 1].round_number + 1;
            }
        }
        if (level > 5) level = 5; // Cap

        const [data, shortData] = await Promise.all([
            API.request('/admin/participants'),
            API.request(`/contest/${this.activeContestId}/shortlisted-participants?level=${level}`)
        ]);

        const participants = data.participants || [];
        const shortlistedIds = new Set((shortData.participants || []).map(p => p.id));

        // Ensure sorted by score descending
        participants.sort((a, b) => (b.score || 0) - (a.score || 0));

        const modalHtml = `
            <div id="selection-modal" class="modal-overlay" style="display:flex; justify-content:center; align-items:center; position:fixed; top:0; left:0; width:100%; height:100%; z-index:2000;">
                <div class="modal-content medium" style="max-height:85vh; display:flex; flex-direction:column;">
                    <div class="modal-header">
                        <h3>Select Participants for Next Level</h3>
                    </div>
                    
                    <div class="modal-body">
                        <div style="margin-bottom: 1.5rem; padding: 1rem; background: #f8fafc; border-radius: 8px; border: 1px solid #e2e8f0;">
                            <label style="display:block; font-weight:600; font-size:0.9rem; margin-bottom:0.5rem; color:#475569;">Select Top Participants</label>
                            <div style="display:flex; gap: 0.5rem;">
                                <input type="number" class="input" id="select-top-input" placeholder="Enter number (e.g., 50)" style="flex:1;" oninput="Admin.autoSelectTop(this.value)">
                                <div style="display:flex; align-items:center; font-size:0.8rem; color:#64748b; background: white; padding: 0 0.75rem; border-radius: 4px; border: 1px solid #cbd5e1;">
                                    Score Based
                                </div>
                            </div>
                        </div>

                        <p style="font-size:0.8rem; color:gray; margin-bottom:0.5rem;">Top performers sorted by score (Highest First).</p>
                        
                        <div id="participant-list-select" class="participant-list" style="margin-bottom:1rem; max-height: 300px; overflow-y:auto;">
                            ${participants.map((p, index) => `
                                <div class="list-item ${shortlistedIds.has(p.id) ? 'selected' : ''}" style="background: ${index < 10 ? '#f0fdf4' : ''};">
                                    <div style="display:flex; align-items:center; gap:0.5rem;">
                                        <span style="font-weight:600; color:#334155; min-width:25px;">${index + 1}.</span>
                                        <span>${p.name}</span>
                                        <span class="badge" style="background-color:#e2e8f0; color:#475569;">${p.score} pts</span>
                                    </div>
                                    <input type="checkbox" class="p-select-chk" value="${p.id}" data-idx="${index}" ${shortlistedIds.has(p.id) ? 'checked' : ''}>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                    
                    <div class="modal-actions">
                        <button class="btn btn-secondary" onclick="document.getElementById('selection-modal').remove()">Cancel</button>
                        <button class="btn btn-primary" onclick="Admin.saveSelection()">Save Selection</button>
                    </div>
                </div>
            </div>
        `;
        document.body.insertAdjacentHTML('beforeend', modalHtml);
    },

    autoSelectTop(n) {
        if (!n || n.trim() === '') {
            // Optional: Reset to DB state or do nothing? 
            // Better UX: If cleared, maybe uncheck all? Or do nothing. 
            // User requirement: "If Top-N input is empty -> no one is selected" (Starting state).
            // But if user clears input, we probably shouldn't uncheck manually checked ones unless explicit.
            // Let's stick to Requirements: "If admin enters a number... Select top N... Leave others unchecked"
            // "If Top-N input is empty → no one is selected" implies default state logic.
            return;
        }

        const count = parseInt(n);
        if (isNaN(count)) return;

        const checkboxes = document.querySelectorAll('.p-select-chk');
        checkboxes.forEach((chk, idx) => {
            if (idx < count) {
                chk.checked = true;
            } else {
                chk.checked = false;
            }
        });
    },

    async saveSelection() {
        // Re-determine level to match what was shown
        let level = 2; // Default
        if (this.currentRounds) {
            const active = this.currentRounds.find(r => r.status === 'active');
            if (active) level = active.round_number + 1;
            else {
                const completed = this.currentRounds.filter(r => r.status === 'completed');
                if (completed.length > 0) level = completed[completed.length - 1].round_number + 1;
            }
        }
        if (level > 5) level = 5;

        const selectedIds = Array.from(document.querySelectorAll('.p-select-chk:checked')).map(el => el.value);

        // Alert Logic Update: Show actual count
        // "Alert message must show the real count of selected participants... NOT... Top N input value"
        // We are using Toast.show below, but user mentioned default alert? Or maybe prompt?
        // Let's ensure we use Toast properly with count.

        await API.request(`/contest/${this.activeContestId}/qualify-participants`, 'POST', {
            participant_ids: selectedIds,
            level: level
        });
        document.getElementById('selection-modal').remove();

        // Alert Confirmation
        alert(`✅ ${selectedIds.length} participants selected successfully`);
        // Toast.show(`Saved selection: ${selectedIds.length} participants qualified.`, "success"); // Optional
    },

    async sendProgressionNotifications() {
        if (!confirm("Send result notifications to all participants? (Qualified vs Blocked)")) return;
        await API.request(`/contest/${this.activeContestId}/notify-progression`, 'POST');
        Toast.show("Notifications sent successfully.", "success");
    },



    async downloadRoundReport() {
        window.open(`${API.BASE_URL}/contest/report/${this.activeContestId}/round`, '_blank');
    },

    async manualActivateLevel(level) {
        if (!confirm(`Start Level ${level} now?`)) return;
        try {
            await API.request(`/contest/${this.activeContestId}/level/${level}/activate`, 'POST');
            Toast.show(`Level ${level} Started`, "success");
            this.loadDashboard(); // Refresh UI to show unlock icon
        } catch (e) {
            Toast.show("Failed to start level", "error");
        }
    },

    async manualCompleteLevel(level) {
        if (!confirm(`Mark Level ${level} as Completed?`)) return;
        try {
            await API.request(`/contest/${this.activeContestId}/level/${level}/complete`, 'POST');
            Toast.show(`Level ${level} Completed`, "success");
            this.loadDashboard(); // Refresh UI to show check icon
        } catch (e) {
            Toast.show("Failed to complete level", "error");
        }
    },

    // ================= PROCTORING MODULE =================
    async loadProctoringView() {
        const contestId = this.activeContestId;

        if (!contestId) {
            document.querySelector('.admin-main').innerHTML = `
                <div class="admin-header">
                    <h1>Proctoring Control Center</h1>
                </div>
    <div style="background: white; padding: 2rem; border-radius: 12px; text-align: center;">
        <i class="fa-solid fa-exclamation-triangle" style="font-size: 3rem; color: var(--warning); margin-bottom: 1rem;"></i>
        <h3>No Active Contest Selected</h3>
        <p style="color: var(--text-secondary); margin: 1rem 0;">Please select a contest from the Dashboard to enable proctoring.</p>
        <button class="btn btn-primary" onclick="Admin.switchView('dashboard')">
            <i class="fa-solid fa-arrow-left"></i> Go to Dashboard
        </button>
    </div>
`;
            return;
        }

        try {
            // Fetch proctoring data
            const [configRes, statsRes, statusRes] = await Promise.all([
                API.request(`/proctoring/config/${contestId}`),
                API.request(`/proctoring/stats/${contestId}`),
                API.request(`/proctoring/status/${contestId}`)
            ]);

            const config = configRes.config;
            const stats = statsRes.stats;
            const statuses = statusRes.statuses || [];

            const html = `
    <div class="admin-header">
                    <div>
                        <h1><i class="fa-solid fa-shield-halved"></i> Proctoring Control Center</h1>
                        <p style="color: var(--text-secondary);">Real-time monitoring and anti-cheat management</p>
                    </div>
                    <div style="display: flex; gap: var(--space-3);">
                        <button class="btn btn-secondary" onclick="Admin.showProctoringConfig()">
                            <i class="fa-solid fa-cog"></i> Configure
                        </button>
                        <button class="btn btn-primary" onclick="Admin.exportProctoringReport()">
                            <i class="fa-solid fa-download"></i> Export Excel
                        </button>
                    </div>
                </div>

                <!-- Proctoring Status -->
                <div style="background: ${config.enabled ? '#d4edda' : '#f8d7da'}; padding: 1.5rem; border-radius: 12px; margin-bottom: 2rem; display: flex; justify-content: space-between; align-items: center; border: 2px solid ${config.enabled ? 'var(--success)' : 'var(--error)'};">
                    <div>
                        <h3 style="margin: 0; color: ${config.enabled ? 'var(--success)' : 'var(--error)'};">
                            <i class="fa-solid fa-${config.enabled ? 'shield-halved' : 'shield-slash'}"></i>
                            Proctoring ${config.enabled ? 'ACTIVE' : 'DISABLED'}
                        </h3>
                        <p style="margin: 0.5rem 0 0 0; color: #333;">
                            ${config.enabled ? 'All participants are being monitored' : 'Monitoring is currently disabled'}
                        </p>
                    </div>
                    <button class="btn ${config.enabled ? 'btn-secondary' : 'btn-primary'}" onclick="Admin.toggleProctoring(${!config.enabled})">
                        ${config.enabled ? 'Disable' : 'Enable'} Proctoring
                    </button>
                </div>

                <!-- Stats Grid -->
                <div class="stats-grid" id="proctoring-stats-grid" style="margin-bottom: 2rem;">
                    <!-- Stats Content will be dynamically updated -->
                    ${this.renderProctoringStats(stats)}
                </div>

                <!-- Live Participant Monitoring -->
                <div style="background: white; padding: 1.5rem; border-radius: 12px; margin-bottom: 2rem;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                        <h3 style="margin: 0;">Live Participant Monitoring</h3>
                         <div style="display:flex; gap: 0.5rem; align-items: center;">
                            <select id="proctoring-level-filter" class="input" style="padding: 4px 8px; font-size: 0.9rem;" onchange="Admin.refreshProctoringData(true)">
                                <option value="">All Levels</option>
                                <option value="1">Level 1</option>
                                <option value="2">Level 2</option>
                                <option value="3">Level 3</option>
                                <option value="4">Level 4</option>
                                <option value="5">Level 5</option>
                            </select>
                            <button class="btn btn-sm btn-secondary" onclick="Admin.refreshProctoringData(true)">
                                <i class="fa-solid fa-refresh"></i> Refresh
                            </button>
                        </div>
                    </div>
                    <div style="overflow-x: auto;">
                        <table class="admin-table">
                            <thead>
                                <tr>
                                    <th>Participant</th>
                                    <th>Violations / Risk</th>
                                    <th>Violations</th>
                                    <th>Tabs</th>
                                    <th>Copy</th>
                                    <th>Screen</th>
                                    <th>Focus</th>
                                    <th>Status</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody id="proctoring-table-body">
                                ${this.renderProctoringParticipants(statuses, config)}
                            </tbody>
                        </table>
                    </div>
                </div>
            `;

            document.querySelector('.admin-main').innerHTML = html;
            this.currentProctoringConfig = config;

            // Start Polling
            if (this.proctoringInterval) clearInterval(this.proctoringInterval);
            this.proctoringInterval = setInterval(() => this.refreshProctoringData(), 3000); // Poll every 3 seconds

        } catch (e) {
            console.error('Error loading proctoring view:', e);
            document.querySelector('.admin-main').innerHTML = `<h2 style="color:red">Error loading proctoring: ${e.message}</h2>`;
        }
    },

    async refreshProctoringData(manual = false) {
        if (!this.activeContestId) return;
        try {
            const btn = manual ? document.querySelector('.btn-secondary i.fa-refresh') : null;
            if (btn) btn.classList.add('fa-spin');

            const levelFilter = document.getElementById('proctoring-level-filter') ? document.getElementById('proctoring-level-filter').value : '';
            const statusUrl = levelFilter ? `/proctoring/status/${this.activeContestId}?level=${levelFilter}` : `/proctoring/status/${this.activeContestId}`;

            const [statsRes, statusRes] = await Promise.all([
                API.request(`/proctoring/stats/${this.activeContestId}`),
                API.request(statusUrl)
            ]);

            // Update UI parts independently to avoid flickers
            // const stats = statsRes.stats;
            // const statuses = statusRes.statuses || [];

            // To ensure we have breakdown data, we rely on backend having these columns.
            // If backend doesn't return them in statuses yet (e.g. if they are missing in DB), they will be undefined.
            const stats = statsRes.stats;
            const statuses = statusRes.statuses || [];

            // Update Stats Grid
            const statsGrid = document.getElementById('proctoring-stats-grid');
            if (statsGrid) statsGrid.innerHTML = this.renderProctoringStats(stats);

            // Update Table
            const tbody = document.getElementById('proctoring-table-body');
            if (tbody) tbody.innerHTML = this.renderProctoringParticipants(statuses, this.currentProctoringConfig || {});

            // Timestamp removed per requirement

            if (manual && btn) setTimeout(() => btn.classList.remove('fa-spin'), 500);

        } catch (e) {
            console.error("Polling error:", e);
        }
    },

    renderProctoringStats(stats) {
        return `
             <div class="stat-card" style="border-left: 4px solid var(--error);">
                <div class="stat-label">Total Violations</div>
                <div class="stat-value" style="color: var(--error);">${stats.total_violations || 0}</div>
                <div style="font-size: 0.875rem; color: var(--text-secondary);">Across all participants</div>
            </div>
            <div class="stat-card" style="border-left: 4px solid var(--warning);">
                <div class="stat-label">Risky Participants</div>
                <div class="stat-value" style="color: var(--warning);">${stats.active_risky_participants || 0}</div>
                <div style="font-size: 0.875rem; color: var(--text-secondary);">High/Critical risk level</div>
            </div>
            <div class="stat-card" style="border-left: 4px solid var(--primary-600);">
                <div class="stat-label">Auto-Disqualified</div>
                <div class="stat-value" style="color: var(--primary-600);">${stats.auto_disqualifications || 0}</div>
                <div style="font-size: 0.875rem; color: var(--text-secondary);">System enforced</div>
            </div>
            <div class="stat-card" style="border-left: 4px solid var(--text-secondary);">
                <div class="stat-label">Manual Actions</div>
                <div class="stat-value">${stats.manual_disqualifications || 0}</div>
                <div style="font-size: 0.875rem; color: var(--text-secondary);">Admin interventions</div>
            </div>
        `;
    },

    async exportProctoringReport() {
        if (!this.activeContestId) return;
        const levelFilter = document.getElementById('proctoring-level-filter') ? document.getElementById('proctoring-level-filter').value : '';
        const url = `${API.BASE_URL}/proctoring/export/${this.activeContestId}?token=${API.token}${levelFilter ? '&level=' + levelFilter : ''}`;
        window.open(url, '_blank');
    },

    renderProctoringParticipants(statuses, config) {
        if (!statuses || statuses.length === 0) {
            return '<tr><td colspan="9" style="text-align: center; padding: 2rem; color: var(--text-secondary);">No participants to monitor</td></tr>';
        }

        const getRiskColor = (level) => {
            const colors = { 'low': 'var(--success)', 'medium': 'var(--warning)', 'high': 'var(--error)', 'critical': '#8b0000' };
            return colors[level] || colors.low;
        };

        return statuses.map(status => {
            const riskColor = getRiskColor(status.risk_level);
            // Ensure violation counts are numbers
            const tabV = status.tab_switches || 0;
            const copyV = status.copy_attempts || 0;
            const screenV = status.screenshot_attempts || 0;
            const focusV = status.focus_losses || 0;

            const compactBtnStyle = "padding: 0.15rem 0.5rem; font-size: 0.75rem; display:inline-flex; align-items:center; gap:4px;";

            return `
                <tr style="${status.is_disqualified ? 'opacity: 0.6; background: #fff5f5;' : ''}">
                    <td>
                        <div style="font-weight: 600;">${status.participant_name || 'Unknown'}</div>
                        <div style="font-size: 0.75rem; color: var(--text-secondary);">${status.participant_id}</div>
                    </td>
                    <td>
                        <span class="badge" style="background: ${riskColor}; color: white; font-size: 0.7rem; padding: 2px 6px;">
                            ${(status.risk_level || 'low').toUpperCase()}
                        </span>
                        <div style="font-size: 0.7rem; margin-top:2px;">Score: ${status.violation_score || 0}</div>
                    </td>
                    <td>
                        <span style="font-size: 1.1rem; font-weight: bold; color: ${status.total_violations > config.warning_threshold ? 'var(--error)' : 'inherit'};">
                            ${status.total_violations || 0}
                        </span>
                        <span style="font-size: 0.7rem; color: var(--text-secondary);"> / ${config.max_violations}</span>
                    </td>
                    <td class="center" style="color: ${tabV > 0 ? 'var(--error)' : 'inherit'}">${tabV}</td>
                    <td class="center" style="color: ${copyV > 0 ? 'var(--error)' : 'inherit'}">${copyV}</td>
                    <td class="center" style="color: ${screenV > 0 ? 'var(--error)' : 'inherit'}">${screenV}</td>
                    <td class="center" style="color: ${focusV > 0 ? 'var(--warning)' : 'inherit'}">${focusV}</td>
                    <td>
                        ${status.is_disqualified ?
                    '<span class="badge" style="background: var(--error); color: white; font-size:0.7rem;">DQ</span>' :
                    status.is_suspended ?
                        '<span class="badge" style="background: var(--warning); color: white; font-size:0.7rem;">SUSP</span>' :
                        '<span class="badge badge-success" style="font-size:0.7rem;">LIVE</span>'
                }
                    </td>
                    <td>
                        <div style="display: flex; gap: 0.3rem;">
                            ${!status.is_disqualified ? `
                                <button class="btn btn-secondary" onclick="Admin.disqualifyParticipant('${status.participant_id}')" style="${compactBtnStyle} color: var(--error); border-color: var(--error);" title="Disqualify">
                                    <i class="fa-solid fa-ban"></i> DQ
                                </button>
                            ` : `
                                <button class="btn btn-primary" onclick="Admin.allowExtraViolations('${status.participant_id}')" style="${compactBtnStyle} background: var(--success); border-color: var(--success);" title="Allow +5 Actions">
                                    <i class="fa-solid fa-check"></i> +5
                                </button>
                            `}
                            <button class="btn btn-secondary" onclick="Admin.resetViolations('${status.participant_id}')" style="${compactBtnStyle}" title="Reset Violations">
                                <i class="fa-solid fa-rotate-left"></i>
                            </button>
                            <button class="btn btn-secondary" onclick="Admin.resetProgress('${status.participant_id}')" style="${compactBtnStyle} background: #eff6ff; border: 1px solid #bfdbfe; color: #1d4ed8;" title="FULL RESET (Progress & Violations)">
                                <i class="fa-solid fa-trash-can-arrow-up"></i>
                            </button>
                            <button class="btn" onclick="Admin.forceSubmitParticipant('${status.participant_id}')" title="Force Submit & Exit" style="${compactBtnStyle} background: #fff; border: 1px solid #d1d5db; color: #4b5563;">
                                <i class="fa-solid fa-paper-plane"></i>
                            </button>
                        </div>
                    </td>
                </tr>
    `;
        }).join('');
    },

    async toggleProctoring(enabled) {
        try {
            const res = await API.request(`/proctoring/config/${this.activeContestId}`, 'PUT', { enabled });
            if (res.success) {
                this.showNotification(`Proctoring ${enabled ? 'enabled' : 'disabled'}`, enabled ? 'success' : 'warning');
                this.loadProctoringView();
            }
        } catch (e) {
            console.error('Error toggling proctoring:', e);
            alert('Failed to toggle proctoring');
        }
    },

    async resetProgress(pid) {
        if (!confirm(`⚠️ DANGER: FULL RESET for ${pid}?\n\nThis will DELETE ALL submissions, level progress, and violations.\nThe participant will start from Level 1 as if new.`)) return;

        try {
            const res = await API.request('/proctoring/action/reset-progress', 'POST', {
                participant_id: pid,
                contest_id: this.activeContestId
            });

            if (res.success) {
                this.showNotification(`Progress reset for ${pid}`, 'success');
                this.loadProctoringView();
            }
        } catch (e) {
            alert("Failed to reset progress: " + e.message);
        }
    },

    async forceSubmitParticipant(pid) {
        if (!confirm(`Are you sure you want to FORCE SUBMIT for participant ${pid}? This will exit their fullscreen and lock their test.`)) return;
        try {
            await API.request(`/contest/${this.activeContestId}/force-submit/${pid}`, 'POST');
            this.showNotification(`Force-submit signal sent to ${pid}`, 'warning');
            this.loadProctoringView();
        } catch (e) {
            console.error(e);
            alert("Failed to force submit participant");
        }
    },

    async allowExtraViolations(pid) {
        if (!confirm(`Allow ${pid} to continue with 5 extra violations?`)) return;
        try {
            await API.request('/proctoring/action/allow-extra', 'POST', {
                participant_id: pid,
                contest_id: this.activeContestId,
                amount: 5
            });
            this.showNotification("Participant Allowed (+5 Violations)", "success");
            this.loadProctoringView();
        } catch (e) {
            alert("Failed to allow: " + e.message);
        }
    },

    showProctoringConfig() {
        const config = this.currentProctoringConfig;
        if (!config) return;

        const modal = document.createElement('div');
        modal.id = 'proctoring-config-modal';
        modal.className = 'modal-overlay';
        modal.style.display = 'flex';
        modal.style.zIndex = '1000';
        modal.style.position = 'fixed';
        modal.style.top = '0';
        modal.style.left = '0';
        modal.style.width = '100%';
        modal.style.height = '100%';
        modal.style.justifyContent = 'center';
        modal.style.alignItems = 'center';

        modal.innerHTML = `
            <div class="modal-content large" style="max-height: 90vh;">
                <div class="modal-header">
                    <h2><i class="fa-solid fa-cog"></i> Proctoring Configuration</h2>
                    <button class="btn-icon" onclick="document.getElementById('proctoring-config-modal').remove()" style="font-size: 1.2rem; background: none; border: none; cursor: pointer; color:#64748b;">
                        <i class="fa-solid fa-times"></i>
                    </button>
                </div>
                
                <div class="modal-body">
                    <form id="proctoring-config-form" onsubmit="event.preventDefault(); Admin.saveProctoringConfig();">
                        <!-- General Settings -->
                        <div style="margin-bottom: 2rem;">
                            <h3 style="margin-bottom: 1rem; color: var(--primary-600); font-size:1.1rem;">General Settings</h3>
                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
                                <div>
                                    <label>Max Violations</label>
                                    <input type="number" class="input" id="config-max-violations" value="${config.max_violations}" min="1" max="50">
                                </div>
                                <div>
                                    <label>Warning Threshold</label>
                                    <input type="number" class="input" id="config-warning-threshold" value="${config.warning_threshold}" min="1" max="50">
                                </div>
                            </div>
                            <div style="margin-top: 1rem;">
                                <label style="display: flex; align-items: center; gap: 0.5rem; cursor:pointer;">
                                    <input type="checkbox" id="config-auto-disqualify" ${config.auto_disqualify ? 'checked' : ''}>
                                    Auto-Disqualify participants who exceed max violations
                                </label>
                            </div>
                        </div>

                        <!-- Monitoring Settings -->
                        <div style="margin-bottom: 1rem;">
                            <h3 style="margin-bottom: 1rem; color: var(--primary-600); font-size:1.1rem;">Monitoring Settings</h3>
                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
                                <label style="display: flex; align-items: center; gap: 0.5rem; cursor:pointer;">
                                    <input type="checkbox" id="config-track-tab-switches" ${config.track_tab_switches ? 'checked' : ''}>
                                    Track Tab Switches
                                </label>
                                <label style="display: flex; align-items: center; gap: 0.5rem; cursor:pointer;">
                                    <input type="checkbox" id="config-track-focus-loss" ${config.track_focus_loss ? 'checked' : ''}>
                                    Track Focus Loss
                                </label>
                                <label style="display: flex; align-items: center; gap: 0.5rem; cursor:pointer;">
                                    <input type="checkbox" id="config-block-copy" ${config.block_copy ? 'checked' : ''}>
                                    Block Copy
                                </label>
                                <label style="display: flex; align-items: center; gap: 0.5rem; cursor:pointer;">
                                    <input type="checkbox" id="config-block-paste" ${config.block_paste ? 'checked' : ''}>
                                    Block Paste
                                </label>
                                <label style="display: flex; align-items: center; gap: 0.5rem; cursor:pointer;">
                                    <input type="checkbox" id="config-detect-screenshot" ${config.detect_screenshot ? 'checked' : ''}>
                                    Detect Screenshots
                                </label>
                            </div>
                        </div>
                    </form>
                </div>

                <div class="modal-actions">
                    <button type="button" class="btn btn-secondary" onclick="document.getElementById('proctoring-config-modal').remove()">Cancel</button>
                    <button type="button" class="btn btn-primary" onclick="Admin.saveProctoringConfig()">
                        <i class="fa-solid fa-save"></i> Save Configuration
                    </button>
                </div>
            </div>
    `;
        document.body.appendChild(modal);
    },

    async saveProctoringConfig() {
        const config = {
            enabled: this.currentProctoringConfig.enabled,
            max_violations: parseInt(document.getElementById('config-max-violations').value),
            warning_threshold: parseInt(document.getElementById('config-warning-threshold').value),
            auto_disqualify: document.getElementById('config-auto-disqualify').checked,
            track_tab_switches: document.getElementById('config-track-tab-switches').checked,
            track_focus_loss: document.getElementById('config-track-focus-loss').checked,
            block_copy: document.getElementById('config-block-copy').checked,
            block_paste: document.getElementById('config-block-paste').checked,
            detect_screenshot: document.getElementById('config-detect-screenshot').checked
        };

        try {
            const res = await API.request(`/proctoring/config/${this.activeContestId}`, 'PUT', config);
            if (res.success) {
                this.showNotification('Configuration saved successfully', 'success');
                document.getElementById('proctoring-config-modal').remove();
                this.loadProctoringView();
            }
        } catch (e) {
            console.error('Error saving config:', e);
            alert('Failed to save configuration');
        }
    },

    async disqualifyParticipant(participantId) {
        const reason = prompt('Reason for disqualification:');
        if (!reason) return;

        try {
            const res = await API.request('/proctoring/action/disqualify', 'POST', {
                participant_id: participantId,
                contest_id: this.activeContestId,
                reason
            });

            if (res.success) {
                this.showNotification('Participant disqualified', 'success');
                this.loadProctoringView();
            }
        } catch (e) {
            console.error('Error disqualifying participant:', e);
            alert('Failed to disqualify participant');
        }
    },

    async reinstateParticipant(participantId) {
        if (!confirm('Reinstate this participant?')) return;

        try {
            const res = await API.request('/proctoring/action/reinstate', 'POST', {
                participant_id: participantId,
                contest_id: this.activeContestId
            });

            if (res.success) {
                this.showNotification('Participant reinstated', 'success');
                this.loadProctoringView();
            }
        } catch (e) {
            console.error('Error reinstating participant:', e);
            alert('Failed to reinstate participant');
        }
    },

    async resetViolations(participantId) {
        if (!confirm('Reset all violations for this participant?')) return;

        try {
            const res = await API.request('/proctoring/action/reset-violations', 'POST', {
                participant_id: participantId,
                contest_id: this.activeContestId
            });

            if (res.success) {
                this.showNotification('Violations reset successfully', 'success');
                this.loadProctoringView();
            }
        } catch (e) {
            console.error('Error resetting violations:', e);
            alert('Failed to reset violations');
        }
    },

    async exportProctoringReport() {
        try {
            const res = await API.request(`/proctoring/export/${this.activeContestId}`);

            if (res.success) {
                const dataStr = JSON.stringify(res.report, null, 2);
                const dataBlob = new Blob([dataStr], { type: 'application/json' });
                const url = URL.createObjectURL(dataBlob);
                const link = document.createElement('a');
                link.href = url;
                link.download = `proctoring-report-${this.activeContestId}-${new Date().toISOString()}.json`;
                link.click();
                URL.revokeObjectURL(url);

                this.showNotification('Report exported successfully', 'success');
            }
        } catch (e) {
            console.error('Error exporting report:', e);
            alert('Failed to export report');
        }
    },

    async startWaitCountdown(event) {
        const waitTime = document.getElementById('wait-time-selector').value;
        if (!confirm(`Trigger wait time countdown for ${waitTime} minutes? Participants will see a blurred screen with a timer.`)) return;

        try {
            await API.request(`/contest/${this.activeContestId}/advance-level`, 'POST', { wait_time: waitTime });
            this.showNotification(`Countdown started for ${waitTime} minutes`, 'success');

            // Optionally update UI to show countdown is active
            const btn = event.target;
            const originalText = btn.innerHTML;
            btn.disabled = true;
            btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Countdown Active...`;

            // Re-enable after a few seconds or when level actually starts
            setTimeout(() => {
                btn.disabled = false;
                btn.innerHTML = originalText;
            }, 5000);

        } catch (e) {
            console.error(e);
            alert("Failed to start countdown");
        }
    },



    async resetLevelStats() {
        if (!confirm("Are you sure? This will reset local solved status and progression counters (visual only for this session).")) return;
        localStorage.removeItem('dm_solved');
        this.showNotification("Level stats reset locally", "info");
        window.location.reload();
    },

    async registerAdmin() {
        const u = document.getElementById('reg-username').value;
        const e = document.getElementById('reg-email').value;
        const p = document.getElementById('reg-password').value;
        const cp = document.getElementById('reg-confirm-password').value;
        const f = document.getElementById('reg-fullname').value;

        // Validation
        if (!u || !e || !p || !cp) return alert("All fields are required");

        // Email Validation
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(e)) return alert("Invalid email format");

        // Password Match
        if (p !== cp) return alert("❌ Passwords do not match");

        try {
            const res = await API.request('/auth/admin/register', 'POST', {
                username: u,
                email: e,
                password: p,
                full_name: f
            });
            if (res.success) {
                alert(res.message || "Registration Successful! Please wait for approval.");
                document.getElementById('register-form').style.display = 'none';
                document.getElementById('login-form').style.display = 'block';
            } else {
                alert(res.error || 'Failed');
            }
        } catch (e) { alert(e.message); }
    },

    async loadPendingAdminsView() {
        this.currentView = 'pending_admins';
        const main = document.querySelector('.admin-main');
        main.innerHTML = '<h2>Loading Pending Admins...</h2>';
        try {
            const res = await API.request('/auth/admin/pending');
            const list = res.pending || [];
            main.innerHTML = `
                <div class="admin-header"><h1>Pending Admin Approvals</h1></div>
                <div class="bg-white rounded-xl shadow-sm" style="padding: 1.5rem;">
                    <table class="admin-table">
                        <thead><tr><th>Username</th><th>Name</th><th>Date</th><th>Action</th></tr></thead>
                        <tbody>${list.length ? list.map(a => `<tr>
                            <td>${a.username}</td><td>${a.full_name}</td><td>${new Date(a.created_at).toLocaleDateString()}</td>
                            <td>
                                <button class="btn btn-sm btn-primary" onclick="Admin.approveAdmin('${a.user_id}', 'APPROVE')">Approve</button>
                                <button class="btn btn-sm btn-secondary" onclick="Admin.approveAdmin('${a.user_id}', 'REJECT')">Reject</button>
                            </td>
                        </tr>`).join('') : '<tr><td colspan="4">No pending requests.</td></tr>'}</tbody>
                    </table>
                </div>
            `;
        } catch (e) { main.innerHTML = `<h2 style="color:red">Error: ${e.message}</h2>`; }
    },

    async approveAdmin(uid, action) {
        if (!confirm(action + " this admin?")) return;
        try {
            const res = await API.request('/auth/admin/approve', 'POST', { user_id: uid, action });
            if (res.success) { this.showNotification('Admin ' + action + 'D', 'success'); this.loadPendingAdminsView(); }
        } catch (e) { alert(e.message); }
    },

    logout() {
        localStorage.removeItem('admin_token');
        window.location.reload();
    }
};


Admin.showEditLevelModal = async function (level) {
    // Find existing round data
    const round = (this.currentRounds || []).find(r => r.round_number == level);
    const timeLimit = round ? round.time_limit_minutes : 30;
    const allowedLanguage = round ? (round.allowed_language || 'python') : 'python';

    // Fetch questions for this level to allow reordering
    let questions = [];
    try {
        const qRes = await API.request(`/contest/questions?contest_id=${this.activeContestId}&level=${level}`);
        questions = qRes.questions || [];
    } catch (e) {
        console.error("Failed to load questions", e);
    }

    const modalHtml = `
        <div id="edit-level-modal" class="modal-overlay" style="display:flex; justify-content:center; align-items:center; position:fixed; top:0; left:0; width:100%; height:100%; z-index:9000;">
            <div class="modal-content medium" style="max-height:85vh; display:flex; flex-direction:column;">
                <div class="modal-header">
                    <h3>Edit Level ${level} Configuration</h3>
                </div>
                
                <div class="modal-body">
                    <div style="display:flex; gap: 1rem; margin-bottom: 1.5rem;">
                        <div style="flex:1;">
                            <label>Time Duration (Minutes)</label>
                            <input type="number" id="edit-lvl-time" class="input" style="width:100%;" value="${timeLimit}">
                        </div>
                        <div style="flex:1;">
                            <label>Allowed Language</label>
                            <select id="edit-lvl-lang" class="input" style="width:100%;">
                                <option value="python" ${allowedLanguage === 'python' ? 'selected' : ''}>Python</option>
                                <option value="javascript" ${allowedLanguage === 'javascript' ? 'selected' : ''}>JavaScript (Node.js)</option>
                                <option value="c" ${allowedLanguage === 'c' ? 'selected' : ''}>C (GCC)</option>
                                <option value="cpp" ${allowedLanguage === 'cpp' ? 'selected' : ''}>C++ (G++)</option>
                                <option value="java" ${allowedLanguage === 'java' ? 'selected' : ''}>Java</option>
                            </select>
                        </div>
                    </div>
                    
                    <label>Question Order</label>
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.5rem;">
                        <p style="font-size:0.8rem; color:gray; margin:0;">Drag to reorder questions.</p>
                        <button class="btn btn-sm btn-primary" onclick="Admin.showAddQuestionModal(${level})"><i class="fa-solid fa-plus"></i> Add Question</button>
                    </div>
                    
                    <div id="lvl-q-list" class="participant-list" style="margin-bottom:1.5rem;">
                        ${questions.length > 0 ? questions.map((q, idx) => `
                            <div class="list-item" data-id="${q.id}" style="cursor:move;">
                                <div style="display:flex; align-items:center; flex:1;">
                                    <span style="margin-right:0.75rem; color:#cbd5e1;"><i class="fa-solid fa-grip-vertical"></i></span>
                                    <div>
                                        <div style="font-weight:500;">${q.title}</div>
                                        <div style="font-size:0.75rem; color:gray;">ID: ${q.number} | ${q.difficulty}</div>
                                    </div>
                                </div>
                                <button class="btn-icon" onclick='event.stopPropagation(); Admin.showQuestionFormModal(${level}, ${JSON.stringify(q).replace(/'/g, "&#39;")})' title="Edit Question">
                                    <i class="fa-solid fa-pen"></i>
                                </button>
                            </div>
                        `).join('') : '<p style="padding:1rem; text-align:center; color:gray;">No questions assigned to this level yet.</p>'}
                    </div>
                </div>
                
                <div class="modal-actions">
                    <button class="btn btn-secondary" onclick="document.getElementById('edit-level-modal').remove()">Cancel</button>
                    <button class="btn btn-primary" onclick="Admin.saveLevelConfig(${level})">Save Changes</button>
                </div>
            </div>
        </div>
    `;
    document.body.insertAdjacentHTML('beforeend', modalHtml);

    // Init Sortable
    const el = document.getElementById('lvl-q-list');
    if (el && questions.length > 0) {
        new Sortable(el, { animation: 150 });
    }
};

Admin.saveLevelConfig = async function (level) {
    const timeLimit = document.getElementById('edit-lvl-time').value;
    const allowedLanguage = document.getElementById('edit-lvl-lang').value;

    // Get question order
    const qItems = document.querySelectorAll('#lvl-q-list .list-item');
    const questionsOrder = [];
    qItems.forEach((item, index) => {
        questionsOrder.push({
            id: item.getAttribute('data-id'),
            number: index + 1
        });
    });

    try {
        await API.request(`/contest/${this.activeContestId}/rounds/${level}`, 'PUT', {
            time_limit: timeLimit,
            allowed_language: allowedLanguage,
            questions_order: questionsOrder
        });

        document.getElementById('edit-level-modal').remove();
        this.showNotification(`Level ${level} updated successfully`, 'success');

        // Silent Update: Fetch latest rounds to keep local state in sync without UI reset
        try {
            const rRes = await API.request(`/contest/${this.activeContestId}/rounds`);
            if (rRes.rounds) {
                this.currentRounds = rRes.rounds;
                // Update the specific round card in the list if visible
                // Or just rely on next interaction to use fresh data
                // We could re-render just the rounds list:
                const roundsListEl = document.getElementById('rounds-list');
                if (roundsListEl) {
                    // We won't re-render full HTML to avoid disrupting any other state,
                    // but we should ideally update the time limit displayed on the card.
                    const roundCard = roundsListEl.querySelector(`[data-id="${level}"]`) ||
                        Array.from(roundsListEl.children).find(el => el.innerText.includes(`Level ${level}`));
                    // Since data-id might be round ID not number, need to match carefully.
                    // But typically loadContestDetail used round.id. Here 'level' is round_number.
                    // Let's just update local state. The user said "Do not navigate".
                }
            }
        } catch (ignore) { }

    } catch (e) {
        console.error(e);
        alert("Failed to update level configuration");
    }
};

Admin.showQuestionFormModal = function (level, questionData = null) {
    const isEdit = !!questionData;
    const title = isEdit ? questionData.title : '';
    const desc = isEdit ? questionData.description : '';
    const code = isEdit ? (questionData.boilerplate && questionData.boilerplate.python ? questionData.boilerplate.python : (questionData.buggy_code || '')) : '';
    const diff = isEdit ? questionData.difficulty : 'medium';
    // Use 'id' (UUID if from bank?) but the map above uses 'id'. Wait, backend returns 'id' (int)?
    // From contest/questions API, it returns questions with 'id' column from DB which is int.
    const qid = isEdit ? questionData.id : null;

    const modalHtml = `
        <div id="q-form-modal" class="modal-overlay" style="display:flex; justify-content:center; align-items:center; position:fixed; top:0; left:0; width:100%; height:100%; z-index:9500;">
            <div class="modal-content medium" style="max-height:90vh; display:flex; flex-direction:column;">
                <div class="modal-header">
                    <h3>${isEdit ? 'Edit Question' : 'Add New Question'} (Level ${level})</h3>
                </div>
                
                <div class="modal-body">
                    <div style="display:grid; grid-template-columns: 3fr 1fr; gap:1rem; margin-bottom:1rem;">
                        <div>
                            <label>Title</label>
                            <input type="text" id="q-form-title" class="input" style="width:100%;" value="${title}" placeholder="e.g. Broken Fibonacci">
                        </div>
                        <div>
                            <label>Difficulty</label>
                            <select id="q-form-diff" class="input" style="width:100%;">
                                <option value="easy" ${diff === 'easy' ? 'selected' : ''}>Easy</option>
                                <option value="medium" ${diff === 'medium' ? 'selected' : ''}>Medium</option>
                                <option value="hard" ${diff === 'hard' ? 'selected' : ''}>Hard</option>
                            </select>
                        </div>
                    </div>

                    <div style="margin-bottom:1rem;">
                        <label>Description (Markdown supported)</label>
                        <textarea id="q-form-desc" class="input" style="width:100%; height:100px; font-family:inherit;">${desc}</textarea>
                    </div>

                    <div style="margin-bottom:1.5rem;">
                        <label>Buggy Code (Python)</label>
                        <textarea id="q-form-code" class="input" style="width:100%; height:150px; font-family:'Fira Code', monospace; font-size:0.9rem; background:#f8fafc;">${code}</textarea>
                    </div>
                </div>

                <div class="modal-actions">
                    <button class="btn btn-secondary" onclick="document.getElementById('q-form-modal').remove()">Cancel</button>
                    <button class="btn btn-primary" onclick="Admin.saveLevelQuestion(${level}, ${qid})">${isEdit ? 'Update Question' : 'Create Question'}</button>
                </div>
            </div>
        </div>
    `;
    document.body.insertAdjacentHTML('beforeend', modalHtml);
};

Admin.saveLevelQuestion = async function (level, qid) {
    const title = document.getElementById('q-form-title').value;
    const desc = document.getElementById('q-form-desc').value;
    const code = document.getElementById('q-form-code').value;
    const diff = document.getElementById('q-form-diff').value;

    if (!title) return alert("Title is required");

    const payload = {
        title,
        description: desc,
        boilerplate: { python: code }, // Match backend structure expectation
        difficulty: diff,
        points: (diff === 'easy' ? 10 : (diff === 'medium' ? 20 : 30))
    };

    try {
        let res;
        if (qid) {
            // Edit
            res = await API.request(`/contest/${this.activeContestId}/rounds/${level}/question/${qid}`, 'PUT', payload);
        } else {
            // Create
            res = await API.request(`/contest/${this.activeContestId}/rounds/${level}/question`, 'POST', payload);
        }

        if (res.success) {
            document.getElementById('q-form-modal').remove();
            this.showNotification('Question saved successfully', 'success');

            // Refresh the questions list in the PARENT modal (Edit Level Modal) without closing it
            try {
                const listContainer = document.getElementById('lvl-q-list');
                if (listContainer) {
                    // Show loading state
                    listContainer.innerHTML = '<p style="padding:1rem; text-align:center; color:gray;">Refreshing list...</p>';

                    // Fetch fresh questions
                    const qRes = await API.request(`/contest/questions?contest_id=${this.activeContestId}&level=${level}`);
                    const questions = qRes.questions || [];

                    // Re-render list
                    listContainer.innerHTML = questions.length > 0 ? questions.map((q, idx) => `
                        <div class="list-item" data-id="${q.id}" style="cursor:move;">
                            <div style="display:flex; align-items:center; flex:1;">
                                <span style="margin-right:0.75rem; color:#cbd5e1;"><i class="fa-solid fa-grip-vertical"></i></span>
                                <div>
                                    <div style="font-weight:500;">${q.title}</div>
                                    <div style="font-size:0.75rem; color:gray;">ID: ${q.number} | ${q.difficulty}</div>
                                </div>
                            </div>
                            <button class="btn-icon" onclick='event.stopPropagation(); Admin.showQuestionFormModal(${level}, ${JSON.stringify(q).replace(/'/g, "&#39;")})' title="Edit Question">
                                <i class="fa-solid fa-pen"></i>
                            </button>
                        </div>
                    `).join('') : '<p style="padding:1rem; text-align:center; color:gray;">No questions assigned to this level yet.</p>';
                }
            } catch (ignore) { console.error(ignore); }
        }
    } catch (e) {
        console.error(e);
        alert("Failed to save question: " + e.message);
    }
};

// Login Handler
document.getElementById('login-form').addEventListener('submit', async (e) => {
    e.preventDefault();

    // Get credentials (in demo mode, any credentials work)
    const username = document.getElementById('admin-username').value;
    const password = document.getElementById('admin-password').value;

    try {
        // Call backend admin login API
        const response = await fetch('/api/auth/admin/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });

        const data = await response.json();

        if (data.success && data.token) {
            // Store the real JWT token
            localStorage.setItem('admin_token', data.token);
            document.getElementById('admin-login').style.display = 'none';
            document.getElementById('admin-dashboard').style.display = 'block';

            // Slight timeout to ensure DOM is ready/visible
            setTimeout(() => Admin.init(), 100);
        } else {
            alert(data.error || 'Login failed. Please try again.');
        }
    } catch (error) {
        console.error('Login error:', error);
        alert('Login failed. Please check your connection.');
    }
});

// Auto-init if token exists (for refresh)
if (localStorage.getItem('admin_token')) {
    document.getElementById('admin-login').style.display = 'none';
    document.getElementById('admin-dashboard').style.display = 'block';
    Admin.init();
}

Admin.activateLevel = async function (level) {
    if (!confirm('Activate Level ' + level + '?')) return;
    try {
        await API.request('/contest/' + this.activeContestId + '/level/' + level + '/activate', 'POST');
        this.showNotification('Level ' + level + ' Activated', 'success');
        this.loadDashboard();
    } catch (e) { alert('Failed: ' + e.message); }
};

Admin.completeLevel = async function (level) {
    if (!confirm('Complete Level ' + level + '?')) return;
    try {
        await API.request('/contest/' + this.activeContestId + '/level/' + level + '/complete', 'POST');
        this.showNotification('Level ' + level + ' Completed', 'success');
        this.loadDashboard();
    } catch (e) { alert('Failed: ' + e.message); }
};

