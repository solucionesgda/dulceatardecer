(function () {
    function actualizarOtraObraSocial() {
        const selector = document.getElementById("id_obra_social");
        const campoOtra = document.querySelector(".field-obra_social_otra");
        if (!selector || !campoOtra) return;
        campoOtra.style.display = selector.value === "Otra" ? "" : "none";
    }

    document.addEventListener("DOMContentLoaded", function () {
        const selector = document.getElementById("id_obra_social");
        if (!selector) return;
        selector.addEventListener("change", actualizarOtraObraSocial);
        actualizarOtraObraSocial();
    });
})();
