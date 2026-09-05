(() => {
    "use strict";

    const STORAGE_KEY = "bs-portal-preferences-v1";
    const COOKIE_PREFIX = "bs-portal-pref-";
    const MAX_AGE_SECONDS = 60 * 60 * 24 * 365;

    function readStore() {
        try {
            const raw = localStorage.getItem(STORAGE_KEY);
            if (!raw) {
                return {};
            }
            const parsed = JSON.parse(raw);
            return parsed && typeof parsed === "object" && !Array.isArray(parsed)
                ? parsed
                : {};
        } catch (error) {
            return {};
        }
    }

    function writeStore(store) {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
        } catch (error) {
            // Browser storage is optional; the cookie remains a fallback.
        }
    }

    function readCookie(name) {
        const prefix = `${COOKIE_PREFIX}${name}=`;
        const parts = document.cookie ? document.cookie.split("; ") : [];
        for (const part of parts) {
            if (part.startsWith(prefix)) {
                try {
                    return decodeURIComponent(part.slice(prefix.length));
                } catch (error) {
                    return part.slice(prefix.length);
                }
            }
        }
        return null;
    }

    function writeCookie(name, value) {
        const secure = window.location.protocol === "https:" ? "; Secure" : "";
        document.cookie = `${COOKIE_PREFIX}${name}=${encodeURIComponent(value)}; Max-Age=${MAX_AGE_SECONDS}; Path=/; SameSite=Lax${secure}`;
    }

    function get(name, fallback = null) {
        const store = readStore();
        if (Object.prototype.hasOwnProperty.call(store, name)) {
            return store[name];
        }

        const cookieValue = readCookie(name);
        if (cookieValue !== null) {
            return cookieValue;
        }

        if (name === "theme") {
            try {
                const legacyTheme = localStorage.getItem("bs-portal-theme");
                if (legacyTheme) {
                    return legacyTheme;
                }
            } catch (error) {
                // Ignore inaccessible legacy storage.
            }
        }

        return fallback;
    }

    function set(name, value) {
        const store = readStore();
        store[name] = value;
        writeStore(store);
        writeCookie(name, String(value));

        if (name === "theme") {
            try {
                localStorage.setItem("bs-portal-theme", String(value));
            } catch (error) {
                // Keep the compatibility write best-effort only.
            }
        }
    }

    function remove(name) {
        const store = readStore();
        delete store[name];
        writeStore(store);
        document.cookie = `${COOKIE_PREFIX}${name}=; Max-Age=0; Path=/; SameSite=Lax`;
    }

    window.BSPortalPreferences = {
        get,
        set,
        remove,
    };
})();
