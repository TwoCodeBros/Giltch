/**
 * api.js
 * API Communication Layer
 */

const API = {
    BASE_URL: '/api',

    async request(endpoint, method = 'GET', data = null) {
        const headers = { 'Content-Type': 'application/json' };

        // Add auth token if available (for admin/authenticated requests)
        let token = localStorage.getItem('admin_token') || localStorage.getItem('auth_token');

        // If no token found, check for participant session (dm_session)
        if (!token) {
            try {
                const sessionStr = localStorage.getItem('dm_session');
                if (sessionStr) {
                    const session = JSON.parse(sessionStr);
                    if (session && session.token) {
                        token = session.token;
                    }
                }
            } catch (e) {
                console.warn('Failed to parse session token', e);
            }
        }

        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        try {
            const config = { method, headers };
            if (data) config.body = JSON.stringify(data);

            const response = await fetch(`${this.BASE_URL}${endpoint}`, config);

            // Handle Unauthorized (401) or Forbidden (403)
            if (response.status === 401 || response.status === 403) {
                console.warn('Unauthorized/Forbidden request, logging out...');
                localStorage.removeItem('admin_token');
                localStorage.removeItem('auth_token');

                // Only reload if we are on a protected page
                if (window.location.pathname.includes('admin.html') || window.location.pathname.includes('leaderboard.html')) {
                    window.location.reload();
                }
                return { error: 'Unauthorized', status: response.status };
            }

            const result = await response.json();
            return result;
        } catch (error) {
            console.error("API Error:", error);
            if (typeof Toast !== 'undefined') {
                Toast.show('Network Error', 'error');
            }
            return null;
        }
    },

    // Specific endpoints
    async login(participantId) {
        return this.request('/auth/participant/login', 'POST', { participant_id: participantId });
    },

    async submit(code, lang, qId) {
        // Real backend submission
        return this.request('/contest/submit', 'POST', { code, language: lang, question_id: qId });
    }
};
