(function () {
    "use strict";

    self.addEventListener("push", function (event) {
        var payload = {};

        if (event.data) {
            try {
                payload = event.data.json();
            } catch (error) {
                payload = { message: event.data.text() };
            }
        }

        var title = payload.title || "Service Manager";
        var options = {
            body: payload.message || "Você recebeu uma nova atualização.",
            tag: payload.tag || undefined,
            data: {
                url: payload.url || "/operator/list_task/"
            }
        };

        event.waitUntil(self.registration.showNotification(title, options));
    });

    self.addEventListener("notificationclick", function (event) {
        event.notification.close();

        var fallbackUrl = new URL("/operator/list_task/", self.location.origin);
        var requestedUrl;

        try {
            requestedUrl = new URL(event.notification.data.url, self.location.origin);
        } catch (error) {
            requestedUrl = fallbackUrl;
        }

        var pointsToMissingTaskDetail = requestedUrl.pathname.indexOf("/operator/service/") === 0;
        var targetUrl = requestedUrl.origin === self.location.origin && !pointsToMissingTaskDetail
            ? requestedUrl.href
            : fallbackUrl.href;

        event.waitUntil(
            self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(function (clients) {
                var matchingClient = clients.find(function (client) {
                    return client.url === targetUrl;
                });

                if (matchingClient) return matchingClient.focus();

                var sameOriginClient = clients.find(function (client) {
                    return new URL(client.url).origin === self.location.origin;
                });

                if (sameOriginClient && "navigate" in sameOriginClient) {
                    return sameOriginClient.navigate(targetUrl).then(function (client) {
                        return client ? client.focus() : self.clients.openWindow(targetUrl);
                    });
                }

                return self.clients.openWindow(targetUrl);
            })
        );
    });
}());
