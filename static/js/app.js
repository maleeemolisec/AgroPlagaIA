// AgroPlaga IA - JavaScript general: menú, validaciones, confirmaciones
document.addEventListener("DOMContentLoaded", () => {
  // Menú móvil
  const btn = document.getElementById("menuBtn"), menu = document.getElementById("menu");
  if (btn) btn.addEventListener("click", () => {
    const abierto = menu.classList.toggle("abierto");
    btn.setAttribute("aria-expanded", abierto);
  });

  // Mostrar u ocultar campos de contraseña
  document.querySelectorAll("[data-password-toggle]").forEach(toggle => {
    const input = document.getElementById(toggle.dataset.passwordToggle);
    if (!input) return;
    toggle.addEventListener("click", () => {
      const mostrar = input.type === "password";
      input.type = mostrar ? "text" : "password";
      toggle.textContent = mostrar ? "Ocultar" : "Mostrar";
      toggle.setAttribute("aria-pressed", String(mostrar));
    });
  });

  // Confirmación antes de acciones destructivas
  document.querySelectorAll("form[data-confirmar]").forEach(f =>
    f.addEventListener("submit", e => { if (!confirm(f.dataset.confirmar)) e.preventDefault(); }));

  // Validación de formularios en el cliente (el servidor valida de nuevo)
  document.querySelectorAll("form[data-validar]").forEach(form => {
    form.addEventListener("submit", e => {
      let ok = true;
      form.querySelectorAll(".error-campo").forEach(n => n.remove());
      form.querySelectorAll(".invalido").forEach(n => n.classList.remove("invalido"));
      form.querySelectorAll("input, select, textarea").forEach(campo => {
        let msg = "";
        const v = campo.value.trim();
        if (campo.required && !v) msg = "Este campo es obligatorio.";
        else if (campo.type === "email" && v && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v)) msg = "Ingresá un correo válido.";
        else if (campo.minLength > 0 && v && v.length < campo.minLength) msg = `Mínimo ${campo.minLength} caracteres.`;
        else if (campo.type === "password" && campo.name === "password" && v && !(/\d/.test(v) && /[A-Za-z]/.test(v))) msg = "Debe incluir letras y números.";
        else if (campo.dataset.igual && v !== form.querySelector(`[name="${campo.dataset.igual}"]`).value) msg = "Las contraseñas no coinciden.";
        else if (campo.type === "number" && v && campo.min !== "" && parseFloat(v) < parseFloat(campo.min)) msg = `El mínimo es ${campo.min}.`;
        if (msg) {
          ok = false;
          campo.classList.add("invalido");
          const s = document.createElement("span");
          s.className = "error-campo"; s.textContent = msg;
          campo.insertAdjacentElement("afterend", s);
        }
      });
      if (!ok) { e.preventDefault(); const p = form.querySelector(".invalido"); if (p) p.focus(); }
    });
  });

  // Indicador de fortaleza de contraseña
  const pw = document.getElementById("password"), fz = document.getElementById("fuerza");
  if (pw && fz) pw.addEventListener("input", () => {
    const v = pw.value; let p = 0;
    if (v.length >= 8) p++; if (/\d/.test(v)) p++; if (/[A-Z]/.test(v) && /[a-z]/.test(v)) p++; if (/[^A-Za-z0-9]/.test(v)) p++;
    const n = ["Muy débil", "Débil", "Aceptable", "Buena", "Fuerte"][p];
    fz.textContent = v ? "Seguridad: " + n : "";
    fz.style.color = p < 2 ? "#c62828" : p < 3 ? "#b78103" : "#2e7d32";
  });
});
