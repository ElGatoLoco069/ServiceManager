(function () {
    "use strict";

    function initializeToast(toast) {
        var closeButton = toast.querySelector("[data-toast-close]");
        var progress = toast.querySelector("[data-toast-progress]");
        var duration = Number(toast.getAttribute("data-duration")) || 5000;
        var remaining = duration;
        var startedAt = 0;
        var timerId = null;
        var frameId = null;
        var closing = false;

        function renderProgress() {
            if (!startedAt || closing) return;
            var elapsed = Date.now() - startedAt;
            var current = Math.max(0, remaining - elapsed);
            if (progress) progress.style.transform = "scaleX(" + (current / duration) + ")";
            frameId = window.requestAnimationFrame(renderProgress);
        }

        function closeToast() {
            if (closing) return;
            closing = true;
            window.clearTimeout(timerId);
            window.cancelAnimationFrame(frameId);
            toast.classList.add("is-leaving");
            toast.addEventListener("animationend", function () { toast.remove(); }, { once: true });
            window.setTimeout(function () { if (toast.isConnected) toast.remove(); }, 300);
        }

        function startTimer() {
            startedAt = Date.now();
            timerId = window.setTimeout(closeToast, remaining);
            frameId = window.requestAnimationFrame(renderProgress);
        }

        function pauseTimer() {
            if (!startedAt || closing) return;
            remaining = Math.max(0, remaining - (Date.now() - startedAt));
            startedAt = 0;
            window.clearTimeout(timerId);
            window.cancelAnimationFrame(frameId);
        }

        if (closeButton) closeButton.addEventListener("click", closeToast);
        toast.addEventListener("mouseenter", pauseTimer);
        toast.addEventListener("mouseleave", startTimer);
        toast.addEventListener("focusin", pauseTimer);
        toast.addEventListener("focusout", function (event) {
            if (!toast.contains(event.relatedTarget)) startTimer();
        });
        startTimer();
    }

    document.querySelectorAll("[data-toast]").forEach(initializeToast);
}());
