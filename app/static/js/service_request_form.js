(function () {
    "use strict";

    var dialog = document.querySelector("[data-service-request-dialog]");
    if (!dialog) return;

    var form = dialog.querySelector("[data-service-request-form]");
    var dateInput = dialog.querySelector("[data-service-request-date]");
    var timeInput = dialog.querySelector("[data-service-request-time]");
    var quantityInput = dialog.querySelector("[data-service-request-quantity]");
    var unitLabel = dialog.querySelector("[data-service-request-unit]");
    var notesInput = dialog.querySelector("[data-service-request-notes]");
    var operatorPicker = dialog.querySelector("[data-service-request-operators]");
    var operatorInputs = Array.from(operatorPicker.querySelectorAll('input[type="checkbox"]'));
    var errorMessage = dialog.querySelector("[data-service-request-error]");
    var successMessage = dialog.querySelector("[data-service-request-success]");
    var title = dialog.querySelector("#service-request-dialog-title");
    var isStandalone = dialog.hasAttribute("data-service-request-standalone");
    var selectedItem = null;
    var opener = null;
    var backdropPressed = false;

    function localIsoDate(date) {
        var year = date.getFullYear();
        var month = String(date.getMonth() + 1).padStart(2, "0");
        var day = String(date.getDate()).padStart(2, "0");
        return year + "-" + month + "-" + day;
    }

    function readPendingItem(item) {
        return {
            sourceId: item.dataset.pendingItemId || "standalone-demo",
            protocol: item.dataset.protocol,
            requester: item.dataset.requester,
            service: item.dataset.service,
            quantity: item.dataset.quantity,
            unit: item.dataset.unit,
            location: item.dataset.location,
            requestedAt: item.dataset.requestedAt
        };
    }

    function setSummary(record) {
        Object.keys(record).forEach(function (key) {
            var field = dialog.querySelector('[data-service-request-summary="' + key + '"]');
            if (field) field.textContent = record[key] || "—";
        });
    }

    function clearValidation() {
        errorMessage.hidden = true;
        errorMessage.textContent = "";
        if (successMessage) successMessage.hidden = true;
        operatorPicker.classList.remove("is-invalid");
        dialog.querySelectorAll(".is-invalid").forEach(function (field) {
            field.classList.remove("is-invalid");
            field.removeAttribute("aria-invalid");
        });
    }

    function showError(message, target) {
        errorMessage.textContent = message;
        errorMessage.hidden = false;
        if (target) {
            target.classList.add("is-invalid");
            target.setAttribute("aria-invalid", "true");
            target.focus();
        }
    }

    function prepareForm(record) {
        form.reset();
        clearValidation();
        setSummary(record);
        dateInput.value = localIsoDate(new Date());
        timeInput.value = "08:00";
        quantityInput.value = record.quantity;
        quantityInput.max = record.quantity;
        unitLabel.textContent = record.unit;
    }

    function openForm(button) {
        if (isStandalone) return;
        var item = button.closest("[data-pending-item]");
        if (!item) return;

        opener = button;
        selectedItem = readPendingItem(item);
        prepareForm(selectedItem);

        if (typeof dialog.showModal === "function") {
            dialog.showModal();
        } else {
            dialog.setAttribute("open", "");
        }
        window.setTimeout(function () { dateInput.focus(); }, 0);
    }

    document.addEventListener("click", function (event) {
        var button = event.target.closest("[data-service-request-open]");
        if (button) openForm(button);
    });

    dialog.querySelectorAll("[data-service-request-close]").forEach(function (button) {
        button.addEventListener("click", function () { dialog.close(); });
    });

    [dateInput, timeInput, quantityInput, notesInput].forEach(function (field) {
        field.addEventListener("input", clearValidation);
    });

    operatorInputs.forEach(function (input) {
        input.addEventListener("change", clearValidation);
    });

    form.addEventListener("submit", function (event) {
        event.preventDefault();
        clearValidation();
        if (!selectedItem) return;

        var invalidField = [dateInput, timeInput, quantityInput].find(function (field) {
            return !field.checkValidity();
        });
        if (invalidField) {
            showError("Preencha data, horário e uma quantidade válida dentro do total solicitado.", invalidField);
            return;
        }

        var operators = operatorInputs.filter(function (input) { return input.checked; })
            .map(function (input) { return input.value; });
        if (!operators.length) {
            operatorPicker.classList.add("is-invalid");
            showError("Selecione pelo menos um operador para continuar.", operatorInputs[0]);
            return;
        }

        var appointment = {
            id: "appointment-" + Date.now(),
            sourceId: selectedItem.sourceId,
            protocol: selectedItem.protocol,
            requester: selectedItem.requester,
            service: selectedItem.service,
            quantity: quantityInput.value,
            unit: selectedItem.unit,
            location: selectedItem.location,
            date: dateInput.value,
            time: timeInput.value,
            operators: operators,
            status: "scheduled",
            notes: notesInput.value.trim() || "Sem observações."
        };

        if (isStandalone) {
            if (successMessage) successMessage.hidden = false;
            return;
        }

        dialog.close("confirmed");
        document.dispatchEvent(new CustomEvent("service-request:confirmed", { detail: appointment }));
    });

    function isBackdrop(event) {
        if (event.target !== dialog) return false;
        var bounds = dialog.getBoundingClientRect();
        return event.clientX < bounds.left || event.clientX > bounds.right ||
            event.clientY < bounds.top || event.clientY > bounds.bottom;
    }

    if (!isStandalone) {
        dialog.addEventListener("pointerdown", function (event) {
            backdropPressed = isBackdrop(event);
        });
        dialog.addEventListener("pointercancel", function () { backdropPressed = false; });
        dialog.addEventListener("click", function (event) {
            if (backdropPressed && isBackdrop(event)) dialog.close();
            backdropPressed = false;
        });

        dialog.addEventListener("close", function () {
            form.reset();
            clearValidation();
            selectedItem = null;
            backdropPressed = false;
            if (opener && opener.isConnected) opener.focus();
            opener = null;
            title.textContent = "Agendar serviço";
        });
    } else {
        selectedItem = readPendingItem(dialog);
        prepareForm(selectedItem);
    }
}());
