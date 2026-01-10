/**
 * PyBirch Theme System JavaScript
 * ===============================
 * Handles theme switching, persistence, and custom theme application.
 * 
 * Features:
 * - Light/Dark/System mode switching
 * - LocalStorage persistence for anonymous users
 * - Server-side persistence for logged-in users
 * - Custom theme palette application
 * - Smooth transition animations
 * - System preference change detection
 */

(function() {
    'use strict';
    
    // Constants
    const STORAGE_KEY = 'pybirch-theme-mode';
    const CUSTOM_THEME_KEY = 'pybirch-custom-theme';
    const TRANSITION_DURATION = 300;
    
    // Theme state
    let currentMode = localStorage.getItem(STORAGE_KEY) || 'system';
    let customTheme = null;
    
    /**
     * Get the effective theme (light or dark) based on current mode
     */
    function getEffectiveTheme() {
        if (currentMode === 'system') {
            return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
        }
        return currentMode;
    }
    
    /**
     * Apply theme to the document
     */
    function applyTheme(mode, transition = true) {
        const html = document.documentElement;
        
        // Add transition class for smooth theme change
        if (transition) {
            html.classList.add('theme-transition');
            setTimeout(() => html.classList.remove('theme-transition'), TRANSITION_DURATION);
        }
        
        // Set data-theme attribute
        if (mode === 'system') {
            html.removeAttribute('data-theme');
        } else {
            html.setAttribute('data-theme', mode);
        }
        
        // Update toggle button state
        updateToggleButton();
        
        // Apply custom theme if set
        if (customTheme) {
            applyCustomTheme(customTheme, getEffectiveTheme());
        }
    }
    
    /**
     * Update the toggle button icon
     */
    function updateToggleButton() {
        const toggle = document.getElementById('theme-toggle');
        if (!toggle) return;
        
        const effectiveTheme = getEffectiveTheme();
        toggle.setAttribute('aria-label', 
            effectiveTheme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'
        );
        toggle.setAttribute('title',
            effectiveTheme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'
        );
    }
    
    /**
     * Toggle between light and dark modes
     */
    function toggleTheme() {
        const effectiveTheme = getEffectiveTheme();
        const newMode = effectiveTheme === 'dark' ? 'light' : 'dark';
        
        setThemeMode(newMode);
    }
    
    /**
     * Set the theme mode and persist it
     */
    function setThemeMode(mode) {
        currentMode = mode;
        
        // Save to localStorage
        localStorage.setItem(STORAGE_KEY, mode);
        
        // Apply theme
        applyTheme(mode);
        
        // Save to server if logged in
        saveThemeModeToServer(mode);
    }
    
    /**
     * Save theme mode to server (for logged-in users)
     */
    function saveThemeModeToServer(mode) {
        fetch('/api/v1/settings/theme-mode', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ theme_mode: mode })
        }).catch(() => {
            // Silently fail - localStorage still has the preference
        });
    }
    
    /**
     * Load theme settings from server
     */
    function loadThemeFromServer() {
        fetch('/api/v1/settings/theme')
            .then(response => response.json())
            .then(data => {
                if (data.theme_mode) {
                    currentMode = data.theme_mode;
                    localStorage.setItem(STORAGE_KEY, data.theme_mode);
                    applyTheme(data.theme_mode, false);
                }
                
                // Load custom theme if set
                if (data.light_palette || data.dark_palette) {
                    customTheme = {
                        light: data.light_palette || {},
                        dark: data.dark_palette || {}
                    };
                    localStorage.setItem(CUSTOM_THEME_KEY, JSON.stringify(customTheme));
                    applyCustomTheme(customTheme, getEffectiveTheme());
                }
            })
            .catch(() => {
                // Fall back to localStorage
            });
    }
    
    /**
     * Apply custom theme palette colors
     */
    function applyCustomTheme(theme, mode) {
        const palette = mode === 'dark' ? theme.dark : theme.light;
        if (!palette || Object.keys(palette).length === 0) return;
        
        const root = document.documentElement;
        
        // Map palette keys to CSS variable names
        const varMap = {
            'primary': '--color-primary',
            'primary_dark': '--color-primary-dark',
            'secondary': '--color-secondary',
            'success': '--color-success',
            'warning': '--color-warning',
            'error': '--color-error',
            'info': '--color-info',
            'bg_primary': '--color-bg-primary',
            'bg_secondary': '--color-bg-secondary',
            'bg_tertiary': '--color-bg-tertiary',
            'text_primary': '--color-text-primary',
            'text_secondary': '--color-text-secondary',
            'text_muted': '--color-text-muted',
            'border': '--color-border',
            'border_dark': '--color-border-dark'
        };
        
        Object.entries(palette).forEach(([key, value]) => {
            const cssVar = varMap[key];
            if (cssVar && value) {
                root.style.setProperty(cssVar, value);
            }
        });
    }
    
    /**
     * Clear custom theme
     */
    function clearCustomTheme() {
        customTheme = null;
        localStorage.removeItem(CUSTOM_THEME_KEY);
        
        // Remove inline styles
        const root = document.documentElement;
        const vars = [
            '--color-primary', '--color-primary-dark', '--color-secondary',
            '--color-success', '--color-warning', '--color-error', '--color-info',
            '--color-bg-primary', '--color-bg-secondary', '--color-bg-tertiary',
            '--color-text-primary', '--color-text-secondary', '--color-text-muted',
            '--color-border', '--color-border-dark'
        ];
        vars.forEach(v => root.style.removeProperty(v));
    }
    
    /**
     * Initialize theme system
     */
    function init() {
        // Apply initial theme (already set in head, but ensure consistency)
        applyTheme(currentMode, false);
        
        // Set up toggle button click handler
        const toggle = document.getElementById('theme-toggle');
        if (toggle) {
            toggle.addEventListener('click', toggleTheme);
        }
        
        // Listen for system preference changes
        const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
        mediaQuery.addEventListener('change', () => {
            if (currentMode === 'system') {
                applyTheme('system');
            }
        });
        
        // Load custom theme from localStorage
        const storedCustom = localStorage.getItem(CUSTOM_THEME_KEY);
        if (storedCustom) {
            try {
                customTheme = JSON.parse(storedCustom);
                applyCustomTheme(customTheme, getEffectiveTheme());
            } catch (e) {
                localStorage.removeItem(CUSTOM_THEME_KEY);
            }
        }
        
        // Try to load theme from server (for logged-in users)
        // This will override localStorage if user has server-side settings
        loadThemeFromServer();
    }
    
    // Export functions for external use
    window.PyBirchTheme = {
        toggle: toggleTheme,
        setMode: setThemeMode,
        getMode: () => currentMode,
        getEffective: getEffectiveTheme,
        setCustomTheme: (theme) => {
            customTheme = theme;
            localStorage.setItem(CUSTOM_THEME_KEY, JSON.stringify(theme));
            applyCustomTheme(theme, getEffectiveTheme());
        },
        clearCustomTheme: clearCustomTheme
    };
    
    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
