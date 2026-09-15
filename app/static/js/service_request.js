(function () {
    "use strict";

    var page = document.querySelector("[data-service-request]");
    if (!page) return;

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

    populateUnits(firstRow);

    addButton.addEventListener("click", function () {
        var row = firstRow.cloneNode(true);
        row.querySelector("[data-service-select]").value = "";
        row.querySelector("[name='quantities']").value = "1";
        populateUnits(row);
        items.appendChild(row);
        renumber();
        row.querySelector("[data-service-select]").focus();
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
        if (nextFocus) nextFocus.querySelector("[data-service-select]").focus();
    });
}());
