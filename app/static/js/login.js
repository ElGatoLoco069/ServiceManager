(function () {
    "use strict";

    var form = document.querySelector("[data-login-form]");

    if (!form) {
        return;
    }

    var usernameField = form.querySelector('[name="username"]');
    var passwordField = form.querySelector('[name="password"]');
    var passwordToggle = form.querySelector("[data-password-toggle]");
    var passwordIcon = form.querySelector("[data-password-icon]");
    var rememberUsername = form.querySelector("[data-remember-username]");
    var submitButton = form.querySelector("[data-submit-button]");
    var submitText = form.querySelector("[data-submit-text]");
    var spinner = form.querySelector(".login-spinner");
    var storageKey = "maqflow20.rememberedUsername";

    function enhanceField(field, placeholder, errorId) {
        if (!field) {
            return;
        }

        if (!field.getAttribute("placeholder")) {
            field.setAttribute("placeholder", placeholder);
        }

        var errorElement = document.getElementById(errorId);

        if (errorElement) {
            field.setAttribute("aria-invalid", "true");
            var describedBy = field.getAttribute("aria-describedby");
            field.setAttribute(
                "aria-describedby",
                describedBy ? describedBy + " " + errorId : errorId
            );
        }
    }

    function readRememberedUsername() {
        try {
            return window.localStorage.getItem(storageKey) || "";
        } catch (error) {
            return "";
        }
    }

    function saveRememberedUsername() {
        if (!rememberUsername || !usernameField) {
            return;
        }

        try {
            if (rememberUsername.checked && usernameField.value.trim()) {
                window.localStorage.setItem(storageKey, usernameField.value.trim());
            } else {
                window.localStorage.removeItem(storageKey);
            }
        } catch (error) {
            // O login continua funcionando mesmo quando o armazenamento local não está disponível.
        }
    }

    function resetSubmitState() {
        form.removeAttribute("data-submitting");

        if (submitButton) {
            submitButton.disabled = false;
            submitButton.removeAttribute("aria-busy");
        }

        if (spinner) {
            spinner.hidden = true;
        }

        if (submitText) {
            submitText.textContent = "Entrar no sistema";
        }
    }

    enhanceField(usernameField, "Informe seu usuário", "username-errors");
    enhanceField(passwordField, "Informe sua senha", "password-errors");

    var rememberedUsername = readRememberedUsername();

    if (rememberedUsername && usernameField && !usernameField.value) {
        usernameField.value = rememberedUsername;

        if (rememberUsername) {
            rememberUsername.checked = true;
        }
    }

    if (passwordToggle && passwordField) {
        if (passwordField.id) {
            passwordToggle.setAttribute("aria-controls", passwordField.id);
        }

        passwordToggle.addEventListener("click", function () {
            var showPassword = passwordField.type === "password";
            passwordField.type = showPassword ? "text" : "password";
            passwordToggle.setAttribute("aria-pressed", String(showPassword));
            passwordToggle.setAttribute("aria-label", showPassword ? "Ocultar senha" : "Mostrar senha");

            if (passwordIcon) {
                passwordIcon.classList.toggle("fa-eye", !showPassword);
                passwordIcon.classList.toggle("fa-eye-slash", showPassword);
            }

            passwordField.focus({ preventScroll: true });
        });
    }

    form.addEventListener("submit", function (event) {
        if (form.hasAttribute("data-submitting")) {
            event.preventDefault();
            return;
        }

        saveRememberedUsername();
        form.setAttribute("data-submitting", "true");

        if (submitButton) {
            submitButton.disabled = true;
            submitButton.setAttribute("aria-busy", "true");
        }

        if (spinner) {
            spinner.hidden = false;
        }

        if (submitText) {
            submitText.textContent = "Validando acesso...";
        }
    });

    window.addEventListener("pageshow", function (event) {
        if (event.persisted) {
            resetSubmitState();
        }
    });
}());
