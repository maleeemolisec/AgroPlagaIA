document.addEventListener("DOMContentLoaded", () => {
  const mapa = L.map("mapaProductivo", { minZoom: 3 }).setView([-38.4, -63.6], 4);
  const estado = document.getElementById("estadoMapa");
  const clima = document.getElementById("climaPunto");
  const actualizacion = document.getElementById("actualizacionClima");
  const filtro = document.getElementById("filtroCultivo");
  const limitesArgentina = L.latLngBounds([[-55.2, -73.6], [-21.7, -53.6]]);
  let ultimaUbicacion = null;
  let gruposCampos = [];
  let marcadorSeleccionado = null;
  let temporizadorClima = null;

  const cartografia = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19, attribution: "&copy; OpenStreetMap contributors"
  });
  const satelite = L.tileLayer(
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    { maxZoom: 19, attribution: "Tiles &copy; Esri" }
  ).addTo(mapa);
  const capas = {
    "Cartografía": cartografia,
    "Satélite Esri": satelite
  };
  const controlCapas = L.control.layers(capas, {}, { collapsed: false }).addTo(mapa);
  L.control.scale({ metric: true, imperial: false }).addTo(mapa);
  mapa.setMaxBounds(limitesArgentina.pad(0.35));

  function agregarCampo(feature) {
    const p = feature.properties;
    const grupo = L.featureGroup();
    const marker = L.circleMarker(
      [feature.geometry.coordinates[1], feature.geometry.coordinates[0]],
      { radius: 8, color: "#fff", weight: 2, fillColor: "#1769aa", fillOpacity: 0.95 }
    );
    const contenido = document.createElement("div");
    const titulo = document.createElement("strong");
    titulo.textContent = p.campo;
    contenido.appendChild(titulo);
    if (p.localidad || p.provincia) {
      const ubicacion = document.createElement("div");
      ubicacion.textContent = [p.localidad, p.provincia].filter(Boolean).join(", ");
      contenido.appendChild(ubicacion);
    }
    if (p.lotes.length) {
      const lista = document.createElement("ul");
      p.lotes.forEach(lote => {
        const li = document.createElement("li");
        const superficie = lote.superficie_ha ? ` · ${lote.superficie_ha} ha` : "";
        li.textContent = `${lote.nombre}: ${lote.cultivo || "cultivo no indicado"}${superficie}`;
        lista.appendChild(li);
      });
      contenido.appendChild(lista);
    } else {
      const sinLotes = document.createElement("div");
      sinLotes.textContent = "Sin lotes activos registrados.";
      contenido.appendChild(sinLotes);
    }
    const enlace = document.createElement("a");
    enlace.href = p.url;
    enlace.textContent = "Abrir campo";
    contenido.appendChild(enlace);
    marker.bindPopup(contenido.cloneNode(true));
    marker.on("click", evento => {
      L.DomEvent.stopPropagation(evento.originalEvent);
      consultarClima(feature.geometry.coordinates[1], feature.geometry.coordinates[0]);
    });
    marker.addTo(grupo);
    p.lotes.forEach(lote => {
      if (!lote.limite_geojson) return;
      const limite = L.geoJSON(JSON.parse(lote.limite_geojson), {
        style: { color: "#ff3b30", weight: 4, opacity: 0.95, fillColor: "#ff3b30", fillOpacity: 0.12 }
      });
      limite.eachLayer(capa => {
        capa.bindPopup(contenido.cloneNode(true));
        capa.on("click", evento => L.DomEvent.stopPropagation(evento.originalEvent));
      });
      limite.addTo(grupo);
    });
    grupo._cultivos = p.lotes.map(lote => lote.cultivo).filter(Boolean);
    grupo.addTo(mapa);
    gruposCampos.push(grupo);
  }

  function mostrarFechaNdvi(fecha) {
    const plantilla = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/" +
      "MODIS_Terra_NDVI_8Day/default/" + fecha +
      "/GoogleMapsCompatible_Level9/{z}/{y}/{x}.png";
    const ndvi = L.tileLayer(plantilla, {
      maxNativeZoom: 9, maxZoom: 14, opacity: 0.68,
      attribution: "NDVI &copy; NASA GIBS / MODIS Terra",
      errorTileUrl: ""
    });
    ndvi.addTo(mapa);
    capas["Vegetación NDVI · NASA (" + fecha + ")"] = ndvi;
    controlCapas.addOverlay(ndvi, "Vegetación NDVI · NASA (" + fecha + ")");
    estado.textContent = "Capa de vegetación NASA MODIS disponible: " + fecha +
      ". Es un compuesto satelital, no detección en tiempo real de cultivos.";
  }

  fetch(window.MAPA_AGRICOLA.camposUrl)
    .then(respuesta => {
      if (!respuesta.ok) throw new Error("No se pudieron cargar los campos registrados.");
      return respuesta.json();
    })
    .then(datos => {
      datos.features.forEach(agregarCampo);
      if (datos.features.length) {
        estado.textContent = datos.features.length + " campo(s) registrado(s). Los perímetros dibujados se muestran en rojo; los lotes sin perímetro se representan con punto central.";
      } else {
        estado.textContent = "Todavía no hay campos geolocalizados. La capa satelital muestra vegetación regional.";
      }
    })
    .catch(error => {
      estado.textContent = error.message;
    });

  fetch(window.MAPA_AGRICOLA.ndviFechaUrl)
    .then(respuesta => respuesta.json().then(datos => {
      if (!respuesta.ok) throw new Error(datos.error || "No se pudo consultar la capa NDVI.");
      return datos;
    }))
    .then(datos => mostrarFechaNdvi(datos.fecha))
    .catch(error => {
      const anterior = estado.textContent;
      estado.textContent = anterior + " No se pudo cargar la fecha NDVI: " + error.message;
    });

  filtro.addEventListener("change", () => {
    const cultivoElegido = filtro.value.toLocaleLowerCase();
    gruposCampos.forEach(grupo => {
      const coincide = !cultivoElegido || grupo._cultivos.some(
        cultivo => cultivo.toLocaleLowerCase() === cultivoElegido
      );
      if (coincide && !mapa.hasLayer(grupo)) grupo.addTo(mapa);
      if (!coincide && mapa.hasLayer(grupo)) mapa.removeLayer(grupo);
    });
  });

  mapa.on("click", evento => {
    if (marcadorSeleccionado) mapa.removeLayer(marcadorSeleccionado);
    marcadorSeleccionado = L.circleMarker(evento.latlng, {
      radius: 7, color: "#fff", weight: 2, fillColor: "#e65100", fillOpacity: 1
    }).addTo(mapa);
    consultarClima(evento.latlng.lat, evento.latlng.lng);
  });

  function consultarClima(latitud, longitud) {
    ultimaUbicacion = { latitud, longitud };
    clima.textContent = "Consultando pronóstico…";
    actualizacion.textContent = "";
    const url = new URL("https://api.open-meteo.com/v1/forecast");
    url.search = new URLSearchParams({
      latitude: latitud.toFixed(4),
      longitude: longitud.toFixed(4),
      current: "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m",
      daily: "temperature_2m_max,temperature_2m_min,precipitation_sum",
      forecast_days: "7",
      timezone: "America/Argentina/Buenos_Aires"
    });
    fetch(url)
      .then(respuesta => {
        if (!respuesta.ok) throw new Error("El servicio meteorológico respondió HTTP " + respuesta.status + ".");
        return respuesta.json();
      })
      .then(datos => renderizarClima(datos, latitud, longitud))
      .catch(error => {
        clima.textContent = "No se pudo obtener el clima: " + error.message;
      });
    if (temporizadorClima) clearTimeout(temporizadorClima);
    temporizadorClima = setTimeout(() => {
      if (ultimaUbicacion) consultarClima(ultimaUbicacion.latitud, ultimaUbicacion.longitud);
    }, 15 * 60 * 1000);
  }

  function renderizarClima(datos, latitud, longitud) {
    const actual = datos.current || {};
    const titulo = document.createElement("p");
    titulo.textContent = `Punto ${latitud.toFixed(3)}, ${longitud.toFixed(3)} · ` +
      `${actual.temperature_2m ?? "—"} °C · humedad ${actual.relative_humidity_2m ?? "—"}% · ` +
      `precipitación ${actual.precipitation ?? "—"} mm · viento ${actual.wind_speed_10m ?? "—"} km/h`;
    const lista = document.createElement("ul");
    const diario = datos.daily || {};
    (diario.time || []).forEach((fecha, i) => {
      const item = document.createElement("li");
      item.textContent = `${fecha}: ${diario.temperature_2m_min[i]}–${diario.temperature_2m_max[i]} °C, ` +
        `${diario.precipitation_sum[i]} mm de precipitación`;
      lista.appendChild(item);
    });
    clima.replaceChildren(titulo, lista);
    actualizacion.textContent = "Última consulta al servicio meteorológico: " +
      (actual.time || "sin fecha disponible") + ". Se actualiza cada 15 minutos mientras la página está abierta.";
  }
});
