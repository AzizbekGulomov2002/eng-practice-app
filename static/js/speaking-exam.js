(function () {
  var dataEl = document.getElementById("speak-data");
  if (!dataEl) return;
  var QUESTIONS = [];
  try { QUESTIONS = JSON.parse(dataEl.textContent || "[]"); } catch (e) { QUESTIONS = []; }
  if (!QUESTIONS.length) return;

  var index = 0;
  var phase = "prep";
  var remaining = 0;
  var tickId = null;
  var stream = null;
  var recorder = null;
  var chunks = [];
  var audioCtx = null;
  var analyser = null;
  var sourceNode = null;
  var waveRaf = null;

  var timerEl = document.getElementById("speakTimer");
  var numEl = document.getElementById("speakNum");
  var qEl = document.getElementById("speakQuestion");
  var prepIcon = document.getElementById("speakPrepIcon");
  var talkIcon = document.getElementById("speakTalkIcon");
  var wave = document.getElementById("speakWave");
  var startBtn = document.getElementById("speakStart");
  var stopBtn = document.getElementById("speakStop");
  var readBtn = document.getElementById("speakRead");
  var form = document.getElementById("speak-form");

  function current() { return QUESTIONS[index]; }

  function plain(htmlOrText) {
    var div = document.createElement("div");
    div.innerHTML = htmlOrText || "";
    return (div.textContent || "").replace(/\s+/g, " ").trim();
  }

  function stopSpeak() {
    if (window.speechSynthesis) window.speechSynthesis.cancel();
  }

  function speakQuestion() {
    if (phase === "talk") return;
    stopSpeak();
    if (!window.speechSynthesis) return;
    var text = current().text || plain(current().html);
    if (!text) return;
    var utter = new SpeechSynthesisUtterance(text);
    utter.lang = "en-GB";
    utter.rate = 0.95;
    window.speechSynthesis.speak(utter);
  }

  function renderQuestion() {
    var q = current();
    numEl.textContent = (q.number || index + 1) + ".";
    qEl.textContent = q.text || plain(q.html) || "Question";
  }

  function renderTimer() {
    if (phase === "prep") {
      timerEl.textContent = "Preparation: " + remaining + " s";
      timerEl.className = "speak-timer speak-timer-prep";
    } else {
      timerEl.textContent = "Speaking: " + remaining + " s";
      timerEl.className = "speak-timer speak-timer-talk";
    }
  }

  function setPhase(next) {
    phase = next;
    var talking = next === "talk";
    prepIcon.hidden = talking;
    talkIcon.hidden = !talking;
    wave.hidden = !talking;
    startBtn.hidden = talking;
    stopBtn.hidden = !talking;
    if (readBtn) readBtn.hidden = talking;
  }

  function stopTick() {
    if (tickId) {
      clearInterval(tickId);
      tickId = null;
    }
  }

  function startTick() {
    stopTick();
    renderTimer();
    tickId = setInterval(function () {
      remaining -= 1;
      if (remaining < 0) remaining = 0;
      renderTimer();
      if (remaining <= 0) {
        stopTick();
        if (phase === "prep") startTalk();
        else finishQuestion();
      }
    }, 1000);
  }

  function ensureMic(cb) {
    if (stream) {
      cb(stream);
      return;
    }
    navigator.mediaDevices.getUserMedia({ audio: true }).then(function (s) {
      stream = s;
      cb(stream);
    }).catch(function () {
      alert("Microphone permission is required to start the speaking test.");
    });
  }

  function startWave(s) {
    try {
      var Ctx = window.AudioContext || window.webkitAudioContext;
      if (!Ctx) return;
      if (!audioCtx) audioCtx = new Ctx();
      if (audioCtx.state === "suspended") audioCtx.resume();
      analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256;
      if (sourceNode) {
        try { sourceNode.disconnect(); } catch (e) {}
      }
      sourceNode = audioCtx.createMediaStreamSource(s);
      sourceNode.connect(analyser);
      drawWave();
    } catch (e) {}
  }

  function stopWave() {
    if (waveRaf) cancelAnimationFrame(waveRaf);
    waveRaf = null;
    if (wave) {
      var ctx = wave.getContext("2d");
      ctx.clearRect(0, 0, wave.width, wave.height);
    }
  }

  function drawWave() {
    if (!analyser || wave.hidden) {
      waveRaf = requestAnimationFrame(drawWave);
      return;
    }
    var ctx = wave.getContext("2d");
    var data = new Uint8Array(analyser.frequencyBinCount);
    analyser.getByteFrequencyData(data);
    ctx.clearRect(0, 0, wave.width, wave.height);
    var bars = 42;
    var gap = 3;
    var w = (wave.width - gap * (bars - 1)) / bars;
    ctx.fillStyle = "#22c55e";
    for (var i = 0; i < bars; i++) {
      var v = data[Math.floor(i * data.length / bars)] / 255;
      var h = Math.max(4, v * wave.height);
      var x = i * (w + gap);
      var y = (wave.height - h) / 2;
      ctx.beginPath();
      if (ctx.roundRect) ctx.roundRect(x, y, w, h, 2);
      else ctx.rect(x, y, w, h);
      ctx.fill();
    }
    waveRaf = requestAnimationFrame(drawWave);
  }

  function startRecording(s) {
    chunks = [];
    var mime = "";
    if (window.MediaRecorder) {
      if (MediaRecorder.isTypeSupported("audio/webm;codecs=opus")) mime = "audio/webm;codecs=opus";
      else if (MediaRecorder.isTypeSupported("audio/webm")) mime = "audio/webm";
    }
    try {
      recorder = mime ? new MediaRecorder(s, { mimeType: mime }) : new MediaRecorder(s);
    } catch (e) {
      recorder = new MediaRecorder(s);
    }
    recorder.ondataavailable = function (e) {
      if (e.data && e.data.size) chunks.push(e.data);
    };
    recorder.start(200);
    startWave(s);
  }

  function saveBlob(done) {
    var q = current();
    var type = (recorder && recorder.mimeType) || "audio/webm";
    var blob = new Blob(chunks, { type: type });
    var input = document.getElementById("record_" + q.number);
    if (input) {
      var file = new File([blob], "speaking-q" + q.number + ".webm", { type: blob.type || "audio/webm" });
      var dt = new DataTransfer();
      dt.items.add(file);
      input.files = dt.files;
    }
    if (done) done();
  }

  function stopRecording(done) {
    stopWave();
    if (!recorder || recorder.state === "inactive") {
      saveBlob(done);
      return;
    }
    recorder.onstop = function () {
      saveBlob(done);
    };
    recorder.stop();
  }

  function startPrep() {
    setPhase("prep");
    remaining = current().prep_time || 5;
    renderQuestion();
    renderTimer();
    speakQuestion();
    startTick();
  }

  function startTalk() {
    if (phase === "talk") return;
    stopTick();
    stopSpeak();
    ensureMic(function (s) {
      stopSpeak();
      setPhase("talk");
      remaining = current().answer_time || 20;
      renderTimer();
      startRecording(s);
      startTick();
    });
  }

  function finishQuestion() {
    stopTick();
    stopSpeak();
    stopBtn.disabled = true;
    startBtn.disabled = true;
    stopRecording(function () {
      index += 1;
      stopBtn.disabled = false;
      startBtn.disabled = false;
      if (index >= QUESTIONS.length) {
        form.submit();
        return;
      }
      startPrep();
    });
  }

  startBtn.addEventListener("click", startTalk);
  stopBtn.addEventListener("click", finishQuestion);
  readBtn.addEventListener("click", speakQuestion);

  startPrep();
})();
