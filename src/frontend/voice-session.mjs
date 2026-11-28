const AudioEngine = window.AudioContext || window.webkitAudioContext;

export function supportsVoice() {
  return !!(AudioEngine && window.MediaRecorder && navigator.mediaDevices?.getUserMedia);
}

export function createVoiceSession({ transcribe, respond, synthesize, onState, onAssistantText, greeting }) {
  const context = new AudioEngine();
  const requests = new AbortController();
  const signal = requests.signal;
  let stream;
  let ending = false;
  let endOpening;
  let endCapture;
  let endPlayback;
  let playbackRequest;
  let voicebotRequest;
  const opening = context.resume();

  function captureTurn(analyser) {
    return new Promise((resolve, reject) => {
      const samples = new Float32Array(analyser.fftSize);
      const chunks = [];
      let recorder;
      let startedAt;
      let lastSpeech;
      let noise = 0.003;

      function finish() {
        clearInterval(timer);
        endCapture = undefined;
        if (recorder?.state === "recording") recorder.stop();
        else if (!recorder) resolve(null);
      }

      endCapture = finish;
      const timer = setInterval(() => {
        analyser.getFloatTimeDomainData(samples);
        const rms = Math.sqrt(samples.reduce((sum, value) => sum + value * value, 0) / samples.length);
        const now = performance.now();
        const speaking = rms > Math.max(0.008, noise * 3);
        if (!recorder && !speaking) {
          noise = 0.95 * noise + 0.05 * rms;
          return;
        }
        if (!recorder) {
          try {
            recorder = new MediaRecorder(stream);
            recorder.ondataavailable = event => { if (event.data.size) chunks.push(event.data); };
            recorder.onstop = () => resolve(lastSpeech - startedAt >= 120
              ? new Blob(chunks, { type: recorder.mimeType }) : null);
            recorder.onerror = () => { finish(); reject(new Error("บันทึกเสียงไม่ได้")); };
            recorder.start();
            startedAt = now;
            onState("กำลังฟังคุณพูด…", "recording");
          } catch (error) {
            clearInterval(timer);
            endCapture = undefined;
            reject(error);
          }
        }
        if (speaking) lastSpeech = now;
        if (now - lastSpeech >= 850 || now - startedAt >= 18000) finish();
      }, 30);
    });
  }

  async function play(utterance) {
    if (!utterance?.text || ending || signal.aborted) return;
    if (!utterance.url) {
      onAssistantText(utterance.text);
      return;
    }
    playbackRequest = new AbortController();
    const audioSignal = playbackRequest.signal;
    try {
      onState("กำลังเตรียมเสียงตอบ…", "waiting");
      const blob = await synthesize(utterance.url, audioSignal);
      if (ending || audioSignal.aborted) return;
      const buffer = await context.decodeAudioData(await blob.arrayBuffer());
      if (ending || audioSignal.aborted) return;
      const source = context.createBufferSource();
      source.buffer = buffer;
      source.connect(context.destination);
      onState("AI กำลังพูด…", "speaking");
      await new Promise(resolve => {
        source.onended = resolve;
        endPlayback = () => { source.stop(); resolve(); };
        source.start();
      });
    } catch {
      if (!ending && !signal.aborted) onState("เล่นเสียงตอบไม่ได้ · พูดเพื่อคุยต่อได้", "waiting");
    } finally {
      endPlayback = undefined;
      playbackRequest = undefined;
    }
    if (!ending && !audioSignal.aborted) onAssistantText(utterance.text);
  }

  function stop() {
    ending = true;
    endOpening?.();
    endCapture?.();
    voicebotRequest?.abort();
    playbackRequest?.abort();
    endPlayback?.();
    stream?.getTracks().forEach(track => track.stop());
  }

  async function run() {
    try {
      onState("กำลังเปิดไมโครโฟน…", "waiting");
      await opening;
      if (ending) return;
      const permission = navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      }).then(input => {
        if (ending) input.getTracks().forEach(track => track.stop());
        return input;
      });
      stream = await Promise.race([permission, new Promise(resolve => { endOpening = resolve; })]);
      endOpening = undefined;
      if (ending) return;
      const track = stream.getAudioTracks()[0];
      track?.addEventListener("ended", () => {
        if (!ending) {
          stop();
          onState("ไมโครโฟนหยุดทำงาน · กดจบการสนทนาเพื่อดูสรุป", "waiting");
        }
      });
      const analyser = context.createAnalyser();
      analyser.fftSize = 1024;
      context.createMediaStreamSource(stream).connect(analyser);
      await play(greeting);
      let listening = "พร้อมฟัง · พูดได้เลย";
      while (!ending && !signal.aborted) {
        onState(listening, "listening");
        const recording = await captureTurn(analyser);
        if (signal.aborted || (ending && !recording?.size)) break;
        if (!recording?.size) continue;
        listening = "พร้อมฟัง · พูดได้เลย";
        try {
          if (!ending) onState("กำลังถอดเสียง…", "waiting");
          const { text } = await transcribe(recording, signal);
          if (signal.aborted) break;
          if (!text?.trim()) {
            listening = "ยังจับคำพูดไม่ได้ · ลองพูดอีกครั้ง";
            continue;
          }
          voicebotRequest = new AbortController();
          const answer = await respond(text, voicebotRequest.signal, !ending);
          if (answer) await play({ text: answer.reply_text, url: answer.tts_audio_url });
        } catch {
          listening = "ประมวลผลเสียงรอบนี้ไม่ได้ · ลองพูดอีกครั้ง";
        } finally {
          voicebotRequest = undefined;
        }
      }
    } finally {
      stop();
      await context.close().catch(() => {});
    }
  }

  return { run, finish: stop, cancel() { requests.abort(); stop(); } };
}
