// Formulario de análisis: vista previa, validación de la foto, ubicación por defecto y pantalla de carga
document.addEventListener("DOMContentLoaded", () => {
  const foto = document.getElementById("foto"), vista = document.getElementById("vista");
  const lote = document.getElementById("lote_id"), form = document.getElementById("formAnalisis");
  if (!form) return;

  foto.addEventListener("change", () => {
    const f = foto.files[0];
    if (!f) { vista.hidden = true; return; }
    if (f.size > 10 * 1024 * 1024) { alert("La foto supera los 10 MB."); foto.value = ""; vista.hidden = true; return; }
    if (!/^image\//.test(f.type)) { alert("El archivo debe ser una imagen."); foto.value = ""; vista.hidden = true; return; }
    vista.src = URL.createObjectURL(f); vista.hidden = false;
  });

  // Al elegir lote, centrar el mapa en su campo (si tiene ubicación)
  function centrar() {
    const o = lote.options[lote.selectedIndex];
    if (!o || !o.dataset.lat || !window._mapaSelector) return;
    const la = parseFloat(o.dataset.lat), lo = parseFloat(o.dataset.lng);
    if (!isNaN(la) && !document.getElementById("latitud").value) window._mapaSelector.mapa.setView([la, lo], 14);
  }
  lote.addEventListener("change", centrar); setTimeout(centrar, 300);

  form.addEventListener("submit", e => {
    if (e.defaultPrevented) return;
    document.getElementById("cargando").hidden = false;
    document.getElementById("btnAnalizar").disabled = true;
  });
});
