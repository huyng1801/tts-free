const $t = (id) => document.getElementById(id);

let currentStory = null;
let allChapters = [];

const storySearch = $t("storySearch");
const storySearchBtn = $t("storySearchBtn");
const storyResults = $t("storyResults");
const storySelected = $t("storySelected");
const selectedStoryTitle = $t("selectedStoryTitle");
const selectedStoryMeta = $t("selectedStoryMeta");
const chapterPicker = $t("chapterPicker");
const chapterFilter = $t("chapterFilter");
const chapterSelect = $t("chapterSelect");
const chapterNumInput = $t("chapterNumInput");
const chapterPrevBtn = $t("chapterPrevBtn");
const chapterNextBtn = $t("chapterNextBtn");
const loadChapterBtn = $t("loadChapterBtn");
const truyenhoanStatus = $t("truyenhoanStatus");
const panelTruyenhoan = $t("panelTruyenhoan");

function setStoryText(value) {
  const input = $t("textInput");
  const count = $t("charCount");
  if (!input) return;
  input.value = value;
  if (count) count.textContent = value.length.toLocaleString("vi-VN");
  input.dispatchEvent(new Event("input", { bubbles: true }));
  localStorage.setItem("bao_ngan_draft", value);
}

function showStatus(msg, isError = false) {
  truyenhoanStatus.textContent = msg;
  truyenhoanStatus.classList.remove("hidden", "error");
  if (isError) truyenhoanStatus.classList.add("error");
}

function hideStatus() {
  truyenhoanStatus.classList.add("hidden");
}

function setLoading(btn, loading) {
  if (!btn) return;
  btn.disabled = loading;
  btn.dataset.loading = loading ? "1" : "";
}

function renderStoryResults(stories) {
  storyResults.innerHTML = "";
  if (!stories.length) {
    storyResults.innerHTML = '<p class="empty-hint">Không tìm thấy truyện nào ~</p>';
    storyResults.classList.remove("hidden");
    return;
  }
  stories.forEach((s) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "story-item";
    btn.innerHTML = `<span class="story-item-title">${escapeHtml(s.title)}</span>`;
    btn.addEventListener("click", () => selectStory(s.url, s.title));
    storyResults.appendChild(btn);
  });
  storyResults.classList.remove("hidden");
}

function escapeHtml(str) {
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

async function searchStories() {
  const q = storySearch.value.trim();
  if (!q) {
    showStatus("Nhập tên truyện trước nha ♡", true);
    return;
  }

  if (q.includes("truyenhoan.com")) {
    if (q.includes("chuong-")) {
      hideStatus();
      setLoading(storySearchBtn, true);
      try {
        const res = await fetch(`/api/truyenhoan/chapter?url=${encodeURIComponent(q)}`);
        const data = await res.json();
        if (!data.ok) throw new Error(data.error);
        if (data.chapter.story_url) {
          await selectStory(data.chapter.story_url);
          chapterNumInput.value = data.chapter.number;
          await loadChapter(false);
        } else {
          setStoryText(`${data.chapter.title}\n\n${data.chapter.text}`);
          showStatus(`Đã lấy ${data.chapter.title}`);
        }
      } catch (e) {
        showStatus(e.message || "Link không hợp lệ", true);
      } finally {
        setLoading(storySearchBtn, false);
      }
      return;
    }
    await selectStory(q);
    return;
  }

  hideStatus();
  setLoading(storySearchBtn, true);
  storyResults.classList.add("hidden");
  try {
    const res = await fetch(`/api/truyenhoan/search?q=${encodeURIComponent(q)}`);
    const data = await res.json();
    if (!data.ok) throw new Error(data.error);
    renderStoryResults(data.stories);
    showStatus(`Tìm thấy ${data.stories.length} truyện`);
  } catch (e) {
    showStatus(e.message || "Không tìm được truyện", true);
  } finally {
    setLoading(storySearchBtn, false);
  }
}

async function selectStory(url, titleHint = "") {
  hideStatus();
  showStatus("Đang tải danh sách chương...");
  chapterPicker.classList.add("hidden");
  storySelected.classList.add("hidden");
  setLoading(storySearchBtn, true);
  try {
    const res = await fetch(`/api/truyenhoan/story?url=${encodeURIComponent(url)}`);
    const data = await res.json();
    if (!data.ok) throw new Error(data.error);
    currentStory = data.story;
    allChapters = data.story.chapters || [];

    selectedStoryTitle.textContent = data.story.title || titleHint;
    selectedStoryMeta.textContent = `${data.story.chapter_count} chương · ${data.story.slug}`;
    storySelected.classList.remove("hidden");

    populateChapters(allChapters);
    chapterPicker.classList.remove("hidden");
    storyResults.classList.add("hidden");
    hideStatus();
  } catch (e) {
    showStatus(e.message || "Không tải được truyện", true);
  } finally {
    setLoading(storySearchBtn, false);
  }
}

function populateChapters(chapters, filter = "") {
  const q = filter.trim().toLowerCase();
  chapterSelect.innerHTML = "";
  const filtered = q
    ? chapters.filter(
        (c) =>
          String(c.number).includes(q) ||
          c.title.toLowerCase().includes(q)
      )
    : chapters;

  filtered.forEach((c) => {
    const opt = document.createElement("option");
    opt.value = c.number;
    opt.textContent = c.title.length > 60 ? `Ch.${c.number}` : c.title;
    opt.dataset.url = c.url;
    chapterSelect.appendChild(opt);
  });

  if (filtered.length) {
    chapterSelect.value = filtered[0].number;
    chapterNumInput.value = filtered[0].number;
    chapterNumInput.max = currentStory?.max_chapter || filtered[0].number;
  }
}

function getSelectedChapter() {
  const num = parseInt(chapterSelect.value, 10);
  return allChapters.find((c) => c.number === num);
}

function goChapter(delta) {
  const current = parseInt(chapterSelect.value, 10);
  const idx = allChapters.findIndex((c) => c.number === current);
  const next = allChapters[idx + delta];
  if (next) {
    chapterSelect.value = next.number;
    chapterNumInput.value = next.number;
  }
}

async function loadChapter(autoGenerate = false) {
  if (!currentStory) {
    showStatus("Chọn truyện trước nha", true);
    return;
  }
  const num = parseInt(chapterNumInput.value || chapterSelect.value, 10);
  if (!num) {
    showStatus("Chọn số chương nha", true);
    return;
  }

  hideStatus();
  setLoading(loadChapterBtn, true);
  showStatus(`Đang lấy chương ${num}...`);

  try {
    const res = await fetch(
      `/api/truyenhoan/chapter?slug=${encodeURIComponent(currentStory.slug)}&number=${num}`
    );
    const data = await res.json();
    if (!data.ok) throw new Error(data.error);

    const header = `${data.chapter.title}\n\n`;
    setStoryText(header + data.chapter.text);

    chapterSelect.value = num;
    showStatus(`Đã lấy chương ${num} (${data.chapter.char_count.toLocaleString("vi-VN")} ký tự)`);

    document.getElementById("panelManual")?.scrollIntoView({ behavior: "smooth", block: "start" });

    if (autoGenerate) {
      document.getElementById("generateBtn")?.click();
    }
  } catch (e) {
    showStatus(e.message || "Không lấy được chương", true);
  } finally {
    setLoading(loadChapterBtn, false);
  }
}

function initTabs() {
  document.querySelectorAll(".source-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".source-tab").forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      const mode = tab.dataset.tab;
      if (mode === "manual") {
        panelTruyenhoan.classList.add("hidden");
      } else {
        panelTruyenhoan.classList.remove("hidden");
      }
    });
  });
}

storySearchBtn?.addEventListener("click", searchStories);
storySearch?.addEventListener("keydown", (e) => {
  if (e.key === "Enter") searchStories();
});

chapterFilter?.addEventListener("input", () => {
  populateChapters(allChapters, chapterFilter.value);
});

chapterSelect?.addEventListener("change", () => {
  chapterNumInput.value = chapterSelect.value;
});

chapterNumInput?.addEventListener("change", () => {
  const num = parseInt(chapterNumInput.value, 10);
  const found = allChapters.find((c) => c.number === num);
  if (found) chapterSelect.value = num;
});

chapterPrevBtn?.addEventListener("click", () => goChapter(1));
chapterNextBtn?.addEventListener("click", () => goChapter(-1));
loadChapterBtn?.addEventListener("click", () => loadChapter(false));

initTabs();

const urlParams = new URLSearchParams(window.location.search);
const initStory = urlParams.get("story");
const initChapter = urlParams.get("chapter");
if (initStory) {
  selectStory(initStory).then(() => {
    if (initChapter) {
      chapterNumInput.value = initChapter;
      loadChapter(false);
    }
  });
}
