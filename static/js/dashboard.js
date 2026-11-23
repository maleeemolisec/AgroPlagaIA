// Panel: gráficos (Chart.js) y mapa de análisis (Leaflet + GeoJSON)
const esc = t => String(t).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
document.addEventListener("DOMContentLoaded", () => {
  const d = window.DATOS;
  if (typeof Chart !== "undefined") {
    new Chart(document.getElementById("graficoEstado"), {
      type: "doughnut",
      data: { labels: ["Sanos", "Con síntomas", "Dudosos"], datasets: [{ data: [d.sanos, d.enfermos, d.dudosos], backgroundColor: ["#2e7d32", "#c62828", "#f9a825"] }] },
      options: { plugins: { legend: { position: "bottom" } } }
    });
    const ge = document.getElementById("graficoEnf");
    if (ge) new Chart(ge, {
      type: "bar",
      data: { labels: Object.keys(d.enfermedades), datasets: [{ label: "Casos", data: Object.values(d.enfermedades), backgroundColor: "#66bb6a" }] },
      options: { indexAxis: "y", plugins: { legend: { display: false } }, scales: { x: { ticks: { precision: 0 } } } }
    });
  }
  if (typeof L === "undefined") return;
  const mapa = L.map("mapa").setView([-32.0, -63.5], 7);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, attribution: "&copy; OpenStreetMap" }).addTo(mapa);
  const color = { sano: "#2e7d32", enfermo: "#c62828", dudoso: "#f9a825", no_planta: "#607d8b" };
  fetch(window.URL_GEOJSON).then(r => r.json()).then(geo => {
    const capa = L.geoJSON(geo, {
      pointToLayer: (f, ll) => L.circleMarker(ll, { radius: 9, color: "#fff", weight: 2, fillColor: color[f.properties.estado] || "#607d8b", fillOpacity: .95 }),
      onEachFeature: (f, layer) => {
        const p = f.properties;
        layer.bindPopup(`<b>${esc(p.cultivo)}</b> · ${esc(p.campo)} / ${esc(p.lote)}<br>${esc(p.enfermedad)}<br><small>${esc(p.fecha)}</small><br><a href="${esc(p.url)}">Ver análisis</a>`);
      }
    }).addTo(mapa);
    if (geo.features.length) mapa.fitBounds(capa.getBounds().pad(0.3), { maxZoom: 14 });
  });
});
