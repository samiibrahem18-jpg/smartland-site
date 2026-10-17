/* main.js — سلوك الواجهة العام. جافاسكربت عادية بلا مكتبات. */
(() => {
  "use strict";

  /* ---------- قائمة الموبايل ---------- */
  const toggle = document.querySelector(".nav-toggle");
  const nav = document.getElementById("site-nav");
  if (toggle && nav) {
    const setOpen = (open) => {
      nav.classList.toggle("is-open", open);
      toggle.setAttribute("aria-expanded", String(open));
    };
    toggle.addEventListener("click", () =>
      setOpen(!nav.classList.contains("is-open")),
    );
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") setOpen(false);
    });
    nav.addEventListener("click", (e) => {
      if (e.target.closest("a")) setOpen(false);
    });
  }

  /* ---------- ظهور تدريجي عند التمرير ---------- */
  const revealEls = document.querySelectorAll(".reveal");
  if ("IntersectionObserver" in window && revealEls.length) {
    const io = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            io.unobserve(entry.target);
          }
        }
      },
      { threshold: 0.12, rootMargin: "0px 0px -40px 0px" },
    );
    revealEls.forEach((el) => io.observe(el));
  } else {
    revealEls.forEach((el) => el.classList.add("is-visible"));
  }

  /* ---------- فلتر المشاريع ---------- */
  const filterBtns = document.querySelectorAll(".filter-btn");
  const projects = document.querySelectorAll(".project[data-sector]");
  if (filterBtns.length && projects.length) {
    filterBtns.forEach((btn) => {
      btn.addEventListener("click", () => {
        const f = btn.dataset.filter;
        filterBtns.forEach((b) =>
          b.setAttribute("aria-pressed", String(b === btn)),
        );
        projects.forEach((p) => {
          p.hidden = !(f === "all" || p.dataset.sector === f);
        });
      });
    });
  }

  /* ---------- Lightbox لتكبير الصور (عنصر dialog الأصلي) ---------- */
  const triggers = document.querySelectorAll("[data-lightbox]");
  if (triggers.length && typeof HTMLDialogElement !== "undefined") {
    const dlg = document.createElement("dialog");
    dlg.className = "lightbox";
    dlg.setAttribute("aria-label", "عرض الصورة");
    dlg.innerHTML =
      '<button class="lightbox__close" type="button" aria-label="إغلاق">&times;</button>' +
      '<img alt=""><p></p>';
    document.body.append(dlg);
    const img = dlg.querySelector("img");
    const caption = dlg.querySelector("p");

    triggers.forEach((t) => {
      t.addEventListener("click", () => {
        const src = t.querySelector("img");
        if (!src) return;
        img.src = src.currentSrc || src.src;
        img.alt = src.alt;
        caption.textContent = src.alt;
        dlg.showModal();
      });
    });
    dlg
      .querySelector(".lightbox__close")
      .addEventListener("click", () => dlg.close());
    // الإغلاق عند الضغط على الخلفية
    dlg.addEventListener("click", (e) => {
      if (e.target === dlg) dlg.close();
    });
  }

  /* ---------- نموذج التواصل (mailto لأن الموقع ثابت) ---------- */
  const form = document.querySelector("form[data-mailto]");
  if (form) {
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const d = new FormData(form);
      const subject = encodeURIComponent("رسالة من موقع Smart Land");
      const body = encodeURIComponent(
        `الاسم: ${d.get("name")}\nالبريد: ${d.get("email")}\n\n${d.get("message")}`,
      );
      window.location.href = `mailto:${form.dataset.mailto}?subject=${subject}&body=${body}`;
      const status = form.querySelector("[data-form-status]");
      if (status) status.textContent = "تم فتح برنامج البريد لإرسال الرسالة.";
    });
  }

  /* ---------- مربعات الإحصاءات: قلب بالضغط (انيمشن flip-diagonal-2-tl) ---------- */
  document.querySelectorAll(".stat").forEach((card) => {
    const inner = card.querySelector(".stat__inner");
    const front = card.querySelector(".stat__face--front");
    const back = card.querySelector(".stat__face--back");
    if (!inner || !front || !back) return;

    let flipped = false; // هل المربع الآن على وجهه الخلفي (النتيجة)؟
    let busy = false; // يمنع الضغط المتكرر أثناء دوران المربع

    // قارئ الشاشة يقرأ الوجه الظاهر فقط
    front.setAttribute("aria-hidden", "false");
    back.setAttribute("aria-hidden", "true");

    card.addEventListener("click", () => {
      if (busy) return;
      busy = true;
      flipped = !flipped;

      inner.classList.remove("flip-diagonal-2-tl", "flip-diagonal-2-tl-back");
      inner.classList.add(
        flipped ? "flip-diagonal-2-tl" : "flip-diagonal-2-tl-back",
      );

      card.setAttribute("aria-pressed", String(flipped));
      front.setAttribute("aria-hidden", String(flipped));
      back.setAttribute("aria-hidden", String(!flipped));

      setTimeout(() => {
        busy = false;
      }, 420); // مدة الانيمشن 0.4 ثانية
    });
  });

  /* ---------- سنة التذييل ---------- */
  document.querySelectorAll("[data-year]").forEach((el) => {
    el.textContent = String(new Date().getFullYear());
  });
})();
