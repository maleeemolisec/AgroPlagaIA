// Mapa Leaflet para elegir una ubicación (campo o toma de foto)
document.addEventListener("DOMContentLoaded", () => {
  const cont = document.getElementById("mapa");
  if (!cont || typeof L === "undefined") return;
  const lat = document.getElementById("latitud"), lng = document.getElementById("longitud");
  const inicio = [parseFloat(lat.value) || -32.0, parseFloat(lng.value) || -63.5];   // centro de Córdoba
  const mapa = L.map("mapa").setView(inicio, lat.value ? 14 : 7);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    { maxZoom: 19, attribution: "&copy; OpenStreetMap" }).addTo(mapa);
  let marcador = lat.value ? L.marker(inicio).addTo(mapa) : null;

  function poner(la, lo, centrar) {
    lat.value = la.toFixed(6); lng.value = lo.toFixed(6);
    if (marcador) marcador.setLatLng([la, lo]); else marcador = L.marker([la, lo]).addTo(mapa);
    if (centrar) mapa.setView([la, lo], 15);
  }
  mapa.on("click", e => poner(e.latlng.lat, e.latlng.lng, false));
  [lat, lng].forEach(i => i.addEventListener("change", () => {
    const a = parseFloat(lat.value.replace(",", ".")), o = parseFloat(lng.value.replace(",", "."));
    if (!isNaN(a) && !isNaN(o)) poner(a, o, true);
  }));

  const b = document.getElementById("btnUbicacion");
  if (b) b.addEventListener("click", () => {
    if (!navigator.geolocation) return alert("Tu navegador no permite geolocalización.");
    b.textContent = "Buscando…";
    navigator.geolocation.getCurrentPosition(
      p => { poner(p.coords.latitude, p.coords.longitude, true); b.textContent = "📍 Usar mi ubicación"; },
      () => { alert("No se pudo obtener la ubicación. Verificá los permisos."); b.textContent = "📍 Usar mi ubicación"; },
      { enableHighAccuracy: true, timeout: 10000 });
  });
  window._mapaSelector = { mapa, poner };
});
