document.addEventListener("DOMContentLoaded", () => {
  const cont = document.getElementById("mapaLote");
  const campoLat = parseFloat(cont.dataset.lat);
  const campoLng = parseFloat(cont.dataset.lng);
  const mapa = L.map(cont).setView([campoLat, campoLng], 14);
  L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", {
    maxZoom: 19, attribution: "Tiles &copy; Esri"
  }).addTo(mapa);

  const limites = new L.FeatureGroup().addTo(mapa);
  const opcionesLinea = { color: "#ff3b30", weight: 4, opacity: 0.95, fillColor: "#ff3b30", fillOpacity: 0.12 };
  const controlDibujo = new L.Control.Draw({
    draw: {
      polygon: { allowIntersection: false, showArea: true, shapeOptions: opcionesLinea },
      rectangle: { shapeOptions: opcionesLinea },
      polyline: false, circle: false, circlemarker: false, marker: false
    },
    edit: { featureGroup: limites, remove: true }
  });
  mapa.addControl(controlDibujo);

  const campoLimite = document.getElementById("limite_geojson");
  function sincronizar() {
    const poligono = limites.getLayers().find(capa => capa instanceof L.Polygon);
    campoLimite.value = poligono ? JSON.stringify(poligono.toGeoJSON().geometry) : "";
  }
  function cargarLimite() {
    if (!campoLimite.value) return;
    const geometria = JSON.parse(campoLimite.value);
    L.geoJSON(geometria, { style: opcionesLinea }).eachLayer(capa => limites.addLayer(capa));
    if (limites.getLayers().length) mapa.fitBounds(limites.getBounds(), { maxZoom: 16 });
  }
  try {
    cargarLimite();
  } catch (error) {
    campoLimite.value = "";
    console.error("No se pudo cargar el perímetro guardado.", error);
  }

  mapa.on(L.Draw.Event.CREATED, evento => {
    limites.clearLayers();
    limites.addLayer(evento.layer);
    sincronizar();
  });
  mapa.on(L.Draw.Event.EDITED, sincronizar);
  mapa.on(L.Draw.Event.DELETED, sincronizar);
});
