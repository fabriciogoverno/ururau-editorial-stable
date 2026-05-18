// V200_13: canais validos no CMS Ururau (sincronizados com
// editorial/classificador_editorial_contextual_v117.py CANAIS_VALIDOS)
const CANAIS_CMS = [
  "Política", "Estado RJ", "Cidades", "Polícia", "Economia",
  "Saúde", "Educação", "Esportes", "Tecnologia", "Rural",
  "Entretenimento", "Curiosidades", "Brasil e Mundo", "Opinião",
];

/* Ururau Editorial - frontend premium organizado em 3 colunas. */
"use strict";

const API = {
  health:    "/api/health",
  diag:      "/api/diag",
  pautas:    "/api/pautas",
  pauta:     (uid) => `/api/pautas/${encodeURIComponent(uid)}`,
  materia:   (uid) => `/api/pautas/${encodeURIComponent(uid)}/materia`,
  job:       (uid) => `/api/pautas/${encodeURIComponent(uid)}/job`,
  imagem:    (uid) => `/api/pautas/${encodeURIComponent(uid)}/imagem`,
  redigir:   (uid) => `/api/pautas/${encodeURIComponent(uid)}/redigir`,
  copydesk:  (uid) => `/api/pautas/${encodeURIComponent(uid)}/copydesk`,
  revisaoPend:    (uid) => `/api/pautas/${encodeURIComponent(uid)}/revisao-pendente`,
  salvarCopydesk: (uid) => `/api/pautas/${encodeURIComponent(uid)}/salvar-copydesk`,
  descartarCopy:  (uid) => `/api/pautas/${encodeURIComponent(uid)}/descartar-copydesk`,
  promptCopydesk: "/api/admin/prompt-copydesk",
  buscarImg: (uid) => `/api/pautas/${encodeURIComponent(uid)}/buscar-imagem`,
  descartar: (uid) => `/api/pautas/${encodeURIComponent(uid)}/descartar`,
  reativar:  (uid) => `/api/pautas/${encodeURIComponent(uid)}/reativar`,
  publicar:  (uid) => `/api/pautas/${encodeURIComponent(uid)}/publicar`,
  aprovar:   (uid) => `/api/pautas/${encodeURIComponent(uid)}/aprovar-baixo-score`,
  coletar:   "/api/coletar",
  coletaSt:  "/api/coletar/status",
  feedDisc:  "/api/feed-universal/discover",
  feedColl:  "/api/feed-universal/collect",
  srcHealth: "/api/feed-universal/source-health",
  stats:     "/api/stats",
  historico: "/api/historico",
  config:    "/api/config",
};

const MARCA_STATUS = {
  "captada":     "#64748b",  "triada":      "#38bdf8",
  "aprovada":    "#22c55e",  "em_redacao":  "#eab308",
  "revisada":    "#a78bfa",  "pronta":      "#22c55e",
  "publicada":   "#10b981",  "rejeitada":   "#ef4444",
  "reprovada":   "#ef4444",  "bloqueada":   "#ef4444",
  "baixo_score": "#f59e0b",
};

const $ = (id) => document.getElementById(id);
const escapeHtml = (s) => String(s == null ? "" : s)
  .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
  .replace(/"/g, "&quot;").replace(/'/g, "&#39;");

async function jget(url) {
  const r = await fetch(url, { headers: { Accept: "application/json" } });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.erro || `HTTP ${r.status}`);
  return j;
}
async function jpost(url, body) {
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(body || {}),
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok && r.status !== 202) throw new Error(j.erro || `HTTP ${r.status}`);
  return j;
}

let _pautasCache = [];
let _uidSelecionado = null;
let _pautaSelecionada = null;
let _iaCfg = { configurada: false, modelo: "" };
const _cacheTextoFonte = new Map(); // V200_30: cache do HTML do texto da fonte por uid
// Token de seleção: incrementa toda vez que troca a pauta. Cada fetch
// guarda o token dele e descarta a resposta se outra seleção entrou no meio.
let _selSeq = 0;

function setStatus(msg, kind) {
  $("status-line").textContent = msg;
  $("status-line").className = "msg" + (kind ? " " + kind : "");
}
function setStatusInd(id, label, kind) {
  const el = $(id);
  if (!el) return;
  el.className = `ind ${kind || ""}`;
  el.innerHTML = `<span class="dot"></span> ${escapeHtml(label)}`;
}

function pautaSel() {
  if (!_uidSelecionado) return null;
  return _pautasCache.find((p) => p.uid === _uidSelecionado) || _pautaSelecionada;
}

// ── Badges ────────────────────────────────────────────────────────────────
function badgeTxt(p) {
  const r = (p.txt_rotulo || "").toUpperCase();
  if (r === "TXT OK")    return `<span class="badge txt-ok">TXT OK · ${p.txt_chars}</span>`;
  if (r === "TXT...")    return `<span class="badge txt-pend">TXT…</span>`;
  if (r === "TXT 429")   return `<span class="badge txt-429">TXT 429</span>`;
  if (r === "TXT CURTO") return `<span class="badge txt-curto">TXT CURTO · ${p.txt_chars}</span>`;
  if (r === "BLOQUEADO") return `<span class="badge s-bloqueada">BLOQUEADO</span>`;
  if (r === "DUPLICADO") return `<span class="badge s-rejeitada">DUPLICADO</span>`;
  if (r === "PUBLICADA") return `<span class="badge s-publicada">PUBLICADA</span>`;
  // V200_14: pautas com materia gerada / revisada
  if (r === "REDIGIDA")  return `<span class="badge s-redigida" title="Materia ja foi redigida pela IA">📝 REDIGIDA</span>`;
  if (r === "REVISADA")  return `<span class="badge s-revisada" title="Materia ja foi redigida e revisada (Copydesk aplicado)">✓ REVISADA</span>`;
  return `<span class="badge txt-vazio">TXT ?</span>`;
}
function badgeStatus(s) {
  if (!s) return "";
  const cls = "s-" + String(s).toLowerCase().replace(/[^a-z_]/g, "");
  return `<span class="badge ${cls}">${escapeHtml(String(s).toUpperCase().slice(0,12))}</span>`;
}

// ── Filtros ───────────────────────────────────────────────────────────────
function aplicarFiltros(pautas) {
  const fStatus = $("sel-status").value.trim().toLowerCase();
  const fFonte  = $("sel-fonte").value.trim();
  const fCanal  = $("sel-canal").value.trim();
  const fTxt    = $("sel-txt").value.trim();
  const busca   = $("inp-busca").value.trim().toLowerCase();
  return pautas.filter((p) => {
    if (fStatus && (p.status_pauta || "").toLowerCase() !== fStatus) return false;
    if (fFonte  && (p.fonte || "") !== fFonte) return false;
    if (fCanal  && (p.canal || "") !== fCanal) return false;
    if (fTxt    && p.txt_rotulo !== fTxt) return false;
    if (busca) {
      const blob = `${p.titulo} ${p.fonte} ${p.link} ${p.canal}`.toLowerCase();
      if (!blob.includes(busca)) return false;
    }
    return true;
  });
}
function atualizarDropdowns(pautas) {
  const sf = $("sel-fonte"), sc = $("sel-canal");
  const fA = sf.value, cA = sc.value;
  const fontes = Array.from(new Set(pautas.map((p) => p.fonte).filter(Boolean))).sort();
  const canais = Array.from(new Set(pautas.map((p) => p.canal).filter(Boolean))).sort();
  sf.innerHTML = `<option value="">todas fontes</option>` + fontes.map((f) =>
    `<option value="${escapeHtml(f)}"${f===fA?" selected":""}>${escapeHtml(f)}</option>`).join("");
  sc.innerHTML = `<option value="">todos canais</option>` + canais.map((c) =>
    `<option value="${escapeHtml(c)}"${c===cA?" selected":""}>${escapeHtml(c)}</option>`).join("");
}

// ── Render FILA (cards compactos) ─────────────────────────────────────────
function renderFila(pautas) {
  const filtradas = aplicarFiltros(pautas);
  const cont = $("fila");
  cont.innerHTML = "";
  if (filtradas.length === 0) {
    const v = document.createElement("div");
    v.className = "fila-vazia";
    v.textContent = pautas.length === 0
      ? "Sem pautas. Clique em Coletar."
      : "Sem resultados.";
    cont.appendChild(v);
    $("meta-total").textContent = `0 / ${pautas.length}`;
    return;
  }
  const frag = document.createDocumentFragment();
  let loteAtual = null;
  for (const p of filtradas) {
    const lote = p.coleta_lote || "Sem lote";
    if (lote !== loteAtual) {
      loteAtual = lote;
      const lb = document.createElement("div");
      lb.className = "lote-bar";
      const qtd = filtradas.filter((x) => x.coleta_lote === lote).length;
      lb.innerHTML = `<span>${escapeHtml(lote)}</span><span class="meta">${qtd}</span>`;
      frag.appendChild(lb);
    }
    const marca = MARCA_STATUS[(p.status_pauta || "").toLowerCase()] || "#475569";
    const card = document.createElement("div");
    card.className = "card";
    if ((p.txt_rotulo || "").toUpperCase() === "BLOQUEADO") card.classList.add("bloqueado");
    // V200_14: destaque visual para materias ja redigidas/revisadas
    const _rot = (p.txt_rotulo || "").toUpperCase();
    if (_rot === "REDIGIDA")  card.classList.add("card-redigida");
    if (_rot === "REVISADA")  card.classList.add("card-revisada");
    if (_rot === "PUBLICADA") card.classList.add("card-publicada");
    if (p.uid === _uidSelecionado) card.classList.add("selecionada");
    card.dataset.uid = p.uid || "";
    card.style.setProperty("--marca", marca);
    const thumbCls = ["thumb"];
    if (p.materia_pronta) thumbCls.push("materia-pronta");
    if (p.urgente) thumbCls.push("urgente");
    if (!p.imagem_url && !p.imagem_local) thumbCls.push("fav");
    const thumbHtml = p.imagem_thumb
      ? `<div class="${thumbCls.join(" ")}"><img loading="lazy" src="${escapeHtml(p.imagem_thumb)}" alt="" onerror="this.style.display='none'"/></div>`
      : `<div class="${thumbCls.join(" ")} fav"></div>`;
    const termosBadges = (p.termos_prioridade || [])
      .slice(0, 3)
      .map((t) => `<span class="badge prioridade-termo" title="termo prioritário encontrado: ${escapeHtml(t)}">${escapeHtml(t)}</span>`)
      .join("");
    const extraTermos = (p.termos_prioridade || []).length > 3
      ? `<span class="badge prioridade-termo">+${(p.termos_prioridade || []).length - 3}</span>` : "";
    card.innerHTML = `
      <div class="marca"></div>
      ${thumbHtml}
      <div class="corpo">
        <div class="linha1">
          ${badgeTxt(p)} ${badgeStatus(p.status_pauta)} ${termosBadges}${extraTermos}
          <div class="titulo" title="${escapeHtml(p.titulo)}">${escapeHtml(p.titulo || "(sem título)")}</div>
        </div>
        <div class="linha2">
          <b>${escapeHtml(p.fonte || "-")}</b> · ${escapeHtml(p.data || "-")} ${p.canal ? "· " + escapeHtml(p.canal) : ""}
        </div>
      </div>
    `;
    frag.appendChild(card);
  }
  cont.appendChild(frag);
  $("meta-total").textContent = `${filtradas.length} / ${pautas.length}`;
}

// ── CENTRO: render do perfil da pauta ─────────────────────────────────────
function renderCentro(p) {
  if (!p) {
    $("centro-titulo").textContent = "Nenhuma pauta selecionada";
    $("centro-acoes").innerHTML = "";
    $("painel-perfil").innerHTML = `
      <div class="empty-state">
        <div class="icon"><svg width="28" height="28"><use href="#ic-doc"/></svg></div>
        <h3>Selecione uma pauta na fila</h3>
        <p>O perfil editorial, o texto da fonte e a matéria gerada aparecem aqui.</p>
      </div>`;
    $("painel-fonte").textContent = "Selecione uma pauta para ver o texto da fonte.";
    $("painel-materia").innerHTML = `<p class="muted">Selecione uma pauta com matéria gerada.</p>`;
    $("painel-diag").textContent = "--";
    atualizarToolbar();
    return;
  }
  $("centro-titulo").textContent = p.titulo || "(sem título)";
  $("centro-acoes").innerHTML = `
    ${p.link ? `<button class="btn mini sec" data-act="abrir" data-link="${escapeHtml(p.link)}">Abrir fonte</button>` : ""}
    <button class="btn mini imagem" data-act="buscar-imagem" data-uid="${escapeHtml(p.uid)}">Imagem</button>
    ${(p.status_pauta || "").toLowerCase() === "baixo_score" ? `<button class="btn mini aprovar" data-act="aprovar" data-uid="${escapeHtml(p.uid)}">Aprovar</button>` : ""}
    ${["rejeitada","bloqueada","reprovada","excluida","descartada"].includes((p.status_pauta || "").toLowerCase()) ? `<button class="btn mini aprovar" data-act="reativar" data-uid="${escapeHtml(p.uid)}">Reativar</button>` : ""}
  `;

  const score = Math.max(0, Math.min(100, p.score || 0));
  const risco = Math.max(0, Math.min(100, p.score_risco || 0));
  const scoreColor = score >= 80 ? "verde" : score >= 50 ? "amarelo" : "vermelho";
  const riscoColor = risco >= 70 ? "vermelho" : risco >= 30 ? "amarelo" : "verde";
  const chips = [];
  if (p.canal) chips.push(`<span class="chip canal">${escapeHtml(p.canal)}</span>`);
  if (p.urgente) chips.push(`<span class="chip risco">URGENTE</span>`);
  if (p.materia_pronta) chips.push(`<span class="chip materia">MATÉRIA PRONTA</span>`);
  if (p.score >= 80) chips.push(`<span class="chip prio">PRIORIDADE</span>`);

  const thumbBlock = p.imagem_thumb
    ? `<div class="perfil-thumb"><img src="${escapeHtml(p.imagem_thumb)}" alt="" onerror="this.parentNode.style.display='none'"/></div>`
    : "";

  $("painel-perfil").innerHTML = `
    <div class="perfil-grid">
      ${thumbBlock}
      <div class="perfil-info">
        <div class="titulo-grande">${escapeHtml(p.titulo || "")}</div>
        ${p.resumo ? `<div class="subtitle">${escapeHtml(p.resumo)}</div>` : ""}
        <div class="chip-row">
          ${badgeTxt(p)} ${badgeStatus(p.status_pauta)} ${chips.join("")}
        </div>
      </div>
    </div>
    <div class="kv-grid">
      <div class="k">Fonte</div><div class="v">${p.link ? `<a href="${escapeHtml(p.link)}" target="_blank" rel="noreferrer noopener">${escapeHtml(p.fonte || "-")}</a>` : escapeHtml(p.fonte || "-")}</div>
      <div class="k">Data publicação</div><div class="v">${escapeHtml(p.data || "-")}</div>
      <div class="k">Método de coleta</div><div class="v">${escapeHtml(p.metodo || "-")}</div>
      <div class="k">Lote</div><div class="v">${escapeHtml(p.coleta_lote || "-")}</div>
      <div class="k">UID</div><div class="v" style="font-family:monospace; font-size:11px;">${escapeHtml(p.uid || "-")}</div>
    </div>
    <div style="margin-top:14px;">
      <div class="barra-header"><span>Score editorial</span><span><b>${score}</b>/100</span></div>
      <div class="barra-prog"><div class="fill ${scoreColor}" style="width:${score}%"></div></div>
      <div class="barra-header"><span>Score de risco</span><span><b>${risco}</b>/100</span></div>
      <div class="barra-prog"><div class="fill ${riscoColor}" style="width:${risco}%"></div></div>
      <div class="barra-header"><span>Texto fonte</span><span><b>${p.txt_chars || 0}</b> chars</span></div>
      <div class="barra-prog"><div class="fill ${p.txt_chars >= 550 ? "verde" : "amarelo"}" style="width:${Math.min(100, (p.txt_chars || 0) / 30)}%"></div></div>
    </div>
    <div id="job-info" class="mono small" style="margin-top:10px;">aguardando comando...</div>
  `;
  atualizarToolbar();
  atualizarJobInfo();
  // As abas são carregadas sob demanda (no clique). Evita race condition
  // ao navegar rápido pela fila com setas.
}

function quebrarParagrafos(texto) {
  // 1) Se já vem com \n\n, respeita.
  let t = String(texto || "").replace(/\r\n/g, "\n").trim();
  let paragrafos = t.split(/\n{2,}/).map((s) => s.trim()).filter(Boolean);
  if (paragrafos.length >= 2) return paragrafos;
  // 2) Se vem com \n simples, tenta cada linha como parágrafo (filtra lixo).
  paragrafos = t.split(/\n/).map((s) => s.trim()).filter((s) => s.length >= 30);
  if (paragrafos.length >= 3) return paragrafos;
  // 3) Texto monolítico: quebra por sentenças e agrupa em parágrafos de 2-3.
  // Regex: final de frase ([.!?]) seguido por espaço e letra maiuscula.
  const sentencas = t
    .replace(/\s+/g, " ")
    .split(/(?<=[.!?])\s+(?=[A-ZÀ-Ú])/g)
    .map((s) => s.trim())
    .filter(Boolean);
  if (sentencas.length <= 1) return [t];
  // Junta a cada 3 sentenças por parágrafo (tamanho confortável de leitura).
  const blocos = [];
  for (let i = 0; i < sentencas.length; i += 3) {
    blocos.push(sentencas.slice(i, i + 3).join(" "));
  }
  return blocos;
}

function limparBoilerplate(texto) {
  // Remove ruido frequente nos sites (legendas, navegação, etc).
  let t = String(texto || "");
  // Sequencias repetidas tipo "Trocar imagem Trocar imagem ... Créditos: ..."
  t = t.replace(/(Trocar imagem\s*){2,}/gi, " ");
  // Caracteres invisíveis e espacos múltiplos
  t = t.replace(/ /g, " ").replace(/[ \t]+/g, " ").replace(/[ \t]+\n/g, "\n");
  return t.trim();
}

async function carregarTabFonte(p) {
  if (!p) return;
  const meuSeq = _selSeq;
  // V200_30: cache - se ja carregou esse uid antes, mostra direto
  // sem skeleton nem fetch. Texto da fonte nao muda entre cliques.
  if (_cacheTextoFonte.has(p.uid)) {
    $("painel-fonte").innerHTML = _cacheTextoFonte.get(p.uid);
    return;
  }
  // Thumb da matéria no topo da aba.
  const thumbHtml = p.imagem_thumb
    ? `<div class="tf-thumb"><img src="${escapeHtml(p.imagem_thumb)}" alt="" onerror="this.parentNode.style.display='none'"/></div>`
    : "";
  // V200_28: skeleton IMEDIATO antes do fetch.
  // O fetch /api/pautas/{uid} pode demorar 5-30s porque dispara hidratacao
  // on-demand (pipeline_v90 -> leitura_fonte -> trafilatura -> Jina). Sem
  // este placeholder, o painel ficava com texto da pauta ANTERIOR durante
  // todo esse tempo, dando impressao de que o sistema travou.
  const skelMeta = `<div class="tf-meta" style="opacity:0.7;">
    <b>${escapeHtml(p.fonte || "-")}</b> · ${escapeHtml(p.data || "-")} ${p.canal ? "· " + escapeHtml(p.canal) : ""}
    ${p.txt_chars ? ` · ${p.txt_chars} caracteres` : ""}
  </div>`;
  $("painel-fonte").innerHTML = `
    ${thumbHtml}
    <h1 class="tf-titulo">${escapeHtml(p.titulo || "")}</h1>
    ${skelMeta}
    <div class="tf-corpo" style="margin-top:14px;">
      <div style="display:flex; align-items:center; gap:10px; padding:14px;
                  background:rgba(124,58,237,0.08); border:1px solid var(--border-2);
                  border-radius:8px; color:var(--text-soft); font-size:13px;">
        <span class="spinner" style="border-color:rgba(255,255,255,0.25); border-top-color:var(--acento-2);"></span>
        <span>Carregando texto da fonte...</span>
      </div>
      <div style="margin-top:14px; display:flex; flex-direction:column; gap:10px;">
        <div style="height:14px; background:rgba(255,255,255,0.05); border-radius:4px; width:100%;"></div>
        <div style="height:14px; background:rgba(255,255,255,0.05); border-radius:4px; width:96%;"></div>
        <div style="height:14px; background:rgba(255,255,255,0.05); border-radius:4px; width:88%;"></div>
        <div style="height:14px; background:rgba(255,255,255,0.05); border-radius:4px; width:92%;"></div>
        <div style="height:14px; background:rgba(255,255,255,0.05); border-radius:4px; width:75%;"></div>
      </div>
    </div>
  `;
  try {
    const j = await jget(API.pauta(p.uid));
    if (meuSeq !== _selSeq) return;  // descartado: outra pauta foi selecionada
    // V200_15: se backend acabou de hidratar on-demand, recarrega a fila
    // pra o badge mudar de TXT... para TXT OK na mesma hora (sem esperar
    // o auto-refresh de 5s).
    if (j.pauta?._hidratado_agora) {
      setTimeout(() => carregarFila(), 100);
    }
    const tf = limparBoilerplate((j.pauta?.texto_fonte || "").trim());
    const origemTf = j.pauta?.texto_fonte_origem || "vazio";
    const tipoFalha = j.pauta?.tipo_falha_extracao || "";
    const motivoFalha = j.pauta?.motivo_falha_extracao || "";
    const fonteHtml = p.link
      ? `<a href="${escapeHtml(p.link)}" target="_blank" rel="noreferrer noopener">${escapeHtml(p.fonte || "-")}</a>`
      : escapeHtml(p.fonte || "-");
    const metaHtml = `
      <div class="tf-meta">
        ${fonteHtml} · ${escapeHtml(p.data || "-")}
        ${p.canal ? ` · ${escapeHtml(p.canal)}` : ""}
        ${p.txt_chars ? ` · ${p.txt_chars} caracteres` : ""}
      </div>`;
    // v1.15.4: helper de erro REAL — mostra a causa concreta, nunca esconde.
    const ICONES = {
      materia_removida: "🔗",
      bloqueio_anti_bot: "🚫",
      exige_login: "🔒",
      paywall: "💳",
      timeout: "⏱",
      spa_js_rendered: "⚙",
      indisponivel: "⚠",
    };
    const LABELS = {
      materia_removida: "MATÉRIA REMOVIDA",
      bloqueio_anti_bot: "SITE BLOQUEIA BOTS (HTTP 403)",
      exige_login: "EXIGE LOGIN",
      paywall: "PAYWALL",
      timeout: "TIMEOUT",
      spa_js_rendered: "SITE RENDERIZADO POR JAVASCRIPT",
      indisponivel: "CONTEÚDO INDISPONÍVEL",
    };
    const linkBtn = p.link
      ? `<p style="margin-top:14px;"><a href="${escapeHtml(p.link)}" target="_blank" rel="noreferrer noopener" style="display:inline-block;padding:8px 14px;text-decoration:none;border:1px solid var(--accent);border-radius:6px;color:var(--accent);">Abrir matéria original →</a></p>`
      : "";
    if (!tf) {
      const icone = ICONES[tipoFalha] || "⚠";
      const label = LABELS[tipoFalha] || "EXTRAÇÃO FALHOU";
      const motivo = motivoFalha || "Causa não identificada.";
      $("painel-fonte").innerHTML = `
        ${thumbHtml}
        <h1 class="tf-titulo">${escapeHtml(p.titulo || "")}</h1>
        ${metaHtml}
        <div class="tf-corpo">
          <div style="background:#4a1f1f;border:1px solid #883333;padding:14px 18px;border-radius:8px;margin:12px 0;">
            <div style="font-size:13px;color:#ff9b9b;font-weight:600;letter-spacing:0.5px;">${icone} ${escapeHtml(label)}</div>
            <p style="margin:8px 0 0 0;color:#ddd;font-size:14px;">${escapeHtml(motivo)}</p>
            ${linkBtn}
          </div>
        </div>`;
      // V200_30: salva no cache mesmo em caso de falha (nao re-buscar)
      try { _cacheTextoFonte.set(p.uid, $("painel-fonte").innerHTML); } catch (e) {}
      return;
    }
    const paragrafos = quebrarParagrafos(tf)
      .map((s) => `<p>${escapeHtml(s)}</p>`)
      .join("");
    // v1.15.4: badge HONESTO quando texto veio do resumo RSS (não da hidratação)
    let avisoOrigem = "";
    if (origemTf === "rss_resumo") {
      const motivoExtra = motivoFalha ? `<br><span style="font-size:11px;opacity:0.85;">${escapeHtml(motivoFalha)}</span>` : "";
      avisoOrigem = `<div style="background:#3a2f0a;border:1px solid #8a7530;padding:10px 14px;border-radius:6px;margin:10px 0;font-size:12px;color:#ffd97a;">
        ⚠ Apenas resumo do RSS disponível — hidratação completa do site falhou.${motivoExtra}
        ${linkBtn}
      </div>`;
    }
    $("painel-fonte").innerHTML = `
      ${thumbHtml}
      <h1 class="tf-titulo">${escapeHtml(p.titulo || "")}</h1>
      ${metaHtml}
      ${avisoOrigem}
      <div class="tf-corpo">${paragrafos}</div>`;
    // V200_30: salva no cache para nao re-buscar
    try { _cacheTextoFonte.set(p.uid, $("painel-fonte").innerHTML); } catch (e) {}
  } catch (e) { $("painel-fonte").textContent = `erro: ${e.message}`; }
}
async function carregarTabMateria(p) {
  if (!p) return;
  const meuSeq = _selSeq;
  try {
    const j = await jget(API.materia(p.uid));
    if (meuSeq !== _selSeq) return;
    const md = j.materia || {};
    const corpo = md.conteudo || md.corpo_materia || "";
    const titulo = md.titulo || p.titulo || "";
    const subtitulo = md.subtitulo || "";
    const legenda = md.legenda || "";
    const tags = md.tags || "";
    const meta_desc = md.meta_description || "";
    const canal = md.canal || p.canal || "";
    if (!corpo && !titulo) {
      $("painel-materia").innerHTML = `<p class="muted">Sem matéria gerada. Selecione uma pauta e clique <b>Redigir</b> na toolbar.</p>`;
      return;
    }
    // V200_11: form editavel com botoes Salvar / Publicar inline
    $("painel-materia").innerHTML = `
      <div class="materia-edit" style="display:flex; flex-direction:column; gap:10px;">
        <div>
          <label class="label" style="display:block; margin-bottom:3px;">Título</label>
          <input id="mat-titulo" type="text" value="${escapeHtmlAttr(titulo)}"
                 style="width:100%; background:#0d1024; color:var(--text); border:1px solid var(--border-2); border-radius:6px; padding:8px; font-size:13.5px; font-weight:600;">
        </div>
        <div style="display:flex; gap:10px;">
          <div style="flex:1;">
            <label class="label" style="display:block; margin-bottom:3px;">Categoria / Canal</label>
            <select id="mat-canal"
                    style="width:100%; background:#0d1024; color:var(--text); border:1px solid var(--border-2); border-radius:6px; padding:8px; font-size:13px;">
              <option value="">(selecione...)</option>
              ${CANAIS_CMS.map(c => `<option value="${escapeHtmlAttr(c)}"${c === canal ? " selected" : ""}>${escapeHtml(c)}</option>`).join("")}
            </select>
          </div>
          <div style="flex:2;">
            <label class="label" style="display:block; margin-bottom:3px;">Subtítulo</label>
            <input id="mat-subtitulo" type="text" value="${escapeHtmlAttr(subtitulo)}"
                   style="width:100%; background:#0d1024; color:var(--text); border:1px solid var(--border-2); border-radius:6px; padding:8px; font-size:13px;">
          </div>
        </div>
        <div>
          <label class="label" style="display:block; margin-bottom:3px;">Corpo da matéria</label>
          <textarea id="mat-corpo" rows="14"
                    style="width:100%; background:#0d1024; color:var(--text); border:1px solid var(--border-2); border-radius:6px; padding:10px; font-size:13px; font-family:inherit; line-height:1.55; resize:vertical;">${escapeHtml(corpo)}</textarea>
        </div>
        <div style="display:flex; gap:10px;">
          <div style="flex:1;">
            <label class="label" style="display:block; margin-bottom:3px;">Legenda da foto</label>
            <input id="mat-legenda" type="text" value="${escapeHtmlAttr(legenda)}"
                   style="width:100%; background:#0d1024; color:var(--text); border:1px solid var(--border-2); border-radius:6px; padding:8px; font-size:13px;">
          </div>
          <div style="flex:1;">
            <label class="label" style="display:block; margin-bottom:3px;">Tags</label>
            <input id="mat-tags" type="text" value="${escapeHtmlAttr(tags)}"
                   style="width:100%; background:#0d1024; color:var(--text); border:1px solid var(--border-2); border-radius:6px; padding:8px; font-size:13px;">
          </div>
        </div>
        <div>
          <label class="label" style="display:block; margin-bottom:3px;">Meta description (SEO)</label>
          <textarea id="mat-meta" rows="2"
                    style="width:100%; background:#0d1024; color:var(--text); border:1px solid var(--border-2); border-radius:6px; padding:8px; font-size:12.5px; font-family:inherit; resize:vertical;">${escapeHtml(meta_desc)}</textarea>
        </div>
        <div style="display:flex; gap:8px; justify-content:space-between; align-items:center; margin-top:6px; padding-top:10px; border-top:1px solid var(--border);">
          <span id="mat-status" class="muted small">Edite os campos acima e clique em Salvar.</span>
          <div style="display:flex; gap:8px;">
            <button id="mat-salvar" class="btn primary" title="Salva alteracoes (sem publicar)">✓ Salvar alterações</button>
            <button id="mat-pub-rascunho" class="btn copydesk" title="Salva no CMS como rascunho (nao publica)">📝 Publicar como rascunho</button>
            <button id="mat-pub-ao-vivo" class="btn publicar" title="Publica AO VIVO no CMS (irreversivel)">🚀 Publicar ao vivo</button>
          </div>
        </div>
      </div>
    `;
    // V200_19: handlers dos botoes inline com validacao + feedback claro
    $("mat-salvar") && ($("mat-salvar").onclick = () => salvarMateriaEditada(false));
    $("mat-pub-rascunho") && ($("mat-pub-rascunho").onclick = async () => {
      const corpoEl = $("mat-corpo");
      if (!corpoEl || !corpoEl.value.trim()) {
        setStatus("Materia sem corpo. Clique em Redigir antes de publicar.", "err");
        if ($("mat-status")) $("mat-status").innerHTML = `<span class="err">corpo vazio - clique Redigir antes</span>`;
        return;
      }
      $("mat-pub-rascunho").disabled = true;
      try {
        const ok = await salvarMateriaEditada(true);
        if (ok) await _publicarFinal(true);
      } catch (e) {
        setStatus("Erro ao publicar rascunho: " + e.message, "err");
      } finally {
        $("mat-pub-rascunho").disabled = false;
      }
    });
    $("mat-pub-ao-vivo") && ($("mat-pub-ao-vivo").onclick = async () => {
      const corpoEl = $("mat-corpo");
      if (!corpoEl || !corpoEl.value.trim()) {
        setStatus("Materia sem corpo. Clique em Redigir antes de publicar.", "err");
        if ($("mat-status")) $("mat-status").innerHTML = `<span class="err">corpo vazio - clique Redigir antes</span>`;
        return;
      }
      if (!confirm("Publicar AO VIVO no CMS?\n\nEssa acao e irreversivel. A materia fica publica imediatamente.")) return;
      $("mat-pub-ao-vivo").disabled = true;
      try {
        const ok = await salvarMateriaEditada(true);
        if (ok) await _publicarFinal(false);
      } catch (e) {
        setStatus("Erro ao publicar ao vivo: " + e.message, "err");
      } finally {
        $("mat-pub-ao-vivo").disabled = false;
      }
    });
  } catch (e) { $("painel-materia").textContent = `erro: ${e.message}`; }
}

function escapeHtmlAttr(s) {
  return String(s || "").replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

async function salvarMateriaEditada(silent) {
  const p = pautaSel();
  if (!p) { setStatus("Selecione uma pauta.", "err"); return false; }
  const body = {
    titulo: $("mat-titulo") ? $("mat-titulo").value : "",
    canal: $("mat-canal") ? $("mat-canal").value : "",
    subtitulo: $("mat-subtitulo") ? $("mat-subtitulo").value : "",
    conteudo: $("mat-corpo") ? $("mat-corpo").value : "",
    legenda: $("mat-legenda") ? $("mat-legenda").value : "",
    tags: $("mat-tags") ? $("mat-tags").value : "",
    meta_description: $("mat-meta") ? $("mat-meta").value : "",
  };
  try {
    const r = await jpost("/api/pautas/" + p.uid + "/materia/salvar", body);
    if (!silent) {
      setStatus("Matéria salva. " + (r.editado_em || ""), "ok");
      if ($("mat-status")) $("mat-status").innerHTML = `<span class="ok">✓ salvo às ${(r.editado_em || "").slice(11,19)}</span>`;
    }
    // refresh fila para refletir mudanca de titulo/canal
    carregarFila();
    return true;
  } catch (e) {
    setStatus("Erro ao salvar: " + e.message, "err");
    if ($("mat-status")) $("mat-status").innerHTML = `<span class="err">erro: ${e.message}</span>`;
    return false;
  }
}
// (aba "Detalhes" com JSON cru removida a pedido — JSON disponível no Diag do Config)

// Cache do prompt padrão SEO Google (carregado uma vez do backend).
let _promptCopydeskPadrao = "";
let _promptCarregado = false;

async function carregarPromptPadrao() {
  if (_promptCarregado) return _promptCopydeskPadrao;
  try {
    const j = await jget(API.promptCopydesk);
    _promptCopydeskPadrao = (j && j.prompt) || "";
  } catch {
    _promptCopydeskPadrao = "";
  }
  _promptCarregado = true;
  return _promptCopydeskPadrao;
}

function _renderRevisaoBloco(rev, problemas, criada_em) {
  const corpo = rev.corpo_materia || "";
  const probTxt = (problemas && problemas.length)
    ? `<b>${problemas.length} aviso(s) residual(is):</b> ${problemas.map(escapeHtml).join(" · ")}`
    : `<span class="ok">✓ sem avisos residuais</span>`;
  const tsTxt = criada_em ? ` · gerada às ${escapeHtml(criada_em.slice(11,19))}` : "";
  $("cd-checagem").innerHTML = probTxt + tsTxt;
  $("cd-revisao").innerHTML = `
    <div class="titulo-mat">${escapeHtml(rev.titulo_seo || "")}</div>
    ${rev.titulo_capa ? `<div class="label">Título capa</div><p>${escapeHtml(rev.titulo_capa)}</p>` : ""}
    ${rev.subtitulo_curto ? `<div class="sub-mat">${escapeHtml(rev.subtitulo_curto)}</div>` : ""}
    ${rev.retranca ? `<div class="label">Retranca</div><p>${escapeHtml(rev.retranca)}</p>` : ""}
    ${rev.legenda_curta ? `<div class="label">Legenda</div><p>${escapeHtml(rev.legenda_curta)}</p>` : ""}
    <div class="label">Corpo revisado</div>
    <div>${escapeHtml(corpo).replace(/\n/g, "<br/>")}</div>
    ${rev.tags ? `<div class="label">Tags</div><p>${escapeHtml(rev.tags)}</p>` : ""}
    ${rev.meta_description ? `<div class="label">Meta description</div><p>${escapeHtml(rev.meta_description)}</p>` : ""}
    ${rev.slug ? `<div class="label">Slug</div><p>${escapeHtml(rev.slug)}</p>` : ""}
    ${rev.alt_imagem ? `<div class="label">ALT imagem</div><p>${escapeHtml(rev.alt_imagem)}</p>` : ""}`;
  $("cd-bloco-revisao").style.display = "block";
}

function _ocultarBlocoRevisao() {
  $("cd-bloco-revisao").style.display = "none";
  $("cd-revisao").innerHTML = "";
  $("cd-checagem").innerHTML = "";
}

async function carregarTabCopydesk(p) {
  if (!p) return;
  const meuSeq = _selSeq;
  $("cd-modelo").textContent = _iaCfg.modelo || "GPT";
  $("cd-status").textContent = "--";
  $("cd-preview").innerHTML = `<p class="muted">carregando matéria atual...</p>`;
  _ocultarBlocoRevisao();

  // Pré-carrega o prompt padrão SEO Google no textarea (apenas se estiver vazio).
  const ta = $("cd-orientacao");
  if (ta && !ta.value.trim()) {
    const padrao = await carregarPromptPadrao();
    if (meuSeq !== _selSeq) return;
    if (padrao && !ta.value.trim()) ta.value = padrao;
  }

  try {
    const j = await jget(API.materia(p.uid));
    if (meuSeq !== _selSeq) return;
    const md = j.materia || {};
    const corpo = md.conteudo || md.corpo_materia || "";
    if (!corpo) {
      $("cd-preview").innerHTML = `<p class="muted">Sem matéria gerada. Selecione uma pauta e clique <b>Redigir</b> na toolbar antes de usar o Copydesk.</p>`;
      $("cd-aplicar").disabled = true;
      $("cd-aplicar-sem").disabled = true;
      return;
    }
    $("cd-aplicar").disabled = !_iaCfg.configurada;
    $("cd-aplicar-sem").disabled = !_iaCfg.configurada;
    $("cd-preview").innerHTML = `
      <div class="titulo-mat">${escapeHtml(md.titulo || p.titulo || "")}</div>
      ${md.subtitulo ? `<div class="sub-mat">${escapeHtml(md.subtitulo)}</div>` : ""}
      <div>${escapeHtml(corpo).replace(/\n/g, "<br/>")}</div>`;

    // Verifica se existe revisão pendente do Copydesk para esta pauta.
    try {
      const rj = await jget(API.revisaoPend(p.uid));
      if (meuSeq !== _selSeq) return;
      if (rj && rj.pendente && rj.revisao) {
        _renderRevisaoBloco(rj.revisao, rj.problemas || [], rj.criada_em || "");
      }
    } catch {}
  } catch (e) {
    $("cd-preview").innerHTML = `<p class="err">erro: ${e.message}</p>`;
  }
}

async function aplicarCopydesk(comOrientacao) {
  const p = pautaSel();
  if (!p) { setStatus("Selecione uma pauta.", "err"); return; }
  if (!p.materia_pronta) { setStatus("Use Redigir antes do Copydesk.", "err"); return; }
  const orientacao = comOrientacao ? ($("cd-orientacao").value || "").trim() : "";
  if (comOrientacao && !orientacao) {
    setStatus("Digite ou restaure as instruções para o GPT.", "err"); return;
  }
  if (!confirm(`Gerar revisão via Copydesk?\n\n"${p.titulo}"\n\nA matéria atual NÃO será alterada — apenas uma revisão de pré-visualização será gerada. Você confirma a aplicação clicando em Salvar alterações.`)) return;
  $("cd-status").innerHTML = `<span class="ok">disparando revisão...</span>`;
  $("cd-aplicar").disabled = true;
  $("cd-aplicar-sem").disabled = true;
  _ocultarBlocoRevisao();
  try {
    // aplicar:false -> backend gera a revisão e armazena como pendente
    await jpost(API.copydesk(p.uid), { aplicar: false, orientacao });
    $("cd-status").innerHTML = `<span class="ok">processando · aguarde alguns segundos.</span>`;
    setStatus("Copydesk gerando revisão (background).", "ok");
    atualizarJobInfo();
    const recarregar = async () => {
      try {
        const j = await jget(API.job(p.uid));
        const slot = j.jobs?.ultimo_job;
        if (slot && slot.tipo === "copydesk" && !slot.em_andamento) {
          if (slot.status === "ok") {
            $("cd-status").innerHTML = `<span class="ok">✓ revisão pronta · revise e clique em <b>Salvar alterações</b> abaixo.</span>`;
            // Busca a revisão pendente e exibe.
            try {
              const rj = await jget(API.revisaoPend(p.uid));
              if (rj && rj.pendente && rj.revisao) {
                _renderRevisaoBloco(rj.revisao, rj.problemas || [], rj.criada_em || "");
              }
            } catch {}
          } else {
            $("cd-status").innerHTML = `<span class="err">✗ ${escapeHtml(slot.mensagem || slot.status)}</span>`;
          }
          $("cd-aplicar").disabled = false;
          $("cd-aplicar-sem").disabled = false;
          return;
        }
      } catch {}
      setTimeout(recarregar, 1500);
    };
    setTimeout(recarregar, 1500);
  } catch (e) {
    $("cd-status").innerHTML = `<span class="err">erro: ${e.message}</span>`;
    $("cd-aplicar").disabled = false;
    $("cd-aplicar-sem").disabled = false;
  }
}

async function salvarCopydesk() {
  const p = pautaSel();
  if (!p) { setStatus("Selecione uma pauta.", "err"); return; }
  if (!confirm(`Aplicar a revisão do Copydesk sobre a matéria gerada?\n\n"${p.titulo}"\n\nA matéria atual será substituída pela versão revisada.`)) return;
  $("cd-salvar").disabled = true;
  $("cd-descartar-rev").disabled = true;
  try {
    const r = await jpost(API.salvarCopydesk(p.uid), {});
    setStatus(`✓ Revisão aplicada (${r.aplicado_em || "agora"})`, "ok");
    $("cd-status").innerHTML = `<span class="ok">✓ revisão aplicada e salva na matéria</span>`;
    _ocultarBlocoRevisao();
    await carregarTabCopydesk(p);
    // V200_11: aplica automatico na aba Materia gerada tambem
    await carregarTabMateria(p);
    await carregarFila();
  } catch (e) {
    setStatus(`Erro ao salvar: ${e.message}`, "err");
  } finally {
    $("cd-salvar").disabled = false;
    $("cd-descartar-rev").disabled = false;
  }
}


// V200_13: edicao manual do corpo no Copydesk
function entrarEdicaoCopydesk() {
  const preview = $("cd-preview");
  const editor = $("cd-editor-texto");
  if (!preview || !editor) return;
  // Pega o texto plano da preview (sem HTML)
  const tmp = document.createElement("div");
  tmp.innerHTML = preview.innerHTML.replace(/<br\s*\/?>(\s*)/gi, "\n");
  const texto = tmp.textContent || tmp.innerText || "";
  editor.value = texto.trim();
  preview.style.display = "none";
  editor.style.display = "block";
  $("cd-editar-texto").style.display = "none";
  $("cd-salvar-texto").style.display = "inline-flex";
  $("cd-cancelar-texto").style.display = "inline-flex";
  editor.focus();
}

function cancelarEdicaoCopydesk() {
  $("cd-preview").style.display = "block";
  $("cd-editor-texto").style.display = "none";
  $("cd-editar-texto").style.display = "inline-flex";
  $("cd-salvar-texto").style.display = "none";
  $("cd-cancelar-texto").style.display = "none";
}

async function salvarEdicaoCopydesk() {
  const p = pautaSel();
  if (!p) { setStatus("Selecione uma pauta.", "err"); return; }
  const novoTexto = ($("cd-editor-texto").value || "").trim();
  if (!novoTexto) { setStatus("Texto vazio - nao salvou.", "err"); return; }
  if (!confirm("Salvar este texto editado como a materia atual?\nA versao anterior sera substituida.")) return;
  try {
    const r = await jpost("/api/pautas/" + p.uid + "/materia/salvar", {
      conteudo: novoTexto,
    });
    setStatus("Texto salvo. Aplicado tambem na Materia gerada.", "ok");
    if ($("cd-status")) $("cd-status").innerHTML = `<span class="ok">✓ texto editado salvo`+ (r.editado_em ? ` (${r.editado_em.slice(11,19)})` : "") +`</span>`;
    cancelarEdicaoCopydesk();
    // Recarrega ambas as abas para refletir
    await carregarTabCopydesk(p);
    await carregarTabMateria(p);
    await carregarFila();
  } catch (e) {
    setStatus("Erro ao salvar texto editado: " + e.message, "err");
  }
}

async function descartarCopydeskRev() {
  const p = pautaSel();
  if (!p) return;
  if (!confirm("Descartar esta revisão e manter a matéria atual?")) return;
  try {
    await jpost(API.descartarCopy(p.uid), {});
    _ocultarBlocoRevisao();
    $("cd-status").innerHTML = `<span class="muted">revisão descartada · matéria atual mantida.</span>`;
    setStatus("Revisão descartada.", "ok");
  } catch (e) {
    setStatus(`Erro: ${e.message}`, "err");
  }
}

async function atualizarJobInfo() {
  if (!_uidSelecionado) return;
  try {
    const j = await jget(API.job(_uidSelecionado));
    const slot = (j.jobs && j.jobs.ultimo_job) || null;
    const div = $("job-info");
    if (!div) return;
    if (!slot) { div.style.display = "none"; return; }
    // Formato amigável em vez de JSON cru.
    const tipoLabel = {
      redigir: "Redigir IA",
      copydesk: "Copydesk",
      buscar_imagem: "Buscar imagem",
      publicar: "Publicar CMS",
    }[slot.tipo] || slot.tipo;
    const statusBadge = slot.em_andamento
      ? `<span class="badge txt-pend">⏳ ${escapeHtml(slot.status || "rodando")}</span>`
      : slot.status === "ok"
      ? `<span class="badge txt-ok">✓ concluído</span>`
      : slot.status === "rascunho_local"
      ? `<span class="badge s-em_redacao">rascunho local</span>`
      : slot.status === "vazio"
      ? `<span class="badge s-captada">sem resultado</span>`
      : `<span class="badge txt-vazio">✗ ${escapeHtml(slot.status || "erro")}</span>`;
    const fim = slot.finalizado_em ? slot.finalizado_em.slice(11, 19) : "—";
    const inicio = slot.iniciado_em ? slot.iniciado_em.slice(11, 19) : "—";
    div.style.display = "block";
    div.style.fontFamily = "inherit";
    div.style.fontSize = "11.5px";
    div.style.background = "rgba(124,58,237,0.06)";
    div.style.border = "1px solid var(--border-2)";
    div.style.borderRadius = "6px";
    div.style.padding = "8px 10px";
    div.style.whiteSpace = "normal";
    div.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:center; gap:8px; margin-bottom:4px;">
        <span style="font-weight:600; color:var(--text);">${escapeHtml(tipoLabel)}</span>
        ${statusBadge}
      </div>
      <div class="muted" style="font-size:10.5px;">
        ${escapeHtml(slot.mensagem || "")}
      </div>
      <div class="muted" style="font-size:10px; margin-top:3px;">
        início ${inicio} · fim ${fim}
      </div>
    `;
    document.querySelectorAll(".card.tem-job").forEach((c) => c.classList.remove("tem-job"));
    if (slot.em_andamento) {
      const card = document.querySelector(`.card[data-uid="${_uidSelecionado}"]`);
      if (card) card.classList.add("tem-job");
      setTimeout(atualizarJobInfo, 1500);
    } else if (["ok", "rascunho_local"].includes(slot.status)) {
      await carregarFila();
      const p = pautaSel(); if (p) renderCentro(p);
    }
  } catch {}
}

// ── Toolbar enable/disable ────────────────────────────────────────────────
function atualizarToolbar() {
  const p = pautaSel();
  const tem = !!p;
  const md  = !!(p && p.materia_pronta);
  const bloq = !!(p && ["publicada","publicado","bloqueada","bloqueado","rejeitada","rejeitado","reprovada","reprovado","excluida","excluido"].includes((p.status_pauta||"").toLowerCase()));
  const podeRedigir = tem && _iaCfg.configurada && !["publicada","publicado"].includes((p?.status_pauta||"").toLowerCase());
  $("btn-redigir").disabled   = !podeRedigir;
  $("btn-copydesk").disabled  = !(tem && md && _iaCfg.configurada);
  $("btn-preview").disabled   = !(tem && md);
  $("btn-publicar").disabled  = !(tem && md && !bloq);
  $("btn-descartar").disabled = !tem;
}

// ── Carregamento ─────────────────────────────────────────────────────────
async function carregarFila() {
  setStatus("Carregando fila...");
  const limite = Number($("inp-limite").value || 240) || 240;
  const incluir = $("chk-incluir-baixo").checked ? 1 : 0;
  try {
    const j = await jget(`${API.pautas}?limite=${limite}&incluir_baixo_score=${incluir}`);
    _pautasCache = j.pautas || [];
    atualizarDropdowns(_pautasCache);
    renderFila(_pautasCache);
    setStatus(`${_pautasCache.length} pauta(s) carregada(s).`, "ok");
    if (_uidSelecionado) {
      const p = _pautasCache.find((x) => x.uid === _uidSelecionado);
      _pautaSelecionada = p || _pautaSelecionada;
      renderCentro(p || null);
      if (!p) _uidSelecionado = null;
    }
    atualizarToolbar();
  } catch (e) {
    setStatus(`Falha ao carregar fila: ${e.message}`, "err");
  }
}

async function carregarStats() {
  try {
    const j = await jget(API.stats);
    $("stats-ts").textContent = (j.data_hoje ? `dia ${j.data_hoje.split("-").reverse().join("/")} · ` : "")
      + new Date().toLocaleTimeString("pt-BR");
    const h = j.hoje || {};
    $("stats-totais").innerHTML = `
      <div class="stats-secao">
        <div class="stats-secao-titulo">Hoje · zera à meia-noite (Brasília)</div>
        <div class="stats-row-4">
          <div class="stat-card-mini hoje"><div class="num acento">${h.captadas || 0}</div><div class="label">Captadas</div></div>
          <div class="stat-card-mini hoje"><div class="num">${h.redigidas || 0}</div><div class="label">Redigidas</div></div>
          <div class="stat-card-mini hoje"><div class="num">${h.publicadas || 0}</div><div class="label">Publicadas</div></div>
          <div class="stat-card-mini hoje"><div class="num">${h.descartadas || 0}</div><div class="label">Descartadas</div></div>
        </div>
      </div>
      <div class="stats-secao">
        <div class="stats-secao-titulo">Acumulado total</div>
        <div class="stats-row-4">
          <div class="stat-card-mini"><div class="num">${j.totais?.pautas || 0}</div><div class="label">Pautas</div></div>
          <div class="stat-card-mini"><div class="num">${j.totais?.publicacoes || 0}</div><div class="label">Publicações</div></div>
          <div class="stat-card-mini"><div class="num">${(j.por_fonte || []).length}</div><div class="label">Fontes</div></div>
          <div class="stat-card-mini"><div class="num">${Object.keys(j.por_status || {}).length}</div><div class="label">Status</div></div>
        </div>
      </div>
    `;
    // Ordem solicitada: Top fontes → Canal → Status.
    const maxF = Math.max(1, ...(j.por_fonte || []).map((x) => x.qtd));
    $("stats-por-fonte").innerHTML = (j.por_fonte || []).slice(0, 8).map((x) => `
      <div class="stat-row">
        <span class="label" title="${escapeHtml(x.fonte)}">${escapeHtml(x.fonte)}</span>
        <div class="bar"><div class="fill" style="width:${(x.qtd / maxF) * 100}%"></div></div>
        <span class="qtd">${x.qtd}</span>
      </div>`).join("");
    const maxC = Math.max(1, ...(j.por_canal || []).map((x) => x.qtd));
    $("stats-por-canal").innerHTML = (j.por_canal || []).slice(0, 8).map((x) => `
      <div class="stat-row">
        <span class="label" title="${escapeHtml(x.canal)}">${escapeHtml(x.canal)}</span>
        <div class="bar"><div class="fill" style="width:${(x.qtd / maxC) * 100}%"></div></div>
        <span class="qtd">${x.qtd}</span>
      </div>`).join("");
    const totalP = j.totais?.pautas || 1;
    $("stats-por-status").innerHTML = Object.entries(j.por_status || {}).map(([k, v]) => `
      <div class="stat-row">
        <span class="label">${badgeStatus(k)}</span>
        <div class="bar"><div class="fill" style="width:${(v / totalP) * 100}%"></div></div>
        <span class="qtd">${v}</span>
      </div>`).join("");
  } catch (e) {
    $("stats-totais").innerHTML = `<p class="err">${e.message}</p>`;
  }
}

// ── Coleta ────────────────────────────────────────────────────────────────
async function dispararColeta() {
  setStatus("Disparando coleta...");
  $("btn-coletar").disabled = true;
  try {
    await jpost(API.coletar, {});
    setStatus("Coleta iniciada em background.", "ok");
    monitorarColeta();
  } catch (e) {
    setStatus(`Falha ao iniciar coleta: ${e.message}`, "err");
  } finally {
    $("btn-coletar").disabled = false;
  }
}
async function monitorarColeta() {
  for (let i = 0; i < 600; i++) {
    try {
      const j = await jget(API.coletaSt);
      const e = j.estado || {};
      atualizarIndColeta(e);
      if (!e.em_andamento) {
        await carregarFila();
        await carregarStats();
        // Resumo claro ao final
        const partes = [
          e.ultimo_lote || "Coleta",
          e.duracao_seg ? `${e.duracao_seg}s` : null,
          `${e.novas || 0} nova(s)`,
          `${e.duplicadas || 0} duplicada(s)`,
          `${e.captadas_brutas || 0} brutas`,
        ].filter(Boolean);
        const msg = partes.join(" · ");
        if (e.ultimo_erro) {
          setStatus(`Coleta falhou: ${e.ultimo_erro}`, "err");
        } else if ((e.novas || 0) > 0) {
          setStatus(`✓ ${msg}`, "ok");
        } else {
          setStatus(`Coleta concluida — ${msg}. Tente Manual ou amplie janela.`, "ok");
        }
        return;
      }
    } catch (err) {
      setStatus(`coleta: erro ${err.message}`, "err");
    }
    await new Promise((r) => setTimeout(r, 2000));
  }
}

async function atualizarAutoColeta() {
  const el = $("auto-coleta-info");
  if (!el) return;
  try {
    const j = await jget("/api/auto-coleta/status");
    const ac = (j && j.auto_coleta) || {};
    if (!ac.ativada) {
      el.textContent = "auto: desligada";
      el.title = "Auto-coleta desativada via URURAU_WEB_AUTO_COLETA=0";
      el.style.color = "#94a3b8";
      el.style.background = "rgba(148,163,184,0.05)";
      return;
    }
    const seg = ac.segundos_para_proxima;
    let restante = "--";
    if (seg !== null && seg !== undefined) {
      if (seg < 60) restante = `${seg}s`;
      else if (seg < 3600) restante = `${Math.floor(seg/60)}m${seg%60>0?` ${seg%60}s`:""}`;
      else restante = `${Math.floor(seg/3600)}h${Math.floor((seg%3600)/60)}m`;
    }
    const ultima = ac.ultima_iso ? ac.ultima_iso.slice(11,19) : "--";
    el.innerHTML = `⏱ auto · próxima em <b>${restante}</b> · última ${ultima} · #${ac.execucoes||0}`;
    el.title = `Auto-coleta a cada ${ac.intervalo_min||30} min · próxima: ${ac.proxima_iso||"--"}`;
    el.style.color = "#86efac";
    el.style.background = "rgba(34,197,94,0.06)";
  } catch {
    el.textContent = "auto · sem resposta";
    el.style.color = "#fca5a5";
  }
}

let _ultimoFinalizadoColeta = null; // null = nao inicializado ainda
let _ultimoEmAndamentoColeta = false;

function atualizarIndColeta(e) {
  // Reflete o estado da coleta apenas na status bar do rodapé, com pill animada.
  const ind = $("status-coleta");
  if (!ind) return;
  if (e.em_andamento) {
    ind.className = "ind busy";
    ind.innerHTML = `<span class="dot"></span> coletando: ${e.captadas_brutas || 0} captadas · ${e.inseridas || 0} salvas`;
  } else if (e.ultimo_erro) {
    ind.className = "ind alerta";
    ind.innerHTML = `<span class="dot"></span> coleta: erro`;
    ind.title = e.ultimo_erro;
  } else if (e.finalizado_em) {
    ind.className = "ind ok";
    ind.innerHTML = `<span class="dot"></span> coleta: ${e.ultimo_resumo || 'concluída'}`;
  } else {
    ind.className = "ind";
    ind.innerHTML = `<span class="dot"></span> coleta: ociosa`;
  }

  // ── Detector de transição: quando coleta termina, recarrega fila + stats.
  // Funciona em DOIS cenarios:
  //  (a) em_andamento mudou de true para false (coleta que comecou e terminou
  //      durante a sessao atual da pagina), e
  //  (b) finalizado_em mudou de valor (cobre coletas auto que rodam em background).
  // IMPORTANTE: o primeiro poll NAO dispara reload (so inicializa o baseline)
  // para nao recarregar fila duas vezes ao abrir a pagina.
  const fimNovo = e.finalizado_em || "";
  if (_ultimoFinalizadoColeta === null) {
    // Primeiro poll: apenas inicializa baseline sem disparar reload.
    _ultimoFinalizadoColeta = fimNovo;
    _ultimoEmAndamentoColeta = !!e.em_andamento;
    return;
  }
  const transitouParaFim = (_ultimoEmAndamentoColeta && !e.em_andamento)
    || (fimNovo && fimNovo !== _ultimoFinalizadoColeta && !e.em_andamento);
  if (transitouParaFim) {
    console.log("[coleta] termino detectado, recarregando fila em 1s...", e.ultimo_resumo);
    // Delay para garantir que a thread de coleta gravou no banco.
    setTimeout(() => {
      try { carregarFila(); } catch {}
      try { carregarStats(); } catch {}
    }, 1000);
    if (e.ultimo_resumo) {
      setStatus(`✓ Coleta: ${e.ultimo_resumo}`, "ok");
    }
  }
  _ultimoFinalizadoColeta = fimNovo;
  _ultimoEmAndamentoColeta = !!e.em_andamento;
}

// ── Ações editoriais ─────────────────────────────────────────────────────
async function acaoRedigir() {
  const p = pautaSel();
  if (!p) return;
  if (!_iaCfg.configurada) {
    setStatus("OPENAI_API_KEY ausente OU lib openai não instalada. Abra Config > Diagnóstico.", "err");
    return;
  }
  if (!confirm(`Redigir matéria via IA (${_iaCfg.modelo})?\n\n"${p.titulo}"`)) return;
  const btn = $("btn-redigir");
  const orig = btn.innerHTML;
  btn.classList.add("loading");
  btn.innerHTML = `<span class="spinner"></span> Redigindo...`;
  btn.disabled = true;
  // V200_22: barra animada + polling do job + toast no fim
  const tituloCurto = (p.titulo || "(sem titulo)").slice(0, 60);
  iniciarProgressoAcao(`Redigindo: "${tituloCurto}..."`, 22000);
  try {
    await jpost(API.redigir(p.uid), { forcar: false });
    const card = document.querySelector(`.card[data-uid="${p.uid}"]`);
    if (card) card.classList.add("tem-job");
    atualizarJobInfo();
    // Polling do job a cada 1s ate concluir (max 90s)
    aguardarJobConcluir(p.uid, "redigir", 90000)
      .then((slot) => {
        if (slot && slot.status === "ok") {
          concluirProgressoAcao(true, `✓ Matéria redigida em ${Math.round((slot.duracao_seg || 0))}s`);
          mostrarToast({
            tipo: "success",
            titulo: "📝 Matéria redigida",
            corpo: `"${tituloCurto}"<br><span style="color:var(--muted)">${escapeHtml(p.fonte || "")} · ${escapeHtml(p.canal || "")}</span>`,
            acao: { label: "Abrir matéria", onclick: () => { _uidSelecionado = p.uid; selecionarTab("materia"); carregarTabMateria(p); } },
            timeoutMs: 8000,
          });
          carregarFila();
          carregarTabMateria(p);
        } else {
          const msg = (slot && (slot.mensagem || slot.status)) || "Falha desconhecida";
          concluirProgressoAcao(false, `✗ Falha: ${msg}`);
          mostrarToast({ tipo: "error", titulo: "✗ Redigir falhou", corpo: escapeHtml(msg), timeoutMs: 10000 });
        }
      })
      .catch((e) => {
        concluirProgressoAcao(false, `✗ Timeout: ${e.message}`);
        mostrarToast({ tipo: "error", titulo: "✗ Redigir timeout", corpo: escapeHtml(e.message), timeoutMs: 8000 });
      });
  } catch (e) {
    concluirProgressoAcao(false, `✗ HTTP: ${e.message}`);
    setStatus(`Falha redigir: ${e.message}`, "err");
  } finally {
    setTimeout(() => { btn.innerHTML = orig; btn.classList.remove("loading"); atualizarToolbar(); }, 1500);
  }
}

// ─────────────────── V200_22: Barra de progresso da acao ──────────────────
let _progressoTimer = null;
let _progressoFimEstimado = 0;
function iniciarProgressoAcao(texto, duracaoMs) {
  const bar = $("progresso-acao");
  const fill = $("progresso-acao-fill");
  const txt = $("progresso-acao-texto");
  if (!bar || !fill || !txt) return;
  if (_progressoTimer) clearInterval(_progressoTimer);
  bar.style.display = "flex";
  fill.classList.remove("ok", "err");
  fill.style.width = "0%";
  txt.textContent = texto || "Processando...";
  const inicio = Date.now();
  _progressoFimEstimado = inicio + (duracaoMs || 20000);
  // anima ate 85% suavemente
  _progressoTimer = setInterval(() => {
    const passado = Date.now() - inicio;
    const total = (_progressoFimEstimado - inicio);
    let pct = Math.min(85, (passado / total) * 85);
    // easing cubic-out
    pct = 85 * (1 - Math.pow(1 - (pct / 85), 3));
    fill.style.width = pct.toFixed(1) + "%";
    if (pct >= 84.9) { clearInterval(_progressoTimer); _progressoTimer = null; }
  }, 200);
}
function concluirProgressoAcao(sucesso, texto) {
  const bar = $("progresso-acao");
  const fill = $("progresso-acao-fill");
  const txt = $("progresso-acao-texto");
  if (!bar || !fill || !txt) return;
  if (_progressoTimer) { clearInterval(_progressoTimer); _progressoTimer = null; }
  fill.classList.remove("ok", "err");
  fill.classList.add(sucesso ? "ok" : "err");
  fill.style.width = "100%";
  txt.textContent = texto || (sucesso ? "Concluído" : "Falhou");
  setTimeout(() => { bar.style.display = "none"; fill.style.width = "0%"; }, sucesso ? 2500 : 5000);
}

async function aguardarJobConcluir(uid, tipo, timeoutMs) {
  const inicio = Date.now();
  while (Date.now() - inicio < (timeoutMs || 60000)) {
    await new Promise((r) => setTimeout(r, 1000));
    try {
      const j = await jget(API.job(uid));
      const slot = j.jobs?.ultimo_job;
      if (slot && (slot.tipo === tipo || tipo === "*") && !slot.em_andamento) {
        return slot;
      }
    } catch (e) {
      // ignora erros de polling pontuais
    }
  }
  throw new Error(`timeout aguardando job ${tipo}`);
}

// ─────────────────── V200_22: Toasts ──────────────────────────────────────
function mostrarToast({ tipo = "info", titulo, corpo, acao, timeoutMs = 6000 }) {
  const cont = $("toast-container");
  if (!cont) return;
  const toast = document.createElement("div");
  toast.className = `toast toast-${tipo}`;
  const acaoBtn = acao ? `<div class="toast-action" data-act="run">${escapeHtml(acao.label || "Abrir")}</div>` : "";
  toast.innerHTML = `
    <div class="toast-head">
      <span>${titulo || ""}</span>
      <button class="toast-close" title="Fechar">×</button>
    </div>
    <div class="toast-body">${corpo || ""}</div>
    ${acaoBtn}
  `;
  cont.appendChild(toast);
  const fechar = () => {
    toast.classList.add("toast-fade-out");
    setTimeout(() => toast.remove(), 400);
  };
  toast.querySelector(".toast-close").onclick = fechar;
  if (acao && typeof acao.onclick === "function") {
    const ab = toast.querySelector(".toast-action");
    if (ab) ab.onclick = () => { try { acao.onclick(); } catch (e) {} fechar(); };
  }
  setTimeout(fechar, timeoutMs);
}
function acaoCopydesk() {
  // Botão da toolbar agora abre a aba "Copydesk" para o editor
  // escrever orientações antes de rodar o GPT.
  const p = pautaSel();
  if (!p) return;
  if (!p.materia_pronta) { setStatus("Use Redigir antes de Copydesk.", "err"); return; }
  selecionarTab("copydesk");
  carregarTabCopydesk(p);
  // Foco no textarea para já começar a digitar.
  setTimeout(() => { const ta = $("cd-orientacao"); if (ta) ta.focus(); }, 100);
}
function acaoPreview() {
  const p = pautaSel();
  if (!p) return;
  selecionarTab("materia");
}
async function acaoDescartar() {
  const p = pautaSel();
  if (!p) return;
  const motivo = prompt(`Descartar pauta:\n"${p.titulo}"\n\nMotivo (opcional):`, "");
  if (motivo === null) return;
  try {
    await jpost(API.descartar(p.uid), { motivo });
    setStatus("Pauta descartada.", "ok");
    _uidSelecionado = null;
    await carregarFila();
    renderCentro(null);
  } catch (e) { setStatus(`Falha descartar: ${e.message}`, "err"); }
}
function acaoPublicar() {
  const p = pautaSel();
  if (!p || !p.materia_pronta) { setStatus("Use Redigir antes de Publicar.", "err"); return; }
  $("pub-titulo").textContent = p.titulo || "(sem título)";
  $("modal-publicar").hidden = false;
}
async function _publicarFinal(rascunho) {
  const p = pautaSel();
  if (!p) return;
  if (!rascunho && !confirm("Confirma publicar AO VIVO no CMS? Não dá para desfazer.")) return;
  $("modal-publicar").hidden = true;
  const tipoLabel = rascunho ? "rascunho" : "ao vivo";
  try {
    await jpost(API.publicar(p.uid), { confirm: true, rascunho });
    setStatus(`Enviando ${tipoLabel} ao CMS...`, "ok");
    atualizarJobInfo();
    // V200_20: polling explicito do job ate concluir (max 60s). Antes o
    // status ficava em "Enviando..." pra sempre e o usuario nao via se
    // deu certo ou se algum erro ocorreu no Playwright/CMS.
    const inicio = Date.now();
    const uid = p.uid;
    const poll = setInterval(async () => {
      if (Date.now() - inicio > 60000) {
        clearInterval(poll);
        setStatus(`Publicar ${tipoLabel}: timeout (60s). Veja console do PowerShell.`, "err");
        return;
      }
      try {
        const j = await jget(API.job(uid));
        const slot = j.jobs?.ultimo_job;
        if (slot && slot.tipo === "publicar" && !slot.em_andamento) {
          clearInterval(poll);
          atualizarJobInfo();
          if (slot.status === "ok") {
            setStatus(`✓ ${tipoLabel} enviado: ${slot.mensagem || "CMS confirmou"}`, "ok");
            carregarFila();
          } else {
            setStatus(`✗ Publicar ${tipoLabel} FALHOU: ${slot.mensagem || slot.status}`, "err");
            console.error("Publicar falhou:", slot);
          }
        }
      } catch (e) {
        // erro de polling - continua tentando ate timeout
        console.warn("polling job falhou:", e.message);
      }
    }, 1000);
  } catch (e) {
    setStatus(`Falha publicar (HTTP): ${e.message}`, "err");
    console.error("publicar HTTP error:", e);
  }
}
async function acaoBuscarImagem(uid) {
  uid = uid || (pautaSel() || {}).uid;
  if (!uid) return;
  if (!confirm("Refazer busca de imagem para esta pauta?")) return;
  setStatus("Buscando imagem...");
  try {
    await jpost(API.buscarImg(uid), {});
    atualizarJobInfo();
  } catch (e) { setStatus(`Falha imagem: ${e.message}`, "err"); }
}
async function acaoAprovar(uid) {
  uid = uid || (pautaSel() || {}).uid;
  if (!uid) return;
  try {
    await jpost(API.aprovar(uid), {});
    setStatus("Aprovada baixo_score.", "ok");
    await carregarFila();
  } catch (e) { setStatus(`Falha aprovar: ${e.message}`, "err"); }
}
async function acaoReativar(uid) {
  uid = uid || (pautaSel() || {}).uid;
  if (!uid) return;
  try {
    await jpost(API.reativar(uid), { status: "captada" });
    setStatus("Pauta reativada.", "ok");
    await carregarFila();
  } catch (e) { setStatus(`Falha reativar: ${e.message}`, "err"); }
}
async function acaoExportar() {
  const p = pautaSel();
  if (!p) { setStatus("Selecione uma pauta primeiro.", "err"); return; }
  try {
    const j = await jget(API.materia(p.uid));
    const blob = new Blob([JSON.stringify({ pauta: p, materia: j.materia || {} }, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `pauta_${p.uid}.json`; a.click();
    URL.revokeObjectURL(url);
    setStatus("Exportado JSON.", "ok");
  } catch (e) { setStatus(`Falha exportar: ${e.message}`, "err"); }
}

function selecionarTab(name) {
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
  document.querySelectorAll(".tab-content").forEach((t) => t.classList.toggle("active", t.id === "tab-" + name));
}

// ── Feed Universal ────────────────────────────────────────────────────────
async function feedAnalisar() {
  const url = ($("feed-url").value || "").trim();
  if (!url) { setStatus("Informe URL.", "err"); return; }
  setStatus("Analisando...");
  try {
    const j = await jpost(API.feedDisc, { url, mode: "auto", limit: 30 });
    $("feed-saida").textContent = JSON.stringify(j.resultado || j, null, 2);
    setStatus("Diagnóstico Feed Universal concluído.", "ok");
  } catch (e) { setStatus(`Falha: ${e.message}`, "err"); }
}
async function feedColetar() {
  const url = ($("feed-url").value || "").trim();
  if (!url) { setStatus("Informe URL.", "err"); return; }
  const limit = Number($("feed-limit").value || 20);
  const last_hours = Number($("feed-janela").value || 24);
  setStatus("Coletando via Feed Universal...");
  try {
    const j = await jpost(API.feedColl, { url, limit, last_hours });
    const r = j.resultado || {};
    $("feed-saida").textContent = JSON.stringify({
      url: r.url, inseridos: r.inseridos,
      duplicados: (r.duplicados || []).length,
      bloqueados: (r.bloqueados || []).length,
      sem_publicacao: r.sem_publicacao,
    }, null, 2);
    setStatus(`Feed Universal: ${r.inseridos || 0} item(ns) inserido(s).`, "ok");
    await carregarFila();
    await carregarStats();
  } catch (e) { setStatus(`Falha: ${e.message}`, "err"); }
}

async function carregarHealth() { /* painel removido */ }

// ── Config modal ─────────────────────────────────────────────────────────
async function abrirConfig(tab) {
  try {
    const c = await jget(API.config);
    const h = await jget(API.health);
    $("cfg-login").value       = "fabricio.freitas";
    $("cfg-assinatura").value  = "Fabrício Freitas";
    $("cfg-modelo").value      = c.ia_modelo || "";
    $("cfg-key").value          = c.ia_configurada ? "definida (mascarada)" : "ausente";
    $("cfg-lib").value          = h.ia_configurada ? "instalada" : "AUSENTE - executar 03_ABRIR_WEB_LOCALHOST.bat para instalar";
    $("cfg-limite-visual").value = c.runtime?.limite_visual ?? 240;
    $("cfg-janela").value        = c.runtime?.janela_padrao_horas ?? 24;
    $("cfg-db").value            = c.arquivo_db || "";
    $("cfg-cors").value          = (c.cors_origens_permitidas || []).join(", ");
    $("cfg-host").value          = `${c.host}:${c.port}`;
    $("modal-config").hidden = false;
    if (tab) selecionarMTab(tab);
    if (tab === "diag" || !tab) carregarDiag();
    if (tab === "hist") carregarHistorico();
    atualizarCorteInfo();
  } catch (e) { setStatus(`Falha config: ${e.message}`, "err"); }
}
function selecionarMTab(name) {
  document.querySelectorAll(".modal-tab").forEach((t) => t.classList.toggle("active", t.dataset.mtab === name));
  document.querySelectorAll(".modal-tab-content").forEach((t) => t.classList.toggle("active", t.id === "mtab-" + name));
  if (name === "diag") carregarDiag();
  if (name === "hist") carregarHistorico();
  if (name === "termos") carregarTermos();
  if (name === "fontes") carregarFontes();
}

// ── Termos editoriais (chips individuais) ───────────────────────────────
let _termosCache = {};  // { grupo_nome: [termo1, termo2, ...] }

function renderTermos() {
  const cont = $("termos-grupos");
  if (!cont) return;
  const grupos = Object.entries(_termosCache);
  if (grupos.length === 0) {
    cont.innerHTML = `<p class="muted small">Nenhum grupo. Clique "+ Novo grupo" para começar.</p>`;
    return;
  }
  cont.innerHTML = grupos.map(([nome, lista]) => `
    <div class="termos-grupo" data-grupo="${escapeHtml(nome)}">
      <div class="termos-grupo-head">
        <input class="nome" data-act="rename" value="${escapeHtml(nome)}" />
        <span class="qtd">${(lista || []).length}</span>
        <button class="btn-rm-grupo" data-act="rm-grupo">remover grupo</button>
      </div>
      <div class="termos-chips">
        ${(lista || []).map((t, i) => `
          <span class="termo-chip">
            ${escapeHtml(t)}
            <button data-act="rm-termo" data-idx="${i}" title="remover">×</button>
          </span>
        `).join("")}
        <span class="termo-add">
          <input type="text" data-act="add-input" placeholder="+ adicionar termo" />
        </span>
      </div>
    </div>
  `).join("");
}

async function carregarTermos() {
  try {
    const j = await jget("/api/admin/termos");
    _termosCache = { ...(j.grupos || {}) };
    renderTermos();
    const total = Object.values(_termosCache).reduce((a, b) => a + (b?.length || 0), 0);
    $("termos-status").innerHTML = `Arquivo: <code>${escapeHtml(j.arquivo)}</code> · ${Object.keys(_termosCache).length} grupos · ${total} termos`;
  } catch (e) {
    $("termos-status").innerHTML = `<span class="err">erro: ${e.message}</span>`;
  }
}

async function salvarTermos() {
  try {
    const j = await jpost("/api/admin/termos", { grupos: _termosCache });
    $("termos-status").innerHTML = `<span class="ok">Salvo · ${j.grupos} grupo(s) · ${j.total_termos} termo(s)</span>`;
    setStatus("Termos editoriais salvos.", "ok");
  } catch (e) {
    $("termos-status").innerHTML = `<span class="err">erro: ${e.message}</span>`;
  }
}

function novoGrupoTermos() {
  const nome = prompt("Nome do novo grupo (ex: cidades_rj, esportes_rj):", "");
  if (!nome) return;
  const limpo = String(nome).trim().toLowerCase().replace(/\s+/g, "_").replace(/[^a-z0-9_]/g, "");
  if (!limpo) { setStatus("Nome inválido.", "err"); return; }
  if (_termosCache[limpo]) { setStatus("Já existe um grupo com esse nome.", "err"); return; }
  _termosCache[limpo] = [];
  renderTermos();
}

// ── Fontes RSS ──────────────────────────────────────────────────────────
let _fontesCache = [];
function renderFontes() {
  const cont = $("fontes-list");
  if (!cont) return;
  const rows = _fontesCache.map((f, idx) => `
    <div class="fonte-row" data-idx="${idx}" style="display:grid; grid-template-columns: 28px 1.4fr 2fr 1fr 50px 36px; gap:6px; align-items:center; padding:6px 4px; border-bottom:1px solid var(--border);">
      <input type="checkbox" data-k="ativo" ${f.ativo ? "checked" : ""} title="ativo" />
      <input type="text" data-k="nome" value="${escapeHtml(f.nome || "")}" placeholder="nome" />
      <input type="url"  data-k="url"  value="${escapeHtml(f.url || "")}"  placeholder="https://..." />
      <input type="text" data-k="canal_forcado" value="${escapeHtml(f.canal_forcado || "")}" placeholder="canal (opcional)" />
      <input type="number" data-k="max_por_link" value="${f.max_por_link || 5}" min="1" max="50" title="max por link" />
      <button class="btn ghost mini" data-act="rm" title="remover">×</button>
    </div>
  `).join("");
  cont.innerHTML = `
    <div style="display:grid; grid-template-columns: 28px 1.4fr 2fr 1fr 50px 36px; gap:6px; padding:4px; font-size:10px; color:var(--text-soft); text-transform:uppercase; letter-spacing:0.4px; border-bottom:1px solid var(--border);">
      <span>on</span><span>Nome</span><span>URL</span><span>Canal</span><span>max</span><span></span>
    </div>
    ${rows}`;
  cont.querySelectorAll(".fonte-row input").forEach((el) => {
    el.addEventListener("change", (e) => {
      const row = e.target.closest(".fonte-row");
      const idx = Number(row.dataset.idx);
      const k = e.target.dataset.k;
      const v = (e.target.type === "checkbox") ? e.target.checked
               : (e.target.type === "number") ? Number(e.target.value || 0)
               : e.target.value;
      _fontesCache[idx] = { ..._fontesCache[idx], [k]: v };
    });
  });
  cont.querySelectorAll("[data-act='rm']").forEach((b) => {
    b.addEventListener("click", (e) => {
      const idx = Number(e.target.closest(".fonte-row").dataset.idx);
      _fontesCache.splice(idx, 1);
      renderFontes();
    });
  });
}
async function carregarFontes() {
  try {
    const j = await jget("/api/admin/fontes-rss");
    _fontesCache = j.fontes || [];
    renderFontes();
    const ativas = _fontesCache.filter((x) => x.ativo).length;
    $("fontes-status").innerHTML = `Arquivo: <code>${escapeHtml(j.arquivo)}</code> · ${_fontesCache.length} fonte(s) · ${ativas} ativa(s)`;
  } catch (e) {
    $("fontes-status").innerHTML = `<span class="err">erro: ${e.message}</span>`;
  }
}
async function salvarFontes() {
  try {
    const j = await jpost("/api/admin/fontes-rss", { fontes: _fontesCache });
    $("fontes-status").innerHTML = `<span class="ok">Salvo · ${j.total} fontes · ${j.ativas} ativa(s)</span>`;
    setStatus("Fontes salvas.", "ok");
  } catch (e) {
    $("fontes-status").innerHTML = `<span class="err">erro: ${e.message}</span>`;
  }
}
function adicionarFonte() {
  _fontesCache.unshift({
    nome: "", url: "", canal_forcado: "",
    ativo: true, tipo_coleta: "rss",
    max_por_link: 5, ordem: 0,
  });
  renderFontes();
}
async function salvarConfig() {
  try {
    await jpost(API.config, {
      limite_visual: Number($("cfg-limite-visual").value || 240),
      janela_padrao_horas: Number($("cfg-janela").value || 24),
    });
    setStatus("Configuração salva (runtime).", "ok");
    $("modal-config").hidden = true;
  } catch (e) { setStatus(`Falha salvar: ${e.message}`, "err"); }
}

async function carregarDiag() {
  $("diag-corpo").textContent = "carregando...";
  try {
    const j = await jget(API.diag);
    const linhas = [
      `=== SERVIDOR ===`,
      `Hora: ${j.ts}`,
      `Diretório (cwd): ${j.caminhos?.cwd || "-"}`,
      `Sistema: ${j.caminhos?.sistema || "-"}`,
      ``,
      `=== IA (OpenAI) ===`,
      `Modelo: ${j.ia?.modelo || "-"}`,
      `Client criado: ${j.ia?.client_criado ? "SIM" : "NÃO"}`,
      `Biblioteca openai: ${j.ia?.lib_instalada === true ? `instalada (v${j.ia?.lib_versao})` : (j.ia?.lib_instalada === false ? "AUSENTE - rode: pip install openai" : "desconhecido")}`,
      `Chave (origem): ${j.ia?.key_origem}`,
      `Chave (mascarada): ${j.ia?.key_mascarada}`,
      j.ia?.ultimo_erro ? `Último erro IA: ${j.ia.ultimo_erro}` : ``,
      ``,
      `=== CMS ===`,
      `URURAU_LOGIN: ${j.cms?.login}`,
      `URURAU_SENHA: ${j.cms?.senha_presente ? "definida (oculta)" : "AUSENTE"}`,
      `URURAU_ASSINATURA: ${j.cms?.assinatura}`,
      ``,
      `=== BANCO ===`,
      `ARQUIVO_DB: ${j.arquivo_db || "-"}`,
      ``,
      `=== BIBLIOTECAS PYTHON ===`,
      ...Object.entries(j.bibliotecas || {}).map(([k, v]) => `${k}: ${v}`),
    ].filter(Boolean).join("\n");
    $("diag-corpo").textContent = linhas;
  } catch (e) { $("diag-corpo").textContent = `erro: ${e.message}`; }
}

async function carregarHistorico() {
  const f = $("hist-status").value;
  $("hist-corpo").innerHTML = "carregando...";
  try {
    const j = await jget(`${API.historico}?limite=200${f ? `&status=${encodeURIComponent(f)}` : ""}`);
    const rows = (j.pautas || []).map((p) => `
      <tr>
        <td>${badgeStatus(p.status)}</td>
        <td>${escapeHtml(p.titulo)}</td>
        <td>${escapeHtml(p.fonte)}</td>
        <td>${escapeHtml(p.canal || "-")}</td>
        <td>${escapeHtml((p.atualizada_em || p.captada_em || "-").slice(0, 19))}</td>
        <td>${p.link ? `<a href="${escapeHtml(p.link)}" target="_blank" rel="noreferrer noopener">abrir</a>` : "-"}</td>
      </tr>`).join("");
    $("hist-corpo").innerHTML = `
      <p class="muted small">${j.total} pauta(s) no histórico</p>
      <table class="historico-table">
        <thead><tr><th>Status</th><th>Título</th><th>Fonte</th><th>Canal</th><th>Atualizada</th><th>Link</th></tr></thead>
        <tbody>${rows || `<tr><td colspan="6" style="text-align:center; padding:20px; color:var(--muted);">(vazio)</td></tr>`}</tbody>
      </table>`;
  } catch (e) { $("hist-corpo").innerHTML = `<p class="err">${e.message}</p>`; }
}

// ── Manual ───────────────────────────────────────────────────────────────
async function adicionarManual() {
  const titulo = $("man-titulo").value.trim();
  const link   = $("man-link").value.trim();
  if (!titulo || !link) { setStatus("Título e link são obrigatórios.", "err"); return; }
  try {
    await jpost(API.pautas, {
      titulo, link,
      fonte: $("man-fonte").value.trim(),
      canal: $("man-canal").value,
      score: Number($("man-score").value || 80),
      resumo: $("man-resumo").value.trim(),
      urgente: $("man-urgente").checked,
    });
    setStatus("Pauta adicionada.", "ok");
    $("modal-manual").hidden = true;
    ["man-titulo","man-link","man-fonte","man-resumo"].forEach((k) => $(k).value = "");
    $("man-score").value = "80"; $("man-urgente").checked = false;
    await carregarFila();
  } catch (e) { setStatus(`Falha adicionar: ${e.message}`, "err"); }
}

// ── Eventos ──────────────────────────────────────────────────────────────
$("btn-atualizar").onclick = carregarFila;
$("btn-coletar").onclick   = dispararColeta;
$("btn-redigir").onclick   = acaoRedigir;
$("btn-copydesk").onclick  = acaoCopydesk;
$("btn-preview").onclick   = acaoPreview;
$("btn-publicar").onclick  = acaoPublicar;
$("btn-descartar").onclick = acaoDescartar;
$("btn-feed-analisar").onclick = () => { $("modal-feed").hidden = false; };
$("btn-feed-coletar").onclick  = () => { $("modal-feed").hidden = false; };
$("btn-add-manual").onclick = () => { $("modal-manual").hidden = false; };
$("btn-config").onclick    = () => abrirConfig();
// btn-health removido (painel saúde foi tirado da coluna direita)
// V200_19: handler do modal Publicar (botao da toolbar)
$("pub-rascunho") && ($("pub-rascunho").onclick = () => {
  $("modal-publicar").hidden = true;
  _publicarFinal(true);
});
$("pub-aovivo") && ($("pub-aovivo").onclick = () => {
  $("modal-publicar").hidden = true;
  _publicarFinal(false);
});
// V200_19: removida linha duplicada que sobrescrevia o handler acima
// (sem fechar o modal). Removida tambem ref a $("modal-x") que nao existe.
$("link-atalhos") && ($("link-atalhos").onclick = (e) => { e.preventDefault(); mostrarAtalhos(); });
$("cfg-salvar").onclick    = salvarConfig;
$("btn-zerar-fila").onclick = async () => {
  if (!confirm("Zerar a fila VISUAL?\n\nIsso esconde tudo que foi captado até agora.\n" +
               "As pautas continuam no banco (e no painel desktop). Você poderá restaurar depois.")) return;
  if (!confirm("Confirma mesmo? Vai ocultar todas as pautas atuais da fila web.")) return;
  try {
    const j = await jpost("/api/admin/zerar-fila", { confirm: true });
    setStatus(`Fila zerada visualmente — corte: ${j.corte}`, "ok");
    await carregarFila();
    await atualizarCorteInfo();
  } catch (e) { setStatus(`Falha: ${e.message}`, "err"); }
};
$("btn-restaurar-fila").onclick = async () => {
  if (!confirm("Restaurar a fila? Vai mostrar todas as pautas do banco de novo.")) return;
  try {
    await jpost("/api/admin/restaurar-fila", {});
    setStatus("Fila restaurada — mostrando todas as pautas.", "ok");
    await carregarFila();
    await atualizarCorteInfo();
  } catch (e) { setStatus(`Falha: ${e.message}`, "err"); }
};

async function atualizarCorteInfo() {
  try {
    const j = await jget(`${API.pautas}?limite=1`);
    const corte = j.corte_captacao || "";
    const el = $("corte-info");
    if (!el) return;
    if (corte) {
      const d = corte.slice(0, 19).replace("T", " ");
      el.innerHTML = `<b style="color:var(--acento);">Corte ativo:</b> só pautas captadas a partir de <b>${d}</b>`;
    } else {
      el.innerHTML = `<b>Sem corte ativo</b> — fila mostra todas as pautas do banco.`;
    }
  } catch {}
}
$("diag-recarregar").onclick = carregarDiag;
$("termos-recarregar").onclick = carregarTermos;
$("termos-salvar").onclick     = salvarTermos;
$("termos-novo-grupo").onclick = novoGrupoTermos;
// Delegação: cliques nos chips e inputs do container de grupos.
$("termos-grupos").addEventListener("click", (e) => {
  const t = e.target.closest("[data-act]");
  if (!t) return;
  const grupoEl = e.target.closest(".termos-grupo");
  if (!grupoEl) return;
  const grupo = grupoEl.dataset.grupo;
  const act = t.dataset.act;
  if (act === "rm-termo") {
    const idx = Number(t.dataset.idx);
    (_termosCache[grupo] || []).splice(idx, 1);
    renderTermos();
  } else if (act === "rm-grupo") {
    if (confirm(`Remover o grupo "${grupo}" e todos seus termos?`)) {
      delete _termosCache[grupo];
      renderTermos();
    }
  }
});
$("termos-grupos").addEventListener("keydown", (e) => {
  if (e.key !== "Enter") return;
  const inp = e.target.closest("input[data-act='add-input']");
  if (!inp) return;
  e.preventDefault();
  const valor = inp.value.trim();
  if (!valor) return;
  const grupoEl = e.target.closest(".termos-grupo");
  if (!grupoEl) return;
  const grupo = grupoEl.dataset.grupo;
  if (!_termosCache[grupo]) _termosCache[grupo] = [];
  if (_termosCache[grupo].includes(valor)) {
    setStatus(`Termo "${valor}" já existe em ${grupo}.`, "err"); return;
  }
  _termosCache[grupo].push(valor);
  renderTermos();
  // Foco no input do mesmo grupo para adicionar próximo termo.
  setTimeout(() => {
    const novo = document.querySelector(`.termos-grupo[data-grupo="${grupo}"] input[data-act='add-input']`);
    if (novo) novo.focus();
  }, 0);
});
$("termos-grupos").addEventListener("blur", (e) => {
  // Renomear grupo quando perde foco do input de nome.
  if (e.target.classList && e.target.classList.contains("nome")) {
    const novo = e.target.value.trim().toLowerCase().replace(/\s+/g, "_").replace(/[^a-z0-9_]/g, "");
    const antigo = e.target.closest(".termos-grupo").dataset.grupo;
    if (!novo || novo === antigo) { e.target.value = antigo; return; }
    if (_termosCache[novo]) {
      setStatus(`Já existe grupo "${novo}".`, "err");
      e.target.value = antigo;
      return;
    }
    // Preserva ordem ao renomear.
    const ordered = {};
    for (const k of Object.keys(_termosCache)) {
      ordered[k === antigo ? novo : k] = _termosCache[k];
    }
    _termosCache = ordered;
    renderTermos();
  }
}, true);
$("fontes-recarregar").onclick = carregarFontes;
$("fontes-salvar").onclick     = salvarFontes;
$("fontes-add").onclick        = adicionarFonte;

// ── Auto-detecção de RSS em lote ──────────────────────────────────────────
$("fontes-auto-detectar") && ($("fontes-auto-detectar").onclick = async () => {
  const ta = $("fontes-auto-urls");
  const raw = (ta.value || "").trim();
  if (!raw) {
    $("fontes-auto-status").innerHTML = `<span class="err">Cole pelo menos uma URL</span>`;
    return;
  }
  const urls = raw.split(/\r?\n/).map(s => s.trim()).filter(Boolean);
  if (!urls.length) return;
  if (!confirm(`Detectar feed RSS de ${urls.length} site(s)?\n\nO sistema tenta os sufixos padrão (/feed/, /rss, etc), depois lê o HTML, depois usa Google News como fallback. Pode levar até ${urls.length * 10}s.`)) return;
  $("fontes-auto-detectar").disabled = true;
  $("fontes-auto-status").innerHTML = `<span class="ok">processando ${urls.length} URLs... aguarde</span>`;
  $("fontes-auto-resultado").innerHTML = "";
  try {
    const r = await jpost("/api/admin/fontes-rss/auto-discover", { urls, adicionar: true });
    const linhas = (r.resultados || []).map(res => {
      const icone = res.adicionada ? "✅" : (res.ja_existia ? "⏭" : "❌");
      const sufixo = res.valida ? ` <span class="ok small">[${res.fonte_descoberta} · ${res.items} items]</span>`
                                : ` <span class="err small">[${res.motivo}]</span>`;
      const ja = res.ja_existia ? ` <span class="muted small">(já existia)</span>` : "";
      const feed = res.feed_url ? `<br><span class="muted small" style="font-family:monospace;">${escapeHtml(res.feed_url)}</span>` : "";
      return `<div style="padding:6px 8px; border-bottom:1px solid var(--border);">
        ${icone} <b>${escapeHtml(res.dominio || res.url_input)}</b> → <b>${escapeHtml(res.nome_sugerido || "")}</b>${ja}${sufixo}${feed}
      </div>`;
    }).join("");
    $("fontes-auto-resultado").innerHTML = linhas || `<p class="muted">Sem resultados</p>`;
    $("fontes-auto-status").innerHTML = `<span class="ok">✓ ${r.adicionadas} adicionada(s) · ${r.ja_existiam} já existia(m) · ${r.invalidas} inválida(s) · total agora: ${r.total_fontes_apos}</span>`;
    if (r.adicionadas > 0) {
      ta.value = "";  // limpa textarea ao sucesso parcial
      carregarFontes();  // recarrega a lista logo abaixo
    }
  } catch (e) {
    $("fontes-auto-status").innerHTML = `<span class="err">erro: ${e.message}</span>`;
  } finally {
    $("fontes-auto-detectar").disabled = false;
  }
});
$("hist-recarregar").onclick = carregarHistorico;
$("hist-status").onchange  = carregarHistorico;
$("export-json").onclick   = acaoExportar;
$("feed-analisar2").onclick = feedAnalisar;
$("feed-coletar2").onclick  = feedColetar;
$("man-adicionar").onclick  = adicionarManual;

document.querySelectorAll(".modal-x[data-close], .btn[data-close]").forEach((b) => {
  b.onclick = () => { $(b.dataset.close).hidden = true; };
});
document.querySelectorAll(".modal").forEach((m) => {
  m.addEventListener("click", (e) => { if (e.target === m) m.hidden = true; });
});

// Filtros
["sel-status","sel-fonte","sel-canal","sel-txt","inp-busca"].forEach((id) => {
  $(id).addEventListener("input", () => renderFila(_pautasCache));
});
$("inp-limite").addEventListener("change", carregarFila);
$("chk-incluir-baixo").addEventListener("change", carregarFila);

// Tabs centrais
document.querySelectorAll(".tab").forEach((t) => {
  t.onclick = () => {
    selecionarTab(t.dataset.tab);
    const p = pautaSel();
    if (p) {
      if (t.dataset.tab === "fonte") carregarTabFonte(p);
      else if (t.dataset.tab === "materia") carregarTabMateria(p);
      else if (t.dataset.tab === "copydesk") carregarTabCopydesk(p);
    }
  };
});

$("cd-aplicar")     && ($("cd-aplicar").onclick = () => aplicarCopydesk(true));
$("cd-aplicar-sem") && ($("cd-aplicar-sem").onclick = () => aplicarCopydesk(false));
$("cd-salvar")      && ($("cd-salvar").onclick = () => salvarCopydesk());
// V200_13: edicao manual do texto no Copydesk + salva atualizando Materia
$("cd-editar-texto") && ($("cd-editar-texto").onclick = () => entrarEdicaoCopydesk());
$("cd-salvar-texto") && ($("cd-salvar-texto").onclick = () => salvarEdicaoCopydesk());
$("cd-cancelar-texto") && ($("cd-cancelar-texto").onclick = () => cancelarEdicaoCopydesk());
$("cd-descartar-rev") && ($("cd-descartar-rev").onclick = () => descartarCopydeskRev());
$("cd-restaurar-padrao") && ($("cd-restaurar-padrao").onclick = async (ev) => {
  ev.preventDefault();
  const padrao = await carregarPromptPadrao();
  if (padrao) {
    $("cd-orientacao").value = padrao;
    setStatus("Prompt SEO Google restaurado.", "ok");
  } else {
    setStatus("Nenhum prompt padrão configurado.", "err");
  }
});
$("cd-limpar") && ($("cd-limpar").onclick = (ev) => {
  ev.preventDefault();
  $("cd-orientacao").value = "";
});

// Tabs do modal Config
document.querySelectorAll(".modal-tab").forEach((t) => {
  t.onclick = () => selecionarMTab(t.dataset.mtab);
});

// Clique na fila
$("fila").addEventListener("click", (e) => {
  const card = e.target.closest(".card");
  if (card) {
    _selSeq++;  // invalida fetches anteriores
    _uidSelecionado = card.dataset.uid;
    _pautaSelecionada = _pautasCache.find((p) => p.uid === _uidSelecionado);
    document.querySelectorAll(".card.selecionada").forEach((c) => c.classList.remove("selecionada"));
    card.classList.add("selecionada");
    renderCentro(_pautaSelecionada);
    selecionarTab("fonte");
    carregarTabFonte(_pautaSelecionada);
  }
});

// Clique em ações do painel central (chips/botões)
document.addEventListener("click", (e) => {
  const t = e.target.closest("[data-act]");
  if (!t || t.closest("#fila")) return;
  const act = t.dataset.act;
  const uid = t.dataset.uid;
  const link = t.dataset.link;
  if (act === "abrir" && link) window.open(link, "_blank", "noreferrer,noopener");
  else if (act === "buscar-imagem" && uid) acaoBuscarImagem(uid);
  else if (act === "aprovar" && uid) acaoAprovarBaixoScore(uid);
});

// ════════════════════════════════════════════════════════════════════════
// V200_27: DRAG-RESIZE das colunas Fila|Centro|Stats
// Os <div class="resizer" data-target="fila|stats"> ficam entre as
// colunas. Arrastar atualiza a CSS var --w-fila ou --w-stats.
// Salva em localStorage para persistir entre sessoes.
// ════════════════════════════════════════════════════════════════════════
(function _init_drag_resize_v200_27() {
  const body = document.querySelector(".body");
  if (!body) return;
  // Restaura larguras salvas
  try {
    const saved_fila = localStorage.getItem("ururau_w_fila");
    if (saved_fila && parseInt(saved_fila) >= 240) {
      body.style.setProperty("--w-fila", saved_fila + "px");
    }
    const saved_stats = localStorage.getItem("ururau_w_stats");
    if (saved_stats && parseInt(saved_stats) >= 240) {
      body.style.setProperty("--w-stats", saved_stats + "px");
    }
  } catch (e) {}

  document.querySelectorAll(".resizer[data-target]").forEach((resizer) => {
    const target = resizer.dataset.target; // "fila" ou "stats"
    let dragging = false;
    let startX = 0;
    let startW = 0;

    const onMouseDown = (e) => {
      dragging = true;
      startX = e.clientX;
      const cssVar = target === "fila" ? "--w-fila" : "--w-stats";
      const cur = getComputedStyle(body).getPropertyValue(cssVar).trim();
      startW = parseInt(cur) || (target === "fila" ? 480 : 340);
      resizer.classList.add("dragging");
      document.body.classList.add("resizing");
      e.preventDefault();
    };

    const onMouseMove = (e) => {
      if (!dragging) return;
      const dx = e.clientX - startX;
      // fila aumenta para direita (dx positivo = mais largo)
      // stats aumenta para esquerda (dx negativo = mais largo)
      const delta = target === "fila" ? dx : -dx;
      let nova = startW + delta;
      // limites: min 240px, max 50% viewport
      const maxW = Math.floor(window.innerWidth * 0.5);
      if (nova < 240) nova = 240;
      if (nova > maxW) nova = maxW;
      const cssVar = target === "fila" ? "--w-fila" : "--w-stats";
      body.style.setProperty(cssVar, nova + "px");
    };

    const onMouseUp = () => {
      if (!dragging) return;
      dragging = false;
      resizer.classList.remove("dragging");
      document.body.classList.remove("resizing");
      // Salva no localStorage
      try {
        const cssVar = target === "fila" ? "--w-fila" : "--w-stats";
        const key = target === "fila" ? "ururau_w_fila" : "ururau_w_stats";
        const cur = getComputedStyle(body).getPropertyValue(cssVar).trim();
        const px = parseInt(cur);
        if (px && px >= 240) localStorage.setItem(key, String(px));
      } catch (e) {}
    };

    resizer.addEventListener("mousedown", onMouseDown);
    // mousemove/up globais para o cursor nao escapar do handle
    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
    // duplo-clique reseta para padrao
    resizer.addEventListener("dblclick", () => {
      const cssVar = target === "fila" ? "--w-fila" : "--w-stats";
      const def = target === "fila" ? "480px" : "340px";
      body.style.setProperty(cssVar, def);
      try {
        localStorage.removeItem(target === "fila" ? "ururau_w_fila" : "ururau_w_stats");
      } catch (e) {}
    });
  });
})();

// ════════════════════════════════════════════════════════════════════════
// V200_26 + V200_29 + V200_31: BOOTSTRAP - chamadas iniciais
// Sem essas chamadas, o app.js carrega mas a fila NUNCA enche e _iaCfg
// fica zerada (botoes Redigir/Copydesk disabled).
//
// Quatro funcoes garantidas:
//   1) _carregar_config_ia_bootstrap()  - le /api/diag e popula _iaCfg
//      (rehabilita Redigir/Copydesk).
//   2) carregarFila()                   - primeira renderizacao da fila.
//   3) carregarEstatisticas()           - painel direito.
//   4) setInterval refresh fila         - a cada 30s.
//
// CHAMADAS DEFENSIVAS: tudo dentro de try/catch, se uma falhar nao
// derruba as outras. Espera DOMContentLoaded para garantir que o HTML
// ja foi parseado.
// ════════════════════════════════════════════════════════════════════════
async function _carregar_config_ia_bootstrap() {
  try {
    const r = await fetch("/api/diag", { cache: "no-store" });
    if (!r.ok) return;
    const j = await r.json();
    const ia = (j && j.ia) || {};
    const configurada = !!(ia.lib_instalada && ia.client_criado);
    _iaCfg = { configurada: configurada, modelo: ia.modelo_redacao || "" };
    try { atualizarToolbar(); } catch (e) {}
  } catch (e) {}
}

function _bootstrap_v200_31() {
  // 1) Config IA (rehabilita Redigir)
  try { _carregar_config_ia_bootstrap(); } catch (e) {}
  // 2) Fila inicial
  try { carregarFila(); } catch (e) {}
  // 3) Estatisticas
  try { if (typeof carregarEstatisticas === "function") carregarEstatisticas(); } catch (e) {}
  // 4) Auto-refresh da fila a cada 30s
  try {
    if (!window._autoRefreshFilaTimer) {
      window._autoRefreshFilaTimer = setInterval(() => {
        try { carregarFila(); } catch (e) {}
        try { if (typeof carregarEstatisticas === "function") carregarEstatisticas(); } catch (e) {}
      }, 30000);
    }
  } catch (e) {}
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", _bootstrap_v200_31);
} else {
  // DOM ja pronto
  _bootstrap_v200_31();
}

// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
// V200_32: ATALHOS DE TECLADO
//
// Setas (â†‘/â†“) e J/K navegam a fila de pautas. Ao selecionar, dispara
// click programatico no card -> handler existente carrega texto da fonte.
// Pula atalhos se foco esta em input/textarea/select/contentEditable.
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
(function _atalhos_v200_32() {
  function _focoEditavel() {
    const a = document.activeElement;
    if (!a) return false;
    const tag = (a.tagName || "").toLowerCase();
    if (tag === "input" || tag === "textarea" || tag === "select") return true;
    if (a.isContentEditable) return true;
    return false;
  }

  function _cards() {
    return Array.from(document.querySelectorAll("#fila .card"));
  }

  function _indiceAtual(cards) {
    if (!cards.length) return -1;
    const sel = document.querySelector("#fila .card.selecionada");
    if (!sel) return -1;
    return cards.indexOf(sel);
  }

  function _selecionar(idx) {
    const cards = _cards();
    if (!cards.length) return;
    if (idx < 0) idx = 0;
    if (idx >= cards.length) idx = cards.length - 1;
    const card = cards[idx];
    if (!card) return;
    // Dispara click programatico - reusa toda a logica existente
    card.click();
    // Scroll suave para manter card visivel
    try {
      card.scrollIntoView({ block: "nearest", behavior: "smooth" });
    } catch (e) {
      card.scrollIntoView();
    }
  }

  function _navProximo()  { const c = _cards(); _selecionar(_indiceAtual(c) + 1); }
  function _navAnterior() { const c = _cards(); _selecionar(_indiceAtual(c) - 1); }
  function _navPularFrente() { const c = _cards(); _selecionar(_indiceAtual(c) + 10); }
  function _navPularTras()   { const c = _cards(); _selecionar(_indiceAtual(c) - 10); }
  function _navPrimeiro() { _selecionar(0); }
  function _navUltimo()   { const c = _cards(); _selecionar(c.length - 1); }

  function _abrirDialogAtalhos() {
    let dlg = document.getElementById("_dlg_atalhos_v32");
    if (dlg) { dlg.style.display = "flex"; return; }
    dlg = document.createElement("div");
    dlg.id = "_dlg_atalhos_v32";
    dlg.style.cssText = "position:fixed;inset:0;background:rgba(0,0,0,.65);z-index:9999;display:flex;align-items:center;justify-content:center;";
    dlg.innerHTML = `
      <div style="background:#1a1a1f;color:#e7e7ea;border:1px solid #333;border-radius:10px;padding:24px 28px;min-width:360px;max-width:520px;font-family:system-ui,sans-serif;">
        <div style="font-size:16px;font-weight:600;margin-bottom:14px;color:#f5a623;">Atalhos de teclado</div>
        <table style="width:100%;border-collapse:collapse;font-size:13px;">
          <tbody>
            <tr><td style="padding:6px 0;color:#aaa;width:140px;"><kbd>â†“</kbd> ou <kbd>J</kbd></td><td>PrÃ³xima pauta</td></tr>
            <tr><td style="padding:6px 0;color:#aaa;"><kbd>â†‘</kbd> ou <kbd>K</kbd></td><td>Pauta anterior</td></tr>
            <tr><td style="padding:6px 0;color:#aaa;"><kbd>PgDn</kbd></td><td>+10 pautas</td></tr>
            <tr><td style="padding:6px 0;color:#aaa;"><kbd>PgUp</kbd></td><td>-10 pautas</td></tr>
            <tr><td style="padding:6px 0;color:#aaa;"><kbd>Home</kbd></td><td>Primeira pauta</td></tr>
            <tr><td style="padding:6px 0;color:#aaa;"><kbd>End</kbd></td><td>Ãšltima pauta</td></tr>
            <tr><td style="padding:6px 0;color:#aaa;"><kbd>?</kbd></td><td>Mostra esta janela</td></tr>
            <tr><td style="padding:6px 0;color:#aaa;"><kbd>Esc</kbd></td><td>Fecha esta janela</td></tr>
          </tbody>
        </table>
        <div style="margin-top:18px;text-align:right;">
          <button id="_dlg_atalhos_v32_ok" style="background:#3a3a44;color:#fff;border:1px solid #555;border-radius:6px;padding:6px 16px;cursor:pointer;">OK</button>
        </div>
      </div>`;
    document.body.appendChild(dlg);
    const fechar = () => { dlg.style.display = "none"; };
    dlg.addEventListener("click", (e) => { if (e.target === dlg) fechar(); });
    document.getElementById("_dlg_atalhos_v32_ok").onclick = fechar;
  }

  function _fecharDialogAtalhos() {
    const dlg = document.getElementById("_dlg_atalhos_v32");
    if (dlg) dlg.style.display = "none";
  }

  // Expose mostrarAtalhos (referenciado pelo link [?] atalhos)
  if (typeof window.mostrarAtalhos !== "function") {
    window.mostrarAtalhos = _abrirDialogAtalhos;
  }

  document.addEventListener("keydown", (e) => {
    if (_focoEditavel()) return;
    if (e.ctrlKey || e.metaKey || e.altKey) return;

    let usado = false;
    switch (e.key) {
      case "ArrowDown":
      case "j": case "J": _navProximo(); usado = true; break;
      case "ArrowUp":
      case "k": case "K": _navAnterior(); usado = true; break;
      case "PageDown": _navPularFrente(); usado = true; break;
      case "PageUp":   _navPularTras();   usado = true; break;
      case "Home": _navPrimeiro(); usado = true; break;
      case "End":  _navUltimo();   usado = true; break;
      case "?": _abrirDialogAtalhos(); usado = true; break;
      case "Escape": _fecharDialogAtalhos(); break;
    }
    if (usado) { e.preventDefault(); e.stopPropagation(); }
  });
})();