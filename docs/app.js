const CACHE_KEY = "portfolj_sammanfattning_v1";

function formatKr(varde) {
  if (varde === null || varde === undefined) return "–";
  return Math.round(varde).toLocaleString("sv-SE") + " kr";
}

function formatPct(pct) {
  if (pct === null || pct === undefined) return "–";
  const tecken = pct > 0 ? "+" : "";
  return `${tecken}${pct.toFixed(2).replace(".", ",")} %`;
}

function formatUppdaterad(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  const nu = new Date();
  const sammaDag = d.toDateString() === nu.toDateString();
  const tid = d.toLocaleTimeString("sv-SE", { hour: "2-digit", minute: "2-digit" });
  return sammaDag ? `Uppdaterad ${tid}` : `Uppdaterad ${d.toLocaleDateString("sv-SE")} ${tid}`;
}

function render(data) {
  const app = document.getElementById("app");
  const pct = data.dagens_forandring_pct;
  const riktningClass = pct === null || pct === undefined ? "" : pct >= 0 ? "up" : "down";

  const innehavRader = (data.innehav || []).map(rad => {
    const radRiktning = rad.dagens_forandring_pct >= 0 ? "up" : "down";
    return `
      <div class="row">
        <span class="namn">${rad.bolag}</span>
        <span class="varde-cell">
          <span class="forandring ${radRiktning}" style="font-size:0.9rem">${formatPct(rad.dagens_forandring_pct)}</span>
          <span class="kr">${formatKr(rad.varde)}</span>
        </span>
      </div>`;
  }).join("");

  const nyhetsRader = (data.nyheter || []).map(n => `
    <div class="news-item">
      <a href="${n.lank}" target="_blank" rel="noopener">
        <span class="bolag-tag">${n.bolag}:</span> ${n.titel}
      </a>
      <div class="meta">${n.kalla || ""}${n.kalla && n.datum ? " · " : ""}${n.datum || ""}</div>
    </div>`).join("");

  app.innerHTML = `
    <header>
      <h1>Min portfölj</h1>
      <div class="varde">${formatKr(data.totalt_varde)}</div>
      <div class="forandring ${riktningClass}">
        ${formatPct(data.dagens_forandring_pct)}${data.dagens_forandring_kr != null ? ` (${data.dagens_forandring_kr >= 0 ? "+" : ""}${formatKr(data.dagens_forandring_kr)} idag)` : ""}
      </div>
      ${data.portfoljscore != null ? `<div class="score-badge">Portföljscore ${data.portfoljscore} / 100</div>` : ""}
      <div class="uppdaterad">${formatUppdaterad(data.uppdaterad)}</div>
    </header>

    <section>
      <h2>Innehav</h2>
      <div class="card">${innehavRader || '<div class="row"><span class="namn">Inga innehav ännu</span></div>'}</div>
    </section>

    <section>
      <h2>Senaste nyheterna</h2>
      <div class="card">${nyhetsRader || '<div class="news-item">Inga nyheter just nu</div>'}</div>
    </section>
  `;
}

function renderFel(meddelande) {
  document.getElementById("app").innerHTML = `<div class="fel">${meddelande}</div>`;
}

async function hamtaData() {
  const cachead = localStorage.getItem(CACHE_KEY);
  if (cachead) {
    try {
      render(JSON.parse(cachead));
    } catch (e) { /* ignorera trasig cache */ }
  }

  try {
    const svar = await fetch(GIST_RAW_URL, { cache: "no-store" });
    if (!svar.ok) throw new Error("Kunde inte hämta data");
    const data = await svar.json();
    localStorage.setItem(CACHE_KEY, JSON.stringify(data));
    render(data);
  } catch (e) {
    if (!cachead) {
      renderFel("Kunde inte hämta portföljdata. Kolla din internetanslutning.");
    }
  }
}

hamtaData();
