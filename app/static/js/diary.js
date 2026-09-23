(function () {
    "use strict";

    var page = document.querySelector("[data-agenda-page]");
    if (!page) return;

    var statusLabels = {
        scheduled: "Agendado",
        confirmed: "Confirmado",
        "in-progress": "Em execução",
        completed: "Concluído",
        cancelled: "Cancelado"
    };
    var statusAliases = {
        in_progress: "in-progress",
        canceled: "cancelled"
    };
    var allowedStatuses = Object.keys(statusLabels);
    var eventSource = page.querySelector("[data-agenda-event-source]");
    var calendarBoard = page.querySelector("[data-calendar-board]");
    var calendarGrid = page.querySelector("[data-calendar-grid]");
    var periodLabel = page.querySelector("[data-calendar-period]");
    var resultCount = page.querySelector("[data-calendar-result-count]");
    var emptyState = page.querySelector("[data-calendar-empty]");
    var searchFilter = page.querySelector("[data-calendar-search]");
    var serviceFilter = page.querySelector("[data-calendar-service]");
    var statusFilter = page.querySelector("[data-calendar-status]");
    var resetFilters = page.querySelector("[data-calendar-reset]");
    var viewButtons = Array.from(page.querySelectorAll("[data-calendar-view-button]"));
    var pendingViewport = page.querySelector("[data-pending-viewport]");
    var pendingEmpty = page.querySelector("[data-pending-empty]");
    var pendingCount = page.querySelector("[data-pending-count]");
    var scheduleDialog = page.querySelector("[data-schedule-dialog]");
    var scheduleForm = scheduleDialog.querySelector("[data-schedule-form]");
    var scheduleItems = scheduleDialog.querySelector("[data-schedule-items]");
    var scheduleItemsEmpty = scheduleDialog.querySelector("[data-schedule-items-empty]");
    var scheduleItemCount = scheduleDialog.querySelector("[data-schedule-item-count]");
    var schedulePayload = scheduleDialog.querySelector("[data-schedule-payload]");
    var scheduleConfirm = scheduleDialog.querySelector("[data-schedule-confirm]");
    var schedulePreviewDate = scheduleDialog.querySelector("[data-schedule-preview-date]");
    var schedulePreviewSelection = scheduleDialog.querySelector("[data-schedule-preview-selection]");
    var schedulePreviewSelectedTime = scheduleDialog.querySelector("[data-schedule-preview-selected-time]");
    var schedulePreviewConflict = scheduleDialog.querySelector("[data-schedule-preview-conflict]");
    var schedulePreviewPrompt = scheduleDialog.querySelector("[data-schedule-preview-prompt]");
    var schedulePreviewClear = scheduleDialog.querySelector("[data-schedule-preview-clear]");
    var schedulePreviewList = scheduleDialog.querySelector("[data-schedule-preview-list]");
    var detailsDialog = page.querySelector("[data-appointment-dialog]");
    var scheduleOpener = null;
    var detailsOpener = null;
    var view = "month";
    var today = parseIsoDate(page.dataset.agendaToday) || startOfDay(new Date());
    var visibleDate = new Date(today);

    function startOfDay(date) {
        return new Date(date.getFullYear(), date.getMonth(), date.getDate());
    }

    function parseIsoDate(value) {
        if (!/^\d{4}-\d{2}-\d{2}$/.test(value || "")) return null;
        var parts = value.split("-").map(Number);
        var date = new Date(parts[0], parts[1] - 1, parts[2]);
        if (date.getFullYear() !== parts[0] || date.getMonth() !== parts[1] - 1 || date.getDate() !== parts[2]) {
            return null;
        }
        return date;
    }

    function isoDate(date) {
        return [
            date.getFullYear(),
            String(date.getMonth() + 1).padStart(2, "0"),
            String(date.getDate()).padStart(2, "0")
        ].join("-");
    }

    function addDays(date, amount) {
        var result = new Date(date);
        result.setDate(result.getDate() + amount);
        return result;
    }

    function startOfWeek(date) {
        return addDays(startOfDay(date), -date.getDay());
    }

    function capitalize(value) {
        return value.charAt(0).toLocaleUpperCase("pt-BR") + value.slice(1);
    }

    function normalizeText(value) {
        return String(value || "")
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .toLocaleLowerCase("pt-BR")
            .trim()
            .replace(/\s+/g, " ");
    }

    function formatDate(date, options) {
        return new Intl.DateTimeFormat("pt-BR", options).format(date);
    }

    function readEventsFromDom() {
        return Array.from(eventSource.querySelectorAll("[data-agenda-event]"))
            .map(function (element, index) {
                var date = parseIsoDate(element.dataset.date);
                if (!date) return null;
                var rawStatus = statusAliases[element.dataset.status] || element.dataset.status;
                var status = allowedStatuses.includes(rawStatus)
                    ? rawStatus
                    : "scheduled";
                var quantity = element.dataset.quantity || "";
                var unit = element.dataset.unit || "";
                var services = element.dataset.services || element.dataset.service || "";
                return {
                    id: element.dataset.id || "agenda-event-" + (index + 1),
                    protocol: element.dataset.protocol || "",
                    requester: element.dataset.requester || "",
                    phone: element.dataset.phone || "",
                    service: element.dataset.service || services,
                    services: services,
                    quantity: quantity,
                    unit: unit,
                    quantityLabel: [quantity, unit].filter(Boolean).join(" "),
                    location: element.dataset.location || "",
                    date: isoDate(date),
                    time: element.dataset.time || "",
                    status: status,
                    notes: element.dataset.notes || ""
                };
            })
            .filter(Boolean);
    }

    var appointments = readEventsFromDom();
    var appointmentsById = new Map(appointments.map(function (appointment) {
        return [appointment.id, appointment];
    }));

    function updatePendingState() {
        var cards = page.querySelectorAll("[data-pending-request-card]");
        var amount = cards.length;
        pendingCount.textContent = amount + (amount === 1 ? " solicitação" : " solicitações");
        pendingViewport.hidden = amount === 0;
        pendingEmpty.hidden = amount !== 0;
    }

    function populateServiceFilter() {
        var currentValue = serviceFilter.value;
        var renderedServices = Array.from(serviceFilter.options).map(function (option) {
            return option.value === "all" ? "" : option.value;
        });
        var eventServices = appointments.map(function (item) { return item.service; });
        var services = Array.from(new Set(renderedServices.concat(eventServices).filter(Boolean))).sort(function (first, second) {
            return first.localeCompare(second, "pt-BR");
        });

        serviceFilter.replaceChildren();
        var allOption = document.createElement("option");
        allOption.value = "all";
        allOption.textContent = "Todos os serviços";
        serviceFilter.appendChild(allOption);
        services.forEach(function (service) {
            var option = document.createElement("option");
            option.value = service;
            option.textContent = service;
            serviceFilter.appendChild(option);
        });
        serviceFilter.value = services.includes(currentValue) ? currentValue : "all";
    }

    function matchesFilters(appointment) {
        var query = normalizeText(searchFilter.value);
        var searchable = normalizeText([
            appointment.protocol,
            appointment.requester
        ].join(" "));
        return (!query || searchable.includes(query)) &&
            (serviceFilter.value === "all" || appointment.service === serviceFilter.value) &&
            (statusFilter.value === "all" || appointment.status === statusFilter.value);
    }

    function isInVisiblePeriod(appointment) {
        var date = parseIsoDate(appointment.date);
        if (view === "month") {
            return date.getFullYear() === visibleDate.getFullYear() &&
                date.getMonth() === visibleDate.getMonth();
        }
        if (view === "week") {
            var firstDay = startOfWeek(visibleDate);
            var lastDay = addDays(firstDay, 6);
            return date >= firstDay && date <= lastDay;
        }
        return appointment.date === isoDate(visibleDate);
    }

    function visibleAppointments() {
        return appointments.filter(function (appointment) {
            return isInVisiblePeriod(appointment) && matchesFilters(appointment);
        }).sort(function (first, second) {
            return (first.date + "T" + first.time).localeCompare(second.date + "T" + second.time);
        });
    }

    function periodTitle() {
        if (view === "month") {
            return capitalize(formatDate(visibleDate, { month: "long", year: "numeric" }));
        }
        if (view === "week") {
            var firstDay = startOfWeek(visibleDate);
            var lastDay = addDays(firstDay, 6);
            var sameMonth = firstDay.getMonth() === lastDay.getMonth();
            var startLabel = sameMonth
                ? formatDate(firstDay, { day: "2-digit" })
                : formatDate(firstDay, { day: "2-digit", month: "short" });
            var endLabel = formatDate(lastDay, { day: "2-digit", month: "short", year: "numeric" });
            return capitalize(startLabel + " – " + endLabel);
        }
        return capitalize(formatDate(visibleDate, {
            weekday: "long",
            day: "2-digit",
            month: "long",
            year: "numeric"
        }));
    }

    function createCalendarEvent(appointment) {
        var button = document.createElement("button");
        button.type = "button";
        button.className = "calendar-event calendar-event--" + appointment.status;
        button.dataset.appointmentId = appointment.id;
        button.setAttribute("aria-haspopup", "dialog");
        button.setAttribute("aria-controls", "appointment-details-dialog");
        button.setAttribute("aria-label", [
            appointment.time,
            appointment.service,
            appointment.requester,
            statusLabels[appointment.status]
        ].filter(Boolean).join(", "));

        var headline = document.createElement("span");
        headline.className = "calendar-event__headline";
        var time = document.createElement("time");
        time.dateTime = appointment.date + (appointment.time ? "T" + appointment.time : "");
        time.textContent = appointment.time || "--:--";
        var service = document.createElement("strong");
        service.textContent = appointment.service || "Serviço";
        headline.append(time, service);

        var requester = document.createElement("span");
        requester.className = "calendar-event__requester";
        requester.textContent = appointment.requester || "Solicitante não informado";
        var quantity = document.createElement("span");
        quantity.className = "calendar-event__quantity";
        quantity.textContent = appointment.quantityLabel || appointment.protocol || "";
        button.append(headline, requester, quantity);
        return button;
    }

    function createDayCell(date, events, outsideMonth) {
        var cell = document.createElement("section");
        var isToday = isoDate(date) === isoDate(today);
        cell.className = "calendar-day" +
            (outsideMonth ? " is-outside" : "") +
            (isToday ? " is-today" : "");
        cell.setAttribute("role", "gridcell");
        cell.setAttribute("aria-label", formatDate(date, {
            weekday: "long",
            day: "2-digit",
            month: "long",
            year: "numeric"
        }));

        var heading = document.createElement("header");
        heading.className = "calendar-day__heading";
        var dayName = document.createElement("span");
        dayName.className = "calendar-day__name";
        dayName.textContent = view === "month"
            ? ""
            : capitalize(formatDate(date, { weekday: view === "day" ? "long" : "short" }));
        var dayNumber = document.createElement("time");
        dayNumber.className = "calendar-day__number";
        dayNumber.dateTime = isoDate(date);
        dayNumber.textContent = date.getDate();
        heading.append(dayName, dayNumber);

        var eventList = document.createElement("div");
        eventList.className = "calendar-day__events";
        var visibleEvents = view === "month" ? events.slice(0, 3) : events;
        visibleEvents.forEach(function (appointment) {
            eventList.appendChild(createCalendarEvent(appointment));
        });
        if (events.length > visibleEvents.length) {
            var more = document.createElement("span");
            more.className = "calendar-more";
            more.textContent = "+" + (events.length - visibleEvents.length) + " serviço" +
                (events.length - visibleEvents.length === 1 ? "" : "s");
            eventList.appendChild(more);
        }

        cell.append(heading, eventList);
        return cell;
    }

    function datesForView() {
        if (view === "month") {
            var firstOfMonth = new Date(visibleDate.getFullYear(), visibleDate.getMonth(), 1);
            var firstGridDate = addDays(firstOfMonth, -firstOfMonth.getDay());
            return Array.from({ length: 42 }, function (_, index) {
                return addDays(firstGridDate, index);
            });
        }
        if (view === "week") {
            var firstOfWeek = startOfWeek(visibleDate);
            return Array.from({ length: 7 }, function (_, index) {
                return addDays(firstOfWeek, index);
            });
        }
        return [startOfDay(visibleDate)];
    }

    function renderCalendar() {
        var filtered = visibleAppointments();
        var grouped = filtered.reduce(function (result, appointment) {
            (result[appointment.date] = result[appointment.date] || []).push(appointment);
            return result;
        }, {});

        periodLabel.textContent = periodTitle();
        resultCount.textContent = filtered.length + (filtered.length === 1
            ? " serviço neste período"
            : " serviços neste período");
        emptyState.hidden = filtered.length !== 0;
        calendarBoard.dataset.calendarView = view;
        calendarGrid.replaceChildren();

        datesForView().forEach(function (date) {
            var outsideMonth = view === "month" && date.getMonth() !== visibleDate.getMonth();
            var events = outsideMonth ? [] : (grouped[isoDate(date)] || []);
            calendarGrid.appendChild(createDayCell(date, events, outsideMonth));
        });

        viewButtons.forEach(function (button) {
            button.setAttribute("aria-pressed", String(button.dataset.calendarViewButton === view));
        });
        resetFilters.disabled = !searchFilter.value &&
            serviceFilter.value === "all" &&
            statusFilter.value === "all";
    }

    function navigatePeriod(direction) {
        if (view === "month") {
            visibleDate = new Date(visibleDate.getFullYear(), visibleDate.getMonth() + direction, 1);
        } else if (view === "week") {
            visibleDate = addDays(visibleDate, direction * 7);
        } else {
            visibleDate = addDays(visibleDate, direction);
        }
        renderCalendar();
    }

    function showDialog(dialog, title) {
        if (typeof dialog.showModal === "function") {
            dialog.showModal();
        } else {
            dialog.setAttribute("open", "");
        }
        window.setTimeout(function () {
            title.focus();
        }, 0);
    }

    function closeDialog(dialog) {
        if (typeof dialog.close === "function") {
            dialog.close();
        } else {
            dialog.removeAttribute("open");
            dialog.dispatchEvent(new Event("close"));
        }
    }

    function valueFromCard(button, name) {
        var card = button.closest("[data-pending-request-card]");
        var directValue = button.dataset[name];
        if (directValue) return directValue;
        if (card && card.dataset[name]) return card.dataset[name];
        if (card) {
            var field = card.querySelector('[data-pending-field="' + name + '"]');
            if (field) return field.textContent.trim();
        }
        return "";
    }

    function scheduleServicesFromCard(button) {
        var card = button.closest("[data-pending-request-card]");
        if (!card) return [];
        return Array.from(card.querySelectorAll("[data-pending-service-item]")).map(function (item) {
            return {
                itemId: item.dataset.itemId || "",
                name: item.dataset.serviceName || "Serviço não informado",
                quantityLabel: item.dataset.quantityLabel || "Quantidade não informada",
                scheduledDate: item.dataset.scheduledDate || "",
                scheduledTime: item.dataset.scheduledTime || "",
                status: item.dataset.status || "pending"
            };
        });
    }

    function createScheduleField(labelText, type, id, value) {
        var field = document.createElement("div");
        field.className = "agenda-dialog__field";
        var label = document.createElement("label");
        label.htmlFor = id;
        label.textContent = labelText;
        var input = document.createElement("input");
        input.id = id;
        input.type = type;
        input.dataset.scheduleField = type;
        input.value = value || "";
        if (type === "date") {
            var todayValue = isoDate(today);
            input.min = input.value && input.value < todayValue ? input.value : todayValue;
        }
        input.addEventListener("input", function () {
            var service = input.closest("[data-schedule-service]");
            if (service) {
                updateScheduleServiceStatus(service);
                renderDaySchedulePreview(service);
            }
        });
        input.addEventListener("focus", function () {
            var service = input.closest("[data-schedule-service]");
            if (service) renderDaySchedulePreview(service);
        });
        field.append(label, input);
        return field;
    }

    function updateScheduleServiceStatus(service) {
        var dateInput = service.querySelector('[data-schedule-field="date"]');
        var timeInput = service.querySelector('[data-schedule-field="time"]');
        var badge = service.querySelector("[data-schedule-service-status]");
        var cancelled = service.classList.contains("is-cancelled");

        dateInput.required = !cancelled && Boolean(timeInput.value);
        timeInput.required = !cancelled && Boolean(dateInput.value);

        if (cancelled) {
            service.dataset.status = "canceled";
            badge.className = "status-badge status-badge--cancelled";
            badge.textContent = "Cancelado";
            return;
        }

        var scheduled = Boolean(dateInput.value && timeInput.value);
        service.dataset.status = scheduled ? "scheduled" : "pending";
        badge.className = "status-badge status-badge--" + (scheduled ? "scheduled" : "waiting");
        badge.textContent = scheduled ? "Agendado" : "A programar";
    }

    function setScheduleServiceCancelled(button, cancelled) {
        var service = button.closest("[data-schedule-service]");
        if (!service) return;
        var icon = button.querySelector("i");
        var label = button.querySelector("span");
        service.classList.toggle("is-cancelled", cancelled);
        service.querySelectorAll("input").forEach(function (input) {
            input.disabled = cancelled;
        });
        button.setAttribute("aria-pressed", String(cancelled));
        button.setAttribute("aria-label", cancelled ? "Reativar item" : "Cancelar item");
        icon.className = cancelled ? "fa-solid fa-rotate-left" : "fa-solid fa-ban";
        label.textContent = cancelled ? "Reativar item" : "Cancelar item";
        updateScheduleServiceStatus(service);
    }

    function createScheduleService(item, index) {
        var service = document.createElement("article");
        service.className = "schedule-service";
        service.dataset.scheduleService = "";
        service.dataset.itemId = item.itemId;
        service.dataset.status = item.status;

        var header = document.createElement("header");
        header.className = "schedule-service__header";
        var description = document.createElement("div");
        var name = document.createElement("strong");
        name.textContent = item.name;
        var quantity = document.createElement("span");
        quantity.textContent = item.quantityLabel;
        description.append(name, quantity);
        var badge = document.createElement("span");
        badge.className = "status-badge status-badge--waiting";
        badge.dataset.scheduleServiceStatus = "";
        badge.textContent = "A programar";
        header.append(description, badge);

        var controls = document.createElement("div");
        controls.className = "schedule-service__controls";
        controls.append(
            createScheduleField("Data", "date", "schedule-item-date-" + index, item.scheduledDate),
            createScheduleField("Horário", "time", "schedule-item-time-" + index, item.scheduledTime)
        );
        var cancelButton = document.createElement("button");
        cancelButton.type = "button";
        cancelButton.className = "schedule-service__cancel";
        cancelButton.dataset.scheduleItemCancel = "";
        cancelButton.setAttribute("aria-pressed", "false");
        cancelButton.setAttribute("aria-label", "Cancelar item");
        var cancelIcon = document.createElement("i");
        cancelIcon.className = "fa-solid fa-ban";
        cancelIcon.setAttribute("aria-hidden", "true");
        var cancelLabel = document.createElement("span");
        cancelLabel.textContent = "Cancelar item";
        cancelButton.append(cancelIcon, cancelLabel);
        controls.appendChild(cancelButton);

        service.append(header, controls);
        if ((statusAliases[item.status] || item.status) === "cancelled") {
            setScheduleServiceCancelled(cancelButton, true);
        } else {
            updateScheduleServiceStatus(service);
        }
        return service;
    }

    function createSchedulePreviewItem(appointment, conflicting) {
        var item = document.createElement("li");
        item.className = "schedule-preview__item" + (conflicting ? " is-conflicting" : "");

        var time = document.createElement("time");
        time.dateTime = appointment.date + "T" + appointment.time;
        time.className = "schedule-preview__time";
        time.textContent = appointment.time || "Horário não informado";

        var service = document.createElement("span");
        service.className = "schedule-preview__service";
        service.textContent = appointment.service || "Serviço";

        var badge = document.createElement("span");
        badge.className = "status-badge status-badge--" + (conflicting ? "conflict" : appointment.status);
        badge.textContent = conflicting ? "Conflito" : statusLabels[appointment.status];

        item.append(time, service, badge);
        return item;
    }

    function renderDaySchedulePreview(service) {
        scheduleItems.querySelectorAll("[data-schedule-service]").forEach(function (item) {
            item.classList.toggle("is-preview-active", item === service);
        });

        var dateInput = service && service.querySelector('[data-schedule-field="date"]');
        var timeInput = service && service.querySelector('[data-schedule-field="time"]');
        var selectedDate = dateInput && !dateInput.disabled ? dateInput.value : "";
        var selectedTime = timeInput && !timeInput.disabled ? timeInput.value : "";
        var parsedDate = parseIsoDate(selectedDate);

        schedulePreviewSelection.hidden = !selectedTime;
        schedulePreviewSelectedTime.textContent = selectedTime || "--:--";
        schedulePreviewConflict.hidden = true;
        schedulePreviewList.replaceChildren();

        if (!parsedDate) {
            schedulePreviewDate.textContent = "Selecione uma data";
            schedulePreviewDate.removeAttribute("datetime");
            schedulePreviewPrompt.hidden = false;
            schedulePreviewClear.hidden = true;
            schedulePreviewList.hidden = true;
            return;
        }

        schedulePreviewDate.dateTime = selectedDate;
        schedulePreviewDate.textContent = formatDate(parsedDate, {
            day: "2-digit",
            month: "long",
            year: "numeric"
        });

        var currentItemId = service ? service.dataset.itemId : "";
        var dayAppointments = appointments.filter(function (appointment) {
            return appointment.date === selectedDate &&
                appointment.status !== "cancelled" &&
                appointment.id !== currentItemId;
        }).sort(function (first, second) {
            return first.time.localeCompare(second.time);
        });

        schedulePreviewPrompt.hidden = true;
        schedulePreviewClear.hidden = dayAppointments.length !== 0;
        schedulePreviewList.hidden = dayAppointments.length === 0;

        var hasConflict = false;
        dayAppointments.forEach(function (appointment) {
            var conflicting = Boolean(selectedTime && appointment.time === selectedTime);
            hasConflict = hasConflict || conflicting;
            schedulePreviewList.appendChild(createSchedulePreviewItem(appointment, conflicting));
        });
        schedulePreviewConflict.hidden = !hasConflict;
    }

    function renderScheduleServices(button) {
        var services = scheduleServicesFromCard(button);
        scheduleItems.replaceChildren();
        scheduleItemCount.textContent = services.length + (services.length === 1 ? " item" : " itens");
        scheduleItemsEmpty.hidden = services.length !== 0;
        scheduleConfirm.disabled = services.length === 0;
        services.forEach(function (item, index) {
            scheduleItems.appendChild(createScheduleService(item, index + 1));
        });
        renderDaySchedulePreview(scheduleItems.querySelector("[data-schedule-service]"));
    }

    function buildSchedulePayload() {
        return Array.from(scheduleItems.querySelectorAll("[data-schedule-service]")).map(function (service) {
            var status = service.dataset.status || "pending";
            var dateInput = service.querySelector('[data-schedule-field="date"]');
            var timeInput = service.querySelector('[data-schedule-field="time"]');
            var scheduled = status === "scheduled";
            return [
                service.dataset.itemId || "",
                scheduled ? dateInput.value : null,
                scheduled ? timeInput.value : null,
                status
            ];
        });
    }

    function scheduleAction(requestId) {
        var itemIds = Array.from(scheduleItems.querySelectorAll("[data-schedule-service]"), function (service) {
            return service.dataset.itemId;
        }).filter(Boolean);
        return scheduleForm.dataset.scheduleActionTemplate
            .replace("REQUEST_ID", encodeURIComponent(requestId))
            .replace("ITEM_IDS", encodeURIComponent(itemIds.join(",") || "none"));
    }

    function openScheduleDialog(button) {
        scheduleOpener = button;
        ["protocol", "requester"].forEach(function (name) {
            scheduleDialog.querySelector('[data-schedule-detail="' + name + '"]').textContent =
                valueFromCard(button, name) || "Não informado";
        });
        renderScheduleServices(button);
        scheduleForm.action = scheduleAction(valueFromCard(button, "requestId"));
        showDialog(scheduleDialog, scheduleDialog.querySelector("#schedule-dialog-title"));
    }

    function openDetails(button) {
        var appointment = appointmentsById.get(button.dataset.appointmentId);
        if (!appointment) return;
        detailsOpener = button;
        var values = {
            protocol: appointment.protocol,
            requester: appointment.requester,
            phone: appointment.phone,
            dateLabel: formatDate(parseIsoDate(appointment.date)),
            time: appointment.time,
            location: appointment.location,
            services: (appointment.services || appointment.service) +
                (appointment.quantityLabel ? " — Quantidade: " + appointment.quantityLabel : ""),
            notes: appointment.notes
        };
        Object.keys(values).forEach(function (name) {
            detailsDialog.querySelector('[data-appointment-detail="' + name + '"]').textContent =
                values[name] || "Não informado";
        });
        var badge = detailsDialog.querySelector("[data-appointment-status]");
        badge.className = "status-badge status-badge--" + appointment.status;
        badge.textContent = statusLabels[appointment.status];
        showDialog(detailsDialog, detailsDialog.querySelector("#appointment-dialog-title"));
    }

    function setupDialog(dialog, closeSelector, onClose) {
        var backdropPressed = false;
        dialog.querySelectorAll(closeSelector).forEach(function (button) {
            button.addEventListener("click", function () {
                closeDialog(dialog);
            });
        });
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
            if (backdropPressed && event.target === dialog) closeDialog(dialog);
            backdropPressed = false;
        });
        dialog.addEventListener("close", onClose);
    }

    page.addEventListener("click", function (event) {
        var cancelItemButton = event.target.closest("[data-schedule-item-cancel]");
        if (cancelItemButton) {
            var scheduleService = cancelItemButton.closest("[data-schedule-service]");
            setScheduleServiceCancelled(
                cancelItemButton,
                cancelItemButton.getAttribute("aria-pressed") !== "true"
            );
            renderDaySchedulePreview(scheduleService);
            return;
        }
        var scheduleButton = event.target.closest("[data-schedule-open]");
        if (scheduleButton) {
            openScheduleDialog(scheduleButton);
            return;
        }
        var appointmentButton = event.target.closest("[data-appointment-id]");
        if (appointmentButton) openDetails(appointmentButton);
    });

    scheduleForm.addEventListener("submit", function (event) {
        var items = buildSchedulePayload();
        if (!items.length) {
            event.preventDefault();
            return;
        }
        schedulePayload.value = JSON.stringify(items);
    });

    setupDialog(scheduleDialog, "[data-schedule-close]", function () {
        scheduleForm.reset();
        scheduleItems.replaceChildren();
        scheduleItemCount.textContent = "0 itens";
        scheduleItemsEmpty.hidden = true;
        scheduleConfirm.disabled = true;
        renderDaySchedulePreview(null);
        if (scheduleOpener && scheduleOpener.isConnected) scheduleOpener.focus();
        scheduleOpener = null;
    });

    setupDialog(detailsDialog, "[data-appointment-close]", function () {
        if (detailsOpener && detailsOpener.isConnected) detailsOpener.focus();
        detailsOpener = null;
    });

    page.querySelector("[data-calendar-previous]").addEventListener("click", function () {
        navigatePeriod(-1);
    });
    page.querySelector("[data-calendar-next]").addEventListener("click", function () {
        navigatePeriod(1);
    });
    page.querySelector("[data-calendar-today]").addEventListener("click", function () {
        today = startOfDay(new Date());
        visibleDate = new Date(today);
        renderCalendar();
    });
    viewButtons.forEach(function (button) {
        button.addEventListener("click", function () {
            view = button.dataset.calendarViewButton;
            renderCalendar();
        });
    });
    [serviceFilter, statusFilter].forEach(function (filter) {
        filter.addEventListener("change", renderCalendar);
    });
    searchFilter.addEventListener("input", renderCalendar);
    resetFilters.addEventListener("click", function () {
        searchFilter.value = "";
        serviceFilter.value = "all";
        statusFilter.value = "all";
        renderCalendar();
        searchFilter.focus();
    });

    populateServiceFilter();
    updatePendingState();
    renderCalendar();
}());
