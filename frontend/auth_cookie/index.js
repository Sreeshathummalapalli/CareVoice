(() => {
  const cookieName = "carevoice_session";
  let lastCommandNonce = "";

  function readToken() {
    const prefix = `${cookieName}=`;
    const cookie = document.cookie.split(";").map((part) => part.trim())
      .find((part) => part.startsWith(prefix));
    if (!cookie) return "";
    try {
      return decodeURIComponent(cookie.slice(prefix.length));
    } catch (error) {
      return "";
    }
  }

  function writeToken(token) {
    const secure = window.location.protocol === "https:" ? "; Secure" : "";
    document.cookie = `${cookieName}=${encodeURIComponent(token)}; Path=/; Max-Age=2592000; SameSite=Strict${secure}`;
    return readToken() === token;
  }

  function clearToken() {
    const secure = window.location.protocol === "https:" ? "; Secure" : "";
    document.cookie = `${cookieName}=; Path=/; Max-Age=0; SameSite=Strict${secure}`;
  }

  function sendToken(token, error = "") {
    window.parent.postMessage({
      isStreamlitMessage: true,
      type: "streamlit:setComponentValue",
      dataType: "json",
      value: { token, error },
    }, "*");
  }

  function onRender(event) {
    const args = event.data.args || {};
    const command = args.command || {};
    if (command.nonce && command.nonce !== lastCommandNonce) {
      lastCommandNonce = command.nonce;
      if (command.action === "set" && command.token) {
        if (writeToken(command.token)) {
          sendToken(command.token);
        } else {
          sendToken("", "The browser blocked the persistent sign-in cookie. Allow cookies and sign in again.");
        }
        return;
      }
      if (command.action === "clear") {
        clearToken();
        sendToken("");
        return;
      }
    }
    sendToken(readToken());
  }

  window.addEventListener("message", (event) => {
    if (event.data && event.data.type === "streamlit:render") onRender(event);
  });
  window.parent.postMessage({ isStreamlitMessage: true, type: "streamlit:componentReady", apiVersion: 1 }, "*");
  window.parent.postMessage({ isStreamlitMessage: true, type: "streamlit:setFrameHeight", height: 0 }, "*");
})();
