(function () {
    "use strict";

    var script = document.currentScript;
    var toggle = document.querySelector("[data-push-toggle]");

    if (!script || !toggle) return;

    var status = toggle.querySelector("[data-push-status]");
    var registration = null;
    var busy = false;

    var config = {
        vapidUrl: script.getAttribute("data-vapid-url"),
        subscriptionUrl: script.getAttribute("data-subscription-url"),
        serviceWorkerUrl: script.getAttribute("data-service-worker-url")
    };

    function announce(message) {
        if (!status) return;
        status.textContent = "";
        window.setTimeout(function () {
            status.textContent = message;
        }, 20);
    }

    function setState(enabled, message) {
        toggle.setAttribute("aria-checked", enabled ? "true" : "false");
        toggle.setAttribute(
            "aria-label",
            enabled ? "Desativar notificações push" : "Ativar notificações push"
        );
        toggle.title = message || (enabled ? "Notificações ativadas" : "Ativar notificações");
        if (message) announce(message);
    }

    function setBusy(nextBusy) {
        busy = nextBusy;
        toggle.disabled = nextBusy;
        toggle.setAttribute("aria-busy", nextBusy ? "true" : "false");
    }

    function disableControl(message) {
        setState(false, message);
        toggle.disabled = true;
    }

    function getCsrfToken() {
        var input = document.querySelector("[name='csrfmiddlewaretoken']");
        if (input && input.value) return input.value;

        var prefix = "csrftoken=";
        var cookies = document.cookie ? document.cookie.split(";") : [];

        for (var index = 0; index < cookies.length; index += 1) {
            var cookie = cookies[index].trim();
            if (cookie.indexOf(prefix) === 0) {
                return decodeURIComponent(cookie.slice(prefix.length));
            }
        }

        return "";
    }

    async function requestJson(url, options) {
        var response = await window.fetch(url, options || {});
        var payload = {};

        try {
            payload = await response.json();
        } catch (error) {
            payload = {};
        }

        if (!response.ok) {
            throw new Error(payload.error || "Não foi possível concluir a operação.");
        }

        return payload;
    }

    function urlBase64ToUint8Array(value) {
        var padding = "=".repeat((4 - (value.length % 4)) % 4);
        var base64 = (value + padding).replace(/-/g, "+").replace(/_/g, "/");
        var rawData = window.atob(base64);
        var output = new Uint8Array(rawData.length);

        for (var index = 0; index < rawData.length; index += 1) {
            output[index] = rawData.charCodeAt(index);
        }

        return output;
    }

    function waitForActiveWorker(workerRegistration) {
        if (workerRegistration.active) return Promise.resolve(workerRegistration);

        var worker = workerRegistration.installing || workerRegistration.waiting;
        if (!worker) {
            return Promise.reject(new Error("O Service Worker não pôde ser iniciado."));
        }

        return new Promise(function (resolve, reject) {
            var timeoutId = window.setTimeout(function () {
                reject(new Error("O Service Worker demorou demais para iniciar."));
            }, 10000);

            function handleStateChange() {
                if (worker.state === "activated") {
                    window.clearTimeout(timeoutId);
                    resolve(workerRegistration);
                } else if (worker.state === "redundant") {
                    window.clearTimeout(timeoutId);
                    reject(new Error("O Service Worker foi descartado pelo navegador."));
                }
            }

            worker.addEventListener("statechange", handleStateChange);
            handleStateChange();
        });
    }

    async function getRegistration() {
        if (registration) return registration;

        registration = await navigator.serviceWorker.register(config.serviceWorkerUrl);
        registration = await waitForActiveWorker(registration);
        return registration;
    }

    async function getPublicKey() {
        var payload = await requestJson(config.vapidUrl, {
            credentials: "same-origin",
            headers: { "Accept": "application/json" }
        });

        if (!payload.public_key) {
            throw new Error("A chave pública de notificações não foi informada.");
        }

        return urlBase64ToUint8Array(payload.public_key);
    }

    async function saveSubscription(subscription) {
        await requestJson(config.subscriptionUrl, {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-CSRFToken": getCsrfToken()
            },
            body: JSON.stringify(subscription.toJSON())
        });
    }

    async function enableNotifications() {
        var permission = Notification.permission;

        if (permission === "default") {
            permission = await Notification.requestPermission();
        }

        if (permission !== "granted") {
            throw new Error("A permissão de notificações não foi concedida.");
        }

        var workerRegistration = await getRegistration();
        var subscription = await workerRegistration.pushManager.getSubscription();

        if (!subscription) {
            subscription = await workerRegistration.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: await getPublicKey()
            });
        }

        await saveSubscription(subscription);
        setState(true, "Notificações ativadas neste dispositivo.");
    }

    async function disableNotifications() {
        var workerRegistration = await getRegistration();
        var subscription = await workerRegistration.pushManager.getSubscription();

        if (!subscription) {
            setState(false, "As notificações já estavam desativadas.");
            return;
        }

        await requestJson(config.subscriptionUrl, {
            method: "DELETE",
            credentials: "same-origin",
            headers: {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-CSRFToken": getCsrfToken()
            },
            body: JSON.stringify({ endpoint: subscription.endpoint })
        });

        await subscription.unsubscribe();
        setState(false, "Notificações desativadas neste dispositivo.");
    }

    async function handleToggle() {
        if (busy) return;
        setBusy(true);

        try {
            if (toggle.getAttribute("aria-checked") === "true") {
                await disableNotifications();
            } else {
                await enableNotifications();
            }
        } catch (error) {
            console.error("Falha ao atualizar notificações push.", error);
            setState(false, error.message || "Não foi possível atualizar as notificações.");

            if (Notification.permission === "denied") {
                disableControl("Permissão bloqueada nas configurações do navegador.");
            }
        } finally {
            if (Notification.permission !== "denied") setBusy(false);
        }
    }

    async function initialize() {
        if (!window.isSecureContext) {
            disableControl("Notificações exigem HTTPS ou acesso por localhost.");
            return;
        }

        if (!("serviceWorker" in navigator) || !("PushManager" in window) || !("Notification" in window)) {
            disableControl("Este navegador não oferece suporte a notificações push.");
            return;
        }

        if (!config.vapidUrl || !config.subscriptionUrl || !config.serviceWorkerUrl) {
            disableControl("A configuração de notificações está incompleta.");
            return;
        }

        if (Notification.permission === "denied") {
            disableControl("Permissão bloqueada nas configurações do navegador.");
            return;
        }

        try {
            var workerRegistration = await getRegistration();
            var subscription = await workerRegistration.pushManager.getSubscription();

            if (subscription && Notification.permission === "granted") {
                await saveSubscription(subscription);
                setState(true, "Notificações ativas neste dispositivo.");
            } else {
                setState(false);
            }
        } catch (error) {
            console.error("Falha ao iniciar notificações push.", error);
            disableControl(error.message || "Não foi possível iniciar as notificações.");
        }
    }

    toggle.addEventListener("click", handleToggle);
    initialize();
}());
