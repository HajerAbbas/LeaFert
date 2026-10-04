/* Maize nitrogen check - client side
 * 1. Language switch (both languages are in the page; CSS shows one)
 * 2. Scroll-driven motion: parallax hero, leaf that yellows with scroll,
 *    one reveal of the evidence chart. All of it is off with reduced motion.
 * 3. Camera with a live plant check (same colour rules as leaf_core.py)
 * 4. Live "what the app is doing" timeline fed by the server
 */
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const root = document.documentElement;
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)");

  // ------------------------------------------------------------------ language
  const STATUS = {
    en: { none: "Point the camera at one maize plant", dark: "Too dark: move to daylight",
          small: "Move closer: the plant should fill the frame", steady: "Plant in view: hold still",
          ready: "Ready: take the photo", auto: "Hold still…", still_ok: "Plant found in this photo",
          still_no: "No plant found in this photo", denied: "Camera blocked. Use Upload instead.",
          measure: "LeaFert model", agent: "AI assistant", note: "Optional note, e.g. growth stage or last fertilizer date",
          chat: "Ask about this plant, fertilizer or weather…" },
    ar: { none: "وجّه الكاميرا نحو نبات ذرة واحد", dark: "الإضاءة ضعيفة: انتقل إلى ضوء النهار",
          small: "اقترب: يجب أن يملأ النبات الإطار", steady: "النبات ظاهر: ثبّت الهاتف",
          ready: "جاهز: التقط الصورة", auto: "اثبت…", still_ok: "تم العثور على نبات في الصورة",
          still_no: "لا يوجد نبات في هذه الصورة", denied: "الكاميرا محجوبة. استخدم الرفع.",
          measure: "نموذج LeaFert", agent: "المساعد الذكي", note: "ملاحظة اختيارية، مثل مرحلة النمو أو تاريخ آخر تسميد",
          chat: "اسأل عن هذا النبات أو السماد أو الطقس…" },
  };
  let LANG = "en";
  const tr = (k) => STATUS[LANG][k] || STATUS.en[k] || k;

  function setLang(l) {
    LANG = l;
    root.dataset.lang = l;
    root.lang = l;
    root.dir = l === "ar" ? "rtl" : "ltr";
    document.querySelectorAll(".lang-btn").forEach((b) => b.classList.toggle("is-on", b.dataset.lang === l));
    const note = $("note"); if (note) note.placeholder = tr("note");
    const ci = document.querySelector("shiny-chat-input"); if (ci) ci.setAttribute("placeholder", tr("chat"));
    document.querySelectorAll(".step-group").forEach((g) => { g.textContent = tr(g.dataset.key); });
    if (lastStatus) renderStatus(lastStatus);
    if (window.Shiny && Shiny.setInputValue) Shiny.setInputValue("lang", l);
  }

  // ------------------------------------------------------------------ scroll-driven motion
  const layers = Array.from(document.querySelectorAll(".hero .layer"));
  const heroCopy = document.querySelector(".hero-copy");
  const heroSvg = document.querySelector(".hero-art");
  const story = $("story");
  const vgroup = $("vgroup");
  const steps = Array.from(document.querySelectorAll(".story-step"));
  const nav = $("nav");
  let ticking = false;

  function frame() {
    ticking = false;
    const y = window.scrollY, vh = window.innerHeight;
    nav.classList.toggle("is-solid", y > vh * 0.6);

    // parallax hero (only while visible)
    if (!reduce.matches && y < vh * 1.3 && heroSvg) {
      const k = 900 / Math.max(1, heroSvg.getBoundingClientRect().height);   // px -> SVG units
      const scale = window.innerWidth < 700 ? 0.6 : 1;
      layers.forEach((l) => l.setAttribute("transform", `translate(0 ${(y * l.dataset.depth * k * scale).toFixed(1)})`));
      if (heroCopy) {
        heroCopy.style.transform = `translate3d(0, ${(y * 0.3 * scale).toFixed(1)}px, 0)`;
        heroCopy.style.opacity = String(Math.max(0, 1 - y / (vh * 0.7)));
      }
    }

    // story: leaf yellows from the tip as the chapter scrolls by (colour, not movement)
    if (story) {
      const r = story.getBoundingClientRect();
      const p = Math.min(1, Math.max(0, -r.top / Math.max(1, r.height - vh)));
      const v = Math.min(1, Math.max(0, (p - 0.18) / 0.62));          // yellowing between 18% and 80%
      vgroup.setAttribute("transform", `translate(985 162) scale(${Math.max(0.001, v).toFixed(3)} 1) translate(-985 -162)`);
      const n0 = parseFloat(story.dataset.n0), nf = parseFloat(story.dataset.nf);
      const share = nf + (n0 - nf) * v;
      $("yshare-num").textContent = Math.round(share * 100) + "%";
      $("yshare-bar").style.width = (v * 100).toFixed(1) + "%";
      const idx = Math.min(steps.length - 1, Math.floor(p * steps.length * 0.999));
      steps.forEach((s, i) => s.classList.toggle("is-on", i === idx));
    }
  }
  function onScroll() { if (!ticking) { ticking = true; requestAnimationFrame(frame); } }

  // evidence: the dots fill in once, when the chart comes into view
  function watchEvidence() {
    const chart = document.querySelector(".ev-chart");
    if (!chart) return;
    if (reduce.matches || !("IntersectionObserver" in window)) { chart.classList.add("is-in"); return; }
    const io = new IntersectionObserver((es) => {
      es.forEach((e) => { if (e.isIntersecting) { chart.classList.add("is-in"); io.disconnect(); } });
    }, { threshold: 0.35 });
    io.observe(chart);
  }

  // ------------------------------------------------------------------ camera
  let stream = null, facing = "environment", loopTimer = null, prevGray = null, readySince = 0;
  let lastStatus = null, busy = false, stillData = null;
  const sample = document.createElement("canvas"); sample.width = 160; sample.height = 120;
  const sctx = sample.getContext("2d", { willReadFrequently: true });
  const setState = (s) => { $("cam").dataset.state = s; };

  // same rules as leaf_core.detect_leaf: excess green + green hue gate
  function measurePixels(img) {
    const d = img.data, n = d.length / 4; let plant = 0, vSum = 0; const gray = new Float32Array(n);
    for (let i = 0, p = 0; i < d.length; i += 4, p++) {
      const r = d[i] / 255, g = d[i + 1] / 255, b = d[i + 2] / 255;
      const mx = Math.max(r, g, b), mn = Math.min(r, g, b), dl = mx - mn;
      vSum += mx; gray[p] = 0.299 * r + 0.587 * g + 0.114 * b;
      const exg = (2 * g - r - b) / (r + g + b + 1e-6);
      if (exg <= 0.05 || mx < 0.118 || dl / (mx || 1) < 0.157) continue;
      let h = mx === r ? 60 * (((g - b) / dl) % 6) : mx === g ? 60 * ((b - r) / dl + 2) : 60 * ((r - g) / dl + 4);
      if (h < 0) h += 360;
      if (h >= 34 && h <= 170) plant++;
    }
    let motion = 0;
    if (prevGray && prevGray.length === n) { for (let p = 0; p < n; p++) motion += Math.abs(gray[p] - prevGray[p]); motion /= n; }
    prevGray = gray;
    return { frac: plant / n, bright: vSum / n, motion };
  }
  function judge(m, live) {
    if (m.bright < 0.15) return { key: "dark", kind: "warn" };
    if (m.frac < 0.12) return { key: live ? "none" : "still_no", kind: "bad" };
    if (m.frac < 0.2) return { key: "small", kind: "warn" };
    if (!live) return { key: "still_ok", kind: "ok" };
    if (m.motion > 0.035) return { key: "steady", kind: "warn" };
    return { key: "ready", kind: "ok" };
  }
  function renderStatus(s) {
    lastStatus = s;
    const el = $("cam-status"); if (!el) return;
    el.textContent = tr(s.key); el.dataset.kind = s.kind;
    if (s.frac !== undefined) {
      const f = $("cam-meter-fill");
      f.style.width = Math.min(100, (s.frac / 0.5) * 100).toFixed(0) + "%"; f.dataset.kind = s.kind;
    }
  }
  function loop() {
    const v = $("cam-video");
    if (!stream || v.readyState < 2 || $("cam").dataset.state !== "live") return;
    sctx.drawImage(v, 0, 0, 160, 120);
    const m = measurePixels(sctx.getImageData(0, 0, 160, 120));
    const s = Object.assign(judge(m, true), { frac: m.frac });
    $("cam-capture").classList.toggle("is-ready", s.key === "ready");
    renderStatus(s);
  }
  async function startCamera() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) { $("cam-unsupported").hidden = false; return; }
    stopCamera();
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: facing }, width: { ideal: 1920 }, height: { ideal: 1440 } }, audio: false });
    } catch (e) {
      $("cam-still").hidden = true; setState("off"); $("cam-unsupported").hidden = false; renderStatus({ key: "denied", kind: "bad" });
      return;
    }
    const v = $("cam-video"); v.srcObject = stream; await v.play().catch(() => {});
    $("cam-capture").disabled = false; setState("live"); prevGray = null;
    loopTimer = setInterval(loop, 250);
  }
  function stopCamera() {
    if (loopTimer) clearInterval(loopTimer); loopTimer = null;
    if (stream) stream.getTracks().forEach((t) => t.stop());
    const v = $("cam-video"); if (v) v.srcObject = null; stream = null;
  }
  function showStill(dataUrl) {
    stillData = dataUrl;
    const img = $("cam-still");
    img.onload = () => {
      sctx.drawImage(img, 0, 0, 160, 120); prevGray = null;
      const m = measurePixels(sctx.getImageData(0, 0, 160, 120));
      renderStatus(Object.assign(judge(m, false), { frac: m.frac }));
    };
    img.src = dataUrl; img.hidden = false; setState("still");
  }
  function toJpeg(src, w, h) {
    const s = Math.min(1, 1600 / Math.max(w, h)), c = document.createElement("canvas");
    c.width = Math.round(w * s); c.height = Math.round(h * s);
    c.getContext("2d").drawImage(src, 0, 0, c.width, c.height);
    return c.toDataURL("image/jpeg", 0.92);
  }
  function capture() {
    const v = $("cam-video"); if (!stream || !v.videoWidth) return;
    const data = toJpeg(v, v.videoWidth, v.videoHeight);
    stopCamera(); showStill(data);
  }
  function fromFile(file) {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const img = new Image();
      img.onload = () => { stopCamera(); showStill(toJpeg(img, img.width, img.height)); };
      img.onerror = () => { stopCamera(); stillData = reader.result; $("cam-still").hidden = true; setState("still");
                            renderStatus({ key: "still_ok", kind: "ok" }); };   // e.g. HEIC: the server decodes it
      img.src = reader.result;
    };
    reader.readAsDataURL(file);
  }
  function analyze() {
    if (!stillData || busy) return;
    busy = true; $("cam-busy").hidden = false; $("cam-analyze").disabled = true;
    Shiny.setInputValue("photo_submit", { data: stillData, ts: Date.now() }, { priority: "event" });
    if (window.matchMedia("(max-width: 900px)").matches) {
      setTimeout(() => document.querySelector(".tool-right").scrollIntoView({ behavior: reduce.matches ? "auto" : "smooth" }), 150);
    }
  }

  // ------------------------------------------------------------------ steps timeline
  const ICON = { running: "", done: "✓", warn: "!", error: "✕", skip: "–" };
  function upsertStep(ev) {
    const ol = $("steps");
    let li = ol.querySelector(`li[data-id="${CSS.escape(ev.id)}"]`);
    if (!li) {
      li = document.createElement("li"); li.dataset.id = ev.id; li.dataset.t0 = performance.now();
      li.innerHTML = '<span class="st-icon"></span><div class="st-body"><div class="st-top"><span class="st-label"></span>' +
        '<span class="step-group"></span><span class="st-ms"></span></div><div class="st-detail"></div></div>';
      ol.appendChild(li);
    }
    if (ev.label) li.querySelector(".st-label").textContent = ev.label;
    if (ev.group) { const g = li.querySelector(".step-group"); g.dataset.key = ev.group; g.textContent = tr(ev.group); li.dataset.group = ev.group; }
    if (ev.status) {
      li.dataset.status = ev.status; li.querySelector(".st-icon").textContent = ICON[ev.status] || "";
      if (ev.status !== "running") {
        const ms = ev.ms || Math.round(performance.now() - Number(li.dataset.t0));
        li.querySelector(".st-ms").textContent = ms < 5 ? "" : ms >= 1000 ? (ms / 1000).toFixed(1) + " s" : ms + " ms";
      }
    }
    if (ev.detail !== undefined) li.querySelector(".st-detail").textContent = ev.detail;
  }

  // ------------------------------------------------------------------ wiring
  function wire() {
    document.querySelectorAll(".lang-btn").forEach((b) => b.addEventListener("click", () => setLang(b.dataset.lang)));
    $("cam-start").addEventListener("click", startCamera);
    $("cam-capture").addEventListener("click", capture);
    $("cam-switch").addEventListener("click", () => { facing = facing === "environment" ? "user" : "environment"; startCamera(); });
    ["cam-file", "cam-file2"].forEach((id) => $(id).addEventListener("change", (e) => { fromFile(e.target.files[0]); e.target.value = ""; }));
    $("cam-retake").addEventListener("click", () => { $("cam-still").hidden = true; stillData = null; startCamera(); });
    $("cam-analyze").addEventListener("click", analyze);
    document.addEventListener("click", (e) => {
      const img = e.target.closest(".shot-toggle"); if (!img) return;
      img.src = img.src === img.dataset.a ? img.dataset.b : img.dataset.a;
    });
    document.addEventListener("keydown", (e) => {
      if ((e.key === "Enter" || e.key === " ") && e.target.classList && e.target.classList.contains("shot-toggle")) { e.preventDefault(); e.target.click(); }
    });
    document.addEventListener("visibilitychange", () => { if (document.hidden) stopCamera(); });
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    reduce.addEventListener && reduce.addEventListener("change", () => { layers.forEach((l) => l.removeAttribute("transform")); onScroll(); });
    watchEvidence();
    frame();
    root.dataset.lang = LANG;
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", wire); else wire();

  // Shiny: send inputs only after the session is initialised
  window.jQuery(document).on("shiny:sessioninitialized", () => setLang(LANG));
  if (window.Shiny) {
    Shiny.addCustomMessageHandler("steps_reset", (msg) => { $("steps").innerHTML = ""; $("steps-title").textContent = msg.title || ""; });
    Shiny.addCustomMessageHandler("step", upsertStep);
    Shiny.addCustomMessageHandler("analysis_done", (_msg) => { busy = false; $("cam-busy").hidden = true; $("cam-analyze").disabled = false; });
  }
})();
