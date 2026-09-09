(function () {
    "use strict";

    var page = document.querySelector("[data-service-types-page]");
    if (!page) return;

    var search = page.querySelector("[data-service-types-search]");
    var status = page.querySelector("[data-service-types-status]");
    var reset = page.querySelector("[data-service-types-reset]");
    var summary = page.querySelector("[data-service-types-summary]");
    var tableWrapper = page.querySelector("[data-service-types-table-wrapper]");
    var empty = page.querySelector("[data-service-types-empty]");
    var emptyTitle = page.querySelector("[data-service-types-empty-title]");
    var emptyDescription = page.querySelector("[data-service-types-empty-description]");
    var emptyIcon = page.querySelector("[data-service-types-empty-icon]");

    // Filtra os registros enviados pela view e renderizados no template, sem novas requisições.
    function normalizeText(value) {
        return value.normalize("NFD").replace(/[\u0300-\u036f]/g, "")
            .toLocaleLowerCase("pt-BR").trim().replace(/\s+/g, " ");
    }

    var records = Array.from(page.querySelectorAll("[data-service-type-row]")).map(function (row) {
        return {
            element: row,
            name: normalizeText(row.querySelector("[data-service-type-name]").textContent),
            status: row.getAttribute("data-service-type-status")
        };
    });

    // Os indicadores representam a lista completa, independentemente dos filtros.
    page.querySelector('[data-service-types-count="total"]').textContent = records.length;
    ["active", "inactive"].forEach(function (value) {
        page.querySelector('[data-service-types-count="' + value + '"]').textContent =
            records.filter(function (record) { return record.status === value; }).length;
    });

    function applyFilters() {
        var query = normalizeText(search.value);
        var visible = 0;

        records.forEach(function (record) {
            var matches = record.name.includes(query) &&
                (status.value === "all" || record.status === status.value);
            record.element.hidden = !matches;
            if (matches) visible += 1;
        });

        summary.textContent = "Exibindo " + visible + " de " + records.length +
            (records.length === 1 ? " tipo de serviço." : " tipos de serviço.");
        reset.disabled = search.value.length === 0 && status.value === "all";
        tableWrapper.hidden = visible === 0;
        empty.hidden = visible !== 0;

        var hasRecords = records.length > 0;
        emptyTitle.textContent = hasRecords
            ? "Nenhum tipo de serviço encontrado."
            : "Nenhum tipo de serviço cadastrado.";
        emptyDescription.textContent = hasRecords
            ? "Tente outro nome ou altere o filtro de situação."
            : "Os tipos de serviço cadastrados aparecerão aqui.";
        emptyIcon.className = "fa-solid " + (hasRecords ? "fa-magnifying-glass" : "fa-list-check");
    }

    search.addEventListener("input", applyFilters);
    status.addEventListener("change", applyFilters);
    reset.addEventListener("click", function () {
        search.value = "";
        status.value = "all";
        applyFilters();
        search.focus();
    });

    applyFilters();

    var modal = page.querySelector("[data-service-type-modal]");
    if (!modal) return;

    var modalTitle = modal.querySelector("[data-service-type-modal-title]");
    var modalDescription = modal.querySelector("[data-service-type-modal-description]");
    var createForm = modal.querySelector("[data-service-type-create-form]");
    var fields = modal.querySelector("[data-service-type-modal-fields]");
    var details = modal.querySelector("[data-service-type-modal-details]");
    var cancelButton = modal.querySelector("[data-service-type-modal-cancel]");
    var editButton = modal.querySelector("[data-service-type-modal-edit]");
    var saveButton = modal.querySelector("[data-service-type-modal-save]");
    var saveButtonLabel = modal.querySelector("[data-service-type-modal-save-label]");
    var nameInput = modal.querySelector("[data-service-type-name-input]");
    var unitInput = modal.querySelector("[data-service-type-unit-input]");
    var statusInput = modal.querySelector("[data-service-type-status-input]");
    var statusText = modal.querySelector("[data-service-type-status-text]");
    var statusValue = modal.querySelector("[data-service-type-status-value]");
    var selectedRecord = null;
    var modalOpener = null;
    var backdropPressed = false;
    var currentMode = "create";

    function readRowText(row, selector) {
        var element = row.querySelector(selector);
        return element ? element.textContent.trim() : "";
    }

    function readRecord(row) {
        return {
            name: readRowText(row, "[data-service-type-name]"),
            unit: row.getAttribute("data-service-type-unit") || "",
            status: row.getAttribute("data-service-type-status"),
            updateUrl: row.getAttribute("data-service-type-update-url"),
            createdAt: readRowText(row, "[data-service-type-created-at]"),
            createdBy: readRowText(row, "[data-service-type-created-by]"),
            updatedAt: readRowText(row, "[data-service-type-updated-at]"),
            updatedBy: readRowText(row, "[data-service-type-updated-by]")
        };
    }

    function setStatusInput(value) {
        var isActive = value === "active";
        statusInput.value = isActive ? "active" : "inactive";
        statusInput.setAttribute("aria-checked", String(isActive));
        statusText.textContent = isActive ? "Ativo" : "Inativo";
        statusValue.value = isActive ? "True" : "False";
    }

    function setModalMode(mode) {
        var isDetails = mode === "details";
        var isEdit = mode === "edit";
        currentMode = mode;
        modalTitle.textContent = isDetails ? "Detalhes do tipo de serviço" :
            (isEdit ? "Editar tipo de serviço" : "Novo tipo de serviço");
        modalDescription.textContent = isDetails ? "Confira as informações do tipo de serviço." :
            (isEdit ? "Revise as informações do tipo de serviço." : "Defina o serviço que poderá ser utilizado nas solicitações.");
        fields.hidden = isDetails;
        details.hidden = !isDetails;
        cancelButton.textContent = isDetails ? "Fechar" : "Cancelar";
        editButton.hidden = !isDetails;
        saveButton.hidden = isDetails;
        saveButton.disabled = isDetails;
        saveButtonLabel.textContent = "Salvar";
        saveButton.removeAttribute("aria-busy");
        createForm.action = isEdit && selectedRecord
            ? selectedRecord.updateUrl
            : createForm.dataset.serviceTypeCreateUrl;

        nameInput.value = selectedRecord ? selectedRecord.name : "";
        unitInput.value = selectedRecord ? selectedRecord.unit : "";
        setStatusInput(selectedRecord ? selectedRecord.status : "active");

        if (isDetails && selectedRecord) {
            details.querySelectorAll("[data-service-type-detail]").forEach(function (field) {
                field.textContent = selectedRecord[field.getAttribute("data-service-type-detail")] || "—";
            });
            var active = selectedRecord.status === "active";
            details.querySelector("[data-service-type-detail-status]").className =
                "record-status record-status--" + (active ? "active" : "inactive");
            details.querySelector("[data-service-type-detail-status-icon]").className =
                "fa-solid fa-circle-" + (active ? "check" : "xmark");
            details.querySelector("[data-service-type-detail-status-text]").textContent = active ? "Ativo" : "Inativo";
        }

        if (!modal.open) modal.showModal();
        (isDetails ? modalTitle : nameInput).focus();
    }

    page.querySelectorAll("[data-service-type-create-open]").forEach(function (button) {
        button.addEventListener("click", function () {
            modalOpener = button;
            selectedRecord = null;
            setModalMode("create");
        });
    });

    page.querySelectorAll("[data-service-type-details-open]").forEach(function (button) {
        button.addEventListener("click", function () {
            var row = button.closest("[data-service-type-row]");
            if (!row) return;
            modalOpener = button;
            selectedRecord = readRecord(row);
            setModalMode("details");
        });
    });

    page.querySelectorAll("[data-service-type-edit-open]").forEach(function (button) {
        button.addEventListener("click", function () {
            var row = button.closest("[data-service-type-row]");
            if (!row) return;
            modalOpener = button;
            selectedRecord = readRecord(row);
            setModalMode("edit");
        });
    });

    statusInput.addEventListener("click", function () {
        setStatusInput(statusInput.value === "active" ? "inactive" : "active");
    });

    createForm.addEventListener("submit", function (event) {
        if (currentMode === "details" || (currentMode === "edit" && !selectedRecord)) {
            event.preventDefault();
            return;
        }
        saveButton.disabled = true;
        saveButton.setAttribute("aria-busy", "true");
        saveButtonLabel.textContent = currentMode === "edit" ? "Atualizando..." : "Salvando...";
    });

    editButton.addEventListener("click", function () {
        if (selectedRecord) setModalMode("edit");
    });

    modal.querySelectorAll("[data-service-type-modal-close]").forEach(function (button) {
        button.addEventListener("click", function () { modal.close(); });
    });

    function isBackdrop(event) {
        if (event.target !== modal) return false;
        var bounds = modal.getBoundingClientRect();
        return event.clientX < bounds.left || event.clientX > bounds.right ||
            event.clientY < bounds.top || event.clientY > bounds.bottom;
    }

    // Evita fechar quando um arraste começa dentro do formulário e termina fora.
    modal.addEventListener("pointerdown", function (event) { backdropPressed = isBackdrop(event); });
    modal.addEventListener("pointercancel", function () { backdropPressed = false; });
    modal.addEventListener("click", function (event) {
        if (backdropPressed && isBackdrop(event)) modal.close();
        backdropPressed = false;
    });

    // Escape e contenção de foco são fornecidos pelo dialog nativo.
    modal.addEventListener("close", function () {
        selectedRecord = null;
        backdropPressed = false;
        nameInput.value = "";
        unitInput.value = "";
        setStatusInput("active");
        currentMode = "create";
        createForm.action = createForm.dataset.serviceTypeCreateUrl;
        saveButton.disabled = false;
        saveButton.removeAttribute("aria-busy");
        saveButtonLabel.textContent = "Salvar";
        if (modalOpener && modalOpener.isConnected) modalOpener.focus();
        modalOpener = null;
    });
}());
