(function () {
    "use strict";

    document.addEventListener("DOMContentLoaded", function () {
        var dialog = document.querySelector("[data-service-photo-dialog]");
        if (!dialog) return;

        var title = dialog.querySelector("[data-service-photo-title]");
        var body = dialog.querySelector("[data-service-photo-body]");
        var opener = null;

        function closeDialog() {
            if (typeof dialog.close === "function" && dialog.open) {
                dialog.close();
                return;
            }
            dialog.removeAttribute("open");
        }

        function openDialog(button) {
            var serviceItem = button.closest(".service-item");
            var content = serviceItem && serviceItem.querySelector("[data-service-photo-content]");
            if (!content || !body) return;

            body.replaceChildren(content.content.cloneNode(true));
            if (title) title.textContent = button.dataset.serviceName || "Imagem do serviço";
            opener = button;

            if (typeof dialog.showModal === "function") {
                if (!dialog.open) dialog.showModal();
            } else {
                dialog.setAttribute("open", "");
            }
            if (title) title.focus();
        }

        document.querySelectorAll("[data-service-photo-open]").forEach(function (button) {
            button.addEventListener("click", function () {
                openDialog(button);
            });
        });

        dialog.querySelectorAll("[data-service-photo-close]").forEach(function (button) {
            button.addEventListener("click", closeDialog);
        });

        var backdropPressed = false;
        dialog.addEventListener("pointerdown", function (event) {
            if (event.target !== dialog) {
                backdropPressed = false;
                return;
            }
            var bounds = dialog.getBoundingClientRect();
            backdropPressed = event.clientX < bounds.left || event.clientX > bounds.right ||
                event.clientY < bounds.top || event.clientY > bounds.bottom;
        });
        dialog.addEventListener("pointercancel", function () {
            backdropPressed = false;
        });
        dialog.addEventListener("click", function (event) {
            if (backdropPressed && event.target === dialog) closeDialog();
            backdropPressed = false;
        });
        dialog.addEventListener("close", function () {
            if (body) body.replaceChildren();
            if (opener && document.contains(opener)) opener.focus();
            opener = null;
        });
    });
}());
