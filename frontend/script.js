/* ── CONFIG ───────────────────────────────────────────────────────────────── */
const API = window.location.protocol === 'file:'
  ? 'http://localhost:8000/api'
  : '/api';

const MESES = ['', 'Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun',
               'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];

/* ── STATE ────────────────────────────────────────────────────────────────── */
let currentProtocolo = null;
let filterConcluido  = 'false';
let searchDebounce   = null;
let perfil           = null; // 'analista' | 'leitura'
let charts           = {};

/* ── INIT ─────────────────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  iniciarRelogio();
  configurarEventos(); 
  document.getElementById('senhaInput').addEventListener('keydown', e => {
    if (e.key === 'Enter') fazerLogin();
  });
  document.getElementById('loginInput').addEventListener('keydown', e => {
    if (e.key === 'Enter') fazerLogin();
  });

  const sessao = sessionStorage.getItem('protocolo_sessao');
  if (sessao) {
    try {
      const u = JSON.parse(sessao);
      iniciarApp(u.login, u.perfil);
    } catch {
      sessionStorage.removeItem('protocolo_sessao');
    }
  }
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

/* ── LOGIN ────────────────────────────────────────────────────────────────── */
async function fazerLogin() {
  const login = document.getElementById('loginInput').value.trim();
  const senha = document.getElementById('senhaInput').value.trim();
  const erroEl = document.getElementById('loginErro');
  erroEl.classList.add('hidden');

  if (!login || !senha) {
    erroEl.classList.remove('hidden');
    return;
  }

  try {
    const resp = await fetch(`${API}/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ login, senha }),
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      erroEl.classList.remove('hidden');
      return;
    }
    sessionStorage.setItem('protocolo_sessao', JSON.stringify(data));
    iniciarApp(data.login, data.perfil);
  } catch {
    erroEl.classList.remove('hidden');
  }
}

function iniciarApp(login, p) {
  perfil = p;
  document.getElementById('telaLogin').classList.add('hidden');
  document.getElementById('appWrapper').classList.remove('hidden');
  document.getElementById('usuarioInfo').textContent = login + ' · ' + (p === 'analista' ? 'Analista' : 'Visualização');

  document.querySelectorAll('.nav-analista').forEach(el => {
    el.style.cssText = p === 'analista' ? 'display:flex !important' : 'display:none !important';
  });

  navegarPara('dashboard');
}

function fazerLogout() {
  sessionStorage.removeItem('protocolo_sessao');
  window.location.reload();
}

/* ── NAVEGAÇÃO ────────────────────────────────────────────────────────────── */
function navegarPara(pagina) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.getElementById(`page-${pagina}`)?.classList.add('active');
  document.querySelector(`[data-page="${pagina}"]`)?.classList.add('active');

  const titulos = { dashboard: 'Dashboard', protocolos: 'Protocolos', importar: 'Importar CSV', revendas: 'Revendas' };
  document.getElementById('topbarTitle').textContent = titulos[pagina] || pagina;

  if (pagina === 'dashboard')  carregarDashboard();
  if (pagina === 'protocolos') carregarProtocolos();
  if (pagina === 'revendas')   carregarRevendas();
}

/* ── EVENTOS ──────────────────────────────────────────────────────────────── */
function configurarEventos() {
  document.querySelectorAll('.nav-item').forEach(btn => {
    btn.addEventListener('click', () => navegarPara(btn.dataset.page));
  });

  document.querySelectorAll('.filter-tab').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.filter-tab').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      filterConcluido = btn.dataset.filter;
      carregarProtocolos();
    });
  });

  document.getElementById('searchInput').addEventListener('input', e => {
    clearTimeout(searchDebounce);
    searchDebounce = setTimeout(() => carregarProtocolos(), 350);
  });

  document.getElementById('filtroMes').addEventListener('change', () => carregarProtocolos());
  document.getElementById('filtroInicio').addEventListener('change', () => carregarProtocolos());
  document.getElementById('filtroFim').addEventListener('change', () => carregarProtocolos());

  document.getElementById('dashFiltroMes')?.addEventListener('change', () => carregarDashboard());

  let searchRevendaDebounce = null;
  document.getElementById('searchRevenda')?.addEventListener('input', e => {
    clearTimeout(searchRevendaDebounce);
    searchRevendaDebounce = setTimeout(() => carregarRevendas(e.target.value), 350);
  });

  document.getElementById('modalConcluido').addEventListener('change', function () {
    document.getElementById('toggleLabel').textContent = this.checked ? 'Concluído' : 'Pendente';
  });

  document.getElementById('modalContato').addEventListener('change', function () {
    document.getElementById('toggleContatoLabel').textContent = this.checked ? 'Sim' : 'Não';
  });

  const fileInput = document.getElementById('fileInput');
  fileInput.addEventListener('change', e => {
    if (e.target.files[0]) importarCSV(e.target.files[0]);
  });

  const importArea = document.getElementById('importArea');
  importArea.addEventListener('dragover', e => { e.preventDefault(); importArea.classList.add('drag-over'); });
  importArea.addEventListener('dragleave', () => importArea.classList.remove('drag-over'));
  importArea.addEventListener('drop', e => {
    e.preventDefault(); importArea.classList.remove('drag-over');
    const f = e.dataTransfer.files[0];
    if (f?.name.endsWith('.csv')) importarCSV(f);
    else mostrarToast('Envie um arquivo .csv', 'error');
  });

  document.getElementById('btnNovaRevenda')?.addEventListener('click', () => {
    document.getElementById('revendaEditId').value = '';
    document.getElementById('revendaNome').value = '';
    document.getElementById('revendaTelefone').value = '';
    document.getElementById('modalRevendaTitulo').textContent = 'Nova Revenda';
    abrirModal('modalRevenda');
  });

  document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', e => {
      if (e.target === overlay) overlay.classList.add('hidden');
    });
  });
}

function limparFiltrosData() {
  document.getElementById('filtroMes').value = '';
  document.getElementById('filtroInicio').value = '';
  document.getElementById('filtroFim').value = '';
  carregarProtocolos();
}

/* ── DASHBOARD ────────────────────────────────────────────────────────────── */
async function carregarDashboard() {
  try {
    const mes = document.getElementById('dashFiltroMes')?.value || '';
    const url = mes ? `${API}/stats?mes=${mes}` : `${API}/stats`;
    const stats = await fetchJSON(url);
    document.getElementById('statPendentes').textContent  = stats.pendentes;
    document.getElementById('statConcluidos').textContent = stats.concluidos;
    document.getElementById('statTotal').textContent      = stats.total_protocolos;
    document.getElementById('statRevendas').textContent   = stats.revendas_cadastradas;
    renderizarGraficos(stats);
  } catch {
    mostrarToast('Erro ao carregar dashboard', 'error');
  }
}

function renderizarGraficos(stats) {
  Chart.defaults.color = '#8896ab';
  Chart.defaults.font  = { family: 'Inter, sans-serif', size: 11 };

  Object.values(charts).forEach(c => c?.destroy());
  charts = {};

  // ── Gráfico 1: Pizza — Total / Concluídos / Pendentes ────────────────────
  const total      = stats.total_protocolos || 0;
  const concluidos = stats.concluidos || 0;
  const pendentes  = stats.pendentes  || 0;

  charts.resolvido = new Chart(document.getElementById('chartConclusao'), {
    type: 'pie',
    data: {
      labels: ['Concluídos', 'Pendentes'],
      datasets: [{
        data: [concluidos, pendentes],
        backgroundColor: ['#22c55ecc', '#ef4444cc'],
        borderColor:     ['#22c55e',   '#ef4444'],
        borderWidth: 2,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: { position: 'bottom', labels: { color: '#8896ab', padding: 10, font: { size: 11 } } },
        tooltip: {
          callbacks: {
            label: ctx => {
              const val = ctx.raw;
              const pct = total ? ((val / total) * 100).toFixed(1) : 0;
              return ` ${ctx.label}: ${val} (${pct}%)`;
            }
          }
        }
      }
    }
  });

  // ── Gráfico 2: Pendentes por Analista ────────────────────────────────────
  const pt = stats.por_analista || [];
  charts.analista = new Chart(document.getElementById('chartTecnico'), {
    type: 'bar',
    data: {
      labels: pt.map(r => r.nome || 'Sem analista'),
      datasets: [{
        label: 'Pendentes',
        data: pt.map(r => r.total),
        backgroundColor: '#3b7fff55',
        borderColor: '#3b7fff',
        borderWidth: 2,
        borderRadius: 4,
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { beginAtZero: true, grid: { color: '#1e2430' }, ticks: { precision: 0 } },
        y: { grid: { display: false } }
      }
    }
  });

  // ── Gráfico 3: Pendentes por Revenda ─────────────────────────────────────
  const pr = stats.por_revenda || [];
  charts.revenda = new Chart(document.getElementById('chartRevenda'), {
    type: 'bar',
    data: {
      labels: pr.map(r => r.nome ? (r.nome.length > 22 ? r.nome.substring(0, 22) + '…' : r.nome) : 'Sem revenda'),
      datasets: [{
        label: 'Pendentes',
        data: pr.map(r => r.total),
        backgroundColor: '#ef444455',
        borderColor: '#ef4444',
        borderWidth: 2,
        borderRadius: 4,
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { beginAtZero: true, grid: { color: '#1e2430' }, ticks: { precision: 0 } },
        y: { grid: { display: false } }
      }
    }
  });
}

/* ── PROTOCOLOS ───────────────────────────────────────────────────────────── */
async function carregarProtocolos() {
  const tbody = document.getElementById('protTableBody');
  tbody.innerHTML = `<tr><td colspan="8" class="empty">Carregando...</td></tr>`;

  try {
    const params = new URLSearchParams();
    if (filterConcluido !== '') params.set('concluido', filterConcluido);

    const busca = document.getElementById('searchInput').value;
    if (busca) params.set('busca', busca);

    const mes   = document.getElementById('filtroMes').value;
    const ini   = document.getElementById('filtroInicio').value;
    const fim   = document.getElementById('filtroFim').value;
    if (mes) params.set('mes', mes);
    if (ini) params.set('data_inicio', ini);
    if (fim) params.set('data_fim', fim);

    const lista = await fetchJSON(`${API}/protocolos?${params}`);

    if (!lista.length) {
      tbody.innerHTML = `<tr><td colspan="8" class="empty">Nenhum protocolo encontrado.</td></tr>`;
      return;
    }

    tbody.innerHTML = lista.map(p => `
      <tr>
        <td><span class="cell-mono">${p.numero_protocolo}</span></td>
        <td>${formatarData(p.datahora)}</td>
        <td title="${p.revenda || ''}">${p.revenda || '—'}</td>
        <td title="${p.tecnico_nome || p.analista || ''}">${p.tecnico_nome || p.analista || '—'}</td>
        <td title="${p.problema || ''}">${p.problema || '—'}</td>
        <td style="text-align:center">
          <span class="badge ${p.contato_realizado ? 'badge-contato' : 'badge-semcontato'}">
            ${p.contato_realizado ? 'Sim' : 'Não'}
          </span>
        </td>
        <td style="text-align:center">
          <span class="badge ${p.concluido ? 'badge-done' : 'badge-pending'}">
            ${p.concluido ? 'Concluído' : 'Pendente'}
          </span>
        </td>
        <td style="text-align:center">
          <button class="btn btn-icon" onclick="abrirProtocolo(${p.id})">Abrir →</button>
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

    document.getElementById('modalNumero').textContent      = p.numero_protocolo;
    document.getElementById('modalDatahora').textContent    = formatarData(p.datahora);
    document.getElementById('modalRevendaNome').textContent = p.revenda || '—';
    document.getElementById('modalAnalista').textContent    = p.analista || '—';
    document.getElementById('modalTecnico').textContent     = p.tecnico_nome || '—';
    document.getElementById('modalProblema').textContent    = p.problema || '—';
    document.getElementById('modalSolucao').textContent     = p.solucao || '—';
    document.getElementById('modalObs').value               = p.observacao || '';

    const chkConcluido = document.getElementById('modalConcluido');
    chkConcluido.checked = p.concluido;
    document.getElementById('toggleLabel').textContent = p.concluido ? 'Concluído' : 'Pendente';

    const chkContato = document.getElementById('modalContato');
    chkContato.checked = p.contato_realizado;
    document.getElementById('toggleContatoLabel').textContent = p.contato_realizado ? 'Sim' : 'Não';

    const soLeitura = perfil !== 'analista';
    document.getElementById('modalObs').disabled      = soLeitura;
    document.getElementById('modalConcluido').disabled = soLeitura;
    document.getElementById('modalContato').disabled   = soLeitura;
    document.querySelectorAll('.modal-analista-only').forEach(el => {
      el.style.display = soLeitura ? 'none' : '';
    });

    abrirModal('modalProtocolo');
  } catch {
    mostrarToast('Erro ao abrir protocolo', 'error');
  }
}

async function salvarProtocolo() {
  if (!currentProtocolo || perfil !== 'analista') return;
  try {
    await fetchJSON(`${API}/protocolos/${currentProtocolo.id}`, {
      method: 'PATCH',
      body: JSON.stringify({
        observacao:        document.getElementById('modalObs').value,
        concluido:         document.getElementById('modalConcluido').checked,
        contato_realizado: document.getElementById('modalContato').checked,
      }),
    });
    mostrarToast('Protocolo atualizado!', 'success');
    fecharModal('modalProtocolo');
    carregarProtocolos();
    carregarDashboard();
  } catch {
    mostrarToast('Erro ao salvar protocolo', 'error');
  }
}

async function deletarDoModal() {
  if (!currentProtocolo || perfil !== 'analista') return;
  fecharModal('modalProtocolo');
  await deletarProtocolo(currentProtocolo.id, currentProtocolo.numero_protocolo);
}

async function deletarProtocolo(id, numero) {
  if (perfil !== 'analista') return;
  if (!confirm(`Deletar o protocolo ${numero}? Esta ação não pode ser desfeita.`)) return;
  try {
    await fetchJSON(`${API}/protocolos/${id}`, { method: 'DELETE' });
    mostrarToast('Protocolo deletado.', 'success');
    carregarProtocolos();
    carregarDashboard();
  } catch {
    mostrarToast('Erro ao deletar protocolo', 'error');
  }
}

/* ── WHATSAPP ─────────────────────────────────────────────────────────────── */
function gerarMensagemWhatsApp() {
  if (!currentProtocolo) return;

  const hora = new Date().getHours();
  let saudacao;
  if (hora >= 5 && hora < 12)       saudacao = 'Bom dia';
  else if (hora >= 12 && hora < 18) saudacao = 'Boa tarde';
  else                               saudacao = 'Boa noite';

  const problema  = currentProtocolo.problema || 'chamado registrado';
  const datahora  = formatarData(currentProtocolo.datahora);
  const protocolo = currentProtocolo.numero_protocolo;

  const mensagem =
    `${saudacao}!\n\n` +
    `Referente ao protocolo *#${protocolo}* registrado em ${datahora}.\n\n` +
    `*Assunto:* ${problema}\n\n` +
    `Gostaria de verificar se o problema foi solucionado ou se ainda precisam de auxilio.`;

  const telefone   = currentProtocolo.revenda_rel?.telefone || currentProtocolo.numero_telefone || '';
  let numeroLimpo  = telefone.replace(/\D/g, '');
  if (numeroLimpo && !numeroLimpo.startsWith('55')) {
    numeroLimpo = '55' + numeroLimpo;
  }

  const textoCodificado = encodeURIComponent(mensagem);
  const urlApp = numeroLimpo
    ? `whatsapp://send?phone=${numeroLimpo}&text=${textoCodificado}`
    : `whatsapp://send?text=${textoCodificado}`;

  window.location.href = urlApp;
}

/* ── IMPORTAR CSV ─────────────────────────────────────────────────────────── */
async function importarCSV(arquivo) {
  if (perfil !== 'analista') return;
  const resultDiv = document.getElementById('importResult');
  resultDiv.classList.add('hidden');

  const formData = new FormData();
  formData.append('file', arquivo);

  try {
    mostrarToast('Importando CSV...', '');
    const resp = await fetch(`${API}/protocolos/importar`, { method: 'POST', body: formData });
    const data = await resp.json();

    if (!resp.ok) { mostrarToast(data.detail || 'Erro ao importar', 'error'); return; }

    resultDiv.classList.remove('hidden');
    resultDiv.innerHTML = `
      <div class="result-title">Importacao concluida: ${arquivo.name}</div>
      <div class="result-grid">
        <div class="result-item"><div class="result-num">${data.total_lidos}</div><div class="result-lbl">Lidos</div></div>
        <div class="result-item"><div class="result-num">${data.pendentes_encontrados}</div><div class="result-lbl">Pendentes</div></div>
        <div class="result-item"><div class="result-num">${data.novos_inseridos}</div><div class="result-lbl">Inseridos</div></div>
        <div class="result-item"><div class="result-num">${data.ja_existentes}</div><div class="result-lbl">Ja existiam</div></div>
      </div>
      ${data.erros?.length ? `<div class="result-erros">${data.erros.map(e => `<span>Aviso: ${e}</span>`).join('')}</div>` : ''}
    `;
    mostrarToast(`${data.novos_inseridos} protocolo(s) importado(s)!`, 'success');
  } catch {
    mostrarToast('Erro de conexao ao importar', 'error');
  }
}

/* ── REVENDAS ─────────────────────────────────────────────────────────────── */
async function carregarRevendas(busca = '') {
  const tbody = document.getElementById('revTableBody');
  try {
    const url = busca ? `${API}/revendas?busca=${encodeURIComponent(busca)}` : `${API}/revendas`;
    const lista = await fetchJSON(url);
    if (!lista.length) {
      tbody.innerHTML = `<tr><td colspan="6" class="empty">Nenhuma revenda encontrada.</td></tr>`;
      return;
    }
    tbody.innerHTML = lista.map(r => {
      const tel = r.telefone.replace(/\D/g, '');
      const telWpp = tel && !tel.startsWith('55') ? '55' + tel : tel;
      return `
      <tr>
        <td><span class="cell-mono">#${r.id}</span></td>
        <td>${r.nome}</td>
        <td>${r.cnpj || '—'}</td>
        <td>${r.telefone}</td>
        <td>${formatarData(r.criado_em)}</td>
        <td style="display:flex;gap:6px">
          ${telWpp ? `<a href="whatsapp://send?phone=${telWpp}" class="btn btn-icon" style="color:var(--success);border-color:#22c55e44;text-decoration:none" title="Abrir WhatsApp">📱</a>` : ''}
          <button class="btn btn-icon" onclick="editarRevenda(${r.id}, '${escapar(r.nome)}', '${escapar(r.cnpj || '')}', '${r.telefone}')">Editar</button>
          <button class="btn btn-icon btn-danger" onclick="deletarRevenda(${r.id}, '${escapar(r.nome)}')">✕</button>
        </td>
      </tr>`;
    }).join('');
  } catch {
    mostrarToast('Erro ao carregar revendas', 'error');
  }
}

function editarRevenda(id, nome, cnpj, telefone) {
  document.getElementById('revendaEditId').value   = id;
  document.getElementById('revendaNome').value     = nome;
  document.getElementById('revendaCnpj').value     = cnpj;
  document.getElementById('revendaTelefone').value = telefone;
  document.getElementById('modalRevendaTitulo').textContent = 'Editar Revenda';
  abrirModal('modalRevenda');
}

async function salvarRevenda() {
  const id       = document.getElementById('revendaEditId').value;
  const nome     = document.getElementById('revendaNome').value.trim();
  const cnpj     = document.getElementById('revendaCnpj').value.trim();
  const telefone = document.getElementById('revendaTelefone').value.trim();

  if (!nome || !telefone) { mostrarToast('Preencha nome e telefone', 'error'); return; }

  try {
    if (id) {
      await fetchJSON(`${API}/revendas/${id}`, { method: 'PUT', body: JSON.stringify({ nome, cnpj, telefone }) });
      mostrarToast('Revenda atualizada!', 'success');
    } else {
      await fetchJSON(`${API}/revendas`, { method: 'POST', body: JSON.stringify({ nome, cnpj, telefone }) });
      mostrarToast('Revenda cadastrada!', 'success');
    }
    fecharModal('modalRevenda');
    carregarRevendas(document.getElementById('searchRevenda')?.value || '');
  } catch (e) {
    mostrarToast(e.message || 'Erro ao salvar revenda', 'error');
  }
}

async function deletarRevenda(id, nome) {
  if (!confirm(`Deletar a revenda "${nome}"?`)) return;
  try {
    await fetchJSON(`${API}/revendas/${id}`, { method: 'DELETE' });
    mostrarToast('Revenda removida.', 'success');
    carregarRevendas();
  } catch {
    mostrarToast('Erro ao deletar revenda', 'error');
  }
}

/* ── HELPERS ──────────────────────────────────────────────────────────────── */
async function fetchJSON(url, opts = {}) {
  if (opts.body && !(opts.body instanceof FormData)) {
    opts.headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
  }
  const resp = await fetch(url, opts);
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

function escapar(str) { return (str || '').replace(/'/g, "\\'"); }
function abrirModal(id) { document.getElementById(id).classList.remove('hidden'); }
function fecharModal(id) { document.getElementById(id).classList.add('hidden'); }

let toastTimer;
function mostrarToast(msg, tipo = '') {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = `toast${tipo ? ' ' + tipo : ''}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.add('hidden'), 3500);
}