(() => {
  const button = document.getElementById("mic");
  const status = document.getElementById("status");
  const caption = document.getElementById("caption");
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const replyAudioPlayer = new Audio();
  const silentAudioSource = "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAIA+AAACABAAZGF0YQAAAAA=";
  let recognition = null;
  let args = {};
  let currentReplyNonce = null;
  const replyNonceStorageKey = "carevoice-last-spoken-reply";
  let pendingSpeechTimer = null;
  let recognitionRestartTimer = null;
  let recordingRequested = false;
  let recognitionActive = false;
  let transcriptBuffer = "";
  let sessionTranscript = "";
  const labels = () => {
    const telugu = String(args.lang_code || "en-IN").toLowerCase().startsWith("te");
    return {
      tap: telugu ? "మాట్లాడటానికి నొక్కండి" : "Tap to Speak",
      speaking: telugu ? "సమాధానం వినిపిస్తోంది..." : "Speaking reply...",
      audioUnavailable: telugu ? "వాయిస్ ప్లే కాలేదు. బ్రౌజర్ వాయిస్ మరియు సౌండ్ సెట్టింగ్‌లను తనిఖీ చేయండి." : "Voice playback is unavailable. Check your browser voice and sound settings.",
      listening: telugu ? "వింటున్నాను..." : "Listening...",
      permission: telugu ? "మైక్రోఫోన్ అనుమతి ఇవ్వండి." : "Microphone permission is blocked. Allow it in browser settings.",
      unsupported: telugu ? "ఈ బ్రౌజర్‌లో మాట గుర్తింపు అందుబాటులో లేదు." : "Speech recognition is not supported in this browser.",
      retry: telugu ? "మీ మాటలు వినిపించలేదు. మళ్లీ ప్రయత్నించండి." : "I didn't catch that. Please try again.",
      you: telugu ? "మీరు" : "You",
    };
  };

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

  function normalizeSpeechText(text) {
    let cleaned = String(text || "")
      .replace(/\*\*|__|`/g, "")
      .replace(/\s*\n\s*/g, " ")
      .replace(/\s{2,}/g, " ")
      .replace(/^\s*[-*•]\s*/gm, "")
      .replace(/^\s*(\d+)\.\s*/gm, "$1. ")
      .trim();
    if (!cleaned) return "";
    if (/^[\d\s\-/.,%:]+$/.test(cleaned)) {
      return String(args.lang_code || "en-IN").toLowerCase().startsWith("te")
        ? `సమాధానం ${cleaned}`
        : `The answer is ${cleaned}`;
    }
    return cleaned;
  }

  function selectVoiceForGender(voices, langCode, voiceGender) {
    const languagePrefix = String(langCode || "en-IN").slice(0, 2).toLowerCase();
    const languageVoices = voices.filter((voice) =>
      String(voice.lang || "").toLowerCase().startsWith(languagePrefix)
    );
    const gender = String(voiceGender || "Female Voice").toLowerCase();
    const isFemale = ["female", "girl", "woman", "women"].some((word) => gender.includes(word));
    const femaleNames = [
      "female", "zira", "heera", "hazel", "susan", "samantha", "victoria",
      "karen", "catherine", "aria", "emma", "ava", "jenny", "michelle",
      "sonia", "libby", "natasha", "moira",
    ];
    const maleNames = [
      "david", "mark", "george", "ravi", "alex", "daniel", "guy", "ryan",
      "tony", "thomas", "oliver", "liam", "eric", "andrew",
    ];
    const matchesGender = (voice) => {
      const name = String(voice.name || "").toLowerCase();
      if (isFemale) return femaleNames.some((hint) => name.includes(hint));
      return !femaleNames.some((hint) => name.includes(hint))
        && (maleNames.some((hint) => name.includes(hint))
          || /(^|[\s-])male($|[\s-])/.test(name));
    };
    return languageVoices.find(matchesGender) || voices.find(matchesGender) || null;
  }

  function rememberSpokenReply(replyNonce) {
    try { window.sessionStorage.setItem(replyNonceStorageKey, replyNonce); } catch (error) {}
  }

  function unlockAudioPlayback() {
    replyAudioPlayer.src = silentAudioSource;
    const playback = replyAudioPlayer.play();
    if (playback && typeof playback.then === "function") {
      playback.then(() => {
        replyAudioPlayer.pause();
        replyAudioPlayer.currentTime = 0;
      }).catch(() => {});
    }
    if ("speechSynthesis" in window) window.speechSynthesis.resume();
  }

  function playReplyAudio(replyNonce) {
    if (!args.reply_audio) return Promise.resolve(false);
    replyAudioPlayer.pause();
    replyAudioPlayer.src = args.reply_audio;
    replyAudioPlayer.currentTime = 0;
    return replyAudioPlayer.play().then(() => {
      rememberSpokenReply(replyNonce);
      status.textContent = labels().speaking;
      return true;
    }).catch(() => false);
  }

  function speakReply() {
    const replyNonce = String(args.reply_nonce || "");
    if (!args.reply_text || !replyNonce || replyNonce === currentReplyNonce) return;
    try {
      if (window.sessionStorage.getItem(replyNonceStorageKey) === replyNonce) return;
    } catch (error) {}
    currentReplyNonce = replyNonce;
    let fallbackStarted = false;
    let speechStarted = false;
    const useAudioFallback = () => {
      if (fallbackStarted) return;
      fallbackStarted = true;
      if (pendingSpeechTimer !== null) {
        window.clearTimeout(pendingSpeechTimer);
        pendingSpeechTimer = null;
      }
      if ("speechSynthesis" in window) window.speechSynthesis.cancel();
      playReplyAudio(replyNonce).then((played) => {
        if (!played && currentReplyNonce === replyNonce) {
          status.textContent = labels().audioUnavailable;
        }
      });
    };
    if ("speechSynthesis" in window && "SpeechSynthesisUtterance" in window) {
      const plainText = normalizeSpeechText(args.reply_text);
      const utterance = new SpeechSynthesisUtterance(plainText);
      utterance.lang = args.lang_code || "en-IN";
      utterance.rate = 1.0;
      utterance.pitch = 1.0;
      utterance.volume = 1;
      const languagePrefix = utterance.lang.slice(0, 2).toLowerCase();
      let attempts = 0;
      let started = false;
      const speakWhenVoicesLoad = () => {
        if (started || currentReplyNonce !== replyNonce) return;
        const voices = window.speechSynthesis.getVoices();
        const selectedVoice = selectVoiceForGender(voices, utterance.lang, args.voice_gender);

        if ((!voices.length || (languagePrefix === "te" && !selectedVoice)) && attempts < 30) {
          attempts += 1;
          pendingSpeechTimer = window.setTimeout(speakWhenVoicesLoad, 150);
          return;
        }

        started = true;
        pendingSpeechTimer = null;
        if (!selectedVoice && languagePrefix === "te") {
          useAudioFallback();
          return;
        }
        if (selectedVoice) utterance.voice = selectedVoice;
        utterance.onstart = () => {
          speechStarted = true;
          if (pendingSpeechTimer !== null) {
            window.clearTimeout(pendingSpeechTimer);
            pendingSpeechTimer = null;
          }
          rememberSpokenReply(replyNonce);
          status.textContent = labels().speaking;
        };
        utterance.onerror = useAudioFallback;
        window.speechSynthesis.cancel();
        try {
          window.speechSynthesis.resume();
          window.speechSynthesis.speak(utterance);
          pendingSpeechTimer = window.setTimeout(() => {
            if (!speechStarted) useAudioFallback();
          }, 3000);
        } catch (error) {
          useAudioFallback();
        }
      };
      speakWhenVoicesLoad();
      return;
    }
    useAudioFallback();
  }

  function render(event) {
    args = event.data.args || {};
    const copy = labels();
    button.setAttribute("aria-label", copy.tap);
    caption.textContent = args.user_text ? `${copy.you}: ${args.user_text}` : "";
    if (!recognition && Recognition) {
      recognition = new Recognition();
      recognition.lang = args.lang_code || "en-IN";
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.maxAlternatives = 1;
      recognition.onstart = () => {
        recognitionActive = true;
        button.setAttribute("aria-pressed", "true");
        button.setAttribute("aria-label", labels().listening);
        status.textContent = labels().listening;
        caption.textContent = transcriptBuffer ? `${labels().you}: ${transcriptBuffer}` : "";
      };
      recognition.onresult = (resultEvent) => {
        let interimText = "";
        const finalParts = [];
        for (let index = 0; index < resultEvent.results.length; index++) {
          const result = resultEvent.results[index];
          if (result.isFinal) finalParts.push(result[0].transcript.trim());
          else interimText += result[0].transcript;
        }
        sessionTranscript = finalParts.join(" ").trim();
        const visibleText = [transcriptBuffer, sessionTranscript, interimText.trim()].filter(Boolean).join(" ");
        caption.textContent = visibleText ? `${copy.you}: ${visibleText}` : "";
      };
      recognition.onerror = (errorEvent) => {
        const currentLabels = labels();
        if (["not-allowed", "service-not-allowed", "audio-capture"].includes(errorEvent.error)) {
          recordingRequested = false;
          status.textContent = errorEvent.error === "audio-capture" ? currentLabels.retry : currentLabels.permission;
        } else {
          status.textContent = currentLabels.listening;
        }
      };
      recognition.onend = () => {
        recognitionActive = false;
        if (sessionTranscript) {
          transcriptBuffer = [transcriptBuffer, sessionTranscript].filter(Boolean).join(" ").trim();
          sessionTranscript = "";
        }
        if (recordingRequested) {
          window.clearTimeout(recognitionRestartTimer);
          recognitionRestartTimer = window.setTimeout(() => {
            if (!recordingRequested) return;
            try { recognition.start(); }
            catch (error) { recognitionRestartTimer = window.setTimeout(() => {
              if (recordingRequested) {
                try { recognition.start(); } catch (retryError) { recordingRequested = false; }
              }
            }, 300); }
          }, 250);
          return;
        }
        button.setAttribute("aria-pressed", "false");
        button.setAttribute("aria-label", labels().tap);
        status.textContent = transcriptBuffer ? labels().tap : labels().retry;
        if (transcriptBuffer) {
          setComponentValue({ text: transcriptBuffer, event_id: `${Date.now()}-${Math.random()}` });
          transcriptBuffer = "";
        }
      };
      button.addEventListener("click", () => {
        if (!recognition) return;
        unlockAudioPlayback();
        if (pendingSpeechTimer !== null) {
          window.clearTimeout(pendingSpeechTimer);
          pendingSpeechTimer = null;
        }
        if ("speechSynthesis" in window) window.speechSynthesis.cancel();
        if (recordingRequested) {
          recordingRequested = false;
          window.clearTimeout(recognitionRestartTimer);
          if (recognitionActive) {
            recognition.stop();
          } else {
            button.setAttribute("aria-pressed", "false");
            button.setAttribute("aria-label", labels().tap);
            status.textContent = transcriptBuffer ? labels().tap : labels().retry;
            if (transcriptBuffer) {
              setComponentValue({ text: transcriptBuffer, event_id: `${Date.now()}-${Math.random()}` });
              transcriptBuffer = "";
            }
          }
          return;
        }
        transcriptBuffer = "";
        sessionTranscript = "";
        recordingRequested = true;
        currentReplyNonce = String(args.reply_nonce || currentReplyNonce || "");
        if (currentReplyNonce) {
          try { window.sessionStorage.setItem(replyNonceStorageKey, currentReplyNonce); } catch (error) {}
        }
        recognition.lang = args.lang_code || "en-IN";
        status.textContent = labels().listening;
        try { recognition.start(); }
        catch (error) {
          recordingRequested = false;
          status.textContent = labels().permission;
        }
      });
    }
    if (!Recognition) status.textContent = copy.unsupported;
    else if (status.textContent === "") status.textContent = copy.tap;
    speakReply();
    setFrameHeight();
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