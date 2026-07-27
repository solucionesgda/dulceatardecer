(function () {
    function actualizarOtraObraSocial() {
        const selector = document.getElementById("id_obra_social");
        const campoOtra = document.querySelector(".field-obra_social_otra");
        if (!selector || !campoOtra) return;
        const esOtra = selector.value === "Otra";
        campoOtra.style.display = esOtra ? "" : "none";
        if (!esOtra) {
            const inputOtra = campoOtra.querySelector("input");
            if (inputOtra) inputOtra.value = "";
        }
    }

    document.addEventListener("DOMContentLoaded", function () {
        const selector = document.getElementById("id_obra_social");
        if (!selector) return;
        selector.addEventListener("change", actualizarOtraObraSocial);
        actualizarOtraObraSocial();
    });
})();
