(function () {
    "use strict";

    function dismiss(toast) {
        if (!toast || toast.dataset.dismissed === "true") return;
        toast.dataset.dismissed = "true";
        toast.classList.add("is-leaving");
        window.setTimeout(function () { toast.remove(); }, 180);
    }

    function arm(toast) {
        const isError = toast.classList.contains("toast-error");
        const delay = isError ? 9000 : 6000;
        let timer = window.setTimeout(function () { dismiss(toast); }, delay);

        toast.addEventListener("mouseenter", function () {
            window.clearTimeout(timer);
        });
        toast.addEventListener("mouseleave", function () {
            timer = window.setTimeout(function () { dismiss(toast); }, 2500);
        });
        const close = toast.querySelector("[data-toast-close]");
        if (close) close.addEventListener("click", function () { dismiss(toast); });
    }

    document.addEventListener("DOMContentLoaded", function () {
        document.querySelectorAll("[data-toast]").forEach(arm);
    });
}());
