/* ── CONFIG ───────────────────────────────────────────────────────────────── */
// Quando o frontend é servido pelo próprio backend (porta 8000),
// usamos URL relativa. Se abrir o HTML direto no navegador (file://),
// cai no fallback para localhost:8000.
const API = window.location.protocol === 'file:'
  ? 'http://localhost:8000/api'
  : '/api';

/* ── STATE ────────────────────────────────────────────────────────────────── */
let currentProtocolo = null;
let filterConcluido = 'false';
let searchDebounce = null;

/* ── INIT ─────────────────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  iniciarRelogio();
  verificarAPI();
  navegarPara('dashboard');
  configurarEventos();
});

/* ── RELÓGIO ──────────────────────────────────────────────────────────────── */
function iniciarRelogio() {
  const el = document.getElementById('topbarTime');
  const atualizar = () => {
    el.textContent = new Date().toLocaleString('pt-BR', {
      weekday: 'short', day: '2-digit', month: '2-digit',
      year: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit'
    });
  };
  atualizar();
  setInterval(atualizar, 1000);
}

/* ── API STATUS ───────────────────────────────────────────────────────────── */
async function verificarAPI() {
  const el = document.getElementById('apiStatus');
  const dot = el.querySelector('.status-dot');
  try {
    await fetch(`${API.replace('/api', '')}/`);
    dot.classList.add('online');
    el.childNodes[1].textContent = ' API online';
  } catch {
    dot.classList.add('offline');
    el.childNodes[1].textContent = ' Sem conexão';
  }
}

/* ── NAVEGAÇÃO ────────────────────────────────────────────────────────────── */
function navegarPara(pagina) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));

  document.getElementById(`page-${pagina}`)?.classList.add('active');
  document.querySelector(`[data-page="${pagina}"]`)?.classList.add('active');

  const titulos = {
    dashboard: 'Dashboard',
    protocolos: 'Protocolos',
    importar: 'Importar CSV',
    revendas: 'Revendas',
  };
  document.getElementById('topbarTitle').textContent = titulos[pagina] || pagina;

  if (pagina === 'dashboard') carregarDashboard();
  if (pagina === 'protocolos') carregarProtocolos();
  if (pagina === 'revendas') carregarRevendas();
}

/* ── EVENTOS ──────────────────────────────────────────────────────────────── */
function configurarEventos() {
  // Navegação
  document.querySelectorAll('.nav-item').forEach(btn => {
    btn.addEventListener('click', () => navegarPara(btn.dataset.page));
  });

  // Filtros de status
  document.querySelectorAll('.filter-tab').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.filter-tab').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      filterConcluido = btn.dataset.filter;
      carregarProtocolos();
    });
  });

  // Busca com debounce
  document.getElementById('searchInput').addEventListener('input', e => {
    clearTimeout(searchDebounce);
    searchDebounce = setTimeout(() => carregarProtocolos(e.target.value), 350);
  });

  // Toggle concluído no modal
  document.getElementById('modalConcluido').addEventListener('change', function () {
    document.getElementById('toggleLabel').textContent = this.checked ? 'Concluído' : 'Pendente';
  });

  // Upload de arquivo
  const fileInput = document.getElementById('fileInput');
  fileInput.addEventListener('change', e => {
    if (e.target.files[0]) importarCSV(e.target.files[0]);
  });

  // Drag & drop
  const importArea = document.getElementById('importArea');
  importArea.addEventListener('dragover', e => { e.preventDefault(); importArea.classList.add('drag-over'); });
  importArea.addEventListener('dragleave', () => importArea.classList.remove('drag-over'));
  importArea.addEventListener('drop', e => {
    e.preventDefault();
    importArea.classList.remove('drag-over');
    const f = e.dataTransfer.files[0];
    if (f?.name.endsWith('.csv')) importarCSV(f);
    else mostrarToast('Envie um arquivo .csv', 'error');
  });

  // Nova revenda
  document.getElementById('btnNovaRevenda').addEventListener('click', () => {
    document.getElementById('revendaEditId').value = '';
    document.getElementById('revendaNome').value = '';
    document.getElementById('revendaTelefone').value = '';
    document.getElementById('modalRevendaTitulo').textContent = 'Nova Revenda';
    abrirModal('modalRevenda');
  });

  // Fechar modais clicando fora
  document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', e => {
      if (e.target === overlay) overlay.classList.add('hidden');
    });
  });
}

/* ── DASHBOARD ────────────────────────────────────────────────────────────── */
async function carregarDashboard() {
  try {
    const [stats, protocolos] = await Promise.all([
      fetchJSON(`${API}/stats`),
      fetchJSON(`${API}/protocolos?concluido=false`),
    ]);

    document.getElementById('statPendentes').textContent = stats.pendentes;
    document.getElementById('statConcluidos').textContent = stats.concluidos;
    document.getElementById('statTotal').textContent = stats.total_protocolos;
    document.getElementById('statRevendas').textContent = stats.revendas_cadastradas;

    const tbody = document.getElementById('dashTableBody');
    if (!protocolos.length) {
      tbody.innerHTML = `<tr><td colspan="6" class="empty">Nenhum protocolo pendente.</td></tr>`;
      return;
    }

    tbody.innerHTML = protocolos.slice(0, 10).map(p => `
      <tr>
        <td><span class="cell-mono">${p.numero_protocolo}</span></td>
        <td>${formatarData(p.datahora)}</td>
        <td>${p.revenda || '—'}</td>
        <td>${p.analista || '—'}</td>
        <td><span class="cell-truncate">${p.problema || '—'}</span></td>
        <td>
          <button class="btn btn-icon" onclick="abrirProtocolo(${p.id})">Abrir →</button>
        </td>
      </tr>
    `).join('');
  } catch {
    mostrarToast('Erro ao carregar dashboard', 'error');
  }
}

/* ── PROTOCOLOS ───────────────────────────────────────────────────────────── */
async function carregarProtocolos(busca = '') {
  const tbody = document.getElementById('protTableBody');
  tbody.innerHTML = `<tr><td colspan="7" class="empty">Carregando...</td></tr>`;

  try {
    let url = `${API}/protocolos`;
    const params = new URLSearchParams();
    if (filterConcluido !== '') params.set('concluido', filterConcluido);
    if (busca) params.set('busca', busca);
    if (params.toString()) url += '?' + params;

    const lista = await fetchJSON(url);

    if (!lista.length) {
      tbody.innerHTML = `<tr><td colspan="7" class="empty">Nenhum protocolo encontrado.</td></tr>`;
      return;
    }

    tbody.innerHTML = lista.map(p => `
      <tr>
        <td><span class="cell-mono">${p.numero_protocolo}</span></td>
        <td>${formatarData(p.datahora)}</td>
        <td>${p.revenda || '—'}</td>
        <td>${p.analista || '—'}</td>
        <td><span class="cell-truncate" title="${p.problema || ''}">${p.problema || '—'}</span></td>
        <td>
          <span class="badge ${p.concluido ? 'badge-done' : 'badge-pending'}">
            ${p.concluido ? 'Concluído' : 'Pendente'}
          </span>
        </td>
        <td style="display:flex;gap:6px">
          <button class="btn btn-icon" onclick="abrirProtocolo(${p.id})">Abrir →</button>
          <button class="btn btn-icon btn-danger" onclick="deletarProtocolo(${p.id}, '${p.numero_protocolo}')">✕</button>
        </td>
      </tr>
    `).join('');
  } catch {
    mostrarToast('Erro ao carregar protocolos', 'error');
  }
}

async function abrirProtocolo(id) {
  try {
    const p = await fetchJSON(`${API}/protocolos/${id}`);
    currentProtocolo = p;

    document.getElementById('modalNumero').textContent = p.numero_protocolo;
    document.getElementById('modalDatahora').textContent = formatarData(p.datahora);
    document.getElementById('modalRevendaNome').textContent = p.revenda || '—';
    document.getElementById('modalAnalista').textContent = p.analista || '—';
    document.getElementById('modalProblema').textContent = p.problema || '—';
    document.getElementById('modalSolucao').textContent = p.solucao || '—';
    document.getElementById('modalObs').value = p.observacao || '';

    const chk = document.getElementById('modalConcluido');
    chk.checked = p.concluido;
    document.getElementById('toggleLabel').textContent = p.concluido ? 'Concluído' : 'Pendente';

    abrirModal('modalProtocolo');
  } catch {
    mostrarToast('Erro ao abrir protocolo', 'error');
  }
}

async function salvarProtocolo() {
  if (!currentProtocolo) return;
  try {
    await fetchJSON(`${API}/protocolos/${currentProtocolo.id}`, {
      method: 'PATCH',
      body: JSON.stringify({
        observacao: document.getElementById('modalObs').value,
        concluido: document.getElementById('modalConcluido').checked,
      }),
    });
    mostrarToast('Protocolo atualizado!', 'success');
    fecharModal('modalProtocolo');
    carregarProtocolos(document.getElementById('searchInput').value);
    carregarDashboard();
  } catch {
    mostrarToast('Erro ao salvar protocolo', 'error');
  }
}

async function deletarProtocolo(id, numero) {
  if (!confirm(`Deletar o protocolo ${numero}? Esta ação não pode ser desfeita.`)) return;
  try {
    await fetch(`${API}/protocolos/${id}`, { method: 'DELETE' });
    mostrarToast('Protocolo deletado.', 'success');
    carregarProtocolos(document.getElementById('searchInput').value);
    carregarDashboard();
  } catch {
    mostrarToast('Erro ao deletar protocolo', 'error');
  }
}

/* ── MENSAGEM WHATSAPP ────────────────────────────────────────────────────── */
function gerarMensagemWhatsApp() {
  if (!currentProtocolo) return;

  const hora = new Date().getHours();
  let saudacao;
  if (hora >= 5 && hora < 12)       saudacao = 'Bom dia';
  else if (hora >= 12 && hora < 18) saudacao = 'Boa tarde';
  else                               saudacao = 'Boa noite';

  const problema = currentProtocolo.problema || 'chamado registrado';
  const datahora = formatarData(currentProtocolo.datahora);
  const protocolo = currentProtocolo.numero_protocolo;

  const mensagem =
    `${saudacao}!\n\n` +
    `Referente ao protocolo *#${protocolo}* registrado em ${datahora}.\n\n` +
    `*Assunto:* ${problema}\n\n` +
    `Gostaria de verificar se o problema foi solucionado ou se ainda precisam de auxilio.`;

  // Número: tenta revenda cadastrada, depois NUMEROTELEFONE do CSV
  const telefone = currentProtocolo.revenda_rel?.telefone
    || currentProtocolo.numero_telefone
    || '';
  const numeroLimpo = telefone.replace(/\D/g, '');

  const url = `https://wa.me/${numeroLimpo}?text=${encodeURIComponent(mensagem)}`;
  window.open(url, '_blank');
}

/* ── IMPORTAR CSV ─────────────────────────────────────────────────────────── */
async function importarCSV(arquivo) {
  const resultDiv = document.getElementById('importResult');
  resultDiv.classList.add('hidden');

  const formData = new FormData();
  formData.append('file', arquivo);

  try {
    mostrarToast('Importando CSV...', '');
    const resp = await fetch(`${API}/protocolos/importar`, { method: 'POST', body: formData });
    const data = await resp.json();

    if (!resp.ok) {
      mostrarToast(data.detail || 'Erro ao importar', 'error');
      return;
    }

    resultDiv.classList.remove('hidden');
    resultDiv.innerHTML = `
      <div class="result-title">✓ Importação concluída — ${arquivo.name}</div>
      <div class="result-grid">
        <div class="result-item">
          <div class="result-num">${data.total_lidos}</div>
          <div class="result-lbl">Linhas lidas</div>
        </div>
        <div class="result-item">
          <div class="result-num">${data.pendentes_encontrados}</div>
          <div class="result-lbl">Pendentes</div>
        </div>
        <div class="result-item">
          <div class="result-num">${data.novos_inseridos}</div>
          <div class="result-lbl">Inseridos</div>
        </div>
        <div class="result-item">
          <div class="result-num">${data.ja_existentes}</div>
          <div class="result-lbl">Já existiam</div>
        </div>
      </div>
      ${data.erros?.length ? `
        <div class="result-erros">
          ${data.erros.map(e => `<span>⚠ ${e}</span>`).join('')}
        </div>` : ''}
    `;
    mostrarToast(`${data.novos_inseridos} protocolo(s) importado(s)!`, 'success');
  } catch {
    mostrarToast('Erro de conexão ao importar', 'error');
  }
}

/* ── REVENDAS ─────────────────────────────────────────────────────────────── */
async function carregarRevendas() {
  const tbody = document.getElementById('revTableBody');
  try {
    const lista = await fetchJSON(`${API}/revendas`);

    if (!lista.length) {
      tbody.innerHTML = `<tr><td colspan="5" class="empty">Nenhuma revenda cadastrada.</td></tr>`;
      return;
    }

    tbody.innerHTML = lista.map(r => `
      <tr>
        <td><span class="cell-mono">#${r.id}</span></td>
        <td>${r.nome}</td>
        <td><a href="https://wa.me/${r.telefone.replace(/\D/g,'')}" target="_blank" style="color:var(--success)">${r.telefone}</a></td>
        <td>${formatarData(r.criado_em)}</td>
        <td style="display:flex;gap:6px">
          <button class="btn btn-icon" onclick="editarRevenda(${r.id}, '${escapar(r.nome)}', '${r.telefone}')">Editar</button>
          <button class="btn btn-icon btn-danger" onclick="deletarRevenda(${r.id}, '${escapar(r.nome)}')">✕</button>
        </td>
      </tr>
    `).join('');
  } catch {
    mostrarToast('Erro ao carregar revendas', 'error');
  }
}

function editarRevenda(id, nome, telefone) {
  document.getElementById('revendaEditId').value = id;
  document.getElementById('revendaNome').value = nome;
  document.getElementById('revendaTelefone').value = telefone;
  document.getElementById('modalRevendaTitulo').textContent = 'Editar Revenda';
  abrirModal('modalRevenda');
}

async function salvarRevenda() {
  const id = document.getElementById('revendaEditId').value;
  const nome = document.getElementById('revendaNome').value.trim();
  const telefone = document.getElementById('revendaTelefone').value.trim();

  if (!nome || !telefone) {
    mostrarToast('Preencha nome e telefone', 'error');
    return;
  }

  try {
    if (id) {
      await fetchJSON(`${API}/revendas/${id}`, {
        method: 'PUT',
        body: JSON.stringify({ nome, telefone }),
      });
      mostrarToast('Revenda atualizada!', 'success');
    } else {
      await fetchJSON(`${API}/revendas`, {
        method: 'POST',
        body: JSON.stringify({ nome, telefone }),
      });
      mostrarToast('Revenda cadastrada!', 'success');
    }
    fecharModal('modalRevenda');
    carregarRevendas();
  } catch (e) {
    mostrarToast(e.message || 'Erro ao salvar revenda', 'error');
  }
}

async function deletarRevenda(id, nome) {
  if (!confirm(`Deletar a revenda "${nome}"?`)) return;
  try {
    await fetch(`${API}/revendas/${id}`, { method: 'DELETE' });
    mostrarToast('Revenda removida.', 'success');
    carregarRevendas();
  } catch {
    mostrarToast('Erro ao deletar revenda', 'error');
  }
}

/* ── HELPERS ──────────────────────────────────────────────────────────────── */
async function fetchJSON(url, opts = {}) {
  // Aplica Content-Type JSON em qualquer requisição com body que não seja FormData
  if (opts.body && !(opts.body instanceof FormData)) {
    opts.headers = {
      'Content-Type': 'application/json',
      ...(opts.headers || {}),
    };
  }

  const resp = await fetch(url, opts);

  // DELETE retorna 204 sem body — não tenta parsear JSON
  if (resp.status === 204) return null;

  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) throw new Error(data.detail || `Erro ${resp.status}`);
  return data;
}

function formatarData(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('pt-BR', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

function escapar(str) {
  return (str || '').replace(/'/g, "\\'");
}

function abrirModal(id) {
  document.getElementById(id).classList.remove('hidden');
}

function fecharModal(id) {
  document.getElementById(id).classList.add('hidden');
}

let toastTimer;
function mostrarToast(msg, tipo = '') {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = `toast${tipo ? ' ' + tipo : ''}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.add('hidden'), 3500);
}