// Mapa de solo lectura con un punto (detalle de un análisis)
document.addEventListener("DOMContentLoaded", () => {
  const c = document.getElementById("mapa");
  if (!c || !c.dataset.lat || typeof L === "undefined") return;
  const p = [parseFloat(c.dataset.lat), parseFloat(c.dataset.lng)];
  const m = L.map("mapa").setView(p, 15);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, attribution: "&copy; OpenStreetMap" }).addTo(m);
  L.marker(p).addTo(m);
});
