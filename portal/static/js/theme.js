(() => {
    "use strict";

    const DEFAULT_THEME = "bs-blue";
    const ALLOWED_THEMES = new Set(["bs-blue", "bs-red"]);

    function normalizeTheme(theme) {
        return ALLOWED_THEMES.has(theme) ? theme : DEFAULT_THEME;
    }

    function currentTheme() {
        return normalizeTheme(document.documentElement.dataset.theme);
    }

    function persistTheme(theme) {
        if (window.BSPortalPreferences) {
            window.BSPortalPreferences.set("theme", theme);
            return;
        }

        try {
            localStorage.setItem("bs-portal-theme", theme);
        } catch (error) {
            // Persistence is optional. Theme switching still works for this page.
        }
    }

    function syncThemeControls(theme) {
        document.querySelectorAll("[data-theme-option]").forEach((button) => {
            const selected = button.dataset.themeOption === theme;
            button.classList.toggle("is-selected", selected);
            button.setAttribute("aria-pressed", selected ? "true" : "false");
        });

        // Backward compatibility if an older page still contains the initial
        // theme <select> while this patch is being merged.
        const legacySelector = document.getElementById("portal-theme");
        if (legacySelector && legacySelector.value !== theme) {
            legacySelector.value = theme;
        }
    }

    function applyTheme(theme, { persist = true } = {}) {
        const normalized = normalizeTheme(theme);
        document.documentElement.dataset.theme = normalized;
        syncThemeControls(normalized);

        if (persist) {
            persistTheme(normalized);
        }

        document.dispatchEvent(
            new CustomEvent("bsportal:themechange", {
                detail: { theme: normalized },
            }),
        );
    }

    function initializeThemeControls() {
        const theme = currentTheme();
        syncThemeControls(theme);
        persistTheme(theme);

        document.querySelectorAll("[data-theme-option]").forEach((button) => {
            button.addEventListener("click", () => {
                applyTheme(button.dataset.themeOption);
            });
        });

        const legacySelector = document.getElementById("portal-theme");
        if (legacySelector) {
            legacySelector.addEventListener("change", (event) => {
                applyTheme(event.target.value);
            });
        }
    }

    function initializeAccountMenu() {
        const menu = document.getElementById("account-menu");
        if (!menu) {
            return;
        }

        document.addEventListener("click", (event) => {
            if (menu.open && !menu.contains(event.target)) {
                menu.removeAttribute("open");
            }
        });

        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape" && menu.open) {
                menu.removeAttribute("open");
                const trigger = menu.querySelector("summary");
                if (trigger) {
                    trigger.focus();
                }
            }
        });
    }

    function initialize() {
        initializeThemeControls();
        initializeAccountMenu();
    }

    window.BSPortalTheme = {
        apply: applyTheme,
        current: currentTheme,
        allowed: Array.from(ALLOWED_THEMES),
    };

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initialize);
    } else {
        initialize();
    }
})();
