/**
 * proctoring.js
 * Advanced Frontend Security & Violation Tracking System
 * - Tab Switch Detection
 * - Focus Loss Detection
 * - Fullscreen Enforcement
 * - DevTools Detection
 * - Copy/Paste/Right-Click Blocking
 */

window.Proctoring = {
    violations: 0,
    isActive: false,
    levelActive: false,
    strictLockActive: false,
    config: {
        max_violations: 20,
        track_tab_switches: true,
        track_focus_loss: true,
        block_copy: true,
        block_paste: true,
        block_right_click: true,
        detect_screenshot: true,
        detect_devtools: true
    },

    // State tracking
    lastInteractionTime: 0,
    enforceInterval: null,
    devToolsInterval: null,

    async init(contestId) {
        if (this.isActive) return;
        this.isActive = true;
        console.log("Initializing Proctoring System...");

        // Try to fetch config, fallback to strict defaults
        try {
            if (contestId) {
                const res = await API.request(`/proctoring/config/${contestId}`);
                if (res.success && res.config) {
                    this.config = { ...this.config, ...res.config };
                }
            }
        } catch (e) {
            console.warn("Proctoring config fetch failed, using defaults.");
        }

        this.bindEvents();
        this.startDevToolsDetection();
        this.updateBadge();
    },

    reset() {
        this.violations = 0;
        this.levelActive = true;
        this.updateBadge();
        this.dismissOverlay();
        // Clear any previous blurred state
        document.body.classList.remove('security-blur');
    },

    bindEvents() {
        // Interaction tracking to debounce false positives
        ['mousedown', 'keydown', 'click', 'mousemove'].forEach(evt => {
            window.addEventListener(evt, () => { this.lastInteractionTime = Date.now(); }, true);
        });

        // 1. Tab Switch & Visibility
        document.addEventListener('visibilitychange', () => {
            if (!this.shouldEnforce()) return;

            if (document.hidden) {
                this.recordViolation('TAB_SWITCH', true, 'Tab switched or browser minimized');
                this.triggerSecurityLockout('Tab Switch Detected');
            } else {
                // Returned to tab
                setTimeout(() => this.checkFullscreen(), 500);
            }
        });

        // 2. Window Focus (Blur)
        window.addEventListener('blur', () => {
            if (!this.shouldEnforce()) return;

            // Immediate blur effect to prevent screenshots of content
            document.body.classList.add('security-blur');

            // Small grace period for legitimate system popups or fast alt-tabs
            // but we engage visual lockout immediately
            setTimeout(() => {
                if (!document.hasFocus() && this.shouldEnforce()) {
                    this.recordViolation('FOCUS_LOST', true, 'Window focus lost (Alt+Tab or outside click)');
                    this.triggerSecurityLockout('Focus Lost! Return Immediately.');
                }
            }, 500);
        });

        window.addEventListener('focus', () => {
            if (this.shouldEnforce()) {
                document.body.classList.remove('security-blur');
                this.checkFullscreen();
            }
        });

        // 3. Fullscreen Enforcement
        document.addEventListener('fullscreenchange', () => {
            if (!this.shouldEnforce()) return;
            if (!document.fullscreenElement) {
                this.recordViolation('FULLSCREEN_EXIT', true, 'Exited fullscreen mode');
                this.triggerSecurityLockout('Fullscreen is Mandatory');
            }
        });

        // 4. Keyboard Shortcuts & PrintScreen
        window.addEventListener('keydown', (e) => {
            if (!this.shouldEnforce()) return;

            // Detect PrintScreen
            if (e.key === 'PrintScreen' || e.code === 'PrintScreen' || e.keyCode === 44) {
                // Obscure screen immediately
                document.body.style.filter = 'blur(20px)';
                setTimeout(() => document.body.style.filter = '', 1000); // Restore after 1s

                this.recordViolation('SCREENSHOT_ATTEMPT', true, 'Screenshot key detected');
                e.preventDefault();
                return;
            }

            // Block Inspect Element / DevTools shortcuts
            // Ctrl+Shift+I, Ctrl+Shift+J, Ctrl+U, F12
            if (e.key === 'F12' ||
                (e.ctrlKey && e.shiftKey && (e.key === 'I' || e.key === 'J' || e.key === 'C')) ||
                (e.ctrlKey && e.key === 'u')) {
                e.preventDefault();
                this.recordViolation('DEV_TOOLS_ATTEMPT', true, 'DevTools shortcut blocked');
                return;
            }

            // Block Copy/Paste/Cut shortcuts if strict
            if (e.ctrlKey && ['c', 'v', 'x', 'a'].includes(e.key.toLowerCase())) {
                if (this.config.block_copy) {
                    e.preventDefault();
                    this.recordViolation('CLIPBOARD_SHORTCUT', true, 'Clipboard shortcut blocked');
                }
            }

            // Alt+Tab detection heuristic (Alt key hold)
            if (e.altKey && e.key === 'Tab') {
                this.recordViolation('TAB_SWITCH_ATTEMPT', true, 'Alt+Tab detected');
            }
        }, true);

        // 5. Mouse Restrictions
        document.addEventListener('contextmenu', (e) => {
            if (this.shouldEnforce() && this.config.block_right_click) {
                e.preventDefault();
                this.recordViolation('RIGHT_CLICK', false, 'Right click blocked');
            }
        }, true);

        // Prevent selection if configured
        document.addEventListener('selectstart', (e) => {
            if (this.shouldEnforce() && this.config.block_copy) {
                const target = e.target;
                // Allow selection in editor if needed, but generally block
                // If target is inside ace-editor, we might allow it? 
                // For now, strict block unless logic refined.
                // e.preventDefault(); 
            }
        });
    },

    shouldEnforce() {
        return this.levelActive || this.strictLockActive;
    },

    triggerSecurityLockout(msg) {
        this.showOverlay(msg);
        this.enterFullscreen(); // Try to force back
        document.body.classList.add('security-blur');
    },

    showOverlay(msg) {
        const overlay = document.getElementById('proctor-overlay');
        if (overlay) {
            overlay.style.display = 'flex';
            const reqText = overlay.querySelector('.proctor-alert p') || overlay.querySelector('p');
            if (reqText) reqText.innerText = msg;
        }
    },

    dismissOverlay() {
        const overlay = document.getElementById('proctor-overlay');
        if (overlay) overlay.style.display = 'none';
        document.body.classList.remove('security-blur');
    },

    async recordViolation(type, countPenalty, desc) {
        if (!this.shouldEnforce()) return;

        console.log(`[PROCTORING] Violation: ${type} - ${desc}`);

        // Anti-bounce for fast occurring events
        const now = Date.now();
        if (now - this.lastViolationTime < 200 && type === this.lastViolationType) return; // Debounce same violation

        this.lastViolationTime = now;
        this.lastViolationType = type;

        if (countPenalty) {
            this.violations++;
            this.updateBadge();

            // Visual Flash
            if (document.getElementById('game-ui-wrapper')) {
                document.getElementById('game-ui-wrapper').style.border = "4px solid red";
                setTimeout(() => {
                    const el = document.getElementById('game-ui-wrapper');
                    if (el) el.style.border = "none";
                }, 500);
            }

            // Send to Backend
            try {
                const session = Storage.get('session');
                const pId = session?.participant?.participant_id;
                const c = window.Contest || {};

                // Don't await this, let it fire and forget to keep UI snappy
                API.request('/proctoring/violation', 'POST', {
                    violation_type: type,
                    description: desc,
                    total_violations: this.violations,
                    participant_id: pId,
                    contest_id: c.activeContestId,
                    question_id: c.currentQId !== undefined && c.questions ? c.questions[c.currentQId]?.id : null,
                    level: c.currentLevel,
                    timestamp: new Date().toISOString()
                });
            } catch (e) { console.error("Proctoring Sync Error", e); }

            if (this.violations >= this.config.max_violations) {
                this.handleDisqualification();
            }
        }
    },

    updateBadge() {
        const el = document.getElementById('violation-count');
        if (el) {
            el.innerText = `${this.violations} Violations`;
            el.className = 'violation-badge';
            if (this.violations > 0) el.classList.add('warning');
            if (this.violations >= 5) el.classList.add('danger');
        }
    },

    checkFullscreen() {
        if (!document.fullscreenElement && this.shouldEnforce()) {
            this.triggerSecurityLockout("Fullscreen is required to continue.");
        }
    },

    enterFullscreen() {
        try {
            const el = document.documentElement;
            if (el.requestFullscreen) el.requestFullscreen();
            else if (el.mozRequestFullScreen) el.mozRequestFullScreen();
            else if (el.webkitRequestFullscreen) el.webkitRequestFullscreen();
            else if (el.msRequestFullscreen) el.msRequestFullscreen();
        } catch (e) {
            // User interaction might be required
        }
    },

    handleDisqualification() {
        this.levelActive = false;
        alert("You have exceeded the maximum number of violations. You are now disqualified.");
        window.location.href = 'index.html'; // Or kick out flow
        if (window.Contest) window.Contest.logout();
    },

    // DevTools Detection
    startDevToolsDetection() {
        if (this.devToolsInterval) clearInterval(this.devToolsInterval);

        let devtoolsOpen = false;

        this.devToolsInterval = setInterval(() => {
            if (!this.shouldEnforce() || !this.config.detect_devtools) return;

            // Method 1: Threshold
            const threshold = 160;
            const widthThreshold = window.outerWidth - window.innerWidth > threshold;
            const heightThreshold = window.outerHeight - window.innerHeight > threshold;

            if ((widthThreshold || heightThreshold) && !devtoolsOpen) {
                devtoolsOpen = true;
                this.recordViolation('DEVTOOLS_DETECTED', true, 'Developer Tools opened');
            } else if (!(widthThreshold || heightThreshold)) {
                devtoolsOpen = false;
            }
        }, 1000);
    }
};
