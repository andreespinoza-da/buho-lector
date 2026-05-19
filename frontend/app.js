/* ============================================
   BÚHO LECTOR — app.js
   Conecta con el backend FastAPI en /api/*
   ============================================ */

const API = 'http://localhost:8000';

// ── Estado global ────────────────────────────
let usuarioId = null;
let catalogoId = null;

// ── Vistas ──────────────────────────────────
const vistas = {
  login:           document.getElementById('vista-login'),
  recomendaciones: document.getElementById('vista-recomendaciones'),
  catalogo:        document.getElementById('vista-catalogo'),
};

function mostrarVista(nombre) {
  Object.values(vistas).forEach(v => v.classList.add('oculto'));
  vistas[nombre].classList.remove('oculto');
}

// ── LOGIN ────────────────────────────────────
async function login() {
  const input = document.getElementById('input-id');
  const error = document.getElementById('error-login');
  const id    = parseInt(input.value, 10);

  error.textContent = '';

  if (!id || id <= 0) {
    error.textContent = 'Introduce un ID de usuario válido.';
    return;
  }

  try {
    const res = await fetch(`${API}/usuarios/${id}`);
    if (!res.ok) throw new Error('Usuario no encontrado');
    const usuario = await res.json();

    const resCatalogos = await fetch(`${API}/usuarios/${id}/catalogos`);
    if (!resCatalogos.ok) throw new Error('Error al obtener catálogos');
    const catalogos = await resCatalogos.json();

    usuarioId = id;

    if (catalogos.length === 0) {
      catalogoId = null;
    } else {
      catalogoId = catalogos[0].id;
    }

    mostrarVista('recomendaciones');
    cargarRecomendaciones();
  } catch (e) {
    error.textContent = 'No se encontró el usuario. Comprueba el ID.';
  }
}

function cerrarSesion() {
  usuarioId = null;
  catalogoId = null;
  document.getElementById('input-id').value = '';
  document.getElementById('error-login').textContent = '';
  mostrarVista('login');
}

// Permitir Enter en el input de login
document.getElementById('input-id').addEventListener('keydown', e => {
  if (e.key === 'Enter') login();
});

// ── RECOMENDACIONES ──────────────────────────
async function cargarRecomendaciones() {
  const contenedor = document.getElementById('lista-recomendaciones');

  if (!catalogoId) {
    contenedor.innerHTML = '<div class="estado-vacio">Tu profesor aún no ha asignado un catálogo.</div>';
    return;
  }

  contenedor.innerHTML = '<div class="estado-carga">Buscando lecturas para ti…</div>';

  try {
    const res  = await fetch(`${API}/recomendaciones/${usuarioId}`);
    if (!res.ok) throw new Error('Sin recomendaciones');
    const data = await res.json();

    const libros = Array.isArray(data) ? data : (data.recommendations ?? []);

    if (libros.length === 0) {
      contenedor.innerHTML = '<div class="estado-vacio">Aún no hay recomendaciones para este usuario.</div>';
      return;
    }

    contenedor.innerHTML = libros.map(renderTarjeta).join('');
    animarBarras();
  } catch (e) {
    contenedor.innerHTML = '<div class="estado-vacio">No se pudieron cargar las recomendaciones.</div>';
    console.error(e);
  }
}

function verRecomendaciones() {
  mostrarVista('recomendaciones');
  cargarRecomendaciones();
}

// ── CATÁLOGO ─────────────────────────────────
let catalogoCompleto = [];

async function verCatalogo() {
  mostrarVista('catalogo');

  if (!catalogoId) {
    document.getElementById('lista-catalogo').innerHTML =
      '<div class="estado-vacio">Tu profesor aún no ha asignado un catálogo.</div>';
    return;
  }

  const lista = document.getElementById('lista-catalogo');
  if (!document.getElementById('buscador-catalogo')) {
    const buscador = document.createElement('input');
    buscador.type        = 'text';
    buscador.id          = 'buscador-catalogo';
    buscador.placeholder = 'Buscar por título, autor o género…';
    document.getElementById('vista-catalogo').insertBefore(buscador, lista);
    buscador.addEventListener('input', filtrarCatalogo);
  }

  lista.innerHTML = '<div class="estado-carga">Cargando catálogo…</div>';

  try {
    const res  = await fetch(`${API}/libros/catalogo/${catalogoId}`);
    if (!res.ok) throw new Error('Error al cargar catálogo');
    const data = await res.json();

    catalogoCompleto = Array.isArray(data) ? data : (data.books ?? []);

    if (catalogoCompleto.length === 0) {
      lista.innerHTML = '<div class="estado-vacio">El catálogo está vacío.</div>';
      return;
    }

    renderCatalogo(catalogoCompleto);
  } catch (e) {
    lista.innerHTML = '<div class="estado-vacio">No se pudo cargar el catálogo.</div>';
    console.error(e);
  }
}

function renderCatalogo(libros) {
  const lista = document.getElementById('lista-catalogo');
  lista.innerHTML = libros.map(renderTarjeta).join('');
  animarBarras();
}

function filtrarCatalogo() {
  const q = document.getElementById('buscador-catalogo').value.toLowerCase();
  if (!q) { renderCatalogo(catalogoCompleto); return; }

  const filtrados = catalogoCompleto.filter(libro => {
    const titulo  = (libro.title  ?? libro.titulo  ?? '').toLowerCase();
    const autor   = (libro.author ?? libro.autor   ?? '').toLowerCase();
    const genero  = (libro.genre  ?? libro.genero  ?? libro.category ?? '').toLowerCase();
    return titulo.includes(q) || autor.includes(q) || genero.includes(q);
  });

  renderCatalogo(filtrados.length ? filtrados : []);
  if (!filtrados.length) {
    document.getElementById('lista-catalogo').innerHTML =
      '<div class="estado-vacio">Sin resultados para «' + q + '».</div>';
  }
}

// ── RENDERIZADO DE TARJETA ───────────────────
function renderTarjeta(libro) {
  // Normaliza campos (por si el backend usa snake_case o español)
  const titulo  = libro.title       ?? libro.titulo       ?? '(Sin título)';
  const autor   = libro.author      ?? libro.autor        ?? 'Autor desconocido';
  const genero  = libro.genre       ?? libro.genero       ?? libro.category ?? '';
  const score   = libro.score       ?? libro.similarity   ?? libro.rating   ?? null;

  const pct = score !== null ? Math.min(Math.round(score * 100), 100) : null;

  return `
    <div class="tarjeta-libro">
      <span class="libro-titulo">${escapar(titulo)}</span>
      ${genero ? `<span class="libro-genero">${escapar(genero)}</span>` : ''}
      <span class="libro-autor">${escapar(autor)}</span>
      ${pct !== null ? `
        <div class="libro-score">
          <span>score: ${(score).toFixed(2)}</span>
          <div class="libro-score-barra">
            <div class="libro-score-barra-fill" data-pct="${pct}" style="width:0%"></div>
          </div>
        </div>` : ''}
    </div>`;
}

// ── ANIMACIÓN DE BARRAS ──────────────────────
function animarBarras() {
  // Pequeño delay para que el DOM esté pintado
  requestAnimationFrame(() => {
    document.querySelectorAll('.libro-score-barra-fill').forEach(el => {
      el.style.width = el.dataset.pct + '%';
    });
  });
}

// ── UTILIDADES ───────────────────────────────
function escapar(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ── INIT ─────────────────────────────────────
mostrarVista('login');