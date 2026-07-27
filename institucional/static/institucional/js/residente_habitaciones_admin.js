(function () {
    function cargarHabitaciones() {
        const geriatrico = document.getElementById("id_geriatrico");
        const habitacion = document.getElementById("id_habitacion");
        if (!geriatrico || !habitacion || !geriatrico.value) return;

        let url = habitacion.dataset.habitacionesUrl.replace("/0/", "/" + geriatrico.value + "/");
        const coincidencia = window.location.pathname.match(/\/residente\/(\d+)\/change\//);
        if (coincidencia) url += "?residente_id=" + coincidencia[1];

        fetch(url)
            .then((respuesta) => respuesta.json())
            .then((datos) => {
                const actual = habitacion.value;
                habitacion.innerHTML = "";
                datos.habitaciones.forEach(([valor, etiqueta]) => {
                    const opcion = new Option(etiqueta, valor, false, valor === actual);
                    habitacion.add(opcion);
                });
            });
    }

    document.addEventListener("DOMContentLoaded", function () {
        const geriatrico = document.getElementById("id_geriatrico");
        if (!geriatrico) return;
        geriatrico.addEventListener("change", cargarHabitaciones);
        cargarHabitaciones();
    });
})();
