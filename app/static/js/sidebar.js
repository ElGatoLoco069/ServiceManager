(function () {
    "use strict";

    document.addEventListener("DOMContentLoaded", function () {
        var layout = document.querySelector("[data-app-layout]");
        if (!layout) return;

        var desktopToggle = layout.querySelector("[data-sidebar-collapse]");
        var desktopToggleIcon = desktopToggle ? desktopToggle.querySelector("i") : null;
        var mobileToggle = layout.querySelector("[data-sidebar-mobile-toggle]");
        var overlay = layout.querySelector("[data-sidebar-overlay]");
        var submenuToggle = layout.querySelector("[data-sidebar-submenu-toggle]");
        var submenu = layout.querySelector("[data-sidebar-submenu]");
        var themeToggle = layout.querySelector("[data-theme-toggle]");
        var themeIcon = themeToggle ? themeToggle.querySelector("[data-theme-icon]") : null;
        var themeLabel = themeToggle ? themeToggle.querySelector("[data-theme-label]") : null;
        var mobileBreakpoint = window.matchMedia("(max-width: 900px)");

        function syncDesktopControl(collapsed) {
            if (!desktopToggle) return;
            desktopToggle.setAttribute("aria-expanded", String(!collapsed));
            desktopToggle.setAttribute("aria-label", collapsed ? "Expandir menu lateral" : "Recolher menu lateral");
            desktopToggle.setAttribute("title", collapsed ? "Expandir menu" : "Recolher menu");
            if (desktopToggleIcon) desktopToggleIcon.className = collapsed ? "fa-solid fa-angles-right" : "fa-solid fa-angles-left";
        }

        try {
            if (localStorage.getItem("maqflow-sidebar-collapsed") === "true") {
                layout.classList.add("is-sidebar-collapsed");
            }
        } catch (error) { /* Armazenamento opcional. */ }
        syncDesktopControl(layout.classList.contains("is-sidebar-collapsed"));

        function setMobileOpen(isOpen) {
            layout.classList.toggle("is-mobile-open", isOpen);
            if (mobileToggle) mobileToggle.setAttribute("aria-expanded", String(isOpen));
            if (overlay) overlay.setAttribute("aria-hidden", String(!isOpen));
            if (desktopToggle && mobileBreakpoint.matches) {
                if (isOpen) {
                    desktopToggle.setAttribute("aria-expanded", "true");
                    desktopToggle.setAttribute("aria-label", "Fechar menu lateral");
                    desktopToggle.setAttribute("title", "Fechar menu");
                    if (desktopToggleIcon) desktopToggleIcon.className = "fa-solid fa-xmark";
                } else {
                    syncDesktopControl(layout.classList.contains("is-sidebar-collapsed"));
                }
            }
        }

        function syncThemeControl() {
            if (!themeToggle) return;
            var isDark = document.documentElement.getAttribute("data-theme") === "dark";
            themeToggle.setAttribute("aria-label", isDark ? "Ativar tema claro" : "Ativar tema escuro");
            themeToggle.setAttribute("aria-checked", String(isDark));
            themeToggle.setAttribute("title", isDark ? "Claro" : "Escuro");
            if (themeLabel) themeLabel.textContent = isDark ? "Claro" : "Escuro";
            if (themeIcon) themeIcon.className = isDark ? "fa-solid fa-sun sidebar__nav-icon" : "fa-solid fa-moon sidebar__nav-icon";
        }

        if (desktopToggle) {
            desktopToggle.addEventListener("click", function () {
                if (mobileBreakpoint.matches) {
                    setMobileOpen(false);
                    if (mobileToggle) mobileToggle.focus();
                    return;
                }
                var collapsed = !layout.classList.contains("is-sidebar-collapsed");
                layout.classList.toggle("is-sidebar-collapsed", collapsed);
                syncDesktopControl(collapsed);
                try { localStorage.setItem("maqflow-sidebar-collapsed", String(collapsed)); } catch (error) { /* Armazenamento opcional. */ }
            });
        }

        if (mobileToggle) mobileToggle.addEventListener("click", function () { setMobileOpen(!layout.classList.contains("is-mobile-open")); });
        if (overlay) overlay.addEventListener("click", function () { setMobileOpen(false); });

        if (submenuToggle && submenu) {
            submenuToggle.addEventListener("click", function () {
                var open = submenuToggle.getAttribute("aria-expanded") !== "true";

                if (open && !mobileBreakpoint.matches && layout.classList.contains("is-sidebar-collapsed")) {
                    layout.classList.remove("is-sidebar-collapsed");
                    syncDesktopControl(false);
                    try { localStorage.setItem("maqflow-sidebar-collapsed", "false"); } catch (error) { /* Armazenamento opcional. */ }
                }

                submenuToggle.setAttribute("aria-expanded", String(open));
                submenu.classList.toggle("is-open", open);
            });
        }

        if (themeToggle) {
            syncThemeControl();
            themeToggle.addEventListener("click", function () {
                var nextTheme = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
                document.documentElement.setAttribute("data-theme", nextTheme);
                try { localStorage.setItem("maqflow-theme", nextTheme); } catch (error) { /* Armazenamento opcional. */ }
                syncThemeControl();
            });
        }

        layout.querySelectorAll("a.sidebar__item").forEach(function (item) {
            item.addEventListener("click", function () {
                if (mobileBreakpoint.matches) setMobileOpen(false);
            });
        });

        document.addEventListener("keydown", function (event) {
            if (event.key === "Escape" && layout.classList.contains("is-mobile-open")) {
                setMobileOpen(false);
                if (mobileToggle) mobileToggle.focus();
            }
        });

        mobileBreakpoint.addEventListener("change", function () { setMobileOpen(false); });
    });
}());
