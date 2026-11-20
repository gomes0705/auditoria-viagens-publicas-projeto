"""Radar de Viagens Públicas — painel de auditoria das viagens a serviço do Governo Federal (2019–2026).

Fonte: Portal da Transparência (CGU) — Viagens a Serviço.
Dados tratados e modelados em Star Schema por pipeline/preparar_dados.py; o painel lê a camada agregada
gerada por pipeline/gerar_agregados.py (ver tratamento_e_analise.ipynb).
"""
import gc
import json
import re
from glob import glob
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Radar de Viagens Públicas", page_icon="✈️", layout="wide",
                   initial_sidebar_state="expanded")
DATA = Path(__file__).parent / "data"

# ============================================================================ identidade visual
AZUL, AZUL_ESC, AZUL_CLARO = "#2a78d6", "#0d366b", "#86b6ef"
LARANJA, AQUA, CINZA, CINZA_CLARO = "#eb6834", "#1baf7a", "#898781", "#c9ced8"
TINTA, TINTA2, GRID = "#0f172a", "#475569", "#e8ebf1"
FONTE = "Inter, system-ui, -apple-system, Segoe UI, sans-serif"

MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
FAIXAS = ["1 dia", "2–3 dias", "4–7 dias", "8–30 dias", "31–90 dias", "> 90 dias"]
URG_DESDE = 2021  # campo "Viagem Urgente" só é preenchido de forma consistente a partir de jun/2020

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, .stApp, .stMarkdown, button, input, textarea, select, label, p, li, td, th {font-family: 'Inter', system-ui, sans-serif !important;}
#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"] {visibility: hidden; height: 0;}
header[data-testid="stHeader"] {background: transparent; height: 2.2rem;}
.stApp {background: #f4f6fb;}
.block-container {padding-top: 1.1rem; padding-bottom: 3rem; max-width: 1440px;}
section[data-testid="stSidebar"] {background: #ffffff; border-right: 1px solid #e6e9f0;}

.hero {position: relative; overflow: hidden; border-radius: 22px; padding: 28px 34px 24px 34px; margin-bottom: 16px;
       background: radial-gradient(900px 380px at 88% -30%, rgba(134,182,239,.55), transparent 60%),
                   linear-gradient(120deg, #0b1f3a 0%, #0d366b 55%, #1c5cab 100%);
       color: #fff; box-shadow: 0 18px 40px -20px rgba(13,54,107,.6);}
.hero:after {content: "✈"; position: absolute; right: 40px; top: -6px; font-size: 130px; opacity: .08; transform: rotate(-14deg);}
.hero .kicker {font-size: .74rem; letter-spacing: .16em; text-transform: uppercase; color: #9ec5f4; font-weight: 700;}
.hero h1 {font-size: 2.15rem; line-height: 1.12; margin: 6px 0 6px 0; font-weight: 800; color: #fff; padding: 0; letter-spacing: -.02em;}
.hero p {color: #cde2fb; margin: 0; font-size: .98rem; max-width: 900px;}
.chips {margin-top: 14px; display: flex; flex-wrap: wrap; gap: 8px;}
.chip {background: rgba(255,255,255,.11); border: 1px solid rgba(255,255,255,.2); color: #eaf2fd; padding: 4px 11px;
       border-radius: 999px; font-size: .76rem; font-weight: 500;}

.kpis {display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 14px; margin: 6px 0 16px 0;}
@media (max-width: 1100px) {.kpis {grid-template-columns: repeat(2, minmax(0, 1fr)) !important;}}
.kpi {background: #fff; border: 1px solid #e6e9f0; border-radius: 18px; padding: 15px 18px 10px 18px;
      box-shadow: 0 1px 2px rgba(15,23,42,.04), 0 10px 26px -18px rgba(15,23,42,.22);}
.kpi .lab {font-size: .72rem; color: #64748b; font-weight: 700; text-transform: uppercase; letter-spacing: .07em;}
.kpi .val {font-size: 1.6rem; font-weight: 800; color: #0f172a; margin-top: 5px; line-height: 1.1; white-space: nowrap; letter-spacing: -.02em;}
.kpi .sub {font-size: .77rem; color: #64748b; margin-top: 3px;}
.kpi svg {display: block; margin-top: 8px;}
.delta {display: inline-block; font-size: .7rem; font-weight: 700; padding: 2px 8px; border-radius: 999px; margin-left: 8px; vertical-align: middle; letter-spacing: 0;}
.delta.up {background: #fdecec; color: #b42318;} .delta.down {background: #e7f6ee; color: #067647;} .delta.neu {background: #eef2f7; color: #475569;}

div[data-testid="stVerticalBlockBorderWrapper"] {background: #fff; border: 1px solid #e6e9f0 !important; border-radius: 18px !important;
      box-shadow: 0 1px 2px rgba(15,23,42,.04), 0 12px 30px -22px rgba(15,23,42,.28);}
.ct {font-size: 1rem; font-weight: 700; color: #0f172a; margin: 2px 0 0 2px; letter-spacing: -.01em;}
.cs {font-size: .8rem; color: #64748b; margin: 2px 0 6px 2px;}

.ins {border-radius: 16px; padding: 13px 18px; margin: 2px 0 16px 0; background: linear-gradient(90deg, #eaf3ff, #f7faff);
      border: 1px solid #d3e4fb; color: #0f172a; font-size: .93rem; line-height: 1.5;}
.ins b {color: #0d366b;}
.warn {background: linear-gradient(90deg, #fff3ea, #fffaf6); border-color: #fbd7c0;}
.warn b {color: #9a3412;}

.ic-num {font-size: 2.35rem; font-weight: 800; color: #0d366b; line-height: 1; letter-spacing: -.03em;}
.ic-tit {font-size: 1rem; font-weight: 700; color: #0f172a; margin: 8px 0 4px 0;}
.ic-txt {font-size: .86rem; color: #475569; line-height: 1.5; min-height: 64px;}
.badge {display: inline-block; font-size: .68rem; font-weight: 700; padding: 3px 9px; border-radius: 999px; margin: 0 6px 4px 0; letter-spacing: .02em;}
.b-alta {background: #e7f6ee; color: #067647;} .b-media {background: #fff4e5; color: #b54708;} .b-tag {background: #eef2f7; color: #334155;}
.decisao {margin-top: 6px; padding: 9px 12px; background: #f8fafc; border-radius: 10px; font-size: .8rem; color: #334155; border-left: 3px solid #2a78d6;}

div[data-testid="stButtonGroup"] {margin: 0 0 14px 0;}
div[data-testid="stButtonGroup"] button {border-radius: 999px !important; font-weight: 600 !important; padding: 6px 16px !important;
      border: 1px solid #dfe4ee !important; background: #fff !important;}
div[data-testid="stButtonGroup"] button[kind*="Active"], div[data-testid="stButtonGroup"] button[aria-checked="true"] {
      background: #0d366b !important; color: #fff !important; border-color: #0d366b !important;}
.side-title {font-weight: 800; font-size: 1.05rem; color: #0f172a;}
.side-note {font-size: .77rem; color: #64748b; line-height: 1.45;}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# ============================================================================ formatação pt-BR
def num(x, casas=0):
    return f"{x:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def brl(x, casas=0):
    return "R$ " + num(x, casas)


def brl_curto(x):
    a = abs(x)
    if a >= 1e9:
        return f"R$ {num(x / 1e9, 2)} bi"
    if a >= 1e6:
        return f"R$ {num(x / 1e6, 1)} mi"
    if a >= 1e3:
        return f"R$ {num(x / 1e3, 1)} mil"
    return brl(x, 2)


def pct(x, casas=1):
    return f"{num(100 * x, casas)}%"


def curto(nome, n=34):
    s = str(nome).replace("Ministério d", "M. d").replace("Presidência da República", "Presidência")
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def md_b(txt):
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", txt)


def sparkline(vals, cor=AZUL, w=170, h=34):
    v = np.asarray(vals, dtype=float)
    v = v[np.isfinite(v)]
    if len(v) < 2 or v.max() == v.min():
        return ""
    x = np.linspace(3, w - 3, len(v))
    y = h - 4 - (v - v.min()) / (v.max() - v.min()) * (h - 8)
    pts = " ".join(f"{a:.1f},{b:.1f}" for a, b in zip(x, y))
    return (f'<svg width="100%" height="{h}" viewBox="0 0 {w} {h}" preserveAspectRatio="none">'
            f'<polygon points="3,{h} {pts} {w - 3},{h}" fill="{cor}" opacity=".10"/>'
            f'<polyline points="{pts}" fill="none" stroke="{cor}" stroke-width="2" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>'
            f'<circle cx="{x[-1]:.1f}" cy="{y[-1]:.1f}" r="3" fill="{cor}"/></svg>')


def kpi(label, valor, sub="", spark=None, delta=None):
    d = ""
    if delta is not None and np.isfinite(delta):
        cls = "neu" if abs(delta) < 0.005 else ("down" if delta < 0 else "up")
        d = f'<span class="delta {cls}">{"▲" if delta > 0 else "▼"} {pct(abs(delta), 0)}</span>'
    return (f'<div class="kpi"><div class="lab">{label}</div><div class="val">{valor}{d}</div>'
            f'<div class="sub">{sub}</div>{sparkline(spark) if spark is not None else ""}</div>')


def kpis(*cards, colunas=5):
    st.markdown(f'<div class="kpis" style="grid-template-columns: repeat({colunas}, minmax(0,1fr));">' + "".join(cards) + "</div>",
                unsafe_allow_html=True)


def titulo(t, s=""):
    st.markdown(f'<div class="ct">{t}</div>' + (f'<div class="cs">{s}</div>' if s else ""), unsafe_allow_html=True)


def estilo(fig, altura=360, legenda=False):
    fig.update_layout(
        height=altura, margin=dict(l=4, r=12, t=8, b=4), separators=",.",
        font=dict(family=FONTE, color=TINTA2, size=12.5), plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        showlegend=legenda, legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0, title=None, font=dict(size=12)),
        hoverlabel=dict(bgcolor="white", bordercolor="#e6e9f0", font=dict(family=FONTE, size=12.5, color=TINTA)),
        bargap=0.28,
    )
    try:
        fig.update_layout(barcornerradius=5)
    except ValueError:
        pass
    fig.update_xaxes(showgrid=False, linecolor="#d5dae3", ticks="", title=None, tickfont=dict(color="#64748b"))
    fig.update_yaxes(gridcolor=GRID, zeroline=False, showline=False, title=None, tickfont=dict(color="#64748b"))
    return fig


LARGURA = {"width": "stretch"} if tuple(int(x) for x in st.__version__.split(".")[:2]) >= (1, 50) else {"use_container_width": True}


def grafico(fig, altura=360, legenda=False):
    st.plotly_chart(estilo(fig, altura, legenda), config={"displayModeBar": False}, **LARGURA)


# ============================================================================ dados (camada agregada do Star Schema)
def _codigos(valores_por_sk):
    """Para uma dimensão com sk = 1..n, devolve (categorias, código da categoria de cada sk)."""
    cats = sorted(set(valores_por_sk))
    pos = {c: i for i, c in enumerate(cats)}
    return cats, np.array([pos[v] for v in valores_por_sk], dtype=np.int16)


@st.cache_resource(show_spinner="Carregando o modelo de dados (8 anos de viagens)...")
def carregar():
    """Carrega a camada agregada (pipeline/gerar_agregados.py), derivada do Star Schema.

    O plano gratuito do Streamlit Cloud tem pouca memória. Por isso o painel NÃO carrega as 5 milhões de viagens
    como tabela: usa um cubo agregado (~400 mil linhas) para somas, contagens e taxas, e só 6 colunas compactas por
    viagem para medianas e curva de Pareto (que não podem ser somadas).
    """
    do = pd.read_parquet(DATA / "dim_orgao.parquet").sort_values("sk_orgao")
    dd = pd.read_parquet(DATA / "dim_destino.parquet").sort_values("sk_destino")
    dm = pd.read_parquet(DATA / "dim_modal.parquet").sort_values("sk_modal")
    du = pd.read_parquet(DATA / "dim_duracao.parquet").sort_values("sk_duracao")
    dt = pd.read_parquet(DATA / "dim_tempo.parquet")
    cat_esc, cod_esc = _codigos(dd["escopo"].tolist())
    cat_uf, cod_uf = _codigos(dd["uf"].tolist())
    orgaos = do["orgao"].tolist()

    # .npz (NumPy comprimido) carrega direto em arrays, sem o pool de memória do Arrow
    with np.load(DATA / "cubo_viagens.npz") as z:
        k = {c: z[c] for c in z.files}
    sk_dest = k["sk_destino"] - 1
    C = pd.DataFrame({
        "ano": k["ano"], "mes": k["mes"],
        "orgao": pd.Categorical.from_codes(k["sk_orgao"] - 1, orgaos),
        "escopo": pd.Categorical.from_codes(cod_esc[sk_dest], cat_esc),
        "uf": pd.Categorical.from_codes(cod_uf[sk_dest], cat_uf),
        "modal": pd.Categorical.from_codes(k["sk_modal"] - 1, dm["modal"].tolist()),
        "faixa_dur": pd.Categorical.from_codes(k["sk_duracao"] - 1, du["faixa_dur"].tolist(), ordered=True),
        "urgente": k["urgente"], "outlier": k["outlier"],
    })
    for c in ["n", "real", "total", "diarias", "passagens", "outros", "fds", "curta", "curta_fds"]:
        C[c] = k[c]
    C["n_out"] = np.where(C["outlier"], C["n"], 0)   # viagens atípicas
    C["n_urg"] = np.where(C["urgente"], C["n"], 0)   # viagens urgentes
    del k, sk_dest

    # medianas e Pareto: histograma de valores (com filtro) e estatísticas exatas (sem filtro), já pré-calculados
    with np.load(DATA / "histograma_valores.npz") as z:
        H = {c: z[c] for c in z.files}
    assert list(H["escopos"]) == cat_esc, "escopos do histograma diferentes das dimensões"
    exatas = json.load(open(DATA / "estatisticas_exatas.json", encoding="utf-8"))

    casos = pd.concat([pd.read_parquet(a) for a in sorted(glob(str(DATA / "casos_*.parquet")))], ignore_index=True)
    fator = dt.groupby("ano")["fator_ipca"].first().to_dict()
    gc.collect()
    return C, H, exatas, casos, dd, fator, cat_esc, orgaos


CUBO, H, EXATAS, casos_all, dim_destino, FATOR, CAT_ESC, ORG_NOMES = carregar()
ANOS = sorted(CUBO["ano"].unique().tolist())
ANO_PARCIAL = max(ANOS)
ORGAOS = CUBO.groupby("orgao", observed=True)["total"].sum().sort_values(ascending=False).index.tolist()
_cnt = CUBO[CUBO["ano"].isin([ANO_PARCIAL, ANO_PARCIAL - 1])].groupby(["ano", "mes"])["n"].sum().unstack(0).fillna(0)
MES_CORTE = int(max([m for m in _cnt.index if _cnt.loc[m, ANO_PARCIAL] >= 0.85 * _cnt.loc[m, ANO_PARCIAL - 1]] or [6]))



# ============================================================================ filtros (barra lateral)
PADRAO = {"f_anos": (ANOS[0], ANOS[-1]), "f_orgaos": [], "f_escopo": "Todos", "f_urg": "Todas", "f_real": True}
for k_, v_ in PADRAO.items():
    st.session_state.setdefault(k_, v_)


def resetar():
    for k_, v_ in PADRAO.items():
        st.session_state[k_] = v_


with st.sidebar:
    st.markdown('<div class="side-title">🎛️ Filtros</div><div class="side-note">Valem para todas as páginas, exceto o Resumo executivo (base completa).</div>',
                unsafe_allow_html=True)
    st.write("")
    st.slider("Período (ano de início)", ANOS[0], ANOS[-1], key="f_anos")
    st.multiselect("Órgão superior", ORGAOS, key="f_orgaos", placeholder="Todos os órgãos")
    st.selectbox("Escopo da viagem", ["Todos", "Nacional", "Internacional", "Sigiloso"], key="f_escopo")
    st.radio("Urgência", ["Todas", "Urgentes", "Programadas"], key="f_urg", horizontal=True,
             help=f"O campo só é preenchido de forma confiável a partir de {URG_DESDE}; ao filtrar por urgência, os anos anteriores saem.")
    st.toggle("Corrigir pela inflação (IPCA)", key="f_real",
              help="Leva os valores de cada ano a preços de dez/2025 (IPCA anual, IBGE). Sem isso, 2019 e 2025 não são comparáveis.")
    st.button("↺  Restaurar filtros", on_click=resetar, **LARGURA)
    st.divider()
    st.markdown(f'<div class="side-note">📌 {ANO_PARCIAL} é parcial (extração set/{ANO_PARCIAL}).<br>'
                'Fonte: Portal da Transparência (CGU), Viagens a Serviço. Apenas viagens realizadas. '
                'Nenhum nome ou CPF é exibido.</div>', unsafe_allow_html=True)

a0, a1 = st.session_state.f_anos
orgs = tuple(st.session_state.f_orgaos)
esc, urg, real = st.session_state.f_escopo, st.session_state.f_urg, st.session_state.f_real
UNID = "R$ de dez/2025" if real else "R$ nominais"
VAL = "real" if real else "total"  # medida de gasto usada pelas páginas (corrigida pelo IPCA ou nominal)
SEM_FILTRO = (a0, a1) == (ANOS[0], ANOS[-1]) and not orgs and esc == "Todos" and urg == "Todas"


def filtrar_cubo(base):
    if SEM_FILTRO:
        return base
    m = base["ano"].between(a0, a1)
    if orgs:
        m &= base["orgao"].isin(orgs)
    if esc != "Todos":
        m &= base["escopo"] == esc
    if urg != "Todas":
        m &= (base["urgente"] == (urg == "Urgentes")) & (base["ano"] >= URG_DESDE)
    return base.loc[m]


def celulas_filtradas():
    """Células do histograma (ano × órgão × escopo × urgência) que entram no filtro atual."""
    m = (H["cel_ano"] >= a0) & (H["cel_ano"] <= a1)
    if orgs:
        m &= np.isin(H["cel_org"] - 1, [ORG_NOMES.index(o) for o in orgs])
    if esc != "Todos":
        m &= H["cel_esc"] == CAT_ESC.index(esc)
    if urg != "Todas":
        m &= (H["cel_urg"] == (urg == "Urgentes")) & (H["cel_ano"] >= URG_DESDE)
    return m


df = filtrar_cubo(CUBO)
CEL = celulas_filtradas()


def _mediana_hist(cont):
    """Mediana a partir das contagens por faixa de valor (interpolação geométrica dentro da faixa)."""
    n = cont.sum()
    if n == 0:
        return np.nan
    acum = np.cumsum(cont)
    i = int(np.searchsorted(acum, n / 2))
    if i == 0:
        return 0.0
    antes = acum[i - 1]
    frac = (n / 2 - antes) / cont[i] if cont[i] else 0.0
    lo, hi = H["faixas"][i - 1], H["faixas"][min(i, len(H["faixas"]) - 1)]
    return float(lo * (hi / lo) ** frac)


def mediana_geral(col):
    """Mediana exata sem filtro; com filtro, estimada pelo histograma (erro máximo ~3%)."""
    if SEM_FILTRO:
        return EXATAS[col]["mediana"]
    return _mediana_hist(H[f"n_{col}"][CEL].sum(axis=0))


def mediana_por(col, chave):
    """Mediana por ano ou por órgão (exata sem filtro; pelo histograma com filtro)."""
    if SEM_FILTRO:
        if chave == "ano":
            return pd.Series({int(k): v for k, v in EXATAS[col]["mediana_ano"].items()}).sort_index()
        return pd.Series({ORG_NOMES[int(k) - 1]: v for k, v in EXATAS[col]["mediana_orgao"].items()})
    grupo = H["cel_ano"][CEL] if chave == "ano" else np.array(ORG_NOMES)[H["cel_org"][CEL] - 1]
    cont = pd.DataFrame(H[f"n_{col}"][CEL]).groupby(grupo).sum()
    return pd.Series({g: _mediana_hist(cont.loc[g].to_numpy()) for g in cont.index}).sort_index()


def pareto(col):
    """Curva de concentração: x = fração das viagens (mais caras primeiro), y = fração acumulada do gasto."""
    if SEM_FILTRO:
        p = EXATAS[col]["pareto"]
        return np.array(p["x"]), np.array(p["y"])
    cont = H[f"n_{col}"][CEL].sum(axis=0)[::-1].astype(float)
    soma_v = H[f"s_{col}"][CEL].sum(axis=0)[::-1]
    x = np.concatenate([[0], np.cumsum(cont) / max(cont.sum(), 1)])
    y = np.concatenate([[0], np.cumsum(soma_v) / max(soma_v.sum(), 1)])
    return x, y


def soma(d, por, col=None):
    col = col or VAL
    return d.groupby(por, observed=True)[col].sum()


def media(d, por, col=None):
    """Média ponderada por viagem (soma do valor ÷ número de viagens) a partir do cubo."""
    col = col or VAL
    g = d.groupby(por, observed=True)[[col, "n"]].sum()
    return g[col] / g["n"]


def share(d, por, num_col):
    g = d.groupby(por, observed=True)[[num_col, "n"]].sum()
    return g[num_col] / g["n"]


# ============================================================================ cabeçalho + navegação
st.markdown(f"""
<div class="hero">
  <div class="kicker">Auditoria cidadã · Governo Federal</div>
  <h1>Radar de Viagens Públicas</h1>
  <p>Quanto o governo gasta com viagens a serviço, quem gasta, como gasta e quais viagens merecem revisão:
     {num(CUBO['n'].sum() / 1e6, 2)} milhões de viagens de {ANOS[0]} a {ANOS[-1]}, organizadas para responder em segundos.</p>
  <div class="chips"><span class="chip">📂 Portal da Transparência (CGU)</span><span class="chip">🗓️ {ANOS[0]}–{ANOS[-1]} ({ANO_PARCIAL} parcial)</span>
  <span class="chip">💱 Valores corrigidos pelo IPCA</span><span class="chip">🔒 Sem dados pessoais (LGPD)</span>
  <span class="chip">⭐ Modelo em Star Schema</span></div>
</div>""", unsafe_allow_html=True)

PAGINAS = {"resumo": "✨ Resumo executivo", "evolucao": "📈 Evolução", "orgaos": "🏛️ Órgãos",
           "perfil": "🧭 Perfil", "radar": "🚨 Radar de revisão", "metodo": "📘 Metodologia"}
p0 = st.query_params.get("p", "resumo")
p0 = p0 if p0 in PAGINAS else "resumo"
pag = st.segmented_control("Navegação", list(PAGINAS), format_func=PAGINAS.get, default=p0, key="nav",
                           label_visibility="collapsed") or "resumo"
st.query_params["p"] = pag

if df["n"].sum() == 0 and pag != "resumo":
    st.warning("Nenhuma viagem com esses filtros.")
    st.stop()


def anual_de(d, col=None):
    col = col or VAL
    return d.groupby("ano").agg(valor=(col, "sum"), viagens=("n", "sum"))


def barras_ano(serie, cores, texto=True, hover="%{x}: R$ %{y:.2f} bi", curto_x=False):
    f = go.Figure(go.Bar(x=[("’" + str(a)[2:]) if curto_x else str(a) for a in serie.index], y=serie.values / 1e9, marker_color=cores,
                         text=[num(v / 1e9, 2) for v in serie.values] if texto else None, textposition="outside",
                         cliponaxis=False, hovertemplate=hover + "<extra></extra>"))
    f.update_xaxes(type="category")
    f.update_yaxes(range=[0, serie.max() / 1e9 * 1.18])
    return f


# ============================================================================ RESUMO EXECUTIVO
def pagina_resumo():
    b, col = CUBO, "real"  # o resumo usa sempre a base completa em valores corrigidos
    an = anual_de(b, col)
    nom = b.groupby("ano")["total"].sum()
    ytd = b[b["mes"] <= MES_CORTE].groupby("ano")[col].sum()
    du = b[b["ano"] >= URG_DESDE]
    ex = EXATAS[col]  # medianas e concentração exatas da base completa (pré-calculadas no pipeline)
    mediana, top1 = ex["mediana"], ex["pareto"]["top1"]
    med_ano = pd.Series({int(k): v for k, v in ex["mediana_ano"].items()}).sort_index()
    fx = b.groupby("faixa_dur", observed=False).agg(v=("n", "sum"), g=(col, "sum")).reindex(FAIXAS)
    fx = fx / fx.sum()
    lv, lg = fx.loc[["31–90 dias", "> 90 dias"]].sum()
    tk = media(du, "urgente", col)
    org = b.groupby("orgao", observed=True).agg(n=("n", "sum"), g=(col, "sum"), o=("n_out", "sum"))
    org["at"] = org["o"] / org["n"]
    top3 = org["g"].nlargest(3).sum() / org["g"].sum()
    n_tot, n_out = int(b["n"].sum()), int(b["n_out"].sum())
    r25 = an.loc[2025, "valor"] / an.loc[2019, "valor"]
    p_urg = du["n_urg"].sum() / du["n"].sum()

    st.markdown('<div class="ins">🧭 <b>Em uma frase:</b> o gasto com viagens <b>voltou acima do nível pré-pandemia mesmo descontada a inflação</b>, '
                'está <b>concentrado em poucas viagens longas</b> e tem a <b>urgência como padrão</b>. Isso aponta falta de planejamento '
                'e mostra onde a auditoria deve olhar primeiro.</div>', unsafe_allow_html=True)

    kpis(kpi(f"Gasto {ANOS[0]}–{ANOS[-1]}", brl_curto(b[col].sum()), "R$ de dez/2025", an["valor"].values),
         kpi("Viagens realizadas", f"{num(n_tot / 1e6, 2)} mi", "processos de viagem", an["viagens"].values),
         kpi("Ticket mediano", brl(mediana), f"média {brl(b[col].sum() / n_tot)}", med_ano.values),
         kpi("Viagens urgentes", pct(p_urg, 0), f"desde {URG_DESDE}", share(du, "ano", "n_urg").values),
         kpi("Casos atípicos", num(n_out), f"{num(n_out / n_tot * 1000, 1)} por mil viagens", b.groupby("ano")["n_out"].sum().values))

    def card(n_txt, tit, txt, conf, tags, decisao, fig, legenda=False):
        with st.container(border=True):
            badge = '<span class="badge b-alta">● Confiança alta</span>' if conf == "alta" else '<span class="badge b-media">● Confiança média</span>'
            st.markdown(f'<div class="ic-num">{n_txt}</div><div class="ic-tit">{tit}</div><div class="ic-txt">{md_b(txt)}</div>'
                        f'<div style="margin-top:8px">{badge}' + "".join(f'<span class="badge b-tag">{t}</span>' for t in tags) + "</div>",
                        unsafe_allow_html=True)
            fig.update_xaxes(tickangle=0, tickfont=dict(size=11))
            grafico(fig, 190, legenda)
            st.markdown(f'<div class="decisao">🎯 <b>Decisão que habilita:</b> {decisao}</div>', unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3, gap="medium")
    with c1:
        f = barras_ano(an["valor"], [CINZA_CLARO if a in (2020, 2021) else (AZUL_CLARO if a == ANO_PARCIAL else AZUL) for a in an.index],
                       texto=False, curto_x=True)
        card(f"{num(r25, 2)}×", "Gasto pós-pandemia supera 2019",
             f"Em 2025 o gasto foi **{num(r25, 2)}× o de 2019 já descontada a inflação** (nominal: {num(nom[2025] / nom[2019], 2)}×). "
             f"A queda de {pct(1 - an.loc[2020, 'valor'] / an.loc[2019, 'valor'], 0)} na pandemia foi totalmente revertida.",
             "alta", ["Tendência", "IPCA"], "rever o teto orçamentário de diárias e passagens e exigir justificativa para o presencial.", f)
    with c2:
        var = ytd[ANO_PARCIAL] / ytd[ANO_PARCIAL - 1] - 1
        f = barras_ano(ytd, [LARANJA if a == ANO_PARCIAL else AZUL_CLARO for a in ytd.index], texto=False, curto_x=True)
        card(f"{'−' if var < 0 else '+'}{pct(abs(var), 0)}", f"{ANO_PARCIAL}: primeiro sinal de {'queda' if var < 0 else 'alta'}",
             f"No mesmo período (jan–{MESES[MES_CORTE - 1]}), {ANO_PARCIAL} gasta **{pct(abs(var), 0)} {'menos' if var < 0 else 'mais'} "
             f"que {ANO_PARCIAL - 1}**, com volume de viagens parecido.",
             "media", ["Ano parcial"], "acompanhar mês a mês se a tendência se confirma no fechamento do ano.", f)
    with c3:
        f = go.Figure()
        fc = ["1d", "2–3d", "4–7d", "8–30d", "31–90d", ">90d"]
        f.add_bar(x=fc, y=fx["v"] * 100, name="% viagens", marker_color=AZUL_CLARO, hovertemplate="%{x}: %{y:.1f}% das viagens<extra></extra>")
        f.add_bar(x=fc, y=fx["g"] * 100, name="% gasto", marker_color=AZUL_ESC, hovertemplate="%{x}: %{y:.1f}% do gasto<extra></extra>")
        f.update_layout(barmode="group", bargroupgap=.06)
        card(pct(top1, 0), "do gasto está em 1% das viagens",
             f"Viagens com mais de 30 dias são **{pct(lv)} das viagens e {pct(lg, 0)} do gasto**. Auditar poucas viagens cobre muito dinheiro.",
             "alta", ["Concentração", "Pareto"], "priorizar a auditoria nas viagens longas e de maior valor (mais retorno por hora de análise).",
             f, legenda=True)

    c4, c5, c6 = st.columns(3, gap="medium")
    with c4:
        t = media(du, ["ano", "urgente"], col).unstack()
        t.index = ["’" + str(a)[2:] for a in t.index]
        f = go.Figure()
        f.add_scatter(x=t.index, y=t[True], name="Urgentes", mode="lines+markers", line=dict(color=LARANJA, width=2.5),
                      marker=dict(size=7), hovertemplate="Urgentes %{x}: R$ %{y:,.0f}<extra></extra>")
        f.add_scatter(x=t.index, y=t[False], name="Programadas", mode="lines+markers", line=dict(color=AZUL, width=2.5),
                      marker=dict(size=7), hovertemplate="Programadas %{x}: R$ %{y:,.0f}<extra></extra>")
        f.update_xaxes(type="category")
        card(pct(p_urg, 0), "das viagens são \"urgentes\"",
             f"Desde {URG_DESDE}, a maioria das viagens é marcada como urgente, e elas custam **{pct(tk[True] / tk[False] - 1, 0)} mais** "
             f"em média (passagens compradas em cima da hora).", "media", ["Planejamento", f"dado confiável desde {URG_DESDE}"],
             "instituir antecedência mínima de compra e exigir justificativa formal da urgência.", f, legenda=True)
    with c5:
        o = org[org["n"] >= 10000].nlargest(6, "at").iloc[::-1]
        f = go.Figure(go.Bar(x=o["at"] * 1000, y=[curto(i, 24) for i in o.index], orientation="h", marker_color=LARANJA,
                             hovertemplate="%{y}: %{x:.1f} por mil viagens<extra></extra>"))
        card(pct(top3, 0), "do gasto em 3 órgãos, por volume",
             "Justiça e Segurança Pública, Defesa e Educação lideram pela **quantidade de viagens**. Normalizando por volume, a "
             "**taxa de casos atípicos por mil viagens** mostra onde olhar.", "media", ["Órgãos", "Normalização"],
             "comparar órgãos pela taxa, não pelo total, e cobrar explicação de quem está acima da média.", f)
    with c6:
        ca = b.groupby("ano")["n_out"].sum()
        f = go.Figure(go.Bar(x=["’" + str(a)[2:] for a in ca.index], y=ca.values, marker_color=AZUL,
                             hovertemplate="%{x}: %{y:,.0f} casos<extra></extra>"))
        card(num(n_out), "viagens na fila de revisão",
             f"Viagens com **custo por dia muito acima de viagens parecidas** (≈ {pct(n_out / n_tot)} do total). "
             "Cada uma tem a PCDP para conferência no Portal, sem expor o servidor.", "media", ["Radar", "Q3 + 3×IQR"],
             "transformar a lista em fila de auditoria amostral: uma lista viável, em vez de milhões de linhas.", f)

    st.markdown('<div class="ins warn">⚠️ <b>Leia com cuidado:</b> caso atípico é um <b>sinal para revisão</b>, não prova de irregularidade. '
                'A base não mede reuniões online: a queda de 2020 coincide com a pandemia, mas não prova que o trabalho remoto causou a economia. '
                f'O campo de urgência só é confiável a partir de {URG_DESDE}.</div>', unsafe_allow_html=True)


# ============================================================================ EVOLUÇÃO
def pagina_evolucao():
    an = anual_de(df)
    tot, n = df[VAL].sum(), int(df["n"].sum())
    du = df[df["ano"] >= URG_DESDE]
    med_ano = mediana_por(VAL, "ano")
    comp = [a for a in an.index if a != ANO_PARCIAL]
    dlt = an["valor"].loc[comp[-1]] / an["valor"].loc[comp[-2]] - 1 if len(comp) >= 2 else None
    tem_urg = du["n"].sum() > 0
    kpis(kpi("Gasto total", brl_curto(tot), UNID, an["valor"].values, dlt),
         kpi("Viagens", f"{num(n / 1e6, 2)} mi" if n >= 1e6 else num(n), "realizadas", an["viagens"].values),
         kpi("Ticket médio", brl(tot / n), "gasto ÷ viagens", (an["valor"] / an["viagens"]).values),
         kpi("Ticket mediano", brl(mediana_geral(VAL)), "metade custa menos que isso", med_ano.values),
         kpi("Urgentes", pct(du["n_urg"].sum() / du["n"].sum(), 0) if tem_urg else "—", f"desde {URG_DESDE}",
             share(du, "ano", "n_urg").values if tem_urg else None))
    if dlt is not None:
        st.caption(f"▲▼ variação de {comp[-1]} sobre {comp[-2]} (últimos anos completos) · mini-linhas = tendência anual")

    ytd = df[df["mes"] <= MES_CORTE].groupby("ano")[VAL].sum()
    c1, c2 = st.columns(2, gap="medium")
    with c1, st.container(border=True):
        titulo("Gasto anual", f"R$ bilhões · {UNID} · barra clara = {ANO_PARCIAL} parcial")
        grafico(barras_ano(an["valor"], [AZUL_CLARO if a == ANO_PARCIAL else AZUL for a in an.index]), 330)
    with c2, st.container(border=True):
        titulo("Comparação justa entre anos", f"Mesmo intervalo (jan–{MESES[MES_CORTE - 1]}) em todos os anos · R$ bilhões")
        grafico(barras_ano(ytd, [LARANJA if a == ANO_PARCIAL else AZUL for a in ytd.index],
                           hover="%{x} (jan–" + MESES[MES_CORTE - 1] + "): R$ %{y:.2f} bi"), 330)

    av, linhas = an["valor"], []
    if 2019 in av and 2020 in av:
        linhas.append(f"Pandemia: **−{pct(1 - av[2020] / av[2019], 0)}** de 2019 para 2020")
    if 2019 in av and 2025 in av:
        linhas.append(f"2025 = **{num(av[2025] / av[2019], 2)}×** 2019 ({'real' if real else 'nominal'})")
    if ANO_PARCIAL in ytd and ANO_PARCIAL - 1 in ytd:
        v = ytd[ANO_PARCIAL] / ytd[ANO_PARCIAL - 1] - 1
        linhas.append(f"{ANO_PARCIAL} até {MESES[MES_CORTE - 1]}: **{'−' if v < 0 else '+'}{pct(abs(v), 0)}** sobre {ANO_PARCIAL - 1}")
    if linhas:
        st.markdown('<div class="ins">💡 ' + md_b(" &nbsp;·&nbsp; ".join(linhas)) + "</div>", unsafe_allow_html=True)

    c3, c4 = st.columns(2, gap="medium")
    with c3, st.container(border=True):
        titulo("Composição do gasto", "Diárias, passagens e outros gastos por ano · R$ bilhões")
        cp = df.groupby("ano")[["diarias", "passagens", "outros"]].sum().astype(float)
        cp = cp.mul(np.array([FATOR[a] for a in cp.index]) if real else 1.0, axis=0) / 1e9
        f = go.Figure()
        for c, nome, cor in [("diarias", "Diárias", AZUL), ("passagens", "Passagens", LARANJA), ("outros", "Outros", AQUA)]:
            f.add_bar(x=cp.index.astype(str), y=cp[c], name=nome, marker_color=cor, marker_line=dict(color="#fff", width=1.5),
                      hovertemplate=nome + ": R$ %{y:.2f} bi<extra></extra>")
        f.update_layout(barmode="stack", hovermode="x unified")
        f.update_xaxes(type="category")
        grafico(f, 330, True)
    with c4, st.container(border=True):
        titulo("Sazonalidade", f"Viagens por mês de início · destaques: 2019, 2020 e {ANO_PARCIAL - 1}")
        mens = df.groupby(["ano", "mes"])["n"].sum().reset_index(name="v")
        mens = mens[mens["v"] > 0]
        f = go.Figure()
        for a in sorted(mens["ano"].unique()):
            s = mens[mens["ano"] == a]
            cor = {2019: CINZA, 2020: LARANJA, ANO_PARCIAL - 1: AZUL}.get(a, "#dde2ea")
            f.add_scatter(x=[MESES[m - 1] for m in s["mes"]], y=s["v"], name=str(a), mode="lines",
                          line=dict(width=2.8 if cor != "#dde2ea" else 1.2, color=cor),
                          hovertemplate=f"{a} · %{{x}}: %{{y:,.0f}} viagens<extra></extra>")
        grafico(f, 330, True)


# ============================================================================ ÓRGÃOS
def pagina_orgaos():
    org = df.groupby("orgao", observed=True).agg(viagens=("n", "sum"), gasto=(VAL, "sum"), o=("n_out", "sum"))
    org = org[org["viagens"] > 0]
    org["mediana"] = mediana_por(VAL, "orgao").reindex(org.index.astype(str)).to_numpy()
    du = df[df["ano"] >= URG_DESDE]
    urg_org = share(du, "orgao", "n_urg") if du["n"].sum() > 0 else pd.Series(dtype=float)
    org["urg"] = urg_org.reindex(org.index)
    org["atip"] = org["o"] / org["viagens"]
    org["ticket"] = org["gasto"] / org["viagens"]
    org["part"] = org["gasto"] / org["gasto"].sum()
    org = org.sort_values("gasto", ascending=False).reset_index()
    t0 = org.iloc[0]
    st.markdown(f'<div class="ins">💡 Os <b>3 maiores órgãos</b> concentram <b>{pct(org["part"].head(3).sum(), 0)}</b> do gasto. '
                f'<b>{t0["orgao"]}</b> lidera com <b>{num(t0["viagens"])}</b> viagens: gasto alto reflete volume, não necessariamente ineficiência. '
                f'Para comparar, use o <b>ticket</b> e a <b>taxa de casos atípicos</b>.</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2, gap="medium")
    with c1, st.container(border=True):
        titulo("Top 10 órgãos por gasto", f"R$ bilhões · participação no total · {UNID}")
        t = org.head(10).iloc[::-1]
        f = go.Figure(go.Bar(x=t["gasto"] / 1e9, y=t["orgao"].map(curto), orientation="h", marker_color=AZUL,
                             text=[f"{num(v / 1e9, 2)} · {pct(p, 0)}" for v, p in zip(t["gasto"], t["part"])],
                             textposition="outside", cliponaxis=False, hovertemplate="<b>%{y}</b><br>R$ %{x:.2f} bi<extra></extra>"))
        f.update_xaxes(showticklabels=False, range=[0, t["gasto"].max() / 1e9 * 1.3])
        grafico(f, 420)
    with c2, st.container(border=True):
        titulo("Volume × custo por viagem", "Cada bolha é um órgão (tamanho = gasto). Direita: muitas viagens · alto: viagens caras")
        o = org[org["viagens"] >= 500]
        f = go.Figure(go.Scatter(x=o["viagens"], y=o["ticket"], mode="markers", text=o["orgao"],
                                 marker=dict(size=np.sqrt(o["gasto"] / o["gasto"].max()) * 52 + 6, color=AZUL, opacity=.55,
                                             line=dict(color="#fff", width=1.5)), customdata=o["gasto"],
                                 hovertemplate="<b>%{text}</b><br>%{x:,.0f} viagens<br>Ticket: R$ %{y:,.0f}<br>Gasto: R$ %{customdata:,.0f}<extra></extra>"))
        for _, r in pd.concat([o.nlargest(2, "gasto"), o.nlargest(1, "ticket")]).drop_duplicates("orgao").iterrows():
            f.add_annotation(x=np.log10(r["viagens"]), y=r["ticket"], text=curto(r["orgao"], 30), showarrow=False, yshift=22,
                             font=dict(size=11, color=TINTA))
        f.update_xaxes(type="log", title="nº de viagens (escala log)")
        f.update_yaxes(title="ticket médio (R$)")
        grafico(f, 420)

    with st.container(border=True):
        titulo("Tabela comparativa normalizada", "Clique no cabeçalho para ordenar · urgência medida a partir de 2021")
        tab = pd.DataFrame({"Órgão": org["orgao"].astype(str), "Viagens": org["viagens"], "Gasto (R$ mi)": org["gasto"] / 1e6,
                            "% do gasto": org["part"] * 100, "Ticket médio": org["ticket"], "Mediana": org["mediana"],
                            "% urgentes": org["urg"] * 100, "Atípicos/mil": org["atip"] * 1000})
        st.dataframe(tab, hide_index=True, height=400, **LARGURA, column_config={
            "Viagens": st.column_config.NumberColumn(format="localized"),
            "Gasto (R$ mi)": st.column_config.NumberColumn(format="%.1f"),
            "% do gasto": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=float(tab["% do gasto"].max())),
            "Ticket médio": st.column_config.NumberColumn(format="R$ %.0f"),
            "Mediana": st.column_config.NumberColumn(format="R$ %.0f"),
            "% urgentes": st.column_config.NumberColumn(format="%.0f%%"),
            "Atípicos/mil": st.column_config.NumberColumn(format="%.1f", help="Casos atípicos por mil viagens (ver Metodologia)."),
        })


# ============================================================================ PERFIL
def pagina_perfil():
    tot = df[VAL].sum()
    fx = df.groupby("faixa_dur", observed=False).agg(v=("n", "sum"), g=(VAL, "sum")).reindex(FAIXAS).fillna(0)
    fx["pv"], fx["pg"] = fx["v"] / fx["v"].sum(), fx["g"] / tot
    lv, lg = fx.loc[["31–90 dias", "> 90 dias"], ["pv", "pg"]].sum()
    px_, py_ = pareto(VAL)
    topo = {p: float(np.interp(p / 100, px_, py_)) for p in (1, 10)}
    st.markdown(f'<div class="ins">💡 <b>Concentração:</b> 1% das viagens responde por <b>{pct(topo[1], 0)}</b> do gasto. '
                f'Viagens com mais de 30 dias são <b>{pct(lv)}</b> das viagens e <b>{pct(lg, 0)}</b> do gasto.</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2, gap="medium")
    with c1, st.container(border=True):
        titulo("Duração: peso nas viagens × peso no gasto", "Viagens curtas são maioria; as longas pesam no orçamento")
        f = go.Figure()
        f.add_bar(x=FAIXAS, y=fx["pv"] * 100, name="% das viagens", marker_color=AZUL_CLARO, hovertemplate="%{x}: %{y:.1f}% das viagens<extra></extra>")
        f.add_bar(x=FAIXAS, y=fx["pg"] * 100, name="% do gasto", marker_color=AZUL_ESC, hovertemplate="%{x}: %{y:.1f}% do gasto<extra></extra>")
        f.update_layout(barmode="group", bargroupgap=.06)
        f.update_yaxes(ticksuffix="%")
        grafico(f, 340, True)
    with c2, st.container(border=True):
        titulo("Curva de concentração (Pareto)", "% acumulado do gasto, das viagens mais caras para as mais baratas")
        ok = px_ > 0
        f = go.Figure(go.Scatter(x=px_[ok] * 100, y=py_[ok] * 100, mode="lines", line=dict(color=AZUL, width=3),
                                 fill="tozeroy", fillcolor="rgba(42,120,214,.08)",
                                 hovertemplate="As %{x:.1f}% mais caras = %{y:.1f}% do gasto<extra></extra>"))
        for p in [1, 10]:
            f.add_scatter(x=[p], y=[topo[p] * 100], mode="markers+text", marker=dict(size=10, color=AZUL_ESC, line=dict(color="#fff", width=2)),
                          text=[f"{p}% → {num(topo[p] * 100, 0)}%  "], textposition="top left", hoverinfo="skip")
        f.update_xaxes(type="log", range=[-1, 2], tickvals=[0.1, 1, 10, 100], ticktext=["0,1%", "1%", "10%", "100%"])
        f.update_yaxes(ticksuffix="%", range=[0, 104])
        grafico(f, 340)
    c3, c4 = st.columns(2, gap="medium")
    with c3, st.container(border=True):
        titulo("Meio de transporte principal", "Gasto em R$ bilhões · viagem com trecho aéreo conta como Aéreo")
        md = df.groupby("modal", observed=True).agg(v=("n", "sum"), g=(VAL, "sum")).sort_values("g")
        md = md[md["g"] > 0]
        f = go.Figure(go.Bar(x=md["g"] / 1e9, y=md.index.astype(str), orientation="h", marker_color=AZUL,
                             text=[pct(g / tot, 0) for g in md["g"]], textposition="outside", cliponaxis=False,
                             customdata=np.stack([md["v"], md["g"] / md["v"]], axis=1),
                             hovertemplate="<b>%{y}</b><br>R$ %{x:.2f} bi<br>%{customdata[0]:,.0f} viagens<br>Ticket R$ %{customdata[1]:,.0f}<extra></extra>"))
        f.update_xaxes(range=[0, md["g"].max() / 1e9 * 1.18])
        grafico(f, 360)
    with c4, st.container(border=True):
        titulo("Para onde vão", "UF do 1º destino · viagens nacionais · tamanho = gasto")
        geo = dim_destino[dim_destino["lat"].notna()][["uf", "nome_uf", "lat", "lon"]].drop_duplicates("uf")
        uf = df[df["escopo"] == "Nacional"].groupby("uf", observed=True).agg(g=(VAL, "sum"), v=("n", "sum")).reset_index()
        uf["uf"] = uf["uf"].astype(str)
        uf = uf[uf["v"] > 0].merge(geo, on="uf")
        if len(uf):
            f = go.Figure(go.Scattergeo(lat=uf["lat"], lon=uf["lon"], text=uf["uf"], mode="markers+text",
                                        textfont=dict(size=10, color=TINTA, family=FONTE),
                                        marker=dict(size=np.sqrt(uf["g"] / uf["g"].max()) * 52 + 7, color=AZUL, opacity=.55,
                                                    line=dict(color="#fff", width=1.5)),
                                        customdata=np.stack([uf["nome_uf"], uf["g"], uf["v"]], axis=1),
                                        hovertemplate="<b>%{customdata[0]}</b><br>R$ %{customdata[1]:,.0f}<br>%{customdata[2]:,.0f} viagens<extra></extra>"))
            f.update_geos(scope="south america", center=dict(lat=-14, lon=-53), projection_scale=1.9, showcountries=True,
                          countrycolor="#d5dae3", showland=True, landcolor="#eef2f8", showocean=False, bgcolor="rgba(0,0,0,0)",
                          showframe=False, showcoastlines=False)
            grafico(f, 360)
        else:
            st.info("Sem viagens nacionais no filtro atual.")


# ============================================================================ RADAR
def pagina_radar():
    st.markdown('<div class="ins warn">🧭 <b>Como ler:</b> caso atípico é a viagem com <b>custo por dia muito acima de viagens parecidas</b> '
                '(mesmo ano, escopo, faixa de duração e com/sem avião), pela regra <b>Q3 + 3×IQR em escala log</b>. '
                'É um <b>sinal para revisão</b>, não prova de irregularidade.</div>', unsafe_allow_html=True)
    n_tot, n_out = df["n"].sum(), df["n_out"].sum()
    v_out = df.loc[df["outlier"], VAL].sum()
    kpis(kpi("Casos atípicos", num(n_out), "viagens sinalizadas", df.groupby("ano")["n_out"].sum().values),
         kpi("Por mil viagens", num(n_out / n_tot * 1000, 1), "taxa normalizada", (share(df, "ano", "n_out") * 1000).values),
         kpi("Valor dos casos", brl_curto(v_out), UNID),
         kpi("Parcela do gasto", pct(v_out / df[VAL].sum()), "do total filtrado"), colunas=4)
    c1, c2 = st.columns(2, gap="medium")
    with c1, st.container(border=True):
        titulo("Órgãos com maior taxa de casos atípicos", "Por mil viagens · mínimo de 2.000 viagens no filtro")
        ot = df.groupby("orgao", observed=True).agg(n=("n", "sum"), o=("n_out", "sum")).reset_index()
        ot["t"] = ot["o"] / ot["n"]
        ot = ot[ot["n"] >= 2000].nlargest(10, "t").iloc[::-1]
        f = go.Figure(go.Bar(x=ot["t"] * 1000, y=ot["orgao"].map(curto), orientation="h", marker_color=LARANJA,
                             text=[num(v * 1000, 1) for v in ot["t"]], textposition="outside", cliponaxis=False, customdata=ot["n"],
                             hovertemplate="<b>%{y}</b><br>%{x:.1f} por mil<br>%{customdata:,.0f} viagens<extra></extra>"))
        f.update_xaxes(showticklabels=False, range=[0, (ot["t"].max() * 1000 if len(ot) else 1) * 1.2])
        grafico(f, 400)
    with c2, st.container(border=True):
        du = df[df["ano"] >= URG_DESDE]
        titulo("Urgentes × programadas", f"Ticket médio por ano (R$) · desde {URG_DESDE}")
        f = go.Figure()
        if du["n"].sum() > 0:
            u = media(du, ["ano", "urgente"]).unstack()
            for flag, nome, cor in [(True, "Urgentes", LARANJA), (False, "Programadas", AZUL)]:
                if flag in u:
                    f.add_scatter(x=u.index.astype(str), y=u[flag], name=nome, mode="lines+markers", line=dict(color=cor, width=2.6),
                                  marker=dict(size=8, line=dict(color="#fff", width=1.5)), hovertemplate=nome + " %{x}: R$ %{y:,.0f}<extra></extra>")
        f.update_layout(hovermode="x unified")
        f.update_xaxes(type="category")
        grafico(f, 400, True)

    with st.expander("❓ Por que \"viagem cara que inclui fim de semana\" não é, sozinho, um indício"):
        fz = (share(df, "faixa_dur", "fds").reindex(FAIXAS) * 100).fillna(0)
        f = go.Figure(go.Bar(x=FAIXAS, y=fz, marker_color=[CINZA_CLARO] * 3 + [LARANJA] * 3, text=[num(v, 0) + "%" for v in fz],
                             textposition="outside", hovertemplate="%{x}: %{y:.1f}% incluem sáb/dom<extra></extra>"))
        f.update_yaxes(range=[0, 115], ticksuffix="%")
        grafico(f, 280)
        curtas = df["curta"].sum()
        st.markdown(f"Toda viagem com 7 dias ou mais inclui um fim de semana, e as viagens mais caras são justamente as longas. "
                    f"O indicador útil olha as **viagens curtas (até 3 dias)**: delas, "
                    f"**{pct(df['curta_fds'].sum() / curtas) if curtas else '—'}** começam no sábado ou domingo.")

    with st.container(border=True):
        titulo("📋 Fila de revisão", "Casos atípicos, maior valor primeiro · valores nominais · a PCDP permite conferir no Portal da Transparência")
        cs = casos_all[casos_all["outlier"] & casos_all["ano"].between(a0, a1)]
        if orgs:
            cs = cs[cs["orgao"].isin(orgs)]
        if esc != "Todos":
            cs = cs[cs["escopo"] == esc]
        if urg != "Todas":
            cs = cs[(cs["urgente"] == (urg == "Urgentes")) & (cs["ano"] >= URG_DESDE)]
        cs = cs.sort_values("total", ascending=False).head(500).copy()
        cs["urgente"] = cs["urgente"].map({True: "Sim", False: "Não"})
        cs["pcdp"] = cs["pcdp"].where(~cs["pcdp"].str.startswith("Informa", na=False), "Sigilosa")
        cs["cargo"] = cs["cargo"].where(~cs["cargo"].str.contains("sigilo", case=False, na=False), "Sigiloso")
        st.dataframe(cs[["ano", "pcdp", "orgao", "orgao_solicitante", "cargo", "inicio", "dur", "escopo", "destinos", "urgente",
                         "total", "custo_dia", "razao_mediana"]], hide_index=True, height=380, **LARGURA,
                     column_config={"ano": st.column_config.NumberColumn("Ano", format="%d"), "pcdp": "PCDP",
                                    "orgao": "Órgão superior", "orgao_solicitante": "Órgão solicitante", "cargo": "Cargo",
                                    "inicio": "Início", "dur": "Dias", "escopo": "Escopo", "destinos": "Destinos", "urgente": "Urgente",
                                    "total": st.column_config.NumberColumn("Valor", format="R$ %.2f"),
                                    "custo_dia": st.column_config.NumberColumn("Custo/dia", format="R$ %.2f"),
                                    "razao_mediana": st.column_config.NumberColumn("× pares", format="%.1f×",
                                                                                   help="Quantas vezes o custo/dia supera o típico de viagens parecidas.")})


# ============================================================================ METODOLOGIA
def pagina_metodo():
    c1, c2 = st.columns([1.15, 1], gap="medium")
    with c1, st.container(border=True):
        titulo("⭐ Modelo de dados (Star Schema)", "1 tabela fato + 5 dimensões, ligadas por chaves substitutas (sk_*) · relação muitos-para-um")
        dot = """
digraph G { rankdir=LR; bgcolor="transparent"; nodesep=0.25; ranksep=0.5;
  node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#d5dae3", fillcolor="#f8fafc", fontcolor="#0f172a"];
  edge [color="#94a3b8", arrowhead=crow, arrowsize=0.7];
  F [label="FATO_VIAGEM\\n(1 linha por viagem)\\n\\nsk_tempo · sk_orgao · sk_destino\\nsk_modal · sk_duracao\\n\\ndiárias · passagens · outros\\ndevolução · duração · urgente\\noutlier · razão p/ pares", fillcolor="#0d366b", fontcolor="white", color="#0d366b"];
  T [label="DIM_TEMPO\\ndata · ano · mês · trimestre\\ndia da semana · fator IPCA"];
  O [label="DIM_ORGAO\\nórgão superior"];
  D [label="DIM_DESTINO\\nescopo · UF · região · lat/lon"];
  M [label="DIM_MODAL\\nmeio · categoria"];
  U [label="DIM_DURACAO\\nfaixa · dias mín/máx"];
  T -> F; O -> F; D -> F; M -> F; U -> F; }
"""
        try:
            st.graphviz_chart(dot, **LARGURA)
        except TypeError:  # versões do Streamlit sem o parâmetro de largura
            st.graphviz_chart(dot)
    with c2, st.container(border=True):
        titulo("Indicadores (KPIs)", "Como cada número do painel é calculado")
        st.markdown("""
| KPI | O que mede |
|---|---|
| **Gasto total** | diárias + passagens + outros gastos |
| **Gasto real** | gasto × fator IPCA (R$ de dez/2025) |
| **Ticket médio / mediano** | gasto por viagem (média e valor central) |
| **% urgentes** | viagens urgentes ÷ viagens (desde 2021) |
| **Concentração** | parcela do gasto nas 1% viagens mais caras |
| **Casos atípicos por mil** | casos atípicos ÷ viagens × 1.000 |
| **Comparação justa** | mesmo intervalo de meses em todos os anos |
""")
    c3, c4 = st.columns(2, gap="medium")
    with c3, st.container(border=True):
        titulo("Do dado bruto ao painel")
        st.markdown(f"""
1. **Fonte:** Portal da Transparência (CGU), Viagens a Serviço, {ANOS[0]}–{ANOS[-1]} (~7 GB de CSV, 4 tabelas por ano).
2. **Limpeza:** só viagens *Realizadas*, IDs duplicados removidos, valores e datas convertidos.
3. **Enriquecimento:** duração, custo/dia, escopo e UF (texto de *Destinos*), meio principal (tabela *Trecho*).
4. **LGPD:** nome, CPF e identificador do viajante descartados.
5. **Modelagem:** Star Schema em Parquet comprimido (~50 MB, ~140× menor que os CSVs).
6. **Camada agregada para o painel:** um cubo (~400 mil linhas) derivado do Star Schema responde somas e taxas;
   só o valor de cada viagem é mantido para medianas e Pareto. Assim o painel cabe na memória do plano gratuito.
7. **Caso atípico:** log(custo/dia) acima de Q3 + 3×IQR entre viagens parecidas e valor ≥ R$ 1.000.

Todo o processo, com código e resultados, está em `tratamento_e_analise.ipynb`.
""")
    with c4, st.container(border=True):
        titulo("Limites da análise")
        st.markdown(f"""
- A base **não mede reuniões online**: a queda de 2020 coincide com a pandemia, mas não prova causa.
- Gasto alto de um órgão reflete **tamanho e missão**; compare indicadores normalizados.
- **Caso atípico ≠ irregularidade**: há justificativas possíveis (missão, comitiva, sigilo).
- O campo **urgência** só é confiável a partir de {URG_DESDE} (antes de jun/2020 vinha sempre "NÃO").
- **{ANO_PARCIAL} é parcial**: comparações usam o mesmo intervalo de meses.
- UF = 1º destino informado; viagens sigilosas não têm destino.
""")


{"resumo": pagina_resumo, "evolucao": pagina_evolucao, "orgaos": pagina_orgaos, "perfil": pagina_perfil,
 "radar": pagina_radar, "metodo": pagina_metodo}[pag]()
