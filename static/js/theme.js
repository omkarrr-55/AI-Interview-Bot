/**
 * Skillverse Theme & Appearance Engine
 * Handles Light Mode, Dark Mode, System Default detection, and Font Scaling.
 * Features:
 * - Instantaneous zero-reload theme and font-size switching
 * - OS color scheme listener for System Default preference
 * - Persistent storage across localStorage and SQLite platform_settings table
 * - Custom DOM event broadcast for real-time UI & preview synchronization
 */
(function(window) {
    'use strict';

    const STORAGE_KEY_THEME = 'sv_theme';
    const STORAGE_KEY_FONT = 'sv_font_size';

    // System Media Query (prefers-color-scheme: dark)
    const systemMedia = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;

    function getSystemTheme() {
        return (systemMedia && systemMedia.matches) ? 'dark' : 'light';
    }

    function getThemeSetting() {
        return localStorage.getItem(STORAGE_KEY_THEME) || 'system';
    }

    function getEffectiveTheme() {
        const setting = getThemeSetting();
        return setting === 'system' ? getSystemTheme() : setting;
    }

    function getFontSizeSetting() {
        return localStorage.getItem(STORAGE_KEY_FONT) || 'medium';
    }

    function applyTheme(themeSetting, persist) {
        if (persist === undefined) persist = true;
        
        const validThemes = ['light', 'dark', 'system'];
        const chosen = validThemes.includes(themeSetting) ? themeSetting : 'system';
        const effective = (chosen === 'system') ? getSystemTheme() : chosen;

        document.documentElement.setAttribute('data-theme', effective);
        document.documentElement.setAttribute('data-theme-setting', chosen);

        if (persist) {
            try {
                localStorage.setItem(STORAGE_KEY_THEME, chosen);
            } catch (e) {
                console.warn('localStorage theme save failed:', e);
            }
            syncToBackend({ theme_mode: chosen });
        }

        // Broadcast to listeners (settings preview, radio UI, etc.)
        window.dispatchEvent(new CustomEvent('skillverse:theme-changed', {
            detail: {
                setting: chosen,
                effective: effective,
                systemPref: getSystemTheme()
            }
        }));
    }

    function applyFontSize(size, persist) {
        if (persist === undefined) persist = true;

        const validSizes = ['small', 'medium', 'large'];
        const chosen = validSizes.includes(size) ? size : 'medium';

        document.documentElement.setAttribute('data-font-size', chosen);

        if (persist) {
            try {
                localStorage.setItem(STORAGE_KEY_FONT, chosen);
            } catch (e) {
                console.warn('localStorage font save failed:', e);
            }
            syncToBackend({ font_size: chosen });
        }

        window.dispatchEvent(new CustomEvent('skillverse:font-size-changed', {
            detail: { fontSize: chosen }
        }));
    }

    // Debounced backend sync to prevent spamming
    let syncTimer = null;
    function syncToBackend(payload) {
        clearTimeout(syncTimer);
        syncTimer = setTimeout(function() {
            fetch('/api/settings/save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            }).catch(function(err) {
                console.debug('Async settings sync status:', err);
            });
        }, 350);
    }

    // Dynamic OS listener for "system" mode
    function onSystemThemeChange(e) {
        if (getThemeSetting() === 'system') {
            const newEffective = e.matches ? 'dark' : 'light';
            document.documentElement.setAttribute('data-theme', newEffective);
            window.dispatchEvent(new CustomEvent('skillverse:theme-changed', {
                detail: {
                    setting: 'system',
                    effective: newEffective,
                    systemPref: newEffective
                }
            }));
        }
    }

    if (systemMedia) {
        if (systemMedia.addEventListener) {
            systemMedia.addEventListener('change', onSystemThemeChange);
        } else if (systemMedia.addListener) {
            systemMedia.addListener(onSystemThemeChange);
        }
    }

    // Initialize state on page readiness
    function init() {
        const theme = getThemeSetting();
        const font = getFontSizeSetting();
        // Re-apply in memory (without rewriting localStorage or sending API call)
        applyTheme(theme, false);
        applyFontSize(font, false);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Public API
    window.SkillverseTheme = {
        getThemeSetting: getThemeSetting,
        getEffectiveTheme: getEffectiveTheme,
        getSystemTheme: getSystemTheme,
        setTheme: function(theme) { applyTheme(theme, true); },
        getFontSize: getFontSizeSetting,
        setFontSize: function(size) { applyFontSize(size, true); }
    };
})(window);
