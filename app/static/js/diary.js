(function () {
    "use strict";

    var page = document.querySelector("[data-agenda-page]");
    if (!page) return;

    var appointments = [
        {
            id: "demo-184-transport-1",
            protocol: "SRV-2026-000184",
            requester: "João da Silva",
            service: "Transporte de terra",
            quantity: "3",
            unit: "cargas",
            location: "Linha São José",
            date: "2026-09-10",
            time: "08:00",
            operators: ["João Emerson", "Carlos Almeida"],
            status: "scheduled",
            notes: "Executar inicialmente três cargas e retornar posteriormente para finalizar."
        },
        {
            id: "demo-191-gravel",
            protocol: "SRV-2026-000191",
            requester: "Maria Oliveira",
            service: "Cascalhamento",
            quantity: "4",
            unit: "cargas",
            location: "Estrada Santa Luzia",
            date: "2026-09-10",
            time: "13:30",
            operators: ["Marcos Oliveira"],
            status: "in-progress",
            notes: "Serviço iniciado pelo trecho próximo à ponte."
        },
        {
            id: "demo-190-cleaning",
            protocol: "SRV-2026-000190",
            requester: "Luciana Alves",
            service: "Limpeza de terreno",
            quantity: "1",
            unit: "serviço",
            location: "Vila Esperança",
            date: "2026-09-10",
            time: "16:30",
            operators: ["Pedro Santos"],
            status: "completed",
            notes: "Área concluída e liberada."
        },
        {
            id: "demo-184-transport-2",
            protocol: "SRV-2026-000184",
            requester: "João da Silva",
            service: "Transporte de terra",
            quantity: "2",
            unit: "cargas",
            location: "Linha São José",
            date: "2026-09-11",
            time: "09:00",
            operators: ["João Emerson"],
            status: "scheduled",
            notes: "Finalizar as duas cargas restantes da solicitação."
        },
        {
            id: "demo-184-grading",
            protocol: "SRV-2026-000184",
            requester: "João da Silva",
            service: "Nivelamento de terreno",
            quantity: "1",
            unit: "serviço",
            location: "Linha São José",
            date: "2026-09-12",
            time: "08:30",
            operators: ["João Emerson"],
            status: "scheduled",
            notes: "Realizar após a conclusão do transporte de terra."
        },
        {
            id: "demo-195-cleaning-cancelled",
            protocol: "SRV-2026-000195",
            requester: "Rafael Martins",
            service: "Limpeza de terreno",
            quantity: "1",
            unit: "serviço",
            location: "Comunidade Boa Vista",
            date: "2026-09-14",
            time: "10:00",
            operators: ["Carlos Almeida"],
            status: "cancelled",
            notes: "Cancelado visualmente por indisponibilidade do local."
        }
    ];

    var statusLabels = {
        "scheduled": "Agendado",
        "in-progress": "Em execução",
        "completed": "Concluído",
        "cancelled": "Cancelado"
    };
    var monthLabel = page.querySelector("[data-calendar-month]");
    var daysContainer = page.querySelector("[data-calendar-days]");
    var mobileAgenda = page.querySelector("[data-mobile-agenda]");
    var emptyState = page.querySelector("[data-calendar-empty]");
    var resultCount = page.querySelector("[data-calendar-result-count]");
    var operatorFilter = page.querySelector("[data-calendar-operator]");
    var statusFilter = page.querySelector("[data-calendar-status]");
    var searchFilter = page.querySelector("[data-calendar-search]");
    var resetFilters = page.querySelector("[data-calendar-reset]");
    var detailsDialog = page.querySelector("[data-appointment-dialog]");
    var detailsStatus = detailsDialog.querySelector("[data-appointment-status]");
    var toast = page.querySelector("[data-agenda-toast]");
    var toastTimer = null;
    var detailsOpener = null;
    var detailsBackdropPressed = false;
    var today = new Date();
    var visibleMonth = new Date(today.getFullYear(), today.getMonth(), 1);

    function localIsoDate(date) {
        var year = date.getFullYear();
        var month = String(date.getMonth() + 1).padStart(2, "0");
        var day = String(date.getDate()).padStart(2, "0");
        return year + "-" + month + "-" + day;
    }

    function dateFromIso(value) {
        var parts = value.split("-").map(Number);
        return new Date(parts[0], parts[1] - 1, parts[2]);
    }

    function normalizeText(value) {
        return String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "")
            .toLocaleLowerCase("pt-BR").trim().replace(/\s+/g, " ");
    }

    function capitalize(value) {
        return value.charAt(0).toLocaleUpperCase("pt-BR") + value.slice(1);
    }

    function monthName(date) {
        return capitalize(new Intl.DateTimeFormat("pt-BR", {
            month: "long",
            year: "numeric"
        }).format(date));
    }

    function fullDate(date) {
        return capitalize(new Intl.DateTimeFormat("pt-BR", {
            weekday: "long",
            day: "2-digit",
            month: "long",
            year: "numeric"
        }).format(date));
    }

    function shortDate(date) {
        return new Intl.DateTimeFormat("pt-BR").format(date);
    }

    function matchesFilters(appointment) {
        var query = normalizeText(searchFilter.value);
        var searchable = normalizeText([
            appointment.protocol,
            appointment.service,
            appointment.requester,
            appointment.location
        ].join(" "));
        var matchesSearch = !query || searchable.includes(query);
        var matchesStatus = statusFilter.value === "all" || appointment.status === statusFilter.value;
        var matchesOperator = operatorFilter.value === "all" || appointment.operators.includes(operatorFilter.value);
        return matchesSearch && matchesStatus && matchesOperator;
    }

    function appointmentsForVisibleMonth() {
        return appointments.filter(function (appointment) {
            var date = dateFromIso(appointment.date);
            return date.getFullYear() === visibleMonth.getFullYear() &&
                date.getMonth() === visibleMonth.getMonth() && matchesFilters(appointment);
        }).sort(function (first, second) {
            return (first.date + first.time).localeCompare(second.date + second.time);
        });
    }

    function createCalendarEvent(appointment) {
        var button = document.createElement("button");
        button.type = "button";
        button.className = "calendar-event calendar-event--" + appointment.status;
        button.dataset.appointmentId = appointment.id;
        button.setAttribute("aria-haspopup", "dialog");
        button.setAttribute("aria-controls", "appointment-dialog");
        button.setAttribute("aria-label", appointment.time + ", " + appointment.service + ", " + appointment.protocol + ", " + statusLabels[appointment.status]);

        var time = document.createElement("time");
        time.dateTime = appointment.date + "T" + appointment.time;
        time.textContent = appointment.time;
        var service = document.createElement("strong");
        service.textContent = appointment.service;
        var protocol = document.createElement("span");
        protocol.textContent = appointment.protocol;
        button.append(time, service, protocol);
        return button;
    }

    function renderCalendarGrid(filtered) {
        daysContainer.replaceChildren();
        var year = visibleMonth.getFullYear();
        var month = visibleMonth.getMonth();
        var firstDayOffset = new Date(year, month, 1).getDay();
        var firstVisibleDate = new Date(year, month, 1 - firstDayOffset);
        var eventsByDate = filtered.reduce(function (groups, appointment) {
            (groups[appointment.date] = groups[appointment.date] || []).push(appointment);
            return groups;
        }, {});

        for (var index = 0; index < 42; index += 1) {
            var date = new Date(firstVisibleDate);
            date.setDate(firstVisibleDate.getDate() + index);
            var isoDate = localIsoDate(date);
            var inCurrentMonth = date.getMonth() === month;
            var cell = document.createElement("div");
            cell.className = "calendar-day" + (inCurrentMonth ? "" : " is-outside") +
                (isoDate === localIsoDate(today) ? " is-today" : "");
            cell.setAttribute("role", "gridcell");
            cell.setAttribute("aria-label", fullDate(date));

            var number = document.createElement("time");
            number.className = "calendar-day__number";
            number.dateTime = isoDate;
            number.textContent = date.getDate();
            cell.appendChild(number);

            var events = document.createElement("div");
            events.className = "calendar-day__events";
            if (inCurrentMonth && eventsByDate[isoDate]) {
                eventsByDate[isoDate].forEach(function (appointment) {
                    events.appendChild(createCalendarEvent(appointment));
                });
            }
            cell.appendChild(events);
            daysContainer.appendChild(cell);
        }
    }

    function createMobileAppointment(appointment) {
        var button = document.createElement("button");
        button.type = "button";
        button.className = "mobile-appointment mobile-appointment--" + appointment.status;
        button.dataset.appointmentId = appointment.id;
        button.setAttribute("aria-haspopup", "dialog");
        button.setAttribute("aria-controls", "appointment-dialog");

        var time = document.createElement("time");
        time.dateTime = appointment.date + "T" + appointment.time;
        time.textContent = appointment.time;
        var copy = document.createElement("span");
        copy.className = "mobile-appointment__copy";
        var service = document.createElement("strong");
        service.textContent = appointment.service;
        var meta = document.createElement("span");
        meta.textContent = appointment.protocol + " · " + statusLabels[appointment.status];
        copy.append(service, meta);
        var chevron = document.createElement("i");
        chevron.className = "fa-solid fa-chevron-right";
        chevron.setAttribute("aria-hidden", "true");
        button.append(time, copy, chevron);
        return button;
    }

    function renderMobileAgenda(filtered) {
        mobileAgenda.replaceChildren();
        var groups = filtered.reduce(function (result, appointment) {
            (result[appointment.date] = result[appointment.date] || []).push(appointment);
            return result;
        }, {});

        Object.keys(groups).sort().forEach(function (dateKey) {
            var section = document.createElement("section");
            section.className = "mobile-agenda__day";
            var heading = document.createElement("header");
            heading.className = "mobile-agenda__heading";
            var dateLabel = document.createElement("strong");
            dateLabel.textContent = fullDate(dateFromIso(dateKey));
            var count = document.createElement("span");
            count.textContent = groups[dateKey].length + (groups[dateKey].length === 1 ? " serviço" : " serviços");
            heading.append(dateLabel, count);
            var items = document.createElement("div");
            items.className = "mobile-agenda__items";
            groups[dateKey].forEach(function (appointment) {
                items.appendChild(createMobileAppointment(appointment));
            });
            section.append(heading, items);
            mobileAgenda.appendChild(section);
        });
    }

    function renderCalendar() {
        var filtered = appointmentsForVisibleMonth();
        monthLabel.textContent = monthName(visibleMonth);
        resultCount.textContent = filtered.length + (filtered.length === 1 ? " serviço" : " serviços");
        emptyState.hidden = filtered.length !== 0;
        renderCalendarGrid(filtered);
        renderMobileAgenda(filtered);
        resetFilters.disabled = operatorFilter.value === "all" && statusFilter.value === "all" && !searchFilter.value;
    }

    function updateIndicators() {
        var todayIso = localIsoDate(today);
        var pendingCount = page.querySelectorAll("[data-pending-item]").length;
        var counts = {
            "pending": pendingCount,
            "scheduled-today": appointments.filter(function (item) {
                return item.date === todayIso && item.status === "scheduled";
            }).length,
            "in-progress": appointments.filter(function (item) { return item.status === "in-progress"; }).length,
            "completed-today": appointments.filter(function (item) {
                return item.date === todayIso && item.status === "completed";
            }).length
        };
        Object.keys(counts).forEach(function (name) {
            page.querySelector('[data-agenda-count="' + name + '"]').textContent = counts[name];
        });
        page.querySelector("[data-pending-label]").textContent = pendingCount + (pendingCount === 1 ? " item" : " itens");
        page.querySelector("[data-pending-list]").hidden = pendingCount === 0;
        page.querySelector("[data-pending-empty]").hidden = pendingCount !== 0;
    }

    function openDetails(button) {
        var appointment = appointments.find(function (item) {
            return item.id === button.dataset.appointmentId;
        });
        if (!appointment) return;

        detailsOpener = button;
        var details = {
            protocol: appointment.protocol,
            requester: appointment.requester,
            service: appointment.service,
            quantityLabel: appointment.quantity + " " + appointment.unit,
            unit: appointment.unit,
            location: appointment.location,
            dateLabel: shortDate(dateFromIso(appointment.date)),
            time: appointment.time,
            operatorsLabel: appointment.operators.join(", "),
            notes: appointment.notes
        };
        Object.keys(details).forEach(function (name) {
            detailsDialog.querySelector('[data-appointment-detail="' + name + '"]').textContent = details[name];
        });
        detailsStatus.className = "status-pill status-pill--" + appointment.status;
        detailsStatus.textContent = statusLabels[appointment.status];
        if (typeof detailsDialog.showModal === "function") detailsDialog.showModal();
        else detailsDialog.setAttribute("open", "");
        window.setTimeout(function () { page.querySelector("#appointment-dialog-title").focus(); }, 0);
    }

    page.addEventListener("click", function (event) {
        var appointmentButton = event.target.closest("[data-appointment-id]");
        if (appointmentButton) openDetails(appointmentButton);
    });

    detailsDialog.querySelectorAll("[data-appointment-close]").forEach(function (button) {
        button.addEventListener("click", function () { detailsDialog.close(); });
    });

    function isDetailsBackdrop(event) {
        if (event.target !== detailsDialog) return false;
        var bounds = detailsDialog.getBoundingClientRect();
        return event.clientX < bounds.left || event.clientX > bounds.right ||
            event.clientY < bounds.top || event.clientY > bounds.bottom;
    }

    detailsDialog.addEventListener("pointerdown", function (event) {
        detailsBackdropPressed = isDetailsBackdrop(event);
    });
    detailsDialog.addEventListener("pointercancel", function () { detailsBackdropPressed = false; });
    detailsDialog.addEventListener("click", function (event) {
        if (detailsBackdropPressed && isDetailsBackdrop(event)) detailsDialog.close();
        detailsBackdropPressed = false;
    });
    detailsDialog.addEventListener("close", function () {
        detailsBackdropPressed = false;
        if (detailsOpener && detailsOpener.isConnected) detailsOpener.focus();
        detailsOpener = null;
    });

    function showSuccess(message) {
        window.clearTimeout(toastTimer);
        page.querySelector("[data-agenda-toast-message]").textContent = message;
        toast.hidden = false;
        toastTimer = window.setTimeout(function () { toast.hidden = true; }, 5000);
    }

    page.querySelector("[data-agenda-toast-close]").addEventListener("click", function () {
        window.clearTimeout(toastTimer);
        toast.hidden = true;
    });

    document.addEventListener("service-request:confirmed", function (event) {
        appointments.push(event.detail);
        var pendingItem = Array.from(page.querySelectorAll("[data-pending-item]")).find(function (item) {
            return item.dataset.pendingItemId === event.detail.sourceId;
        });
        if (pendingItem) pendingItem.remove();

        operatorFilter.value = "all";
        statusFilter.value = "all";
        searchFilter.value = "";
        var scheduledDate = dateFromIso(event.detail.date);
        visibleMonth = new Date(scheduledDate.getFullYear(), scheduledDate.getMonth(), 1);
        updateIndicators();
        renderCalendar();
        showSuccess("Serviço agendado com sucesso.");
    });

    page.querySelector("[data-calendar-previous]").addEventListener("click", function () {
        visibleMonth = new Date(visibleMonth.getFullYear(), visibleMonth.getMonth() - 1, 1);
        renderCalendar();
    });
    page.querySelector("[data-calendar-next]").addEventListener("click", function () {
        visibleMonth = new Date(visibleMonth.getFullYear(), visibleMonth.getMonth() + 1, 1);
        renderCalendar();
    });
    page.querySelector("[data-calendar-today]").addEventListener("click", function () {
        today = new Date();
        visibleMonth = new Date(today.getFullYear(), today.getMonth(), 1);
        renderCalendar();
    });

    [operatorFilter, statusFilter].forEach(function (filter) {
        filter.addEventListener("change", renderCalendar);
    });
    searchFilter.addEventListener("input", renderCalendar);
    resetFilters.addEventListener("click", function () {
        operatorFilter.value = "all";
        statusFilter.value = "all";
        searchFilter.value = "";
        renderCalendar();
        searchFilter.focus();
    });

    updateIndicators();
    renderCalendar();
}());
