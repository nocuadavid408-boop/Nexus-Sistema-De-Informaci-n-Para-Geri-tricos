// Itinerario: cascada Categoría -> Medicamento/Actividad, día de solo lectura
// y ✓/✗ por hora. Lo usan crear.html, calendario.html y el panel del personal.
const nxEsc = s => String(s ?? '').replace(/[&<>"']/g,
  c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

// ---------- Cascada ----------
function nxOpciones(arr, vacio) {
  return `<option value="">${vacio}</option>` +
    arr.map(o => `<option value="${o.id}">${nxEsc(o.nombre)}</option>`).join('');
}

async function nxCargarCategorias(tipo, selCat, selItem) {
  selItem.innerHTML = nxOpciones([], 'Primero elige la categoría');
  selItem.disabled = true;
  const d = await (await fetch(`/api/catalogo/${tipo}/categorias`)).json();
  selCat.innerHTML = nxOpciones(d.items || [], 'Selecciona una categoría…');
}

async function nxCargarItems(tipo, categoriaId, selItem) {
  if (!categoriaId) {
    selItem.innerHTML = nxOpciones([], 'Primero elige la categoría');
    selItem.disabled = true;
    return;
  }
  const d = await (await fetch(`/api/catalogo/${tipo}/items?categoria_id=${categoriaId}`)).json();
  selItem.innerHTML = nxOpciones(d.items || [],
    tipo === 'medicamento' ? 'Selecciona el medicamento…' : 'Selecciona la actividad…');
  selItem.disabled = false;
}

// ---------- Día del calendario: SOLO LECTURA (sin editar ni eliminar) ----------
function nxFila(e, editable) {
  const check = editable
    ? `<div class="ag-check" role="group" aria-label="Estado">
         <button type="button" class="ag-btn ag-ok" title="Completado" onclick="nxCheck(${e.id},'${e.hora}','completado',this)">✓</button>
         <button type="button" class="ag-btn ag-no" title="Pendiente" onclick="nxCheck(${e.id},'${e.hora}','pendiente',this)">✗</button>
       </div>`
    : `<span class="ag-estado-solo" title="${e.completado ? 'Completado' : 'Pendiente'}">${e.completado ? '✅' : '⏳'}</span>`;
  const quien = e.completado && e.por ? ` · ✓ ${nxEsc(e.por)} ${nxEsc(e.en || '')}` : '';
  return `<li class="ag-fila ${e.completado ? 'ag-hecho' : 'ag-pend'}" data-id="${e.id}" data-hora="${e.hora}" data-tipo="${e.tipo}">
    <span class="ag-hora">${e.hora}</span>
    <span class="ag-icono">${e.tipo === 'medicamento' ? '💊' : '🏃'}</span>
    <div class="ag-texto"><strong>${nxEsc(e.nombre)}</strong>
      <small>${nxEsc(e.observaciones || '')}${quien}</small></div>${check}</li>`;
}

function nxPintarListas(items, editable, ulMed, ulAct) {
  const vacio = t => `<li class="ag-vacio" style="color:var(--txt-muted)">Sin ${t} este día.</li>`;
  const med = items.filter(e => e.tipo === 'medicamento');
  const act = items.filter(e => e.tipo === 'actividad');
  ulMed.innerHTML = med.length ? med.map(e => nxFila(e, editable)).join('') : vacio('medicamentos');
  ulAct.innerHTML = act.length ? act.map(e => nxFila(e, editable)).join('') : vacio('actividades');
}

// ---------- ✓ / ✗ ----------
async function nxCheck(id, hora, estado, boton) {
  const fila = boton.closest('[data-id]');
  const fd = new FormData(); fd.append('hora', hora); fd.append('estado', estado);
  boton.disabled = true;
  try {
    const d = await (await fetch(`/itinerario/${id}/check`, { method: 'POST', body: fd })).json();
    if (!d.ok) { alert(d.error || 'No se pudo actualizar.'); return; }
    fila.classList.toggle('ag-hecho', estado === 'completado');
    fila.classList.toggle('ag-pend', estado !== 'completado');

    // Panel del personal: contador y barra.
    const cont = document.getElementById('ruta-contador');
    if (cont) {
      const filas = document.querySelectorAll('#ruta [data-id]');
      const hechas = document.querySelectorAll('#ruta .ag-hecho').length;
      cont.textContent = `${hechas} de ${filas.length} hechas`;
      const top = document.getElementById('ruta-hechas-top');
      if (top) top.textContent = `${hechas}/${filas.length}`;
      const barra = document.getElementById('ruta-barra');
      if (barra) barra.style.width = (filas.length ? Math.floor(hechas * 100 / filas.length) : 0) + '%';
    }
    document.dispatchEvent(new CustomEvent('itinerario:check'));
  } catch (e) {
    alert('Error de conexión. Intenta de nuevo.');
  } finally {
    boton.disabled = false;
  }
}
