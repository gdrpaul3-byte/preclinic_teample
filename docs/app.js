(function () {
  "use strict";

  const DEPT_SHORT = { 바이오헬스케어: "바이오", 의생명과학: "의생명" };
  const UNDECIDED = "미정";
  const state = {
    groups: [],
    query: "",
    filters: new Set(),
  };

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) =>
    Array.from(root.querySelectorAll(sel));

  function formatMembers(members, leader) {
    return members.map((m) => ({
      ...m,
      isLeader: leader && m.name === leader,
      deptShort: DEPT_SHORT[m.department] || m.department,
      studentIdTail: m.studentId.slice(-4),
    }));
  }

  function buildCard(group, template) {
    const node = template.content.firstElementChild.cloneNode(true);
    const isConfirmed = group.topicConfirmed;
    if (isConfirmed) node.classList.add("is-confirmed");

    node.dataset.id = String(group.id);

    const gif = $(".card__gif", node);
    gif.src = group.gifPath;
    gif.alt = isConfirmed ? `${group.id}조 발표 주제 일러스트` : "";
    gif.onerror = () => {
      gif.src = "assets/gifs/placeholder.gif";
      gif.onerror = null;
    };

    $(".card__badge", node).textContent = `${group.id}조`;

    const topicEl = $(".card__topic", node);
    if (isConfirmed) {
      topicEl.textContent = group.topic;
    } else {
      topicEl.textContent = "발표 주제 미정";
      topicEl.classList.add("is-undecided");
    }
    const leaderName = $(".card__leader-name", node);
    if (group.leader) {
      leaderName.textContent = `${group.leader} (조장)`;
    } else {
      leaderName.textContent = "조장 미정";
      leaderName.classList.add("is-undecided");
    }

    const membersList = $(".card__members", node);
    formatMembers(group.members, group.leader).forEach((m) => {
      const li = document.createElement("li");
      if (m.isLeader) li.classList.add("is-leader");
      li.innerHTML = `<span>${m.name}</span><span class="dept">${m.deptShort} ${m.year}</span>`;
      membersList.appendChild(li);
    });

    node.addEventListener("click", () => openModal(group));
    node.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        openModal(group);
      }
    });
    return node;
  }

  function openModal(group) {
    const modal = $("#detail");
    const isConfirmed = group.topicConfirmed;
    modal.classList.toggle("is-confirmed", isConfirmed);

    $(".modal__group-num", modal).textContent = `${group.id}조`;
    $(".modal__badge", modal).textContent = isConfirmed
      ? "주제 확정"
      : "주제 미정";

    const topicEl = $(".modal__topic", modal);
    if (isConfirmed) {
      topicEl.textContent = group.topic;
      topicEl.classList.remove("is-undecided");
    } else {
      topicEl.textContent = "발표 주제 미정";
      topicEl.classList.add("is-undecided");
    }
    const gif = $(".modal__gif", modal);
    gif.src = group.gifPath;
    gif.alt = isConfirmed ? `${group.id}조 발표 주제 일러스트` : "";
    gif.onerror = () => {
      gif.src = "assets/gifs/placeholder.gif";
      gif.onerror = null;
    };

    const list = $(".modal__members", modal);
    list.innerHTML = "";
    formatMembers(group.members, group.leader).forEach((m) => {
      const li = document.createElement("li");
      if (m.isLeader) li.classList.add("is-leader");
      li.innerHTML = `
        <span class="name">${m.name}${m.isLeader ? " ★" : ""}</span>
        <span class="sub">${m.studentId} · ${m.deptShort} ${m.year}학년</span>
      `;
      list.appendChild(li);
    });

    if (typeof modal.showModal === "function") {
      modal.showModal();
    } else {
      modal.setAttribute("open", "");
    }
  }

  function closeModal() {
    const modal = $("#detail");
    if (typeof modal.close === "function") modal.close();
    else modal.removeAttribute("open");
  }

  function matchesGroup(group) {
    if (state.filters.has("topic") && !group.topicConfirmed) return false;
    if (state.filters.has("leader") && !group.leader) return false;
    const depts = new Set(group.members.map((m) => m.department));
    if (state.filters.has("bio") && !depts.has("바이오헬스케어")) return false;
    if (
      state.filters.has("ms-only") &&
      (depts.size !== 1 || !depts.has("의생명과학"))
    )
      return false;

    if (!state.query) return true;
    const q = state.query.toLowerCase();
    const haystack = [
      `${group.id}조`,
      group.leader || "",
      group.topic || "",
      ...group.members.flatMap((m) => [
        m.name,
        m.studentId,
        m.department,
        DEPT_SHORT[m.department] || "",
        `${m.year}학년`,
        `${m.year}`,
      ]),
    ]
      .join(" ")
      .toLowerCase();
    return haystack.includes(q);
  }

  function render() {
    const grid = $("#grid");
    const cards = $$(".card", grid);
    cards.forEach((card) => {
      const id = Number(card.dataset.id);
      const group = state.groups.find((g) => g.id === id);
      card.classList.toggle("is-hidden", !matchesGroup(group));
    });
  }

  function wireControls() {
    const input = $("#search");
    input.addEventListener("input", (e) => {
      state.query = e.target.value.trim();
      render();
    });

    $$(".chip").forEach((btn) => {
      btn.addEventListener("click", () => {
        const key = btn.dataset.filter;
        if (key === "reset") {
          state.query = "";
          state.filters.clear();
          input.value = "";
          $$(".chip").forEach((c) => c.classList.remove("is-active"));
          render();
          return;
        }
        if (state.filters.has(key)) {
          state.filters.delete(key);
          btn.classList.remove("is-active");
        } else {
          state.filters.add(key);
          btn.classList.add("is-active");
        }
        render();
      });
    });

    const modal = $("#detail");
    $(".modal__close", modal).addEventListener("click", closeModal);
    modal.addEventListener("click", (e) => {
      if (e.target === modal) closeModal();
    });
  }

  function updateStats() {
    const total = state.groups.reduce((n, g) => n + g.members.length, 0);
    const confirmed = state.groups.filter((g) => g.topicConfirmed).length;
    const leaders = state.groups.filter((g) => g.leader).length;
    $("#stat-members").textContent = String(total);
    $("#stat-confirmed").textContent = String(confirmed);
    $("#stat-leaders").textContent = String(leaders);
  }

  // Particles ------------------------------------------------------
  function startParticles() {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const canvas = $("#bg-particles");
    const ctx = canvas.getContext("2d");
    let w, h, particles;

    function resize() {
      w = canvas.width = window.innerWidth * devicePixelRatio;
      h = canvas.height = window.innerHeight * devicePixelRatio;
      canvas.style.width = window.innerWidth + "px";
      canvas.style.height = window.innerHeight + "px";
    }
    resize();
    window.addEventListener("resize", resize);

    const count = Math.min(
      80,
      Math.floor((window.innerWidth * window.innerHeight) / 22000)
    );
    particles = Array.from({ length: count }, () => ({
      x: Math.random() * w,
      y: Math.random() * h,
      r: (Math.random() * 1.6 + 0.4) * devicePixelRatio,
      vx: (Math.random() - 0.5) * 0.25,
      vy: (Math.random() - 0.5) * 0.25,
      a: Math.random() * 0.4 + 0.15,
    }));

    function tick() {
      ctx.clearRect(0, 0, w, h);
      particles.forEach((p) => {
        p.x += p.vx;
        p.y += p.vy;
        if (p.x < 0 || p.x > w) p.vx *= -1;
        if (p.y < 0 || p.y > h) p.vy *= -1;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(180, 200, 255, ${p.a})`;
        ctx.fill();
      });
      requestAnimationFrame(tick);
    }
    tick();
  }

  // Boot -----------------------------------------------------------
  async function init() {
    try {
      const res = await fetch("data.json", { cache: "no-cache" });
      if (!res.ok) throw new Error(`data.json HTTP ${res.status}`);
      const data = await res.json();
      state.groups = data.groups;

      $("#generated-at").textContent = data.generatedAt;
      updateStats();

      const template = $("#card-template");
      const grid = $("#grid");
      const fragment = document.createDocumentFragment();
      state.groups
        .slice()
        .sort((a, b) => a.id - b.id)
        .forEach((g) => fragment.appendChild(buildCard(g, template)));
      grid.appendChild(fragment);

      wireControls();
      startParticles();
    } catch (err) {
      console.error(err);
      $("#grid").innerHTML = `
        <p style="padding:24px;color:#f87171">
          data.json을 불러오지 못했습니다. <code>python scripts/build_data.py</code>를 실행했는지,
          이 페이지를 로컬 서버로 열었는지 확인하세요 (file:// 에서는 fetch가 차단될 수 있습니다).
        </p>`;
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
