/**
 * proctoring.js
 * Frontend security and violation tracking
 */

window.Proctoring = {
    violations: 0,
    isActive: false,

    async init(contestId) {
        if (this.isActive) return;
        this.isActive = true;

        // Fetch Config
        try {
            const res = await API.request(`/proctoring/config/${contestId}`);
            if (res.success) {
                this.config = res.config;
                console.log('Proctoring Config Loaded:', this.config);
            }
        } catch (e) {
            console.warn('Failed to load proctoring config, using defaults', e);
            this.config = {
                max_violations: 10,
                track_tab_switches: true,
                track_focus_loss: true,
                block_copy: true,
                block_paste: true,
                block_right_click: true,
                detect_screenshot: true
            };
        }

        if (this.config && this.config.enabled === false) {
            console.log('Proctoring is disabled for this contest.');
            this.isActive = false;
            return;
        }

        // Fetch Current Status (Persistence)
        try {
            const session = Storage.get('session');
            if (session && session.participant) {
                const pid = session.participant.participant_id;
                const statusRes = await API.request(`/proctoring/status/participant/${pid}`);
                if (statusRes.success && statusRes.status) {
                    this.violations = statusRes.status.total_violations || 0;
                    console.log("Restored violations:", this.violations);
                }
            }
        } catch (e) {
            console.warn("Failed to restore violations", e);
        }

        this.updateBadge();
        this.bindEvents();
        console.log('Proctoring System Initialized');
    },

    config: null,

    lastViolationTime: 0,
    levelActive: false, // Only monitor when level is actually playing

    bindEvents() {
        // 1. Tab Switch (Visibility Change)
        document.addEventListener('visibilitychange', () => {
            if (this.levelActive || this.strictLockActive) {
                if (document.hidden) {
                    this.recordViolation('TAB_SWITCH', true, 'Tab switched or minimized');
                    this.showOverlay('Tab switching is bad! Return immediately.');
                } else {
                    // Returned to tab -> Force Fullscreen
                    this.enterFullscreen();
                }
            }
        });

        // 2. Window Blur (Focus Lost)
        window.addEventListener('blur', () => {
            if (this.levelActive || this.strictLockActive) {
                // Ignore if inside editor iframe or interaction
                if (document.activeElement && document.activeElement.tagName === 'IFRAME') return;

                // Ignore if recent screenshot (suppress double count)
                if (this.ignoreBlur) return;

                setTimeout(() => {
                    // Confirm focus is actually lost (debounce)
                    if (!document.hasFocus() && (this.levelActive || this.strictLockActive)) {
                        this.recordViolation('FOCUS_LOST', true, 'Window lost focus');
                        this.showOverlay('Focus lost! Click to return.');
                    }
                }, 500);
            }
        });

        // 3. Focus Regained
        window.addEventListener('focus', () => {
            if ((this.levelActive || this.strictLockActive) && !document.fullscreenElement) {
                this.enterFullscreen();
            }
        });

        // 4. Fullscreen Change
        document.addEventListener('fullscreenchange', () => {
            if (!document.fullscreenElement && (this.levelActive || this.strictLockActive)) {
                this.recordViolation('FULLSCREEN_EXIT', true, 'Exited fullscreen mode');
                this.showOverlay('FULLSCREEN REQUIRED! Click button to return.');
            }
        });

        // 5. Keyboard Blockers (Combined)
        document.addEventListener('keydown', (e) => {
            if (!this.levelActive && !this.strictLockActive) return;

            // Strict Mode Keys
            const isEscape = (e.key === 'Escape');
            const isCtrlM = (e.ctrlKey && e.key.toLowerCase() === 'm');
            const isAltTab = (e.altKey && (e.key === 'Tab' || e.keyCode === 9));
            const isWin = (e.metaKey);

            if (this.strictLockActive) {
                if (isEscape || isCtrlM || isWin || isAltTab) {
                    e.preventDefault();
                    e.stopPropagation();
                    this.recordViolation('KEY_LOCK_ATTEMPT', true, `Blocked Key: ${e.key}`);
                    return false;
                }
            } else {
                if (isEscape) {
                    e.preventDefault();
                    this.recordViolation('ESC_ATTEMPT', false, 'Tried to exit via ESC');
                    return false;
                }
            }

            // DevTools
            if (e.key === 'F12' || (e.ctrlKey && e.shiftKey && ['I', 'C', 'J', 'U'].includes(e.key))) {
                e.preventDefault();
                this.recordViolation('DEVTOOLS_ATTEMPT', true, 'DevTools blocked');
            }

            // PrintScreen
            if (e.key === 'PrintScreen') {
                this.ignoreBlur = true;
                this.recordViolation('SCREENSHOT_ATTEMPT', true, 'Screenshot detected');
                setTimeout(() => this.ignoreBlur = false, 2000);
            }
        });

        // 6. Mouse/Paste Blockers
        document.addEventListener('contextmenu', e => {
            if ((this.levelActive || this.strictLockActive) && this.config?.block_right_click) {
                e.preventDefault();
                this.recordViolation('RIGHT_CLICK', false);
            }
        });
        document.body.addEventListener('copy', e => {
            if ((this.levelActive || this.strictLockActive) && this.config?.block_copy && !e.target.closest('.ace_editor')) {
                e.preventDefault();
                this.recordViolation('COPY_ATTEMPT', true);
            }
        });
        document.body.addEventListener('paste', e => {
            if ((this.levelActive || this.strictLockActive) && this.config?.block_paste) {
                e.preventDefault();
                this.recordViolation('PASTE_ATTEMPT', true);
            }
        });
        document.body.addEventListener('cut', e => {
            if ((this.levelActive || this.strictLockActive) && this.config?.block_cut && !e.target.closest('.ace_editor')) {
                e.preventDefault();
                this.recordViolation('CUT_ATTEMPT', true);
            }
        });

        // Periodic Enforcement
        this.startEnforcement();
    },

    // ... (rest of the file unchanged methods) ...

    async recordViolation(type, countPenalty = true, description = '') {
        // ... (unchanged logic) ...
        if (this.config) {
            if (type === 'TAB_SWITCH' && !this.config.track_tab_switches) return;
            if (type === 'FOCUS_LOST' && !this.config.track_focus_loss) return;
            if (type === 'COPY_ATTEMPT' && !this.config.block_copy) return;
            if (type === 'PASTE_ATTEMPT' && !this.config.block_paste) return;
            if (type === 'SCREENSHOT_ATTEMPT' && !this.config.detect_screenshot) return;
            if (type === 'RIGHT_CLICK' && !this.config.block_right_click) return;
        }

        // Always record logic ...
        this.lastViolationTime = Date.now();
        if (countPenalty) {
            this.violations++;
            this.updateBadge();

            // ... API Calls ...
            try {
                const session = Storage.get('session');
                const pId = session ? session.participant.participant_id : null;
                const c = window.Contest || {};
                await API.request('/proctoring/violation', 'POST', {
                    violation_type: type,
                    description,
                    total_violations: this.violations,
                    participant_id: pId,
                    contest_id: c.activeContestId,
                    question_id: c.questions ? (c.questions[c.currentQId]?.id) : null,
                    level: c.currentLevel,
                    timestamp: new Date().toISOString()
                });
            } catch (e) { }

            // Check Max
            const max = this.config?.max_violations || 10;
            if (this.violations > max) {
                this.stop(); // Stop proctoring first
                if (window.Contest) window.Contest.submitLevel(true, 'DISQUALIFIED');
                else window.location.href = 'index.html';
            }
        }
    },

    // Stub methods for replace compatibility if needed, but aiming for minimal destructive edit in replace_file is better.
    // Since I need to inject `strictLockActive` check into existing listener, I'll rewrite bindEvents completely.

    updateBadge() {
        const badge = document.getElementById('violation-count');
        if (badge) {
            badge.textContent = `${this.violations} Violations`;
            if (this.violations < 3) badge.style.backgroundColor = 'var(--success)';
            else if (this.violations < 5) badge.style.backgroundColor = 'var(--warning)';
            else badge.style.backgroundColor = 'var(--error)';
        }
    },

    showOverlay(message) {
        if (!this.levelActive && !this.strictLockActive) return;
        const overlay = document.getElementById('proctor-overlay');
        const msgElem = overlay ? overlay.querySelector('p') : null;
        if (overlay) {
            if (msgElem && message) msgElem.textContent = message;
            overlay.style.display = 'flex';
        }
    },

    dismissOverlay() {
        if ((this.levelActive || this.strictLockActive) && !document.fullscreenElement) {
            this.enterFullscreen();
            return;
        }
        const overlay = document.getElementById('proctor-overlay');
        if (overlay) overlay.style.display = 'none';
    },

    startEnforcement() {
        if (this.enforceInterval) clearInterval(this.enforceInterval);
        this.enforceInterval = setInterval(() => {
            if ((this.levelActive || this.strictLockActive) && !document.fullscreenElement) {
                const overlay = document.getElementById('proctor-overlay');
                if (!overlay || overlay.style.display === 'none') {
                    this.showOverlay('Fullscreen is MANDATORY.');
                }
            }
        }, 2000);
    },

    enterFullscreen() {
        const elem = document.documentElement;
        if (document.fullscreenElement) return;
        const req = elem.requestFullscreen || elem.webkitRequestFullscreen || elem.msRequestFullscreen;
        if (req) req.call(elem).catch(() => { });
    },

    exitFullscreen() {
        if (document.fullscreenElement) document.exitFullscreen().catch(() => { });
        if (this.enforceInterval) clearInterval(this.enforceInterval);
        if (this.enforceFocus) clearInterval(this.enforceFocus);
    },
    stop() {
        this.levelActive = false;
        this.strictLockActive = false;
        this.exitFullscreen();
        this.dismissOverlay();
        console.log('Proctoring Deactivated');
    },

    strictLockActive: false,

    enableStrictLock() {
        this.strictLockActive = true;
        this.enterFullscreen();
        this.enforceFocus = setInterval(() => {
            if (this.strictLockActive && !document.hasFocus()) {
                window.focus();
            }
        }, 100);
    }
};
