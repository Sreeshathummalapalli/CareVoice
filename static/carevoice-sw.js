self.addEventListener("install", (event) => {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("push", (event) => {
  if (!event.data) return;

  let payload;
  try {
    payload = event.data.json();
  } catch (error) {
    return;
  }

  event.waitUntil((async () => {
    if ("BroadcastChannel" in self) {
      const reminders = new BroadcastChannel("carevoice-reminders");
      reminders.postMessage({ type: "carevoice-reminder", ...payload });
      reminders.close();
    }

    const telugu = String(payload.lang || "").toLowerCase().startsWith("te");
    await self.registration.showNotification(payload.title || "CareVoice Medicine Reminder", {
      body: payload.body || "A scheduled medicine is due.",
      tag: `carevoice-${payload.medicine_id}-${payload.scheduled_time}`,
      renotify: true,
      data: payload,
      actions: [
        { action: "take", title: telugu ? "తీసుకున్నాను" : "Taken" },
        { action: "snooze", title: telugu ? "5 నిమిషాలు వాయిదా" : "Snooze 5m" },
      ],
    });
  })());
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const payload = event.notification.data || {};

  event.waitUntil((async () => {
    if (["take", "snooze", "skip"].includes(event.action)) {
      const telugu = String(payload.lang || "").toLowerCase().startsWith("te");
      try {
        const response = await fetch(payload.action_endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ token: payload.action_token, action: event.action }),
        });
        const result = await response.json();
        await self.registration.showNotification(
          response.ok ? (telugu ? "మందుల నమోదు నవీకరించబడింది" : "Medicine log updated") : (telugu ? "నమోదు చేయలేకపోయాం" : "Could not update medicine log"),
          { body: result.message || (telugu ? "తర్వాత మళ్లీ ప్రయత్నించండి." : "Please try again from CareVoice."), tag: `carevoice-action-${payload.medicine_id}` },
        );
      } catch (error) {
        await self.registration.showNotification(
          "CareVoice",
          {
            body: telugu
              ? "ఈ రిమైండర్ చర్యను సేవ్ చేయలేకపోయాం. కేర్‌వాయిస్‌ను తెరిచి మళ్లీ ప్రయత్నించండి."
              : "Could not save this reminder action. Open CareVoice and try again.",
          },
        );
      }
      return;
    }

    const target = new URL(payload.app_url || "/", self.location.origin);
    if (target.origin !== self.location.origin) return;
    target.searchParams.set("due_med_id", String(payload.medicine_id || ""));
    target.searchParams.set("due_med_time", String(payload.scheduled_time || ""));
    const windows = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
    const appWindow = windows.find((client) => new URL(client.url).origin === self.location.origin);
    if (appWindow) {
      await appWindow.navigate(target.href);
      return appWindow.focus();
    }
    return self.clients.openWindow(target.href);
  })());
});