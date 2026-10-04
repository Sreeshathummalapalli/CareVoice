(() => {
  const button = document.getElementById("enable");
  const status = document.getElementById("status");
  let args = {};
  let eventId = 0;

  function setFrameHeight() {
    window.parent.postMessage({
      isStreamlitMessage: true,
      type: "streamlit:setFrameHeight",
      height: document.documentElement.scrollHeight,
    }, "*");
  }

  function setComponentValue(value) {
    window.parent.postMessage({
      isStreamlitMessage: true,
      type: "streamlit:setComponentValue",
      dataType: "json",
      value,
    }, "*");
  }

  function decodeApplicationKey(value) {
    const padding = "=".repeat((4 - value.length % 4) % 4);
    const raw = atob((value + padding).replace(/-/g, "+").replace(/_/g, "/"));
    return Uint8Array.from(raw, character => character.charCodeAt(0));
  }

  function render(event) {
    args = event.data.args || {};
    const telugu = String(args.lang_code || "").toLowerCase().startsWith("te");
    button.textContent = telugu ? "బ్రౌజర్ మందుల నోటిఫికేషన్లు ప్రారంభించండి" : "Enable browser medicine notifications";
    status.textContent = telugu
      ? "ఈ ట్యాబ్ పనిచేయకపోయినా రిమైండర్లు పొందడానికి అనుమతించండి."
      : "Allow notifications to receive reminders while this tab is inactive.";
    button.addEventListener("click", enableNotifications, { once: true });
    setFrameHeight();
  }

  async function enableNotifications() {
    button.disabled = true;
    try {
      if (!window.isSecureContext) {
        throw new Error("Browser push notifications require HTTPS or localhost.");
      }
      if (!args.public_key || !("Notification" in window) || !("serviceWorker" in navigator)) {
        throw new Error("Browser push notifications are not available on this connection.");
      }
      let permission = Notification.permission;
      if (permission === "default") permission = await Notification.requestPermission();
      if (permission !== "granted") throw new Error("Notification permission was not granted.");

      const workerUrl = new URL(args.service_worker_url || "/app/static/carevoice-sw.js", window.location.href);
      if (workerUrl.origin !== window.location.origin) {
        throw new Error("The service worker must be served from the CareVoice HTTPS origin.");
      }
      const registration = await navigator.serviceWorker.register(workerUrl.href);
      let subscription = await registration.pushManager.getSubscription();
      if (!subscription) {
        subscription = await registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: decodeApplicationKey(args.public_key),
        });
      }
      status.textContent = "Saving this browser for medicine reminders...";
      setComponentValue({
        subscription: subscription.toJSON(),
        event_id: `${Date.now()}-${++eventId}`,
      });
    } catch (error) {
      status.textContent = error.message;
      button.disabled = false;
      button.addEventListener("click", enableNotifications, { once: true });
    }
  }

  window.addEventListener("message", (event) => {
    if (event.data && event.data.type === "streamlit:render") render(event);
  });
  window.parent.postMessage({
    isStreamlitMessage: true,
    type: "streamlit:componentReady",
    apiVersion: 1,
  }, "*");
  setFrameHeight();
})();