/**
 * auth.js
 * Authentication logic for Participants
 */

document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('login-form');
    const loginSection = document.getElementById('login-section');
    const dashboardContainer = document.getElementById('dashboard-container');

    // Check if already logged in
    const session = Storage.get('session');
    if (session) {
        enterDashboard(session.participant);
    } else {
        // Show login
        if (loginSection) loginSection.style.display = 'flex';
    }

    if (loginForm) {
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const pid = document.getElementById('participant-id').value;

            const response = await API.login(pid);

            if (response && response.success) {
                const user = response.participant;
                Storage.set('session', { participant: user, token: response.token });
                enterDashboard(user);
                Toast.show(`Welcome, ${user.name}!`, 'success');
            } else {
                Toast.show(response.error || 'Invalid Participant ID. Admin must create it via Admin Panel.', 'error');
            }
        });
    }

    async function enterDashboard(user) {
        if (loginSection) loginSection.style.display = 'none';
        const levelSelection = document.getElementById('level-selection-section');
        if (levelSelection) {
            levelSelection.style.display = 'block';
        }

        // Hide Game UI just in case
        const gameWrapper = document.getElementById('game-ui-wrapper');
        if (gameWrapper) gameWrapper.style.display = 'none';

        // Initialize other modules
        if (window.Contest) {
            await window.Contest.init(user);
        }
        if (window.Proctoring && window.Contest && window.Contest.activeContestId) {
            window.Proctoring.init(window.Contest.activeContestId);
        }
    }
});
window.Auth = {
    logout() {
        Storage.remove('session');
        window.location.href = 'index.html';
    }
};
