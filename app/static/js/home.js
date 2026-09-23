document.addEventListener("DOMContentLoaded", function () {
    "use strict";

    var dashboard = document.querySelector(".dashboard");
    if (!dashboard) return;

    var pendingModal = document.querySelector("[data-pending-modal]");
    var pendingModalOpen = dashboard.querySelector("[data-pending-modal-open]");
    var pendingModalTitle = pendingModal && pendingModal.querySelector("[data-pending-modal-title]");
    var pendingModalOpener = null;
    var suppressPendingFocusRestore = false;

    var scheduleDialog = document.querySelector("[data-dashboard-schedule-dialog]");
    var scheduleForm = scheduleDialog && scheduleDialog.querySelector("[data-dashboard-schedule-form]");
    var scheduleTitle = scheduleDialog && scheduleDialog.querySelector("[data-dashboard-schedule-title]");
    var scheduleItems = scheduleDialog && scheduleDialog.querySelector("[data-dashboard-schedule-items]");
    var scheduleCount = scheduleDialog && scheduleDialog.querySelector("[data-dashboard-schedule-count]");
    var schedulePayload = scheduleDialog && scheduleDialog.querySelector("[data-dashboard-schedule-payload]");
    var scheduleConfirm = scheduleDialog && scheduleDialog.querySelector("[data-dashboard-schedule-confirm]");
    var scheduleNotice = scheduleDialog && scheduleDialog.querySelector("[data-dashboard-schedule-notice]");
    var previewDate = scheduleDialog && scheduleDialog.querySelector("[data-dashboard-preview-date]");
    var previewSelection = scheduleDialog && scheduleDialog.querySelector("[data-dashboard-preview-selection]");
    var previewTime = scheduleDialog && scheduleDialog.querySelector("[data-dashboard-preview-time]");
    var previewConflict = scheduleDialog && scheduleDialog.querySelector("[data-dashboard-preview-conflict]");
    var previewPrompt = scheduleDialog && scheduleDialog.querySelector("[data-dashboard-preview-prompt]");
    var previewUnavailable = scheduleDialog && scheduleDialog.querySelector("[data-dashboard-preview-unavailable]");
    var previewClear = scheduleDialog && scheduleDialog.querySelector("[data-dashboard-preview-clear]");
    var previewList = scheduleDialog && scheduleDialog.querySelector("[data-dashboard-preview-list]");
    var scheduleOpener = null;
    var reopenPendingModal = false;
    var defaultScheduleNotice = scheduleNotice ? scheduleNotice.textContent.trim() : "";

    function isBackdrop(dialog, event) {
        if (event.target !== dialog) return false;
        var bounds = dialog.getBoundingClientRect();
        return event.clientX < bounds.left || event.clientX > bounds.right ||
            event.clientY < bounds.top || event.clientY > bounds.bottom;
    }

    function setupBackdropClose(dialog) {
        var backdropPressed = false;

        dialog.addEventListener("pointerdown", function (event) {
            backdropPressed = isBackdrop(dialog, event);
        });
        dialog.addEventListener("pointercancel", function () {
            backdropPressed = false;
        });
        dialog.addEventListener("click", function (event) {
            if (backdropPressed && isBackdrop(dialog, event)) dialog.close();
            backdropPressed = false;
        });
    }

    if (pendingModal && pendingModalOpen) {
        pendingModalOpen.addEventListener("click", function () {
            pendingModalOpener = pendingModalOpen;
            if (!pendingModal.open) pendingModal.showModal();
            if (pendingModalTitle) pendingModalTitle.focus();
        });

        pendingModal.querySelectorAll("[data-pending-modal-close]").forEach(function (button) {
            button.addEventListener("click", function () { pendingModal.close(); });
        });

        setupBackdropClose(pendingModal);
        pendingModal.addEventListener("close", function () {
            if (suppressPendingFocusRestore) {
                suppressPendingFocusRestore = false;
                return;
            }
            if (pendingModalOpener && document.contains(pendingModalOpener)) {
                pendingModalOpener.focus();
            }
            pendingModalOpener = null;
        });
    }

    if (!scheduleDialog || !scheduleForm) return;

    function setScheduleNotice(message, isError) {
        scheduleNotice.lastChild.textContent = " " + message;
        scheduleNotice.classList.toggle("is-error", Boolean(isError));
    }

    function updateScheduleService(service) {
        var dateInput = service.querySelector('[data-dashboard-schedule-field="date"]');
        var timeInput = service.querySelector('[data-dashboard-schedule-field="time"]');
        var status = service.querySelector("[data-dashboard-schedule-status]");
        var scheduled = Boolean(dateInput.value && timeInput.value);

        dateInput.required = Boolean(timeInput.value);
        timeInput.required = Boolean(dateInput.value);
        service.dataset.status = scheduled ? "scheduled" : "pending";
        status.className = "schedule-modal__status " + (scheduled ? "is-scheduled" : "is-pending");
        status.textContent = scheduled ? "Agendado" : "A programar";
        setScheduleNotice(defaultScheduleNotice, false);
    }

    function createPreviewItem(appointment, conflicting) {
        var item = document.createElement("li");
        item.className = "schedule-modal__preview-item" + (conflicting ? " is-conflicting" : "");

        var time = document.createElement("time");
        time.className = "schedule-modal__preview-time";
        time.dateTime = appointment.date + "T" + appointment.time;
        time.textContent = appointment.time;

        var service = document.createElement("span");
        service.className = "schedule-modal__preview-service";
        service.textContent = appointment.service || "Serviço";

        var badge = document.createElement("span");
        badge.className = "schedule-modal__status " + (conflicting ? "is-conflicting" : "is-" + appointment.status);
        badge.textContent = conflicting ? "Conflito" : appointment.statusLabel;

        item.append(time, service, badge);
        return item;
    }

    function renderDaySchedulePreview(service) {
        scheduleItems.querySelectorAll("[data-dashboard-schedule-service]").forEach(function (item) {
            item.classList.toggle("is-preview-active", item === service);
        });

        var dateInput = service && service.querySelector('[data-dashboard-schedule-field="date"]');
        var timeInput = service && service.querySelector('[data-dashboard-schedule-field="time"]');
        var selectedDate = dateInput ? dateInput.value : "";
        var selectedTime = timeInput ? timeInput.value : "";
        var dateParts = /^\d{4}-\d{2}-\d{2}$/.test(selectedDate) ? selectedDate.split("-").map(Number) : null;
        var date = dateParts && new Date(dateParts[0], dateParts[1] - 1, dateParts[2]);
        var validDate = date && date.getFullYear() === dateParts[0] &&
            date.getMonth() === dateParts[1] - 1 && date.getDate() === dateParts[2];

        previewSelection.hidden = !selectedTime;
        previewTime.textContent = selectedTime || "--:--";
        previewConflict.hidden = true;
        previewList.replaceChildren();
        previewPrompt.hidden = Boolean(validDate);
        previewUnavailable.hidden = true;
        previewClear.hidden = true;
        previewList.hidden = true;

        if (!validDate) {
            previewDate.textContent = "Selecione uma data";
            previewDate.removeAttribute("datetime");
            return;
        }

        previewDate.dateTime = selectedDate;
        previewDate.textContent = new Intl.DateTimeFormat("pt-BR", {
            day: "2-digit", month: "long", year: "numeric"
        }).format(date);

        if (selectedDate !== dashboard.dataset.dashboardToday) {
            previewUnavailable.hidden = false;
            return;
        }

        var currentItemId = service ? service.dataset.itemId : "";
        var appointments = Array.from(dashboard.querySelectorAll("[data-dashboard-preview-event]"))
            .map(function (event) {
                return {
                    date: event.dataset.date,
                    time: event.dataset.time,
                    service: event.dataset.service,
                    status: event.dataset.status.replace("_", "-"),
                    statusLabel: event.dataset.statusLabel,
                    itemId: event.dataset.itemId
                };
            })
            .filter(function (appointment) {
                return appointment.date === selectedDate && appointment.status !== "canceled" &&
                    appointment.itemId !== currentItemId;
            })
            .sort(function (first, second) { return first.time.localeCompare(second.time); });

        previewClear.hidden = appointments.length !== 0;
        previewList.hidden = appointments.length === 0;
        var hasConflict = false;
        appointments.forEach(function (appointment) {
            var conflicting = Boolean(selectedTime && appointment.time === selectedTime);
            hasConflict = hasConflict || conflicting;
            previewList.appendChild(createPreviewItem(appointment, conflicting));
        });
        previewConflict.hidden = !hasConflict;
    }

    function createScheduleField(labelText, type, id) {
        var field = document.createElement("div");
        field.className = "schedule-modal__field";

        var label = document.createElement("label");
        label.htmlFor = id;
        label.textContent = labelText;

        var input = document.createElement("input");
        input.id = id;
        input.type = type;
        input.dataset.dashboardScheduleField = type;
        if (type === "date") input.min = dashboard.dataset.dashboardToday || "";
        input.addEventListener("input", function () {
            var service = input.closest("[data-dashboard-schedule-service]");
            updateScheduleService(service);
            renderDaySchedulePreview(service);
        });
        input.addEventListener("focus", function () {
            renderDaySchedulePreview(input.closest("[data-dashboard-schedule-service]"));
        });

        field.append(label, input);
        return field;
    }

    function createScheduleService(item, index) {
        var service = document.createElement("article");
        service.className = "schedule-modal__service";
        service.dataset.dashboardScheduleService = "";
        service.dataset.itemId = item.itemId;
        service.dataset.status = "pending";

        var header = document.createElement("header");
        header.className = "schedule-modal__service-header";
        var description = document.createElement("div");
        var name = document.createElement("strong");
        name.textContent = item.name;
        var quantity = document.createElement("span");
        quantity.textContent = item.quantityLabel;
        description.append(name, quantity);

        var status = document.createElement("span");
        status.className = "schedule-modal__status is-pending";
        status.dataset.dashboardScheduleStatus = "";
        status.textContent = "A programar";
        header.append(description, status);

        var fields = document.createElement("div");
        fields.className = "schedule-modal__fields";
        fields.append(
            createScheduleField("Data", "date", "dashboard-schedule-date-" + index),
            createScheduleField("Horário", "time", "dashboard-schedule-time-" + index)
        );
        service.append(header, fields);
        return service;
    }

    function servicesFromCard(button) {
        var card = button.closest("[data-pending-request-item]");
        if (!card) return [];
        return Array.from(card.querySelectorAll("[data-pending-service-item]")).map(function (item) {
            return {
                itemId: item.dataset.itemId || "",
                name: item.dataset.serviceName || "Serviço não informado",
                quantityLabel: item.dataset.quantityLabel || "Quantidade não informada"
            };
        });
    }

    function renderScheduleServices(button) {
        var services = servicesFromCard(button);
        scheduleItems.replaceChildren();
        services.forEach(function (item, index) {
            scheduleItems.appendChild(createScheduleService(item, index + 1));
        });
        scheduleCount.textContent = services.length + (services.length === 1 ? " item" : " itens");
        scheduleConfirm.disabled = services.length === 0;
        renderDaySchedulePreview(scheduleItems.querySelector("[data-dashboard-schedule-service]"));
    }

    function buildSchedulePayload() {
        return Array.from(scheduleItems.querySelectorAll("[data-dashboard-schedule-service]")).map(function (service) {
            var dateInput = service.querySelector('[data-dashboard-schedule-field="date"]');
            var timeInput = service.querySelector('[data-dashboard-schedule-field="time"]');
            var scheduled = service.dataset.status === "scheduled";
            return [
                service.dataset.itemId || "",
                scheduled ? dateInput.value : null,
                scheduled ? timeInput.value : null,
                scheduled ? "scheduled" : "pending"
            ];
        });
    }

    function openScheduleDialog(button) {
        var card = button.closest("[data-pending-request-item]");
        if (!card) return;

        scheduleOpener = button;
        reopenPendingModal = Boolean(pendingModal && pendingModal.open && pendingModal.contains(button));
        if (reopenPendingModal) {
            suppressPendingFocusRestore = true;
            pendingModal.close();
        }

        ["protocol", "requester"].forEach(function (name) {
            scheduleDialog.querySelector('[data-dashboard-schedule-detail="' + name + '"]').textContent =
                card.dataset[name] || "Não informado";
        });
        renderScheduleServices(button);
        scheduleForm.action = scheduleForm.dataset.scheduleActionTemplate.replace(
            "REQUEST_ID",
            encodeURIComponent(card.dataset.requestId || "")
        );
        setScheduleNotice(defaultScheduleNotice, false);
        scheduleDialog.showModal();
        scheduleTitle.focus();
    }

    document.addEventListener("click", function (event) {
        var button = event.target.closest("[data-dashboard-schedule-open]");
        if (button) openScheduleDialog(button);
    });

    scheduleDialog.querySelectorAll("[data-dashboard-schedule-close]").forEach(function (button) {
        button.addEventListener("click", function () { scheduleDialog.close(); });
    });
    setupBackdropClose(scheduleDialog);

    scheduleForm.addEventListener("submit", function (event) {
        var items = buildSchedulePayload();
        var hasScheduledItem = items.some(function (item) { return item[3] === "scheduled"; });
        if (!hasScheduledItem) {
            event.preventDefault();
            setScheduleNotice("Preencha a data e o horário de pelo menos um serviço.", true);
            var firstDate = scheduleItems.querySelector('[data-dashboard-schedule-field="date"]');
            if (firstDate) firstDate.focus();
            return;
        }
        schedulePayload.value = JSON.stringify(items);
        scheduleConfirm.disabled = true;
        scheduleConfirm.setAttribute("aria-busy", "true");
    });

    scheduleDialog.addEventListener("close", function () {
        scheduleForm.reset();
        scheduleItems.replaceChildren();
        scheduleCount.textContent = "0 itens";
        scheduleConfirm.disabled = true;
        scheduleConfirm.removeAttribute("aria-busy");
        setScheduleNotice(defaultScheduleNotice, false);
        renderDaySchedulePreview(null);

        if (reopenPendingModal && pendingModal && !pendingModal.open) {
            pendingModal.showModal();
            if (scheduleOpener && scheduleOpener.isConnected) scheduleOpener.focus();
        } else if (scheduleOpener && scheduleOpener.isConnected) {
            scheduleOpener.focus();
        }
        scheduleOpener = null;
        reopenPendingModal = false;
    });
});
