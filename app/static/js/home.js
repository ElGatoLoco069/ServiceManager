document.addEventListener("DOMContentLoaded", function () {
    "use strict";

    var dashboard = document.querySelector(".dashboard");
    var modal = document.querySelector("[data-pending-modal]");
    var openButton = dashboard && dashboard.querySelector("[data-pending-modal-open]");
    var modalTitle = modal && modal.querySelector("[data-pending-modal-title]");
    var modalOpener = null;
    var backdropPressed = false;

    if (!modal || !openButton) return;

    function isBackdrop(event) {
        if (event.target !== modal) return false;
        var bounds = modal.getBoundingClientRect();
        return event.clientX < bounds.left || event.clientX > bounds.right ||
            event.clientY < bounds.top || event.clientY > bounds.bottom;
    }

    openButton.addEventListener("click", function () {
        modalOpener = openButton;
        if (!modal.open) modal.showModal();
        if (modalTitle) modalTitle.focus();
    });

    modal.querySelectorAll("[data-pending-modal-close]").forEach(function (button) {
        button.addEventListener("click", function () { modal.close(); });
    });

    modal.addEventListener("pointerdown", function (event) {
        backdropPressed = isBackdrop(event);
    });

    modal.addEventListener("pointercancel", function () {
        backdropPressed = false;
    });

    modal.addEventListener("click", function (event) {
        if (backdropPressed && isBackdrop(event)) modal.close();
        backdropPressed = false;
    });

    modal.addEventListener("close", function () {
        if (modalOpener && document.contains(modalOpener)) modalOpener.focus();
        modalOpener = null;
    });
});
