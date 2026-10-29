const PDFDocument = require("pdfkit");
const fs = require("fs");

// ---------------------------------------------------------
// CONFIGURACIÓN
// ---------------------------------------------------------

const outputPath = process.argv[2];

if (!outputPath) {
    console.error("ERROR: No se indicó la ruta del PDF.");
    process.exit(1);
}

// ---------------------------------------------------------
// LEER DATOS ENVIADOS DESDE PYTHON
// ---------------------------------------------------------

let input = "";

process.stdin.setEncoding("utf8");

process.stdin.on("data", chunk => {
    input += chunk;
});

process.stdin.on("end", () => {
    try {
        const datos = JSON.parse(input);
        generarPDF(datos);
    } catch (error) {
        console.error("ERROR al leer los datos:", error.message);
        process.exit(1);
    }
});

// ---------------------------------------------------------
// GENERAR PDF
// ---------------------------------------------------------

function generarPDF(datos) {

    const doc = new PDFDocument({
        size: "A4",
        margin: 50
    });

    const stream = fs.createWriteStream(outputPath);

    doc.pipe(stream);

    // -----------------------------------------------------
    // ENCABEZADO
    // -----------------------------------------------------

    doc
        .fontSize(24)
        .font("Helvetica-Bold")
        .text("NEXUS", { align: "center" });

    doc
        .fontSize(13)
        .font("Helvetica")
        .text("Sistema de Información para Hogares Geriátricos", {
            align: "center"
        });

    doc.moveDown();

    doc
        .fontSize(18)
        .font("Helvetica-Bold")
        .text("Reporte del Cuidador", {
            align: "center"
        });

    doc.moveDown();

    // Línea separadora
    doc
        .moveTo(50, doc.y)
        .lineTo(545, doc.y)
        .stroke();

    doc.moveDown();

    // -----------------------------------------------------
    // INFORMACIÓN DEL CUIDADOR
    // -----------------------------------------------------

    const cuidador = datos.cuidador || {};

    doc
        .fontSize(15)
        .font("Helvetica-Bold")
        .text("Información del cuidador");

    doc.moveDown(0.5);

    doc.fontSize(11).font("Helvetica");

    doc.text(`Nombre: ${cuidador.nombre || "No registrado"}`);
    doc.text(`Correo: ${cuidador.correo || "No registrado"}`);
    doc.text(`Teléfono: ${cuidador.telefono || "No registrado"}`);
    doc.text(`Turno: ${cuidador.turno || "No registrado"}`);

    doc.moveDown();

    // -----------------------------------------------------
    // RESIDENTES
    // -----------------------------------------------------

    const residentes = datos.residentes || [];

    doc
        .fontSize(15)
        .font("Helvetica-Bold")
        .text(`Adultos mayores a cargo (${residentes.length})`);

    doc.moveDown();

    if (residentes.length === 0) {

        doc
            .fontSize(11)
            .font("Helvetica")
            .text("No hay adultos mayores asignados a este cuidador.");

    } else {

        residentes.forEach((residente, index) => {

            // Evitar que una nueva sección quede cortada
            if (doc.y > 680) {
                doc.addPage();
            }

            // -------------------------------------------------
            // DATOS DEL RESIDENTE
            // -------------------------------------------------

            doc
                .fontSize(14)
                .font("Helvetica-Bold")
                .text(`${index + 1}. ${residente.nombre || "Sin nombre"}`);

            doc.moveDown(0.3);

            doc
                .fontSize(10)
                .font("Helvetica");

            doc.text(`Documento: ${residente.documento || "No registrado"}`);
            doc.text(`Edad: ${residente.edad ?? "No registrada"}`);
            doc.text(`Habitación: ${residente.habitacion || "No registrada"}`);

            if (residente.diagnostico) {
                doc.text(`Diagnóstico: ${residente.diagnostico}`);
            }

            doc.moveDown(0.5);

            // -------------------------------------------------
            // ACTIVIDADES
            // -------------------------------------------------

            doc
                .fontSize(12)
                .font("Helvetica-Bold")
                .text("Actividades asignadas");

            doc.moveDown(0.3);

            const actividades = residente.actividades || [];

            if (actividades.length === 0) {

                doc
                    .fontSize(10)
                    .font("Helvetica")
                    .text("No hay actividades registradas.");

            } else {

                actividades.forEach(actividad => {

                    doc
                        .fontSize(10)
                        .font("Helvetica")
                        .text(
                            `• ${actividad.fecha || ""} - ` +
                            `${actividad.hora || ""} - ` +
                            `${actividad.actividad || ""}`
                        );
                });
            }

            doc.moveDown(0.5);

            // -------------------------------------------------
            // MEDICAMENTOS
            // -------------------------------------------------

            doc
                .fontSize(12)
                .font("Helvetica-Bold")
                .text("Medicamentos");

            doc.moveDown(0.3);

            const medicamentos = residente.medicamentos || [];

            if (medicamentos.length === 0) {

                doc
                    .fontSize(10)
                    .font("Helvetica")
                    .text("No hay medicamentos registrados.");

            } else {

                medicamentos.forEach(medicamento => {

                    doc
                        .fontSize(10)
                        .font("Helvetica")
                        .text(
                            `• ${medicamento.nombre || "Sin nombre"} ` +
                            `| Dosis: ${medicamento.dosis || "No registrada"} ` +
                            `| Día: ${medicamento.dia || "Todos los días"} ` +
                            `| Horario: ${medicamento.horario || "No registrado"}`
                        );

                    if (medicamento.observaciones) {
                        doc.text(
                            `  Observaciones: ${medicamento.observaciones}`
                        );
                    }
                });
            }

            doc.moveDown();

            // Separador entre residentes
            doc
                .moveTo(50, doc.y)
                .lineTo(545, doc.y)
                .stroke();

            doc.moveDown();
        });
    }

    // -----------------------------------------------------
    // PIE DE PÁGINA
    // -----------------------------------------------------

    const paginas = doc.bufferedPageRange();

    for (
        let i = paginas.start;
        i < paginas.start + paginas.count;
        i++
    ) {

        doc.switchToPage(i);

        doc
            .fontSize(8)
            .font("Helvetica")
            .text(
                `Nexus - Reporte del cuidador | Página ${i + 1}`,
                50,
                770,
                {
                    align: "center",
                    width: 495
                }
            );
    }

    // -----------------------------------------------------
    // FINALIZAR
    // -----------------------------------------------------

    doc.end();

    stream.on("finish", () => {
        console.log(`PDF generado correctamente: ${outputPath}`);
    });

    stream.on("error", error => {
        console.error("ERROR al crear el PDF:", error.message);
        process.exit(1);
    });
}