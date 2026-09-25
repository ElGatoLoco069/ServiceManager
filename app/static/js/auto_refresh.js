(function () {
    "use strict";

    document.addEventListener("DOMContentLoaded", function () {
        var refreshPage = document.querySelector("[data-auto-refresh-minutes]");
        if (!refreshPage) return;

        var refreshMinutes = Number(refreshPage.dataset.autoRefreshMinutes);
        if (!Number.isFinite(refreshMinutes) || refreshMinutes <= 0) return;

        window.setTimeout(function () {
            window.location.reload();
        }, refreshMinutes * 60 * 1000);
    });
}());
