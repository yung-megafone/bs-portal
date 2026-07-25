(() => {
    "use strict";

    const STORAGE_KEY = "bs-portal-theme";
    const DEFAULT_THEME = "bs-blue";
    const ALLOWED_THEMES = new Set(["bs-blue", "bs-red"]);

    function normalizeTheme(theme) {
        return ALLOWED_THEMES.has(theme) ? theme : DEFAULT_THEME;
    }

    function currentTheme() {
        return normalizeTheme(document.documentElement.dataset.theme);
    }

    function persistTheme(theme) {
        try {
            localStorage.setItem(STORAGE_KEY, theme);
        } catch (error) {
            // Persistence is optional. Theme switching still works for this page.
        }
    }

    function applyTheme(theme, { persist = true } = {}) {
        const normalized = normalizeTheme(theme);
        document.documentElement.dataset.theme = normalized;

        const selector = document.getElementById("portal-theme");
        if (selector && selector.value !== normalized) {
            selector.value = normalized;
        }

        if (persist) {
            persistTheme(normalized);
        }

        document.dispatchEvent(
            new CustomEvent("bsportal:themechange", {
                detail: { theme: normalized },
            }),
        );
    }

    function initializeThemeControl() {
        const selector = document.getElementById("portal-theme");
        if (!selector) {
            return;
        }

        selector.value = currentTheme();
        selector.addEventListener("change", (event) => {
            applyTheme(event.target.value);
        });
    }

    window.BSPortalTheme = {
        apply: applyTheme,
        current: currentTheme,
        allowed: Array.from(ALLOWED_THEMES),
    };

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initializeThemeControl);
    } else {
        initializeThemeControl();
    }
})();
