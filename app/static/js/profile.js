(function () {
    "use strict";

    document.addEventListener("DOMContentLoaded", function () {
        var page = document.querySelector("[data-profile-page]");
        if (!page) return;

        var profileNavigationItem = Array.from(document.querySelectorAll(".sidebar__item")).find(function (item) {
            var label = item.querySelector(".sidebar__label");
            return label && label.textContent.trim() === "Perfil";
        });

        if (profileNavigationItem) {
            profileNavigationItem.classList.remove("is-unavailable");
            profileNavigationItem.removeAttribute("aria-disabled");
            profileNavigationItem.removeAttribute("title");
            profileNavigationItem.setAttribute("aria-current", "page");
        }

        page.querySelectorAll("[data-profile-editable]").forEach(function (field) {
            var input = field.querySelector("[data-profile-editable-input]");
            var button = field.querySelector("[data-profile-edit-button]");
            var icon = button ? button.querySelector("i") : null;

            if (!input || !button || !icon) return;

            function setEditing(editing, restoreValue) {
                if (editing) {
                    input.dataset.originalValue = input.value;
                    input.readOnly = false;
                    field.classList.add("is-editing");
                    icon.className = "fa-solid fa-check";
                    button.setAttribute("aria-label", button.dataset.confirmLabel);
                    button.setAttribute("title", button.dataset.confirmLabel);
                    input.focus();
                    return;
                }

                if (restoreValue) input.value = input.dataset.originalValue || input.value;
                input.readOnly = true;
                field.classList.remove("is-editing");
                icon.className = "fa-solid fa-pen";
                button.setAttribute("aria-label", button.dataset.editLabel);
                button.setAttribute("title", button.dataset.editLabel);
                button.focus();
            }

            button.addEventListener("click", function () {
                setEditing(input.readOnly);
            });

            input.addEventListener("keydown", function (event) {
                if (event.key === "Enter") {
                    event.preventDefault();
                    setEditing(false);
                }

                if (event.key === "Escape") {
                    event.preventDefault();
                    setEditing(false, true);
                }
            });
        });

        var themeButtons = Array.from(page.querySelectorAll("[data-profile-theme]"));
        var globalThemeToggle = document.querySelector("[data-theme-toggle]");

        function syncThemeButtons() {
            var currentTheme = document.documentElement.getAttribute("data-theme") || "light";
            themeButtons.forEach(function (button) {
                button.setAttribute("aria-pressed", String(button.dataset.profileTheme === currentTheme));
            });
        }

        themeButtons.forEach(function (button) {
            button.addEventListener("click", function () {
                var requestedTheme = button.dataset.profileTheme;
                var currentTheme = document.documentElement.getAttribute("data-theme") || "light";
                if (requestedTheme === currentTheme) return;

                if (globalThemeToggle) {
                    globalThemeToggle.click();
                } else {
                    document.documentElement.setAttribute("data-theme", requestedTheme);
                    try {
                        localStorage.setItem("maqflow-theme", requestedTheme);
                    } catch (error) {
                        /* Armazenamento local é opcional. */
                    }
                }

                syncThemeButtons();
            });
        });

        if (globalThemeToggle) {
            globalThemeToggle.addEventListener("click", function () {
                window.requestAnimationFrame(syncThemeButtons);
            });
        }

        syncThemeButtons();
    });
}());
