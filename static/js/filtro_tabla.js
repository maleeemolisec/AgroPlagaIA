// Filtro en vivo sobre una tabla (sin recargar la página)
document.addEventListener("DOMContentLoaded", () => {
  const input = document.getElementById("buscar"), tabla = document.getElementById("tablaAnalisis");
  if (!input || !tabla) return;
  input.addEventListener("input", () => {
    const q = input.value.toLowerCase().trim();
    tabla.querySelectorAll("tbody tr").forEach(tr => {
      tr.style.display = tr.textContent.toLowerCase().includes(q) ? "" : "none";
    });
  });
});
