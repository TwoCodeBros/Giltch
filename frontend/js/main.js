/**
 * main.js
 * Core utilities for Debug Marathon
 */

// Format seconds into HH:MM:SS
function formatTime(seconds) {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

// Toast Notification System
const Toast = {
    show(message, type = 'info') {
        const container = document.getElementById('toast-container');
        if (!container) return;

        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        
        // Icon based on type
        let icon = 'fa-info-circle';
        if (type === 'success') icon = 'fa-check-circle';
        if (type === 'warning') icon = 'fa-exclamation-triangle';
        if (type === 'error') icon = 'fa-ban';

        toast.innerHTML = `
            <i class="fa-solid ${icon}" style="font-size: 1.25rem;"></i>
            <div>
                <div style="font-weight: 600; text-transform: capitalize;">${type}</div>
                <div style="font-size: 0.875rem; color: var(--text-secondary);">${message}</div>
            </div>
        `;

        container.appendChild(toast);

        // Auto remove after 4 seconds
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(100%)';
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    }
};

// Local Storage Helper
const Storage = {
    get(key) {
        try {
            return JSON.parse(localStorage.getItem(`dm_${key}`));
        } catch {
            return null;
        }
    },
    set(key, value) {
        localStorage.setItem(`dm_${key}`, JSON.stringify(value));
    },
    remove(key) {
        localStorage.removeItem(`dm_${key}`);
    }
};
