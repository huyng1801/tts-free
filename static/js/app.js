const DEFAULT_VOICE = "vi-VN-HoaiMyNeural";
const VI_VOICES = [
  "vi-VN-HoaiMyNeural",
  "vi-VN-NamMinhNeural",
];

let allVoices = [];
let pollTimer = null;

const $ = (id) => document.getElementById(id);

const textInput = $("textInput");
const charCount = $("charCount");
const voiceSearch = $("voiceSearch");
const voiceSelect = $("voiceSelect");
const rateSlider = $("rateSlider");
const pitchSlider = $("pitchSlider");
const volumeSlider = $("volumeSlider");
const rateVal = $("rateVal");
const pitchVal = $("pitchVal");
const volumeVal = $("volumeVal");
const generateBtn = $("generateBtn");
const progressBox = $("progressBox");
const progressText = $("progressText");
const progressPercent = $("progressPercent");
const progressFill = $("progressFill");
const errorBox = $("errorBox");
const playerBar = $("playerBar");
const audioPlayer = $("audioPlayer");
const progressEmoji = $("progressEmoji");
const successBox = $("successBox");
const downloadBtn = $("downloadBtn");

const PROGRESS_EMOJIS = ["🌷", "✨", "📖", "🎀", "💫"];

function formatRate(val) {
  if (val === 0) return "Bình thường";
  return val > 0 ? `Nhanh +${val}%` : `Chậm ${val}%`;
}

function formatPitch(val) {
  return val === 0 ? "0 Hz" : `${val > 0 ? "+" : ""}${val} Hz`;
}

function formatVolume(val) {
  const pct = 100 + val;
  return `${pct}%`;
}

function toRateStr(val) {
  return val === 0 ? "+0%" : `${val > 0 ? "+" : ""}${val}%`;
}

function toPitchStr(val) {
  return val === 0 ? "+0Hz" : `${val > 0 ? "+" : ""}${val}Hz`;
}

function toVolumeStr(val) {
  return val === 0 ? "+0%" : `${val > 0 ? "+" : ""}${val}%`;
}

rateSlider.addEventListener("input", () => {
  rateVal.textContent = formatRate(+rateSlider.value);
});

pitchSlider.addEventListener("input", () => {
  pitchVal.textContent = formatPitch(+pitchSlider.value);
});

volumeSlider.addEventListener("input", () => {
  volumeVal.textContent = formatVolume(+volumeSlider.value);
});

textInput.addEventListener("input", () => {
  charCount.textContent = textInput.value.length.toLocaleString("vi-VN");
});

function populateVoices(voices, filter = "") {
  const q = filter.toLowerCase().trim();
  const filtered = q
    ? voices.filter(
        (v) =>
          v.name.toLowerCase().includes(q) ||
          v.friendly.toLowerCase().includes(q) ||
          v.locale.toLowerCase().includes(q)
      )
    : voices;

  voiceSelect.innerHTML = "";
  filtered.forEach((v) => {
    const opt = document.createElement("option");
    opt.value = v.name;
    opt.textContent = `${v.friendly} (${v.locale})`;
    voiceSelect.appendChild(opt);
  });

  if (voiceSelect.options.length === 0) {
    const opt = document.createElement("option");
    opt.value = DEFAULT_VOICE;
    opt.textContent = "vi-VN-HoaiMyNeural";
    voiceSelect.appendChild(opt);
  }

  const saved = localStorage.getItem("bao_ngan_voice") || localStorage.getItem("tts_voice");
  if (saved && [...voiceSelect.options].some((o) => o.value === saved)) {
    voiceSelect.value = saved;
  } else if ([...voiceSelect.options].some((o) => o.value === DEFAULT_VOICE)) {
    voiceSelect.value = DEFAULT_VOICE;
  }
}

voiceSelect.addEventListener("change", () => {
  localStorage.setItem("bao_ngan_voice", voiceSelect.value);
});

voiceSearch.addEventListener("input", () => {
  populateVoices(allVoices, voiceSearch.value);
});

async function loadVoices() {
  try {
    const res = await fetch("/api/voices?locale=vi");
    const data = await res.json();
    if (data.ok && data.voices.length) {
      allVoices = data.voices;
    } else {
      const resAll = await fetch("/api/voices");
      const dataAll = await resAll.json();
      allVoices = dataAll.voices || [];
    }
    populateVoices(allVoices);
  } catch {
    allVoices = VI_VOICES.map((name) => ({
      name,
      friendly: name,
      locale: "vi-VN",
    }));
    populateVoices(allVoices);
  }
}

function setLoading(loading) {
  generateBtn.disabled = loading;
  generateBtn.querySelector(".btn-text").classList.toggle("hidden", loading);
  generateBtn.querySelector(".btn-loader").classList.toggle("hidden", !loading);
}

function showError(msg) {
  errorBox.textContent = msg;
  errorBox.classList.remove("hidden");
}

function hideError() {
  errorBox.classList.add("hidden");
}

function hideSuccess() {
  successBox.classList.add("hidden");
}

function updateProgress(current, total) {
  progressBox.classList.remove("hidden");
  hideSuccess();
  const pct = total ? Math.round((current / total) * 100) : 0;
  if (progressEmoji) {
    progressEmoji.textContent = PROGRESS_EMOJIS[current % PROGRESS_EMOJIS.length];
  }
  if (current === 0) {
    progressText.textContent = "Đang chuẩn bị đọc truyện...";
  } else if (total > 1) {
    progressText.textContent = `Đang đọc đoạn ${current}/${total} nha~`;
  } else {
    progressText.textContent = "Đang tạo truyện audio...";
  }
  progressPercent.textContent = `${pct}%`;
  progressFill.style.width = `${pct}%`;
}

function formatError(msg) {
  if (!msg) return "Lỗi không xác định";
  if (msg.includes("No audio was received")) {
    return "Hmm, chưa tạo được audio. Thử lại sau vài giây nha, hoặc bỏ emoji trong văn bản ~";
  }
  return msg;
}

async function pollStatus(jobId) {
  return new Promise((resolve, reject) => {
    pollTimer = setInterval(async () => {
      try {
        const res = await fetch(`/api/tts/${jobId}/status`);
        const data = await res.json();
        if (!data.ok) {
          clearInterval(pollTimer);
          reject(new Error(data.error));
          return;
        }
        if (data.total) {
          updateProgress(data.progress, data.total);
        }
        if (data.status === "done") {
          clearInterval(pollTimer);
          resolve(data.result);
        } else if (data.status === "error") {
          clearInterval(pollTimer);
          reject(new Error(formatError(data.error)));
        }
      } catch (e) {
        clearInterval(pollTimer);
        reject(e);
      }
    }, 800);
  });
}

generateBtn.addEventListener("click", async () => {
  const text = textInput.value.trim();
  if (!text) {
    showError("Nhập truyện vào ô trên trước nha ♡");
    textInput.focus();
    return;
  }

  hideError();
  hideSuccess();
  setLoading(true);
  progressBox.classList.remove("hidden");
  updateProgress(0, 1);
  playerBar.classList.add("hidden");

  try {
    const res = await fetch("/api/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text,
        voice: voiceSelect.value,
        rate: toRateStr(+rateSlider.value),
        pitch: toPitchStr(+pitchSlider.value),
        volume: toVolumeStr(+volumeSlider.value),
      }),
    });

    const data = await res.json();
    if (!data.ok) throw new Error(data.error);

    await pollStatus(data.job_id);

    updateProgress(1, 1);
    progressText.textContent = "Xong rồi nha!";
    if (progressEmoji) progressEmoji.textContent = "🎉";
    successBox.classList.remove("hidden");
    progressBox.classList.add("hidden");

    const audioUrl = `/api/tts/${data.job_id}/audio?t=${Date.now()}`;
    audioPlayer.src = audioUrl;
    downloadBtn.href = `/api/tts/${data.job_id}/download`;
    playerBar.classList.remove("hidden");

    setTimeout(() => {
      audioPlayer.play().catch(() => {});
    }, 300);
  } catch (e) {
    showError(e.message || "Có lỗi rồi, thử lại nha ~");
    progressBox.classList.add("hidden");
  } finally {
    setLoading(false);
  }
});

loadVoices();
textInput.dispatchEvent(new Event("input"));

const savedText = localStorage.getItem("bao_ngan_draft") || localStorage.getItem("tts_draft");
if (savedText) {
  textInput.value = savedText;
  charCount.textContent = savedText.length.toLocaleString("vi-VN");
}

let saveTimer;
textInput.addEventListener("input", () => {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => {
    localStorage.setItem("bao_ngan_draft", textInput.value);
  }, 500);
});
