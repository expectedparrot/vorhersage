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
sliderIds.forEach(id => document.getElementById(id).addEventListener("input", updateScenario));
document.getElementById("reset-scenario").addEventListener("click", () => {
  sliderIds.forEach((id, index) => { document.getElementById(id).value = [60, 80, 10][index]; });
  updateScenario();
});
updateScenario();

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
