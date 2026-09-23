(function () {
    "use strict";

    var page = document.querySelector("[data-service-request]");
    if (!page) return;

    function ensureHeaderControls() {
        var header = page.querySelector(".service-request__header");
        var headerCopy = header.querySelector(".service-request__header-copy");
        if (!headerCopy) {
            headerCopy = document.createElement("div");
            headerCopy.className = "service-request__header-copy";
            Array.from(header.children).forEach(function (child) {
                headerCopy.appendChild(child);
            });
            header.appendChild(headerCopy);
        }

        var button = header.querySelector("[data-service-request-clear]");
        if (!button) {
            button = document.createElement("button");
            button.className = "service-request__clear";
            button.type = "button";
            button.dataset.serviceRequestClear = "";
            button.setAttribute("aria-label", "Limpar formulário e apagar rascunho");
            button.title = "Limpar formulário";

            var icon = document.createElement("i");
            icon.className = "fa-solid fa-trash";
            icon.setAttribute("aria-hidden", "true");
            button.appendChild(icon);
            button.appendChild(document.createTextNode(" Limpar formulário"));
            header.appendChild(button);
        }

        return button;
    }

    var form = page.querySelector("[data-service-request-form]");
    var draftStatus = page.querySelector("[data-draft-status]");
    var clearButton = ensureHeaderControls();
    var draftStorageKey = page.dataset.draftStorageKey;
    var submissionStorageKey = draftStorageKey + ":submission";
    var draftSaveTimer = null;
    var discardDraftOnLeave = false;
    var scalarFieldNames = [
        "requester_name",
        "requester_phone",
        "requester_document",
        "requester_email",
        "service_postal_code",
        "service_address",
        "service_number",
        "service_neighborhood",
        "service_landmark",
        "notes"
    ];

    function setDraftStatus(message, state) {
        draftStatus.textContent = message || "";
        draftStatus.dataset.state = state || "";
        draftStatus.hidden = !message;
    }

    function draftTime(savedAt) {
        var date = new Date(savedAt);
        if (Number.isNaN(date.getTime())) return "";
        return date.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
    }

    function readStoredDraft() {
        try {
            var stored = localStorage.getItem(draftStorageKey);
            return stored ? JSON.parse(stored) : null;
        } catch (error) {
            setDraftStatus("O rascunho não pôde ser acessado neste navegador.", "error");
            return null;
        }
    }

    function clearStoredDraft() {
        if (draftSaveTimer) window.clearTimeout(draftSaveTimer);
        draftSaveTimer = null;
        try {
            localStorage.removeItem(draftStorageKey);
        } catch (error) {
            setDraftStatus("O rascunho não pôde ser removido neste navegador.", "error");
            return;
        }
        setDraftStatus("", "");
    }

    function setSubmissionPending(isPending) {
        try {
            if (isPending) sessionStorage.setItem(submissionStorageKey, "1");
            else sessionStorage.removeItem(submissionStorageKey);
        } catch (error) {
            // The draft remains safe even when session storage is unavailable.
        }
    }

    function submissionWasPending() {
        try {
            return sessionStorage.getItem(submissionStorageKey) === "1";
        } catch (error) {
            return false;
        }
    }

    function digitsOnly(value) {
        return value.replace(/\D/g, "");
    }

    function formatWithPattern(digits, pattern) {
        var formatted = "";
        var digitIndex = 0;
        for (var index = 0; index < pattern.length && digitIndex < digits.length; index += 1) {
            if (pattern[index] === "#") {
                formatted += digits[digitIndex];
                digitIndex += 1;
            } else {
                formatted += pattern[index];
            }
        }
        return formatted;
    }

    function caretAfterDigits(value, count) {
        if (!count) return 0;
        for (var index = 0, seen = 0; index < value.length; index += 1) {
            if (/\d/.test(value[index]) && ++seen === count) return index + 1;
        }
        return value.length;
    }

    function attachMask(field, maximum, choosePattern) {
        function format() {
            var previous = field.value;
            var start = field.selectionStart;
            var end = field.selectionEnd;
            var beforeStart = start === null ? 0 : digitsOnly(previous.slice(0, start)).length;
            var beforeEnd = end === null ? 0 : digitsOnly(previous.slice(0, end)).length;
            var digits = digitsOnly(previous).slice(0, maximum);
            field.value = formatWithPattern(digits, choosePattern(digits.length));
            if (start !== null && end !== null && document.activeElement === field) {
                field.setSelectionRange(
                    caretAfterDigits(field.value, beforeStart),
                    caretAfterDigits(field.value, beforeEnd)
                );
            }
        }

        field.addEventListener("input", format);
        field.addEventListener("keydown", function (event) {
            if (field.selectionStart !== field.selectionEnd) return;
            var position = field.selectionStart;
            if (event.key === "Backspace" && position > 0 && /\D/.test(field.value[position - 1])) {
                var previousDigit = position - 1;
                while (previousDigit >= 0 && /\D/.test(field.value[previousDigit])) previousDigit -= 1;
                if (previousDigit >= 0) field.setSelectionRange(previousDigit, position);
            } else if (event.key === "Delete" && position < field.value.length && /\D/.test(field.value[position])) {
                var nextDigit = position;
                while (nextDigit < field.value.length && /\D/.test(field.value[nextDigit])) nextDigit += 1;
                if (nextDigit < field.value.length) field.setSelectionRange(position, nextDigit + 1);
            }
        });
        format();
    }

    attachMask(page.querySelector("[data-mask-phone]"), 11, function (length) {
        return length > 10 ? "(##) #####-####" : "(##) ####-####";
    });
    attachMask(page.querySelector("[data-mask-document]"), 14, function (length) {
        return length > 11 ? "##.###.###/####-##" : "###.###.###-##";
    });

    var cepInput = page.querySelector("[data-mask-cep]");
    var addressInput = page.querySelector("[data-service-address]");
    var neighborhoodInput = page.querySelector("[data-service-neighborhood]");
    var cepStatus = page.querySelector("[data-cep-status]");
    var currentCep = digitsOnly(cepInput.value);
    var lookupVersion = 0;
    var lookupController = null;
    var autofilledAddress = "";
    var autofilledNeighborhood = "";

    attachMask(cepInput, 8, function () { return "#####-###"; });

    function setCepStatus(message, state) {
        cepStatus.textContent = message;
        cepStatus.hidden = !message;
        cepStatus.dataset.state = state || "";
    }

    function clearAutofilledLocation() {
        if (autofilledAddress && addressInput.value === autofilledAddress) addressInput.value = "";
        if (autofilledNeighborhood && neighborhoodInput.value === autofilledNeighborhood) neighborhoodInput.value = "";
        autofilledAddress = "";
        autofilledNeighborhood = "";
    }

    function fillFromCep(field, value, previousAutofill) {
        if (!value || (field.value && field.value !== previousAutofill)) return false;
        field.value = value;
        return true;
    }

    function searchCep(cep) {
        var version = ++lookupVersion;
        var controller = new AbortController();
        lookupController = controller;
        var timeout = setTimeout(function () { controller.abort(); }, 8000);
        setCepStatus("Buscando CEP...", "");

        fetch("https://viacep.com.br/ws/" + cep + "/json/", { signal: controller.signal })
            .then(function (response) {
                if (!response.ok) throw new Error("Falha na consulta de CEP");
                return response.json();
            })
            .then(function (result) {
                if (version !== lookupVersion || digitsOnly(cepInput.value) !== cep) return;
                if (!result || result.erro) {
                    setCepStatus("CEP não encontrado. Informe o local manualmente.", "error");
                    return;
                }

                var street = (result.logradouro || "").trim();
                var neighborhood = (result.bairro || "").trim();
                if (fillFromCep(addressInput, street, autofilledAddress)) autofilledAddress = street;
                if (fillFromCep(neighborhoodInput, neighborhood, autofilledNeighborhood)) {
                    autofilledNeighborhood = neighborhood;
                }
                setCepStatus(street ? "CEP localizado. Confira ou complete os dados do local." :
                    "CEP localizado. Informe o endereço/localidade manualmente.", "success");
            })
            .catch(function () {
                if (version === lookupVersion) {
                    setCepStatus("Não foi possível consultar o CEP. Informe o local manualmente.", "error");
                }
            })
            .finally(function () {
                clearTimeout(timeout);
                if (lookupController === controller) lookupController = null;
            });
    }

    cepInput.addEventListener("input", function () {
        var cep = digitsOnly(cepInput.value);
        if (cep !== currentCep) {
            clearAutofilledLocation();
            currentCep = cep;
        }
        lookupVersion += 1;
        if (lookupController) lookupController.abort();
        lookupController = null;
        if (cep.length === 8) searchCep(cep);
        else setCepStatus("Busca automática com 8 dígitos.", "");
    });

    cepInput.addEventListener("blur", function () {
        var cep = digitsOnly(cepInput.value);
        if (cep.length > 0 && cep.length < 8) {
            setCepStatus("Informe os 8 dígitos do CEP ou deixe o campo vazio.", "error");
        }
    });

    if (currentCep.length === 8) searchCep(currentCep);

    var items = page.querySelector("[data-service-items]");
    var addButton = page.querySelector("[data-service-add]");
    var firstRow = items.querySelector("[data-service-item]");
    var serviceOptions = Array.from(firstRow.querySelector("[data-service-select]").options);
    var hasAvailableServices = serviceOptions.some(function (option) { return Boolean(option.value); });
    addButton.disabled = !hasAvailableServices;
    page.querySelector(".service-request__submit").disabled = !hasAvailableServices;
    var units = Array.from(new Set(serviceOptions.map(function (option) {
        return (option.dataset.unit || "").trim();
    }).filter(Boolean)));

    function populateUnits(row) {
        var service = row.querySelector("[data-service-select]");
        var unit = row.querySelector("[data-unit-select]");
        var selectedOption = service.selectedOptions[0];
        var defaultUnit = selectedOption ? (selectedOption.dataset.unit || "").trim() : "";

        unit.replaceChildren(new Option("Selecione", ""));
        units.forEach(function (value) { unit.add(new Option(value, value)); });
        unit.value = defaultUnit;
    }

    function renumber() {
        var rows = Array.from(items.querySelectorAll("[data-service-item]"));
        rows.forEach(function (row, index) {
            var number = index + 1;
            var badge = row.querySelector("[data-service-number]");
            var remove = row.querySelector("[data-service-remove]");
            badge.textContent = number;
            badge.setAttribute("aria-label", "Serviço " + number);
            remove.setAttribute("aria-label", "Remover serviço " + number);
            remove.disabled = rows.length === 1;

            [
                ["[data-service-select]", "requested-service-"],
                ["[name='quantities']", "service-quantity-"],
                ["[data-unit-select]", "service-unit-"]
            ].forEach(function (entry) {
                var control = row.querySelector(entry[0]);
                control.id = entry[1] + number;
                control.closest(".service-request__field").querySelector("label").htmlFor = control.id;
            });
        });
    }

    function applyServiceItem(row, item) {
        var service = row.querySelector("[data-service-select]");
        var quantity = row.querySelector("[name='quantities']");
        var unit = row.querySelector("[data-unit-select]");

        service.value = item && item.service ? item.service : "";
        quantity.value = item && item.quantity ? item.quantity : "1";
        populateUnits(row);
        if (item && item.unit && Array.from(unit.options).some(function (option) {
            return option.value === item.unit;
        })) {
            unit.value = item.unit;
        }
    }

    function appendServiceItem(item, shouldFocus) {
        var row = firstRow.cloneNode(true);
        applyServiceItem(row, item);
        items.appendChild(row);
        renumber();
        if (shouldFocus) row.querySelector("[data-service-select]").focus();
        return row;
    }

    function collectDraft() {
        var fields = {};
        scalarFieldNames.forEach(function (name) {
            var field = form.elements.namedItem(name);
            fields[name] = field ? field.value : "";
        });

        return {
            version: 1,
            savedAt: new Date().toISOString(),
            fields: fields,
            services: Array.from(items.querySelectorAll("[data-service-item]")).map(function (row) {
                return {
                    service: row.querySelector("[data-service-select]").value,
                    quantity: row.querySelector("[name='quantities']").value,
                    unit: row.querySelector("[data-unit-select]").value
                };
            })
        };
    }

    function draftHasContent(draft) {
        var hasScalarValue = scalarFieldNames.some(function (name) {
            return Boolean((draft.fields[name] || "").trim());
        });
        var hasServiceValue = draft.services.some(function (item) {
            return Boolean(item.service || item.unit || (item.quantity && item.quantity !== "1"));
        });
        return hasScalarValue || hasServiceValue || draft.services.length > 1;
    }

    function saveDraft() {
        if (discardDraftOnLeave) return;
        var draft = collectDraft();
        if (!draftHasContent(draft)) {
            clearStoredDraft();
            return;
        }

        try {
            localStorage.setItem(draftStorageKey, JSON.stringify(draft));
            setDraftStatus("Rascunho salvo automaticamente às " + draftTime(draft.savedAt) + ".", "saved");
        } catch (error) {
            setDraftStatus("O rascunho não pôde ser salvo neste navegador.", "error");
        }
    }

    function scheduleDraftSave() {
        if (draftSaveTimer) window.clearTimeout(draftSaveTimer);
        draftSaveTimer = window.setTimeout(saveDraft, 250);
    }

    function restoreDraft(draft) {
        if (!draft || draft.version !== 1 || !draft.fields || !Array.isArray(draft.services)) return false;

        scalarFieldNames.forEach(function (name) {
            var field = form.elements.namedItem(name);
            if (field && typeof draft.fields[name] === "string") field.value = draft.fields[name];
        });

        Array.from(items.querySelectorAll("[data-service-item]")).slice(1).forEach(function (row) {
            row.remove();
        });
        applyServiceItem(firstRow, draft.services[0]);
        draft.services.slice(1).forEach(function (item) { appendServiceItem(item, false); });
        renumber();

        ["[data-mask-phone]", "[data-mask-document]", "[data-mask-cep]"].forEach(function (selector) {
            var field = page.querySelector(selector);
            if (field) field.dispatchEvent(new Event("input", { bubbles: false }));
        });

        setDraftStatus("Rascunho de " + (draftTime(draft.savedAt) || "uma sessão anterior") +
            " restaurado automaticamente.", "restored");
        return true;
    }

    function resetRequestForm() {
        form.reset();
        Array.from(items.querySelectorAll("[data-service-item]")).slice(1).forEach(function (row) {
            row.remove();
        });
        applyServiceItem(firstRow, null);
        renumber();

        lookupVersion += 1;
        if (lookupController) lookupController.abort();
        lookupController = null;
        currentCep = "";
        autofilledAddress = "";
        autofilledNeighborhood = "";
        setCepStatus("Busca automática com 8 dígitos.", "");

        clearStoredDraft();
        setSubmissionPending(false);
        setDraftStatus("Formulário limpo. O rascunho também foi removido.", "cleared");
        form.elements.namedItem("requester_name").focus();
    }

    populateUnits(firstRow);

    addButton.addEventListener("click", function () {
        appendServiceItem(null, true);
        scheduleDraftSave();
    });

    items.addEventListener("change", function (event) {
        if (event.target.matches("[data-service-select]")) {
            populateUnits(event.target.closest("[data-service-item]"));
        }
    });

    items.addEventListener("click", function (event) {
        var remove = event.target.closest("[data-service-remove]");
        if (!remove || items.querySelectorAll("[data-service-item]").length === 1) return;
        var nextFocus = remove.closest("[data-service-item]").previousElementSibling ||
            remove.closest("[data-service-item]").nextElementSibling;
        remove.closest("[data-service-item]").remove();
        renumber();
        scheduleDraftSave();
        if (nextFocus) nextFocus.querySelector("[data-service-select]").focus();
    });

    var successfulSubmission = submissionWasPending() && Boolean(document.querySelector(".app-toast--success"));
    setSubmissionPending(false);
    if (successfulSubmission) clearStoredDraft();
    else restoreDraft(readStoredDraft());

    form.addEventListener("input", scheduleDraftSave);
    form.addEventListener("change", scheduleDraftSave);
    form.addEventListener("submit", function () {
        saveDraft();
        setSubmissionPending(true);
    });

    clearButton.addEventListener("click", function () {
        if (draftHasContent(collectDraft()) &&
            !window.confirm("Limpar todos os campos e apagar o rascunho salvo?")) return;
        resetRequestForm();
    });

    var discardLink = page.querySelector("[data-draft-discard]");
    discardLink.addEventListener("click", function () {
        discardDraftOnLeave = true;
        clearStoredDraft();
        setSubmissionPending(false);
    });

    window.addEventListener("pagehide", saveDraft);
}());
