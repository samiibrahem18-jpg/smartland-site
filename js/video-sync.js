/* video-sync.js — نص مرافق متزامن مع الفيديو، مبني على ملف الترجمة (.vtt).
   كل [data-video-block] يحوي <video> فيه <track> و <ol data-transcript>.
   - يبني قائمة الجمل من cues الملف.
   - يميّز الجملة الحالية أثناء التشغيل.
   - الضغط على جملة ينقل الفيديو إلى لحظتها. */
(() => {
  "use strict";

  const fmt = (s) => {
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${m}:${String(sec).padStart(2, "0")}`;
  };

  function init(block) {
    const video = block.querySelector("video");
    const list = block.querySelector("[data-transcript]");
    const fallback = block.querySelector(".video-fallback");
    const trackEl = video && video.querySelector("track");
    if (!video || !list || !trackEl) return;

    const track = trackEl.track;
    let items = [];

    /* إظهار رسالة بديلة إن لم يوجد ملف الفيديو بعد */
    const sources = video.querySelectorAll("source");
    const lastSource = sources[sources.length - 1];
    if (lastSource && fallback) {
      lastSource.addEventListener("error", () => { fallback.hidden = false; });
      video.addEventListener("loadedmetadata", () => { fallback.hidden = true; });
    }

    function build() {
      const cues = track.cues ? Array.from(track.cues) : [];
      if (!cues.length) return false;
      list.replaceChildren();
      items = cues.map((cue) => {
        const li = document.createElement("li");
        const btn = document.createElement("button");
        btn.type = "button";
        const t = document.createElement("time");
        t.textContent = fmt(cue.startTime);
        btn.append(t, document.createTextNode(cue.text.replace(/<[^>]+>/g, "")));
        btn.addEventListener("click", () => {
          video.currentTime = cue.startTime + 0.01;
          video.play().catch(() => {});
        });
        li.append(btn);
        list.append(li);
        return { cue, li };
      });
      return true;
    }

    function highlight() {
      const now = video.currentTime;
      let active = null;
      for (const it of items) {
        const on = now >= it.cue.startTime && now < it.cue.endTime;
        it.li.classList.toggle("is-active", on);
        if (on) active = it.li;
      }
      if (active) {
        // تمرير داخل قائمة النص فقط، دون تحريك الصفحة كلها
        const top = active.offsetTop - list.clientHeight / 2 + active.clientHeight / 2;
        list.scrollTo({ top, behavior: "smooth" });
      }
    }

    // لازم أن لا تكون الحالة disabled كي تُحمَّل الـ cues؛ hidden تكفي لقراءتها
    // ونترك عرض الترجمة على الفيديو للمتصفح (default) إن كانت showing.
    if (track.mode === "disabled") track.mode = "hidden";

    if (!build()) {
      trackEl.addEventListener("load", build, { once: true });
      video.addEventListener("loadedmetadata", build, { once: true });
    }
    track.addEventListener("cuechange", highlight);
    video.addEventListener("timeupdate", highlight);
  }

  document.querySelectorAll("[data-video-block]").forEach(init);
})();
