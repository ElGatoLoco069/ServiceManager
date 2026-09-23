(function () {
    "use strict";

    document.addEventListener("DOMContentLoaded", function () {
        var page = document.querySelector("[data-operator-tasks]");
        if (!page) return;

        var filters = Array.prototype.slice.call(page.querySelectorAll("[data-task-filter]"));
        var cards = Array.prototype.slice.call(page.querySelectorAll("[data-task-card]"));
        var emptyState = page.querySelector("[data-task-empty]");
        var summary = page.querySelector("[data-task-filter-summary]");
        var todayCount = page.querySelector("[data-today-task-count]");
        var todayLabel = page.querySelector("[data-today-task-label]");
        var progressCount = page.querySelector("[data-progress-task-count]");
        var greetingPeriod = page.querySelector("[data-greeting-period]");
        var todayDate = page.querySelector("[data-today-date]");
        var emptyTitle = page.querySelector("[data-task-empty-title]");
        var emptyDescription = page.querySelector("[data-task-empty-description]");
        var taskDialog = document.querySelector("[data-task-dialog]");
        var taskDialogTitle = taskDialog && taskDialog.querySelector("[data-task-dialog-title]");
        var taskDialogBody = taskDialog && taskDialog.querySelector("[data-task-dialog-body]");
        var taskDialogFeedback = taskDialog && taskDialog.querySelector("[data-task-dialog-feedback]");
        var taskStartForm = taskDialog && taskDialog.querySelector("[data-task-start-form]");
        var taskStartSubmit = taskDialog && taskDialog.querySelector("[data-task-start-submit]");
        var taskStartLabel = taskDialog && taskDialog.querySelector("[data-task-start-label]");
        var taskCompleteOpen = taskDialog && taskDialog.querySelector("[data-task-complete-open]");
        var completionDialog = document.querySelector("[data-task-completion-dialog]");
        var completionForm = completionDialog && completionDialog.querySelector("[data-task-completion-form]");
        var completionTitle = completionDialog && completionDialog.querySelector("[data-task-completion-title]");
        var completionService = completionDialog && completionDialog.querySelector("[data-task-completion-service]");
        var completionProtocol = completionDialog && completionDialog.querySelector("[data-task-completion-protocol]");
        var completionInputs = completionDialog
            ? Array.prototype.slice.call(completionDialog.querySelectorAll("[data-task-completion-input]"))
            : [];
        var completionCameraInput = completionDialog && completionDialog.querySelector("[data-task-completion-camera-input]");
        var completionGalleryInput = completionDialog && completionDialog.querySelector("[data-task-completion-gallery-input]");
        var completionEmpty = completionDialog && completionDialog.querySelector("[data-task-completion-empty]");
        var completionPreview = completionDialog && completionDialog.querySelector("[data-task-completion-preview]");
        var completionImage = completionDialog && completionDialog.querySelector("[data-task-completion-image]");
        var completionFileName = completionDialog && completionDialog.querySelector("[data-task-completion-file-name]");
        var completionFileSize = completionDialog && completionDialog.querySelector("[data-task-completion-file-size]");
        var completionConfirm = completionDialog && completionDialog.querySelector("[data-task-completion-confirm]");
        var completionConfirmLabel = completionDialog && completionDialog.querySelector("[data-task-completion-confirm-label]");
        var completionFeedback = completionDialog && completionDialog.querySelector("[data-task-completion-feedback]");
        var taskDialogOpener = null;
        var completionReturnFocus = null;
        var openCompletionAfterTaskClose = false;
        var completionPreviewUrl = "";
        var selectedCompletionInput = null;
        var currentTaskService = "Serviço";
        var currentTaskProtocol = "Protocolo";
        var currentTaskFinishUrl = "";

        function getTodayKey() {
            var now = new Date();
            return [
                now.getFullYear(),
                String(now.getMonth() + 1).padStart(2, "0"),
                String(now.getDate()).padStart(2, "0")
            ].join("-");
        }

        function pluralizeTasks(count) {
            return count === 1 ? "tarefa" : "tarefas";
        }

        function updateIndicators() {
            var todayKey = getTodayKey();
            var todayCards = cards.filter(function (card) {
                return card.dataset.taskDate === todayKey;
            });
            var inProgressCards = todayCards.filter(function (card) {
                return card.dataset.taskStatus === "in_progress";
            });

            if (todayCount) todayCount.textContent = String(todayCards.length);
            if (todayLabel) todayLabel.textContent = todayCards.length === 1 ? "serviço" : "serviços";
            if (progressCount) progressCount.textContent = String(inProgressCards.length);
        }

        function updateGreeting() {
            if (!greetingPeriod) return;
            var hour = new Date().getHours();
            greetingPeriod.textContent = hour < 12 ? "Bom dia" : (hour < 18 ? "Boa tarde" : "Boa noite");
        }

        function updateTodayDate() {
            if (!todayDate || typeof Intl === "undefined") return;
            var now = new Date();
            var formattedDate = new Intl.DateTimeFormat("pt-BR", {
                weekday: "long",
                day: "2-digit",
                month: "long"
            }).format(now);

            todayDate.dateTime = getTodayKey();
            todayDate.textContent = formattedDate.charAt(0).toUpperCase() + formattedDate.slice(1);
        }

        function applyFilter(status) {
            var visibleCount = 0;

            cards.forEach(function (card) {
                var isVisible = status === "all" || card.dataset.taskStatus === status;
                card.hidden = !isVisible;
                if (isVisible) visibleCount += 1;
            });

            filters.forEach(function (filter) {
                var isActive = filter.dataset.taskFilter === status;
                filter.classList.toggle("is-active", isActive);
                filter.setAttribute("aria-pressed", String(isActive));
            });

            if (emptyState) {
                emptyState.hidden = visibleCount !== 0;
                if (visibleCount === 0 && emptyTitle && emptyDescription) {
                    var hasAssignedTasks = cards.length > 0;
                    emptyTitle.textContent = hasAssignedTasks
                        ? "Nenhuma tarefa neste status"
                        : "Nenhuma tarefa atribuída";
                    emptyDescription.textContent = hasAssignedTasks
                        ? "Selecione outro filtro para conferir suas demais tarefas."
                        : "Não há serviços designados para você no momento.";
                }
            }
            if (summary) {
                summary.textContent = visibleCount === 0
                    ? "Nenhuma tarefa encontrada para este filtro."
                    : "Exibindo " + visibleCount + " " + pluralizeTasks(visibleCount) + ".";
            }
        }

        function closeTaskDialog() {
            if (!taskDialog) return;
            if (typeof taskDialog.close === "function" && taskDialog.open) {
                taskDialog.close();
                return;
            }
            taskDialog.removeAttribute("open");
        }

        function showLocationFeedback() {
            if (!taskDialogFeedback) return;
            taskDialogFeedback.textContent = "A visualização da localização ainda não abre um mapa.";
            taskDialogFeedback.hidden = false;
        }

        function updateStartAction(button) {
            if (!taskStartForm || !taskStartSubmit || !taskStartLabel || !taskCompleteOpen) return;
            var status = button.dataset.taskStartStatus;
            var canStart = status === "pending" || status === "scheduled";

            taskStartForm.hidden = status === "in_progress";
            taskCompleteOpen.hidden = status !== "in_progress";

            if (canStart) {
                taskStartForm.action = button.dataset.taskStartUrl || "";
            } else {
                taskStartForm.removeAttribute("action");
            }
            taskStartSubmit.disabled = !canStart;
            taskStartSubmit.setAttribute("aria-disabled", String(!canStart));
            taskStartLabel.textContent = status === "completed"
                ? "Tarefa concluída"
                : (status === "canceled" ? "Tarefa cancelada" : "Iniciar tarefa");

            if (!canStart && status !== "in_progress") {
                taskStartSubmit.title = status === "completed"
                    ? "Esta tarefa já foi concluída"
                    : "Esta tarefa não pode mais ser iniciada";
            } else {
                taskStartSubmit.removeAttribute("title");
            }
        }

        function clearCompletionPreview() {
            if (completionPreviewUrl) {
                URL.revokeObjectURL(completionPreviewUrl);
                completionPreviewUrl = "";
            }
            completionInputs.forEach(function (input) {
                input.value = "";
            });
            selectedCompletionInput = null;
            if (completionImage) completionImage.removeAttribute("src");
            if (completionFileName) completionFileName.textContent = "";
            if (completionFileSize) completionFileSize.textContent = "";
            if (completionEmpty) completionEmpty.hidden = false;
            if (completionPreview) completionPreview.hidden = true;
            if (completionConfirm) {
                completionConfirm.disabled = true;
                completionConfirm.setAttribute("aria-disabled", "true");
            }
            if (completionConfirmLabel) completionConfirmLabel.textContent = "Concluir tarefa";
        }

        function clearCompletionFeedback() {
            if (!completionFeedback) return;
            completionFeedback.textContent = "";
            completionFeedback.hidden = true;
            completionFeedback.removeAttribute("data-state");
        }

        function showCompletionFeedback(message, state) {
            if (!completionFeedback) return;
            completionFeedback.textContent = message;
            completionFeedback.hidden = false;
            completionFeedback.dataset.state = state || "info";
        }

        function formatFileSize(size) {
            if (size < 1024) return size + " B";
            if (size < 1024 * 1024) return (size / 1024).toFixed(1).replace(".", ",") + " KB";
            return (size / (1024 * 1024)).toFixed(1).replace(".", ",") + " MB";
        }

        function closeCompletionDialog() {
            if (!completionDialog) return;
            if (typeof completionDialog.close === "function" && completionDialog.open) {
                completionDialog.close();
                return;
            }
            completionDialog.removeAttribute("open");
        }

        function openCompletionDialog() {
            if (!completionDialog) return;
            clearCompletionPreview();
            clearCompletionFeedback();
            if (completionService) completionService.textContent = currentTaskService;
            if (completionProtocol) completionProtocol.textContent = "Protocolo #" + currentTaskProtocol;
            if (completionForm) completionForm.action = currentTaskFinishUrl;

            if (typeof completionDialog.showModal === "function") {
                if (!completionDialog.open) completionDialog.showModal();
            } else {
                completionDialog.setAttribute("open", "");
            }
            if (completionTitle) completionTitle.focus();
        }

        function selectCompletionPhoto(input) {
            if (input) input.click();
        }

        function handleCompletionPhoto(event) {
            var input = event.currentTarget;
            if (!input || !input.files || !input.files[0]) {
                clearCompletionPreview();
                return;
            }

            var file = input.files[0];
            var isImage = file.type.indexOf("image/") === 0 || /\.(avif|bmp|gif|heic|heif|jpe?g|png|webp)$/i.test(file.name);
            if (!isImage) {
                clearCompletionPreview();
                showCompletionFeedback("Selecione um arquivo de imagem para visualizar.", "error");
                return;
            }

            clearCompletionFeedback();
            completionInputs.forEach(function (candidate) {
                if (candidate !== input) candidate.value = "";
            });
            selectedCompletionInput = input;
            if (completionPreviewUrl) URL.revokeObjectURL(completionPreviewUrl);
            completionPreviewUrl = URL.createObjectURL(file);
            if (completionImage) completionImage.src = completionPreviewUrl;
            if (completionFileName) completionFileName.textContent = file.name;
            if (completionFileSize) {
                completionFileSize.textContent = (input.dataset.completionSource || "Foto") +
                    " • " + formatFileSize(file.size);
            }
            if (completionEmpty) completionEmpty.hidden = true;
            if (completionPreview) completionPreview.hidden = false;
            if (completionConfirm) {
                completionConfirm.disabled = false;
                completionConfirm.setAttribute("aria-disabled", "false");
            }
        }

        function openTaskDialog(button) {
            if (!taskDialog || !taskDialogBody) return;
            var card = button.closest("[data-task-card]");
            var details = card && card.querySelector("[data-task-details]");
            if (!details) return;

            taskDialogBody.replaceChildren(details.content.cloneNode(true));
            if (taskDialogFeedback) {
                taskDialogFeedback.textContent = "";
                taskDialogFeedback.hidden = true;
            }
            currentTaskService = button.dataset.taskService || "Serviço";
            currentTaskProtocol = button.dataset.taskProtocol || "Protocolo";
            currentTaskFinishUrl = button.dataset.taskFinishUrl || "";
            updateStartAction(button);
            taskDialogOpener = button;

            if (typeof taskDialog.showModal === "function") {
                if (!taskDialog.open) taskDialog.showModal();
            } else {
                taskDialog.setAttribute("open", "");
            }
            if (taskDialogTitle) taskDialogTitle.focus();
        }

        filters.forEach(function (filter) {
            filter.addEventListener("click", function () {
                applyFilter(filter.dataset.taskFilter);
                filter.scrollIntoView({ block: "nearest", inline: "nearest" });
            });
        });

        if (taskDialog) {
            page.querySelectorAll("[data-task-details-open]").forEach(function (button) {
                button.addEventListener("click", function () {
                    openTaskDialog(button);
                });
            });

            taskDialog.querySelectorAll("[data-task-dialog-close]").forEach(function (button) {
                button.addEventListener("click", closeTaskDialog);
            });

            taskDialog.querySelectorAll("[data-task-visual-action]").forEach(function (button) {
                button.addEventListener("click", function () {
                    showLocationFeedback();
                });
            });

            if (taskStartForm && taskStartSubmit && taskStartLabel) {
                taskStartForm.addEventListener("submit", function () {
                    taskStartSubmit.disabled = true;
                    taskStartSubmit.setAttribute("aria-disabled", "true");
                    taskStartLabel.textContent = "Iniciando...";
                });
            }

            if (taskCompleteOpen) {
                taskCompleteOpen.addEventListener("click", function () {
                    completionReturnFocus = taskDialogOpener;
                    openCompletionAfterTaskClose = true;
                    closeTaskDialog();
                });
            }

            var backdropPressed = false;
            taskDialog.addEventListener("pointerdown", function (event) {
                if (event.target !== taskDialog) {
                    backdropPressed = false;
                    return;
                }
                var bounds = taskDialog.getBoundingClientRect();
                backdropPressed = event.clientX < bounds.left || event.clientX > bounds.right ||
                    event.clientY < bounds.top || event.clientY > bounds.bottom;
            });
            taskDialog.addEventListener("pointercancel", function () {
                backdropPressed = false;
            });
            taskDialog.addEventListener("click", function (event) {
                if (backdropPressed && event.target === taskDialog) closeTaskDialog();
                backdropPressed = false;
            });
            taskDialog.addEventListener("close", function () {
                var opener = taskDialogOpener;
                var shouldOpenCompletion = openCompletionAfterTaskClose;
                taskDialogOpener = null;
                openCompletionAfterTaskClose = false;
                if (taskDialogBody) taskDialogBody.replaceChildren();
                if (taskStartForm) taskStartForm.removeAttribute("action");
                if (taskStartForm) taskStartForm.hidden = false;
                if (taskCompleteOpen) taskCompleteOpen.hidden = true;
                if (taskStartSubmit) {
                    taskStartSubmit.disabled = false;
                    taskStartSubmit.setAttribute("aria-disabled", "false");
                    taskStartSubmit.removeAttribute("title");
                }
                if (taskStartLabel) taskStartLabel.textContent = "Iniciar tarefa";
                if (taskDialogFeedback) {
                    taskDialogFeedback.textContent = "";
                    taskDialogFeedback.hidden = true;
                }
                if (shouldOpenCompletion) {
                    openCompletionDialog();
                } else if (opener && document.contains(opener)) {
                    opener.focus();
                }
            });
        }

        if (completionDialog) {
            completionDialog.querySelectorAll("[data-task-completion-close]").forEach(function (button) {
                button.addEventListener("click", closeCompletionDialog);
            });

            var completionCameraButton = completionDialog.querySelector("[data-task-completion-camera]");
            var completionGalleryButton = completionDialog.querySelector("[data-task-completion-gallery]");
            if (completionCameraButton) {
                completionCameraButton.addEventListener("click", function () {
                    selectCompletionPhoto(completionCameraInput);
                });
            }
            if (completionGalleryButton) {
                completionGalleryButton.addEventListener("click", function () {
                    selectCompletionPhoto(completionGalleryInput);
                });
            }

            completionDialog.querySelectorAll("[data-task-completion-remove]").forEach(function (button) {
                button.addEventListener("click", function () {
                    clearCompletionPreview();
                    clearCompletionFeedback();
                });
            });

            completionInputs.forEach(function (input) {
                input.addEventListener("change", handleCompletionPhoto);
            });

            if (completionForm && completionConfirm) {
                completionForm.addEventListener("submit", function (event) {
                    if (!selectedCompletionInput || !selectedCompletionInput.files ||
                        !selectedCompletionInput.files[0]) {
                        event.preventDefault();
                        showCompletionFeedback("Selecione uma foto antes de concluir a tarefa.", "error");
                        return;
                    }
                    completionConfirm.disabled = true;
                    completionConfirm.setAttribute("aria-disabled", "true");
                    if (completionConfirmLabel) completionConfirmLabel.textContent = "Concluindo...";
                });
            }

            var completionBackdropPressed = false;
            completionDialog.addEventListener("pointerdown", function (event) {
                if (event.target !== completionDialog) {
                    completionBackdropPressed = false;
                    return;
                }
                var bounds = completionDialog.getBoundingClientRect();
                completionBackdropPressed = event.clientX < bounds.left || event.clientX > bounds.right ||
                    event.clientY < bounds.top || event.clientY > bounds.bottom;
            });
            completionDialog.addEventListener("pointercancel", function () {
                completionBackdropPressed = false;
            });
            completionDialog.addEventListener("click", function (event) {
                if (completionBackdropPressed && event.target === completionDialog) closeCompletionDialog();
                completionBackdropPressed = false;
            });
            completionDialog.addEventListener("close", function () {
                clearCompletionPreview();
                clearCompletionFeedback();
                if (completionForm) completionForm.removeAttribute("action");
                if (completionReturnFocus && document.contains(completionReturnFocus)) completionReturnFocus.focus();
                completionReturnFocus = null;
            });
        }

        updateGreeting();
        updateTodayDate();
        updateIndicators();
        applyFilter("all");
    });
}());
