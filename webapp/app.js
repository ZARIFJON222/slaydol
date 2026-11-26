const tg = window.Telegram?.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
}

function haptic(style = "light") {
  try {
    tg?.HapticFeedback?.impactOccurred(style);
  } catch {}
}

const I18N = {
  uz: {
    tabSlide: "📊 Slayd",
    tabReferat: "📄 Referat",
    tabHistory: "📚 Ishlarim",
    topicLabel: "Taqdimot mavzusi",
    refTopicLabel: "Ish mavzusi",
    authorLabel: "Muallif va guruh (ixtiyoriy)",
    countLabel: "Slaydlar soni",
    themeLabel: "Dizayn uslubi",
    docTypeLabel: "Hujjat turi",
    typeReferat: "Referat",
    typeMustaqil: "Mustaqil ish",
    sizeLabel: "Sahifa hajmi",
    sizeShort: "5–7 bet",
    sizeMedium: "10–12 bet",
    sizeLong: "15+ bet",
    generateSlide: "Taqdimotni yaratish",
    generateReferat: "GOST hujjatni yaratish",
    historyTitle: "So'nggi yaratilgan ishlar",
    refreshBtn: "Yangilash",
    gostMinistry: "O'ZBEKISTON RESPUBLIKASI OLIY TA'LIM VAZIRLIGI",
    step1: "1/3 · Mavzu tahlil qilinmoqda va tuzilma yaratilmoqda...",
    step2: "2/3 · Dizayn va slaydlar chizilmoqda...",
    step3: "3/3 · Tayyor fayl yuklanmoqda...",
    sentChat: "Telegram chatga ham yuborildi ✓",
    downloadBtn: "Faylni yuklab olish",
    emptyHistory: "Hozircha yaratilgan ishlar yo'q.",
    errPrefix: "Xatolik: ",
    slideUnit: "slayd",
    defaultSlideTitle: "Sun'iy intellektning tibbiyotdagi o'rni",
    defaultRefTitle: "O'zbekistonda raqamli iqtisodiyot rivoji",
    defaultAuthor: "SlaydYasa Studio",
    byPrefix: "Bajardi: ",
    placeholderSlide: "Masalan: Sun'iy intellektning tibbiyotdagi o'rni",
    placeholderRef: "Masalan: O'zbekistonda raqamli iqtisodiyot rivoji",
  },
  ru: {
    tabSlide: "📊 Слайд",
    tabReferat: "📄 Реферат",
    tabHistory: "📚 Мои работы",
    topicLabel: "Тема презентации",
    refTopicLabel: "Тема работы",
    authorLabel: "Автор и группа (необязательно)",
    countLabel: "Количество слайдов",
    themeLabel: "Стиль оформления",
    docTypeLabel: "Тип документа",
    typeReferat: "Реферат",
    typeMustaqil: "Самостоятельная",
    sizeLabel: "Объём работы",
    sizeShort: "5–7 стр.",
    sizeMedium: "10–12 стр.",
    sizeLong: "15+ стр.",
    generateSlide: "Создать презентацию",
    generateReferat: "Создать документ ГОСТ",
    historyTitle: "Недавние работы",
    refreshBtn: "Обновить",
    gostMinistry: "МИНИСТЕРСТВО ВЫСШЕГО ОБРАЗОВАНИЯ И НАУКИ",
    step1: "1/3 · Анализируем тему и формируем структуру...",
    step2: "2/3 · Оформляем дизайн и страницы...",
    step3: "3/3 · Подготавливаем файл...",
    sentChat: "Также отправлено в чат Telegram ✓",
    downloadBtn: "Скачать файл",
    emptyHistory: "Пока нет готовых работ.",
    errPrefix: "Ошибка: ",
    slideUnit: "слайдов",
    defaultSlideTitle: "Роль искусственного интеллекта в медицине",
    defaultRefTitle: "Развитие цифровой экономики",
    defaultAuthor: "SlaydYasa Studio",
    byPrefix: "Выполнил(а): ",
    placeholderSlide: "Например: Роль искусственного интеллекта в медицине",
    placeholderRef: "Например: Развитие цифровой экономики",
  },
};

const state = {
  lang: tg?.initDataUnsafe?.user?.language_code?.startsWith("ru") ? "ru" : "uz",
  slideCount: 10,
  slideTheme: "obsidian_gold",
  refType: "Referat",
  refSize: "medium",
};

function apiHeaders() {
  const headers = { "Content-Type": "application/json" };
  if (tg?.initData) {
    headers["X-Telegram-Init-Data"] = tg.initData;
  }
  return headers;
}

function applyLang() {
  const dict = I18N[state.lang];
  document.documentElement.lang = state.lang;
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const key = el.dataset.i18n;
    if (dict[key]) el.textContent = dict[key];
  });
  document.getElementById("slide-topic").placeholder = dict.placeholderSlide;
  document.getElementById("ref-topic").placeholder = dict.placeholderRef;
  document.querySelectorAll(".lang-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.lang === state.lang);
  });
  updatePreviews();
}

function updatePreviews() {
  const dict = I18N[state.lang];
  const sTopic = document.getElementById("slide-topic").value.trim();
  const sAuthor = document.getElementById("slide-author").value.trim();
  document.getElementById("preview-slide-title").textContent = sTopic || dict.defaultSlideTitle;
  document.getElementById("preview-slide-author").textContent = sAuthor || dict.defaultAuthor;
  document.getElementById("preview-slide-badge").textContent = `${state.slideCount} ${dict.slideUnit}`;
  document.getElementById("slide-preview").dataset.themePreview = state.slideTheme;

  const rTopic = document.getElementById("ref-topic").value.trim();
  const rAuthor = document.getElementById("ref-author").value.trim();
  const rTypeLabel =
    state.refType === "Referat" ? dict.typeReferat.toUpperCase() : dict.typeMustaqil.toUpperCase();
  document.getElementById("preview-ref-type").textContent = rTypeLabel;
  document.getElementById("preview-ref-topic").textContent = rTopic || dict.defaultRefTitle;
  document.getElementById("preview-ref-author").textContent = dict.byPrefix + (rAuthor || "Talaba");
}

// Language buttons
document.querySelectorAll(".lang-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    haptic();
    state.lang = btn.dataset.lang;
    applyLang();
  });
});

// Tabs
document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    haptic();
    const target = btn.dataset.tab;
    document.querySelectorAll(".tab-btn").forEach((b) => {
      const active = b.dataset.tab === target;
      b.classList.toggle("active", active);
      b.setAttribute("aria-selected", active ? "true" : "false");
    });
    document.querySelectorAll(".tab-panel").forEach((p) => {
      p.classList.toggle("active", p.id === `panel-${target}`);
    });
    if (target === "history") loadHistory();
  });
});

// Live preview bindings
["slide-topic", "slide-author", "ref-topic", "ref-author"].forEach((id) => {
  document.getElementById(id).addEventListener("input", updatePreviews);
});

document.querySelectorAll("#slide-count-group .pill-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    haptic();
    state.slideCount = Number(btn.dataset.count);
    document.querySelectorAll("#slide-count-group .pill-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    updatePreviews();
  });
});

document.querySelectorAll("#slide-theme-group .theme-card").forEach((btn) => {
  btn.addEventListener("click", () => {
    haptic();
    state.slideTheme = btn.dataset.theme;
    document.querySelectorAll("#slide-theme-group .theme-card").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    updatePreviews();
  });
});

document.querySelectorAll("#ref-type-group .pill-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    haptic();
    state.refType = btn.dataset.rtype;
    document.querySelectorAll("#ref-type-group .pill-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    updatePreviews();
  });
});

document.querySelectorAll("#ref-size-group .pill-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    haptic();
    state.refSize = btn.dataset.size;
    document.querySelectorAll("#ref-size-group .pill-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
  });
});

function runProgressSimulation(fillEl, textEl) {
  const dict = I18N[state.lang];
  fillEl.style.width = "30%";
  textEl.textContent = dict.step1;
  const t1 = setTimeout(() => {
    fillEl.style.width = "68%";
    textEl.textContent = dict.step2;
  }, 2400);
  const t2 = setTimeout(() => {
    fillEl.style.width = "90%";
    textEl.textContent = dict.step3;
  }, 5500);
  return () => {
    clearTimeout(t1);
    clearTimeout(t2);
  };
}

function renderResult(container, ok, payload) {
  const dict = I18N[state.lang];
  container.classList.remove("hidden", "success", "error");
  if (!ok) {
    container.classList.add("error");
    container.textContent = "";
    const p = document.createElement("p");
    p.textContent = dict.errPrefix + (payload.error || "Unknown error");
    container.appendChild(p);
    return;
  }
  container.classList.add("success");
  container.textContent = "";

  const h = document.createElement("div");
  h.className = "result-title";
  h.textContent = payload.title || payload.filename;

  const m = document.createElement("div");
  m.className = "result-meta";
  m.textContent = payload.sent_to_chat ? dict.sentChat : payload.filename;

  const a = document.createElement("a");
  a.className = "download-btn";
  a.href = payload.download_url;
  a.download = payload.filename;
  a.textContent = dict.downloadBtn;

  container.append(h, m, a);
}

// Submit Slide
document.getElementById("slide-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  haptic("medium");
  const btn = document.getElementById("slide-submit-btn");
  const progBox = document.getElementById("slide-progress");
  const progFill = document.getElementById("slide-progress-fill");
  const progText = document.getElementById("slide-progress-text");
  const resBox = document.getElementById("slide-result");

  btn.disabled = true;
  resBox.classList.add("hidden");
  progBox.classList.remove("hidden");
  const stopSim = runProgressSimulation(progFill, progText);

  try {
    const resp = await fetch("/api/generate/slide", {
      method: "POST",
      headers: apiHeaders(),
      body: JSON.stringify({
        topic: document.getElementById("slide-topic").value.trim(),
        author: document.getElementById("slide-author").value.trim(),
        count: state.slideCount,
        theme: state.slideTheme,
        lang: state.lang,
      }),
    });
    const data = await resp.json();
    stopSim();
    progBox.classList.add("hidden");
    renderResult(resBox, resp.ok && data.ok, data);
  } catch (err) {
    stopSim();
    progBox.classList.add("hidden");
    renderResult(resBox, false, { error: err.message });
  } finally {
    btn.disabled = false;
  }
});

// Submit Referat
document.getElementById("referat-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  haptic("medium");
  const btn = document.getElementById("ref-submit-btn");
  const progBox = document.getElementById("ref-progress");
  const progFill = document.getElementById("ref-progress-fill");
  const progText = document.getElementById("ref-progress-text");
  const resBox = document.getElementById("ref-result");

  btn.disabled = true;
  resBox.classList.add("hidden");
  progBox.classList.remove("hidden");
  const stopSim = runProgressSimulation(progFill, progText);

  try {
    const resp = await fetch("/api/generate/referat", {
      method: "POST",
      headers: apiHeaders(),
      body: JSON.stringify({
        topic: document.getElementById("ref-topic").value.trim(),
        author: document.getElementById("ref-author").value.trim(),
        doc_type: state.refType,
        size_tier: state.refSize,
        lang: state.lang,
      }),
    });
    const data = await resp.json();
    stopSim();
    progBox.classList.add("hidden");
    renderResult(resBox, resp.ok && data.ok, data);
  } catch (err) {
    stopSim();
    progBox.classList.add("hidden");
    renderResult(resBox, false, { error: err.message });
  } finally {
    btn.disabled = false;
  }
});

// Load History
async function loadHistory() {
  const list = document.getElementById("history-list");
  const dict = I18N[state.lang];
  list.textContent = "...";
  try {
    const resp = await fetch("/api/history", { headers: apiHeaders() });
    const data = await resp.json();
    list.textContent = "";
    const items = data.items || [];
    if (!items.length) {
      const empty = document.createElement("p");
      empty.className = "progress-text";
      empty.textContent = dict.emptyHistory;
      list.appendChild(empty);
      return;
    }
    items.forEach((it) => {
      const row = document.createElement("div");
      row.className = "history-item";

      const left = document.createElement("div");
      const t = document.createElement("div");
      t.className = "history-item-title";
      t.textContent = it.topic;
      const meta = document.createElement("div");
      meta.className = "history-item-meta";
      meta.textContent = (it.created_at || "").slice(0, 16).replace("T", " ");
      left.append(t, meta);

      const badge = document.createElement("span");
      badge.className = "history-badge";
      badge.textContent = it.type === "slide" ? "PPTX" : "DOCX";

      row.append(left, badge);
      list.appendChild(row);
    });
  } catch (err) {
    list.textContent = dict.errPrefix + err.message;
  }
}

document.getElementById("refresh-history-btn").addEventListener("click", () => {
  haptic();
  loadHistory();
});

applyLang();
