"use strict";

const sliderIds = ["ready-weight", "ready-success", "unready-success"];
function updateScenario() {
  const [weight, ready, unready] = sliderIds.map(id => Number(document.getElementById(id).value) / 100);
  sliderIds.forEach(id => { document.getElementById(`${id}-value`).textContent = `${document.getElementById(id).value}%`; });
  const total = weight * ready + (1 - weight) * unready;
  document.getElementById("scenario-total").textContent = `${Number((total * 100).toFixed(1))}%`;
  document.getElementById("scenario-formula").textContent = `${weight.toFixed(2)} × ${ready.toFixed(2)} + ${(1 - weight).toFixed(2)} × ${unready.toFixed(2)} = ${total.toFixed(4).replace(/0+$/, "").replace(/\.$/, "")}`;
  document.getElementById("ready-contribution").style.width = `${100 * weight * ready}%`;
  document.getElementById("unready-contribution").style.width = `${100 * (1 - weight) * unready}%`;
}
if (sliderIds.every(id => document.getElementById(id))) {
  sliderIds.forEach(id => document.getElementById(id).addEventListener("input", updateScenario));
  document.getElementById("reset-scenario").addEventListener("click", () => {
    sliderIds.forEach((id, index) => { document.getElementById(id).value = [60, 80, 10][index]; });
    updateScenario();
  });
  updateScenario();
}

document.querySelectorAll("details.command-output").forEach(details => {
  details.addEventListener("toggle", () => {
    details.querySelector("summary").textContent = details.open ? "Hide command output" : "Show command output";
  });
});

const outcome = document.getElementById("outcome");
if (outcome) {
  outcome.addEventListener("change", () => {
    const y = Number(outcome.value);
    document.getElementById("score-a").textContent = ((0.25 - y) ** 2).toFixed(4);
    document.getElementById("score-b").textContent = ((0.75 - y) ** 2).toFixed(4);
    document.getElementById("score-explanation").textContent = y ? "With YES, arm b is closer to the outcome." : "With hypothetical NO, arm a is closer to the outcome. The saved result is unchanged.";
  });
}

const traceSelect = document.getElementById("trace-event");
if (traceSelect) {
  const events = JSON.parse(document.getElementById("session-trace").textContent);
  const explain = {
    attempt_start: "The attempt is recorded before the external worker is invoked.",
    tool_request: "The model queues a research request for the tool worker.",
    evidence: "The captured packet joins the session’s available evidence.",
    research: "A successful tool receipt points to a specific captured record.",
    assessment: "The worker assesses a required research domain and cites its evidence.",
    observation: "A worker-reported observation is compared with the registered protocol requirement."
  };
  function updateTrace() {
    const event = events[Number(traceSelect.value)];
    const description = event.kind === "attempt_result"
      ? (event.payload.status === "waiting" ? "The tool is waiting. Its continuation will be polled under this same attempt ID; final usage is still unknown." : "The worker completed. Its usage and returned actions are preserved before the actions are applied.")
      : explain[event.kind];
    document.getElementById("trace-explanation").textContent = description;
    document.getElementById("trace-payload").textContent = JSON.stringify(event, null, 2);
  }
  traceSelect.addEventListener("change", updateTrace);
  updateTrace();
}

document.querySelectorAll("[data-copy]").forEach(button => {
  button.addEventListener("click", async () => {
    const text = document.getElementById(button.dataset.copy).textContent;
    try {
      await navigator.clipboard.writeText(text);
      button.textContent = "Copied";
      document.getElementById("copy-status").textContent = "Code copied to clipboard.";
      window.setTimeout(() => { button.textContent = "Copy"; }, 2000);
    } catch {
      document.getElementById("copy-status").textContent = "Copy unavailable. Select and copy the code manually.";
    }
  });
});

if ("IntersectionObserver" in window) {
  const observer = new IntersectionObserver(entries => {
    const visible = entries.filter(entry => entry.isIntersecting);
    if (!visible.length) return;
    const current = visible[0].target.id;
    document.querySelectorAll(".sidebar nav a").forEach(link => {
      const active = link.getAttribute("href") === `#${current}`;
      link.classList.toggle("active", active);
      if (active) link.setAttribute("aria-current", "location");
      else link.removeAttribute("aria-current");
    });
  }, { rootMargin: "-10% 0px -70% 0px" });
  document.querySelectorAll(".content > section").forEach(section => observer.observe(section));
}
