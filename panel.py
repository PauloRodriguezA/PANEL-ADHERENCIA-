import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import unicodedata
import base64
import hashlib
import html
import json
import re
import os
import sqlite3
from io import BytesIO
from pathlib import Path
from urllib import error as urlerror
from urllib import request as urlrequest

# =========================================================
# CONFIG
# =========================================================

st.set_page_config(
    page_title="Panel de Adherencia Entel",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

APP_CODE_PATH = Path(__file__).resolve()
APP_HASH_PATH = APP_CODE_PATH.with_name(APP_CODE_PATH.name + ".sha256")


def verificar_integridad_codigo():
    # Seguridad SHA desactivada temporalmente mientras el panel sigue en desarrollo.
    # Cuando el panel quede finalizado, se puede reactivar el control de integridad.
    return


verificar_integridad_codigo()

# =========================================================
# RUTAS
# =========================================================

APP_DIR = Path(__file__).resolve().parent
ASSETS_DIR = APP_DIR / "assets"
PST_DIR_OFICIAL = Path(r"C:\Users\artof\OneDrive\Paulo Rodriguez\PYTHON\PST")


def resolver_pst_dir_default_panel():
    if PST_DIR_OFICIAL.exists():
        return PST_DIR_OFICIAL
    if APP_DIR.parent.name.upper() == "ST" and len(APP_DIR.parents) >= 3:
        return APP_DIR.parents[2] / "PST"
    return APP_DIR.parent / "PST"


PST_DIR = Path(os.environ.get("PST_CORREO_DIR", resolver_pst_dir_default_panel())).expanduser()

DISPONIBILIDAD_ESTADOS = ["Cumple", "No cumple", "Reclamo"]

LOGO_ECC = ASSETS_DIR / "logo-ecc-transparente.png"
LOGO_ECC_ICONO = ASSETS_DIR / "logo-ecc-icono.png"
LOGO_ECC_NEGRO = ASSETS_DIR / "logo-ecc.png"

SERVICIOS_CONFIG = {
    "IBM": {
        "archivo": "IBM_2026.xlsx",
        "disponibilidad": "DISPONIBILIDAD_IBM_2026.csv",
        "reclamos": "RECLAMOS_IBM_2026.csv",
        "pst": PST_DIR / "pst-ibm.pst",
        "logo": ASSETS_DIR / "IBM-transparente.png",
        "epa_dir": "EPA",
        "epa_db": "epa_entel.sqlite3",
        "epa_db_legacy": "epa_ibm.sqlite3",
        "participa_disponibilidad": True,
        "participa_reclamos": True,
        "participa_uso_herramienta": True,
    },
    "SAO": {
        "archivo": "SAO_2026.xlsx",
        "disponibilidad": "DISPONIBILIDAD_SAO_2026.csv",
        "reclamos": "RECLAMOS_SAO_2026.csv",
        "pst": PST_DIR / "pst-sao.pst",
        "logo": ASSETS_DIR / "LOGO-SAO-transparente.png",
        "epa_dir": "EPA-SAO",
        "epa_db": "epa_entel_sao.sqlite3",
        "epa_db_legacy": "epa_entel.sqlite3",
        "participa_disponibilidad": True,
        "participa_reclamos": True,
        "participa_uso_herramienta": True,
    },
    "ECC": {
        "archivo": "ECC_2026.xlsx",
        "disponibilidad": "",
        "reclamos": "",
        "pst": None,
        "logo": LOGO_ECC_NEGRO,
        "epa_dir": "EPA-ECC",
        "epa_db": "epa_ecc.sqlite3",
        "epa_db_legacy": "epa_ecc.sqlite3",
        "participa_disponibilidad": False,
        "participa_reclamos": False,
        "participa_uso_herramienta": True,
    },
}
SERVICIO_TODO = "Todo"
SERVICIO_OPCIONES = list(SERVICIOS_CONFIG.keys()) + [SERVICIO_TODO]


def servicio_fijo_desde_contexto():
    servicio_env = os.environ.get("PANEL_SERVICIO_FIJO", "").strip().upper()
    if servicio_env in SERVICIOS_CONFIG:
        return servicio_env
    if APP_DIR.parent.name.upper() == "ST" and APP_DIR.name.upper() in SERVICIOS_CONFIG:
        return APP_DIR.name.upper()
    return ""


SERVICIO_FIJO = servicio_fijo_desde_contexto()
MODO_GERENCIAL = not SERVICIO_FIJO


def servicio_default_gerencial():
    servicio_env = os.environ.get("PANEL_SERVICIO_DEFAULT", "").strip()
    if servicio_env in SERVICIO_OPCIONES:
        return servicio_env
    if APP_DIR.name.upper() in {"PANEL_PUBLICAR_GIT_TODO", "PUBLICAR_GIT_PANEL", "PANEL_GIT_TODO"}:
        return SERVICIO_TODO
    return "IBM"

def imagen_data_uri(ruta):
    ruta = str(ruta)
    mime = "image/png" if ruta.lower().endswith(".png") else "image/jpeg"
    with open(ruta, "rb") as img_file:
        return f"data:{mime};base64," + base64.b64encode(img_file.read()).decode("ascii")

LOGO_ECC_DATA = imagen_data_uri(LOGO_ECC)
LOGO_ECC_ICONO_DATA = imagen_data_uri(LOGO_ECC_ICONO)

with st.sidebar:
    st.markdown(
        f"""
        <div class="sidebar-logo-shell">
            <img class="sidebar-logo-img" src="{LOGO_ECC_DATA}" alt="Entel Connect" draggable="false">
        </div>
        """,
        unsafe_allow_html=True
    )

    if MODO_GERENCIAL:
        servicio_default = st.session_state.get("servicio_tecnico", servicio_default_gerencial())
        if servicio_default not in SERVICIO_OPCIONES:
            servicio_default = servicio_default_gerencial()
        st.markdown('<span class="filter-anchor filter-anchor-service"></span>', unsafe_allow_html=True)
        servicio_actual = st.pills(
            "Servicio Técnico",
            SERVICIO_OPCIONES,
            default=servicio_default,
            selection_mode="single",
            key="servicio_tecnico_pills",
            width="stretch",
        ) or servicio_default
        st.session_state["servicio_tecnico"] = servicio_actual
    else:
        servicio_actual = SERVICIO_FIJO
        st.session_state["servicio_tecnico"] = servicio_actual

SERVICIO_ACTUAL = servicio_actual
SERVICIO_COMPARATIVO = SERVICIO_ACTUAL == SERVICIO_TODO
SERVICIOS_ACTIVOS = list(SERVICIOS_CONFIG.keys()) if SERVICIO_COMPARATIVO else [SERVICIO_ACTUAL]
SERVICIO_TITULO = "IBM + SAO + ECC" if SERVICIO_COMPARATIVO else SERVICIO_ACTUAL
SERVICIO_CONFIG = SERVICIOS_CONFIG[SERVICIOS_ACTIVOS[0]]

servicio_anterior_filtros = st.session_state.get("_servicio_filtros_actual")
if servicio_anterior_filtros is not None and servicio_anterior_filtros != SERVICIO_ACTUAL:
    claves_a_limpiar = [
        key for key in st.session_state.keys()
        if key.startswith(("reg_", "tec_", "mes_", "cli_", "disp_cli_", "disp_zona_", "disp_estado_"))
        or key in {
            "disp_cli_pills", "disp_zona_pills", "disp_estado_pills", "disp_mes_pills",
            "toggle_clientes_disponibilidad_pills_empty_intent",
            "toggle_zonas_disponibilidad_pills_empty_intent",
            "toggle_estados_disponibilidad_pills_empty_intent",
            "toggle_meses_disponibilidad_pills_empty_intent",
        }
        or key.endswith(("_empty_intent", "_force_all"))
    ]
    for key in claves_a_limpiar:
        st.session_state.pop(key, None)
st.session_state["_servicio_filtros_actual"] = SERVICIO_ACTUAL

ARCHIVO = APP_DIR / str(SERVICIO_CONFIG["archivo"])
EPA_DIR = APP_DIR / str(SERVICIO_CONFIG["epa_dir"])
EPA_DB = EPA_DIR / str(SERVICIO_CONFIG["epa_db"])
EPA_DB_LEGACY = EPA_DIR / str(SERVICIO_CONFIG["epa_db_legacy"])
DISPONIBILIDAD_CACHE = APP_DIR / str(SERVICIO_CONFIG["disponibilidad"])
RECLAMOS_CACHE = APP_DIR / str(SERVICIO_CONFIG["reclamos"])
PST_DISPONIBILIDAD = SERVICIO_CONFIG["pst"]
LOGO_ST_DATA = "" if SERVICIO_COMPARATIVO else imagen_data_uri(SERVICIO_CONFIG["logo"])
LOGO_ST_CLASS = "brand-lockup-ecc" if SERVICIO_ACTUAL == "ECC" else "brand-lockup-ibm"

APP_OWNER = f"Entel Connect / {SERVICIO_TITULO} - Uso interno"
APP_SIGNATURE = f"ECONNECT-{SERVICIO_TITULO}-OPERACIONES-2026"

SAO_COORDINADORES_AUDITADOS = {
    "d.galarce@saocomputacion.cl": "Daniel Galarce",
    "pia.ossandon@saocomputacion.cl": "Pia Ossandon",
    "pia.saocomputacion@gmail.com": "Pia Ossandon",
    "angelicafuentes1@saocomputacion.cl": "Angelica Fuentes",
}
SAO_COORDINADORES_NOMBRES = {
    "daniel galarce": "Daniel Galarce",
    "pia ossandon": "Pia Ossandon",
    "angelica fuentes": "Angelica Fuentes",
}


def correo_limpio_panel(valor):
    return str(valor or "").strip().lower()


def nombre_coordinador_sao(valor_nombre="", valor_correo=""):
    correo = correo_limpio_panel(valor_correo)
    if correo in SAO_COORDINADORES_AUDITADOS:
        return SAO_COORDINADORES_AUDITADOS[correo]
    nombre_como_correo = correo_limpio_panel(valor_nombre)
    if nombre_como_correo in SAO_COORDINADORES_AUDITADOS:
        return SAO_COORDINADORES_AUDITADOS[nombre_como_correo]

    nombre = normalizar_texto_operacional(valor_nombre)
    if nombre in SAO_COORDINADORES_NOMBRES:
        return SAO_COORDINADORES_NOMBRES[nombre]
    return str(valor_nombre or "").strip()

# =====================================================
# COLORES CORPORATIVOS ENTEL
# =====================================================

AZUL = "#10069F"          # Azul corporativo
AZUL_CLARO = "#005CFF"    # Azul brillante

NARANJO = "#FF3D00"

VERDE = "#47E190"

CELESTE = "#2ECBF2"

GRIS = "#999999"

NEGRO = "#000000"

ROSADO = "#FD6C98"

BLANCO = "#FFFFFF"

FONDO = "#F7F9FC"

BORDE = "#E7ECF3"

# Uso visual separado para que los KPIs no se confundan con las series del gráfico.
KPI_TOTAL = "#2D8CFF"
KPI_CUMPLIMIENTO = CELESTE
KPI_PRIMERA_VISITA = VERDE
KPI_REVISITA = ROSADO
CHART_PALETTE = ["#168BFF", NARANJO, VERDE, ROSADO, CELESTE, "#8FA7FF"]

PLOTLY_CONFIG_SOLO_LECTURA = {
    "displayModeBar": False,
    "staticPlot": True,
    "scrollZoom": False,
    "doubleClick": False,
    "editable": False,
    "responsive": True,
}
DISPONIBILIDAD_META_PCT = 90
DISPONIBILIDAD_SLA_MIN = 30
RECLAMOS_META_CUMPLIMIENTO_PCT = 90
RECLAMOS_META_RATIO_INCUMPLIMIENTO_PCT = 100 - RECLAMOS_META_CUMPLIMIENTO_PCT
USO_HERRAMIENTA_META_PCT = 85
DISPONIBILIDAD_TABLA_MAX_FILAS = 300

# =========================================================
# CSS CORPORATIVO V3
# =========================================================

st.markdown(f"""
<style>

/*======================================================
FONDO GENERAL
======================================================*/

.stApp{{
    background:linear-gradient(180deg,#FCFCFD 0%,#F4F7FB 100%);
}}

/*======================================================
SIDEBAR
======================================================*/

section[data-testid="stSidebar"]{{
    background:linear-gradient(180deg,#000000 0%,#080808 100%);
    border-right:2px solid #10069F;
    min-width:320px !important;
    max-width:320px !important;
}}

section[data-testid="stSidebar"] img{{
    margin:auto;
    display:block;
}}

hr{{
    margin-top:12px;
    margin-bottom:18px;
    border:0;
    border-top:1px solid #E8ECF4;
}}

/*======================================================
TITULOS
======================================================*/

.titulo{{

    color:#10069F;
    font-size:64px;
    font-weight:800;
    letter-spacing:-2px;
    line-height:1;
    margin-bottom:6px;
    text-shadow:0 3px 10px rgba(16,6,159,.10);

}}

.subtitulo{{
  color:#64748B;
    font-size:20px;
    font-weight:500;
    margin-top:8px;
    letter-spacing:.2px;
}}

.linea-titulo{{
 width:230px;
    height:6px;
    background:linear-gradient(90deg,#10069F,#005CFF);
    border-radius:30px;
    margin-top:14px;
    margin-bottom:18px;
    box-shadow:0px 3px 10px rgba(16,6,159,.18);
}}

/*=============================================
TITULO SECCION KPI
=============================================*/

.kpi-section{{
    display:flex;
    align-items:center;
    gap:12px;

    margin-top:40px;
    margin-bottom:28px;

    padding-bottom:12px;

    border-bottom:2px solid #E8ECF4;
}}

.kpi-icon{{
    width:42px;
    height:42px;
    border-radius:10px;
    background:#10069F;
    color:white;
    display:flex;
    align-items:center;
    justify-content:center;
    font-size:22px;
    font-weight:900;
    box-shadow:0 4px 12px rgba(16,6,159,.20);
}}

.kpi-square{{
    width:16px;
    height:16px;
    border-radius:4px;
    background:#10069F;
}}

.kpi-title{{
    font-size:28px;

    font-weight:900;

    color:#0F172A;

    margin-top:28px;

    margin-bottom:12px;

    letter-spacing:-0.3px;
}}

.kpi-divider{{
    width:100%;

    height:4px;

    background:#10069F;

    border-radius:30px;

    margin-bottom:30px;
}}


.separador-dashboard{{
    width:100%;
    height:4px;
    margin-top:24px;
    margin-bottom:14px;

    background:linear-gradient(
        90deg,
        #10069F 0%,
        #005CFF 25%,
        #2ECBF2 50%,
        #005CFF 75%,
        #10069F 100%
    );

    border-radius:20px;

    box-shadow:0 2px 10px rgba(16,6,159,.12);
}}

.titulo-seccion{{
    color:#FFFFFF;
    font-size:22px;
    font-weight:800;
    letter-spacing:.4px;
    margin-bottom:18px;
}}

/*======================================================
KPI
======================================================*/

.kpi-card{{
    background:white;
    padding:22px;
    border-radius:18px;

    border:1px solid #EDF2F7;

    box-shadow:
        0px 8px 25px rgba(15,23,42,.05);

    transition:.25s;
}}

.kpi-card:hover{{

    transform:translateY(-4px);

    box-shadow:
        0px 18px 35px rgba(16,6,159,.12);

}}

.kpi-card h4{{

    color:#0F172A;

    font-size:24px;

    font-weight:900;

}}

.kpi-card h1{{

    font-size:52px;

    font-weight:800;

}}

.kpi-card p{{

    color:#64748B;

    font-size:19px;

}}

.disp-kpi-grid{{
    display:grid;
    grid-template-columns:repeat(auto-fit,minmax(145px,1fr));
    gap:8px;
    max-width:100%;
    margin:0 0 14px 0;
}}

.disp-kpi-card{{
    position:relative;
    min-width:0;
    height:146px;
    overflow:hidden;
    border:1px solid color-mix(in srgb,var(--accent) 54%,transparent);
    border-radius:8px;
    background:
        radial-gradient(circle at 74% 50%,color-mix(in srgb,var(--accent) 16%,transparent),transparent 28%),
        linear-gradient(135deg,rgba(6,18,34,.92),rgba(8,22,39,.84));
    box-shadow:
        0 18px 34px rgba(0,0,0,.24),
        inset 0 1px 0 rgba(255,255,255,.08);
    padding:17px 14px 14px 64px;
}}

.disp-kpi-card::before{{
    content:"";
    position:absolute;
    top:0;
    left:0;
    right:0;
    height:3px;
    background:var(--accent);
    box-shadow:0 0 18px color-mix(in srgb,var(--accent) 62%,transparent);
}}

.disp-kpi-icon{{
    position:absolute;
    left:16px;
    top:18px;
    width:36px;
    height:36px;
    display:flex;
    align-items:center;
    justify-content:center;
    border:1px solid color-mix(in srgb,var(--accent) 46%,transparent);
    border-radius:50%;
    color:var(--accent);
    background:color-mix(in srgb,var(--accent) 13%,transparent);
    font-size:25px;
    font-weight:950;
    line-height:1;
}}

.disp-kpi-title{{
    color:#EAFBFF;
    font-size:12.5px;
    font-weight:900;
    line-height:1.15;
    min-height:29px;
    white-space:normal;
    overflow:visible;
    text-overflow:clip;
}}

.disp-kpi-value-row{{
    display:flex;
    align-items:center;
    gap:6px;
    margin-top:5px;
    min-width:0;
}}

.disp-kpi-value{{
    color:var(--accent);
    font-size:clamp(40px,3.2vw,54px);
    font-weight:950;
    line-height:1.08;
    white-space:nowrap;
}}

.disp-kpi-card.is-text-value .disp-kpi-value{{
    max-width:100%;
    font-size:clamp(24px,2vw,31px);
    overflow:hidden;
    text-overflow:ellipsis;
}}

.disp-kpi-badge{{
    flex:0 0 auto;
    color:var(--accent);
    font-size:10px;
    font-weight:950;
    padding:4px 6px;
    border:1px solid color-mix(in srgb,var(--accent) 36%,transparent);
    background:color-mix(in srgb,var(--accent) 14%,transparent);
}}

.disp-kpi-subtitle{{
    margin-top:4px;
    color:#BDEFFF;
    font-size:10.2px;
    font-weight:850;
    line-height:1.18;
    white-space:normal;
}}

.ai-insight-grid{{
    display:grid;
    grid-template-columns:repeat(3,minmax(0,1fr));
    gap:10px;
    margin:2px 0 14px 0;
}}

.ai-insight-card{{
    min-height:118px;
    border:1px solid color-mix(in srgb,var(--accent) 52%,transparent);
    border-radius:8px;
    padding:14px 15px 13px;
    background:
        radial-gradient(circle at 82% 32%,color-mix(in srgb,var(--accent) 14%,transparent),transparent 30%),
        linear-gradient(135deg,rgba(6,18,34,.91),rgba(9,16,30,.84));
    box-shadow:0 16px 32px rgba(0,0,0,.20), inset 0 1px 0 rgba(255,255,255,.08);
}}

.ai-insight-kicker{{
    color:var(--accent);
    font-size:10px;
    font-weight:950;
    letter-spacing:.05em;
    text-transform:uppercase;
    margin-bottom:6px;
}}

.ai-insight-title{{
    color:#F4FCFF;
    font-size:17px;
    font-weight:950;
    line-height:1.12;
    margin-bottom:7px;
}}

.ai-insight-body{{
    color:#BDEFFF;
    font-size:12px;
    font-weight:780;
    line-height:1.33;
}}

.no-data-shell{{
    min-height:250px;
    display:flex;
    align-items:center;
    justify-content:center;
    gap:18px;
    padding:34px 30px;
    margin:10px 0 18px;
    border:1px solid rgba(46,203,242,.32);
    border-radius:8px;
    background:
        linear-gradient(135deg,rgba(6,18,34,.88),rgba(8,20,38,.76) 58%,rgba(255,61,0,.055));
    box-shadow:0 18px 36px rgba(0,0,0,.18), inset 0 1px 0 rgba(255,255,255,.08);
}}

.no-data-logo-wrap{{
    width:72px;
    height:72px;
    display:flex;
    align-items:center;
    justify-content:center;
    border:1px solid rgba(46,203,242,.34);
    border-radius:8px;
    background:linear-gradient(145deg,rgba(0,0,0,.72),rgba(7,18,34,.84));
    box-shadow:0 0 0 1px rgba(255,255,255,.05),0 12px 24px rgba(0,0,0,.22);
    flex:0 0 auto;
}}

.no-data-logo-wrap img{{
    width:44px;
    height:auto;
    filter:drop-shadow(0 0 8px rgba(46,203,242,.34));
}}

.no-data-copy{{
    min-width:0;
}}

.no-data-kicker{{
    color:{CELESTE};
    font-size:11px;
    font-weight:950;
    letter-spacing:.08em;
    text-transform:uppercase;
    margin-bottom:6px;
}}

.no-data-title{{
    color:#F4FCFF;
    font-size:24px;
    font-weight:950;
    line-height:1.08;
}}

.no-data-detail{{
    color:#BDEFFF;
    font-size:13px;
    font-weight:780;
    line-height:1.35;
    margin-top:8px;
    max-width:760px;
}}

@media (max-width: 980px){{
    .ai-insight-grid{{
        grid-template-columns:1fr;
    }}
    .no-data-shell{{
        flex-direction:column;
        text-align:center;
    }}
}}

div[data-testid="stTabs"] [data-baseweb="tab-list"]{{
    gap:8px !important;
    border-bottom:1px solid rgba(148,163,184,.18) !important;
    overflow-x:auto !important;
    padding-bottom:0 !important;
}}

div[data-testid="stTabs"] [data-baseweb="tab"]{{
    min-height:38px !important;
    padding:0 13px !important;
    border:1px solid transparent !important;
    border-bottom:0 !important;
    border-radius:8px 8px 0 0 !important;
    background:rgba(255,255,255,.018) !important;
    transition:background .16s ease,border-color .16s ease,color .16s ease;
}}

div[data-testid="stTabs"] [data-baseweb="tab"] p{{
    color:#EAFBFF !important;
    font-size:13px !important;
    font-weight:900 !important;
}}

div[data-testid="stTabs"] [data-baseweb="tab"]:hover{{
    background:rgba(255,255,255,.065) !important;
    border-color:rgba(255,255,255,.16) !important;
}}

div[data-testid="stTabs"] [data-baseweb="tab"][aria-selected="true"]{{
    background:linear-gradient(180deg,rgba(255,61,22,.16),rgba(255,61,22,.025)) !important;
    border-color:rgba(255,61,22,.48) !important;
    box-shadow:inset 0 -3px 0 {NARANJO};
}}

div[data-testid="stTabs"] [data-baseweb="tab"][aria-selected="true"] p{{
    color:#FFFFFF !important;
}}

.disp-kpi-progress{{
    position:absolute;
    left:72px;
    right:18px;
    bottom:13px;
    height:5px;
    background:rgba(143,239,255,.14);
}}

.disp-kpi-progress-fill{{
    height:100%;
    width:var(--progress);
    max-width:100%;
    background:var(--accent);
    box-shadow:0 0 14px color-mix(in srgb,var(--accent) 52%,transparent);
}}

/*======================================================
CONTENEDORES GRAFICOS
======================================================*/

.chart-card{{

    background:white;

    border-radius:20px;

    padding:18px;

    border:1px solid #EEF2F7;

    box-shadow:
        0px 8px 25px rgba(15,23,42,.05);

}}

/*======================================================
TABLAS
======================================================*/

thead tr th{{

    background:{AZUL};

    color:white !important;

    font-size:15px;

}}

tbody tr:nth-child(even){{
    background:#FAFBFD;
}}

tbody tr:hover{{
    background:#EEF5FF;
}}

/*======================================================
BOTONES
======================================================*/

.stButton button{{

    border-radius:12px;

    background:{AZUL};

    color:white;

    border:none;

}}

.stButton button:hover{{

    background:{AZUL_CLARO};

}}

/*======================================================
SELECTORES PREMIUM ENTEL
======================================================*/

div[data-baseweb="select"]{{

    min-height:58px;
    border-radius:18px !important;
    border:2px solid #10069F !important;
    background:linear-gradient(180deg,#FFFFFF,#F6F9FF) !important;
    box-shadow:0 8px 20px rgba(16,6,159,.12);
    font-size:16px;
    font-weight:900;
}}

div[data-baseweb="select"]:hover{{
    border:2px solid #2ECBF2 !important;
    box-shadow:0 10px 25px rgba(46,203,242,.25);
}}

div[data-baseweb="tag"]{{
    background:linear-gradient(90deg,#10069F,#005CFF) !important;
    color:white !important;
    border:none !important;
    border-radius:18px !important;
    font-size:15px !important;
    font-weight:700 !important;
    padding:6px 10px !important;
}}



/* Sidebar checkbox style */
div[data-testid="stCheckbox"]{{padding-bottom:2px;}}
div[data-testid="stCheckbox"] label{{color:white !important;font-weight:700 !important;font-size:15px !important;}}

/* ===== EXPANDER PREMIUM ===== */
div[data-testid="stExpander"]{{
    background:#0F1117 !important;
    border:1px solid #1F3B8F !important;
    border-radius:12px !important;
    margin-bottom:12px !important;
}}
div[data-testid="stExpander"] details summary,
div[data-testid="stExpander"] details summary:hover,
div[data-testid="stExpander"] details summary:focus,
div[data-testid="stExpander"] details summary:active{{
    color:#FFFFFF !important;
    background:#0F1117 !important;
}}

div[data-testid="stExpander"] details summary *,
div[data-testid="stExpander"] details summary p,
div[data-testid="stExpander"] details summary span,
div[data-testid="stExpander"] details summary svg{{
    color:#FFFFFF !important;
    fill:#FFFFFF !important;
    stroke:#FFFFFF !important;
    opacity:1 !important;
    font-size:20px !important;
    font-weight:800 !important;
}}
div[data-testid="stExpander"] svg{{
    width:30px !important;
    height:30px !important;
    color:#FFFFFF !important;
}}
div[data-testid="stExpanderContent"]{{
    background:#0F1117 !important;
    border-radius:0 0 12px 12px !important;
    padding:10px !important;
}}

/* Todo el texto del contenido en blanco */
div[data-testid="stExpanderContent"] *,
div[data-testid="stCheckbox"] label,
div[data-testid="stCheckbox"] p,
div[data-testid="stCheckbox"] span{{
    color:#FFFFFF !important;
    font-size:15px !important;
    font-weight:700 !important;
}}

/* Etiqueta del buscador */
div[data-testid="stTextInput"] label{{
    color:#FFFFFF !important;
}}

/* Caja del buscador */
div[data-testid="stTextInput"] input{{
    color:#FFFFFF !important;
    background:#1A1A1A !important;
    border:1px solid #3B82F6 !important;
}}

div[data-testid="stTextInput"] input::placeholder{{
    color:#BDBDBD !important;
}}

/*======================================================
SIDEBAR PREMIUM CONTROL CENTER
======================================================*/

section[data-testid="stSidebar"]{{
    background:
        linear-gradient(180deg,#050507 0%,#080A12 46%,#000000 100%) !important;
    border-right:1px solid rgba(46,203,242,.45) !important;
    box-shadow:18px 0 40px rgba(16,6,159,.20);
}}

section[data-testid="stSidebar"] > div:first-child{{
    padding-left:16px;
    padding-right:16px;
}}

.filter-hero{{
    position:relative;
    padding:17px 16px 15px 16px;
    margin:4px 0 16px 0;
    background:
        linear-gradient(145deg,rgba(16,6,159,.62),rgba(0,92,255,.28) 48%,rgba(46,203,242,.12));
    border:1px solid rgba(46,203,242,.40);
    box-shadow:
        0 18px 36px rgba(0,0,0,.32),
        inset 0 1px 0 rgba(255,255,255,.18);
}}

.filter-hero::after{{
    content:"";
    position:absolute;
    left:14px;
    right:14px;
    bottom:0;
    height:3px;
    background:linear-gradient(90deg,{VERDE},{CELESTE},{ROSADO});
}}

.filter-eyebrow{{
    color:{CELESTE};
    font-size:11px;
    font-weight:900;
    letter-spacing:.12em;
    text-transform:uppercase;
    margin-bottom:5px;
}}

.filter-title{{
    color:#FFFFFF;
    font-size:24px;
    font-weight:900;
    line-height:1.05;
    letter-spacing:-.2px;
}}

.filter-subtitle{{
    color:#C7D2FE;
    font-size:12px;
    font-weight:700;
    margin-top:8px;
}}

.filter-stat-row{{
    display:grid;
    grid-template-columns:1fr 1fr;
    gap:8px;
    margin-top:12px;
}}

.filter-stat{{
    padding:9px 10px;
    background:rgba(255,255,255,.08);
    border:1px solid rgba(255,255,255,.12);
}}

.filter-stat b{{
    display:block;
    color:#FFFFFF;
    font-size:18px;
    line-height:1;
}}

.filter-stat span{{
    display:block;
    color:#CBD5E1;
    font-size:10px;
    font-weight:800;
    margin-top:4px;
}}

section[data-testid="stSidebar"] hr{{
    border-top:1px solid rgba(148,163,184,.22) !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"]{{
    background:linear-gradient(180deg,rgba(15,17,27,.98),rgba(8,10,18,.98)) !important;
    border:1px solid rgba(46,203,242,.36) !important;
    box-shadow:
        0 14px 26px rgba(0,0,0,.32),
        inset 0 1px 0 rgba(255,255,255,.08);
    border-radius:10px !important;
    overflow:hidden;
    margin-bottom:14px !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"]:hover{{
    border-color:rgba(71,225,144,.55) !important;
    box-shadow:
        0 16px 30px rgba(0,0,0,.38),
        0 0 0 1px rgba(71,225,144,.10),
        inset 0 1px 0 rgba(255,255,255,.10);
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary,
section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary:hover,
section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary:focus,
section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary:active{{
    min-height:50px;
    padding:12px 14px !important;
    background:
        linear-gradient(90deg,rgba(16,6,159,.42),rgba(46,203,242,.10)) !important;
    border-bottom:1px solid rgba(148,163,184,.22);
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary *{{
    color:#FFFFFF !important;
    font-size:17px !important;
    font-weight:900 !important;
    letter-spacing:.01em;
}}

section[data-testid="stSidebar"] div[data-testid="stExpanderContent"]{{
    background:linear-gradient(180deg,rgba(10,12,20,.98),rgba(6,8,14,.98)) !important;
    padding:12px 12px 14px 12px !important;
}}

section[data-testid="stSidebar"] div[data-testid="stButton"] button{{
    min-height:34px;
    border-radius:8px !important;
    background:linear-gradient(135deg,{AZUL},{AZUL_CLARO}) !important;
    border:1px solid rgba(46,203,242,.42) !important;
    color:#FFFFFF !important;
    box-shadow:0 8px 18px rgba(0,92,255,.20);
    font-size:12px !important;
    font-weight:900 !important;
}}

section[data-testid="stSidebar"] div[data-testid="stButton"] button:hover{{
    background:linear-gradient(135deg,{AZUL_CLARO},{CELESTE}) !important;
    border-color:rgba(71,225,144,.65) !important;
    transform:translateY(-1px);
}}

section[data-testid="stSidebar"] div[data-testid="stTextInput"] label p{{
    color:#DDE7FF !important;
    font-size:12px !important;
    font-weight:900 !important;
}}

section[data-testid="stSidebar"] div[data-testid="stTextInput"] input{{
    min-height:42px;
    color:#FFFFFF !important;
    background:linear-gradient(180deg,#101827,#0A0F1B) !important;
    border:1px solid rgba(46,203,242,.62) !important;
    box-shadow:
        inset 0 1px 0 rgba(255,255,255,.08),
        0 10px 20px rgba(0,0,0,.24);
    font-weight:800 !important;
}}

section[data-testid="stSidebar"] div[data-testid="stTextInput"] input:focus{{
    border-color:{VERDE} !important;
    box-shadow:0 0 0 2px rgba(71,225,144,.18), 0 10px 22px rgba(0,0,0,.28);
}}

section[data-testid="stSidebar"] div[data-testid="stCheckbox"]{{
    padding:5px 7px !important;
    margin:3px 0 !important;
    background:rgba(255,255,255,.035);
    border:1px solid rgba(255,255,255,.055);
    border-radius:9px;
}}

section[data-testid="stSidebar"] div[data-testid="stCheckbox"]:hover{{
    background:rgba(46,203,242,.08);
    border-color:rgba(46,203,242,.36);
}}

section[data-testid="stSidebar"] div[data-testid="stCheckbox"] label,
section[data-testid="stSidebar"] div[data-testid="stCheckbox"] label p,
section[data-testid="stSidebar"] div[data-testid="stCheckbox"] label span{{
    color:#FFFFFF !important;
    font-size:13px !important;
    font-weight:850 !important;
    line-height:1.25 !important;
}}

.filter-mini-note{{
    color:#94A3B8;
    font-size:11px;
    font-weight:800;
    margin:3px 0 10px 0;
}}

/*======================================================
SIDEBAR PREMIUM V2 - COMMAND CENTER
======================================================*/

section[data-testid="stSidebar"]{{
    background:
        radial-gradient(circle at 12% 0%,rgba(46,203,242,.22),transparent 28%),
        radial-gradient(circle at 100% 12%,rgba(253,108,152,.12),transparent 24%),
        linear-gradient(180deg,#060711 0%,#090B14 48%,#020205 100%) !important;
    border-right:1px solid rgba(46,203,242,.42) !important;
}}

section[data-testid="stSidebar"] > div:first-child{{
    padding:20px 16px 24px 16px;
}}

.filter-hero{{
    padding:0 !important;
    margin:8px 0 18px 0 !important;
    background:transparent !important;
    border:0 !important;
    box-shadow:none !important;
}}

.filter-hero::after{{
    display:none !important;
}}

.control-glass{{
    position:relative;
    overflow:hidden;
    padding:18px 16px 16px 16px;
    background:
        linear-gradient(145deg,rgba(255,255,255,.12),rgba(255,255,255,.045)),
        linear-gradient(135deg,rgba(16,6,159,.55),rgba(0,92,255,.22) 58%,rgba(46,203,242,.16));
    border:1px solid rgba(255,255,255,.18);
    border-radius:18px;
    box-shadow:
        0 22px 42px rgba(0,0,0,.34),
        inset 0 1px 0 rgba(255,255,255,.22);
}}

.control-glass::before{{
    content:"";
    position:absolute;
    inset:-45% -20% auto auto;
    width:150px;
    height:150px;
    background:radial-gradient(circle,rgba(71,225,144,.35),transparent 62%);
}}

.control-glass::after{{
    content:"";
    position:absolute;
    left:16px;
    right:16px;
    bottom:0;
    height:3px;
    background:linear-gradient(90deg,{VERDE},{CELESTE},{ROSADO});
    border-radius:20px 20px 0 0;
}}

.filter-eyebrow{{
    position:relative;
    width:max-content;
    padding:5px 9px;
    color:#FFFFFF !important;
    background:rgba(0,0,0,.25);
    border:1px solid rgba(255,255,255,.15);
    border-radius:999px;
    font-size:10px !important;
    font-weight:900 !important;
    letter-spacing:.14em !important;
    text-transform:uppercase;
}}

.filter-title{{
    position:relative;
    margin-top:12px;
    color:#FFFFFF !important;
    font-size:25px !important;
    font-weight:950 !important;
    line-height:1.05 !important;
    letter-spacing:-.35px !important;
}}

.filter-subtitle{{
    position:relative;
    color:#DCE6FF !important;
    font-size:12px !important;
    font-weight:750 !important;
    margin-top:7px !important;
}}

.filter-status-pill{{
    display:flex;
    align-items:center;
    gap:10px;
    margin:6px 0 18px 0;
    padding:11px 12px;
    background:linear-gradient(90deg,rgba(46,203,242,.13),rgba(255,255,255,.035));
    border:1px solid rgba(46,203,242,.24);
    border-radius:13px;
    box-shadow:inset 0 1px 0 rgba(255,255,255,.08);
}}

.filter-status-pill svg{{
    width:19px;
    height:19px;
    stroke:{CELESTE};
    stroke-width:2.4;
}}

.filter-status-pill b{{
    display:block;
    color:#FFFFFF;
    font-size:12px;
    font-weight:950;
    letter-spacing:.08em;
    text-transform:uppercase;
}}

.filter-status-pill span{{
    display:block;
    color:#90A6C8;
    font-size:10.5px;
    font-weight:850;
    margin-top:2px;
}}

.filter-stat-row{{
    position:relative;
    display:grid !important;
    grid-template-columns:1fr 1fr;
    gap:9px !important;
    margin-top:14px !important;
}}

.filter-stat{{
    padding:10px 11px !important;
    background:rgba(3,7,18,.40) !important;
    border:1px solid rgba(255,255,255,.14) !important;
    border-radius:13px !important;
    box-shadow:inset 0 1px 0 rgba(255,255,255,.08);
}}

.filter-stat b{{
    color:#FFFFFF !important;
    font-size:20px !important;
    font-weight:950 !important;
    letter-spacing:-.3px;
}}

.filter-stat span{{
    color:#AFC4FF !important;
    font-size:10px !important;
    font-weight:900 !important;
    letter-spacing:.06em;
    text-transform:uppercase;
}}

.filter-section-label{{
    display:flex;
    align-items:center;
    gap:10px;
    margin:17px 0 8px 0;
    color:#EAF2FF;
    font-size:11px;
    font-weight:950;
    letter-spacing:.13em;
    text-transform:uppercase;
}}

.filter-section-label span{{
    display:inline-flex;
    align-items:center;
    justify-content:center;
    width:24px;
    height:24px;
    border-radius:8px;
    color:#041015;
    background:linear-gradient(135deg,{VERDE},{CELESTE});
    box-shadow:0 10px 18px rgba(46,203,242,.18);
    font-size:11px;
    letter-spacing:0;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"]{{
    background:rgba(6,9,18,.74) !important;
    border:1px solid rgba(148,163,184,.20) !important;
    border-radius:16px !important;
    box-shadow:
        0 18px 35px rgba(0,0,0,.30),
        inset 0 1px 0 rgba(255,255,255,.065);
    backdrop-filter:blur(18px);
    margin-bottom:14px !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"]:hover{{
    border-color:rgba(46,203,242,.48) !important;
    box-shadow:
        0 20px 38px rgba(0,0,0,.36),
        0 0 0 1px rgba(46,203,242,.08),
        inset 0 1px 0 rgba(255,255,255,.08);
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary,
section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary:hover,
section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary:focus,
section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary:active{{
    min-height:48px !important;
    padding:12px 14px !important;
    background:
        linear-gradient(90deg,rgba(255,255,255,.075),rgba(255,255,255,.025)) !important;
    border-bottom:1px solid rgba(148,163,184,.16) !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary *{{
    color:#FFFFFF !important;
    font-size:15px !important;
    font-weight:950 !important;
    letter-spacing:.04em !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] svg{{
    color:{CELESTE} !important;
    stroke:{CELESTE} !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpanderContent"]{{
    background:rgba(3,6,14,.58) !important;
    padding:12px !important;
}}

section[data-testid="stSidebar"] div[data-testid="stButton"] button{{
    min-height:32px !important;
    border-radius:10px !important;
    background:rgba(255,255,255,.075) !important;
    border:1px solid rgba(46,203,242,.32) !important;
    color:#F8FAFC !important;
    box-shadow:inset 0 1px 0 rgba(255,255,255,.10) !important;
    font-size:11px !important;
    font-weight:950 !important;
    letter-spacing:.04em !important;
    text-transform:uppercase;
}}

section[data-testid="stSidebar"] div[data-testid="stButton"] button:hover{{
    background:linear-gradient(135deg,rgba(16,6,159,.72),rgba(0,92,255,.56)) !important;
    border-color:rgba(71,225,144,.55) !important;
    transform:translateY(-1px);
}}

section[data-testid="stSidebar"] div[data-testid="stTextInput"] label p{{
    color:#BFD2FF !important;
    font-size:11px !important;
    font-weight:950 !important;
    letter-spacing:.04em;
    text-transform:uppercase;
}}

section[data-testid="stSidebar"] div[data-testid="stTextInput"] input{{
    min-height:42px !important;
    border-radius:12px !important;
    color:#FFFFFF !important;
    background:
        linear-gradient(180deg,rgba(15,23,42,.94),rgba(8,12,22,.94)) !important;
    border:1px solid rgba(46,203,242,.44) !important;
    box-shadow:
        inset 0 1px 0 rgba(255,255,255,.08),
        0 12px 22px rgba(0,0,0,.22) !important;
    font-weight:850 !important;
}}

section[data-testid="stSidebar"] div[data-testid="stTextInput"] input:focus{{
    border-color:{VERDE} !important;
    box-shadow:0 0 0 2px rgba(71,225,144,.16), 0 12px 24px rgba(0,0,0,.28) !important;
}}

section[data-testid="stSidebar"] div[data-testid="stCheckbox"]{{
    position:relative;
    padding:8px 9px 8px 11px !important;
    margin:5px 0 !important;
    background:
        linear-gradient(90deg,rgba(255,255,255,.075),rgba(255,255,255,.030)) !important;
    border:1px solid rgba(255,255,255,.075) !important;
    border-radius:12px !important;
    box-shadow:inset 0 1px 0 rgba(255,255,255,.05);
}}

section[data-testid="stSidebar"] div[data-testid="stCheckbox"]::before{{
    content:"";
    position:absolute;
    left:0;
    top:9px;
    bottom:9px;
    width:3px;
    border-radius:0 8px 8px 0;
    background:linear-gradient(180deg,{CELESTE},{VERDE});
    opacity:.78;
}}

section[data-testid="stSidebar"] div[data-testid="stCheckbox"]:hover{{
    background:
        linear-gradient(90deg,rgba(46,203,242,.14),rgba(255,255,255,.045)) !important;
    border-color:rgba(46,203,242,.32) !important;
}}

section[data-testid="stSidebar"] div[data-testid="stCheckbox"] label,
section[data-testid="stSidebar"] div[data-testid="stCheckbox"] label p,
section[data-testid="stSidebar"] div[data-testid="stCheckbox"] label span{{
    color:#F8FAFC !important;
    font-size:12.5px !important;
    font-weight:900 !important;
    line-height:1.25 !important;
}}

section[data-testid="stSidebar"] div[data-testid="stCheckbox"] input[type="checkbox"]{{
    accent-color:{VERDE} !important;
}}

.filter-mini-note{{
    color:#91A6C8 !important;
    font-size:10.5px !important;
    font-weight:900 !important;
    letter-spacing:.05em;
    text-transform:uppercase;
    margin:6px 0 10px 1px !important;
}}

/*======================================================
SIDEBAR PREMIUM V3 - EXECUTIVE FILTERS
======================================================*/

.control-glass{{
    padding:14px 14px 13px 14px !important;
    background:
        linear-gradient(135deg,rgba(16,6,159,.50),rgba(0,92,255,.18)),
        linear-gradient(180deg,rgba(255,255,255,.10),rgba(255,255,255,.035)) !important;
    border:1px solid rgba(46,203,242,.34) !important;
    border-radius:14px !important;
    box-shadow:
        0 16px 30px rgba(0,0,0,.26),
        inset 0 1px 0 rgba(255,255,255,.18) !important;
}}

.control-glass::before{{
    display:none !important;
}}

.filter-eyebrow{{
    padding:0 !important;
    background:transparent !important;
    border:0 !important;
    color:{CELESTE} !important;
    font-size:10px !important;
    letter-spacing:.16em !important;
}}

.filter-title{{
    margin-top:6px !important;
    font-size:22px !important;
    letter-spacing:-.25px !important;
}}

.filter-subtitle{{
    margin-top:5px !important;
    font-size:11px !important;
    color:#C9D7FF !important;
}}

.filter-stat-row{{
    display:none !important;
}}

.filter-section-label{{
    display:grid !important;
    grid-template-columns:38px 1fr !important;
    align-items:center !important;
    gap:11px !important;
    margin:18px 0 9px 0 !important;
    color:#FFFFFF !important;
    letter-spacing:0 !important;
    text-transform:none !important;
}}

.filter-section-label .filter-icon{{
    display:flex !important;
    align-items:center !important;
    justify-content:center !important;
    width:38px !important;
    height:38px !important;
    border-radius:12px !important;
    color:#061015 !important;
    background:linear-gradient(135deg,{VERDE},{CELESTE}) !important;
    box-shadow:
        0 12px 22px rgba(46,203,242,.22),
        inset 0 1px 0 rgba(255,255,255,.40) !important;
}}

.filter-section-label .filter-icon svg{{
    width:20px !important;
    height:20px !important;
    stroke:#061015 !important;
    stroke-width:2.6 !important;
}}

.filter-label-copy b{{
    display:block;
    color:#FFFFFF;
    font-size:13px;
    font-weight:950;
    letter-spacing:.07em;
    text-transform:uppercase;
    line-height:1.05;
}}

.filter-label-copy small{{
    display:block;
    color:#90A6C8;
    font-size:10.5px;
    font-weight:850;
    margin-top:4px;
    letter-spacing:.02em;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"]{{
    border-radius:12px !important;
    margin-bottom:10px !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary,
section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary:hover,
section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary:focus,
section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary:active{{
    min-height:44px !important;
    padding:11px 13px !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary *{{
    font-size:13px !important;
    letter-spacing:.03em !important;
}}

/*======================================================
SIDEBAR FINAL CLEAN OVERRIDE
======================================================*/

.filter-status-pill,
.filter-hero,
.control-glass{{
    display:none !important;
}}

section[data-testid="stSidebar"]{{
    background:linear-gradient(180deg,#050812 0%,#080B12 58%,#030407 100%) !important;
    border-right:1px solid rgba(46,203,242,.30) !important;
    --primary-color:{CELESTE} !important;
}}

section[data-testid="stSidebar"] > div:first-child{{
    padding:20px 18px 22px 18px !important;
}}

.filter-section-label{{
    grid-template-columns:30px 1fr !important;
    gap:10px !important;
    margin:16px 0 7px 0 !important;
}}

.filter-section-label .filter-icon{{
    width:30px !important;
    height:30px !important;
    border-radius:9px !important;
    background:linear-gradient(135deg,{CELESTE},{VERDE}) !important;
    box-shadow:none !important;
}}

.filter-section-label .filter-icon svg{{
    width:16px !important;
    height:16px !important;
}}

.filter-label-copy b{{
    font-size:12px !important;
    letter-spacing:.08em !important;
}}

.filter-label-copy small{{
    font-size:10px !important;
    color:#8EA0BD !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"]{{
    background:rgba(12,16,25,.88) !important;
    border:1px solid rgba(148,163,184,.24) !important;
    border-radius:10px !important;
    box-shadow:none !important;
    margin-bottom:15px !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary,
section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary:hover,
section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary:focus,
section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary:active{{
    min-height:42px !important;
    padding:10px 12px !important;
    background:rgba(255,255,255,.025) !important;
    border-bottom:1px solid rgba(148,163,184,.18) !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary *{{
    color:#F8FAFC !important;
    font-size:12px !important;
    font-weight:850 !important;
    letter-spacing:.02em !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpanderContent"]{{
    background:#070A11 !important;
    padding:12px 12px 14px 12px !important;
}}

section[data-testid="stSidebar"] div[data-testid="stButton"] button{{
    min-height:31px !important;
    border-radius:8px !important;
    background:#111827 !important;
    border:1px solid rgba(46,203,242,.35) !important;
    color:#EAF2FF !important;
    box-shadow:none !important;
    font-size:11px !important;
    font-weight:850 !important;
}}

section[data-testid="stSidebar"] div[data-testid="stButton"] button:hover{{
    background:#142033 !important;
    border-color:{CELESTE} !important;
    transform:none !important;
}}

section[data-testid="stSidebar"] div[data-testid="stTextInput"] input{{
    background:#0B1220 !important;
    border:1px solid rgba(46,203,242,.38) !important;
    box-shadow:none !important;
    border-radius:9px !important;
}}

section[data-testid="stSidebar"] div[data-testid="stCheckbox"]{{
    background:transparent !important;
    border:0 !important;
    border-radius:0 !important;
    box-shadow:none !important;
    margin:2px 0 !important;
    padding:3px 0 !important;
}}

section[data-testid="stSidebar"] div[data-testid="stCheckbox"]::before{{
    display:none !important;
}}

section[data-testid="stSidebar"] div[data-testid="stCheckbox"]:hover{{
    background:transparent !important;
    border-color:transparent !important;
}}

section[data-testid="stSidebar"] div[data-testid="stCheckbox"] label,
section[data-testid="stSidebar"] div[data-testid="stCheckbox"] label p,
section[data-testid="stSidebar"] div[data-testid="stCheckbox"] label span,
section[data-testid="stSidebar"] div[data-testid="stCheckbox"] label div{{
    background:transparent !important;
    box-shadow:none !important;
    color:#F8FAFC !important;
}}

section[data-testid="stSidebar"] div[data-testid="stCheckbox"] label p{{
    font-size:12px !important;
    font-weight:750 !important;
    line-height:1.25 !important;
}}

section[data-testid="stSidebar"] div[data-testid="stCheckbox"] input[type="checkbox"]{{
    accent-color:{CELESTE} !important;
}}

.filter-mini-note{{
    color:#8EA0BD !important;
    font-size:10px !important;
    margin:6px 0 8px 0 !important;
}}

/*======================================================
SIDEBAR FUTURISTA EJECUTIVO - FINAL
======================================================*/

section[data-testid="stSidebar"]{{
    background:
        linear-gradient(180deg,rgba(5,9,20,.98) 0%,rgba(6,11,19,.98) 54%,rgba(3,5,10,1) 100%),
        radial-gradient(circle at 85% 8%,rgba(46,203,242,.16),transparent 30%) !important;
    border-right:1px solid rgba(46,203,242,.28) !important;
    box-shadow:18px 0 38px rgba(2,6,23,.22);
    --primary-color:{CELESTE} !important;
}}

section[data-testid="stSidebar"]::before{{
    content:"";
    position:absolute;
    inset:0;
    pointer-events:none;
    background:
        linear-gradient(rgba(255,255,255,.028) 1px,transparent 1px),
        linear-gradient(90deg,rgba(255,255,255,.020) 1px,transparent 1px);
    background-size:28px 28px;
    mask-image:linear-gradient(180deg,rgba(0,0,0,.70),rgba(0,0,0,.16));
}}

section[data-testid="stSidebar"] img{{
    background:transparent !important;
    box-shadow:none !important;
    border-radius:0 !important;
    margin-bottom:14px !important;
}}

.filter-section-label{{
    position:relative;
    grid-template-columns:32px 1fr !important;
    gap:11px !important;
    margin:18px 0 8px 0 !important;
    padding-left:1px !important;
}}

.filter-section-label .filter-icon{{
    width:32px !important;
    height:32px !important;
    border-radius:10px !important;
    background:
        linear-gradient(145deg,rgba(46,203,242,.95),rgba(71,225,144,.82)) !important;
    box-shadow:
        0 8px 18px rgba(46,203,242,.13),
        inset 0 1px 0 rgba(255,255,255,.44) !important;
}}

.filter-label-copy b{{
    color:#F8FAFC !important;
    font-size:12px !important;
    font-weight:900 !important;
    letter-spacing:.09em !important;
}}

.filter-label-copy small{{
    color:#9AAECF !important;
    font-size:10px !important;
    font-weight:800 !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"]{{
    position:relative;
    overflow:hidden;
    background:linear-gradient(180deg,rgba(13,18,29,.86),rgba(8,12,20,.92)) !important;
    border:1px solid rgba(148,163,184,.22) !important;
    border-radius:12px !important;
    box-shadow:
        0 10px 24px rgba(0,0,0,.20),
        inset 0 1px 0 rgba(255,255,255,.045) !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"]::before{{
    content:"";
    position:absolute;
    left:0;
    top:0;
    bottom:0;
    width:3px;
    background:rgba(148,163,184,.24);
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"]:has(input:checked){{
    background:
        linear-gradient(180deg,rgba(13,28,43,.96),rgba(8,17,29,.96)) !important;
    border-color:rgba(46,203,242,.42) !important;
    box-shadow:
        0 14px 28px rgba(2,6,23,.30),
        inset 0 1px 0 rgba(255,255,255,.075),
        inset 0 0 0 1px rgba(46,203,242,.055) !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"]:has(input:checked)::before{{
    background:linear-gradient(180deg,{CELESTE},{VERDE});
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"]:has(details[open]){{
    border-color:rgba(71,225,144,.42) !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary,
section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary:hover,
section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary:focus,
section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary:active{{
    background:rgba(255,255,255,.018) !important;
    border-bottom:1px solid rgba(148,163,184,.14) !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"]:has(input:checked) details summary{{
    background:linear-gradient(90deg,rgba(46,203,242,.105),rgba(255,255,255,.020)) !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpanderContent"]{{
    background:linear-gradient(180deg,rgba(5,9,16,.72),rgba(4,7,12,.88)) !important;
}}

section[data-testid="stSidebar"] div[data-testid="stButton"] button{{
    background:linear-gradient(180deg,rgba(16,24,39,.96),rgba(10,15,25,.98)) !important;
    border:1px solid rgba(46,203,242,.34) !important;
    color:#EAF6FF !important;
}}

section[data-testid="stSidebar"] div[data-testid="stButton"] button:hover{{
    background:linear-gradient(180deg,rgba(18,32,48,.98),rgba(12,20,33,.98)) !important;
    border-color:rgba(71,225,144,.46) !important;
}}

section[data-testid="stSidebar"] div[data-testid="stCheckbox"]{{
    padding:6px 8px !important;
    margin:4px 0 !important;
    border-radius:9px !important;
    background:rgba(12,18,29,.72) !important;
    border:1px solid rgba(148,163,184,.18) !important;
}}

section[data-testid="stSidebar"] div[data-testid="stCheckbox"]:has(input:checked){{
    background:
        linear-gradient(90deg,rgba(46,203,242,.38),rgba(71,225,144,.24)) !important;
    border:1px solid rgba(46,203,242,.55) !important;
    box-shadow:
        inset 3px 0 0 {CELESTE},
        inset 0 1px 0 rgba(255,255,255,.10),
        0 8px 18px rgba(2,6,23,.18) !important;
}}

section[data-testid="stSidebar"] div[data-testid="stCheckbox"] input[type="checkbox"]{{
    accent-color:{CELESTE} !important;
}}

section[data-testid="stSidebar"] div[data-testid="stCheckbox"] label p{{
    color:#F5F8FF !important;
    font-size:12px !important;
    font-weight:760 !important;
}}

section[data-testid="stSidebar"] div[data-testid="stCheckbox"]:has(input:checked) label p{{
    color:#FFFFFF !important;
    font-weight:900 !important;
}}

/*======================================================
DASHBOARD FUTURISTA RESPONSIVO - FINAL
======================================================*/

.block-container{{
    max-width:100% !important;
    padding-top:1.0rem !important;
    padding-left:1.35rem !important;
    padding-right:1.35rem !important;
    padding-bottom:.8rem !important;
}}

.stApp{{
    background:
        radial-gradient(circle at 88% 4%,rgba(46,203,242,.16),transparent 28%),
        radial-gradient(circle at 20% 0%,rgba(16,6,159,.08),transparent 32%),
        linear-gradient(180deg,#FBFCFF 0%,#F3F7FC 100%) !important;
}}

.titulo{{
    font-size:clamp(34px,3.1vw,48px) !important;
    line-height:.98 !important;
    letter-spacing:-1px !important;
    margin-bottom:4px !important;
}}

.subtitulo{{
    font-size:clamp(13px,1vw,16px) !important;
    margin-top:5px !important;
}}

.linea-titulo{{
    width:clamp(140px,13vw,210px) !important;
    height:4px !important;
    margin-top:10px !important;
    margin-bottom:10px !important;
}}

.kpi-title{{
    font-size:clamp(20px,1.55vw,25px) !important;
    margin-top:16px !important;
    margin-bottom:8px !important;
}}

.kpi-divider{{
    height:3px !important;
    margin-bottom:16px !important;
}}

div[data-testid="stPlotlyChart"]{{
    min-width:0 !important;
    border-radius:10px !important;
    overflow:hidden !important;
}}

div[data-testid="column"],
div[data-testid="stVerticalBlock"],
div[data-testid="element-container"]{{
    min-width:0 !important;
}}

img{{
    max-width:100% !important;
    height:auto !important;
}}

.main .block-container{{
    overflow-x:hidden !important;
}}

div[data-testid="stHorizontalBlock"]{{
    gap:.75rem !important;
}}

@media (max-width: 1250px){{
    .block-container{{
        padding-left:.85rem !important;
        padding-right:.85rem !important;
    }}

    div[data-testid="stHorizontalBlock"]{{
        gap:.45rem !important;
    }}
}}

@media (max-width: 900px){{
    .titulo{{
        font-size:34px !important;
    }}

    .subtitulo{{
        font-size:13px !important;
    }}
}}

div[data-testid="stPlotlyChart"],
div[data-testid="stPlotlyChart"] > div,
.js-plotly-plot,
.js-plotly-plot .plotly,
.js-plotly-plot .main-svg{{
    overflow:visible !important;
}}

@media (max-width: 1180px){{
    .disp-kpi-grid{{
        grid-template-columns:repeat(2,minmax(0,1fr)) !important;
    }}

    .disp-kpi-card{{
        min-height:132px !important;
        height:auto !important;
    }}

    div[data-testid="stHorizontalBlock"]{{
        flex-wrap:wrap !important;
    }}

    div[data-testid="stHorizontalBlock"] > div[data-testid="column"]{{
        flex:1 1 360px !important;
        min-width:min(100%,360px) !important;
    }}
}}

@media (max-width: 760px){{
    .block-container{{
        padding-left:.55rem !important;
        padding-right:.55rem !important;
    }}

    .disp-kpi-grid,
    .ai-insight-grid{{
        grid-template-columns:1fr !important;
    }}

    div[data-testid="stHorizontalBlock"] > div[data-testid="column"]{{
        flex:1 1 100% !important;
        min-width:100% !important;
    }}

    .disp-kpi-card{{
        padding-left:58px !important;
    }}
}}

/*======================================================
INTERACCION FINAL: SELECCION + SIDEBAR RAIL
======================================================*/

.block-container{{
    padding-top:.85rem !important;
}}

.titulo{{
    font-size:clamp(34px,2.75vw,44px) !important;
    line-height:1.12 !important;
    padding-top:0 !important;
    overflow:visible !important;
}}

section[data-testid="stSidebar"] div[data-testid="stCheckbox"]{{
    min-height:34px !important;
    display:flex !important;
    align-items:center !important;
    border:1px solid rgba(148,163,184,.18) !important;
    background:rgba(10,15,25,.58) !important;
    transition:background .18s ease,border-color .18s ease,box-shadow .18s ease;
}}

section[data-testid="stSidebar"] div[data-testid="stCheckbox"]:has(input:checked){{
    background:
        linear-gradient(90deg,rgba(46,203,242,.34),rgba(71,225,144,.20)) !important;
    border-color:rgba(46,203,242,.62) !important;
    box-shadow:
        inset 3px 0 0 {CELESTE},
        inset 0 0 0 1px rgba(255,255,255,.045),
        0 10px 22px rgba(2,6,23,.18) !important;
}}

section[data-testid="stSidebar"] div[data-testid="stCheckbox"]:not(:has(input:checked)){{
    background:rgba(10,15,25,.58) !important;
    border-color:rgba(148,163,184,.16) !important;
    box-shadow:none !important;
}}

section[data-testid="stSidebar"] div[data-testid="stCheckbox"] input[type="checkbox"]{{
    width:14px !important;
    height:14px !important;
    accent-color:{CELESTE} !important;
    filter:none !important;
}}

section[data-testid="stSidebar"] div[data-testid="stCheckbox"] input[type="checkbox"]:checked{{
    accent-color:{VERDE} !important;
    filter:drop-shadow(0 0 5px rgba(46,203,242,.62)) !important;
}}

section[data-testid="stSidebar"] div[data-testid="stCheckbox"] label p{{
    color:#DDE7F7 !important;
    font-size:12px !important;
    font-weight:760 !important;
}}

section[data-testid="stSidebar"] div[data-testid="stCheckbox"]:has(input:checked) label p{{
    color:#FFFFFF !important;
    font-weight:900 !important;
}}

section[data-testid="stSidebar"][aria-expanded="false"]{{
    min-width:86px !important;
    max-width:86px !important;
    width:86px !important;
    transform:translateX(0) !important;
    visibility:visible !important;
    overflow:hidden !important;
}}

section[data-testid="stSidebar"][aria-expanded="false"] > div:first-child{{
    width:86px !important;
    padding:16px 11px !important;
    overflow:hidden !important;
}}

section[data-testid="stSidebar"][aria-expanded="false"] img{{
    content:url("{LOGO_ECC_ICONO_DATA}") !important;
    width:58px !important;
    min-width:58px !important;
    max-width:58px !important;
    margin:8px auto 28px auto !important;
    display:block !important;
}}

section[data-testid="stSidebar"][aria-expanded="false"] .filter-section-label{{
    display:grid !important;
    grid-template-columns:1fr !important;
    justify-items:center !important;
    margin:24px 0 !important;
    padding:0 !important;
}}

section[data-testid="stSidebar"][aria-expanded="false"] .filter-section-label .filter-icon{{
    width:42px !important;
    height:42px !important;
    border-radius:13px !important;
}}

section[data-testid="stSidebar"][aria-expanded="false"] .filter-label-copy,
section[data-testid="stSidebar"][aria-expanded="false"] div[data-testid="stExpander"],
section[data-testid="stSidebar"][aria-expanded="false"] .filter-mini-note{{
    display:none !important;
}}

section[data-testid="stSidebar"][aria-expanded="false"] ~ div .block-container,
section[data-testid="stSidebar"][aria-expanded="false"] + div .block-container{{
    padding-left:1rem !important;
    padding-right:1rem !important;
    max-width:100% !important;
}}

/*======================================================
ICONOS NEON PARA FILTROS SELECCIONABLES
======================================================*/

section[data-testid="stSidebar"] div[data-testid="stCheckbox"] label{{
    display:flex !important;
    align-items:center !important;
    gap:9px !important;
    width:100% !important;
}}

section[data-testid="stSidebar"] div[data-testid="stCheckbox"] label > div:first-child,
section[data-testid="stSidebar"] div[data-testid="stCheckbox"] label > span:first-child{{
    display:none !important;
}}

section[data-testid="stSidebar"] div[data-testid="stCheckbox"] input[type="checkbox"]{{
    position:absolute !important;
    opacity:0 !important;
    width:1px !important;
    height:1px !important;
    pointer-events:none !important;
}}

section[data-testid="stSidebar"] div[data-testid="stCheckbox"] label::before{{
    content:"";
    flex:0 0 22px;
    width:22px;
    height:22px;
    border-radius:8px;
    border:1px solid rgba(46,203,242,.34);
    background-color:rgba(3,9,18,.78);
    background-repeat:no-repeat;
    background-position:center;
    background-size:14px 14px;
    background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%232ECBF2' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='12' cy='7.5' r='3.2'/%3E%3Cpath d='M5.5 20c.8-4.4 3.2-6.5 6.5-6.5s5.7 2.1 6.5 6.5'/%3E%3C/svg%3E");
    box-shadow:inset 0 1px 0 rgba(255,255,255,.08);
    opacity:.62;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"]:has(input[aria-label="Ene"]) div[data-testid="stCheckbox"] label::before,
section[data-testid="stSidebar"] div[data-testid="stExpander"]:has(input[aria-label="Feb"]) div[data-testid="stCheckbox"] label::before{{
    background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%232ECBF2' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M7 3v3M17 3v3M4.5 9h15'/%3E%3Crect x='4' y='5' width='16' height='16' rx='2.5'/%3E%3Cpath d='M8 13h3M13 13h3M8 17h3'/%3E%3C/svg%3E") !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"]:has(input[aria-label*="CLAUDIO"]) div[data-testid="stCheckbox"] label::before,
section[data-testid="stSidebar"] div[data-testid="stExpander"]:has(input[aria-label*="CRISTOFER"]) div[data-testid="stCheckbox"] label::before,
section[data-testid="stSidebar"] div[data-testid="stExpander"]:has(input[aria-label*="CHRISTOPHER"]) div[data-testid="stCheckbox"] label::before,
section[data-testid="stSidebar"] div[data-testid="stExpander"]:has(input[aria-label*="ELIET"]) div[data-testid="stCheckbox"] label::before,
section[data-testid="stSidebar"] div[data-testid="stExpander"]:has(input[aria-label*="LUIS"]) div[data-testid="stCheckbox"] label::before,
section[data-testid="stSidebar"] div[data-testid="stExpander"]:has(input[aria-label*="MATIAS"]) div[data-testid="stCheckbox"] label::before,
section[data-testid="stSidebar"] div[data-testid="stExpander"]:has(input[aria-label*="OSTION"]) div[data-testid="stCheckbox"] label::before,
section[data-testid="stSidebar"] div[data-testid="stExpander"]:has(input[aria-label*="PABLO"]) div[data-testid="stCheckbox"] label::before,
section[data-testid="stSidebar"] div[data-testid="stExpander"]:has(input[aria-label*="PEDRO"]) div[data-testid="stCheckbox"] label::before{{
    background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%232ECBF2' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='12' cy='7.5' r='3.2'/%3E%3Cpath d='M5.5 20c.8-4.4 3.2-6.5 6.5-6.5s5.7 2.1 6.5 6.5'/%3E%3C/svg%3E") !important;
}}

section[data-testid="stSidebar"] div[data-testid="stCheckbox"] label:has(input[aria-label*="Region"])::before,
section[data-testid="stSidebar"] div[data-testid="stCheckbox"] label:has(input[aria-label*="Región"])::before{{
    background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%232ECBF2' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 21s7-5.4 7-12a7 7 0 1 0-14 0c0 6.6 7 12 7 12Z'/%3E%3Ccircle cx='12' cy='9' r='2.5'/%3E%3C/svg%3E");
}}

section[data-testid="stSidebar"] div[data-testid="stCheckbox"] label:has(input[aria-label="Ene"])::before,
section[data-testid="stSidebar"] div[data-testid="stCheckbox"] label:has(input[aria-label="Feb"])::before,
section[data-testid="stSidebar"] div[data-testid="stCheckbox"] label:has(input[aria-label="Mar"])::before,
section[data-testid="stSidebar"] div[data-testid="stCheckbox"] label:has(input[aria-label="Abr"])::before,
section[data-testid="stSidebar"] div[data-testid="stCheckbox"] label:has(input[aria-label="May"])::before,
section[data-testid="stSidebar"] div[data-testid="stCheckbox"] label:has(input[aria-label="Jun"])::before,
section[data-testid="stSidebar"] div[data-testid="stCheckbox"] label:has(input[aria-label="Jul"])::before,
section[data-testid="stSidebar"] div[data-testid="stCheckbox"] label:has(input[aria-label="Ago"])::before,
section[data-testid="stSidebar"] div[data-testid="stCheckbox"] label:has(input[aria-label="Sep"])::before,
section[data-testid="stSidebar"] div[data-testid="stCheckbox"] label:has(input[aria-label="Oct"])::before,
section[data-testid="stSidebar"] div[data-testid="stCheckbox"] label:has(input[aria-label="Nov"])::before,
section[data-testid="stSidebar"] div[data-testid="stCheckbox"] label:has(input[aria-label="Dic"])::before{{
    background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%232ECBF2' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M7 3v3M17 3v3M4.5 9h15'/%3E%3Crect x='4' y='5' width='16' height='16' rx='2.5'/%3E%3Cpath d='M8 13h3M13 13h3M8 17h3'/%3E%3C/svg%3E");
}}

section[data-testid="stSidebar"] div[data-testid="stCheckbox"]:has(input:checked) label::before{{
    border-color:rgba(71,225,144,.95);
    background-color:rgba(46,203,242,.14);
    box-shadow:
        0 0 0 1px rgba(46,203,242,.26),
        0 0 14px rgba(46,203,242,.40),
        inset 0 0 12px rgba(71,225,144,.14);
    opacity:1;
}}

section[data-testid="stSidebar"] div[data-testid="stCheckbox"]:not(:has(input:checked)) label::before{{
    border-color:rgba(148,163,184,.36);
    background-color:rgba(3,9,18,.72);
    filter:grayscale(.25);
    opacity:.54;
}}

section[data-testid="stSidebar"] div[data-testid="stCheckbox"]:has(input:checked){{
    background:
        linear-gradient(90deg,rgba(46,203,242,.22),rgba(71,225,144,.13)) !important;
    border-color:rgba(46,203,242,.46) !important;
}}

/*======================================================
FIX FINAL SUPERIOR: SIN FRANJA BLANCA Y SIN TITULO CORTADO
======================================================*/

header[data-testid="stHeader"]{{
    display:none !important;
    height:0 !important;
    min-height:0 !important;
    visibility:hidden !important;
}}

div[data-testid="stToolbar"],
div[data-testid="stDecoration"],
.stDeployButton,
#MainMenu,
footer{{
    display:none !important;
    height:0 !important;
    visibility:hidden !important;
}}

section.main,
div[data-testid="stAppViewContainer"] > .main{{
    padding-top:0 !important;
}}

.block-container{{
    padding-top:1.05rem !important;
}}

.titulo{{
    margin-top:0 !important;
    padding-top:0 !important;
    line-height:1.16 !important;
    font-size:clamp(32px,2.55vw,42px) !important;
    overflow:visible !important;
}}

.subtitulo{{
    margin-top:4px !important;
}}

section[data-testid="stSidebar"] > div:first-child{{
    padding-top:16px !important;
}}

section[data-testid="stSidebar"] img{{
    width:220px !important;
    margin-top:-10px !important;
    margin-bottom:20px !important;
    margin-left:auto !important;
    margin-right:auto !important;
    display:block !important;
}}

/*======================================================
PROFUNDIDAD 3D EJECUTIVA GLOBAL
======================================================*/

div[data-testid="stPlotlyChart"]{{
    background:linear-gradient(180deg,rgba(255,255,255,.98),rgba(248,251,255,.98)) !important;
    border:1px solid rgba(16,6,159,.08) !important;
    box-shadow:
        0 18px 36px rgba(15,23,42,.10),
        0 5px 0 rgba(15,23,42,.055),
        inset 0 1px 0 rgba(255,255,255,.92) !important;
}}

div[data-testid="stPlotlyChart"]:hover{{
    box-shadow:
        0 22px 42px rgba(15,23,42,.13),
        0 5px 0 rgba(15,23,42,.065),
        inset 0 1px 0 rgba(255,255,255,.95) !important;
}}

div[data-testid="stMarkdownContainer"] > div[style*="border-top"]{{
    box-shadow:
        0 16px 34px rgba(15,23,42,.10),
        0 5px 0 rgba(16,6,159,.10),
        inset 0 1px 0 rgba(255,255,255,.90) !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"]{{
    box-shadow:
        0 16px 30px rgba(0,0,0,.30),
        0 4px 0 rgba(0,0,0,.26),
        inset 0 1px 0 rgba(255,255,255,.07) !important;
}}

section[data-testid="stSidebar"] .filter-section-label{{
    filter:drop-shadow(0 12px 18px rgba(0,0,0,.22));
}}

section[data-testid="stSidebar"] .filter-section-label .filter-icon{{
    box-shadow:
        0 14px 26px rgba(46,203,242,.22),
        0 4px 0 rgba(0,0,0,.20),
        inset 0 1px 0 rgba(255,255,255,.52),
        inset 0 -8px 14px rgba(2,6,23,.12) !important;
}}

section[data-testid="stSidebar"] div[data-testid="stCheckbox"]{{
    box-shadow:
        0 10px 20px rgba(0,0,0,.18),
        0 3px 0 rgba(0,0,0,.18),
        inset 0 1px 0 rgba(255,255,255,.055) !important;
}}

section[data-testid="stSidebar"] div[data-testid="stCheckbox"]:has(input:checked){{
    box-shadow:
        inset 3px 0 0 {CELESTE},
        inset 0 1px 0 rgba(255,255,255,.12),
        0 16px 28px rgba(2,6,23,.26),
        0 0 0 1px rgba(46,203,242,.22) !important;
}}

/*======================================================
AJUSTE FINAL: SIDEBAR MAS FINA + LOGO 3D
======================================================*/

section[data-testid="stSidebar"]{{
    min-width:286px !important;
    max-width:286px !important;
    width:286px !important;
}}

section[data-testid="stSidebar"] > div:first-child{{
    width:286px !important;
    padding-top:14px !important;
    padding-left:18px !important;
    padding-right:18px !important;
}}

section[data-testid="stSidebar"] img{{
    width:198px !important;
    max-width:198px !important;
    margin-top:-8px !important;
    margin-bottom:18px !important;
    transform:perspective(820px) rotateX(5deg) translateZ(0);
    filter:
        drop-shadow(0 13px 10px rgba(0,0,0,.42))
        drop-shadow(0 0 12px rgba(46,203,242,.16))
        drop-shadow(2px 2px 0 rgba(46,203,242,.18))
        drop-shadow(-1px -1px 0 rgba(255,255,255,.20)) !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"]{{
    border-radius:11px !important;
}}

section[data-testid="stSidebar"] div[data-testid="stCheckbox"] label p{{
    font-size:11.5px !important;
    line-height:1.15 !important;
}}

section[data-testid="stSidebar"][aria-expanded="false"]{{
    min-width:76px !important;
    max-width:76px !important;
    width:76px !important;
}}

section[data-testid="stSidebar"][aria-expanded="false"] > div:first-child{{
    width:76px !important;
    padding-left:9px !important;
    padding-right:9px !important;
}}

section[data-testid="stSidebar"][aria-expanded="false"] img{{
    width:50px !important;
    min-width:50px !important;
    max-width:50px !important;
    margin:6px auto 26px auto !important;
}}

section[data-testid="stSidebar"][aria-expanded="false"] .filter-section-label .filter-icon{{
    width:38px !important;
    height:38px !important;
}}

/*======================================================
PULIDO EJECUTIVO FINAL: LOGOS, MESES, EXPORTACION
======================================================*/

button[title*="fullscreen" i],
button[aria-label*="fullscreen" i],
button[title*="pantalla completa" i],
button[aria-label*="pantalla completa" i],
div[data-testid="StyledFullScreenButton"],
div[data-testid="stElementToolbar"]{{
    display:none !important;
    opacity:0 !important;
    pointer-events:none !important;
}}

button[data-testid="stSidebarCollapseButton"],
div[data-testid="stSidebarCollapseButton"] button,
button[title*="sidebar" i],
button[aria-label*="sidebar" i],
button[title*="barra" i],
button[aria-label*="barra" i]{{
    background:
        radial-gradient(circle at 35% 25%,rgba(255,255,255,.46),transparent 25%),
        linear-gradient(135deg,{NARANJO} 0%,{ROSADO} 100%) !important;
    color:#FFFFFF !important;
    border:1px solid rgba(255,61,0,.72) !important;
    border-radius:12px !important;
    box-shadow:
        0 0 0 1px rgba(255,61,0,.22),
        0 0 18px rgba(255,61,0,.42),
        0 12px 24px rgba(2,6,23,.24) !important;
}}

.sidebar-logo-shell{{
    display:flex;
    justify-content:center;
    align-items:center;
    margin:-4px auto 18px auto;
    user-select:none;
    pointer-events:none;
}}

section[data-testid="stSidebar"] .sidebar-logo-img{{
    width:188px !important;
    max-width:188px !important;
    height:auto !important;
    transform:none !important;
    opacity:.98;
    filter:
        drop-shadow(0 11px 14px rgba(0,0,0,.46))
        drop-shadow(0 0 10px rgba(46,203,242,.13))
        drop-shadow(1px 1px 0 rgba(255,255,255,.18)) !important;
}}

section[data-testid="stSidebar"][aria-expanded="false"] .sidebar-logo-img{{
    content:url("{LOGO_ECC_ICONO_DATA}") !important;
    width:48px !important;
    min-width:48px !important;
    max-width:48px !important;
    margin:4px auto 24px auto !important;
}}

.brand-lockup{{
    height:58px;
    display:flex;
    align-items:flex-start;
    justify-content:flex-end;
    pointer-events:none;
    user-select:none;
}}

.brand-lockup img{{
    width:118px;
    height:auto;
    filter:
        drop-shadow(0 8px 13px rgba(16,6,159,.14))
        drop-shadow(0 0 8px rgba(46,203,242,.10));
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"]:has(input[aria-label="Ene"]) div[data-testid="stCheckbox"]{{
    padding:2px 0 !important;
    margin:3px 0 !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"]:has(input[aria-label="Ene"]) div[data-testid="stCheckbox"] label{{
    min-height:32px !important;
    height:32px !important;
    padding:0 7px !important;
    gap:6px !important;
    border-radius:10px !important;
    border:1px solid rgba(46,203,242,.24) !important;
    background:linear-gradient(180deg,rgba(13,22,36,.92),rgba(7,13,23,.96)) !important;
    box-shadow:
        0 9px 18px rgba(0,0,0,.20),
        inset 0 1px 0 rgba(255,255,255,.055) !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"]:has(input[aria-label="Ene"]) div[data-testid="stCheckbox"]:has(input:checked) label{{
    background:
        linear-gradient(135deg,rgba(46,203,242,.30),rgba(253,108,152,.16)) !important;
    border-color:rgba(46,203,242,.72) !important;
    box-shadow:
        inset 3px 0 0 {NARANJO},
        0 0 0 1px rgba(46,203,242,.18),
        0 0 18px rgba(46,203,242,.18),
        0 12px 22px rgba(0,0,0,.24) !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"]:has(input[aria-label="Ene"]) div[data-testid="stCheckbox"] label::before{{
    flex:0 0 18px !important;
    width:18px !important;
    height:18px !important;
    border-radius:6px !important;
    background-size:12px 12px !important;
    border-color:rgba(46,203,242,.42) !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"]:has(input[aria-label="Ene"]) div[data-testid="stCheckbox"]:has(input:checked) label::before{{
    border-color:{NARANJO} !important;
    background-color:rgba(255,61,0,.16) !important;
    box-shadow:
        0 0 0 1px rgba(255,61,0,.22),
        0 0 13px rgba(255,61,0,.42),
        inset 0 1px 0 rgba(255,255,255,.20) !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"]:has(input[aria-label="Ene"]) div[data-testid="stCheckbox"] label p{{
    min-width:0 !important;
    max-width:68px !important;
    overflow:hidden !important;
    text-overflow:ellipsis !important;
    white-space:nowrap !important;
    font-size:10.5px !important;
    line-height:1 !important;
    letter-spacing:0 !important;
}}

.sidebar-export-card{{
    position:fixed !important;
    left:18px !important;
    bottom:58px !important;
    width:230px !important;
    margin:0 !important;
    padding:14px 15px;
    border-radius:14px;
    border:1px solid rgba(253,108,152,.66);
    display:flex;
    align-items:center;
    gap:12px;
    text-decoration:none !important;
    cursor:pointer;
    color:#FFFFFF !important;
    z-index:999998 !important;
    background:
        radial-gradient(circle at 82% 18%,rgba(253,108,152,.46),transparent 36%),
        radial-gradient(circle at 16% 86%,rgba(46,203,242,.16),transparent 34%),
        linear-gradient(145deg,rgba(253,108,152,.22),rgba(18,8,32,.96) 62%,rgba(5,10,20,.98));
    box-shadow:
        0 0 18px rgba(253,108,152,.22),
        0 16px 30px rgba(0,0,0,.30),
        inset 0 1px 0 rgba(255,255,255,.10);
    transition:filter .16s ease, border-color .16s ease, box-shadow .16s ease;
}}

@keyframes exportModeGlow {{
    0% {{ opacity:.82; filter:brightness(.92) saturate(.95); }}
    45% {{ opacity:1; filter:brightness(1.22) saturate(1.18); }}
    100% {{ opacity:1; filter:brightness(1) saturate(1); }}
}}

@keyframes exportFlowIn {{
    0% {{ opacity:.76; transform:translateY(-12px); filter:brightness(.92); }}
    100% {{ opacity:1; transform:translateY(0); filter:brightness(1); }}
}}

@keyframes clientFilterIn {{
    0% {{ transform:translateX(-18px); opacity:0; filter:blur(3px) brightness(.9); }}
    100% {{ transform:translateX(0); opacity:1; filter:blur(0) brightness(1); }}
}}

@keyframes clientFilterOut {{
    0% {{ max-height:48px; margin:8px 0 10px; opacity:1; transform:translateX(0); }}
    100% {{ max-height:0; margin:0; opacity:0; transform:translateX(-18px); padding-top:0; padding-bottom:0; border-color:transparent; }}
}}

.sidebar-export-card-animate{{
    animation:exportModeGlow .46s ease-out both;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details:has(.filter-anchor-client){{
    animation:clientFilterIn .46s ease-out both;
    transform-origin:top center;
}}

.client-filter-exit-shell{{
    overflow:hidden;
    height:44px;
    margin:8px 0 10px;
    padding:0 14px;
    border-radius:10px;
    border:1px solid rgba(46,203,242,.34);
    color:#CFF8FF;
    display:flex;
    align-items:center;
    font-size:12px;
    font-weight:900;
    letter-spacing:.06em;
    background:rgba(6,18,34,.68);
    box-shadow:0 0 14px rgba(46,203,242,.12), inset 0 1px 0 rgba(255,255,255,.08);
    animation:clientFilterOut .44s ease-in forwards;
}}

.sidebar-export-card:hover{{
    border-color:rgba(253,108,152,.90);
    filter:brightness(1.07);
    box-shadow:
        0 0 22px rgba(253,108,152,.34),
        0 0 28px rgba(46,203,242,.12),
        0 18px 32px rgba(0,0,0,.32),
        inset 0 1px 0 rgba(255,255,255,.14);
}}

.sidebar-export-icon{{
    width:36px;
    height:36px;
    min-width:36px;
    border-radius:12px;
    display:flex;
    align-items:center;
    justify-content:center;
    color:{ROSADO};
    border:1px solid rgba(253,108,152,.58);
    background:
        radial-gradient(circle at 50% 30%,rgba(253,108,152,.30),transparent 42%),
        rgba(253,108,152,.10);
    box-shadow:
        0 0 12px rgba(253,108,152,.38),
        0 0 20px rgba(46,203,242,.14),
        inset 0 1px 0 rgba(255,255,255,.16);
}}

.sidebar-export-icon svg{{
    width:21px;
    height:21px;
    stroke:currentColor;
    filter:
        drop-shadow(0 0 5px rgba(253,108,152,.62))
        drop-shadow(0 0 8px rgba(46,203,242,.26));
}}

.sidebar-export-text{{
    display:flex;
    flex-direction:column;
    gap:3px;
}}

.sidebar-export-kicker{{
    color:{ROSADO};
    font-size:9.5px;
    font-weight:900;
    text-transform:uppercase;
    letter-spacing:.12em;
    text-shadow:0 0 10px rgba(253,108,152,.42);
}}

.sidebar-export-title{{
    color:#FFFFFF;
    font-size:15px;
    font-weight:950;
    margin-top:3px;
    line-height:1.08;
}}

.sidebar-export-copy{{
    display:none;
}}

section[data-testid="stSidebar"] div[data-testid="stDownloadButton"] button{{
    min-height:36px !important;
    border-radius:11px !important;
    border:1px solid rgba(253,108,152,.72) !important;
    background:
        linear-gradient(135deg,rgba(253,108,152,.98) 0%,rgba(255,61,0,.92) 58%,rgba(46,203,242,.60) 130%) !important;
    color:#FFFFFF !important;
    font-size:11px !important;
    font-weight:950 !important;
    letter-spacing:.04em !important;
    box-shadow:
        0 0 0 1px rgba(253,108,152,.18),
        0 0 18px rgba(253,108,152,.36),
        0 12px 24px rgba(0,0,0,.28) !important;
}}

section[data-testid="stSidebar"] div[data-testid="stDownloadButton"]{{
    position:fixed !important;
    left:18px !important;
    bottom:58px !important;
    width:230px !important;
    z-index:999998 !important;
}}

section[data-testid="stSidebar"] div[data-testid="stDownloadButton"] button:hover{{
    filter:brightness(1.08);
    transform:none !important;
}}

section[data-testid="stSidebar"]:has(.filter-anchor-client) .sidebar-export-card{{
    position:fixed !important;
    left:18px !important;
    bottom:18px !important;
    width:230px !important;
    margin:0 !important;
}}

section[data-testid="stSidebar"]:has(details[open]) .sidebar-export-card,
section[data-testid="stSidebar"]:has(.filter-anchor-client):has(details[open]) .sidebar-export-card{{
    position:relative !important;
    left:auto !important;
    bottom:auto !important;
    width:230px !important;
    margin:18px 0 34px 0 !important;
    z-index:5 !important;
    animation:exportFlowIn .36s ease-out both;
}}

section[data-testid="stSidebar"]:has(.filter-anchor-client) div[data-testid="stDownloadButton"]{{
    position:fixed !important;
    left:18px !important;
    bottom:18px !important;
    width:230px !important;
    z-index:999998 !important;
}}

section[data-testid="stSidebar"]:has(details[open]) div[data-testid="stDownloadButton"],
section[data-testid="stSidebar"]:has(.filter-anchor-client):has(details[open]) div[data-testid="stDownloadButton"]{{
    position:relative !important;
    left:auto !important;
    bottom:auto !important;
    width:230px !important;
    margin:18px 0 34px 0 !important;
    z-index:5 !important;
    animation:exportFlowIn .36s ease-out both;
}}

section[data-testid="stSidebar"][aria-expanded="false"] .sidebar-export-card,
section[data-testid="stSidebar"][aria-expanded="false"] div[data-testid="stDownloadButton"],
section[data-testid="stSidebar"][aria-expanded="false"] div[data-testid="stDownloadButton"] *,
section[data-testid="stSidebar"][aria-expanded="false"] div:has(> div[data-testid="stDownloadButton"]){{
    display:none !important;
    visibility:hidden !important;
    opacity:0 !important;
    width:0 !important;
    height:0 !important;
    min-height:0 !important;
    margin:0 !important;
    padding:0 !important;
    overflow:hidden !important;
    pointer-events:none !important;
}}

button[data-testid="stSidebarCollapseButton"],
div[data-testid="stSidebarCollapseButton"] button,
section[data-testid="stSidebar"] button[title*="sidebar" i],
section[data-testid="stSidebar"] button[aria-label*="sidebar" i],
section[data-testid="stSidebar"] button[title*="barra" i],
section[data-testid="stSidebar"] button[aria-label*="barra" i]{{
    position:fixed !important;
    left:246px !important;
    bottom:18px !important;
    top:auto !important;
    width:34px !important;
    height:34px !important;
    padding:0 !important;
    background:transparent !important;
    border:0 !important;
    border-radius:0 !important;
    box-shadow:none !important;
    color:{NARANJO} !important;
    z-index:999999 !important;
}}

section[data-testid="stSidebar"][aria-expanded="false"] button[data-testid="stSidebarCollapseButton"],
section[data-testid="stSidebar"][aria-expanded="false"] div[data-testid="stSidebarCollapseButton"] button,
section[data-testid="stSidebar"][aria-expanded="false"] button[title*="sidebar" i],
section[data-testid="stSidebar"][aria-expanded="false"] button[aria-label*="sidebar" i],
section[data-testid="stSidebar"][aria-expanded="false"] button[title*="barra" i],
section[data-testid="stSidebar"][aria-expanded="false"] button[aria-label*="barra" i]{{
    left:23px !important;
}}

button[data-testid="stSidebarCollapseButton"] svg,
div[data-testid="stSidebarCollapseButton"] button svg,
section[data-testid="stSidebar"] button[title*="sidebar" i] svg,
section[data-testid="stSidebar"] button[aria-label*="sidebar" i] svg,
section[data-testid="stSidebar"] button[title*="barra" i] svg,
section[data-testid="stSidebar"] button[aria-label*="barra" i] svg{{
    width:24px !important;
    height:24px !important;
    color:{NARANJO} !important;
    filter:drop-shadow(0 0 8px rgba(255,61,0,.42)) !important;
}}

/* Flechas sidebar: siempre visibles, neon y sin circulo */
button[data-testid="stSidebarCollapseButton"],
div[data-testid="stSidebarCollapseButton"],
div[data-testid="stSidebarCollapseButton"] button,
button[title*="sidebar" i],
button[aria-label*="sidebar" i],
button[title*="barra lateral" i],
button[aria-label*="barra lateral" i]{{
    display:flex !important;
    align-items:center !important;
    justify-content:center !important;
    position:fixed !important;
    left:252px !important;
    bottom:18px !important;
    top:auto !important;
    right:auto !important;
    width:32px !important;
    height:32px !important;
    min-width:32px !important;
    min-height:32px !important;
    padding:0 !important;
    margin:0 !important;
    background:transparent !important;
    background-color:transparent !important;
    border:0 !important;
    outline:0 !important;
    border-radius:0 !important;
    box-shadow:none !important;
    color:{NARANJO} !important;
    opacity:1 !important;
    visibility:visible !important;
    pointer-events:auto !important;
    z-index:2147483647 !important;
}}

section[data-testid="stSidebar"][aria-expanded="false"] button[data-testid="stSidebarCollapseButton"],
section[data-testid="stSidebar"][aria-expanded="false"] div[data-testid="stSidebarCollapseButton"],
section[data-testid="stSidebar"][aria-expanded="false"] div[data-testid="stSidebarCollapseButton"] button,
section[data-testid="stSidebar"][aria-expanded="false"] button[title*="sidebar" i],
section[data-testid="stSidebar"][aria-expanded="false"] button[aria-label*="sidebar" i],
section[data-testid="stSidebar"][aria-expanded="false"] button[title*="barra lateral" i],
section[data-testid="stSidebar"][aria-expanded="false"] button[aria-label*="barra lateral" i]{{
    left:22px !important;
}}

button[data-testid="stSidebarCollapseButton"] svg,
div[data-testid="stSidebarCollapseButton"] svg,
div[data-testid="stSidebarCollapseButton"] button svg,
button[title*="sidebar" i] svg,
button[aria-label*="sidebar" i] svg,
button[title*="barra lateral" i] svg,
button[aria-label*="barra lateral" i] svg{{
    width:25px !important;
    height:25px !important;
    color:{NARANJO} !important;
    stroke:{NARANJO} !important;
    fill:none !important;
    filter:
        drop-shadow(0 0 4px rgba(255,61,0,.95))
        drop-shadow(0 0 12px rgba(255,61,0,.58)) !important;
}}

button[data-testid="stSidebarCollapseButton"] svg *,
div[data-testid="stSidebarCollapseButton"] svg *,
div[data-testid="stSidebarCollapseButton"] button svg *,
button[title*="sidebar" i] svg *,
button[aria-label*="sidebar" i] svg *,
button[title*="barra lateral" i] svg *,
button[aria-label*="barra lateral" i] svg *{{
    stroke:{NARANJO} !important;
    fill:none !important;
}}

/* Refuerzo final: icono naranjo corporativo incluso si Streamlit usa currentColor */
button[data-testid="stSidebarCollapseButton"],
button[data-testid="stSidebarCollapseButton"] *,
div[data-testid="stSidebarCollapseButton"],
div[data-testid="stSidebarCollapseButton"] *,
button[title*="sidebar" i],
button[title*="sidebar" i] *,
button[aria-label*="sidebar" i],
button[aria-label*="sidebar" i] *,
button[title*="barra lateral" i],
button[title*="barra lateral" i] *,
button[aria-label*="barra lateral" i],
button[aria-label*="barra lateral" i] *{{
    color:{NARANJO} !important;
    -webkit-text-fill-color:{NARANJO} !important;
}}

button[data-testid="stSidebarCollapseButton"] svg,
button[data-testid="stSidebarCollapseButton"] svg path,
button[data-testid="stSidebarCollapseButton"] svg polyline,
button[data-testid="stSidebarCollapseButton"] svg line,
div[data-testid="stSidebarCollapseButton"] svg,
div[data-testid="stSidebarCollapseButton"] svg path,
div[data-testid="stSidebarCollapseButton"] svg polyline,
div[data-testid="stSidebarCollapseButton"] svg line,
button[title*="sidebar" i] svg,
button[title*="sidebar" i] svg path,
button[title*="sidebar" i] svg polyline,
button[title*="sidebar" i] svg line,
button[aria-label*="sidebar" i] svg,
button[aria-label*="sidebar" i] svg path,
button[aria-label*="sidebar" i] svg polyline,
button[aria-label*="sidebar" i] svg line,
button[title*="barra lateral" i] svg,
button[title*="barra lateral" i] svg path,
button[title*="barra lateral" i] svg polyline,
button[title*="barra lateral" i] svg line,
button[aria-label*="barra lateral" i] svg,
button[aria-label*="barra lateral" i] svg path,
button[aria-label*="barra lateral" i] svg polyline,
button[aria-label*="barra lateral" i] svg line{{
    color:{NARANJO} !important;
    stroke:{NARANJO} !important;
    fill:none !important;
    filter:
        drop-shadow(0 0 5px rgba(255,61,0,1))
        drop-shadow(0 0 14px rgba(255,61,0,.72))
        drop-shadow(0 0 24px rgba(255,61,0,.42)) !important;
}}

/*======================================================
FILTROS EJECUTIVOS: TITULO DENTRO DEL DESPLEGABLE
======================================================*/

section[data-testid="stSidebar"] .filter-section-label{{
    position:relative !important;
    z-index:8 !important;
    width:42px !important;
    height:42px !important;
    margin:18px 0 -38px 4px !important;
    pointer-events:none !important;
    transform:translateX(0) translateY(4px) !important;
    filter:
        drop-shadow(0 0 8px rgba(46,203,242,.48))
        drop-shadow(0 12px 16px rgba(0,0,0,.30)) !important;
}}

section[data-testid="stSidebar"] .filter-section-label .filter-label-copy{{
    display:none !important;
}}

section[data-testid="stSidebar"] .filter-section-label .filter-icon{{
    position:relative !important;
    width:40px !important;
    height:40px !important;
    border-radius:14px !important;
    border:1px solid rgba(46,203,242,.78) !important;
    background:
        radial-gradient(circle at 50% 50%,rgba(46,203,242,.14),transparent 58%),
        linear-gradient(145deg,rgba(46,203,242,.08),rgba(253,108,152,.035)) !important;
    backdrop-filter:blur(10px) saturate(1.2) !important;
    box-shadow:
        0 0 0 1px rgba(20,220,188,.12),
        0 0 14px rgba(46,203,242,.44),
        0 0 26px rgba(46,203,242,.18),
        0 10px 18px rgba(0,0,0,.24),
        inset 0 1px 0 rgba(255,255,255,.16),
        inset 0 0 18px rgba(46,203,242,.10) !important;
}}

section[data-testid="stSidebar"] .filter-section-label .filter-icon::before{{
    content:"";
    position:absolute;
    inset:5px;
    border-radius:11px;
    border:1px solid rgba(20,220,188,.28);
    box-shadow:inset 0 0 10px rgba(46,203,242,.18);
}}

section[data-testid="stSidebar"] .filter-section-label .filter-icon::after{{
    content:"";
    position:absolute;
    inset:-3px;
    border-radius:16px;
    border:1px solid rgba(253,108,152,.16);
    opacity:.78;
}}

section[data-testid="stSidebar"] .filter-section-label .filter-icon svg{{
    position:relative !important;
    z-index:2 !important;
    width:21px !important;
    height:21px !important;
    color:{CELESTE} !important;
    stroke:{CELESTE} !important;
    fill:none !important;
    stroke-width:2.35 !important;
    filter:
        drop-shadow(0 0 5px rgba(46,203,242,.88))
        drop-shadow(0 0 13px rgba(20,220,188,.34)) !important;
}}

section[data-testid="stSidebar"] .filter-section-label .filter-icon svg *,
section[data-testid="stSidebar"] .filter-section-label .filter-icon svg path,
section[data-testid="stSidebar"] .filter-section-label .filter-icon svg circle{{
    stroke:{CELESTE} !important;
    fill:none !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"]{{
    width:calc(100% - 48px) !important;
    margin-left:48px !important;
    transform:none !important;
    transition:border-color .16s ease, background .16s ease, box-shadow .16s ease !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"]:hover{{
    transform:none !important;
    box-shadow:
        0 16px 30px rgba(0,0,0,.30),
        0 4px 0 rgba(0,0,0,.26),
        inset 0 1px 0 rgba(255,255,255,.07) !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary{{
    position:relative !important;
    overflow:visible !important;
    min-height:42px !important;
    padding:8px 12px 8px 34px !important;
    display:flex !important;
    align-items:center !important;
    gap:0 !important;
    border-radius:11px !important;
    border:1px solid rgba(46,203,242,.34) !important;
    background:
        linear-gradient(90deg,rgba(46,203,242,.16),rgba(14,28,48,.74) 48%,rgba(253,108,152,.07)) !important;
    box-shadow:
        0 14px 24px rgba(0,0,0,.24),
        inset 0 1px 0 rgba(255,255,255,.09) !important;
    list-style:none !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary::-webkit-details-marker{{
    display:none !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary::marker{{
    content:"" !important;
    color:transparent !important;
    font-size:0 !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary > svg,
section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary span > svg,
section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary [data-testid="stExpanderToggleIcon"],
section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary [data-testid="stExpanderToggleIcon"] *{{
    width:0 !important;
    height:0 !important;
    min-width:0 !important;
    max-width:0 !important;
    opacity:0 !important;
    visibility:hidden !important;
    overflow:hidden !important;
    display:none !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary > span:first-child:not(:has(p)){{
    width:0 !important;
    height:0 !important;
    min-width:0 !important;
    opacity:0 !important;
    visibility:hidden !important;
    overflow:hidden !important;
    display:none !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary::before{{
    content:"\\203A";
    position:absolute;
    left:34px;
    top:50%;
    transform:translateY(-50%);
    color:{CELESTE};
    font-size:16px;
    font-weight:950;
    line-height:1;
    text-shadow:
        0 0 6px rgba(46,203,242,.80),
        0 0 16px rgba(46,203,242,.35);
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary:hover{{
    border-color:rgba(46,203,242,.58) !important;
    background:
        linear-gradient(90deg,rgba(46,203,242,.22),rgba(15,34,56,.82) 52%,rgba(253,108,152,.10)) !important;
    box-shadow:
        0 14px 24px rgba(0,0,0,.24),
        0 0 18px rgba(46,203,242,.13),
        inset 0 1px 0 rgba(255,255,255,.11) !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary p{{
    display:block !important;
    position:absolute !important;
    z-index:9 !important;
    left:52px !important;
    top:50% !important;
    transform:translateY(-50%) !important;
    width:auto !important;
    min-width:0 !important;
    max-width:none !important;
    white-space:nowrap !important;
    overflow:visible !important;
    margin:0 !important;
    color:#FFFFFF !important;
    font-size:12px !important;
    line-height:1 !important;
    font-weight:950 !important;
    letter-spacing:.09em !important;
    text-transform:uppercase !important;
    text-shadow:0 0 12px rgba(46,203,242,.16) !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary::after{{
    content:"";
    position:absolute;
    left:132px;
    right:14px;
    top:50%;
    transform:translateY(-50%);
    height:2px;
    border-radius:999px;
    background:linear-gradient(90deg,{CELESTE},rgba(46,203,242,.20),rgba(253,108,152,.34),transparent);
    box-shadow:0 0 12px rgba(46,203,242,.26);
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details[open] summary{{
    border-color:rgba(20,220,188,.54) !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details[open] summary::after{{
    background:linear-gradient(90deg,{CELESTE},rgba(20,220,188,.55),rgba(253,108,152,.38),transparent);
    box-shadow:
        0 0 13px rgba(46,203,242,.34),
        0 0 20px rgba(20,220,188,.14);
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary svg,
section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary svg path,
section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary svg polyline{{
    display:none !important;
    opacity:0 !important;
    visibility:hidden !important;
}}

/* Flecha real del desplegable: nativa, clickeable y naranjo Entel */
section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary::before{{
    content:none !important;
    display:none !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary::-webkit-details-marker{{
    display:inline-block !important;
    color:{NARANJO} !important;
    filter:drop-shadow(0 0 8px rgba(255,61,0,.62)) !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary::marker{{
    content:normal !important;
    color:{NARANJO} !important;
    font-size:15px !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary > svg,
section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary span > svg,
section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary [data-testid="stExpanderToggleIcon"],
section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary [data-testid="stExpanderToggleIcon"] *{{
    display:block !important;
    visibility:visible !important;
    opacity:1 !important;
    width:17px !important;
    height:17px !important;
    min-width:17px !important;
    max-width:17px !important;
    color:{NARANJO} !important;
    stroke:{NARANJO} !important;
    fill:none !important;
    filter:
        drop-shadow(0 0 5px rgba(255,61,0,.95))
        drop-shadow(0 0 13px rgba(255,61,0,.50)) !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary > span:first-child:not(:has(p)){{
    display:flex !important;
    align-items:center !important;
    justify-content:center !important;
    visibility:visible !important;
    opacity:1 !important;
    width:18px !important;
    min-width:18px !important;
    height:18px !important;
    position:absolute !important;
    left:28px !important;
    top:50% !important;
    transform:translateY(-50%) !important;
    color:{NARANJO} !important;
    pointer-events:auto !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary p{{
    left:50px !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary::after{{
    left:128px !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpanderContent"]{{
    padding:12px 12px 14px 12px !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] div[data-testid="column"]{{
    min-width:0 !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] div[data-testid="stButton"] button{{
    min-height:31px !important;
    padding:0 10px !important;
    white-space:nowrap !important;
    word-break:keep-all !important;
    overflow:hidden !important;
    text-overflow:ellipsis !important;
    font-size:11px !important;
    letter-spacing:.04em !important;
    border-radius:999px !important;
    border:1px solid rgba(255,61,0,.45) !important;
    background:
        linear-gradient(135deg,rgba(255,61,0,.16),rgba(46,203,242,.08)) !important;
    box-shadow:
        0 0 0 1px rgba(255,61,0,.10),
        0 0 12px rgba(255,61,0,.18),
        inset 0 1px 0 rgba(255,255,255,.08) !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] div[data-testid="stButton"] button::before{{
    content:"";
    width:10px;
    height:10px;
    min-width:10px;
    margin-right:7px;
    border-radius:999px;
    border:1px solid {NARANJO};
    background:rgba(255,61,0,.18);
    box-shadow:
        0 0 7px rgba(255,61,0,.70),
        0 0 14px rgba(255,61,0,.35),
        inset 0 0 6px rgba(255,61,0,.24);
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] div[data-testid="stButton"] button:hover{{
    border-color:rgba(255,61,0,.70) !important;
    background:
        linear-gradient(135deg,rgba(255,61,0,.22),rgba(46,203,242,.11)) !important;
    filter:brightness(1.05);
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] div[data-testid="stButton"] button p,
section[data-testid="stSidebar"] div[data-testid="stExpander"] div[data-testid="stButton"] button span{{
    white-space:nowrap !important;
    word-break:keep-all !important;
    overflow:hidden !important;
    text-overflow:ellipsis !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] div[data-testid="stCheckbox"] label p{{
    white-space:normal !important;
    overflow-wrap:normal !important;
    word-break:normal !important;
    line-height:1.15 !important;
}}

/* Estabilidad: hover premium sin saltos ni temblores */
section[data-testid="stSidebar"] *,
section[data-testid="stSidebar"] *:hover,
section[data-testid="stSidebar"] *:focus,
section[data-testid="stSidebar"] *:active{{
    transform-origin:center center !important;
}}

section[data-testid="stSidebar"] div[data-testid="stButton"] button:hover,
section[data-testid="stSidebar"] div[data-testid="stDownloadButton"] button:hover,
section[data-testid="stSidebar"] div[data-testid="stExpander"]:hover,
section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary:hover{{
    transform:none !important;
}}

.estado-info-note{{
    display:flex;
    align-items:center;
    gap:10px;
    margin:12px 0 2px 0;
    padding:11px 14px;
    border-radius:12px;
    border:1px solid rgba(253,108,152,.36);
    background:
        linear-gradient(135deg,rgba(253,108,152,.13),rgba(255,255,255,.92) 42%,rgba(46,203,242,.08));
    color:#694052;
    font-size:12px;
    font-weight:800;
    box-shadow:
        0 12px 26px rgba(253,108,152,.10),
        inset 0 1px 0 rgba(255,255,255,.86);
}}

.estado-info-note .info-icon{{
    width:25px;
    height:25px;
    min-width:25px;
    border-radius:9px;
    display:flex;
    align-items:center;
    justify-content:center;
    background:linear-gradient(135deg,{ROSADO},#FF9DBA);
    color:#FFFFFF;
    font-weight:950;
    box-shadow:0 8px 16px rgba(253,108,152,.28);
}}

/*======================================================
BLINDAJE VISUAL: MODO OSCURO DEL NAVEGADOR
======================================================*/

:root,
html,
body,
.stApp,
div[data-testid="stAppViewContainer"],
section.main,
.block-container{{
    color-scheme:light !important;
    forced-color-adjust:none !important;
}}

html,
body{{
    background:#F4F7FB !important;
    color:#0F172A !important;
}}

*{{
    color-scheme:light !important;
}}

html,
body,
.stApp,
div[data-testid="stAppViewContainer"],
div[data-testid="stMain"],
section[data-testid="stSidebar"],
div[data-testid="stPlotlyChart"],
div[data-testid="stDataFrame"],
.metric-card,
.disp-kpi-card,
.ai-insight-card{{
    user-select:none !important;
    -webkit-user-select:none !important;
}}

input,
textarea,
select,
button,
div[data-testid="stPlotlyChart"],
canvas,
svg,
img{{
    color-scheme:light !important;
    forced-color-adjust:none !important;
}}

img,
svg,
canvas{{
    filter:none;
    mix-blend-mode:normal !important;
}}

@media (prefers-color-scheme: dark){{
    html,
    body,
    .stApp,
    div[data-testid="stAppViewContainer"]{{
        background:
            radial-gradient(circle at 88% 4%,rgba(46,203,242,.16),transparent 28%),
            radial-gradient(circle at 20% 0%,rgba(16,6,159,.08),transparent 32%),
            linear-gradient(180deg,#FBFCFF 0%,#F3F7FC 100%) !important;
        color:#0F172A !important;
    }}
}}

/*======================================================
NEON GERENCIAL ENTEL: PREMIUM SIN PERDER LECTURA
======================================================*/

html,
body,
.stApp,
div[data-testid="stAppViewContainer"]{{
    background:
        radial-gradient(circle at 92% 5%,rgba(46,203,242,.22),transparent 28%),
        radial-gradient(circle at 5% 7%,rgba(16,6,159,.10),transparent 30%),
        radial-gradient(circle at 86% 78%,rgba(253,108,152,.10),transparent 26%),
        linear-gradient(180deg,#FBFCFF 0%,#F3F8FF 48%,#EFF5FC 100%) !important;
}}

@media (prefers-color-scheme: dark){{
    html,
    body,
    .stApp,
    div[data-testid="stAppViewContainer"]{{
        background:
            radial-gradient(circle at 92% 5%,rgba(46,203,242,.22),transparent 28%),
            radial-gradient(circle at 5% 7%,rgba(16,6,159,.10),transparent 30%),
            radial-gradient(circle at 86% 78%,rgba(253,108,152,.10),transparent 26%),
            linear-gradient(180deg,#FBFCFF 0%,#F3F8FF 48%,#EFF5FC 100%) !important;
        color:#0F172A !important;
    }}
}}

.block-container{{
    background:
        linear-gradient(180deg,rgba(255,255,255,.42),rgba(255,255,255,.12)) !important;
}}

.titulo{{
    color:{AZUL} !important;
    text-shadow:
        0 0 18px rgba(0,92,255,.18),
        0 6px 18px rgba(16,6,159,.10) !important;
}}

.subtitulo{{
    color:#526174 !important;
}}

.linea-titulo,
.kpi-divider{{
    height:4px !important;
    background:
        linear-gradient(90deg,{AZUL} 0%,{AZUL_CLARO} 28%,{CELESTE} 54%,{ROSADO} 78%,{NARANJO} 100%) !important;
    box-shadow:
        0 0 10px rgba(46,203,242,.42),
        0 0 18px rgba(0,92,255,.22),
        0 0 26px rgba(253,108,152,.12) !important;
}}

.kpi-title{{
    color:#101827 !important;
    text-shadow:
        0 0 14px rgba(46,203,242,.12),
        0 5px 16px rgba(16,6,159,.08) !important;
}}

div[data-testid="stPlotlyChart"]{{
    border-radius:13px !important;
    border:1px solid rgba(46,203,242,.24) !important;
    background:
        linear-gradient(145deg,rgba(255,255,255,.96),rgba(248,252,255,.92)) !important;
    box-shadow:
        0 18px 36px rgba(15,23,42,.10),
        0 0 0 1px rgba(255,255,255,.72),
        0 0 16px rgba(46,203,242,.16),
        0 0 28px rgba(0,92,255,.08),
        inset 0 1px 0 rgba(255,255,255,.95) !important;
}}

div[data-testid="stPlotlyChart"]:hover{{
    border-color:rgba(46,203,242,.38) !important;
    box-shadow:
        0 20px 40px rgba(15,23,42,.12),
        0 0 0 1px rgba(255,255,255,.82),
        0 0 20px rgba(46,203,242,.20),
        0 0 32px rgba(253,108,152,.10),
        inset 0 1px 0 rgba(255,255,255,.95) !important;
}}

.brand-lockup,
.estado-info-note{{
    box-shadow:
        0 14px 30px rgba(15,23,42,.10),
        0 0 18px rgba(46,203,242,.14),
        inset 0 1px 0 rgba(255,255,255,.78) !important;
}}

.estado-info-note{{
    border-color:rgba(253,108,152,.46) !important;
    background:
        linear-gradient(135deg,rgba(253,108,152,.15),rgba(255,255,255,.88) 46%,rgba(46,203,242,.11)) !important;
}}

/* Descarga puntual de revisitas: flecha neon ejecutiva */
.revisita-export-shell{{
    height:100%;
    min-height:74px;
    display:flex;
    align-items:center;
    justify-content:center;
    padding:4px 0;
}}

.revisita-download-icon{{
    width:54px;
    height:58px;
    border-radius:16px;
    display:flex;
    align-items:center;
    justify-content:center;
    text-decoration:none !important;
    color:{NARANJO} !important;
    color-scheme:light !important;
    forced-color-adjust:none !important;
    border:1px solid rgba(255,61,0,.72);
    background:
        radial-gradient(circle at 50% 16%,rgba(255,255,255,.50),transparent 24%),
        radial-gradient(circle at 78% 82%,rgba(46,203,242,.22),transparent 34%),
        linear-gradient(145deg,rgba(255,61,0,.24),rgba(255,255,255,.92) 48%,rgba(46,203,242,.15));
    box-shadow:
        0 0 12px rgba(255,61,0,.52),
        0 0 22px rgba(46,203,242,.26),
        0 14px 28px rgba(15,23,42,.13),
        inset 0 1px 0 rgba(255,255,255,.88),
        inset 0 -12px 22px rgba(255,61,0,.10);
    transition:box-shadow .16s ease, border-color .16s ease, filter .16s ease;
}}

.revisita-download-icon:hover{{
    color:#FFFFFF !important;
    border-color:rgba(255,61,0,.95);
    background:
        radial-gradient(circle at 50% 16%,rgba(255,255,255,.36),transparent 24%),
        radial-gradient(circle at 78% 82%,rgba(46,203,242,.32),transparent 34%),
        linear-gradient(145deg,rgba(255,61,0,.86),rgba(255,83,36,.78) 48%,rgba(46,203,242,.26));
    box-shadow:
        0 0 16px rgba(255,61,0,.76),
        0 0 32px rgba(46,203,242,.30),
        0 16px 30px rgba(15,23,42,.16),
        inset 0 1px 0 rgba(255,255,255,.76);
    filter:brightness(1.04);
}}

.revisita-download-icon svg{{
    width:28px;
    height:28px;
    stroke:currentColor;
    filter:
        drop-shadow(0 0 5px rgba(255,61,0,.65))
        drop-shadow(0 0 8px rgba(46,203,242,.30));
}}

@media (prefers-color-scheme: dark){{
    .revisita-download-icon{{
        color:{NARANJO} !important;
        background:
            radial-gradient(circle at 50% 16%,rgba(255,255,255,.50),transparent 24%),
            radial-gradient(circle at 78% 82%,rgba(46,203,242,.22),transparent 34%),
            linear-gradient(145deg,rgba(255,61,0,.24),rgba(255,255,255,.92) 48%,rgba(46,203,242,.15)) !important;
    }}
}}

/* Logo IBM integrado: sin placa blanca */
.brand-lockup,
.brand-lockup-ibm{{
    height:52px !important;
    display:flex !important;
    align-items:flex-start !important;
    justify-content:flex-end !important;
    background:transparent !important;
    border:0 !important;
    box-shadow:none !important;
    filter:none !important;
    padding:0 !important;
    margin:0 !important;
}}

.brand-lockup img,
.brand-lockup-ibm img{{
    width:104px !important;
    height:auto !important;
    display:block !important;
    background:transparent !important;
    border:0 !important;
    box-shadow:none !important;
    opacity:.96 !important;
    mix-blend-mode:multiply !important;
    filter:
        drop-shadow(0 0 4px rgba(46,203,242,.20))
        drop-shadow(0 8px 11px rgba(16,6,159,.10)) !important;
}}

/*======================================================
NAVEGACION KPI TIPO CARPETA
======================================================*/

div[role="radiogroup"][aria-label="Selector KPI"]{{
    display:flex;
    flex-wrap:wrap;
    gap:8px;
    align-items:flex-end;
    padding:18px 0 0 0;
    margin:8px 0 22px 0;
    border-bottom:4px solid rgba(46,203,242,.72);
    filter:drop-shadow(0 0 14px rgba(46,203,242,.22));
}}

div[role="radiogroup"][aria-label="Selector KPI"] label{{
    position:relative;
    min-width:238px;
    min-height:70px;
    padding:18px 24px 13px 24px;
    margin:0 0 -4px 0;
    border:1px solid rgba(46,203,242,.42);
    border-bottom:0;
    border-radius:14px 14px 0 0;
    background:
        radial-gradient(circle at 90% 0%,rgba(46,203,242,.24),transparent 28%),
        linear-gradient(180deg,rgba(255,255,255,.88),rgba(236,249,255,.64));
    box-shadow:inset 0 1px 0 rgba(255,255,255,.95),0 -2px 18px rgba(46,203,242,.14),0 12px 22px rgba(16,6,159,.07);
    transform:translateY(5px);
    transition:all .18s ease;
}}

div[role="radiogroup"][aria-label="Selector KPI"] label:hover{{
    transform:translateY(0);
    border-color:rgba(46,203,242,.82);
    box-shadow:0 0 20px rgba(46,203,242,.30),inset 0 1px 0 rgba(255,255,255,.95);
}}

div[role="radiogroup"][aria-label="Selector KPI"] label:has(input:checked){{
    background:linear-gradient(180deg,#FFFFFF 0%,#F4FCFF 100%);
    border-color:#2ECBF2;
    transform:translateY(0);
    z-index:2;
    box-shadow:0 0 0 1px rgba(46,203,242,.58),0 0 28px rgba(46,203,242,.50),0 -2px 30px rgba(16,6,159,.18);
}}

div[role="radiogroup"][aria-label="Selector KPI"] label:has(input:checked)::before{{
    content:"";
    position:absolute;
    left:10px;
    right:10px;
    top:0;
    height:4px;
    border-radius:999px;
    background:linear-gradient(90deg,#10069F,#2ECBF2,#FF3D00);
    box-shadow:0 0 14px rgba(46,203,242,.80);
}}

div[role="radiogroup"][aria-label="Selector KPI"] label p{{
    color:#005CFF !important;
    font-weight:950 !important;
    letter-spacing:0 !important;
    font-size:15px !important;
    line-height:1.22 !important;
    margin:0 !important;
    white-space:normal !important;
}}

div[role="radiogroup"][aria-label="Selector KPI"] label input{{
    position:absolute !important;
    opacity:0 !important;
    width:0 !important;
    height:0 !important;
    pointer-events:none !important;
}}

div[role="radiogroup"][aria-label="Selector KPI"] label > div:first-child:not(:has(p)){{
    display:none !important;
}}

div[role="radiogroup"][aria-label="Selector KPI"] label:has(input:checked) p{{
    color:#10069F !important;
    text-shadow:0 0 12px rgba(46,203,242,.34);
}}

/*======================================================
LIQUID GLASS NEON - ESTILO EPA PARA DASHBOARD
======================================================*/

@property --dash-border-angle {{
    syntax:"<angle>";
    initial-value:0deg;
    inherits:false;
}}

@keyframes dashBorderSpin {{
    to {{ --dash-border-angle:360deg; }}
}}

@keyframes dashGridDrift {{
    from {{ background-position:0 0, 0 0, 0 0; }}
    to {{ background-position:48px 48px, -48px 24px, 0 0; }}
}}

@keyframes glassSweep {{
    0% {{ transform:translateX(-120%) skewX(-18deg); opacity:0; }}
    18% {{ opacity:.74; }}
    48% {{ opacity:.38; }}
    100% {{ transform:translateX(150%) skewX(-18deg); opacity:0; }}
}}

@keyframes glassBreath {{
    0%,100% {{
        box-shadow:
            0 18px 42px rgba(0,0,0,.18),
            0 0 0 1px rgba(46,203,242,.18),
            0 0 24px rgba(46,203,242,.10);
    }}
    50% {{
        box-shadow:
            0 22px 52px rgba(0,0,0,.22),
            0 0 0 1px rgba(46,203,242,.32),
            0 0 34px rgba(46,203,242,.22);
    }}
}}

@keyframes neonPulseLine {{
    0%,100% {{ filter:drop-shadow(0 0 7px rgba(46,203,242,.44)); opacity:.86; }}
    50% {{ filter:drop-shadow(0 0 18px rgba(46,203,242,.92)); opacity:1; }}
}}

.stApp{{
    background:
        linear-gradient(rgba(255,255,255,.030) 1px, transparent 1px),
        linear-gradient(90deg,rgba(255,255,255,.030) 1px, transparent 1px),
        radial-gradient(circle at 12% 8%,rgba(0,92,255,.34),transparent 34rem),
        radial-gradient(circle at 92% 10%,rgba(253,108,152,.20),transparent 32rem),
        radial-gradient(circle at 54% 92%,rgba(46,203,242,.18),transparent 30rem),
        linear-gradient(135deg,#061426 0%,#07111E 45%,#160A18 100%) !important;
    background-size:24px 24px,24px 24px,auto,auto,auto,auto !important;
    animation:dashGridDrift 34s linear infinite;
}}

div[data-testid="stAppViewContainer"] > .main .block-container{{
    position:relative;
    max-width:1500px;
    padding-top:2.2rem;
    padding-bottom:3rem;
    border-radius:28px;
    border:1px solid rgba(255,255,255,.34);
    background:
        radial-gradient(circle at 92% 4%,rgba(46,203,242,.18),transparent 26rem),
        radial-gradient(circle at 5% 12%,rgba(255,255,255,.56),transparent 22rem),
        linear-gradient(135deg,rgba(255,255,255,.78),rgba(236,249,255,.58) 48%,rgba(255,255,255,.46));
    backdrop-filter:blur(22px) saturate(1.45);
    -webkit-backdrop-filter:blur(22px) saturate(1.45);
    box-shadow:
        0 28px 78px rgba(0,0,0,.26),
        inset 0 1px 0 rgba(255,255,255,.78),
        0 0 0 1px rgba(46,203,242,.12);
}}

div[data-testid="stAppViewContainer"] > .main .block-container::before{{
    content:"";
    position:absolute;
    inset:0;
    border-radius:28px;
    padding:2px;
    pointer-events:none;
    background:conic-gradient(
        from var(--dash-border-angle),
        rgba(46,203,242,.95),
        rgba(0,92,255,.72),
        rgba(255,61,0,.74),
        rgba(253,108,152,.64),
        rgba(46,203,242,.95)
    );
    -webkit-mask:
        linear-gradient(#000 0 0) content-box,
        linear-gradient(#000 0 0);
    -webkit-mask-composite:xor;
    mask-composite:exclude;
    opacity:.72;
    animation:dashBorderSpin 9s linear infinite;
}}

.titulo{{
    color:#FFFFFF !important;
    font-size:clamp(40px,4.5vw,64px) !important;
    letter-spacing:0 !important;
    text-shadow:
        0 0 12px rgba(46,203,242,.56),
        0 0 28px rgba(0,92,255,.32),
        0 14px 24px rgba(0,0,0,.20) !important;
}}

.subtitulo{{
    color:#D9F6FF !important;
    text-shadow:0 0 12px rgba(46,203,242,.22);
}}

.linea-titulo,
.kpi-divider{{
    height:5px !important;
    border-radius:999px !important;
    background:linear-gradient(90deg,{AZUL},{AZUL_CLARO},{CELESTE},{NARANJO},{ROSADO}) !important;
    background-size:220% 100% !important;
    box-shadow:
        0 0 14px rgba(46,203,242,.58),
        0 0 26px rgba(0,92,255,.28) !important;
    animation:neonPulseLine 3.4s ease-in-out infinite;
}}

section[data-testid="stSidebar"]{{
    position:relative !important;
    overflow:visible !important;
    border-right:0 !important;
    background:
        linear-gradient(rgba(255,255,255,.035) 1px, transparent 1px),
        linear-gradient(90deg,rgba(255,255,255,.035) 1px, transparent 1px),
        radial-gradient(circle at 22% 0%,rgba(46,203,242,.22),transparent 18rem),
        radial-gradient(circle at 100% 18%,rgba(253,108,152,.18),transparent 16rem),
        linear-gradient(180deg,rgba(5,12,24,.94),rgba(4,9,18,.98)) !important;
    background-size:24px 24px,24px 24px,auto,auto,auto !important;
    backdrop-filter:blur(24px) saturate(1.35);
    -webkit-backdrop-filter:blur(24px) saturate(1.35);
    box-shadow:
        24px 0 62px rgba(0,0,0,.34),
        inset -1px 0 0 rgba(46,203,242,.24) !important;
}}

section[data-testid="stSidebar"]::before{{
    content:"";
    position:absolute;
    inset:9px 8px 18px 8px;
    border-radius:24px;
    padding:2px;
    pointer-events:none;
    z-index:4;
    background:conic-gradient(
        from var(--dash-border-angle),
        rgba(46,203,242,1),
        rgba(0,92,255,.80),
        rgba(255,61,0,.82),
        rgba(253,108,152,.72),
        rgba(46,203,242,1)
    );
    -webkit-mask:
        linear-gradient(#000 0 0) content-box,
        linear-gradient(#000 0 0);
    -webkit-mask-composite:xor;
    mask-composite:exclude;
    filter:drop-shadow(0 0 12px rgba(46,203,242,.70));
    animation:dashBorderSpin 5.4s linear infinite;
}}

section[data-testid="stSidebar"]::after{{
    content:"";
    position:absolute;
    top:0;
    right:-2px;
    width:3px;
    height:100%;
    pointer-events:none;
    background:linear-gradient(180deg,{AZUL_CLARO},{CELESTE},{NARANJO},{ROSADO},{CELESTE});
    box-shadow:
        0 0 16px rgba(46,203,242,.78),
        0 0 30px rgba(0,92,255,.36);
    animation:neonPulseLine 2.6s ease-in-out infinite;
}}

.sidebar-logo-shell{{
    position:relative;
    padding:14px 0 6px;
    border-radius:22px;
    background:
        radial-gradient(circle at 50% 0%,rgba(255,255,255,.18),transparent 42%),
        linear-gradient(180deg,rgba(255,255,255,.045),rgba(255,255,255,.015));
    box-shadow:inset 0 1px 0 rgba(255,255,255,.12);
}}

.filter-section-label{{
    position:relative;
    overflow:hidden;
    min-height:58px;
    border-radius:17px !important;
    border:1px solid rgba(46,203,242,.40) !important;
    background:
        radial-gradient(circle at 14% 0%,rgba(46,203,242,.22),transparent 34%),
        linear-gradient(135deg,rgba(255,255,255,.11),rgba(255,255,255,.035)) !important;
    backdrop-filter:blur(16px) saturate(1.35);
    -webkit-backdrop-filter:blur(16px) saturate(1.35);
    box-shadow:
        0 14px 30px rgba(0,0,0,.24),
        inset 0 1px 0 rgba(255,255,255,.18),
        0 0 18px rgba(46,203,242,.12) !important;
}}

.filter-section-label::after{{
    content:"";
    position:absolute;
    inset:-40% -70%;
    background:linear-gradient(115deg,transparent 44%,rgba(255,255,255,.22) 50%,transparent 56%);
    animation:glassSweep 7s ease-in-out infinite;
    pointer-events:none;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"]{{
    position:relative;
    overflow:hidden;
    border-radius:18px !important;
    border:1px solid rgba(46,203,242,.38) !important;
    background:
        linear-gradient(145deg,rgba(255,255,255,.105),rgba(255,255,255,.035) 62%,rgba(46,203,242,.055)) !important;
    backdrop-filter:blur(18px) saturate(1.35);
    -webkit-backdrop-filter:blur(18px) saturate(1.35);
    box-shadow:
        0 16px 34px rgba(0,0,0,.30),
        inset 0 1px 0 rgba(255,255,255,.16),
        0 0 18px rgba(46,203,242,.13) !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"]:has(details[open]){{
    border-color:rgba(46,203,242,.72) !important;
    box-shadow:
        0 0 0 1px rgba(46,203,242,.24),
        0 0 26px rgba(46,203,242,.24),
        0 18px 38px rgba(0,0,0,.32),
        inset 0 1px 0 rgba(255,255,255,.20) !important;
}}

div[data-testid="stPlotlyChart"]{{
    position:relative;
    overflow:hidden;
    border-radius:22px;
    border:1px solid rgba(46,203,242,.34);
    background:
        radial-gradient(circle at 92% 0%,rgba(46,203,242,.18),transparent 24%),
        radial-gradient(circle at 0% 100%,rgba(253,108,152,.10),transparent 28%),
        linear-gradient(135deg,rgba(255,255,255,.72),rgba(238,249,255,.48));
    backdrop-filter:blur(18px) saturate(1.3);
    -webkit-backdrop-filter:blur(18px) saturate(1.3);
    box-shadow:
        0 18px 42px rgba(0,0,0,.16),
        inset 0 1px 0 rgba(255,255,255,.72),
        0 0 22px rgba(46,203,242,.10);
    animation:glassBreath 6.8s ease-in-out infinite;
}}

div[data-testid="stPlotlyChart"]::before{{
    content:"";
    position:absolute;
    inset:-30% -70%;
    z-index:3;
    pointer-events:none;
    background:linear-gradient(115deg,transparent 44%,rgba(255,255,255,.28) 50%,transparent 56%);
    animation:glassSweep 8.5s ease-in-out infinite;
}}

div[data-testid="stPlotlyChart"]::after{{
    content:"";
    position:absolute;
    inset:0;
    z-index:4;
    pointer-events:none;
    border-radius:22px;
    padding:1px;
    background:conic-gradient(
        from var(--dash-border-angle),
        rgba(46,203,242,.72),
        rgba(0,92,255,.42),
        rgba(255,61,0,.46),
        rgba(253,108,152,.42),
        rgba(46,203,242,.72)
    );
    -webkit-mask:
        linear-gradient(#000 0 0) content-box,
        linear-gradient(#000 0 0);
    -webkit-mask-composite:xor;
    mask-composite:exclude;
    animation:dashBorderSpin 8s linear infinite;
}}

div[data-testid="stDataFrame"],
div[data-testid="stTable"]{{
    overflow:hidden;
    border-radius:18px;
    border:1px solid rgba(46,203,242,.28);
    background:rgba(255,255,255,.62);
    backdrop-filter:blur(14px) saturate(1.2);
    -webkit-backdrop-filter:blur(14px) saturate(1.2);
    box-shadow:
        0 16px 34px rgba(0,0,0,.12),
        inset 0 1px 0 rgba(255,255,255,.66);
}}

div[role="radiogroup"][aria-label="Selector KPI"]{{
    position:relative;
    padding:18px 0 0 0 !important;
    border-bottom:1px solid rgba(46,203,242,.58) !important;
    filter:drop-shadow(0 0 18px rgba(46,203,242,.20));
}}

div[role="radiogroup"][aria-label="Selector KPI"] label{{
    overflow:hidden;
    border-radius:18px 18px 0 0 !important;
    border-color:rgba(46,203,242,.42) !important;
    background:
        radial-gradient(circle at 92% 0%,rgba(46,203,242,.26),transparent 32%),
        linear-gradient(180deg,rgba(255,255,255,.74),rgba(236,249,255,.50)) !important;
    backdrop-filter:blur(16px) saturate(1.35);
    -webkit-backdrop-filter:blur(16px) saturate(1.35);
}}

div[role="radiogroup"][aria-label="Selector KPI"] label:has(input:checked){{
    background:
        radial-gradient(circle at 92% 0%,rgba(46,203,242,.36),transparent 36%),
        linear-gradient(180deg,rgba(255,255,255,.94),rgba(239,252,255,.74)) !important;
    box-shadow:
        0 0 0 1px rgba(46,203,242,.64),
        0 0 32px rgba(46,203,242,.48),
        0 -2px 30px rgba(16,6,159,.18),
        inset 0 1px 0 rgba(255,255,255,.92) !important;
}}

div[role="radiogroup"][aria-label="Selector KPI"] label:has(input:checked)::after{{
    content:"";
    position:absolute;
    inset:-50% -85%;
    background:linear-gradient(115deg,transparent 45%,rgba(255,255,255,.42) 50%,transparent 55%);
    animation:glassSweep 6.4s ease-in-out infinite;
    pointer-events:none;
}}

.kpi-title{{
    color:#07162F !important;
    text-shadow:0 0 12px rgba(46,203,242,.34),0 10px 18px rgba(255,255,255,.42);
}}

.chart-card,
.kpi-card{{
    border:1px solid rgba(46,203,242,.30) !important;
    background:
        radial-gradient(circle at 100% 0%,rgba(46,203,242,.14),transparent 28%),
        linear-gradient(135deg,rgba(255,255,255,.72),rgba(255,255,255,.44)) !important;
    backdrop-filter:blur(18px) saturate(1.28);
    -webkit-backdrop-filter:blur(18px) saturate(1.28);
    box-shadow:
        0 18px 42px rgba(0,0,0,.14),
        inset 0 1px 0 rgba(255,255,255,.72),
        0 0 20px rgba(46,203,242,.11) !important;
}}

/*======================================================
CORRECCION VISUAL: FONDO OSCURO TOTAL + FILTROS LIMPIOS
======================================================*/

div[data-testid="stAppViewContainer"],
section.main,
div[data-testid="stAppViewContainer"] > .main,
.main .block-container,
.block-container,
div[data-testid="stAppViewContainer"] > .main .block-container{{
    background:
        linear-gradient(rgba(255,255,255,.035) 1px, transparent 1px),
        linear-gradient(90deg,rgba(255,255,255,.035) 1px, transparent 1px),
        radial-gradient(circle at 13% 7%,rgba(0,92,255,.32),transparent 34rem),
        radial-gradient(circle at 92% 16%,rgba(253,108,152,.16),transparent 30rem),
        radial-gradient(circle at 56% 96%,rgba(46,203,242,.16),transparent 32rem),
        linear-gradient(135deg,#061426 0%,#07111E 48%,#160A18 100%) !important;
    background-size:24px 24px,24px 24px,auto,auto,auto,auto !important;
}}

div[data-testid="stAppViewContainer"] > .main .block-container,
.main .block-container,
.block-container{{
    border-radius:0 !important;
    border:0 !important;
    box-shadow:none !important;
    backdrop-filter:none !important;
    -webkit-backdrop-filter:none !important;
}}

div[data-testid="stAppViewContainer"] > .main .block-container::before{{
    display:none !important;
}}

div[data-testid="stAppViewContainer"] > .main{{
    border-left:1px solid rgba(46,203,242,.30);
    box-shadow:inset 1px 0 0 rgba(255,255,255,.035);
}}

.titulo{{
    color:#F7FBFF !important;
    text-shadow:
        0 0 10px rgba(46,203,242,.64),
        0 0 24px rgba(0,92,255,.36),
        0 15px 24px rgba(0,0,0,.46) !important;
}}

.subtitulo{{
    color:#BDEFFF !important;
    opacity:.96;
}}

.brand-lockup img,
.brand-lockup-ibm img{{
    mix-blend-mode:screen !important;
    opacity:.94 !important;
    filter:
        drop-shadow(0 0 8px rgba(46,203,242,.36))
        drop-shadow(0 10px 16px rgba(0,0,0,.24)) !important;
}}

.brand-lockup-ecc{{
    height:54px !important;
    align-items:flex-start !important;
    justify-content:flex-end !important;
}}

.brand-lockup-ecc img{{
    width:126px !important;
    max-width:126px !important;
    padding:7px 10px !important;
    border-radius:0 !important;
    background:
        linear-gradient(115deg,rgba(0,0,0,.88),rgba(4,16,34,.70) 58%,rgba(46,203,242,.10)) !important;
    mix-blend-mode:normal !important;
    opacity:.96 !important;
    box-shadow:
        inset 0 1px 0 rgba(255,255,255,.13),
        0 0 0 1px rgba(46,203,242,.18),
        0 12px 22px rgba(0,0,0,.22) !important;
    filter:
        drop-shadow(0 0 7px rgba(46,203,242,.20))
        drop-shadow(0 9px 12px rgba(0,0,0,.18)) !important;
}}

section[data-testid="stSidebar"] .filter-section-label{{
    display:grid !important;
    grid-template-columns:46px minmax(0,1fr) 20px !important;
    align-items:center !important;
    gap:10px !important;
    min-height:58px !important;
    width:100% !important;
    margin:0 0 11px 0 !important;
    padding:9px 12px 9px 9px !important;
    border-radius:15px !important;
    border:1px solid rgba(46,203,242,.50) !important;
    background:
        linear-gradient(90deg,rgba(46,203,242,.16),rgba(0,92,255,.07) 58%,rgba(253,108,152,.08)) !important;
    box-shadow:
        0 12px 24px rgba(0,0,0,.24),
        inset 0 1px 0 rgba(255,255,255,.10),
        0 0 18px rgba(46,203,242,.16) !important;
    filter:none !important;
    transform:none !important;
}}

section[data-testid="stSidebar"] .filter-section-label::after{{
    display:none !important;
}}

section[data-testid="stSidebar"] .filter-section-label .filter-icon{{
    position:relative !important;
    left:auto !important;
    top:auto !important;
    right:auto !important;
    bottom:auto !important;
    transform:none !important;
    width:38px !important;
    height:38px !important;
    min-width:38px !important;
    margin:0 !important;
    padding:0 !important;
    border-radius:12px !important;
    display:grid !important;
    place-items:center !important;
    color:{CELESTE} !important;
    border:1px solid rgba(46,203,242,.62) !important;
    background:
        radial-gradient(circle at 38% 24%,rgba(255,255,255,.24),transparent 28%),
        linear-gradient(145deg,rgba(46,203,242,.20),rgba(0,92,255,.10)) !important;
    box-shadow:
        0 0 14px rgba(46,203,242,.34),
        inset 0 1px 0 rgba(255,255,255,.22) !important;
}}

section[data-testid="stSidebar"] .filter-section-label .filter-icon::before,
section[data-testid="stSidebar"] .filter-section-label .filter-icon::after{{
    display:none !important;
}}

section[data-testid="stSidebar"] .filter-section-label .filter-icon svg{{
    width:21px !important;
    height:21px !important;
    display:block !important;
    overflow:visible !important;
    stroke:{CELESTE} !important;
    fill:none !important;
    stroke-width:2.1 !important;
    filter:drop-shadow(0 0 6px rgba(46,203,242,.58)) !important;
}}

section[data-testid="stSidebar"] .filter-section-label .filter-icon svg *,
section[data-testid="stSidebar"] .filter-section-label .filter-icon svg path,
section[data-testid="stSidebar"] .filter-section-label .filter-icon svg circle{{
    stroke:{CELESTE} !important;
    fill:none !important;
}}

section[data-testid="stSidebar"] .filter-section-label .filter-label-copy{{
    min-width:0 !important;
    display:flex !important;
    flex-direction:column !important;
    justify-content:center !important;
    gap:2px !important;
}}

section[data-testid="stSidebar"] .filter-label-copy b{{
    color:#FFFFFF !important;
    font-size:12px !important;
    font-weight:950 !important;
    letter-spacing:.07em !important;
    text-transform:uppercase !important;
    line-height:1.05 !important;
    text-shadow:0 0 10px rgba(46,203,242,.34);
}}

section[data-testid="stSidebar"] .filter-label-copy small{{
    color:#8FEFFF !important;
    font-size:9.5px !important;
    font-weight:800 !important;
    letter-spacing:0 !important;
    line-height:1.05 !important;
    opacity:.78 !important;
}}

section[data-testid="stSidebar"] .filter-section-label::before{{
    content:"";
    width:18px;
    height:2px;
    justify-self:end;
    border-radius:999px;
    background:linear-gradient(90deg,{CELESTE},{ROSADO});
    box-shadow:0 0 9px rgba(46,203,242,.64);
}}

section[data-testid="stSidebar"][aria-expanded="false"] .filter-section-label{{
    display:grid !important;
    grid-template-columns:1fr !important;
    width:46px !important;
    height:46px !important;
    min-height:46px !important;
    padding:4px !important;
    margin:0 auto 14px auto !important;
    place-items:center !important;
}}

section[data-testid="stSidebar"][aria-expanded="false"] .filter-section-label .filter-icon{{
    width:36px !important;
    height:36px !important;
    min-width:36px !important;
}}

section[data-testid="stSidebar"][aria-expanded="false"] .filter-section-label::before,
section[data-testid="stSidebar"][aria-expanded="false"] .filter-label-copy{{
    display:none !important;
}}

section[data-testid="stSidebar"] .filter-section-label{{
    grid-template-columns:34px minmax(0,1fr) 18px !important;
    min-height:50px !important;
    padding:8px 11px !important;
    gap:10px !important;
    border-radius:14px !important;
    background:
        linear-gradient(90deg,rgba(8,22,39,.96),rgba(6,18,34,.90) 58%,rgba(15,25,39,.92)) !important;
}}

section[data-testid="stSidebar"] .filter-symbol{{
    width:28px !important;
    height:28px !important;
    min-width:28px !important;
    display:block !important;
    border-radius:10px !important;
    border:1px solid rgba(46,203,242,.42) !important;
    background-color:rgba(46,203,242,.08) !important;
    background-repeat:no-repeat !important;
    background-position:center !important;
    background-size:17px 17px !important;
    box-shadow:
        0 0 10px rgba(46,203,242,.20),
        inset 0 1px 0 rgba(255,255,255,.12) !important;
}}

section[data-testid="stSidebar"] .filter-symbol-region{{
    background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%232ECBF2' stroke-width='2.15' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 21s6-5.2 6-11a6 6 0 0 0-12 0c0 5.8 6 11 6 11Z'/%3E%3Ccircle cx='12' cy='10' r='2.4'/%3E%3C/svg%3E") !important;
}}

section[data-testid="stSidebar"] .filter-symbol-tech{{
    background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%232ECBF2' stroke-width='2.15' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='12' cy='7.5' r='3.2'/%3E%3Cpath d='M5.5 20c.8-4.4 3.2-6.5 6.5-6.5s5.7 2.1 6.5 6.5'/%3E%3C/svg%3E") !important;
}}

section[data-testid="stSidebar"] .filter-symbol-period{{
    background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%232ECBF2' stroke-width='2.15' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M7 4v3M17 4v3M4.5 9h15'/%3E%3Crect x='4' y='6' width='16' height='14' rx='2.5'/%3E%3Cpath d='M8 13h3M13 13h3'/%3E%3C/svg%3E") !important;
}}

section[data-testid="stSidebar"] .filter-icon,
section[data-testid="stSidebar"] .filter-icon *,
section[data-testid="stSidebar"] .filter-icon::before,
section[data-testid="stSidebar"] .filter-icon::after{{
    display:none !important;
}}

section[data-testid="stSidebar"] .filter-section-label::before{{
    width:16px !important;
    height:2px !important;
    opacity:.85 !important;
}}

section[data-testid="stSidebar"][aria-expanded="false"] .filter-section-label{{
    grid-template-columns:1fr !important;
    width:42px !important;
    height:42px !important;
    min-height:42px !important;
}}

section[data-testid="stSidebar"][aria-expanded="false"] .filter-symbol{{
    width:30px !important;
    height:30px !important;
    min-width:30px !important;
}}

div[data-testid="stPlotlyChart"]{{
    border:1px solid rgba(46,203,242,.36) !important;
    background:
        radial-gradient(circle at 96% 8%,rgba(46,203,242,.16),transparent 26%),
        radial-gradient(circle at 0% 100%,rgba(253,108,152,.08),transparent 30%),
        linear-gradient(135deg,rgba(7,18,34,.86),rgba(5,13,25,.72)) !important;
    box-shadow:
        0 18px 42px rgba(0,0,0,.24),
        inset 0 1px 0 rgba(255,255,255,.09),
        0 0 22px rgba(46,203,242,.12) !important;
}}

div[data-testid="stPlotlyChart"] .main-svg{{
    background:transparent !important;
}}

div[data-testid="stPlotlyChart"] .bg{{
    fill:rgba(6,18,34,.70) !important;
}}

div[data-testid="stPlotlyChart"] .gridlayer path{{
    stroke:rgba(143,239,255,.14) !important;
}}

div[data-testid="stPlotlyChart"] .zerolinelayer path{{
    stroke:rgba(143,239,255,.16) !important;
}}

div[data-testid="stPlotlyChart"] .legend rect.bg{{
    fill:rgba(6,18,34,.84) !important;
    stroke:rgba(46,203,242,.35) !important;
}}

div[data-testid="stPlotlyChart"] .xtick text,
div[data-testid="stPlotlyChart"] .ytick text,
div[data-testid="stPlotlyChart"] .legend text{{
    fill:#DDFBFF !important;
}}

div[data-testid="stMarkdownContainer"] > div[style*="background:radial-gradient"],
div[data-testid="stMarkdownContainer"] > div[style*="background: radial-gradient"],
div[data-testid="stMarkdownContainer"] > div[style*="border-top"]{{
    background:
        radial-gradient(circle at 96% 18%,rgba(46,203,242,.16),transparent 24%),
        linear-gradient(180deg,rgba(7,18,34,.92),rgba(5,13,25,.82)) !important;
    border-color:rgba(46,203,242,.40) !important;
    box-shadow:
        0 16px 34px rgba(0,0,0,.24),
        inset 0 1px 0 rgba(255,255,255,.10),
        0 0 18px rgba(46,203,242,.12) !important;
}}

div[data-testid="stMarkdownContainer"] > div[style*="background:radial-gradient"] div,
div[data-testid="stMarkdownContainer"] > div[style*="background: radial-gradient"] div,
div[data-testid="stMarkdownContainer"] > div[style*="border-top"] div{{
    color:#EAFBFF !important;
}}

/*======================================================
AJUSTE FINAL: FILTROS TIPO EXPORTAR + ESTADO COMPACTO
======================================================*/

section[data-testid="stSidebar"] .filter-section-label{{
    display:none !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"]{{
    margin:0 0 26px 0 !important;
    padding:0 !important;
    border:0 !important;
    border-radius:14px !important;
    background:transparent !important;
    box-shadow:none !important;
    overflow:visible !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details{{
    overflow:hidden !important;
    border-radius:14px !important;
    border:1px solid rgba(253,108,152,.56) !important;
    background:
        radial-gradient(circle at 82% 18%,rgba(253,108,152,.35),transparent 36%),
        radial-gradient(circle at 16% 86%,rgba(46,203,242,.16),transparent 34%),
        linear-gradient(145deg,rgba(253,108,152,.16),rgba(18,8,32,.95) 62%,rgba(5,10,20,.98)) !important;
    box-shadow:
        0 0 18px rgba(253,108,152,.20),
        0 16px 30px rgba(0,0,0,.30),
        inset 0 1px 0 rgba(255,255,255,.10) !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details[open]{{
    border-color:rgba(253,108,152,.88) !important;
    box-shadow:
        0 0 22px rgba(253,108,152,.28),
        0 0 28px rgba(46,203,242,.13),
        0 18px 32px rgba(0,0,0,.32),
        inset 0 1px 0 rgba(255,255,255,.14) !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary,
section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary:hover,
section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary:focus,
section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary:active{{
    display:grid !important;
    grid-template-columns:minmax(0,1fr) 18px !important;
    align-items:center !important;
    gap:12px !important;
    min-height:62px !important;
    padding:12px 15px !important;
    border:0 !important;
    background:transparent !important;
    cursor:pointer !important;
    list-style:none !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary::-webkit-details-marker{{
    display:none !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary svg,
section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary [data-testid="stExpanderToggleIcon"]{{
    display:none !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary > span{{
    display:grid !important;
    grid-template-columns:42px minmax(0,1fr) !important;
    align-items:center !important;
    gap:17px !important;
    width:100% !important;
    height:auto !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary > span > span{{
    display:flex !important;
    align-items:center !important;
    justify-content:center !important;
    width:42px !important;
    height:42px !important;
    min-width:42px !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary > span > div,
section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary [data-testid="stMarkdownContainer"]{{
    display:block !important;
    min-width:0 !important;
    width:100% !important;
    height:auto !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary [data-testid="stIconMaterial"]{{
    display:block !important;
    box-sizing:border-box !important;
    width:42px;
    height:42px;
    min-width:42px;
    border-radius:12px;
    border:1px solid rgba(253,108,152,.82);
    color:transparent !important;
    font-size:0 !important;
    line-height:0 !important;
    overflow:hidden !important;
    background-color:rgba(253,108,152,.14) !important;
    background-image:
        url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23FFFFFF' stroke-width='2.35' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M4 6h16'/%3E%3Cpath d='M4 12h16'/%3E%3Cpath d='M4 18h16'/%3E%3Ccircle cx='9' cy='6' r='2'/%3E%3Ccircle cx='15' cy='12' r='2'/%3E%3Ccircle cx='11' cy='18' r='2'/%3E%3C/svg%3E"),
        radial-gradient(circle at 50% 30%,rgba(253,108,152,.30),transparent 42%),
        linear-gradient(145deg,rgba(253,108,152,.22),rgba(46,203,242,.10)) !important;
    background-repeat:no-repeat,no-repeat,no-repeat !important;
    background-position:center,center,center !important;
    background-size:24px 24px,cover,cover !important;
    box-shadow:
        0 0 15px rgba(253,108,152,.48),
        0 0 24px rgba(46,203,242,.18),
        inset 0 1px 0 rgba(255,255,255,.22);
}}

section[data-testid="stSidebar"] .filter-anchor{{
    display:none !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details:has(.filter-anchor-region) summary [data-testid="stIconMaterial"]{{
    background-image:
        url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23FFFFFF' stroke-width='2.25' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 21s6-5.2 6-11a6 6 0 0 0-12 0c0 5.8 6 11 6 11Z'/%3E%3Ccircle cx='12' cy='10' r='2.4'/%3E%3C/svg%3E"),
        radial-gradient(circle at 50% 30%,rgba(46,203,242,.34),transparent 42%),
        linear-gradient(145deg,rgba(46,203,242,.26),rgba(253,108,152,.14)) !important;
    border-color:rgba(46,203,242,.82) !important;
    box-shadow:
        0 0 15px rgba(46,203,242,.48),
        0 0 24px rgba(253,108,152,.16),
        inset 0 1px 0 rgba(255,255,255,.22) !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details:has(.filter-anchor-tech) summary [data-testid="stIconMaterial"]{{
    background-image:
        url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23FFFFFF' stroke-width='2.25' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='12' cy='7.5' r='3.2'/%3E%3Cpath d='M5.5 20c.8-4.4 3.2-6.5 6.5-6.5s5.7 2.1 6.5 6.5'/%3E%3C/svg%3E"),
        radial-gradient(circle at 50% 30%,rgba(253,108,152,.34),transparent 42%),
        linear-gradient(145deg,rgba(253,108,152,.25),rgba(46,203,242,.12)) !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details:has(.filter-anchor-period) summary [data-testid="stIconMaterial"]{{
    background-image:
        url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23FFFFFF' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M7 4v3M17 4v3M4.5 9h15'/%3E%3Crect x='4' y='6' width='16' height='14' rx='2.5'/%3E%3Cpath d='M8 13h3M13 13h3'/%3E%3C/svg%3E"),
        radial-gradient(circle at 50% 30%,rgba(71,225,144,.30),transparent 42%),
        linear-gradient(145deg,rgba(71,225,144,.20),rgba(46,203,242,.16)) !important;
    border-color:rgba(71,225,144,.70) !important;
    box-shadow:
        0 0 15px rgba(71,225,144,.34),
        0 0 24px rgba(46,203,242,.18),
        inset 0 1px 0 rgba(255,255,255,.22) !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary::before{{
    content:none !important;
    display:none !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary::after{{
    content:"";
    width:18px;
    height:2px;
    justify-self:end;
    border-radius:999px;
    background:linear-gradient(90deg,{CELESTE},{ROSADO});
    box-shadow:0 0 9px rgba(46,203,242,.58);
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary p{{
    min-width:0 !important;
    max-width:100% !important;
    margin:0 !important;
    display:flex !important;
    flex-direction:column !important;
    gap:3px !important;
    color:#FFFFFF !important;
    font-size:15px !important;
    font-weight:950 !important;
    line-height:1.08 !important;
    letter-spacing:0 !important;
    white-space:normal !important;
    overflow:visible !important;
    text-overflow:clip !important;
    word-break:keep-all !important;
    overflow-wrap:normal !important;
    text-shadow:0 0 10px rgba(46,203,242,.18);
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary p::before{{
    content:"Filtro";
    color:{ROSADO};
    font-size:9.5px;
    font-weight:900;
    text-transform:uppercase;
    letter-spacing:.12em;
    line-height:1;
    text-shadow:0 0 10px rgba(253,108,152,.42);
}}

section[data-testid="stSidebar"] div[data-testid="stExpanderContent"]{{
    margin:0 !important;
    padding:12px !important;
    border-top:1px solid rgba(253,108,152,.24) !important;
    background:linear-gradient(180deg,rgba(5,12,24,.86),rgba(3,8,16,.94)) !important;
}}

section[data-testid="stSidebar"][aria-expanded="false"] div[data-testid="stExpander"]{{
    display:none !important;
}}

.estado-final-heading{{
    margin:12px 0 10px 0 !important;
    padding:10px 14px 8px 14px !important;
    border-radius:14px !important;
    background:
        radial-gradient(circle at 8% 45%,rgba(46,203,242,.18),transparent 28%),
        linear-gradient(90deg,rgba(46,203,242,.14),rgba(253,108,152,.05),transparent 76%) !important;
    box-shadow:inset 0 1px 0 rgba(255,255,255,.08) !important;
}}

.estado-final-heading .kpi-title{{
    margin:0 0 8px 0 !important;
    font-size:clamp(19px,1.4vw,23px) !important;
    color:#F8FAFC !important;
    font-weight:950 !important;
    letter-spacing:0 !important;
    text-shadow:
        0 0 12px rgba(46,203,242,.72),
        0 0 22px rgba(0,92,255,.32),
        0 8px 18px rgba(0,0,0,.46) !important;
}}

.estado-final-heading .kpi-divider{{
    margin:0 0 10px 0 !important;
    height:4px !important;
    border-radius:999px !important;
    box-shadow:0 0 18px rgba(46,203,242,.62) !important;
}}

div[data-testid="element-container"]:has(.estado-final-heading),
div[data-testid="stElementContainer"]:has(.estado-final-heading){{
    margin-top:0 !important;
    margin-bottom:0 !important;
}}

div[data-testid="stPlotlyChart"]{{
    margin-bottom:6px !important;
}}

.estado-info-note{{
    margin:14px 0 4px 0 !important;
    padding:13px 16px !important;
    border:1px solid rgba(253,108,152,.58) !important;
    border-radius:14px !important;
    background:
        radial-gradient(circle at 10% 50%,rgba(253,108,152,.22),transparent 26%),
        linear-gradient(135deg,rgba(10,22,39,.96),rgba(17,16,35,.92) 62%,rgba(5,10,20,.96)) !important;
    color:#F8FAFC !important;
    font-size:13px !important;
    font-weight:900 !important;
    letter-spacing:0 !important;
    box-shadow:
        0 16px 32px rgba(0,0,0,.28),
        0 0 22px rgba(253,108,152,.18),
        inset 0 1px 0 rgba(255,255,255,.12) !important;
}}

.estado-info-note .info-icon{{
    background:
        radial-gradient(circle at 50% 28%,rgba(255,255,255,.28),transparent 36%),
        linear-gradient(135deg,{ROSADO},#FF3D73) !important;
    color:#FFFFFF !important;
    box-shadow:
        0 0 14px rgba(253,108,152,.52),
        inset 0 1px 0 rgba(255,255,255,.24) !important;
}}

/* Pulido final sidebar: queda solo la linea viva que separa el panel. */
section[data-testid="stSidebar"]{{
    border-right:0 !important;
    box-shadow:none !important;
}}

section[data-testid="stSidebar"]::before{{
    content:none !important;
    display:none !important;
}}

section[data-testid="stSidebar"]::after{{
    top:10px !important;
    right:-3px !important;
    bottom:10px !important;
    width:4px !important;
    height:auto !important;
    border-radius:999px !important;
    background:linear-gradient(180deg,{AZUL_CLARO},{CELESTE},{NARANJO},{ROSADO},{CELESTE}) !important;
    box-shadow:
        0 0 18px rgba(46,203,242,.78),
        0 0 30px rgba(0,92,255,.36),
        0 0 22px rgba(253,108,152,.26) !important;
}}

@media (prefers-reduced-motion:reduce){{
    .stApp,
    div[data-testid="stAppViewContainer"] > .main .block-container::before,
    section[data-testid="stSidebar"]::before,
    section[data-testid="stSidebar"]::after,
    div[data-testid="stPlotlyChart"],
    div[data-testid="stPlotlyChart"]::before,
    div[data-testid="stPlotlyChart"]::after,
    .filter-section-label::after,
    div[role="radiogroup"][aria-label="Selector KPI"] label:has(input:checked)::after,
    .linea-titulo,
    .kpi-divider{{
        animation:none !important;
    }}
}}


/*======================================================
FILTROS COMO BOTONES PREMIUM - AJUSTE FINAL EXPORTAR DATOS
======================================================*/

/* Alineación real con el botón Exportar datos:
   se corrige el empuje hacia la derecha y se baja el grosor visual. */
section[data-testid="stSidebar"] div[data-testid="stExpander"]{{
    width:230px !important;
    max-width:230px !important;
    margin:0 0 22px -10px !important;
    padding:0 !important;
    overflow:visible !important;
    border:0 !important;
    background:transparent !important;
    box-shadow:none !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details{{
    width:230px !important;
    min-height:64px !important;
    border-radius:14px !important;
    border:1px solid rgba(253,108,152,.66) !important;
    background:
        radial-gradient(circle at 82% 18%,rgba(253,108,152,.46),transparent 36%),
        radial-gradient(circle at 16% 86%,rgba(46,203,242,.16),transparent 34%),
        linear-gradient(145deg,rgba(253,108,152,.22),rgba(18,8,32,.96) 62%,rgba(5,10,20,.98)) !important;
    box-shadow:
        0 0 18px rgba(253,108,152,.22),
        0 16px 30px rgba(0,0,0,.30),
        inset 0 1px 0 rgba(255,255,255,.10) !important;
    overflow:hidden !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details[open]{{
    border-color:rgba(253,108,152,.90) !important;
    filter:brightness(1.04);
    box-shadow:
        0 0 22px rgba(253,108,152,.34),
        0 0 28px rgba(46,203,242,.12),
        0 18px 32px rgba(0,0,0,.32),
        inset 0 1px 0 rgba(255,255,255,.14) !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details::before{{
    content:none !important;
    display:none !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary,
section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary:hover,
section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary:focus,
section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary:active{{
    display:grid !important;
    grid-template-columns:minmax(0,1fr) 18px !important;
    align-items:center !important;
    gap:8px !important;
    min-height:64px !important;
    padding:14px 15px !important;
    background:transparent !important;
    border:0 !important;
    cursor:pointer !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary > span{{
    display:grid !important;
    grid-template-columns:36px minmax(0,1fr) !important;
    align-items:center !important;
    gap:26px !important;
    width:100% !important;
}}

/* Icono idéntico al estilo Exportar datos: tamaño 36 y color rosado */
section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary [data-testid="stIconMaterial"]{{
    width:36px !important;
    height:36px !important;
    min-width:36px !important;
    border-radius:12px !important;
    display:flex !important;
    align-items:center !important;
    justify-content:center !important;
    color:{ROSADO} !important;
    border:1px solid rgba(253,108,152,.46) !important;
    background:
        radial-gradient(circle at 50% 30%,rgba(253,108,152,.22),transparent 42%),
        linear-gradient(145deg,rgba(253,108,152,.16),rgba(255,255,255,.035)) !important;
    box-shadow:
        0 0 13px rgba(253,108,152,.32),
        inset 0 1px 0 rgba(255,255,255,.16) !important;
}}

/* Anula colores anteriores por región/técnico/periodo y deja todos rosados */
section[data-testid="stSidebar"] div[data-testid="stExpander"] details:has(.filter-anchor-region) summary [data-testid="stIconMaterial"]{{
    background-image:
        url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23FD6C98' stroke-width='2.35' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 21s6-5.2 6-11a6 6 0 0 0-12 0c0 5.8 6 11 6 11Z'/%3E%3Ccircle cx='12' cy='10' r='2.4'/%3E%3C/svg%3E"),
        radial-gradient(circle at 50% 30%,rgba(253,108,152,.22),transparent 42%),
        linear-gradient(145deg,rgba(253,108,152,.16),rgba(255,255,255,.035)) !important;
    background-repeat:no-repeat,no-repeat,no-repeat !important;
    background-position:center,center,center !important;
    background-size:23px 23px,cover,cover !important;
    border-color:rgba(253,108,152,.46) !important;
    box-shadow:0 0 13px rgba(253,108,152,.32), inset 0 1px 0 rgba(255,255,255,.16) !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details:has(.filter-anchor-tech) summary [data-testid="stIconMaterial"]{{
    background-image:
        url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23FD6C98' stroke-width='2.35' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='12' cy='7.5' r='3.2'/%3E%3Cpath d='M5.5 20c.8-4.4 3.2-6.5 6.5-6.5s5.7 2.1 6.5 6.5'/%3E%3C/svg%3E"),
        radial-gradient(circle at 50% 30%,rgba(253,108,152,.22),transparent 42%),
        linear-gradient(145deg,rgba(253,108,152,.16),rgba(255,255,255,.035)) !important;
    background-repeat:no-repeat,no-repeat,no-repeat !important;
    background-position:center,center,center !important;
    background-size:23px 23px,cover,cover !important;
    border-color:rgba(253,108,152,.46) !important;
    box-shadow:0 0 13px rgba(253,108,152,.32), inset 0 1px 0 rgba(255,255,255,.16) !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details:has(.filter-anchor-period) summary [data-testid="stIconMaterial"]{{
    background-image:
        url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23FD6C98' stroke-width='2.3' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M7 4v3M17 4v3M4.5 9h15'/%3E%3Crect x='4' y='6' width='16' height='14' rx='2.5'/%3E%3Cpath d='M8 13h3M13 13h3'/%3E%3C/svg%3E"),
        radial-gradient(circle at 50% 30%,rgba(253,108,152,.22),transparent 42%),
        linear-gradient(145deg,rgba(253,108,152,.16),rgba(255,255,255,.035)) !important;
    background-repeat:no-repeat,no-repeat,no-repeat !important;
    background-position:center,center,center !important;
    background-size:23px 23px,cover,cover !important;
    border-color:rgba(253,108,152,.46) !important;
    box-shadow:0 0 13px rgba(253,108,152,.32), inset 0 1px 0 rgba(255,255,255,.16) !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details:has(.filter-anchor-client) summary [data-testid="stIconMaterial"]{{
    background-image:
        url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23FD6C98' stroke-width='2.25' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='9' cy='8' r='3'/%3E%3Cpath d='M3.8 19c.7-4 2.6-6 5.2-6s4.5 2 5.2 6'/%3E%3Ccircle cx='17' cy='9.5' r='2.4'/%3E%3Cpath d='M14.2 14.2c2.7.2 4.6 1.8 5.8 4.8'/%3E%3C/svg%3E"),
        radial-gradient(circle at 50% 30%,rgba(253,108,152,.22),transparent 42%),
        linear-gradient(145deg,rgba(253,108,152,.16),rgba(255,255,255,.035)) !important;
    background-repeat:no-repeat,no-repeat,no-repeat !important;
    background-position:center,center,center !important;
    background-size:23px 23px,cover,cover !important;
    border-color:rgba(253,108,152,.46) !important;
    box-shadow:0 0 13px rgba(253,108,152,.32), inset 0 1px 0 rgba(255,255,255,.16) !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details:has(.filter-anchor-coord) summary [data-testid="stIconMaterial"],
section[data-testid="stSidebar"] div[data-testid="stExpander"] details:has(.filter-anchor-coordinator) summary [data-testid="stIconMaterial"]{{
    background-image:
        url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23FD6C98' stroke-width='2.25' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='9' cy='8' r='3'/%3E%3Cpath d='M3.8 19c.7-4 2.6-6 5.2-6s4.5 2 5.2 6'/%3E%3Cpath d='m15 12 2 2 4-5'/%3E%3C/svg%3E"),
        radial-gradient(circle at 50% 30%,rgba(253,108,152,.22),transparent 42%),
        linear-gradient(145deg,rgba(253,108,152,.16),rgba(255,255,255,.035)) !important;
    background-repeat:no-repeat,no-repeat,no-repeat !important;
    background-position:center,center,center !important;
    background-size:23px 23px,cover,cover !important;
    border-color:rgba(253,108,152,.46) !important;
    box-shadow:0 0 13px rgba(253,108,152,.32), inset 0 1px 0 rgba(255,255,255,.16) !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary p{{
    margin:0 0 0 10px !important;
    display:flex !important;
    flex-direction:column !important;
    color:#FFFFFF !important;
    font-size:14px !important;
    font-weight:950 !important;
    line-height:1.04 !important;
    letter-spacing:-.02em !important;
    text-transform:uppercase !important;
    text-shadow:none !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary p::before{{
    content:"FILTRO" !important;
    color:{ROSADO} !important;
    font-size:9px !important;
    font-weight:950 !important;
    letter-spacing:.15em !important;
    line-height:1 !important;
    margin-bottom:3px !important;
    text-transform:uppercase !important;
    text-shadow:0 0 8px rgba(253,108,152,.36) !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary::before{{
    content:none !important;
    display:none !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary::after{{
    content:"" !important;
    width:18px !important;
    height:2px !important;
    justify-self:end !important;
    border-radius:999px !important;
    background:linear-gradient(90deg,{CELESTE},{ROSADO}) !important;
    box-shadow:0 0 9px rgba(46,203,242,.60) !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpanderContent"]{{
    border-top:1px solid rgba(253,108,152,.22) !important;
    background:linear-gradient(180deg,rgba(5,12,24,.86),rgba(3,8,16,.96)) !important;
    padding:12px !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpanderContent"] div[data-testid="stButton"] button{{
    min-height:32px !important;
    border-radius:10px !important;
    background:
        linear-gradient(135deg,rgba(253,108,152,.20),rgba(10,7,20,.88)) !important;
    border:1px solid rgba(253,108,152,.52) !important;
    color:#FFFFFF !important;
    font-size:10.5px !important;
    font-weight:950 !important;
    letter-spacing:.04em !important;
    text-transform:uppercase !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpanderContent"] div[data-testid="stButton"] button:hover{{
    background:
        linear-gradient(135deg,rgba(253,108,152,.28),rgba(16,6,159,.46)) !important;
    border-color:rgba(253,108,152,.78) !important;
}}

section[data-testid="stSidebar"][aria-expanded="false"] div[data-testid="stExpander"]{{
    display:none !important;
}}

/*======================================================
PULIDO KPI DISPONIBILIDAD: FILTRO ESTADO
======================================================*/

section[data-testid="stSidebar"] div[data-testid="stExpander"] details:has(.filter-anchor-status) summary [data-testid="stIconMaterial"]{{
    background-image:
        url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23FD6C98' stroke-width='2.25' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M5 12.5 9.2 17 19 7'/%3E%3Cpath d='M20 12a8 8 0 1 1-3.4-6.5'/%3E%3C/svg%3E"),
        radial-gradient(circle at 50% 30%,rgba(253,108,152,.22),transparent 42%),
        linear-gradient(145deg,rgba(253,108,152,.16),rgba(255,255,255,.035)) !important;
    background-repeat:no-repeat,no-repeat,no-repeat !important;
    background-position:center,center,center !important;
    background-size:23px 23px,cover,cover !important;
    border-color:rgba(253,108,152,.46) !important;
    box-shadow:0 0 13px rgba(253,108,152,.32), inset 0 1px 0 rgba(255,255,255,.16) !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details:has(.filter-anchor-status) div[data-testid="stExpanderContent"]{{
    padding:10px 12px 12px 12px !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details:has(.filter-anchor-status) .filter-mini-note{{
    margin:5px 0 8px 0 !important;
    color:#BDEFFF !important;
    font-size:10px !important;
    line-height:1.15 !important;
    letter-spacing:.02em !important;
    opacity:.82 !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details:has(.filter-anchor-status) div[data-testid="stCheckbox"]{{
    margin:5px 0 !important;
    padding:0 !important;
    background:transparent !important;
    border:0 !important;
    box-shadow:none !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details:has(.filter-anchor-status) div[data-testid="stCheckbox"] label{{
    min-height:34px !important;
    height:34px !important;
    padding:0 10px !important;
    gap:8px !important;
    border-radius:9px !important;
    border:1px solid rgba(46,203,242,.36) !important;
    background:linear-gradient(135deg,rgba(7,18,34,.92),rgba(4,10,20,.98)) !important;
    box-shadow:
        inset 0 1px 0 rgba(255,255,255,.06),
        0 8px 16px rgba(0,0,0,.20) !important;
}}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details:has(.filter-anchor-status) div[data-testid="stCheckbox"] label p{{
    font-size:10.5px !important;
    font-weight:950 !important;
    letter-spacing:0 !important;
    line-height:1 !important;
    white-space:nowrap !important;
}}

section[data-testid="stSidebar"] div[data-testid="stCheckbox"] label:has(input[aria-label="Cumple"])::before{{
    background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%2347E190' stroke-width='2.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M5 12.5 9.4 17 19 7'/%3E%3C/svg%3E") !important;
}}

section[data-testid="stSidebar"] div[data-testid="stCheckbox"] label:has(input[aria-label="No cumple"])::before{{
    background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23FD6C98' stroke-width='2.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M7 7l10 10M17 7 7 17'/%3E%3C/svg%3E") !important;
}}

section[data-testid="stSidebar"] div[data-testid="stCheckbox"] label:has(input[aria-label="Reclamo"])::before{{
    background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23FF3D00' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 3 22 20H2L12 3Z'/%3E%3Cpath d='M12 9v5M12 17h.01'/%3E%3C/svg%3E") !important;
}}

section[data-testid="stSidebar"] div[data-testid="stCheckbox"] label:has(input[aria-label="Cumple"])::before,
section[data-testid="stSidebar"] div[data-testid="stCheckbox"] label:has(input[aria-label="No cumple"])::before,
section[data-testid="stSidebar"] div[data-testid="stCheckbox"] label:has(input[aria-label="Reclamo"])::before{{
    flex:0 0 20px !important;
    width:20px !important;
    height:20px !important;
    border-radius:7px !important;
    background-size:13px 13px !important;
}}

section[data-testid="stSidebar"] div[data-testid="stCheckbox"]:has(input[aria-label="Cumple"][aria-checked="true"]) label{{
    border-color:rgba(71,225,144,.74) !important;
    background:linear-gradient(135deg,rgba(71,225,144,.20),rgba(6,18,34,.96)) !important;
    box-shadow:inset 3px 0 0 {VERDE}, 0 0 16px rgba(71,225,144,.18), 0 8px 16px rgba(0,0,0,.20) !important;
}}

section[data-testid="stSidebar"] div[data-testid="stCheckbox"]:has(input[aria-label="No cumple"][aria-checked="true"]) label{{
    border-color:rgba(253,108,152,.74) !important;
    background:linear-gradient(135deg,rgba(253,108,152,.20),rgba(6,18,34,.96)) !important;
    box-shadow:inset 3px 0 0 {ROSADO}, 0 0 16px rgba(253,108,152,.18), 0 8px 16px rgba(0,0,0,.20) !important;
}}

section[data-testid="stSidebar"] div[data-testid="stCheckbox"]:has(input[aria-label="Reclamo"][aria-checked="true"]) label{{
    border-color:rgba(255,61,0,.74) !important;
    background:linear-gradient(135deg,rgba(255,61,0,.18),rgba(6,18,34,.96)) !important;
    box-shadow:inset 3px 0 0 {NARANJO}, 0 0 16px rgba(255,61,0,.18), 0 8px 16px rgba(0,0,0,.20) !important;
}}

section[data-testid="stSidebar"] div[data-testid="stCheckbox"]:has(input[aria-checked="false"]) label{{
    opacity:.42 !important;
    filter:saturate(.45) brightness(.82) !important;
    border-color:rgba(100,116,139,.28) !important;
    background:linear-gradient(135deg,rgba(5,12,24,.62),rgba(2,6,12,.90)) !important;
    box-shadow:inset 0 1px 0 rgba(255,255,255,.03) !important;
}}

section[data-testid="stSidebar"] div[data-testid="stCheckbox"]:has(input[aria-checked="false"]) label p,
section[data-testid="stSidebar"] div[data-testid="stCheckbox"]:has(input[aria-checked="false"]) label span{{
    color:#7F90A8 !important;
    text-shadow:none !important;
}}

section[data-testid="stSidebar"] div[data-testid="stCheckbox"]:has(input[aria-checked="false"]) label::before{{
    opacity:.52 !important;
    border-color:rgba(100,116,139,.36) !important;
    background-color:rgba(3,8,16,.76) !important;
    box-shadow:none !important;
}}

section[data-testid="stSidebar"] div[data-testid="stCheckbox"]:has(input[aria-checked="true"]) label{{
    opacity:1 !important;
    filter:none !important;
}}

section[data-testid="stSidebar"] div[data-testid="stCheckbox"]:has(input[aria-checked="true"]) label p,
section[data-testid="stSidebar"] div[data-testid="stCheckbox"]:has(input[aria-checked="true"]) label span{{
    color:#FFFFFF !important;
    text-shadow:0 0 9px rgba(46,203,242,.28) !important;
}}

section[data-testid="stSidebar"] div[data-testid="stPills"]{{
    width:100% !important;
}}

section[data-testid="stSidebar"] div[data-testid="stPills"] div[role="group"]{{
    display:flex !important;
    flex-wrap:wrap !important;
    gap:8px !important;
}}

section[data-testid="stSidebar"] button[data-testid="stBaseButton-pillsActive"]{{
    min-height:34px !important;
    border-radius:9px !important;
    border:1px solid rgba(46,203,242,.72) !important;
    background:
        linear-gradient(135deg,rgba(46,203,242,.24),rgba(71,225,144,.18)),
        linear-gradient(180deg,rgba(12,31,49,.98),rgba(5,13,25,.96)) !important;
    color:#FFFFFF !important;
    font-weight:900 !important;
    letter-spacing:0 !important;
    box-shadow:
        inset 3px 0 0 {CELESTE},
        inset 0 1px 0 rgba(255,255,255,.12),
        0 0 14px rgba(46,203,242,.28),
        0 8px 18px rgba(2,6,23,.22) !important;
    text-shadow:0 0 9px rgba(46,203,242,.32) !important;
}}

section[data-testid="stSidebar"] button[data-testid="stBaseButton-pills"]{{
    min-height:34px !important;
    border-radius:9px !important;
    border:1px solid rgba(100,116,139,.34) !important;
    background:linear-gradient(135deg,rgba(5,12,24,.66),rgba(2,6,12,.90)) !important;
    color:#7F90A8 !important;
    font-weight:800 !important;
    opacity:.62 !important;
    box-shadow:inset 0 1px 0 rgba(255,255,255,.03) !important;
}}

section[data-testid="stSidebar"] button[data-testid="stBaseButton-pills"]:hover{{
    opacity:.9 !important;
    border-color:rgba(46,203,242,.54) !important;
    color:#D7F7FF !important;
}}

/* Overrides de rendimiento: sidebar y navegacion quietos; el vidrio dinamico queda solo en graficos. */

html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"]{{
    scroll-behavior:auto !important;
}}

[data-baseweb="tab-highlight"],
[data-baseweb="radio"] *,
[data-testid="stRadio"] *,
[data-testid="stSelectbox"] *,
.stApp,
div[data-testid="stAppViewContainer"] > .main .block-container::before,
.linea-titulo,
.kpi-divider,
section[data-testid="stSidebar"] *,
section[data-testid="stSidebar"],
section[data-testid="stSidebar"]::before,
section[data-testid="stSidebar"]::after,
.filter-section-label,
.filter-section-label::after,
div[role="radiogroup"][aria-label="Selector KPI"] label:has(input:checked)::after,
.control-glass,
.control-glass::before,
.control-glass::after,
.metric-card,
.metric-card::before,
.metric-card::after,
.ai-insight-card,
.ai-insight-card::before,
.ai-insight-card::after,
.sidebar-export-card,
.sidebar-export-card::before,
.sidebar-export-card::after{{
    animation:none !important;
    transition:none !important;
}}

.control-glass,
.control-glass::before,
.control-glass::after,
.metric-card,
.ai-insight-card,
.sidebar-export-card,
[data-testid="stSidebar"] [data-baseweb="select"] > div{{
    backdrop-filter:none !important;
    -webkit-backdrop-filter:none !important;
}}

@keyframes chartGlassSweepStaticPage{{
    0%{{ transform:translateX(-115%) skewX(-13deg); opacity:.04; }}
    42%{{ opacity:.16; }}
    100%{{ transform:translateX(115%) skewX(-13deg); opacity:.04; }}
}}

div[data-testid="stPlotlyChart"]{{
    position:relative !important;
    overflow:hidden !important;
    border-radius:16px !important;
}}

div[data-testid="stPlotlyChart"]::before{{
    content:"" !important;
    position:absolute !important;
    inset:0 !important;
    pointer-events:none !important;
    z-index:8 !important;
    background:
        linear-gradient(105deg,transparent 0 32%,rgba(255,255,255,.10) 44%,rgba(46,203,242,.10) 50%,transparent 64%),
        radial-gradient(circle at 72% 18%,rgba(253,108,152,.08),transparent 28%) !important;
    mix-blend-mode:screen !important;
    animation:chartGlassSweepStaticPage 12s linear infinite !important;
}}

@media (prefers-reduced-motion:reduce){{
    div[data-testid="stPlotlyChart"]::before{{
        animation:none !important;
        opacity:.08 !important;
    }}
}}

section[data-testid="stSidebar"] div[data-testid="stSelectbox"]{{
    margin:12px 0 26px 0 !important;
}}

section[data-testid="stSidebar"] div[data-testid="stSelectbox"] > label{{
    margin:0 0 8px 0 !important;
}}

section[data-testid="stSidebar"] div[data-baseweb="select"] > div{{
    min-height:64px !important;
    border-radius:9px !important;
    border:1px solid rgba(253,108,152,.58) !important;
    background:
        url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23FD6C98' stroke-width='2.25' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='12' cy='7.5' r='3.2'/%3E%3Cpath d='M5.5 20c.8-4.4 3.2-6.5 6.5-6.5s5.7 2.1 6.5 6.5'/%3E%3C/svg%3E"),
        radial-gradient(circle at 82% 34%,rgba(253,108,152,.32),transparent 30%),
        linear-gradient(135deg,rgba(253,108,152,.20),rgba(46,203,242,.08)),
        linear-gradient(180deg,rgba(11,17,32,.96),rgba(7,9,21,.98)) !important;
    background-repeat:no-repeat,no-repeat,no-repeat,no-repeat !important;
    background-position:17px center,center,center,center !important;
    background-size:24px 24px,cover,cover,cover !important;
    padding-left:54px !important;
    box-shadow:
        inset 3px 0 0 {ROSADO},
        inset 0 1px 0 rgba(255,255,255,.12),
        0 12px 28px rgba(2,6,23,.38),
        0 0 16px rgba(253,108,152,.24) !important;
}}

section[data-testid="stSidebar"] div[data-baseweb="select"] span,
section[data-testid="stSidebar"] div[data-baseweb="select"] input{{
    color:#FFFFFF !important;
    font-weight:900 !important;
    letter-spacing:0 !important;
}}

section[data-testid="stSidebar"] div[data-baseweb="select"] svg{{
    fill:{CELESTE} !important;
}}

section[data-testid="stSidebar"] label p{{
    color:#BDEFFF !important;
    font-weight:900 !important;
    letter-spacing:.02em !important;
    text-transform:uppercase !important;
}}

section[data-testid="stSidebar"] .sidebar-export-card,
section[data-testid="stSidebar"]:has(.filter-anchor-client) .sidebar-export-card,
section[data-testid="stSidebar"]:has(details[open]) .sidebar-export-card,
section[data-testid="stSidebar"]:has(.filter-anchor-client):has(details[open]) .sidebar-export-card,
section[data-testid="stSidebar"] div[data-testid="stDownloadButton"],
section[data-testid="stSidebar"]:has(.filter-anchor-client) div[data-testid="stDownloadButton"],
section[data-testid="stSidebar"]:has(details[open]) div[data-testid="stDownloadButton"],
section[data-testid="stSidebar"]:has(.filter-anchor-client):has(details[open]) div[data-testid="stDownloadButton"]{{
    position:relative !important;
    left:auto !important;
    bottom:auto !important;
    width:230px !important;
    margin:18px 0 34px 0 !important;
    z-index:5 !important;
}}

</style>
""", unsafe_allow_html=True)

# =========================================================
# ORDEN MESES
# =========================================================

MESES = [
    "Enero","Febrero","Marzo","Abril","Mayo","Junio",
    "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"
]

MESES_CORTOS = {
    "Enero": "Ene",
    "Febrero": "Feb",
    "Marzo": "Mar",
    "Abril": "Abr",
    "Mayo": "May",
    "Junio": "Jun",
    "Julio": "Jul",
    "Agosto": "Ago",
    "Septiembre": "Sep",
    "Octubre": "Oct",
    "Noviembre": "Nov",
    "Diciembre": "Dic",
}


def normalizar_texto_mes(valor):
    """Normaliza textos de mes para que Ene, Enero, 01, 2026-01, etc. filtren igual."""
    if pd.isna(valor):
        return ""
    texto = unicodedata.normalize("NFKD", str(valor).strip())
    texto = texto.encode("ascii", "ignore").decode("ascii").lower()
    texto = "".join(caracter if caracter.isalnum() else " " for caracter in texto)
    return " ".join(texto.split())


MESES_NORMALIZADOS = {normalizar_texto_mes(mes): mes for mes in MESES}
MESES_NORMALIZADOS.update({normalizar_texto_mes(corto): mes for mes, corto in MESES_CORTOS.items()})
for indice_mes, nombre_mes in enumerate(MESES, start=1):
    MESES_NORMALIZADOS[str(indice_mes)] = nombre_mes
    MESES_NORMALIZADOS[f"{indice_mes:02d}"] = nombre_mes


def normalizar_mes_operacional(valor):
    texto = normalizar_texto_mes(valor)
    if not texto or texto in {"nan", "nat", "none", "null"}:
        return pd.NA

    if texto in MESES_NORMALIZADOS:
        return MESES_NORMALIZADOS[texto]

    for token in texto.split():
        if token in MESES_NORMALIZADOS:
            return MESES_NORMALIZADOS[token]
        try:
            numero = int(token)
        except ValueError:
            continue
        if 1 <= numero <= 12:
            return MESES[numero - 1]

    return pd.NA


def serie_mes_operacional(df_base, fecha_col, mes_col="mes"):
    """Devuelve el mes operacional priorizando la fecha real y usando la columna mes como respaldo."""
    if df_base is None or df_base.empty:
        return pd.Series(dtype="object")

    if fecha_col in df_base.columns:
        fecha = pd.to_datetime(df_base[fecha_col], errors="coerce")
        mes_fecha = fecha.dt.month.map(
            lambda mes: MESES[int(mes) - 1] if pd.notna(mes) and 1 <= int(mes) <= 12 else pd.NA
        )
    else:
        mes_fecha = pd.Series(pd.NA, index=df_base.index, dtype="object")

    if mes_col in df_base.columns:
        mes_respaldo = df_base[mes_col].map(normalizar_mes_operacional)
        return mes_fecha.fillna(mes_respaldo)

    return mes_fecha


def ordenar_meses_operacionales(meses):
    meses_set = set(str(mes) for mes in meses if pd.notna(mes))
    return [mes for mes in MESES if mes in meses_set]


def resumen_meses_disponibilidad_para_filtro(df_base):
    columnas = ["mes", "solicitudes", "cumple", "no_cumple", "cumplimiento_pct", "bajo_meta"]
    if df_base.empty or "cumple_kpi" not in df_base.columns:
        return pd.DataFrame(columns=columnas)

    base = df_base.copy()
    base["_mes_operacional"] = serie_mes_operacional(base, "fecha_solicitud", "mes")
    base = base.dropna(subset=["_mes_operacional"])
    if base.empty:
        return pd.DataFrame(columns=columnas)

    base["_cumple"] = base["cumple_kpi"].fillna(False).astype(bool)
    resumen = (
        base.groupby("_mes_operacional", dropna=False)
        .agg(solicitudes=("_cumple", "size"), cumple=("_cumple", "sum"))
        .reset_index()
        .rename(columns={"_mes_operacional": "mes"})
    )
    resumen["no_cumple"] = resumen["solicitudes"] - resumen["cumple"]
    resumen["cumplimiento_pct"] = (resumen["cumple"] / resumen["solicitudes"].clip(lower=1) * 100).round(1)
    resumen["bajo_meta"] = resumen["cumplimiento_pct"].lt(DISPONIBILIDAD_META_PCT)
    resumen["_orden"] = resumen["mes"].map({mes: i for i, mes in enumerate(MESES)})
    return resumen.sort_values("_orden").drop(columns="_orden")


def resumen_meses_reclamos_para_filtro(df_base):
    columnas = ["mes", "reclamos"]
    if df_base.empty:
        return pd.DataFrame(columns=columnas)

    base = df_base.copy()
    base["_mes_operacional"] = serie_mes_operacional(base, "fecha_reclamo", "mes")
    base = base.dropna(subset=["_mes_operacional"])
    if base.empty:
        return pd.DataFrame(columns=columnas)

    resumen = (
        base.groupby("_mes_operacional", dropna=False)
        .size()
        .reset_index(name="reclamos")
        .rename(columns={"_mes_operacional": "mes"})
    )
    resumen["_orden"] = resumen["mes"].map({mes: i for i, mes in enumerate(MESES)})
    return resumen.sort_values("_orden").drop(columns="_orden")


# =========================================================
# CARGA
# =========================================================

@st.cache_data
def cargar(ruta_archivo, version_archivo):
    ruta = Path(ruta_archivo)
    if not ruta.exists():
        return pd.DataFrame()

    df = pd.read_excel(ruta)

    if "Mes" in df.columns:
        df["Mes"] = pd.Categorical(
            df["Mes"],
            categories=MESES,
            ordered=True
        )

    return df


def version_archivo(ruta_archivo):
    ruta = Path(ruta_archivo)
    info = ruta.stat()
    return f"{info.st_size}-{info.st_mtime_ns}"


def version_archivo_opcional(ruta_archivo):
    ruta = Path(ruta_archivo)
    if not ruta.exists():
        return "missing"
    return version_archivo(ruta)


def ruta_epa_activa(servicio=None):
    servicio_ref = servicio or SERVICIO_CONFIG
    if isinstance(servicio_ref, str):
        config = SERVICIOS_CONFIG[servicio_ref]
    else:
        config = servicio_ref
    epa_dir = APP_DIR / str(config["epa_dir"])
    epa_db = epa_dir / str(config["epa_db"])
    epa_db_legacy = epa_dir / str(config["epa_db_legacy"])
    if epa_db.exists():
        return epa_db
    if epa_db_legacy.exists():
        return epa_db_legacy
    return epa_db


DISPONIBILIDAD_COLUMNAS = [
    "cliente", "numero_ticket", "ticket_principal", "region", "zona", "ciudad",
    "coordinador", "correo_coordinador", "coordinador_tipo",
    "remitente_cecom", "asunto_solicitud", "fecha_solicitud",
    "fecha_respuesta", "minutos_habiles", "minutos_calendario",
    "cumple_kpi", "estado_kpi", "demora_respuesta", "exceso_sla_habiles",
    "exceso_sla", "tipo_solicitud", "secuencia_solicitud",
    "solicitud_caso_n", "total_solicitudes_caso", "solicitudes_en_ciclo",
    "reiteraciones_previas", "reiteraciones_hasta_respuesta", "reiteraciones_total_operacional",
    "reiteraciones_cecom_operador", "reiteraciones_supervisor_cecom",
    "intervenciones_supervisor_terreno", "interventores_supervisor_terreno",
    "intervenciones_supervisor_servicio_tecnico", "interventores_supervisor_servicio_tecnico",
    "remitentes_reiteracion", "fechas_reiteracion",
    "fecha_primera_reiteracion", "fecha_ultima_reiteracion",
    "grupo_solicitud_id", "mes", "thread_id",
    "mensaje_solicitud_id", "mensaje_respuesta_id", "fuente_pst",
    "actualizado_en", "observacion",
]

RECLAMOS_COLUMNAS = [
    "cliente", "numero_ticket", "ticket_principal", "region", "zona", "ciudad",
    "tipo_registro", "familia_reclamo", "motivo_reclamo", "severidad_reclamo",
    "reforzamiento", "proveedor_reforzado", "motivo_reforzamiento",
    "fecha_reclamo", "remitente", "destinatarios", "asunto",
    "extracto_reclamo", "fecha_programada_reclamo", "hora_programada_reclamo",
    "estado_wfm", "fecha_wfm", "ventana_wfm", "inicio_wfm", "tecnico_wfm",
    "mismo_dia_wfm", "diferencia_hora_wfm_min", "mes", "thread_id",
    "mensaje_id", "fuente_pst", "actualizado_en", "observacion",
]


def serie_texto_limpio(serie):
    return serie.fillna("").astype(str).str.strip()


def serie_bool_panel(serie):
    return (
        serie.fillna(False)
        .astype(str)
        .str.strip()
        .str.lower()
        .isin({"1", "true", "si", "sí", "s\u00ed", "yes", "y", "x", "verdadero"})
    )



def normalizar_texto_operacional(valor):
    """Normaliza texto de correos para detectar reclamos, zonas y exclusiones."""
    if pd.isna(valor):
        return ""
    texto = unicodedata.normalize("NFKD", str(valor))
    texto = texto.encode("ascii", "ignore").decode("ascii").lower()
    return " ".join(texto.split())


RECLAMO_MALA_GESTION_KEYWORDS = [
    "reclamo", "queja", "mala gestion", "mala atencion", "mal gestionado",
    "incumplimiento", "no cumple", "no cumplio", "sin respuesta", "no responde",
    "no han respondido", "no tenemos respuesta", "respuesta pendiente", "demora",
    "demorado", "atraso", "retraso", "no llegada", "no se presenta", "no asistio",
    "sin contacto", "cliente molesto", "molestia", "escalamiento", "urgente apoyo",
    "favor gestionar", "favor regularizar", "mala coordinacion", "problema de gestion",
    "mala higiene", "higiene", "mala presentacion", "mal presentado", "desaseado",
    "sucio", "mal olor", "sin uniforme", "mal trato", "mala actitud", "grosero",
    "cierre falso", "cerrado sin atencion", "cerrado sin atender",
]

RECLAMO_FAMILIAS_PANEL = [
    (
        "No llegada tecnico",
        [
            "tecnico no llego", "tecnico no llega", "tecnico no asiste", "tecnico no asistio",
            "no se presento", "no se presenta", "no llego el tecnico", "no asistio el tecnico",
            "visita fallida", "visita no realizada por tecnico", "no concurrio", "no acudio",
            "nunca llego", "no llego nadie", "sin visita", "tecnico ausente",
        ],
        "Tecnico no llega/no se presenta en visita programada",
    ),
    (
        "Retraso o incumplimiento horario",
        [
            "retraso no informado", "atraso no informado", "llego tarde", "llega tarde",
            "fuera de horario", "sin aviso", "sin avisar", "atraso", "retraso",
            "atrasado", "atrasada", "incumplimiento horario", "incumplio horario",
            "no cumple horario", "no cumple ventana", "fuera de ventana",
        ],
        "Retraso, llegada fuera de horario o incumplimiento de ventana",
    ),
    (
        "Mala higiene o presentacion",
        [
            "mala higiene", "higiene", "falta de higiene", "mala presentacion",
            "presentacion personal", "presentacion del tecnico", "mal presentado",
            "desaseado", "sucio", "mal olor", "olor", "aseo personal",
            "ropa sucia", "uniforme sucio", "sin uniforme", "vestimenta inadecuada",
        ],
        "Tecnico reportado por higiene, presentacion personal o vestimenta",
    ),
    (
        "Mal trato al usuario",
        [
            "mal trato", "mala actitud", "trato inadecuado", "trato grosero",
            "grosero", "prepotente", "falta de respeto", "discusion con usuario",
            "discusion con cliente", "se niega a atender",
        ],
        "Trato inadecuado, falta de respeto o negativa de atencion",
    ),
    (
        "Sin herramientas o insumos",
        [
            "sin herramientas", "no llevo herramientas", "sin herramienta", "sin imagen",
            "no llevo imagen", "sin insumos", "sin insumo", "no llevo repuesto",
            "sin cable", "no cuenta con herramientas", "sin aplicaciones",
        ],
        "Tecnico asiste sin herramientas, imagen, repuestos o insumos",
    ),
    (
        "Sin contacto con usuario",
        [
            "no contacto", "sin contacto", "no llamo", "no llama", "no se contacto",
            "no contacto usuario", "sin coordinacion con usuario", "no coordino con usuario",
        ],
        "Tecnico no contacta o no coordina con usuario",
    ),
    (
        "Mala ejecucion de atencion",
        [
            "mala gestion", "mala atencion", "mal gestionado", "problema de gestion",
            "no termino", "no se termino", "trabajo incompleto", "cierre incorrecto",
            "cerrado incorrectamente", "ot incorrecta", "no resolvio", "dejo sin servicio",
            "incumplimiento", "incumplio", "no cumple", "no cumplio", "no realiza",
            "no realizo", "cierre falso", "cerrado sin atencion", "cerrado sin atender",
            "atencion deficiente", "gestion deficiente", "mala ejecucion",
        ],
        "Atencion incompleta, cierre incorrecto o gestion deficiente",
    ),
]

RECLAMO_EXCLUSION_PATTERNS = [
    r"\bbodega\b", r"\bdevolucion\b", r"\bdevoluciones\b", r"\bretorno\b", r"\bretirar equipo\b",
    r"\bentrega equipo\b", r"\btw\b", r"\bterminal wireless\b", r"\bterminal wifi\b",
    r"\bpago incorrecto\b", r"\bliquidacion\b", r"\bremuneracion\b", r"\bmarcas correspondientes\b",
    r"\bprovision y regularizacion\b", r"\bcanal para solicitudes sap\b", r"\bpedidos sin ticket\b",
    r"\bcuenta del reemplazo\b", r"\brecursos outsourcing\b",
]

REGION_TARAPACA_TERMS = ["tarapaca", "iquique", "alto hospicio", "pozo almonte"]
REGION_ANTOFAGASTA_TERMS = ["antofagasta", "calama", "mejillones", "tocopilla", "taltal", "sierra gorda"]

CLIENTES_ALIASES_PANEL = [
    ("UC CHRISTUS", ["uc christus", "christus", "servicios ambulatorios", "servicio ambulatorio", "red salud uc"]),
    ("BANCO SECURITY", ["banco security", "security"]),
    ("ACHS", ["achs", " ach ", "asoc chilena de seguridad", "asociacion chilena de seguridad", "asociacion chile de seguridad", "asociacion de seguridad"]),
    ("AFC", ["afc", "administradora de fondos de cesantia", "administradora fondos de cesantia", "fondos de cesantia"]),
    ("COPEC", ["copec", "compania de petroleos de chile", "petroleos de chile"]),
    ("CGE", ["cge", "compania general de electricidad", "general de electricidad"]),
    ("IDEMIA", ["idemia", "registro civil"]),
    ("DIBAM", ["dibam", "snpc", "serpac", "servicio nacional de patrimonio", "patrimonio cultural", "biblioteca regional gabriela mistral"]),
    ("BUPA", ["bupa", "bupa chile"]),
    ("ENTEL CHILE", ["entel cio", "entel rhh", "entel rrhh", "entel chile", "entel tiendas", "tiendas entel"]),
]
CLIENTE_NO_IDENTIFICADO = "Sin cliente WFM"
CLIENTE_SIN_DATO_EQUIVALENTES = {"", "sin dato", "cliente no identificado", CLIENTE_NO_IDENTIFICADO.lower()}
TICKET_ID_COLS_PANEL = ["ID Externo", "ID externo", "ID Ticket", "Ticket", "Ticket ID", "Numero Ticket", "Número Ticket"]
CLIENTE_COLS_ATENCION_PANEL = ["Empresa Cliente", "Cliente", "Empresa", "Nombre Cliente"]

SERVICIO_ALIAS_PANEL = {
    "IBM": [
        "ibm", "@ibm.com", "fabian trujillo", "fabian.trujillo", "heraldo", "crisostomo",
        "hcrisostomo", "p.albornoz", "patricio albornoz",
    ],
    "SAO": [
        "sao", "sao computacion", "saocomputacion", "@saocomputacion.cl",
        "d.galarce", "daniel galarce", "pia ossandon", "pia.ossandon",
        "pia.saocomputacion", "angelica fuentes", "angelicafuentes1",
    ],
}


def contiene_exclusion_reclamo(texto):
    limpio = normalizar_texto_operacional(texto)
    return any(re.search(patron, limpio) for patron in RECLAMO_EXCLUSION_PATTERNS)


def contiene_mala_gestion_ibm(texto):
    limpio = normalizar_texto_operacional(texto)
    if not limpio:
        return False
    return any(palabra in limpio for palabra in RECLAMO_MALA_GESTION_KEYWORDS)


def clasificar_reclamo_operacional_panel(texto):
    limpio = normalizar_texto_operacional(texto)
    if not limpio:
        return {"familia": "", "motivo": "", "severidad": ""}
    for familia, terminos, motivo in RECLAMO_FAMILIAS_PANEL:
        if any(normalizar_texto_operacional(termino) in limpio for termino in terminos):
            return {"familia": familia, "motivo": motivo, "severidad": "ALTA"}
    if any(palabra in limpio for palabra in ["reclamo", "queja", "cliente molesto", "escalamiento"]):
        return {
            "familia": "Reclamo explicito cliente",
            "motivo": f"Correo indica reclamo explicito asociado a {SERVICIO_TITULO}",
            "severidad": "ALTA",
        }
    return {"familia": "", "motivo": "", "severidad": ""}


def region_operacional_desde_texto(texto, region_actual=""):
    actual = str(region_actual or "").strip()
    actual_norm = normalizar_texto_operacional(actual)
    if any(term in actual_norm for term in REGION_TARAPACA_TERMS):
        return "Region de Tarapaca"
    if any(term in actual_norm for term in REGION_ANTOFAGASTA_TERMS):
        return "Region de Antofagasta"

    limpio = normalizar_texto_operacional(texto)
    if any(term in limpio for term in REGION_TARAPACA_TERMS):
        return "Region de Tarapaca"
    if any(term in limpio for term in REGION_ANTOFAGASTA_TERMS):
        return "Region de Antofagasta"
    return actual if actual else "Sin zona"


def cliente_desde_texto_panel(texto):
    limpio = normalizar_texto_operacional(texto)
    if not limpio:
        return "Sin dato"
    texto_padded = f" {limpio} "
    for cliente, aliases in CLIENTES_ALIASES_PANEL:
        for alias in aliases:
            alias_n = normalizar_texto_operacional(alias)
            if alias_n.startswith(" ") or alias_n.endswith(" "):
                if alias_n in texto_padded:
                    return cliente
            elif re.search(rf"(?<![a-z0-9]){re.escape(alias_n)}(?![a-z0-9])", limpio):
                return cliente
            elif alias_n in limpio:
                return cliente
    return "Sin dato"


def normalizar_ticket_panel(valor):
    texto = str(valor or "").strip().upper()
    if not texto or texto.lower() == "nan":
        return ""
    texto = re.sub(r"\.0$", "", texto)
    ticket_norm = re.sub(r"[^A-Z0-9]", "", texto)
    if re.fullmatch(r"[A-F0-9]{20,}", ticket_norm):
        return ""
    if len(ticket_norm) > 20 and not ticket_norm.startswith(("INC", "RITM", "WO", "REQ", "CNR")):
        return ""
    return ticket_norm


def cliente_panel_desde_valor(valor):
    texto = str(valor or "").strip()
    if not texto or texto.lower() == "nan":
        return "Sin dato"
    cliente = cliente_desde_texto_panel(texto)
    if cliente != "Sin dato":
        return cliente
    texto = " ".join(texto.upper().split())
    return texto if texto else "Sin dato"


def mapa_clientes_atenciones_panel(df_atenciones):
    mapa = {}
    if df_atenciones is None or df_atenciones.empty:
        return mapa

    ticket_cols = [col for col in TICKET_ID_COLS_PANEL if col in df_atenciones.columns]
    cliente_col = next((col for col in CLIENTE_COLS_ATENCION_PANEL if col in df_atenciones.columns), None)
    if not ticket_cols or cliente_col is None:
        return mapa

    columnas = ticket_cols + [cliente_col]
    if "servicio_tecnico" in df_atenciones.columns:
        columnas.append("servicio_tecnico")

    for _, row in df_atenciones[columnas].fillna("").iterrows():
        cliente = cliente_panel_desde_valor(row.get(cliente_col))
        if cliente == "Sin dato":
            continue
        servicio = str(row.get("servicio_tecnico") or "").strip().upper()
        for ticket_col in ticket_cols:
            ticket_norm = normalizar_ticket_panel(row.get(ticket_col))
            if not ticket_norm:
                continue
            if servicio:
                mapa.setdefault((servicio, ticket_norm), cliente)
            mapa.setdefault(("", ticket_norm), cliente)
    return mapa


def mapa_zonas_atenciones_panel(df_atenciones):
    mapa = {}
    if df_atenciones is None or df_atenciones.empty:
        return mapa

    ticket_cols = [col for col in TICKET_ID_COLS_PANEL if col in df_atenciones.columns]
    if not ticket_cols:
        return mapa

    columnas = ticket_cols[:]
    for col in ["Estado", "Ciudad"]:
        if col in df_atenciones.columns:
            columnas.append(col)
    if "servicio_tecnico" in df_atenciones.columns:
        columnas.append("servicio_tecnico")

    for _, row in df_atenciones[columnas].fillna("").iterrows():
        region = region_operacional_desde_texto(row.get("Ciudad", ""), row.get("Estado", ""))
        ciudad = str(row.get("Ciudad") or "").strip() or "Sin dato"
        if not region or region == "Sin zona":
            continue
        servicio = str(row.get("servicio_tecnico") or "").strip().upper()
        for ticket_col in ticket_cols:
            ticket_norm = normalizar_ticket_panel(row.get(ticket_col))
            if not ticket_norm:
                continue
            if servicio:
                mapa.setdefault((servicio, ticket_norm), (region, ciudad))
            mapa.setdefault(("", ticket_norm), (region, ciudad))
    return mapa


def completar_cliente_desde_atenciones_panel(df_base, df_atenciones):
    if df_base is None or df_base.empty or "cliente" not in df_base.columns:
        return df_base

    mapa = mapa_clientes_atenciones_panel(df_atenciones)
    if not mapa:
        return df_base

    base = df_base.copy()
    ticket_cols = [col for col in ["ticket_principal", "numero_ticket"] if col in base.columns]
    if not ticket_cols:
        return base

    clientes_actuales = base["cliente"].fillna("").astype(str).str.strip()
    mask_sin_cliente = clientes_actuales.str.lower().isin(CLIENTE_SIN_DATO_EQUIVALENTES)
    if not mask_sin_cliente.any():
        return base

    for idx, row in base.loc[mask_sin_cliente].iterrows():
        servicio = str(row.get("servicio_tecnico") or "").strip().upper()
        cliente = ""
        for ticket_col in ticket_cols:
            ticket_norm = normalizar_ticket_panel(row.get(ticket_col))
            if not ticket_norm:
                continue
            cliente = mapa.get((servicio, ticket_norm)) or mapa.get(("", ticket_norm)) or ""
            if cliente:
                break
        if cliente:
            base.at[idx, "cliente"] = cliente

    base["cliente"] = base["cliente"].replace({"": CLIENTE_NO_IDENTIFICADO, "Sin dato": CLIENTE_NO_IDENTIFICADO})
    return base


def completar_zona_desde_atenciones_panel(df_base, df_atenciones):
    if df_base is None or df_base.empty:
        return df_base

    mapa = mapa_zonas_atenciones_panel(df_atenciones)
    if not mapa:
        return df_base

    base = df_base.copy()
    for col in ["region", "zona", "ciudad"]:
        if col not in base.columns:
            base[col] = ""
    ticket_cols = [col for col in ["ticket_principal", "numero_ticket"] if col in base.columns]
    if not ticket_cols:
        return base

    regiones_actuales = base["region"].fillna("").astype(str).str.strip()
    mask_sin_zona = regiones_actuales.str.lower().isin({"", "sin zona", "sin dato", "nan"})
    if not mask_sin_zona.any():
        return base

    for idx, row in base.loc[mask_sin_zona].iterrows():
        servicio = str(row.get("servicio_tecnico") or "").strip().upper()
        zona = None
        for ticket_col in ticket_cols:
            ticket_norm = normalizar_ticket_panel(row.get(ticket_col))
            if not ticket_norm:
                continue
            zona = mapa.get((servicio, ticket_norm)) or mapa.get(("", ticket_norm))
            if zona:
                break
        if zona:
            region, ciudad = zona
            base.at[idx, "region"] = region
            base.at[idx, "zona"] = region
            if not str(row.get("ciudad") or "").strip() or str(row.get("ciudad") or "").strip() == "Sin dato":
                base.at[idx, "ciudad"] = ciudad

    base["region"] = base["region"].replace("", "Sin zona")
    base["zona"] = base["zona"].where(base["zona"].fillna("").astype(str).str.strip().ne(""), base["region"])
    base["ciudad"] = base["ciudad"].replace("", "Sin dato")
    return base


def deduplicar_reclamos_ticket_familia_panel(df_base):
    if df_base is None or df_base.empty:
        return df_base
    columnas_necesarias = {"ticket_principal", "numero_ticket", "familia_reclamo", "fecha_reclamo"}
    if not columnas_necesarias.intersection(df_base.columns):
        return df_base

    base = df_base.copy()
    ticket_serie = (
        base["ticket_principal"].fillna("").astype(str)
        if "ticket_principal" in base.columns else pd.Series("", index=base.index)
    )
    if "numero_ticket" in base.columns:
        ticket_serie = ticket_serie.where(ticket_serie.str.strip().ne(""), base["numero_ticket"].fillna("").astype(str))
    base["_ticket_reclamo_norm"] = ticket_serie.map(normalizar_ticket_panel)
    if "thread_id" in base.columns:
        base["_ticket_reclamo_norm"] = base["_ticket_reclamo_norm"].where(
            base["_ticket_reclamo_norm"].ne(""),
            base["thread_id"].fillna("").astype(str).map(normalizar_ticket_panel),
        )
    if "mensaje_id" in base.columns:
        base["_ticket_reclamo_norm"] = base["_ticket_reclamo_norm"].where(
            base["_ticket_reclamo_norm"].ne(""),
            base["mensaje_id"].fillna("").astype(str).map(normalizar_ticket_panel),
        )
    base["_familia_reclamo_norm"] = base.get("familia_reclamo", pd.Series("", index=base.index)).fillna("").astype(str).map(normalizar_texto_operacional)
    base["_familia_reclamo_norm"] = base["_familia_reclamo_norm"].replace("", "sin familia")
    base["_fecha_reclamo_orden"] = pd.to_datetime(base.get("fecha_reclamo"), errors="coerce")
    base = base.sort_values(["_ticket_reclamo_norm", "_familia_reclamo_norm", "_fecha_reclamo_orden"], kind="mergesort")
    base = base.drop_duplicates(subset=["_ticket_reclamo_norm", "_familia_reclamo_norm"], keep="first")
    return base.drop(columns=[col for col in ["_ticket_reclamo_norm", "_familia_reclamo_norm", "_fecha_reclamo_orden"] if col in base.columns])


def serie_cliente_atencion_panel(df_base):
    if df_base is None or df_base.empty:
        return pd.Series(dtype="object")
    texto_partes = []
    for col in ["Empresa Cliente", "Cliente", "Descripción Detallada", "Descripcion Detallada", "Motivo"]:
        if col in df_base.columns:
            texto_partes.append(df_base[col].fillna("").astype(str))
    if not texto_partes:
        return pd.Series("Sin dato", index=df_base.index, dtype="object")
    texto_total = texto_partes[0].copy()
    for parte in texto_partes[1:]:
        texto_total = texto_total + " | " + parte
    return texto_total.map(cliente_panel_desde_valor)


def filtrar_atenciones_reclamos_panel(df_base, clientes_sel, clientes_todos, zonas_sel, zonas_todas):
    if df_base is None or df_base.empty:
        return pd.DataFrame() if df_base is None else df_base

    base = df_base.copy()
    clientes_sel_set = set(map(str, clientes_sel or []))
    clientes_todos_set = set(map(str, clientes_todos or []))
    if clientes_sel_set and clientes_todos_set and clientes_sel_set != clientes_todos_set:
        base["_cliente_ratio_reclamo"] = serie_cliente_atencion_panel(base)
        base = base.loc[base["_cliente_ratio_reclamo"].astype(str).isin(clientes_sel_set)].copy()

    zonas_sel_set = set(map(str, zonas_sel or []))
    zonas_todas_set = set(map(str, zonas_todas or []))
    if zonas_sel_set and zonas_todas_set and zonas_sel_set != zonas_todas_set:
        if "Estado" in base.columns:
            zonas_base = base["Estado"].map(lambda valor: region_operacional_desde_texto("", valor))
        elif "Ciudad" in base.columns:
            zonas_base = base["Ciudad"].map(lambda valor: region_operacional_desde_texto(valor, ""))
        else:
            zonas_base = pd.Series("Sin zona", index=base.index)
        base = base.loc[zonas_base.astype(str).isin(zonas_sel_set)].copy()

    return base.drop(columns=[col for col in ["_cliente_ratio_reclamo"] if col in base.columns])


def contiene_alias_servicio_panel(texto, servicio):
    limpio = normalizar_texto_operacional(texto)
    for alias in SERVICIO_ALIAS_PANEL.get(str(servicio or "").upper(), []):
        alias_n = normalizar_texto_operacional(alias)
        if not alias_n:
            continue
        if alias_n in {"ibm", "sao"}:
            if re.search(rf"(?<![a-z0-9]){re.escape(alias_n)}(?![a-z0-9])", limpio):
                return True
        elif alias_n in limpio:
            return True
    return False


def reclamo_corresponde_servicio_panel(texto, servicio):
    servicio = str(servicio or "").upper()
    if servicio not in {"IBM", "SAO"}:
        return True
    otro = "SAO" if servicio == "IBM" else "IBM"
    tiene_servicio = contiene_alias_servicio_panel(texto, servicio)
    tiene_otro = contiene_alias_servicio_panel(texto, otro)
    return not (tiene_otro and not tiene_servicio)


def completar_cliente_panel(df_base, columnas_texto):
    if df_base is None or df_base.empty or "cliente" not in df_base.columns:
        return df_base
    base = df_base.copy()
    columnas = [col for col in columnas_texto if col in base.columns]
    if not columnas:
        base["cliente"] = base["cliente"].replace({"": CLIENTE_NO_IDENTIFICADO, "Sin dato": CLIENTE_NO_IDENTIFICADO})
        return base

    texto_total = base[columnas].fillna("").astype(str).agg(" | ".join, axis=1)
    clientes_actuales = base["cliente"].fillna("").astype(str).str.strip()
    clientes_inferidos = texto_total.map(cliente_desde_texto_panel)
    mask_sin_cliente = clientes_actuales.str.lower().isin(CLIENTE_SIN_DATO_EQUIVALENTES)
    mask_inferido = clientes_inferidos.ne("Sin dato")
    base.loc[mask_sin_cliente & mask_inferido, "cliente"] = clientes_inferidos.loc[mask_sin_cliente & mask_inferido]
    base["cliente"] = base["cliente"].replace({"": CLIENTE_NO_IDENTIFICADO, "Sin dato": CLIENTE_NO_IDENTIFICADO})
    return base


def normalizar_coordinadores_sao_panel(df_base):
    if df_base is None or df_base.empty or "coordinador" not in df_base.columns:
        return df_base
    base = df_base.copy()
    if "correo_coordinador" not in base.columns:
        base["correo_coordinador"] = ""
    servicio_serie = base["servicio_tecnico"].astype(str).str.upper() if "servicio_tecnico" in base.columns else pd.Series("SAO", index=base.index)
    mask_sao = servicio_serie.eq("SAO")
    if not mask_sao.any():
        return base
    base.loc[mask_sao, "coordinador"] = [
        nombre_coordinador_sao(nombre, correo) or nombre
        for nombre, correo in zip(
            base.loc[mask_sao, "coordinador"].fillna(""),
            base.loc[mask_sao, "correo_coordinador"].fillna(""),
        )
    ]
    return base


def depurar_reclamos_ibm(df_rec, servicio=None):
    """
    Mantiene reclamos IBM por mala gestion aunque el extractor no haya llenado familia/motivo.
    Excluye correos de bodega, devolucion y TW porque no corresponden al KPI operacional.
    """
    if df_rec is None or df_rec.empty:
        return df_rec

    servicio_label = servicio or SERVICIO_TITULO
    base = df_rec.copy()
    columnas_texto = [
        col for col in [
            "familia_reclamo", "motivo_reclamo", "severidad_reclamo", "remitente", "destinatarios",
            "asunto", "extracto_reclamo", "observacion", "cliente", "region", "zona", "ciudad",
        ]
        if col in base.columns
    ]
    if not columnas_texto:
        return base

    texto_total = base[columnas_texto].fillna("").astype(str).agg(" | ".join, axis=1)
    servicio_codigo = str(servicio or "").upper()
    if servicio_codigo in {"IBM", "SAO"}:
        columnas_servicio = [
            col for col in [
                "remitente", "destinatarios", "asunto", "extracto_reclamo",
                "cliente", "region", "zona", "ciudad",
            ]
            if col in base.columns
        ]
        texto_servicio = base[columnas_servicio].fillna("").astype(str).agg(" | ".join, axis=1) if columnas_servicio else texto_total
        mask_servicio = texto_servicio.map(lambda texto: reclamo_corresponde_servicio_panel(texto, servicio_codigo))
        base = base.loc[mask_servicio].copy()
        texto_total = texto_total.loc[base.index]

    mask_excluir = texto_total.map(contiene_exclusion_reclamo)
    base = base.loc[~mask_excluir].copy()
    texto_total = texto_total.loc[base.index]
    mask_mala_gestion = texto_total.map(contiene_mala_gestion_ibm)
    clasificacion_operacional = texto_total.map(clasificar_reclamo_operacional_panel)
    mask_reclamo_operacional = clasificacion_operacional.map(lambda item: bool(item.get("familia")))

    if "familia_reclamo" in base.columns:
        familia_actual = base["familia_reclamo"].fillna("").astype(str).str.strip()
        familia_generica = familia_actual.eq("") | familia_actual.str.lower().str.contains("mala gestion|sin clasificar", na=False)
        for idx, item in clasificacion_operacional.loc[mask_reclamo_operacional & familia_generica].items():
            base.at[idx, "familia_reclamo"] = item["familia"]
        base.loc[mask_mala_gestion & familia_actual.eq(""), "familia_reclamo"] = f"Mala gestion {servicio_label}"

    if "motivo_reclamo" in base.columns:
        motivo_vacio = base["motivo_reclamo"].fillna("").astype(str).str.strip().eq("")
        for idx, item in clasificacion_operacional.loc[mask_reclamo_operacional & motivo_vacio].items():
            base.at[idx, "motivo_reclamo"] = item["motivo"]
        base.loc[mask_mala_gestion & motivo_vacio, "motivo_reclamo"] = base.loc[mask_mala_gestion & motivo_vacio, "motivo_reclamo"].replace("", "Reclamo por mala gestion operacional")

    if "severidad_reclamo" in base.columns:
        severidad_vacia = base["severidad_reclamo"].fillna("").astype(str).str.strip().eq("")
        base.loc[(mask_mala_gestion | mask_reclamo_operacional) & severidad_vacia, "severidad_reclamo"] = "ALTA"

    if "region" in base.columns:
        base["region"] = [
            region_operacional_desde_texto(texto, region_actual)
            for texto, region_actual in zip(texto_total, base["region"].fillna(""))
        ]
    if "zona" in base.columns and "region" in base.columns:
        base["zona"] = base["zona"].where(base["zona"].fillna("").astype(str).str.strip().ne(""), base["region"])

    if "observacion" in base.columns:
        obs = base["observacion"].fillna("").astype(str)
        marca = f"Detectado como reclamo {servicio_label} por mala gestion operacional"
        base.loc[mask_mala_gestion & ~obs.str.contains("mala gestion", case=False, na=False), "observacion"] = (
            obs.loc[mask_mala_gestion & ~obs.str.contains("mala gestion", case=False, na=False)]
            .map(lambda x: f"{x} | {marca}".strip(" |"))
        )

    return base


def serie_numero_segura(df_base, columna):
    if columna in df_base.columns:
        return pd.to_numeric(df_base[columna], errors="coerce").fillna(0)
    return pd.Series(0, index=df_base.index, dtype="float64")


def calcular_reiteraciones_total_operacional(df_base):
    """
    Regla simplificada: toda re-insistencia por disponibilidad cuenta como reiteracion,
    independiente de si la hace CECOM, PRODRIGUEZA, NPEREZC o RRODRIGUEZB.

    Para no duplicar cuando el CSV ya trae un total, se toma el mayor valor entre:
    - reiteraciones_hasta_respuesta
    - suma de componentes separados: agente CECOM + supervisor CECOM + intervenciones
    """
    if df_base is None or df_base.empty:
        return pd.Series(dtype="float64")

    total_base = pd.concat([
        serie_numero_segura(df_base, "reiteraciones_hasta_respuesta"),
        serie_numero_segura(df_base, "reiteraciones_total_operacional"),
    ], axis=1).max(axis=1).fillna(0)
    componentes = (
        serie_numero_segura(df_base, "reiteraciones_cecom_operador")
        + serie_numero_segura(df_base, "reiteraciones_supervisor_cecom")
        + serie_numero_segura(df_base, "intervenciones_supervisor_servicio_tecnico")
        + serie_numero_segura(df_base, "intervenciones_supervisor_terreno")
    )
    return pd.concat([total_base, componentes], axis=1).max(axis=1).fillna(0)


def aplicar_reiteraciones_total_operacional(df_base):
    if df_base is None or df_base.empty:
        return df_base
    df_base = df_base.copy()
    df_base["reiteraciones_total_operacional"] = calcular_reiteraciones_total_operacional(df_base)
    return df_base


@st.cache_data
def cargar_disponibilidad(ruta_cache, version_cache):
    ruta = Path(ruta_cache)
    if not ruta.exists():
        return pd.DataFrame(columns=DISPONIBILIDAD_COLUMNAS)

    try:
        if ruta.suffix.lower() in {".xlsx", ".xlsm", ".xls"}:
            df_disp = pd.read_excel(ruta)
        else:
            df_disp = pd.read_csv(ruta, encoding="utf-8-sig")
    except Exception:
        return pd.DataFrame(columns=DISPONIBILIDAD_COLUMNAS)

    for col in DISPONIBILIDAD_COLUMNAS:
        if col not in df_disp.columns:
            df_disp[col] = pd.NA

    for col in ["fecha_solicitud", "fecha_respuesta", "fecha_primera_reiteracion", "fecha_ultima_reiteracion", "actualizado_en"]:
        df_disp[col] = pd.to_datetime(df_disp[col], errors="coerce")

    for col in [
        "minutos_habiles", "minutos_calendario", "exceso_sla_habiles",
        "secuencia_solicitud", "solicitud_caso_n", "total_solicitudes_caso",
        "solicitudes_en_ciclo", "reiteraciones_previas", "reiteraciones_hasta_respuesta",
        "reiteraciones_total_operacional", "reiteraciones_cecom_operador", "reiteraciones_supervisor_cecom",
        "intervenciones_supervisor_terreno", "intervenciones_supervisor_servicio_tecnico",
    ]:
        df_disp[col] = pd.to_numeric(df_disp[col], errors="coerce")

    texto_cumple = serie_texto_limpio(df_disp["cumple_kpi"]).str.lower()
    df_disp["cumple_kpi"] = texto_cumple.isin({"true", "1", "si", "sí", "cumple", "ok"})

    for col in [
        "cliente", "numero_ticket", "ticket_principal", "region", "zona", "ciudad",
        "coordinador", "correo_coordinador", "coordinador_tipo", "remitente_cecom",
        "asunto_solicitud", "estado_kpi", "demora_respuesta", "exceso_sla",
        "tipo_solicitud", "interventores_supervisor_terreno", "interventores_supervisor_servicio_tecnico", "remitentes_reiteracion",
        "fechas_reiteracion", "grupo_solicitud_id", "thread_id", "fuente_pst", "observacion",
    ]:
        df_disp[col] = serie_texto_limpio(df_disp[col])

    df_disp = completar_cliente_panel(
        df_disp,
        [
            "cliente", "asunto_solicitud", "observacion", "remitente_cecom",
            "numero_ticket", "ticket_principal", "region", "zona", "ciudad",
        ],
    )
    df_disp["region"] = df_disp["region"].where(df_disp["region"].ne(""), df_disp["zona"])
    df_disp["zona"] = df_disp["zona"].where(df_disp["zona"].ne(""), df_disp["region"])
    df_disp["ticket_principal"] = df_disp["ticket_principal"].where(df_disp["ticket_principal"].ne(""), df_disp["numero_ticket"])
    df_disp["coordinador"] = df_disp["coordinador"].replace("", "Sin respuesta")
    df_disp["tipo_solicitud"] = df_disp["tipo_solicitud"].replace("", "Solicitud inicial")
    df_disp["exceso_sla"] = df_disp["exceso_sla"].replace("", "Sin exceso")
    df_disp["reiteraciones_previas"] = df_disp["reiteraciones_previas"].fillna(0)
    df_disp["reiteraciones_hasta_respuesta"] = df_disp["reiteraciones_hasta_respuesta"].fillna(0)
    for col in ["solicitud_caso_n", "total_solicitudes_caso", "solicitudes_en_ciclo", "reiteraciones_total_operacional", "reiteraciones_cecom_operador", "reiteraciones_supervisor_cecom", "intervenciones_supervisor_terreno", "intervenciones_supervisor_servicio_tecnico"]:
        df_disp[col] = df_disp[col].fillna(0)
    df_disp["intervenciones_supervisor_servicio_tecnico"] = df_disp["intervenciones_supervisor_servicio_tecnico"].where(
        df_disp["intervenciones_supervisor_servicio_tecnico"].ne(0),
        df_disp["intervenciones_supervisor_terreno"],
    )
    df_disp["interventores_supervisor_servicio_tecnico"] = df_disp["interventores_supervisor_servicio_tecnico"].where(
        df_disp["interventores_supervisor_servicio_tecnico"].ne(""),
        df_disp["interventores_supervisor_terreno"],
    )
    df_disp = aplicar_reiteraciones_total_operacional(df_disp)
    df_disp["region"] = df_disp["region"].replace("", "Sin zona")
    df_disp["zona"] = df_disp["zona"].replace("", "Sin zona")
    df_disp["ciudad"] = df_disp["ciudad"].replace("", "Sin dato")
    df_disp["cliente"] = df_disp["cliente"].replace({"": CLIENTE_NO_IDENTIFICADO, "Sin dato": CLIENTE_NO_IDENTIFICADO})

    desde_2026 = pd.Timestamp("2026-01-01")
    if "fecha_solicitud" in df_disp.columns:
        df_disp = df_disp.loc[df_disp["fecha_solicitud"].isna() | df_disp["fecha_solicitud"].ge(desde_2026)].copy()

    df_disp["mes"] = serie_mes_operacional(df_disp, "fecha_solicitud", "mes")
    df_disp["mes"] = pd.Categorical(df_disp["mes"], categories=MESES, ordered=True)

    return df_disp[DISPONIBILIDAD_COLUMNAS].copy()


@st.cache_data
def cargar_reclamos(ruta_cache, version_cache, servicio=None):
    ruta = Path(ruta_cache)
    if not ruta.exists():
        return pd.DataFrame(columns=RECLAMOS_COLUMNAS)

    try:
        df_rec = pd.read_csv(ruta, encoding="utf-8-sig")
    except Exception:
        return pd.DataFrame(columns=RECLAMOS_COLUMNAS)

    for col in RECLAMOS_COLUMNAS:
        if col not in df_rec.columns:
            df_rec[col] = pd.NA

    for col in ["fecha_reclamo", "fecha_programada_reclamo", "fecha_wfm", "actualizado_en"]:
        df_rec[col] = pd.to_datetime(df_rec[col], errors="coerce")

    df_rec["diferencia_hora_wfm_min"] = pd.to_numeric(df_rec["diferencia_hora_wfm_min"], errors="coerce")

    for col in [
        "cliente", "numero_ticket", "ticket_principal", "region", "zona", "ciudad",
        "tipo_registro", "familia_reclamo", "motivo_reclamo", "severidad_reclamo",
        "proveedor_reforzado", "motivo_reforzamiento", "remitente",
        "destinatarios", "asunto", "extracto_reclamo", "hora_programada_reclamo",
        "estado_wfm", "ventana_wfm", "inicio_wfm", "tecnico_wfm", "mismo_dia_wfm",
        "mes", "thread_id", "mensaje_id", "fuente_pst", "observacion",
    ]:
        df_rec[col] = serie_texto_limpio(df_rec[col])
    df_rec["reforzamiento"] = serie_bool_panel(df_rec["reforzamiento"])
    df_rec["tipo_registro"] = df_rec["tipo_registro"].where(
        df_rec["tipo_registro"].ne(""),
        df_rec["reforzamiento"].map({True: "Reforzamiento", False: "Reclamo"}),
    )

    df_rec = completar_cliente_panel(
        df_rec,
        [
            "cliente", "asunto", "extracto_reclamo", "observacion",
            "remitente", "destinatarios", "numero_ticket", "ticket_principal",
            "region", "zona", "ciudad",
        ],
    )
    df_rec["region"] = df_rec["region"].replace("", "Sin zona")
    df_rec["zona"] = df_rec["zona"].where(df_rec["zona"].ne(""), df_rec["region"])
    df_rec["ticket_principal"] = df_rec["ticket_principal"].where(df_rec["ticket_principal"].ne(""), df_rec["numero_ticket"])

    df_rec = depurar_reclamos_ibm(df_rec, servicio)
    df_rec["cliente"] = df_rec["cliente"].replace({"": CLIENTE_NO_IDENTIFICADO, "Sin dato": CLIENTE_NO_IDENTIFICADO})

    desde_2026 = pd.Timestamp("2026-01-01")
    df_rec = df_rec.loc[df_rec["fecha_reclamo"].isna() | df_rec["fecha_reclamo"].ge(desde_2026)].copy()
    df_rec["mes"] = serie_mes_operacional(df_rec, "fecha_reclamo", "mes")
    df_rec["mes"] = pd.Categorical(df_rec["mes"], categories=MESES, ordered=True)

    return df_rec[RECLAMOS_COLUMNAS].copy()


@st.cache_data
def cargar_epa(ruta_db, version_db):
    ruta = Path(ruta_db)
    columnas = [
        "proveedor", "atencion_id", "public_token", "atencion_creada",
        "cliente", "region", "st", "ticket", "tecnico", "fecha_atencion", "canal",
        "contacto", "servicio", "observacion_interna", "respondida",
        "respuesta_id", "respuesta_creada", "q1", "q2", "q3", "q4", "q5",
        "promedio", "comentario",
    ]

    if not ruta.exists():
        return pd.DataFrame(columns=columnas)

    try:
        with sqlite3.connect(ruta) as con:
            tablas = pd.read_sql_query(
                "SELECT name FROM sqlite_master WHERE type='table'",
                con
            )["name"].tolist()

            if "atenciones" not in tablas:
                return pd.DataFrame(columns=columnas)

            columnas_atenciones = set(
                pd.read_sql_query("PRAGMA table_info(atenciones)", con)["name"].tolist()
            )
            region_expr = "a.region" if "region" in columnas_atenciones else "'' AS region"

            return pd.read_sql_query(
                f"""
                SELECT
                    a.proveedor,
                    a.id AS atencion_id,
                    a.public_token,
                    a.created_at AS atencion_creada,
                    a.cliente,
                    {region_expr},
                    a.st,
                    a.ticket,
                    a.tecnico,
                    a.fecha_atencion,
                    a.canal,
                    a.contacto,
                    a.servicio,
                    a.observacion_interna,
                    CASE WHEN r.id IS NULL THEN 0 ELSE 1 END AS respondida,
                    r.id AS respuesta_id,
                    r.created_at AS respuesta_creada,
                    r.q1,
                    r.q2,
                    r.q3,
                    r.q4,
                    r.q5,
                    ROUND((r.q1 + r.q2 + r.q3 + r.q4 + r.q5) / 5.0, 2) AS promedio,
                    r.comentario
                FROM atenciones a
                LEFT JOIN respuestas r ON r.atencion_id = a.id
                ORDER BY a.created_at DESC
                """,
                con,
            )
    except Exception:
        return pd.DataFrame(columns=columnas)


def concatenar_frames_servicio(frames):
    frames_validos = [frame for frame in frames if frame is not None and not frame.empty]
    if not frames_validos:
        return pd.DataFrame()
    return pd.concat(frames_validos, ignore_index=True, sort=False)


def cargar_atenciones_servicios(servicios):
    frames = []
    for servicio in servicios:
        config = SERVICIOS_CONFIG[servicio]
        ruta = APP_DIR / str(config["archivo"])
        base = cargar(str(ruta), version_archivo_opcional(ruta))
        if not base.empty:
            base["servicio_tecnico"] = servicio
            frames.append(base)
    return concatenar_frames_servicio(frames)


def cargar_epa_servicios(servicios):
    frames = []
    for servicio in servicios:
        ruta = ruta_epa_activa(servicio)
        base = cargar_epa(str(ruta), version_archivo_opcional(ruta))
        if not base.empty:
            base["servicio_tecnico"] = servicio
            frames.append(base)
    return concatenar_frames_servicio(frames)


def cargar_disponibilidad_servicios(servicios):
    frames = []
    for servicio in servicios:
        config = SERVICIOS_CONFIG[servicio]
        if not config.get("participa_disponibilidad", True) or not config.get("disponibilidad"):
            continue
        ruta = APP_DIR / str(config["disponibilidad"])
        base = cargar_disponibilidad(str(ruta), version_archivo_opcional(ruta))
        if not base.empty:
            base["servicio_tecnico"] = servicio
            frames.append(base)
    return concatenar_frames_servicio(frames)


def cargar_reclamos_servicios(servicios):
    frames = []
    for servicio in servicios:
        config = SERVICIOS_CONFIG[servicio]
        if not config.get("participa_reclamos", True) or not config.get("reclamos"):
            continue
        ruta = APP_DIR / str(config["reclamos"])
        base = cargar_reclamos(str(ruta), version_archivo_opcional(ruta), servicio)
        if not base.empty:
            base["servicio_tecnico"] = servicio
            frames.append(base)
    return concatenar_frames_servicio(frames)


def existe_cache_disponibilidad(servicios):
    return any(
        SERVICIOS_CONFIG[servicio].get("participa_disponibilidad", True)
        and bool(SERVICIOS_CONFIG[servicio].get("disponibilidad"))
        and (APP_DIR / str(SERVICIOS_CONFIG[servicio]["disponibilidad"])).exists()
        for servicio in servicios
    )


@st.cache_data(show_spinner=False, ttl=600)
def crear_excel_filtrado(df_export, filtros_export, sheet_name="Datos filtrados", titulo="Vista filtrada dashboard operaciones"):
    salida = BytesIO()
    df_excel = df_export.copy()

    for col in df_excel.select_dtypes(include=["category"]).columns:
        df_excel[col] = df_excel[col].astype(str)

    control = pd.DataFrame(
        [
            ["Propiedad", APP_OWNER],
            ["Firma", APP_SIGNATURE],
            ["Generado", datetime.now().strftime("%d-%m-%Y %H:%M:%S")],
            ["Regiones", ", ".join(filtros_export.get("regiones", []))],
            ["Tecnicos", ", ".join(filtros_export.get("tecnicos", []))],
            ["Meses", ", ".join(filtros_export.get("meses", []))],
            ["Clientes", ", ".join(filtros_export.get("clientes", []))],
            ["Zonas", ", ".join(filtros_export.get("zonas", []))],
            ["Registros exportados", len(df_excel)],
        ],
        columns=["Campo", "Valor"]
    )

    with pd.ExcelWriter(salida, engine="openpyxl") as writer:
        df_excel.to_excel(writer, sheet_name=sheet_name, index=False)
        control.to_excel(writer, sheet_name="Control interno", index=False)

        libro = writer.book
        libro.properties.creator = APP_OWNER
        libro.properties.title = titulo
        libro.properties.subject = APP_SIGNATURE

        hoja = writer.sheets[sheet_name]
        hoja.freeze_panes = "A2"
        hoja.auto_filter.ref = hoja.dimensions

        for col_cells in hoja.columns:
            encabezado = str(col_cells[0].value) if col_cells[0].value is not None else ""
            ancho = min(max(len(encabezado) + 4, 12), 42)
            hoja.column_dimensions[col_cells[0].column_letter].width = ancho

        hoja_control = writer.sheets["Control interno"]
        hoja_control.sheet_state = "hidden"

    salida.seek(0)
    return salida.getvalue()


def preparar_export_epa(df_epa_base):
    vista_epa = df_epa_base.copy()
    if "respondida" in vista_epa.columns:
        vista_epa["Estado EPA"] = vista_epa["respondida"].fillna(0).astype(int).map({1: "Respondida", 0: "Pendiente"})

    columnas_epa = [
        "Estado EPA", "servicio_tecnico", "cliente", "region", "st", "ticket", "tecnico", "fecha_atencion",
        "promedio", "q1", "q2", "q3", "q4", "q5", "comentario", "respuesta_creada",
    ]
    columnas_epa = [col for col in columnas_epa if col in vista_epa.columns]
    vista_epa = vista_epa[columnas_epa] if columnas_epa else vista_epa
    return vista_epa.rename(columns={"servicio_tecnico": "Servicio tecnico"})


def preparar_export_disponibilidad(df_disp_base):
    vista = df_disp_base.copy()
    if "cumple_kpi" in vista.columns:
        vista["Cumple KPI"] = vista["cumple_kpi"].fillna(False).astype(bool).map({True: "Si", False: "No"})

    columnas = [
        "servicio_tecnico", "cliente", "numero_ticket", "ticket_principal", "region", "ciudad", "coordinador",
        "correo_coordinador", "coordinador_tipo", "remitente_cecom",
        "asunto_solicitud", "fecha_solicitud", "fecha_respuesta",
        "minutos_habiles", "minutos_calendario", "demora_respuesta",
        "exceso_sla_habiles", "exceso_sla", "tipo_solicitud",
        "solicitud_caso_n", "total_solicitudes_caso", "solicitudes_en_ciclo",
        "reiteraciones_total_operacional", "reiteraciones_hasta_respuesta", "reiteraciones_cecom_operador",
        "reiteraciones_supervisor_cecom", "intervenciones_supervisor_servicio_tecnico",
        "interventores_supervisor_servicio_tecnico", "remitentes_reiteracion",
        "fechas_reiteracion", "fecha_primera_reiteracion", "fecha_ultima_reiteracion",
        "Cumple KPI", "estado_kpi",
        "observacion", "thread_id", "grupo_solicitud_id",
    ]
    columnas = [col for col in columnas if col in vista.columns]
    vista = vista[columnas] if columnas else vista
    return vista.rename(columns={
        "servicio_tecnico": "Servicio tecnico",
        "cliente": "Cliente",
        "numero_ticket": "Numero ticket",
        "ticket_principal": "Ticket principal",
        "region": "Region",
        "ciudad": "Ciudad",
        "coordinador": f"Respondedor {SERVICIO_TITULO}",
        "correo_coordinador": "Correo respondedor",
        "coordinador_tipo": "Rol respondedor",
        "remitente_cecom": "Solicitante CECOM",
        "asunto_solicitud": "Asunto correo",
        "fecha_solicitud": "Fecha hora solicitud CECOM",
        "fecha_respuesta": f"Fecha hora respuesta {SERVICIO_TITULO}",
        "minutos_habiles": "Minutos habiles respuesta",
        "minutos_calendario": "Minutos calendario",
        "demora_respuesta": "Demora respuesta",
        "exceso_sla_habiles": "Exceso SLA habiles",
        "exceso_sla": "Exceso SLA",
        "tipo_solicitud": "Tipo solicitud",
        "solicitud_caso_n": "Solicitud caso N",
        "total_solicitudes_caso": "Total solicitudes caso",
        "solicitudes_en_ciclo": "Correos solicitud en ciclo",
        "reiteraciones_total_operacional": "Reiteraciones totales",
        "reiteraciones_hasta_respuesta": "Reiteraciones base",
        "reiteraciones_cecom_operador": "Reiteraciones agente CECOM",
        "reiteraciones_supervisor_cecom": "Reiteraciones supervisor CECOM",
        "intervenciones_supervisor_servicio_tecnico": "Intervenciones Supervisor Servicio Tecnico",
        "interventores_supervisor_servicio_tecnico": "Supervisor Servicio Tecnico involucrado",
        "remitentes_reiteracion": "Remitentes reiteracion",
        "fechas_reiteracion": "Fechas reiteracion",
        "fecha_primera_reiteracion": "Primera reiteracion",
        "fecha_ultima_reiteracion": "Ultima reiteracion",
        "estado_kpi": "Estado KPI",
        "observacion": "Observacion",
        "thread_id": "Thread correo",
        "grupo_solicitud_id": "Grupo solicitud",
    })


def preparar_export_reclamos(df_rec_base):
    vista = df_rec_base.copy()
    columnas = [
        "servicio_tecnico", "fecha_reclamo", "cliente", "numero_ticket", "ticket_principal", "region", "ciudad",
        "tipo_registro", "familia_reclamo", "motivo_reclamo", "severidad_reclamo",
        "reforzamiento", "proveedor_reforzado", "motivo_reforzamiento", "remitente",
        "destinatarios", "asunto", "extracto_reclamo", "fecha_programada_reclamo",
        "hora_programada_reclamo", "estado_wfm", "fecha_wfm", "ventana_wfm",
        "inicio_wfm", "tecnico_wfm", "mismo_dia_wfm", "diferencia_hora_wfm_min",
        "observacion", "thread_id",
    ]
    columnas = [col for col in columnas if col in vista.columns]
    vista = vista[columnas] if columnas else vista
    return vista.rename(columns={
        "servicio_tecnico": "Servicio tecnico",
        "fecha_reclamo": "Fecha hora reclamo",
        "cliente": "Cliente",
        "numero_ticket": "Numero ticket",
        "ticket_principal": "Ticket principal",
        "region": "Region",
        "ciudad": "Ciudad",
        "tipo_registro": "Tipo señal",
        "familia_reclamo": "Familia reclamo",
        "motivo_reclamo": "Motivo reclamo",
        "severidad_reclamo": "Severidad",
        "reforzamiento": "Reforzamiento",
        "proveedor_reforzado": "ST reforzado",
        "motivo_reforzamiento": "Motivo reforzamiento",
        "remitente": "Remitente",
        "destinatarios": "Destinatarios",
        "asunto": "Asunto",
        "extracto_reclamo": "Extracto reclamo",
        "fecha_programada_reclamo": "Fecha programada reclamo",
        "hora_programada_reclamo": "Hora programada reclamo",
        "estado_wfm": "Estado WFM",
        "fecha_wfm": "Fecha WFM",
        "ventana_wfm": "Ventana WFM",
        "inicio_wfm": "Inicio WFM",
        "tecnico_wfm": "Tecnico WFM",
        "mismo_dia_wfm": "Mismo dia WFM",
        "diferencia_hora_wfm_min": "Diferencia hora WFM min",
        "observacion": "Observacion",
        "thread_id": "Thread correo",
    })


@st.cache_data(show_spinner=False)
def cargar_uso_herramienta(ruta_archivo, version_archivo):
    ruta = Path(ruta_archivo)
    columnas = [
        "folio_ot", "ticket", "cliente", "ciudad", "region_atendida", "fecha_atencion",
        "tecnico", "st", "puntaje_total", "estado_calidad", "score_detalle",
        "score_equipos", "score_activo_fijo", "score_redaccion", "requiere_retiro",
        "requiere_instalacion", "cliente_cge", "activo_fijo_detectado", "hallazgos",
    ]
    if not ruta.exists():
        return pd.DataFrame(columns=columnas)
    try:
        df_uso = pd.read_csv(ruta, encoding="utf-8-sig")
    except UnicodeDecodeError:
        df_uso = pd.read_csv(ruta, encoding="latin1")
    for col in columnas:
        if col not in df_uso.columns:
            df_uso[col] = ""
    for col in ["puntaje_total", "score_detalle", "score_equipos", "score_activo_fijo", "score_redaccion"]:
        df_uso[col] = pd.to_numeric(df_uso[col], errors="coerce")
    df_uso["st"] = df_uso["st"].fillna("Sin clasificar").astype(str).str.strip().str.upper().replace({"": "Sin clasificar"})
    df_uso["servicio_tecnico"] = df_uso["st"]
    return df_uso


def cargar_uso_herramienta_servicios(servicios):
    ruta = APP_DIR / "USO_HERRAMIENTA_OT_2026.csv"
    base = cargar_uso_herramienta(str(ruta), version_archivo_opcional(ruta))
    if base.empty or "st" not in base.columns:
        return base
    servicios_validos = {
        servicio for servicio in servicios
        if SERVICIOS_CONFIG[servicio].get("participa_uso_herramienta", True)
    }
    return base.loc[base["st"].isin(servicios_validos)].copy()


def preparar_export_uso_herramienta(df_uso_base):
    vista = df_uso_base.copy()
    columnas = [
        "servicio_tecnico", "folio_ot", "ticket", "cliente", "ciudad", "region_atendida",
        "fecha_atencion", "hora_inicio", "hora_termino", "tecnico", "puntaje_total",
        "estado_calidad", "score_identificacion", "score_detalle", "score_equipos",
        "score_activo_fijo", "score_redaccion", "score_firmas", "requiere_retiro",
        "requiere_instalacion", "cliente_cge", "activo_fijo_detectado", "hallazgos",
        "fortalezas", "descripcion", "archivo_pdf", "correo_asunto", "fecha_correo",
        "fuente_clasificacion", "match_score",
    ]
    columnas = [col for col in columnas if col in vista.columns]
    vista = vista[columnas] if columnas else vista
    return vista.rename(columns={
        "servicio_tecnico": "Servicio tecnico",
        "folio_ot": "Folio OT",
        "ticket": "Ticket",
        "cliente": "Cliente",
        "ciudad": "Ciudad",
        "region_atendida": "Region atendida",
        "fecha_atencion": "Fecha atencion",
        "hora_inicio": "Hora inicio",
        "hora_termino": "Hora termino",
        "tecnico": "Tecnico",
        "puntaje_total": "Nota OT",
        "estado_calidad": "Clasificacion",
        "score_identificacion": "Score identificacion",
        "score_detalle": "Score detalle",
        "score_equipos": "Score equipos",
        "score_activo_fijo": "Score activo fijo",
        "score_redaccion": "Score redaccion",
        "score_firmas": "Score firmas",
        "requiere_retiro": "Requiere retiro",
        "requiere_instalacion": "Requiere instalacion",
        "cliente_cge": "Cliente CGE",
        "activo_fijo_detectado": "Activo fijo detectado",
        "hallazgos": "Hallazgos",
        "fortalezas": "Fortalezas",
        "descripcion": "Descripcion OT",
        "archivo_pdf": "Archivo PDF",
        "correo_asunto": "Asunto correo",
        "fecha_correo": "Fecha correo",
        "fuente_clasificacion": "Fuente clasificacion",
        "match_score": "Score match tecnico",
    })


def preparar_vista_reclamos_limpia(df_reclamos_export):
    columnas = [
        "Servicio tecnico", "Fecha hora reclamo", "Cliente", "Numero ticket", "Ticket principal",
        "Tipo señal", "Familia reclamo", "Motivo reclamo", "Severidad", "ST reforzado", "Region", "Ciudad",
    ]
    columnas = [col for col in columnas if col in df_reclamos_export.columns]
    return df_reclamos_export[columnas].copy() if columnas else df_reclamos_export.copy()


def render_boton_revisitas(df_revisitas, filtros_export):
    nombre_archivo = f"revisitas_filtradas_entel_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    excel_b64 = base64.b64encode(crear_excel_filtrado(df_revisitas, filtros_export)).decode("ascii")
    st.markdown(
        f"""
        <div class="revisita-export-shell">
            <a class="revisita-download-icon"
               href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{excel_b64}"
               download="{nombre_archivo}"
               title="Descargar revisitas filtradas"
               aria-label="Descargar revisitas filtradas">
                <svg viewBox="0 0 24 24" fill="none" stroke-width="2.35" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                    <path d="M12 4v10"></path>
                    <path d="m7.5 9.8 4.5 4.5 4.5-4.5"></path>
                    <path d="M5 18.5h14"></path>
                </svg>
            </a>
        </div>
        """,
        unsafe_allow_html=True
    )


def render_boton_exportar_epa_revision(df_epa_export, filtros_export):
    nombre_archivo = f"epa_filtrada_entel_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    excel_b64 = base64.b64encode(
        crear_excel_filtrado(df_epa_export, filtros_export, "EPA filtrada", "Vista filtrada EPA Entel")
    ).decode("ascii")
    st.markdown(
        f"""
        <div class="revisita-export-shell">
            <a class="revisita-download-icon"
               href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{excel_b64}"
               download="{nombre_archivo}"
               title="Descargar EPA filtrada"
               aria-label="Descargar EPA filtrada">
                <svg viewBox="0 0 24 24" fill="none" stroke-width="2.35" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                    <path d="M12 4v10"></path>
                    <path d="m7.5 9.8 4.5 4.5 4.5-4.5"></path>
                    <path d="M5 18.5h14"></path>
                </svg>
            </a>
        </div>
        """,
        unsafe_allow_html=True
    )


def render_boton_exportar_datos(df_export, filtros_export, modo="datos"):
    es_epa = modo == "epa"
    es_disponibilidad = modo == "disponibilidad"
    es_reclamos = modo == "reclamos"
    es_uso_herramienta = modo == "uso_herramienta"
    nombre_archivo = (
        f"epa_filtrada_entel_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        if es_epa else
        f"disponibilidad_filtrada_entel_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        if es_disponibilidad else
        f"reclamos_filtrados_entel_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        if es_reclamos else
        f"uso_herramienta_ot_filtrado_entel_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        if es_uso_herramienta else
        f"vista_filtrada_entel_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    )
    sheet_name = "EPA filtrada" if es_epa else "Disponibilidad" if es_disponibilidad else "Reclamos" if es_reclamos else "KPI Uso Herramienta" if es_uso_herramienta else "Datos filtrados"
    titulo_excel = (
        "Vista filtrada EPA Entel" if es_epa else
        f"KPI Disponibilidad {SERVICIO_TITULO}" if es_disponibilidad else
        f"KPI Reclamos {SERVICIO_TITULO}" if es_reclamos else
        f"KPI Uso correcto de herramienta {SERVICIO_TITULO}" if es_uso_herramienta else
        "Vista filtrada dashboard operaciones"
    )
    titulo_link = "Exportar EPA filtrada" if es_epa else "Exportar disponibilidad filtrada" if es_disponibilidad else "Exportar reclamos filtrados" if es_reclamos else "Exportar auditoria OT filtrada" if es_uso_herramienta else "Exportar datos filtrados"
    kicker = "EPA filtrada" if es_epa else "KPI Disponibilidad" if es_disponibilidad else "KPI Reclamos" if es_reclamos else "KPI Uso Herramienta" if es_uso_herramienta else "Datos filtrados"
    texto_boton = "Exportar EPA" if es_epa else "Exportar disponibilidad" if es_disponibilidad else "Exportar reclamos" if es_reclamos else "Exportar OT" if es_uso_herramienta else "Exportar datos"
    modo_anterior = st.session_state.get("_export_mode_rendered")
    animar_modo = modo_anterior is not None and modo_anterior != modo
    st.session_state["_export_mode_rendered"] = modo
    clases_export = [
        "sidebar-export-card",
        "sidebar-export-card-epa" if es_epa else "sidebar-export-card-disponibilidad" if es_disponibilidad else "sidebar-export-card-data",
    ]
    if animar_modo:
        clases_export.append("sidebar-export-card-animate")
    clase_export = " ".join(clases_export)
    excel_b64 = base64.b64encode(
        crear_excel_filtrado(df_export, filtros_export, sheet_name, titulo_excel)
    ).decode("ascii")
    st.markdown(
        f"""
        <a class="{clase_export}"
           href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{excel_b64}"
           download="{nombre_archivo}"
           title="{titulo_link}"
           aria-label="{titulo_link}">
            <span class="sidebar-export-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke-width="2.25" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                    <path d="M12 3v10"></path>
                    <path d="m7.5 8.8 4.5 4.5 4.5-4.5"></path>
                    <path d="M5 17.5h14"></path>
                    <path d="M7 20.5h10"></path>
                </svg>
            </span>
            <span class="sidebar-export-text">
                <span class="sidebar-export-kicker">{kicker}</span>
                <span class="sidebar-export-title">{texto_boton}</span>
            </span>
        </a>
        """,
        unsafe_allow_html=True
    )

df = cargar_atenciones_servicios(SERVICIOS_ACTIVOS)
EPA_DB_ACTIVA = ruta_epa_activa(SERVICIOS_ACTIVOS[0])
df_epa = cargar_epa_servicios(SERVICIOS_ACTIVOS)
df_disponibilidad = cargar_disponibilidad_servicios(SERVICIOS_ACTIVOS)
df_disponibilidad = normalizar_coordinadores_sao_panel(df_disponibilidad)
df_reclamos = cargar_reclamos_servicios(SERVICIOS_ACTIVOS)
df_disponibilidad = completar_cliente_desde_atenciones_panel(df_disponibilidad, df)
df_reclamos = completar_cliente_desde_atenciones_panel(df_reclamos, df)
df_disponibilidad = completar_zona_desde_atenciones_panel(df_disponibilidad, df)
df_reclamos = completar_zona_desde_atenciones_panel(df_reclamos, df)
df_reclamos = deduplicar_reclamos_ticket_familia_panel(df_reclamos)
df_uso_herramienta = cargar_uso_herramienta_servicios(SERVICIOS_ACTIVOS)

KPI_INICIO = "KPI Inicio Actividad"
KPI_EPA = "KPI EPA Satisfacci\u00f3n"
KPI_USO_HERRAMIENTA = "KPI Uso correcto de herramienta"
KPI_DISPONIBILIDAD = "KPI Disponibilidad"
KPI_RECLAMOS = "KPI Reclamos"
KPI_OPCIONES = [KPI_INICIO, KPI_EPA, KPI_USO_HERRAMIENTA, KPI_DISPONIBILIDAD, KPI_RECLAMOS]
DEMO_TECH_KEYWORDS = ("DEMO", "PRUEBA", "TEST")
CLIENTE_EPA_EXCLUIR_EXACTO = {"CLIENTE VISUAL"}
CLIENTE_EPA_EXCLUIR_KEYWORDS = ("DEMO", "PRUEBA", "TEST")


def es_tecnico_demo(valor):
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    texto = texto.encode("ascii", "ignore").decode("ascii").upper()
    return any(keyword in texto for keyword in DEMO_TECH_KEYWORDS)


def es_cliente_epa_no_real(valor):
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    texto = texto.encode("ascii", "ignore").decode("ascii").upper()
    texto = " ".join(texto.split())
    if texto in CLIENTE_EPA_EXCLUIR_EXACTO:
        return True
    return any(keyword in texto for keyword in CLIENTE_EPA_EXCLUIR_KEYWORDS)


if "cliente" in df_epa.columns:
    cliente_real_mask = df_epa["cliente"].map(es_cliente_epa_no_real).fillna(False).astype(bool)
    df_epa = df_epa.loc[~cliente_real_mask].copy()

if st.session_state.get("kpi_activo") not in KPI_OPCIONES:
    st.session_state["kpi_activo"] = KPI_INICIO

pagina_epa_activa = st.session_state.get("kpi_activo") == KPI_EPA
pagina_uso_herramienta_activa = st.session_state.get("kpi_activo") == KPI_USO_HERRAMIENTA
pagina_disponibilidad_activa = st.session_state.get("kpi_activo") == KPI_DISPONIBILIDAD
pagina_reclamos_activa = st.session_state.get("kpi_activo") == KPI_RECLAMOS
pagina_disp_rec_activa = pagina_disponibilidad_activa or pagina_reclamos_activa
disponibilidad_no_aplica_servicio = (not SERVICIO_COMPARATIVO) and (not SERVICIOS_CONFIG.get(SERVICIO_ACTUAL, {}).get("participa_disponibilidad", True))
reclamos_no_aplica_servicio = (not SERVICIO_COMPARATIVO) and (not SERVICIOS_CONFIG.get(SERVICIO_ACTUAL, {}).get("participa_reclamos", True))
pagina_kpi_no_aplica_servicio = (
    (pagina_disponibilidad_activa and disponibilidad_no_aplica_servicio)
    or (pagina_reclamos_activa and reclamos_no_aplica_servicio)
)
if pagina_kpi_no_aplica_servicio:
    pagina_disp_rec_activa = False

# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    df_filtros_base = df
    if pagina_uso_herramienta_activa and not df_uso_herramienta.empty:
        df_filtros_base = df_uso_herramienta.rename(columns={"region_atendida": "Estado", "tecnico": "Recurso"}).copy()

    regiones = sorted(df_filtros_base["Estado"].dropna().unique()) if "Estado" in df_filtros_base.columns else []
    tecnicos = sorted(
        t for t in df_filtros_base["Recurso"].dropna().unique()
        if not es_tecnico_demo(t)
    ) if "Recurso" in df_filtros_base.columns else []
    clientes_epa = sorted(
        c for c in df_epa["cliente"].dropna().astype(str).str.strip().replace("", pd.NA).dropna().unique()
        if not es_cliente_epa_no_real(c)
    ) if "cliente" in df_epa.columns else []
    clientes_reclamos = sorted(
        c for c in df_reclamos["cliente"].dropna().astype(str).str.strip().replace("", pd.NA).dropna().unique()
    ) if "cliente" in df_reclamos.columns else []
    clientes_disponibilidad = sorted(set(
        c for c in df_disponibilidad["cliente"].dropna().astype(str).str.strip().replace("", pd.NA).dropna().unique()
    ) | set(clientes_reclamos)) if "cliente" in df_disponibilidad.columns else clientes_reclamos
    zonas_reclamos = sorted(
        z for z in df_reclamos["region"].dropna().astype(str).str.strip().replace("", pd.NA).dropna().unique()
    ) if "region" in df_reclamos.columns else []
    zonas_atenciones = sorted(
        z for z in df["Estado"].dropna().astype(str).str.strip().replace("", pd.NA).dropna().unique()
    ) if "Estado" in df.columns else []
    zonas_disponibilidad = sorted(set(
        z for z in df_disponibilidad["region"].dropna().astype(str).str.strip().replace("", pd.NA).dropna().unique()
    ) | set(zonas_reclamos) | set(zonas_atenciones)) if "region" in df_disponibilidad.columns else sorted(set(zonas_reclamos) | set(zonas_atenciones))
    coordinadores_disponibilidad = []
    if SERVICIO_ACTUAL == "SAO" and "coordinador" in df_disponibilidad.columns:
        base_coord = df_disponibilidad.copy()
        if "correo_coordinador" not in base_coord.columns:
            base_coord["correo_coordinador"] = ""
        if "fecha_respuesta" in base_coord.columns:
            base_coord = base_coord.loc[base_coord["fecha_respuesta"].notna()].copy()
        base_coord["_coord_email_norm"] = base_coord["correo_coordinador"].map(correo_limpio_panel)
        base_coord["_coord_nombre_email_norm"] = base_coord["coordinador"].map(correo_limpio_panel)
        base_coord["_coord_nombre_norm"] = base_coord["coordinador"].map(normalizar_texto_operacional)
        base_coord = base_coord.loc[
            base_coord["_coord_email_norm"].isin(SAO_COORDINADORES_AUDITADOS.keys())
            | base_coord["_coord_nombre_email_norm"].isin(SAO_COORDINADORES_AUDITADOS.keys())
            | base_coord["_coord_nombre_norm"].isin(SAO_COORDINADORES_NOMBRES.keys())
        ].copy()
        base_coord["coordinador"] = [
            nombre_coordinador_sao(nombre, correo)
            for nombre, correo in zip(base_coord["coordinador"], base_coord["correo_coordinador"])
        ]
        coordinadores_disponibilidad = sorted(
            c for c in base_coord["coordinador"].dropna().astype(str).str.strip().replace("", pd.NA).dropna().unique()
            if c != "Sin respuesta"
        )

    for r in regiones:
        if f"reg_{r}" not in st.session_state:
            st.session_state[f"reg_{r}"] = True

    for t in tecnicos:
        if f"tec_{t}" not in st.session_state:
            st.session_state[f"tec_{t}"] = True

    for m in MESES:
        if f"mes_{m}" not in st.session_state:
            st.session_state[f"mes_{m}"] = True

    for c in clientes_epa:
        if f"cli_{c}" not in st.session_state:
            st.session_state[f"cli_{c}"] = True

    for c in clientes_disponibilidad:
        if f"disp_cli_{c}" not in st.session_state:
            st.session_state[f"disp_cli_{c}"] = True

    for z in zonas_disponibilidad:
        if f"disp_zona_{z}" not in st.session_state:
            st.session_state[f"disp_zona_{z}"] = True

    for c in coordinadores_disponibilidad:
        if f"disp_coord_{c}" not in st.session_state:
            st.session_state[f"disp_coord_{c}"] = True

    for estado in DISPONIBILIDAD_ESTADOS:
        if f"disp_estado_{estado}" not in st.session_state:
            st.session_state[f"disp_estado_{estado}"] = True

    def boton_toggle_filtro(items, prefijo, key, texto_activar, texto_limpiar):
        todos_activos = bool(items) and all(
            st.session_state.get(f"{prefijo}_{item}", False)
            for item in items
        )
        etiqueta = texto_limpiar if todos_activos else texto_activar

        if st.button(etiqueta, use_container_width=True, key=key):
            kpi_en_curso = st.session_state.get("kpi_activo", KPI_INICIO)
            nuevo_estado = not todos_activos
            for item in items:
                st.session_state[f"{prefijo}_{item}"] = nuevo_estado
            st.session_state[f"{key}_empty_intent"] = not nuevo_estado
            if kpi_en_curso in KPI_OPCIONES:
                st.session_state["kpi_activo"] = kpi_en_curso
            st.rerun()

    def asegurar_filtro_con_seleccion(items, prefijo, key_toggle, permitir_vacio=True):
        if not items:
            return False
        hay_activo = any(st.session_state.get(f"{prefijo}_{item}", False) for item in items)
        if hay_activo or (permitir_vacio and st.session_state.get(f"{key_toggle}_empty_intent", False)):
            return False
        for item in items:
            st.session_state[f"{prefijo}_{item}"] = True
        st.session_state[f"{key_toggle}_empty_intent"] = False
        return True

    def inicializar_pills_filtro(items, key):
        items_lista = list(items)
        if st.session_state.get(f"{key}_force_all", False):
            st.session_state[key] = items_lista
            st.session_state[f"{key}_force_all"] = False

        seleccion = st.session_state.get(key, items_lista)
        if seleccion is None:
            seleccion = []
        if not isinstance(seleccion, list):
            seleccion = [seleccion]
        seleccion = [item for item in seleccion if item in items_lista]
        if not seleccion and not st.session_state.get(f"{key}_empty_intent", False):
            seleccion = items_lista
        if st.session_state.get(key) != seleccion:
            st.session_state[key] = seleccion
        return seleccion

    def boton_seleccionar_todo_pills(items, key, key_boton):
        items_lista = list(items)
        seleccion = list(st.session_state.get(key, items_lista))
        todos_activos = bool(items_lista) and set(seleccion) == set(items_lista)
        etiqueta = "Vaciar todo" if todos_activos else "Seleccionar todo"
        if st.button(etiqueta, use_container_width=True, key=key_boton):
            kpi_en_curso = st.session_state.get("kpi_activo", KPI_INICIO)
            st.session_state[key] = [] if todos_activos else items_lista
            st.session_state[f"{key}_empty_intent"] = todos_activos
            if kpi_en_curso in KPI_OPCIONES:
                st.session_state["kpi_activo"] = kpi_en_curso
            st.rerun()

    def proteger_pills_vacios(seleccion, key):
        if seleccion:
            st.session_state[f"{key}_empty_intent"] = False
            return list(seleccion)
        if st.session_state.get(f"{key}_empty_intent", False):
            return []
        kpi_en_curso = st.session_state.get("kpi_activo", KPI_INICIO)
        st.session_state[f"{key}_force_all"] = True
        if kpi_en_curso in KPI_OPCIONES:
            st.session_state["kpi_activo"] = kpi_en_curso
        st.rerun()

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    region = list(regiones)
    tecnico = list(tecnicos)
    meses_sel = list(MESES)
    clientes_sel = clientes_epa
    disp_clientes_sel = clientes_disponibilidad
    disp_coordinadores_sel = []
    disp_zonas_sel = zonas_disponibilidad
    disp_estados_sel = list(DISPONIBILIDAD_ESTADOS)

    if pagina_disp_rec_activa:
        inicializar_pills_filtro(clientes_disponibilidad, "disp_cli_pills")
        inicializar_pills_filtro(zonas_disponibilidad, "disp_zona_pills")
        inicializar_pills_filtro(MESES, "disp_mes_pills")
        if pagina_disponibilidad_activa:
            inicializar_pills_filtro(DISPONIBILIDAD_ESTADOS, "disp_estado_pills")

        disp_clientes_sel = []
        with st.expander("CLIENTE", expanded=False):
            st.markdown('<span class="filter-anchor filter-anchor-client"></span>', unsafe_allow_html=True)
            boton_seleccionar_todo_pills(
                clientes_disponibilidad,
                "disp_cli_pills",
                "toggle_clientes_disponibilidad_pills"
            )
            st.markdown(f'<div class="filter-mini-note">Mostrando {len(clientes_disponibilidad)} clientes con solicitudes o reclamos</div>', unsafe_allow_html=True)
            disp_clientes_sel = st.pills(
                "Clientes disponibilidad",
                clientes_disponibilidad,
                selection_mode="multi",
                key="disp_cli_pills",
                label_visibility="collapsed",
                width="stretch"
            )
            disp_clientes_sel = proteger_pills_vacios(disp_clientes_sel, "disp_cli_pills")

        disp_zonas_sel = []
        with st.expander("ZONAS", expanded=False):
            st.markdown('<span class="filter-anchor filter-anchor-region"></span>', unsafe_allow_html=True)
            boton_seleccionar_todo_pills(
                zonas_disponibilidad,
                "disp_zona_pills",
                "toggle_zonas_disponibilidad_pills"
            )
            st.markdown(f'<div class="filter-mini-note">Mostrando {len(zonas_disponibilidad)} zonas con solicitudes o reclamos</div>', unsafe_allow_html=True)
            disp_zonas_sel = st.pills(
                "Zonas disponibilidad",
                zonas_disponibilidad,
                selection_mode="multi",
                key="disp_zona_pills",
                label_visibility="collapsed",
                width="stretch"
            )
            disp_zonas_sel = proteger_pills_vacios(disp_zonas_sel, "disp_zona_pills")

        disp_coordinadores_sel = []

        if pagina_disponibilidad_activa:
            disp_estados_sel = []
            with st.expander("ESTADO", expanded=True):
                st.markdown('<span class="filter-anchor filter-anchor-status"></span>', unsafe_allow_html=True)
                boton_seleccionar_todo_pills(
                    DISPONIBILIDAD_ESTADOS,
                    "disp_estado_pills",
                    "toggle_estados_disponibilidad_pills"
                )
                st.markdown('<div class="filter-mini-note">Vista SLA de disponibilidad</div>', unsafe_allow_html=True)
                disp_estados_sel = st.pills(
                    "Estado disponibilidad",
                    DISPONIBILIDAD_ESTADOS,
                    selection_mode="multi",
                    key="disp_estado_pills",
                    label_visibility="collapsed",
                    width="stretch"
                )
                disp_estados_sel = proteger_pills_vacios(disp_estados_sel, "disp_estado_pills")

        meses_sel=[]
        with st.expander("PERIODO", expanded=False):
            st.markdown('<span class="filter-anchor filter-anchor-period"></span>', unsafe_allow_html=True)
            boton_seleccionar_todo_pills(
                MESES,
                "disp_mes_pills",
                "toggle_meses_disponibilidad_pills"
            )
            meses_sel = st.pills(
                "Periodo disponibilidad",
                MESES,
                selection_mode="multi",
                format_func=lambda m: MESES_CORTOS.get(m, m),
                key="disp_mes_pills",
                label_visibility="collapsed",
                width="stretch"
            )
            meses_sel = proteger_pills_vacios(meses_sel, "disp_mes_pills")

        st.session_state["_client_filter_visible"] = False

    else:
        region=[]
        with st.expander("REGIÓN", expanded=False):
            st.markdown('<span class="filter-anchor filter-anchor-region"></span>', unsafe_allow_html=True)
            boton_toggle_filtro(
                regiones,
                "reg",
                "toggle_regiones",
                "Seleccionar todo",
                "Vaciar todo"
            )
            st.markdown('<div class="filter-mini-note">Zonas incluidas en la vista</div>', unsafe_allow_html=True)

            for r in regiones:
                if st.checkbox(r, key=f"reg_{r}"):
                    region.append(r)

        if len(region) == 1 and "Estado" in df_filtros_base.columns and "Recurso" in df_filtros_base.columns:
            tecnicos_filtro = sorted(
                t for t in df_filtros_base.loc[df_filtros_base["Estado"].isin(region), "Recurso"].dropna().unique()
                if not es_tecnico_demo(t)
            )
            tecnico_contexto = f"de {region[0]}"
        else:
            tecnicos_filtro = tecnicos
            tecnico_contexto = "activos"

        tecnico=[]
        with st.expander("TÉCNICO", expanded=False):
            st.markdown('<span class="filter-anchor filter-anchor-tech"></span>', unsafe_allow_html=True)

            boton_toggle_filtro(
                tecnicos_filtro,
                "tec",
                "toggle_tecnicos",
                "Seleccionar todo",
                "Vaciar todo"
            )
            st.markdown(f'<div class="filter-mini-note">Mostrando {len(tecnicos_filtro)} técnicos {tecnico_contexto}</div>', unsafe_allow_html=True)

            for t in tecnicos_filtro:
                st.checkbox(t, key=f"tec_{t}")

            tecnico = [t for t in tecnicos_filtro if st.session_state.get(f"tec_{t}", False)]

        meses_sel=[]
        with st.expander("PERIODO", expanded=False):
            st.markdown('<span class="filter-anchor filter-anchor-period"></span>', unsafe_allow_html=True)
            boton_toggle_filtro(
                MESES,
                "mes",
                "toggle_meses",
                "Seleccionar todo",
                "Vaciar todo"
            )
            st.markdown('<div class="filter-mini-note">Periodo operacional</div>', unsafe_allow_html=True)

            c1,c2=st.columns(2)
            for i,m in enumerate(MESES):
                with (c1 if i<6 else c2):
                    st.checkbox(MESES_CORTOS.get(m, m), key=f"mes_{m}")
                    if st.session_state[f"mes_{m}"]:
                        meses_sel.append(m)

        clientes_sel = clientes_epa
        cliente_filtro_saliendo = st.session_state.get("_client_filter_visible", False) and not pagina_epa_activa
        if pagina_epa_activa:
            clientes_sel = []
            with st.expander("CLIENTE", expanded=False):
                st.markdown('<span class="filter-anchor filter-anchor-client"></span>', unsafe_allow_html=True)

                boton_toggle_filtro(
                    clientes_epa,
                    "cli",
                    "toggle_clientes_epa",
                    "Seleccionar todo",
                    "Vaciar todo"
                )
                st.markdown(f'<div class="filter-mini-note">Mostrando {len(clientes_epa)} clientes EPA</div>', unsafe_allow_html=True)

                for c in clientes_epa:
                    st.checkbox(c, key=f"cli_{c}")

                clientes_sel = [c for c in clientes_epa if st.session_state.get(f"cli_{c}", False)]
        elif cliente_filtro_saliendo:
            st.markdown('<div class="client-filter-exit-shell"><span>CLIENTE</span></div>', unsafe_allow_html=True)
        st.session_state["_client_filter_visible"] = pagina_epa_activa

    st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)

# =========================================================
# FILTROS
# =========================================================

df_f = df.copy()

if "Estado" in df_f.columns:
    df_f = df_f.loc[df_f["Estado"].isin(region)]

    if "Recurso" in df_f.columns and not df_f.empty:
        tecnico_demo_mask = df_f["Recurso"].map(es_tecnico_demo).fillna(False).astype(bool)
        df_f = df_f.loc[~tecnico_demo_mask]
        if tecnico:
            df_f = df_f.loc[df_f["Recurso"].isin(tecnico)]
        else:
            df_f = df_f.iloc[0:0]

if "Mes" in df_f.columns:
    df_f = df_f.loc[df_f["Mes"].isin(meses_sel)]

filtros_export = {
    "regiones": region,
    "tecnicos": tecnico,
    "meses": meses_sel,
    "clientes": disp_clientes_sel if pagina_disp_rec_activa else clientes_sel,
    "zonas": disp_zonas_sel,
    "estados": disp_estados_sel if pagina_disponibilidad_activa else [],
    "servicio_tecnico": SERVICIOS_ACTIVOS,
}

df_epa_f = df_epa.copy()

if not df_epa_f.empty:
    for col in ["respondida", "q1", "q2", "q3", "q4", "q5", "promedio"]:
        if col in df_epa_f.columns:
            df_epa_f[col] = pd.to_numeric(df_epa_f[col], errors="coerce")

    if region and len(region) < len(regiones) and "region" in df_epa_f.columns:
        regiones_disponibles_epa = set(df_epa_f["region"].dropna().astype(str))
        regiones_seleccionadas = set(map(str, region))
        if regiones_disponibles_epa & regiones_seleccionadas:
            df_epa_f = df_epa_f[df_epa_f["region"].astype(str).isin(regiones_seleccionadas)]

    if tecnico and "tecnico" in df_epa_f.columns:
        tecnicos_disponibles_epa = set(df_epa_f["tecnico"].dropna().astype(str))
        tecnicos_seleccionados = set(map(str, tecnico))
        if tecnicos_disponibles_epa & tecnicos_seleccionados:
            df_epa_f = df_epa_f[df_epa_f["tecnico"].astype(str).isin(tecnicos_seleccionados)]

    if pagina_epa_activa and clientes_epa and "cliente" in df_epa_f.columns:
        clientes_seleccionados = set(map(str, clientes_sel))
        df_epa_f = df_epa_f[df_epa_f["cliente"].fillna("").astype(str).isin(clientes_seleccionados)]

    fecha_atencion_epa = pd.to_datetime(df_epa_f.get("fecha_atencion"), errors="coerce")
    fecha_respuesta_epa = pd.to_datetime(df_epa_f.get("respuesta_creada"), errors="coerce", utc=True)
    if hasattr(fecha_respuesta_epa, "dt"):
        fecha_respuesta_epa = fecha_respuesta_epa.dt.tz_localize(None)

    df_epa_f["_fecha_epa"] = fecha_atencion_epa.fillna(fecha_respuesta_epa)

    if meses_sel and len(meses_sel) < len(MESES):
        mes_epa = df_epa_f["_fecha_epa"].dt.month.map(lambda mes: MESES[mes - 1] if pd.notna(mes) else None)
        df_epa_f = df_epa_f[mes_epa.isin(meses_sel) | df_epa_f["_fecha_epa"].isna()]

df_epa_respondidas = df_epa_f[df_epa_f.get("respondida", pd.Series(dtype=float)).fillna(0).astype(int).eq(1)].copy()
epa_total_atenciones = len(df_epa_f)
epa_total_respuestas = len(df_epa_respondidas)
epa_pendientes = max(epa_total_atenciones - epa_total_respuestas, 0)
epa_promedio = float(df_epa_respondidas["promedio"].dropna().mean()) if epa_total_respuestas and "promedio" in df_epa_respondidas.columns else 0
epa_satisfechas = int(df_epa_respondidas["promedio"].ge(4).sum()) if epa_total_respuestas and "promedio" in df_epa_respondidas.columns else 0
epa_satisfaccion = round(epa_satisfechas / max(epa_total_respuestas, 1) * 100, 1)
epa_recomendacion = float(df_epa_respondidas["q5"].dropna().mean()) if epa_total_respuestas and "q5" in df_epa_respondidas.columns else 0
df_epa_export = preparar_export_epa(df_epa_f)

df_disp_f = df_disponibilidad.copy()
if not df_disp_f.empty:
    if clientes_disponibilidad and "cliente" in df_disp_f.columns:
        df_disp_f = df_disp_f.loc[df_disp_f["cliente"].astype(str).isin(set(map(str, disp_clientes_sel)))]

    if zonas_disponibilidad and "region" in df_disp_f.columns:
        df_disp_f = df_disp_f.loc[df_disp_f["region"].astype(str).isin(set(map(str, disp_zonas_sel)))]

    if meses_sel:
        mes_disp_f = serie_mes_operacional(df_disp_f, "fecha_solicitud", "mes")
        df_disp_f = df_disp_f.loc[mes_disp_f.isin(set(map(str, meses_sel)))]
    else:
        df_disp_f = df_disp_f.iloc[0:0]

    estados_sla = set(disp_estados_sel) & {"Cumple", "No cumple"}
    if estados_sla and "cumple_kpi" in df_disp_f.columns:
        cumple_mask = df_disp_f["cumple_kpi"].fillna(False).astype(bool)
        if "estado_kpi" in df_disp_f.columns:
            cumple_mask = cumple_mask | df_disp_f["estado_kpi"].astype(str).str.strip().str.lower().eq("cumple")
        estado_mask = pd.Series(False, index=df_disp_f.index)
        if "Cumple" in estados_sla:
            estado_mask = estado_mask | cumple_mask
        if "No cumple" in estados_sla:
            estado_mask = estado_mask | ~cumple_mask
        df_disp_f = df_disp_f.loc[estado_mask]
    elif pagina_disponibilidad_activa:
        df_disp_f = df_disp_f.iloc[0:0]

df_reclamos_f = df_reclamos.copy()
if not df_reclamos_f.empty:
    if clientes_disponibilidad and "cliente" in df_reclamos_f.columns:
        df_reclamos_f = df_reclamos_f.loc[df_reclamos_f["cliente"].astype(str).isin(set(map(str, disp_clientes_sel)))]

    if zonas_disponibilidad and "region" in df_reclamos_f.columns:
        df_reclamos_f = df_reclamos_f.loc[df_reclamos_f["region"].astype(str).isin(set(map(str, disp_zonas_sel)))]

    if meses_sel:
        mes_reclamos_f = serie_mes_operacional(df_reclamos_f, "fecha_reclamo", "mes")
        df_reclamos_f = df_reclamos_f.loc[mes_reclamos_f.isin(set(map(str, meses_sel)))]
    else:
        df_reclamos_f = df_reclamos_f.iloc[0:0]

    if pagina_disponibilidad_activa and "Reclamo" not in set(disp_estados_sel):
        df_reclamos_f = df_reclamos_f.iloc[0:0]

df_atenciones_reclamos_f = filtrar_atenciones_reclamos_panel(
    df_f,
    disp_clientes_sel if pagina_disp_rec_activa else [],
    clientes_disponibilidad if pagina_disp_rec_activa else [],
    disp_zonas_sel if pagina_disp_rec_activa else [],
    zonas_disponibilidad if pagina_disp_rec_activa else [],
)

disp_total = len(df_disp_f)
disp_cumple = int(df_disp_f["cumple_kpi"].fillna(False).astype(bool).sum()) if disp_total and "cumple_kpi" in df_disp_f.columns else 0
disp_no_cumple = max(disp_total - disp_cumple, 0)
disp_sin_respuesta = int(df_disp_f["fecha_respuesta"].isna().sum()) if disp_total and "fecha_respuesta" in df_disp_f.columns else 0
disp_pct = round(disp_cumple / max(disp_total, 1) * 100, 1)
disp_promedio_min = float(df_disp_f["minutos_habiles"].dropna().mean()) if disp_total and "minutos_habiles" in df_disp_f.columns else 0
reiteraciones_operacionales_serie = calcular_reiteraciones_total_operacional(df_disp_f) if disp_total else pd.Series(dtype="float64")
disp_reiteraciones = int(reiteraciones_operacionales_serie.sum()) if disp_total else 0
disp_tickets_reiterados = int(df_disp_f.loc[reiteraciones_operacionales_serie.gt(0), "numero_ticket"].replace("", pd.NA).dropna().nunique()) if disp_total and "numero_ticket" in df_disp_f.columns else 0
disp_solicitudes_reiteradas = int(reiteraciones_operacionales_serie.gt(0).sum()) if disp_total else 0
disp_intervenciones_servicio = int(pd.to_numeric(df_disp_f["intervenciones_supervisor_servicio_tecnico"], errors="coerce").fillna(0).sum()) if disp_total and "intervenciones_supervisor_servicio_tecnico" in df_disp_f.columns else 0
disp_intervenciones_terreno = disp_intervenciones_servicio
disp_reit_cecom_operador = int(pd.to_numeric(df_disp_f["reiteraciones_cecom_operador"], errors="coerce").fillna(0).sum()) if disp_total and "reiteraciones_cecom_operador" in df_disp_f.columns else 0
disp_reit_supervisor_cecom = int(pd.to_numeric(df_disp_f["reiteraciones_supervisor_cecom"], errors="coerce").fillna(0).sum()) if disp_total and "reiteraciones_supervisor_cecom" in df_disp_f.columns else 0
disp_reit_cecom_total = disp_reit_cecom_operador + disp_reit_supervisor_cecom
disp_casos_multi_solicitud = int(df_disp_f.loc[pd.to_numeric(df_disp_f["total_solicitudes_caso"], errors="coerce").fillna(0).gt(1), "ticket_principal"].replace("", pd.NA).dropna().nunique()) if disp_total and {"total_solicitudes_caso", "ticket_principal"}.issubset(df_disp_f.columns) else 0
disp_brecha_meta = round(disp_pct - DISPONIBILIDAD_META_PCT, 1)
df_disp_export = preparar_export_disponibilidad(df_disp_f)
reclamos_total = len(df_reclamos_f)
reclamos_reforzamientos = int(serie_bool_panel(df_reclamos_f["reforzamiento"]).sum()) if reclamos_total and "reforzamiento" in df_reclamos_f.columns else 0
reclamos_reclamos_duros = max(reclamos_total - reclamos_reforzamientos, 0)
reclamos_alta = int(df_reclamos_f["severidad_reclamo"].astype(str).str.upper().eq("ALTA").sum()) if reclamos_total and "severidad_reclamo" in df_reclamos_f.columns else 0
reclamos_tickets = int(
    df_reclamos_f["ticket_principal"]
    .fillna("")
    .astype(str)
    .map(normalizar_ticket_panel)
    .replace("", pd.NA)
    .dropna()
    .nunique()
) if reclamos_total and "ticket_principal" in df_reclamos_f.columns else 0
reclamos_clientes = int(df_reclamos_f["cliente"].replace("", pd.NA).dropna().nunique()) if reclamos_total and "cliente" in df_reclamos_f.columns else 0
reclamos_motivo_top = df_reclamos_f["familia_reclamo"].replace("", pd.NA).dropna().mode().iloc[0] if reclamos_total and "familia_reclamo" in df_reclamos_f.columns and not df_reclamos_f["familia_reclamo"].replace("", pd.NA).dropna().empty else "Sin reclamos"
reclamos_motivo_top_count = int(df_reclamos_f["familia_reclamo"].astype(str).eq(str(reclamos_motivo_top)).sum()) if reclamos_total and "familia_reclamo" in df_reclamos_f.columns else 0
reclamos_cliente_counts = (
    df_reclamos_f["cliente"].fillna("").astype(str).str.strip().replace("", pd.NA).dropna().value_counts()
    if reclamos_total and "cliente" in df_reclamos_f.columns
    else pd.Series(dtype="int64")
)
reclamos_cliente_top = str(reclamos_cliente_counts.index[0]) if not reclamos_cliente_counts.empty else "Sin cliente"
reclamos_cliente_top_count = int(reclamos_cliente_counts.iloc[0]) if not reclamos_cliente_counts.empty else 0
reclamos_proveedor_reforzado_counts = (
    df_reclamos_f.loc[
        serie_bool_panel(df_reclamos_f["reforzamiento"]) if "reforzamiento" in df_reclamos_f.columns else pd.Series(False, index=df_reclamos_f.index),
        "proveedor_reforzado",
    ].fillna("").astype(str).str.strip().replace("", pd.NA).dropna().value_counts()
    if reclamos_reforzamientos and "proveedor_reforzado" in df_reclamos_f.columns
    else pd.Series(dtype="int64")
)
reclamos_proveedor_reforzado_top = str(reclamos_proveedor_reforzado_counts.index[0]) if not reclamos_proveedor_reforzado_counts.empty else "Sin reforzar"
reclamos_proveedor_reforzado_top_count = int(reclamos_proveedor_reforzado_counts.iloc[0]) if not reclamos_proveedor_reforzado_counts.empty else 0
if reclamos_total and reclamos_cliente_top_count and {"cliente", "ticket_principal"}.issubset(df_reclamos_f.columns):
    mask_cliente_foco = df_reclamos_f["cliente"].fillna("").astype(str).str.strip().eq(reclamos_cliente_top)
    reclamos_cliente_top_tickets = int(
        df_reclamos_f.loc[mask_cliente_foco, "ticket_principal"]
        .fillna("")
        .astype(str)
        .map(normalizar_ticket_panel)
        .replace("", pd.NA)
        .dropna()
        .nunique()
    )
else:
    reclamos_cliente_top_tickets = 0
atenciones_asignadas_reclamos = len(df_atenciones_reclamos_f)
reclamos_ratio_incumplimiento = round(reclamos_total / max(atenciones_asignadas_reclamos, 1) * 100, 1) if atenciones_asignadas_reclamos else 0
reclamos_cumplimiento_ajustado = round(max(0, 100 - reclamos_ratio_incumplimiento), 1)
reclamos_brecha_meta = round(reclamos_cumplimiento_ajustado - RECLAMOS_META_CUMPLIMIENTO_PCT, 1)
df_reclamos_export = preparar_export_reclamos(df_reclamos_f)

df_uso_f = df_uso_herramienta.copy()
if not df_uso_f.empty:
    if region and "region_atendida" in df_uso_f.columns:
        df_uso_f = df_uso_f.loc[df_uso_f["region_atendida"].astype(str).isin(set(map(str, region)))]

    if tecnico and "tecnico" in df_uso_f.columns:
        df_uso_f = df_uso_f.loc[df_uso_f["tecnico"].astype(str).isin(set(map(str, tecnico)))]
    elif pagina_uso_herramienta_activa:
        df_uso_f = df_uso_f.iloc[0:0]

    fecha_uso = pd.to_datetime(df_uso_f.get("fecha_atencion"), dayfirst=True, errors="coerce")
    df_uso_f["_fecha_uso"] = fecha_uso
    if meses_sel:
        mes_uso = fecha_uso.dt.month.map(lambda mes: MESES[int(mes) - 1] if pd.notna(mes) and 1 <= int(mes) <= 12 else None)
        df_uso_f = df_uso_f.loc[mes_uso.isin(set(map(str, meses_sel))) | fecha_uso.isna()]
    else:
        df_uso_f = df_uso_f.iloc[0:0]

uso_total = len(df_uso_f)
uso_promedio = float(df_uso_f["puntaje_total"].dropna().mean()) if uso_total and "puntaje_total" in df_uso_f.columns else 0
uso_excelentes = int(df_uso_f["estado_calidad"].astype(str).eq("Excelente").sum()) if uso_total and "estado_calidad" in df_uso_f.columns else 0
uso_buenas = int(df_uso_f["estado_calidad"].astype(str).eq("Bueno").sum()) if uso_total and "estado_calidad" in df_uso_f.columns else 0
uso_regulares = int(df_uso_f["estado_calidad"].astype(str).eq("Regular").sum()) if uso_total and "estado_calidad" in df_uso_f.columns else 0
uso_criticas = int(df_uso_f["estado_calidad"].astype(str).eq("Critico").sum()) if uso_total and "estado_calidad" in df_uso_f.columns else 0
uso_ok = uso_excelentes + uso_buenas
uso_pct_ok = round(uso_ok / max(uso_total, 1) * 100, 1) if uso_total else 0
uso_retiros_incompletos = int(
    df_uso_f["hallazgos"].fillna("").astype(str).str.contains("Retiro sin declarar", case=False, na=False).sum()
) if uso_total and "hallazgos" in df_uso_f.columns else 0
uso_cge_sin_activo = int(
    (
        df_uso_f["cliente_cge"].fillna("").astype(str).str.upper().eq("SI")
        & ~df_uso_f["activo_fijo_detectado"].fillna("").astype(str).str.upper().eq("SI")
    ).sum()
) if uso_total and {"cliente_cge", "activo_fijo_detectado"}.issubset(df_uso_f.columns) else 0
uso_tecnicos = int(df_uso_f["tecnico"].replace("", pd.NA).dropna().nunique()) if uso_total and "tecnico" in df_uso_f.columns else 0
uso_brecha_meta = round(uso_promedio - USO_HERRAMIENTA_META_PCT, 1) if uso_total else 0
df_uso_export = preparar_export_uso_herramienta(df_uso_f)


def resumen_comparativo_disponibilidad_proveedor(df_base):
    if not SERVICIO_COMPARATIVO or df_base is None or df_base.empty or "servicio_tecnico" not in df_base.columns:
        return ""
    base = df_base.copy()
    base["_cumple"] = base["cumple_kpi"].fillna(False).astype(bool) if "cumple_kpi" in base.columns else False
    base["_sin_respuesta"] = base["fecha_respuesta"].isna() if "fecha_respuesta" in base.columns else False
    base["_reiteraciones"] = calcular_reiteraciones_total_operacional(base)
    resumen = (
        base.groupby("servicio_tecnico", dropna=False)
        .agg(
            solicitudes=("_cumple", "size"),
            cumple=("_cumple", "sum"),
            sin_respuesta=("_sin_respuesta", "sum"),
            reiteraciones=("_reiteraciones", "sum"),
        )
        .reset_index()
    )
    if resumen.empty:
        return ""
    resumen["pct"] = (resumen["cumple"] / resumen["solicitudes"].clip(lower=1) * 100).round(1)
    resumen["fuera"] = resumen["solicitudes"] - resumen["cumple"]
    resumen = resumen.sort_values("pct", ascending=True)
    return "; ".join(
        f"{row.servicio_tecnico}: {row.pct:.1f}% ({int(row.fuera)} fuera SLA, {int(row.sin_respuesta)} sin respuesta, {int(row.reiteraciones)} reiteraciones)"
        for row in resumen.itertuples(index=False)
    )


def resumen_comparativo_reclamos_proveedor(df_rec_base, df_atenciones_base):
    if not SERVICIO_COMPARATIVO:
        return ""
    if df_atenciones_base is None or df_atenciones_base.empty or "servicio_tecnico" not in df_atenciones_base.columns:
        return ""

    atenciones = (
        df_atenciones_base.copy()
        .assign(servicio_tecnico=lambda tmp: tmp["servicio_tecnico"].fillna("Sin dato").astype(str).str.strip().replace({"": "Sin dato"}))
        .groupby("servicio_tecnico", dropna=False)
        .size()
        .reset_index(name="atenciones")
    )
    if df_rec_base is not None and not df_rec_base.empty and "servicio_tecnico" in df_rec_base.columns:
        rec = df_rec_base.copy()
        rec["servicio_tecnico"] = rec["servicio_tecnico"].fillna("Sin dato").astype(str).str.strip().replace({"": "Sin dato"})
        rec["_alta"] = rec["severidad_reclamo"].astype(str).str.upper().eq("ALTA") if "severidad_reclamo" in rec.columns else False
        rec["_reforzamiento"] = serie_bool_panel(rec["reforzamiento"]) if "reforzamiento" in rec.columns else False
        reclamos = (
            rec.groupby("servicio_tecnico", dropna=False)
            .agg(reclamos=("servicio_tecnico", "size"), alta=("_alta", "sum"), reforzamientos=("_reforzamiento", "sum"))
            .reset_index()
        )
    else:
        reclamos = pd.DataFrame(columns=["servicio_tecnico", "reclamos", "alta", "reforzamientos"])

    resumen = atenciones.merge(reclamos, on="servicio_tecnico", how="left")
    resumen[["reclamos", "alta", "reforzamientos"]] = resumen[["reclamos", "alta", "reforzamientos"]].fillna(0)
    resumen["ratio"] = (resumen["reclamos"] / resumen["atenciones"].replace(0, pd.NA) * 100).fillna(0).round(1)
    resumen["cumplimiento"] = (100 - resumen["ratio"]).clip(lower=0).round(1)
    resumen = resumen.sort_values("cumplimiento", ascending=True)
    return "; ".join(
        f"{row.servicio_tecnico}: {int(row.reclamos)} señales ({int(row.reforzamientos)} ref.)/{int(row.atenciones)} atenciones, {row.ratio:.1f}% incumplimiento, {row.cumplimiento:.1f}% cumplimiento"
        for row in resumen.itertuples(index=False)
    )


def resumen_comparativo_uso_herramienta_proveedor(df_uso_base):
    if not SERVICIO_COMPARATIVO or df_uso_base is None or df_uso_base.empty or "servicio_tecnico" not in df_uso_base.columns:
        return ""
    base = df_uso_base.copy()
    base["servicio_tecnico"] = base["servicio_tecnico"].fillna("Sin dato").astype(str).str.strip().replace({"": "Sin dato"})
    base["_ok"] = base["estado_calidad"].astype(str).isin(["Excelente", "Bueno"]) if "estado_calidad" in base.columns else False
    resumen = (
        base.groupby("servicio_tecnico", dropna=False)
        .agg(
            ots=("servicio_tecnico", "size"),
            nota=("puntaje_total", "mean"),
            ok=("_ok", "sum"),
        )
        .reset_index()
    )
    if resumen.empty:
        return ""
    resumen["nota"] = resumen["nota"].fillna(0).round(1)
    resumen["pct_ok"] = (resumen["ok"] / resumen["ots"].clip(lower=1) * 100).round(1)
    resumen = resumen.sort_values(["nota", "pct_ok"], ascending=[True, True])
    return "; ".join(
        f"{row.servicio_tecnico}: nota {row.nota:.1f}, {row.pct_ok:.1f}% excelente/bueno en {int(row.ots)} OT"
        for row in resumen.itertuples(index=False)
    )


comparativo_disponibilidad_proveedor = resumen_comparativo_disponibilidad_proveedor(df_disp_f)
comparativo_reclamos_proveedor = resumen_comparativo_reclamos_proveedor(df_reclamos_f, df_atenciones_reclamos_f)
comparativo_uso_herramienta_proveedor = resumen_comparativo_uso_herramienta_proveedor(df_uso_f)

# =========================================================
# CALCULO CUMPLE: INICIO <= VENTANA + 15 MIN
# =========================================================

def hora_operativa_a_timedelta(serie):
    texto = serie.astype(str).str.strip()
    texto = texto.str.replace(",", ".", regex=False)

    hora_extraida = texto.str.extract(r"(\d{1,2}:\d{2}(?::\d{2})?)", expand=False)
    texto = hora_extraida.fillna(texto)
    texto = texto.where(texto.str.count(":").ge(2), texto + ":00")

    tiempo = pd.to_timedelta(texto, errors="coerce")

    numero = pd.to_numeric(serie, errors="coerce")
    tiempo_excel = pd.Series(pd.NaT, index=serie.index, dtype="timedelta64[ns]")
    numero_valido = numero.between(0, 1)
    if numero_valido.any():
        tiempo_excel.loc[numero_valido] = pd.to_timedelta(numero.loc[numero_valido], unit="D")

    return tiempo.fillna(tiempo_excel)

if "Ventana de entrega" in df_f.columns and "Inicio" in df_f.columns:

    ventana_td = hora_operativa_a_timedelta(df_f["Ventana de entrega"])
    inicio_td = hora_operativa_a_timedelta(df_f["Inicio"])

    # Cumple si inicia antes de la ventana o hasta 15 minutos despues.
    df_f["Dif"] = (inicio_td - ventana_td).dt.total_seconds() / 60
    df_f["Cumple"] = ventana_td.notna() & inicio_td.notna() & df_f["Dif"].le(15)

else:

    df_f["Cumple"] = False

# =========================================================
# KPIS
# =========================================================


def texto_normalizado(serie):
    return serie.fillna("").astype(str).map(
        lambda texto: unicodedata.normalize("NFKD", texto)
        .encode("ascii", "ignore")
        .decode("ascii")
        .upper()
    )


def motivo_no_realizado_estandar(valor):
    if pd.isna(valor):
        return "Otros"

    texto = unicodedata.normalize("NFKD", str(valor).strip())
    texto = texto.encode("ascii", "ignore").decode("ascii").upper()
    texto = "".join(caracter if caracter.isalnum() or caracter.isspace() else " " for caracter in texto)
    texto = " ".join(texto.split())

    if not texto or texto in {"NAN", "NONE", "NULL", "SIN INFORMACION"}:
        return "Otros"

    tokens = set(texto.split())

    if "USUARIO" in tokens and any(palabra.startswith("COORDIN") for palabra in tokens):
        return "Usuario coordina"

    if "USUARIO" in tokens and "ENCUENTRA" in tokens and ("NO" in tokens or "UBICA" in tokens):
        return "Usuario no se encuentra"

    if "USUARIO" in tokens and any(palabra.startswith("RECHAZ") for palabra in tokens):
        return "Usuario rechaza visita"

    if "SUCURSAL" in tokens and any(palabra.startswith("PROBLEMA") for palabra in tokens):
        return "Problema de sucursal"

    if "FUERZA" in tokens and "MAYOR" in tokens:
        return "Fuerza mayor"

    return texto.lower().capitalize()


def consolidar_motivos_no_realizado(serie):
    return serie.map(motivo_no_realizado_estandar).value_counts()


TICKET_ID_COLS = ["ID Externo", "ID externo", "ID Ticket", "Ticket", "Ticket ID", "Numero Ticket", "Número Ticket"]


def preparar_visitas_ticket(df_base, estado_col_base=None):
    id_col = next((c for c in TICKET_ID_COLS if c in df_base.columns), None)
    if not id_col:
        return None

    columnas = [id_col]
    if estado_col_base and estado_col_base in df_base.columns:
        columnas.append(estado_col_base)

    base = df_base[columnas].copy()
    base["_idx_original"] = df_base.index
    base["_id_ticket_original"] = base[id_col].fillna("").astype(str).str.strip()
    base["_id_ticket_orden"] = base["_id_ticket_original"]

    sin_id = base["_id_ticket_orden"].eq("")
    base.loc[sin_id, "_id_ticket_orden"] = "__SIN_ID__" + base.loc[sin_id, "_idx_original"].astype(str)

    if "Fecha de Agendamiento" in df_base.columns:
        base["_fecha_orden"] = pd.to_datetime(df_base["Fecha de Agendamiento"], dayfirst=True, errors="coerce")
    else:
        base["_fecha_orden"] = pd.NaT

    if "Inicio" in df_base.columns:
        hora_texto = df_base["Inicio"].astype(str).str.strip()
        hora_texto = hora_texto.where(hora_texto.str.count(":").ge(2), hora_texto + ":00")
        base["_hora_orden"] = pd.to_timedelta(hora_texto, errors="coerce")
    else:
        base["_hora_orden"] = pd.NaT

    base = base.sort_values(["_id_ticket_orden", "_fecha_orden", "_hora_orden", "_idx_original"])
    base["_numero_visita_ticket"] = base.groupby("_id_ticket_orden").cumcount().add(1)
    return base


def numero_visita_ticket(df_base):
    numero_visita = pd.Series(1, index=df_base.index, dtype="int64")
    base = preparar_visitas_ticket(df_base)

    if base is None:
        return numero_visita

    numero_visita.loc[base["_idx_original"]] = base["_numero_visita_ticket"].astype("int64").to_numpy()
    return numero_visita


def detectar_revisitas(df_base):
    estado_col_base = next(
        (c for c in ["Estado de actividad", "Estado Actividad"] if c in df_base.columns),
        None
    )

    base = preparar_visitas_ticket(df_base, estado_col_base)

    if base is not None and estado_col_base:
        base["_estado_norm"] = texto_normalizado(base[estado_col_base])
        base["_no_realizado"] = base["_estado_norm"].str.contains("NO REALIZAD|NO FINALIZAD", na=False)
        no_realizado_previo = (
            base.groupby("_id_ticket_orden")["_no_realizado"]
                .cummax()
                .groupby(base["_id_ticket_orden"])
                .shift(fill_value=False)
        )

        revisita_ordenada = (
            base["_numero_visita_ticket"].ge(3)
            & no_realizado_previo
            & base["_id_ticket_original"].ne("")
        )
        revisita_mask = pd.Series(False, index=df_base.index)
        revisita_mask.loc[base["_idx_original"]] = revisita_ordenada.to_numpy()
        return revisita_mask

    revisita_cols = [c for c in df_base.columns if "revis" in str(c).lower()]

    if revisita_cols:
        serie = df_base[revisita_cols[0]]
        if pd.api.types.is_numeric_dtype(serie):
            valores = pd.to_numeric(serie, errors="coerce").fillna(0)
            return valores > 0

        texto = texto_normalizado(serie)
        return texto.str.contains(r"\b(SI|TRUE|VERDADERO|1)\b|REVIS", regex=True, na=False)

    texto_cols = [
        c for c in [
            "Tipo de actividad", "Tipo Actividad", "Actividad", "Trabajo",
            "Resultado", "Acción Realizada", "Accion Realizada",
            "Observación", "Observacion"
        ]
        if c in df_base.columns
    ]

    revisita_mask = pd.Series(False, index=df_base.index)
    for col in texto_cols:
        texto = texto_normalizado(df_base[col])
        revisita_mask |= texto.str.contains(r"REVIS|TERCERA VISITA|3RA VISITA|3ERA VISITA|VISITA 3", regex=True, na=False)

    return revisita_mask


def contar_revisitas(df_base):
    return int(detectar_revisitas(df_base).sum())


total = len(df_f)

cumple = int(df_f["Cumple"].sum())

pct = round(
    (cumple / total) * 100,
    2
) if total else 0

estado_col = next(
    (c for c in ["Estado de actividad", "Estado Actividad", "Estado"] if c in df_f.columns),
    None
)

estado = df_f[estado_col].astype(str).str.upper() if estado_col else pd.Series(["FINAL"] * len(df_f), index=df_f.index)
estado_final_mask = estado.str.contains("FINAL", na=False)
numero_visita_global = numero_visita_ticket(df)
numero_visita = numero_visita_global.reindex(df_f.index).fillna(1).astype("int64")
revisita_mask_global = detectar_revisitas(df)
revisita_mask = revisita_mask_global.reindex(df_f.index).fillna(False).astype(bool)

finalizadas = int(estado_final_mask.sum())
no_finalizadas = total - finalizadas
total_atenciones = total
pct_fin = round(finalizadas / max(total_atenciones, 1) * 100, 1)
pct_no_fin = round(no_finalizadas / max(total_atenciones, 1) * 100, 1)
revisitas = int(revisita_mask.sum())
pct_revisitas = round(revisitas / max(total_atenciones, 1) * 100, 1)
finalizadas_primera_visita = int((estado_final_mask & numero_visita.eq(1)).sum())
pct_primera_visita = round(finalizadas_primera_visita / max(total_atenciones, 1) * 100, 1)

comparativo_inicio_proveedor = ""
if SERVICIO_COMPARATIVO and total_atenciones and "servicio_tecnico" in df_f.columns:
    base_inicio_comp = df_f.copy()
    base_inicio_comp["_cumple_inicio"] = df_f["Cumple"].fillna(False).astype(bool)
    base_inicio_comp["_revisita"] = revisita_mask.reindex(df_f.index).fillna(False).astype(bool)
    base_inicio_comp["_finalizada_primera"] = (estado_final_mask & numero_visita.eq(1)).reindex(df_f.index).fillna(False).astype(bool)
    resumen_inicio_comp = (
        base_inicio_comp.assign(servicio_tecnico=lambda tmp: tmp["servicio_tecnico"].fillna("Sin ST").astype(str).str.strip().replace({"": "Sin ST"}))
        .groupby("servicio_tecnico", dropna=False)
        .agg(
            atenciones=("servicio_tecnico", "size"),
            cumple=("_cumple_inicio", "sum"),
            primera=("_finalizada_primera", "sum"),
            revisitas=("_revisita", "sum"),
        )
        .reset_index()
    )
    resumen_inicio_comp["pct"] = (resumen_inicio_comp["cumple"] / resumen_inicio_comp["atenciones"].clip(lower=1) * 100).round(1)
    resumen_inicio_comp["pct_revisitas"] = (resumen_inicio_comp["revisitas"] / resumen_inicio_comp["atenciones"].clip(lower=1) * 100).round(1)
    resumen_inicio_comp = resumen_inicio_comp.sort_values("pct", ascending=True)
    comparativo_inicio_proveedor = "; ".join(
        f"{row.servicio_tecnico}: {row.pct:.1f}% inicio, {int(row.revisitas)} revisitas ({row.pct_revisitas:.1f}%)"
        for row in resumen_inicio_comp.itertuples(index=False)
    )

df_export = df_f.copy()
df_export["Numero visita ticket"] = numero_visita
df_export["Estado final detectado"] = estado_final_mask.map({True: "Si", False: "No"})
df_export["Revisita detectada"] = revisita_mask.map({True: "Si", False: "No"})

df_revisitas_export = df_f.loc[revisita_mask].copy()
df_revisitas_export["Numero visita ticket"] = numero_visita.reindex(df_revisitas_export.index)
df_revisitas_export["Estado final detectado"] = estado_final_mask.reindex(df_revisitas_export.index).map({True: "Si", False: "No"})
df_revisitas_export["Revisita detectada"] = revisita_mask.reindex(df_revisitas_export.index).map({True: "Si", False: "No"})
df_revisitas_export["Regla revisita"] = "Visita 3 o superior con No Realizado previo"

with st.sidebar:
    if pagina_disponibilidad_activa and not disponibilidad_no_aplica_servicio:
        render_boton_exportar_datos(df_disp_export, filtros_export, modo="disponibilidad")
    elif pagina_reclamos_activa and not reclamos_no_aplica_servicio:
        render_boton_exportar_datos(df_reclamos_export, filtros_export, modo="reclamos")
    elif pagina_disponibilidad_activa or pagina_reclamos_activa:
        st.markdown('<div class="filter-mini-note">Sin datos exportables para este KPI.</div>', unsafe_allow_html=True)
    elif pagina_epa_activa:
        render_boton_exportar_datos(df_epa_export, filtros_export, modo="epa")
    elif pagina_uso_herramienta_activa:
        render_boton_exportar_datos(df_uso_export, filtros_export, modo="uso_herramienta")
    else:
        render_boton_exportar_datos(df_export, filtros_export)

# =========================================================
# HEADER
# =========================================================

c1, c2 = st.columns([8,1])

with c1:

    st.markdown("""
    <div class="titulo">
        Panel de Adherencia Entel Connect
    </div>

    <div class="linea-titulo"></div>

    <div class="subtitulo">
        Cumplimiento de KPI, adherencia operacional y desempeño del Servicio Técnico Externo.
    </div>
    """, unsafe_allow_html=True)


with c2:
    if LOGO_ST_DATA:
        st.markdown(
            f"""
            <div class="brand-lockup {LOGO_ST_CLASS}">
                <img src="{LOGO_ST_DATA}" alt="{SERVICIO_ACTUAL}" draggable="false">
            </div>
            """,
            unsafe_allow_html=True
        )

kpi_activo = st.radio(
    "Selector KPI",
    KPI_OPCIONES,
    horizontal=True,
    label_visibility="collapsed",
    key="kpi_activo",
)

mostrar_kpi_inicio = kpi_activo == KPI_INICIO
mostrar_kpi_epa = kpi_activo == KPI_EPA
mostrar_kpi_uso_herramienta = kpi_activo == KPI_USO_HERRAMIENTA
mostrar_kpi_disponibilidad = kpi_activo == KPI_DISPONIBILIDAD
mostrar_kpi_reclamos = kpi_activo == KPI_RECLAMOS

if mostrar_kpi_inicio:
    st.markdown('<div class="kpi-divider"></div>', unsafe_allow_html=True)

# =========================================================
# # =========================================================
# =========================================================
# NOTA: Próxima mejora: reemplazar las 4 KPI Cards HTML por indicadores Plotly.
# =========================================================

# KPI CARDS GERENCIALES ENTEL - PLOTLY PRO
# =========================================================
# Tarjetas sobrias para dashboard gerencial: iconos dibujados con
# formas Plotly, acentos corporativos, lectura ejecutiva y barra de avance.


def rgba(hex_color, alpha):
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def dibujar_icono(fig_kpi, tipo, color):
    """Iconografía ejecutiva sin emojis: barras, check, alerta y gauge."""

    # Contenedor sutil del icono
    fig_kpi.add_shape(
        type="circle",
        x0=0.065, y0=0.655, x1=0.185, y1=0.855,
        xref="paper", yref="paper",
        fillcolor=rgba(color, 0.10),
        line=dict(color=rgba(color, 0.35), width=1.3),
        layer="above"
    )

    if tipo == "total":
        # Barras ejecutivas
        barras = [
            (0.094, 0.702, 0.108, 0.765),
            (0.122, 0.702, 0.136, 0.805),
            (0.150, 0.702, 0.164, 0.745),
        ]
        for x0, y0, x1, y1 in barras:
            fig_kpi.add_shape(
                type="rect", x0=x0, y0=y0, x1=x1, y1=y1,
                xref="paper", yref="paper",
                fillcolor=color,
                line=dict(color=color, width=0),
                layer="above"
            )
        fig_kpi.add_shape(
            type="line", x0=0.088, y0=0.695, x1=0.170, y1=0.695,
            xref="paper", yref="paper",
            line=dict(color=color, width=2),
            layer="above"
        )

    elif tipo == "ok":
        # Check dibujado con línea
        fig_kpi.add_trace(go.Scatter(
            x=[0.095, 0.122, 0.165],
            y=[0.745, 0.705, 0.805],
            mode="lines",
            line=dict(color=color, width=6),
            hoverinfo="skip",
            showlegend=False
        ))

    elif tipo == "no_ok":
        # Cruz sobria
        fig_kpi.add_trace(go.Scatter(
            x=[0.102, 0.162], y=[0.705, 0.805],
            mode="lines", line=dict(color=color, width=5),
            hoverinfo="skip", showlegend=False
        ))
        fig_kpi.add_trace(go.Scatter(
            x=[0.102, 0.162], y=[0.805, 0.705],
            mode="lines", line=dict(color=color, width=5),
            hoverinfo="skip", showlegend=False
        ))

    elif tipo == "global":
        # Target / desempeño
        for radio, ancho in [(0.048, 2.2), (0.030, 2.2), (0.012, 0)]:
            fig_kpi.add_shape(
                type="circle",
                x0=0.125-radio, y0=0.755-radio,
                x1=0.125+radio, y1=0.755+radio,
                xref="paper", yref="paper",
                fillcolor=color if radio == 0.012 else "rgba(255,255,255,0)",
                line=dict(color=color, width=ancho),
                layer="above"
            )
        fig_kpi.add_shape(
            type="line", x0=0.160, y0=0.790, x1=0.182, y1=0.825,
            xref="paper", yref="paper",
            line=dict(color=color, width=3),
            layer="above"
        )

    elif tipo == "revisita":
        # Ciclo / retorno: separa visualmente la revisita de una falla operacional.
        fig_kpi.add_shape(
            type="circle",
            x0=0.092, y0=0.705, x1=0.168, y1=0.805,
            xref="paper", yref="paper",
            fillcolor="rgba(255,255,255,0)",
            line=dict(color=color, width=3),
            layer="above"
        )
        fig_kpi.add_trace(go.Scatter(
            x=[0.158, 0.178, 0.163],
            y=[0.812, 0.822, 0.840],
            mode="lines",
            line=dict(color=color, width=3),
            hoverinfo="skip",
            showlegend=False
        ))
        fig_kpi.add_trace(go.Scatter(
            x=[0.100, 0.080, 0.095],
            y=[0.698, 0.688, 0.670],
            mode="lines",
            line=dict(color=color, width=3),
            hoverinfo="skip",
            showlegend=False
        ))


def kpi_card(container, tipo_icono, titulo, valor, subtitulo, color, indicador=None, progreso=None):
    with container:
        fig_kpi = go.Figure()
        valor_x = 0.42 if indicador is not None else 0.50

        # Sombra de profundidad dentro del lienzo Plotly.
        fig_kpi.add_shape(
            type="rect",
            x0=0.042, y0=0.022, x1=0.995, y1=0.895,
            xref="paper", yref="paper",
            fillcolor="rgba(15,23,42,0.135)",
            line=dict(color="rgba(15,23,42,0)", width=0),
            layer="below"
        )
        fig_kpi.add_shape(
            type="rect",
            x0=0.024, y0=0.055, x1=0.978, y1=0.928,
            xref="paper", yref="paper",
            fillcolor=rgba(color, 0.10),
            line=dict(color="rgba(15,23,42,0)", width=0),
            layer="below"
        )

        # Fondo principal con volumen sutil.
        fig_kpi.add_shape(
            type="rect",
            x0=0.000, y0=0.085, x1=0.955, y1=0.970,
            xref="paper", yref="paper",
            fillcolor="rgba(6,18,34,0.82)",
            line=dict(color=rgba(color, 0.46), width=1.5),
            layer="below"
        )

        # Brillo superior y acento corporativo.
        fig_kpi.add_shape(
            type="rect",
            x0=0.020, y0=0.910, x1=0.935, y1=0.952,
            xref="paper", yref="paper",
            fillcolor=rgba(color, 0.14),
            line=dict(color=rgba(color, 0), width=0),
            layer="above"
        )
        fig_kpi.add_shape(
            type="rect",
            x0=0.000, y0=0.945, x1=0.955, y1=0.970,
            xref="paper", yref="paper",
            fillcolor=color,
            line=dict(color=color, width=0),
            layer="above"
        )

        # Banda lateral y halo del valor para separar lectura KPI vs gráfico.
        fig_kpi.add_shape(
            type="rect",
            x0=0.000, y0=0.085, x1=0.012, y1=0.945,
            xref="paper", yref="paper",
            fillcolor=rgba(color, 0.20),
            line=dict(color=rgba(color, 0), width=0),
            layer="above"
        )
        fig_kpi.add_shape(
            type="circle",
            x0=valor_x - 0.190, y0=0.225, x1=valor_x + 0.190, y1=0.650,
            xref="paper", yref="paper",
            fillcolor=rgba(color, 0.13),
            line=dict(color=rgba(color, 0), width=0),
            layer="above"
        )

        dibujar_icono(fig_kpi, tipo_icono, color)

        fig_kpi.add_annotation(
            x=valor_x, y=0.725,
            xref="paper", yref="paper",
            text=f"<b>{titulo}</b>",
            showarrow=False,
            align="center",
            xanchor="center",
            font=dict(size=14, color="#EAFBFF", family="Segoe UI Semibold")
        )

        # Valor principal
        fig_kpi.add_annotation(
            x=valor_x + 0.002, y=0.465,
            xref="paper", yref="paper",
            text=f"<b>{valor}</b>",
            showarrow=False,
            align="center",
            xanchor="center",
            font=dict(size=31, color="rgba(255,255,255,0.12)", family="Segoe UI Black")
        )
        fig_kpi.add_annotation(
            x=valor_x, y=0.462,
            xref="paper", yref="paper",
            text=f"<b>{valor}</b>",
            showarrow=False,
            align="center",
            xanchor="center",
            font=dict(size=31, color=color, family="Segoe UI Black")
        )

        # Indicador derecho
        if indicador is not None:
            indicador_size = 15 if len(str(indicador)) > 5 else 18
            fig_kpi.add_shape(
                type="rect",
                x0=0.690, y0=0.390, x1=0.920, y1=0.570,
                xref="paper", yref="paper",
                fillcolor=rgba(color, 0.16),
                line=dict(color=rgba(color, 0.34), width=1),
                layer="above"
            )
            fig_kpi.add_annotation(
                x=0.805, y=0.480,
                xref="paper", yref="paper",
                text=f"<b>{indicador}</b>",
                showarrow=False,
                align="center",
                xanchor="center",
                font=dict(size=indicador_size, color=color, family="Segoe UI Black")
            )

        # Subtítulo
        fig_kpi.add_annotation(
            x=valor_x, y=0.245,
            xref="paper", yref="paper",
            text=subtitulo,
            showarrow=False,
            align="center",
            xanchor="center",
            font=dict(size=10, color="#BDEFFF", family="Segoe UI Semibold")
        )

        # Barra de avance inferior
        if progreso is not None:
            prog = max(0, min(float(progreso), 100)) / 100
            fig_kpi.add_shape(
                type="rect",
                x0=0.070, y0=0.098, x1=0.890, y1=0.124,
                xref="paper", yref="paper",
                fillcolor="rgba(143,239,255,0.14)",
                line=dict(color="rgba(143,239,255,0.14)", width=0),
                layer="above"
            )
            fig_kpi.add_shape(
                type="rect",
                x0=0.070, y0=0.098, x1=0.070 + 0.82 * prog, y1=0.124,
                xref="paper", yref="paper",
                fillcolor=color,
                line=dict(color=color, width=0),
                layer="above"
            )
            fig_kpi.add_shape(
                type="rect",
                x0=0.070, y0=0.124, x1=0.070 + 0.82 * prog, y1=0.134,
                xref="paper", yref="paper",
                fillcolor=rgba(color, 0.30),
                line=dict(color=rgba(color, 0), width=0),
                layer="above"
            )

        fig_kpi.update_layout(
            height=142,
            margin=dict(l=0, r=0, t=0, b=0),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(visible=False, range=[0, 1], fixedrange=True),
            yaxis=dict(visible=False, range=[0, 1], fixedrange=True),
            showlegend=False,
            hovermode=False
        )

        st.plotly_chart(
            fig_kpi,
            use_container_width=True,
            config=PLOTLY_CONFIG_SOLO_LECTURA
        )


def render_kpi_card_grid(cards):
    def card(icono, titulo, valor, subtitulo, color, badge="", progreso=None):
        valor_texto = str(valor)
        es_valor_texto = not bool(re.fullmatch(r"\s*[-+]?\d+(?:[.,]\d+)?%?\s*", valor_texto))
        clase_valor = "disp-kpi-card is-text-value" if es_valor_texto else "disp-kpi-card"
        progress_value = 0 if progreso is None else max(0, min(float(progreso), 100))
        badge_html = f'<span class="disp-kpi-badge">{badge}</span>' if badge else ""
        progress_html = (
            f'<div class="disp-kpi-progress"><div class="disp-kpi-progress-fill" style="--progress:{progress_value:.1f}%;"></div></div>'
            if progreso is not None else ""
        )
        return (
            f'<div class="{clase_valor}" style="--accent:{color};">'
            f'<div class="disp-kpi-icon">{icono}</div>'
            f'<div class="disp-kpi-title">{titulo}</div>'
            f'<div class="disp-kpi-value-row"><div class="disp-kpi-value">{valor_texto}</div>{badge_html}</div>'
            f'<div class="disp-kpi-subtitle">{subtitulo}</div>'
            f'{progress_html}'
            f'</div>'
        )

    html_cards = [
        card(
            item.get("icono", "&#9673;"),
            item.get("titulo", ""),
            item.get("valor", ""),
            item.get("subtitulo", ""),
            item.get("color", CELESTE),
            item.get("badge", ""),
            item.get("progreso"),
        )
        for item in cards
    ]
    st.markdown(f'<div class="disp-kpi-grid">{"".join(html_cards)}</div>', unsafe_allow_html=True)


def render_estado_sin_datos(titulo="No hay datos para mostrar", detalle="", etiqueta="Sin datos"):
    detalle_html = f'<div class="no-data-detail">{html.escape(str(detalle))}</div>' if detalle else ""
    st.markdown(
        f"""
        <div class="no-data-shell">
            <div class="no-data-logo-wrap">
                <img src="{LOGO_ECC_ICONO_DATA}" alt="Entel Connect" draggable="false">
            </div>
            <div class="no-data-copy">
                <div class="no-data-kicker">{html.escape(str(etiqueta))}</div>
                <div class="no-data-title">{html.escape(str(titulo))}</div>
                {detalle_html}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def kpi_no_aplica_servicio(servicio, kpi):
    config = SERVICIOS_CONFIG.get(servicio, {})
    if kpi == KPI_DISPONIBILIDAD:
        return not config.get("participa_disponibilidad", True)
    if kpi == KPI_RECLAMOS:
        return not config.get("participa_reclamos", True)
    return False


def render_disponibilidad_kpi_cards(color_cumplimiento, disp_pct, disp_total, disp_cumple, disp_no_cumple, disp_sin_respuesta, disp_reit_cecom_total):
    render_kpi_card_grid([
        {"icono": "&#9673;", "titulo": "Cumplimiento KPI", "valor": f"{disp_pct:.1f}%", "subtitulo": f"<= {DISPONIBILIDAD_SLA_MIN} min habiles", "color": color_cumplimiento, "badge": f"Meta {DISPONIBILIDAD_META_PCT}%", "progreso": disp_pct},
        {"icono": "&#9606;", "titulo": "Solicitudes CECOM", "valor": disp_total, "subtitulo": "Desde 01-01-2026", "color": KPI_TOTAL},
        {"icono": "&#10003;", "titulo": "Cumplen KPI", "valor": disp_cumple, "subtitulo": f"Respuesta {SERVICIO_TITULO} transversal", "color": VERDE},
        {"icono": "&#10005;", "titulo": "No cumplen", "valor": disp_no_cumple, "subtitulo": f"{disp_sin_respuesta} sin respuesta", "color": ROSADO},
        {"icono": "&#8635;", "titulo": "Reiteraciones CECOM", "valor": disp_reit_cecom_total, "subtitulo": "Insistencias antes de respuesta", "color": CELESTE if disp_reit_cecom_total else VERDE},
    ])


def _texto_corto(valor, max_chars=150):
    texto = str(valor or "").strip()
    if len(texto) <= max_chars:
        return texto
    return texto[: max_chars - 3].rstrip() + "..."


def construir_insights_disponibilidad_fallback(metricas):
    disp_total = int(metricas.get("disp_total", 0))
    disp_pct = float(metricas.get("disp_pct", 0))
    disp_cumple = int(metricas.get("disp_cumple", 0))
    disp_sin_respuesta = int(metricas.get("disp_sin_respuesta", 0))
    disp_brecha_meta = float(metricas.get("disp_brecha_meta", 0))
    disp_reiteraciones = int(metricas.get("disp_reiteraciones", 0))
    disp_tickets_reiterados = int(metricas.get("disp_tickets_reiterados", 0))
    disp_reit_cecom_total = int(metricas.get("disp_reit_cecom_total", 0))
    comparativo = str(metricas.get("comparativo_disponibilidad_proveedor", "")).strip()

    if disp_total:
        titulo_cumplimiento = "Bajo meta operacional" if disp_pct < DISPONIBILIDAD_META_PCT else "Dentro de meta"
        cuerpo_cumplimiento = (
            f"{disp_cumple}/{disp_total} solicitudes cumplen ({disp_pct:.1f}%). "
            f"Brecha {disp_brecha_meta:+.1f} pp; foco inmediato en {disp_sin_respuesta} sin respuesta."
        )
        if comparativo:
            cuerpo_cumplimiento = f"{cuerpo_cumplimiento} Comparativo: {comparativo}."
    else:
        titulo_cumplimiento = "Sin base filtrada"
        cuerpo_cumplimiento = "No hay solicitudes disponibles para evaluar cumplimiento con los filtros actuales."

    if disp_reit_cecom_total or disp_reiteraciones:
        titulo_reiteraciones = "Reiteración con fricción"
        cuerpo_reiteraciones = (
            f"{disp_reit_cecom_total} reiteraciones CECOM y {disp_reiteraciones} totales en "
            f"{disp_tickets_reiterados} tickets. Priorizar tickets con mas gestiones, proveedor bajo meta y sin respuesta {SERVICIO_TITULO}."
        )
    else:
        titulo_reiteraciones = "Sin fricción reiterada"
        cuerpo_reiteraciones = "No se observan reiteraciones en la vista filtrada; mantener monitoreo preventivo."

    if disp_sin_respuesta:
        titulo_respuesta = "Pendiente de respuesta"
        cuerpo_respuesta = f"{disp_sin_respuesta} solicitudes siguen sin respuesta. Ordenar por cliente y antiguedad para cierre operativo."
    else:
        titulo_respuesta = "Respuesta completa"
        cuerpo_respuesta = "No quedan solicitudes sin respuesta en la vista filtrada; sostener control del SLA."

    return [
        {"indicador": "Cumplimiento KPI", "titulo": titulo_cumplimiento, "cuerpo": cuerpo_cumplimiento, "tono": "mal" if disp_pct < DISPONIBILIDAD_META_PCT else "bien"},
        {"indicador": "Reiteraciones", "titulo": titulo_reiteraciones, "cuerpo": cuerpo_reiteraciones, "tono": "mal" if disp_reit_cecom_total or disp_reiteraciones else "bien"},
        {"indicador": "Respuesta", "titulo": titulo_respuesta, "cuerpo": cuerpo_respuesta, "tono": "mal" if disp_sin_respuesta else "bien"},
    ]


def construir_prompt_ollama_disponibilidad(metricas):
    return f"""
Eres gerente de operaciones de un dashboard Entel/{SERVICIO_TITULO}. Analiza los indicadores filtrados y devuelve SOLO JSON valido.
Formato exacto: [
  {{"indicador":"Cumplimiento KPI","titulo":"...","cuerpo":"...","tono":"bien|mal|accion"}},
  {{"indicador":"Reiteraciones","titulo":"...","cuerpo":"...","tono":"bien|mal|accion"}},
  {{"indicador":"Respuesta","titulo":"...","cuerpo":"...","tono":"bien|mal|accion"}}
]
Reglas: maximo 12 palabras en titulo, maximo 24 palabras en cuerpo, tono ejecutivo, concreto, sin markdown.
Metricas: {json.dumps(metricas, ensure_ascii=False)}
"""


@st.cache_data(ttl=600, show_spinner=False)
def consultar_ollama_analisis(prompt, modelo, endpoint):
    try:
        payload = json.dumps({
            "model": modelo,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.15, "num_predict": 260},
        }).encode("utf-8")
        req = urlrequest.Request(
            endpoint,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlrequest.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return str(data.get("response", "")).strip()
    except (OSError, TimeoutError, ValueError, urlerror.URLError, urlerror.HTTPError):
        return ""


def normalizar_insights_ollama(texto, fallback):
    if not texto:
        return fallback
    try:
        inicio = texto.find("[")
        fin = texto.rfind("]")
        if inicio >= 0 and fin > inicio:
            texto = texto[inicio:fin + 1]
        data = json.loads(texto)
        if isinstance(data, dict):
            data = data.get("insights", [])
        if not isinstance(data, list):
            return fallback

        normalizados = []
        for item, respaldo in zip(data[:3], fallback):
            if not isinstance(item, dict):
                normalizados.append(respaldo)
                continue
            indicador = _texto_corto(item.get("indicador") or respaldo["indicador"], 32)
            titulo = _texto_corto(item.get("titulo") or respaldo["titulo"], 58)
            cuerpo = _texto_corto(item.get("cuerpo") or respaldo["cuerpo"], 220)
            tono = str(item.get("tono") or respaldo["tono"]).strip().lower()
            if tono not in {"bien", "mal", "accion"}:
                tono = respaldo["tono"]
            normalizados.append({"indicador": indicador, "titulo": titulo, "cuerpo": cuerpo, "tono": tono})
        return normalizados if len(normalizados) == 3 else fallback
    except (TypeError, ValueError, json.JSONDecodeError):
        return fallback


def render_analisis_disponibilidad(metricas):
    fallback = construir_insights_disponibilidad_fallback(metricas)
    render_analisis_hoja("KPI Disponibilidad", metricas, fallback)


def render_reclamos_kpi_cards(
    reclamos_total,
    reclamos_reclamos_duros,
    reclamos_reforzamientos,
    reclamos_alta,
    reclamos_tickets,
    reclamos_clientes,
    atenciones_asignadas_reclamos,
    reclamos_ratio_incumplimiento,
    reclamos_cumplimiento_ajustado,
    reclamos_brecha_meta,
    reclamos_cliente_top,
    reclamos_cliente_top_count,
    reclamos_cliente_top_tickets,
    reclamos_proveedor_reforzado_top,
    reclamos_proveedor_reforzado_top_count,
):
    pct_foco = round(reclamos_cliente_top_count / max(reclamos_total, 1) * 100, 1) if reclamos_total else 0
    color_cumplimiento = VERDE if reclamos_cumplimiento_ajustado >= RECLAMOS_META_CUMPLIMIENTO_PCT else ROSADO
    render_kpi_card_grid([
        {"icono": "&#9888;", "titulo": "Señales operacionales", "valor": reclamos_total, "subtitulo": f"{reclamos_reclamos_duros} reclamos | {reclamos_reforzamientos} reforzamientos", "color": NARANJO if reclamos_total else VERDE},
        {"icono": "&#9776;", "titulo": "Atenciones asignadas", "valor": atenciones_asignadas_reclamos, "subtitulo": "Denominador filtrado por periodo", "color": KPI_TOTAL},
        {"icono": "&#37;", "titulo": "Ratio incumplimiento", "valor": f"{reclamos_ratio_incumplimiento:.1f}%", "subtitulo": f"{reclamos_total}/{max(atenciones_asignadas_reclamos, 0)} señales/atenciones", "color": ROSADO if reclamos_ratio_incumplimiento > RECLAMOS_META_RATIO_INCUMPLIMIENTO_PCT else VERDE, "badge": f"Meta <= {RECLAMOS_META_RATIO_INCUMPLIMIENTO_PCT:.1f}%"},
        {"icono": "&#9673;", "titulo": "Cumplimiento ajustado", "valor": f"{reclamos_cumplimiento_ajustado:.1f}%", "subtitulo": f"Meta {RECLAMOS_META_CUMPLIMIENTO_PCT}% | brecha {reclamos_brecha_meta:+.1f} pp", "color": color_cumplimiento, "progreso": reclamos_cumplimiento_ajustado},
        {"icono": "&#9881;", "titulo": "Reforzamientos", "valor": reclamos_reforzamientos, "subtitulo": f"Foco ST: {nombre_corto_leyenda(reclamos_proveedor_reforzado_top, 18)} ({reclamos_proveedor_reforzado_top_count})", "color": CELESTE if reclamos_reforzamientos else VERDE, "badge": "Refuerzo" if reclamos_reforzamientos else "OK"},
        {"icono": "&#33;", "titulo": "Cliente a revisar", "valor": nombre_corto_leyenda(reclamos_cliente_top, 18), "subtitulo": f"{reclamos_cliente_top_count} registros | {reclamos_cliente_top_tickets} tickets distintos | {pct_foco:.1f}% del total", "color": ROSADO if reclamos_cliente_top_count else VERDE, "badge": "Foco" if reclamos_cliente_top_count else "OK"},
    ])


def construir_insights_reclamos_fallback(metricas):
    reclamos_total = int(metricas.get("reclamos_total", 0))
    reclamos_duros = int(metricas.get("reclamos_reclamos_duros", max(reclamos_total, 0)))
    reforzamientos = int(metricas.get("reclamos_reforzamientos", 0))
    reclamos_alta = int(metricas.get("reclamos_alta", 0))
    reclamos_tickets = int(metricas.get("reclamos_tickets", 0))
    reclamos_clientes = int(metricas.get("reclamos_clientes", 0))
    motivo_top = str(metricas.get("reclamos_motivo_top", "Sin reclamos"))
    motivo_top_count = int(metricas.get("reclamos_motivo_top_count", 0))
    cliente_top = str(metricas.get("reclamos_cliente_top", "Sin cliente"))
    cliente_top_count = int(metricas.get("reclamos_cliente_top_count", 0))
    atenciones = int(metricas.get("atenciones_asignadas_reclamos", 0))
    ratio_incumplimiento = float(metricas.get("reclamos_ratio_incumplimiento", 0))
    cumplimiento_ajustado = float(metricas.get("reclamos_cumplimiento_ajustado", 0))
    brecha_meta = float(metricas.get("reclamos_brecha_meta", 0))
    proveedor_ref_top = str(metricas.get("reclamos_proveedor_reforzado_top", "Sin reforzar"))
    proveedor_ref_top_count = int(metricas.get("reclamos_proveedor_reforzado_top_count", 0))
    comparativo = str(metricas.get("comparativo_reclamos_proveedor", "")).strip()

    if reclamos_total:
        titulo_volumen = "Riesgo contractual activo"
        cuerpo_volumen = (
            f"{reclamos_total} señales sobre {atenciones} atenciones: {reclamos_duros} reclamos y {reforzamientos} reforzamientos. "
            f"Incumplimiento {ratio_incumplimiento:.1f}% y cumplimiento ajustado {cumplimiento_ajustado:.1f}% ({brecha_meta:+.1f} pp vs meta)."
        )
    else:
        titulo_volumen = "Sin reclamos activos"
        cuerpo_volumen = "No hay reclamos ni reforzamientos en la vista filtrada; sostener seguimiento preventivo."

    if reforzamientos:
        titulo_foco_cliente = "Reforzamiento activo"
        cuerpo_foco_cliente = f"{proveedor_ref_top} concentra {proveedor_ref_top_count} reforzamientos. Convertirlos en plan semanal: causa, responsable, fecha y evidencia de cierre."
    elif cliente_top_count:
        titulo_foco_cliente = "Foco cliente activo"
        cuerpo_foco_cliente = f"{cliente_top} tiene {cliente_top_count} señales; validar tickets distintos, fecha, tecnico y causa antes de accionar."
    else:
        titulo_foco_cliente = "Sin foco operativo"
        cuerpo_foco_cliente = "No aparece concentracion de reclamos ni reforzamientos con los filtros actuales."

    titulo_motivo = "Causa y comparativo"
    if reclamos_total:
        base_motivo = f"{motivo_top}: {motivo_top_count} registros. Cliente a revisar: {cliente_top}. Clientes afectados: {reclamos_clientes}; tickets: {reclamos_tickets}."
        cuerpo_motivo = f"{base_motivo} {comparativo}" if comparativo else f"{base_motivo} Comparar proveedor, causa y recurrencia antes de reclamar a contratista."
    else:
        cuerpo_motivo = "Sin motivo dominante para analizar."

    return [
        {"indicador": "Volumen", "titulo": titulo_volumen, "cuerpo": cuerpo_volumen, "tono": "mal" if reclamos_total else "bien"},
        {"indicador": "Foco operativo", "titulo": titulo_foco_cliente, "cuerpo": cuerpo_foco_cliente, "tono": "accion" if reforzamientos else "mal" if cliente_top_count else "bien"},
        {"indicador": "Causa", "titulo": titulo_motivo, "cuerpo": cuerpo_motivo, "tono": "accion" if reclamos_total else "bien"},
    ]


def render_analisis_reclamos(metricas):
    render_analisis_hoja("KPI Reclamos", metricas, construir_insights_reclamos_fallback(metricas))


def render_analisis_hoja(nombre_hoja, metricas, fallback):
    # Sin LLM local: insights livianos, deterministicos y recalculados desde la data filtrada.
    insights = fallback

    colores = {"bien": VERDE, "mal": ROSADO, "accion": CELESTE}
    html_cards = []
    for insight in insights:
        color = colores.get(insight.get("tono"), CELESTE)
        html_cards.append(
            f'<div class="ai-insight-card" style="--accent:{color};">'
            f'<div class="ai-insight-kicker">{html.escape(str(insight.get("indicador", "")))}</div>'
            f'<div class="ai-insight-title">{html.escape(str(insight.get("titulo", "")))}</div>'
            f'<div class="ai-insight-body">{html.escape(str(insight.get("cuerpo", "")))}</div>'
            f'</div>'
        )
    st.markdown(f'<div class="ai-insight-grid">{"".join(html_cards)}</div>', unsafe_allow_html=True)


def construir_prompt_ollama_hoja(nombre_hoja, metricas, fallback):
    indicadores = [
        {"indicador": item["indicador"], "tono_sugerido": item.get("tono", "accion")}
        for item in fallback
    ]
    return f"""
Eres gerente de operaciones de Entel/{SERVICIO_TITULO}. Analiza la hoja "{nombre_hoja}" y devuelve SOLO JSON valido.
Formato exacto: [
  {{"indicador":"...","titulo":"...","cuerpo":"...","tono":"bien|mal|accion"}},
  {{"indicador":"...","titulo":"...","cuerpo":"...","tono":"bien|mal|accion"}},
  {{"indicador":"...","titulo":"...","cuerpo":"...","tono":"bien|mal|accion"}}
]
Usa estos indicadores, en este orden: {json.dumps(indicadores, ensure_ascii=False)}
Reglas: maximo 12 palabras en titulo, maximo 42 palabras en cuerpo, tono ejecutivo, concreto, sin markdown. Si la vista incluye Todo, compara proveedor contra proveedor y explica donde mejorar usando denominador, brecha contra meta, causa y siguiente accion.
Metricas: {json.dumps(metricas, ensure_ascii=False)}
"""


def construir_insights_inicio_fallback(metricas):
    total_base = int(metricas.get("total", 0))
    pct_cumplimiento = float(metricas.get("pct", 0))
    finalizadas_primera = int(metricas.get("finalizadas_primera_visita", 0))
    pct_primera = float(metricas.get("pct_primera_visita", 0))
    revisitas_total = int(metricas.get("revisitas", 0))
    pct_revisitas_valor = float(metricas.get("pct_revisitas", 0))
    no_finalizadas_total = int(metricas.get("no_finalizadas", 0))
    comparativo = str(metricas.get("comparativo_inicio_proveedor", "")).strip()

    titulo_cumplimiento = "Bajo meta de inicio" if pct_cumplimiento < 80 else "Inicio dentro de meta"
    cuerpo_cumplimiento = (
        f"{pct_cumplimiento:.1f}% de cumplimiento sobre {total_base} atenciones. "
        + (f"Comparativo ST: {comparativo}." if comparativo else "Priorizar proveedor, técnico o base filtrada bajo 80%.")
        if total_base else
        "No hay base filtrada para evaluar inicio de actividad."
    )

    titulo_primera = "Buena resolución inicial" if pct_primera >= 70 else "Primera visita débil"
    cuerpo_primera = (
        f"{finalizadas_primera} cierres en primera visita ({pct_primera:.1f}%). "
        f"{no_finalizadas_total} atenciones siguen fuera de cierre final."
        if total_base else
        "Sin atenciones filtradas para evaluar cierre en primera visita."
    )

    titulo_revisitas = "Revisitas bajo control" if pct_revisitas_valor <= 5 else "Revisitas elevan fricción"
    cuerpo_revisitas = (
        f"{revisitas_total} revisitas equivalen a {pct_revisitas_valor:.1f}% de la base. "
        + ("Comparar recurrencia por ST antes de bajar a técnico." if comparativo else "Revisar causa raíz por técnico y base filtrada.")
        if total_base else
        "Sin base filtrada para detectar revisitas."
    )

    return [
        {"indicador": "Cumplimiento inicio", "titulo": titulo_cumplimiento, "cuerpo": cuerpo_cumplimiento, "tono": "mal" if pct_cumplimiento < 80 else "bien"},
        {"indicador": "Primera visita", "titulo": titulo_primera, "cuerpo": cuerpo_primera, "tono": "bien" if pct_primera >= 70 else "accion"},
        {"indicador": "Revisitas", "titulo": titulo_revisitas, "cuerpo": cuerpo_revisitas, "tono": "bien" if pct_revisitas_valor <= 5 else "mal"},
    ]


def render_analisis_inicio(metricas):
    render_analisis_hoja("KPI Inicio Actividad", metricas, construir_insights_inicio_fallback(metricas))


def construir_insights_epa_fallback(metricas):
    total_atenciones = int(metricas.get("epa_total_atenciones", 0))
    respondidas = int(metricas.get("epa_total_respuestas", 0))
    pendientes = int(metricas.get("epa_pendientes", 0))
    satisfaccion = float(metricas.get("epa_satisfaccion", 0))
    promedio = float(metricas.get("epa_promedio", 0))
    recomendacion = float(metricas.get("epa_recomendacion", 0))
    tasa_respuesta = round(respondidas / max(total_atenciones, 1) * 100, 1) if total_atenciones else 0

    titulo_satisfaccion = "Satisfacción sobre meta" if satisfaccion >= 90 else "Satisfacción bajo meta"
    cuerpo_satisfaccion = (
        f"{satisfaccion:.1f}% de satisfacción y promedio {promedio:.1f}/5. "
        "Revisar comentarios de notas bajas."
        if respondidas else
        "Aún no hay respuestas EPA suficientes para evaluar satisfacción."
    )

    titulo_respuesta = "Buena captura EPA" if tasa_respuesta >= 70 else "Captura EPA insuficiente"
    cuerpo_respuesta = (
        f"{respondidas}/{total_atenciones} respuestas ({tasa_respuesta:.1f}%). "
        f"Pendientes: {pendientes}; reforzar contacto post atención."
        if total_atenciones else
        "No hay links EPA en la vista filtrada."
    )

    titulo_recomendacion = "Recomendación sólida" if recomendacion >= 4 else "Recomendación a reforzar"
    cuerpo_recomendacion = (
        f"Promedio recomendación {recomendacion:.1f}/5. "
        "Cruzar técnicos con menor nota para acciones de coaching."
        if respondidas else
        "Sin respuestas suficientes para analizar recomendación."
    )

    return [
        {"indicador": "Satisfacción EPA", "titulo": titulo_satisfaccion, "cuerpo": cuerpo_satisfaccion, "tono": "bien" if satisfaccion >= 90 else "mal"},
        {"indicador": "Respuestas", "titulo": titulo_respuesta, "cuerpo": cuerpo_respuesta, "tono": "bien" if tasa_respuesta >= 70 else "accion"},
        {"indicador": "Recomendación", "titulo": titulo_recomendacion, "cuerpo": cuerpo_recomendacion, "tono": "bien" if recomendacion >= 4 else "accion"},
    ]


def render_analisis_epa(metricas):
    render_analisis_hoja("KPI EPA Satisfacción", metricas, construir_insights_epa_fallback(metricas))


def preparar_dispersion_epa(df_base, dimension):
    columnas_necesarias = {dimension, "promedio", "_fecha_epa"}
    if df_base.empty or not columnas_necesarias.issubset(df_base.columns):
        return pd.DataFrame()

    base = df_base[list(columnas_necesarias)].copy()
    base["promedio"] = pd.to_numeric(base["promedio"], errors="coerce")
    base["_fecha_epa"] = pd.to_datetime(base["_fecha_epa"], errors="coerce")
    base[dimension] = (
        base[dimension]
        .fillna("Sin dato")
        .astype(str)
        .str.strip()
        .replace({"": "Sin dato"})
    )
    base = base.dropna(subset=["_fecha_epa", "promedio"])

    if base.empty:
        return pd.DataFrame()

    base["_periodo_orden"] = base["_fecha_epa"].dt.to_period("M").dt.to_timestamp()
    base["_periodo_label"] = base["_periodo_orden"].map(
        lambda fecha: f"{MESES_CORTOS.get(MESES[fecha.month - 1], fecha.strftime('%m'))} {fecha.year}"
    )
    resumen = (
        base.groupby(["_periodo_orden", "_periodo_label", dimension], as_index=False)
        .agg(promedio=("promedio", "mean"), respuestas=("promedio", "size"))
        .sort_values(["_periodo_orden", "promedio"], ascending=[True, False])
    )
    resumen["promedio"] = resumen["promedio"].round(2)
    resumen["brecha_minima"] = (resumen["promedio"] - 4).round(2)
    return resumen


def nombre_corto_leyenda(valor, largo=30):
    texto = str(valor)
    return texto if len(texto) <= largo else texto[:largo - 3] + "..."


def grafico_dispersion_epa(resumen, dimension, titulo):
    fig_disp = go.Figure()
    categorias_periodo = []
    tickvals_periodo = None

    fig_disp.add_hrect(
        y0=4,
        y1=5,
        fillcolor=rgba(VERDE, 0.10),
        line_width=0,
        layer="below"
    )
    fig_disp.add_hline(
        y=4,
        line_dash="dot",
        line_width=2.6,
        line_color=ROSADO,
        annotation_text="M\u00ednimo 4",
        annotation_position="top left",
        annotation_font=dict(size=12, color=ROSADO, family="Segoe UI Black")
    )
    fig_disp.add_hline(
        y=5,
        line_width=1.8,
        line_color=VERDE,
        annotation_text="Objetivo 5",
        annotation_position="bottom right",
        annotation_font=dict(size=12, color=VERDE, family="Segoe UI Black")
    )

    if len(resumen):
        colores_neon = [CELESTE, VERDE, ROSADO, AZUL_CLARO, NARANJO, "#8FA7FF", "#F7D154", "#B96CFF"]
        max_respuestas = max(int(resumen["respuestas"].max()), 1)
        periodo_orden = resumen[["_periodo_orden", "_periodo_label"]].drop_duplicates().sort_values("_periodo_orden")
        categorias_periodo = periodo_orden["_periodo_label"].tolist()
        if categorias_periodo:
            max_ticks = 10
            if len(categorias_periodo) > max_ticks:
                paso = max(1, -(-len(categorias_periodo) // max_ticks))
                tickvals_periodo = [
                    etiqueta
                    for indice, etiqueta in enumerate(categorias_periodo)
                    if indice % paso == 0 or indice == len(categorias_periodo) - 1
                ]
            else:
                tickvals_periodo = categorias_periodo
        for idx, nombre in enumerate(resumen[dimension].drop_duplicates()):
            datos = resumen[resumen[dimension].eq(nombre)].copy()
            color = colores_neon[idx % len(colores_neon)]
            tamanos = 13 + (datos["respuestas"] / max_respuestas * 18)
            borde = [VERDE if valor >= 4 else ROSADO for valor in datos["promedio"]]
            customdata = datos[[dimension, "respuestas", "brecha_minima"]].to_numpy()

            fig_disp.add_trace(
                go.Scatter(
                    x=datos["_periodo_label"],
                    y=datos["promedio"],
                    mode="markers",
                    marker=dict(
                        size=tamanos + 18,
                        color=rgba(color, 0.20),
                        line=dict(color=rgba(color, 0.34), width=1),
                    ),
                    hoverinfo="skip",
                    showlegend=False,
                )
            )
            fig_disp.add_trace(
                go.Scatter(
                    x=datos["_periodo_label"],
                    y=datos["promedio"],
                    mode="markers",
                    name=nombre_corto_leyenda(nombre),
                    marker=dict(
                        size=tamanos,
                        color=rgba(color, 0.86),
                        line=dict(color=borde, width=2.3),
                        symbol="circle",
                    ),
                    customdata=customdata,
                    hovertemplate=(
                        "<b>%{customdata[0]}</b><br>"
                        "Periodo: %{x}<br>"
                        "Promedio EPA: <b>%{y:.2f}</b><br>"
                        "Respuestas: <b>%{customdata[1]}</b><br>"
                        "Brecha vs 4: <b>%{customdata[2]:+.2f}</b>"
                        "<extra></extra>"
                    ),
                    showlegend=True,
                )
            )

    fig_disp.update_layout(
        title=dict(
            text=f"<b>{titulo}</b><br><span style='font-size:12px;color:#BDEFFF'>Meta 90%: promedios con nota 4 o superior; objetivo ideal 5</span>",
            x=0.02,
            xanchor="left",
            font=dict(size=17, color="#DDFBFF", family="Segoe UI Semibold")
        ),
        height=390,
        margin=dict(l=48, r=190, t=86, b=48),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(6,18,34,0.74)",
        legend=dict(
            title=dict(text=dimension.capitalize(), font=dict(size=12, color="#DDFBFF", family="Segoe UI Black")),
            orientation="v",
            x=1.02,
            xanchor="left",
            y=0.98,
            yanchor="top",
            bgcolor="rgba(6,18,34,0.82)",
            bordercolor="rgba(46,203,242,0.38)",
            borderwidth=1,
            font=dict(size=11, color="#EAFBFF", family="Segoe UI Semibold"),
        ),
        hoverlabel=dict(
            bgcolor="rgba(6,18,34,0.96)",
            bordercolor="rgba(46,203,242,0.40)",
            font=dict(size=12, family="Segoe UI", color="#EAFBFF")
        ),
    )
    fig_disp.update_xaxes(
        title=None,
        type="category",
        categoryorder="array",
        categoryarray=categorias_periodo if categorias_periodo else None,
        tickmode="array" if tickvals_periodo else "auto",
        tickvals=tickvals_periodo,
        tickangle=-18,
        showgrid=True,
        gridcolor="rgba(143,239,255,0.12)",
        zeroline=False,
        automargin=True,
        tickfont=dict(size=12, color="#BDEFFF", family="Segoe UI Semibold")
    )
    fig_disp.update_yaxes(
        title=None,
        range=[1, 5.15],
        dtick=0.5,
        showgrid=True,
        gridcolor="rgba(143,239,255,0.14)",
        zeroline=False,
        tickfont=dict(size=12, color="#BDEFFF", family="Segoe UI Semibold")
    )
    return fig_disp


def etiqueta_mes_fecha(fecha):
    if pd.isna(fecha):
        return "Sin fecha"
    return f"{MESES_CORTOS.get(MESES[int(fecha.month) - 1], fecha.strftime('%m'))} {int(fecha.year)}"


def preparar_resumen_mensual_disponibilidad(df_base):
    if df_base.empty or "fecha_solicitud" not in df_base.columns:
        return pd.DataFrame()

    base = df_base.copy()
    base["fecha_solicitud"] = pd.to_datetime(base["fecha_solicitud"], errors="coerce")
    base = base.dropna(subset=["fecha_solicitud"])
    if base.empty:
        return pd.DataFrame()

    base["cumple_kpi"] = base["cumple_kpi"].fillna(False).astype(bool)
    base["_sin_respuesta"] = base["fecha_respuesta"].isna() if "fecha_respuesta" in base.columns else False
    base["_reiteraciones"] = calcular_reiteraciones_total_operacional(base)
    base["_periodo_orden"] = base["fecha_solicitud"].dt.to_period("M").dt.to_timestamp()
    base["_periodo_label"] = base["_periodo_orden"].map(etiqueta_mes_fecha)
    resumen = (
        base.groupby(["_periodo_orden", "_periodo_label"], as_index=False)
        .agg(
            solicitudes=("cumple_kpi", "size"),
            cumple=("cumple_kpi", "sum"),
            sin_respuesta=("_sin_respuesta", "sum"),
            reiteraciones=("_reiteraciones", "sum"),
            promedio_min=("minutos_habiles", "mean"),
        )
        .sort_values("_periodo_orden")
    )
    resumen["no_cumple"] = resumen["solicitudes"] - resumen["cumple"]
    resumen["cumplimiento_pct"] = (resumen["cumple"] / resumen["solicitudes"].clip(lower=1) * 100).round(1)
    resumen["promedio_min"] = resumen["promedio_min"].round(1)
    return resumen


def grafico_disponibilidad_mensual(resumen):
    fig_disp = go.Figure()
    categorias = resumen["_periodo_label"].tolist() if len(resumen) else []

    if len(resumen):
        resumen = resumen.copy()
        resumen["promedio_min"] = resumen["promedio_min"].fillna(0)
        max_solicitudes = max(float(resumen["solicitudes"].max()), 1.0)
        resumen["_marker_size"] = 16 + (resumen["solicitudes"] / max_solicitudes * 18)
        colores = [VERDE if valor >= DISPONIBILIDAD_META_PCT else ROSADO for valor in resumen["cumplimiento_pct"]]
        fig_disp.add_trace(go.Scatter(
            x=resumen["_periodo_label"],
            y=resumen["cumplimiento_pct"],
            mode="lines+markers+text",
            name="Cumplimiento KPI",
            fill="tozeroy",
            fillcolor=rgba(CELESTE, 0.13),
            line=dict(color=CELESTE, width=4.2, shape="spline", smoothing=0.7),
            marker=dict(
                size=resumen["_marker_size"],
                color=colores,
                line=dict(color="#EAFBFF", width=2.2),
                opacity=0.92,
            ),
            text=[f"{v:.1f}%" for v in resumen["cumplimiento_pct"]],
            textposition="top center",
            textfont=dict(size=12, color=CELESTE, family="Segoe UI Black"),
            customdata=resumen[["solicitudes", "cumple", "no_cumple", "sin_respuesta", "reiteraciones", "promedio_min"]].to_numpy(),
            hovertemplate=(
                "<b>%{x}</b><br>"
                "Cumplimiento KPI: <b>%{y:.1f}%</b><br>"
                "Solicitudes: <b>%{customdata[0]}</b><br>"
                "Cumplen KPI: <b>%{customdata[1]}</b><br>"
                "No cumplen: <b>%{customdata[2]}</b><br>"
                "Sin respuesta: <b>%{customdata[3]}</b><br>"
                "Reiteraciones: <b>%{customdata[4]}</b><br>"
                "Promedio habiles: <b>%{customdata[5]:.1f} min</b>"
                "<extra></extra>"
            ),
        ))
        fig_disp.add_trace(go.Scatter(
            x=resumen["_periodo_label"],
            y=[DISPONIBILIDAD_META_PCT] * len(resumen),
            mode="lines",
            name=f"Meta KPI {DISPONIBILIDAD_META_PCT}%",
            line=dict(color=VERDE, width=2.5, dash="dot"),
            hovertemplate=f"<b>%{{x}}</b><br>Meta KPI: <b>{DISPONIBILIDAD_META_PCT}%</b><extra></extra>",
        ))

    fig_disp.add_annotation(
        xref="paper",
        x=1,
        yref="y",
        y=DISPONIBILIDAD_META_PCT,
        xanchor="right",
        yanchor="bottom",
        text=f"<b>Meta {DISPONIBILIDAD_META_PCT}% <= {DISPONIBILIDAD_SLA_MIN} min habiles</b>",
        showarrow=False,
        font=dict(size=12, color=VERDE, family="Segoe UI Black"),
        bgcolor="rgba(6,18,34,0.82)",
        bordercolor=rgba(VERDE, 0.42),
        borderwidth=1,
        borderpad=4,
    )
    fig_disp.update_layout(
        title=dict(
            text=f"<b>Cumplimiento mensual de disponibilidad {SERVICIO_TITULO}</b><br><span style='font-size:12px;color:#BDEFFF'>Solicitudes CECOM respondidas por {SERVICIO_TITULO} dentro de {DISPONIBILIDAD_SLA_MIN} minutos habiles</span>",
            x=0.02,
            xanchor="left",
            font=dict(size=18, color="#DDFBFF", family="Segoe UI Semibold")
        ),
        height=390,
        margin=dict(l=54, r=70, t=88, b=52),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(6,18,34,0.74)",
        legend=dict(
            orientation="h",
            x=0.5,
            xanchor="center",
            y=1.04,
            yanchor="bottom",
            bgcolor="rgba(6,18,34,0.82)",
            bordercolor="rgba(46,203,242,0.38)",
            borderwidth=1,
            font=dict(size=12, color="#EAFBFF", family="Segoe UI Semibold"),
        ),
        hovermode="x unified",
        hoverlabel=dict(bgcolor="rgba(6,18,34,0.96)", bordercolor="rgba(46,203,242,0.40)", font=dict(size=12, family="Segoe UI", color="#EAFBFF")),
        transition=dict(duration=0),
    )
    fig_disp.update_xaxes(
        title=None,
        type="category",
        categoryorder="array",
        categoryarray=categorias,
        tickangle=-14,
        showgrid=False,
        zeroline=False,
        automargin=True,
        tickfont=dict(size=12, color="#BDEFFF", family="Segoe UI Semibold")
    )
    fig_disp.update_yaxes(
        title=dict(text="% cumplimiento KPI", font=dict(size=12, color="#BDEFFF", family="Segoe UI Semibold")),
        range=[0, 105],
        ticksuffix="%",
        showgrid=True,
        gridcolor="rgba(143,239,255,0.14)",
        zeroline=False,
        tickfont=dict(size=12, color="#BDEFFF", family="Segoe UI Semibold")
    )
    return fig_disp


def preparar_resumen_mensual_disponibilidad_servicio(df_base):
    if df_base.empty or "fecha_solicitud" not in df_base.columns or "servicio_tecnico" not in df_base.columns:
        return pd.DataFrame()

    base = df_base.copy()
    base["fecha_solicitud"] = pd.to_datetime(base["fecha_solicitud"], errors="coerce")
    base = base.dropna(subset=["fecha_solicitud"])
    if base.empty:
        return pd.DataFrame()

    base["servicio_tecnico"] = base["servicio_tecnico"].fillna("Sin dato").astype(str).str.strip().replace({"": "Sin dato"})
    base["cumple_kpi"] = base["cumple_kpi"].fillna(False).astype(bool)
    base["_periodo_orden"] = base["fecha_solicitud"].dt.to_period("M").dt.to_timestamp()
    base["_periodo_label"] = base["_periodo_orden"].map(etiqueta_mes_fecha)
    resumen = (
        base.groupby(["_periodo_orden", "_periodo_label", "servicio_tecnico"], as_index=False)
        .agg(
            solicitudes=("cumple_kpi", "size"),
            cumple=("cumple_kpi", "sum"),
        )
        .sort_values(["_periodo_orden", "servicio_tecnico"])
    )
    resumen["no_cumple"] = resumen["solicitudes"] - resumen["cumple"]
    resumen["cumplimiento_pct"] = (resumen["cumple"] / resumen["solicitudes"].clip(lower=1) * 100).round(1)
    return resumen


def grafico_disponibilidad_mensual_servicio(resumen):
    if resumen.empty:
        return figura_disponibilidad_vacia("Disponibilidad comparativa", "No hay solicitudes para comparar por contratista")

    fig = go.Figure()
    categorias = (
        resumen[["_periodo_orden", "_periodo_label"]]
        .drop_duplicates()
        .sort_values("_periodo_orden")["_periodo_label"]
        .tolist()
    )
    colores_servicio = {"IBM": CELESTE, "SAO": ROSADO, "ECC": NARANJO}
    for servicio, datos in resumen.groupby("servicio_tecnico", dropna=False):
        datos = datos.sort_values("_periodo_orden")
        color = colores_servicio.get(str(servicio).upper(), "#8FA7FF")
        fig.add_trace(go.Scatter(
            x=datos["_periodo_label"],
            y=datos["cumplimiento_pct"],
            mode="lines+markers+text",
            name=str(servicio),
            line=dict(color=color, width=3.8, shape="spline", smoothing=0.65),
            marker=dict(size=13, color=color, line=dict(color="#EAFBFF", width=1.8)),
            text=[f"{v:.0f}%" for v in datos["cumplimiento_pct"]],
            textposition="top center",
            textfont=dict(size=11, color=color, family="Segoe UI Black"),
            customdata=datos[["solicitudes", "cumple", "no_cumple"]].to_numpy(),
            hovertemplate=(
                "%{fullData.name}<br><b>%{x}</b><br>"
                "Cumplimiento: <b>%{y:.1f}%</b><br>"
                "Solicitudes: <b>%{customdata[0]}</b><br>"
                "Cumplen: <b>%{customdata[1]}</b><br>"
                "No cumplen: <b>%{customdata[2]}</b><extra></extra>"
            ),
        ))
    fig.add_hline(
        y=DISPONIBILIDAD_META_PCT,
        line_dash="dot",
        line_width=2.6,
        line_color=VERDE,
        annotation_text=f"Meta {DISPONIBILIDAD_META_PCT}%",
        annotation_position="top left",
        annotation_font=dict(size=12, color=VERDE, family="Segoe UI Black"),
    )
    fig.update_layout(
        title=dict(
            text=f"<b>Disponibilidad comparativa por contratista</b><br><span style='font-size:12px;color:#BDEFFF'>Vista Todo: cada linea mide su propio cumplimiento SLA; ECC no aplica por operar directo con centro de comando</span>",
            x=0.02,
            xanchor="left",
            font=dict(size=18, color="#DDFBFF", family="Segoe UI Semibold"),
        ),
        height=400,
        margin=dict(l=54, r=78, t=92, b=54),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(6,18,34,0.74)",
        legend=dict(
            orientation="h",
            x=0.5,
            xanchor="center",
            y=1.04,
            yanchor="bottom",
            bgcolor="rgba(6,18,34,0.82)",
            bordercolor="rgba(46,203,242,0.38)",
            borderwidth=1,
            font=dict(size=12, color="#EAFBFF", family="Segoe UI Semibold"),
        ),
        hovermode="x unified",
        hoverlabel=dict(bgcolor="rgba(6,18,34,0.96)", bordercolor="rgba(46,203,242,0.40)", font=dict(size=12, family="Segoe UI", color="#EAFBFF")),
        transition=dict(duration=0),
    )
    fig.update_xaxes(
        title=None,
        type="category",
        categoryorder="array",
        categoryarray=categorias,
        tickangle=-14,
        showgrid=False,
        zeroline=False,
        automargin=True,
        tickfont=dict(size=12, color="#BDEFFF", family="Segoe UI Semibold"),
    )
    fig.update_yaxes(
        title=dict(text="% cumplimiento KPI", font=dict(size=12, color="#BDEFFF", family="Segoe UI Semibold")),
        range=[0, 105],
        ticksuffix="%",
        showgrid=True,
        gridcolor="rgba(143,239,255,0.14)",
        zeroline=False,
        tickfont=dict(size=12, color="#BDEFFF", family="Segoe UI Semibold"),
    )
    return fig


def grafico_disponibilidad_servicio(df_base):
    if df_base.empty or "servicio_tecnico" not in df_base.columns or "cumple_kpi" not in df_base.columns:
        return figura_disponibilidad_vacia("Comparativo por servicio tecnico")

    base = df_base.copy()
    base["servicio_tecnico"] = base["servicio_tecnico"].fillna("Sin dato").astype(str).str.strip().replace({"": "Sin dato"})
    base["_cumple_bool"] = base["cumple_kpi"].fillna(False).astype(bool)
    if "fecha_respuesta" in base.columns:
        fecha_respuesta = pd.to_datetime(base["fecha_respuesta"], errors="coerce")
    else:
        fecha_respuesta = pd.Series(pd.NaT, index=base.index)

    resumen = (
        base.groupby("servicio_tecnico", dropna=False)
        .agg(
            solicitudes=("servicio_tecnico", "size"),
            cumple=("_cumple_bool", "sum"),
            sin_respuesta=("servicio_tecnico", lambda s: int(fecha_respuesta.loc[s.index].isna().sum())),
        )
        .reset_index()
    )
    if resumen.empty:
        return figura_disponibilidad_vacia("Comparativo por servicio tecnico")

    resumen["cumplimiento_pct"] = (resumen["cumple"] / resumen["solicitudes"].replace(0, pd.NA) * 100).fillna(0)
    resumen["fuera_sla"] = resumen["solicitudes"] - resumen["cumple"]
    resumen = resumen.sort_values(["cumplimiento_pct", "solicitudes"], ascending=[True, False])
    colores = [VERDE if pct >= DISPONIBILIDAD_META_PCT else ROSADO for pct in resumen["cumplimiento_pct"]]

    fig_servicio = go.Figure(go.Bar(
        x=resumen["cumplimiento_pct"],
        y=resumen["servicio_tecnico"],
        orientation="h",
        marker=dict(color=colores, line=dict(color="rgba(255,255,255,.45)", width=1)),
        text=[
            f"{pct:.1f}% | {int(total)} sol. | {int(fuera)} fuera SLA"
            for pct, total, fuera in zip(resumen["cumplimiento_pct"], resumen["solicitudes"], resumen["fuera_sla"])
        ],
        textposition="outside",
        cliponaxis=False,
        customdata=resumen[["solicitudes", "cumple", "fuera_sla", "sin_respuesta"]].to_numpy(),
        hovertemplate=(
            "%{y}<br>Cumplimiento: <b>%{x:.1f}%</b><br>"
            "Solicitudes: <b>%{customdata[0]}</b><br>"
            "Cumplen: <b>%{customdata[1]}</b><br>"
            "Fuera SLA: <b>%{customdata[2]}</b><br>"
            "Sin respuesta: <b>%{customdata[3]}</b><extra></extra>"
        ),
    ))
    fig_servicio.add_shape(
        type="line",
        x0=DISPONIBILIDAD_META_PCT,
        x1=DISPONIBILIDAD_META_PCT,
        y0=-0.5,
        y1=max(len(resumen) - 0.5, 0.5),
        line=dict(color=VERDE, width=2, dash="dot"),
    )
    fig_servicio.add_annotation(
        x=DISPONIBILIDAD_META_PCT,
        y=max(len(resumen) - 0.5, 0.5),
        text=f"Meta {DISPONIBILIDAD_META_PCT}%",
        showarrow=False,
        xanchor="left",
        yanchor="bottom",
        font=dict(size=11, color=VERDE, family="Segoe UI Semibold"),
    )
    fig_servicio.update_layout(
        template="plotly_dark",
        height=280,
        margin=dict(l=78, r=120, t=80, b=44),
        paper_bgcolor="rgba(2,8,23,0)",
        plot_bgcolor="rgba(2,8,23,.34)",
        title=dict(
            text="<b>Comparativo de disponibilidad por contratista</b><br><span style='font-size:12px;color:#BDEFFF'>Visible al seleccionar Todo: quien responde mejor y quien concentra fuera de SLA</span>",
            font=dict(size=18, color="#EAFBFF", family="Segoe UI Semibold"),
            x=0.02,
        ),
        xaxis=dict(
            title=dict(text="% cumplimiento KPI", font=dict(size=12, color="#BDEFFF")),
            range=[0, max(100, float(resumen["cumplimiento_pct"].max()) + 14)],
            ticksuffix="%",
            gridcolor="rgba(189,239,255,.12)",
            zeroline=False,
            fixedrange=True,
        ),
        yaxis=dict(title=None, fixedrange=True),
        showlegend=False,
    )
    return fig_servicio


def grafico_disponibilidad_dimension(df_base, dimension, titulo):
    if df_base.empty or dimension not in df_base.columns:
        return go.Figure()

    base = df_base.copy()
    base[dimension] = base[dimension].fillna("Sin dato").astype(str).str.strip().replace({"": "Sin dato"})
    base["cumple_kpi"] = base["cumple_kpi"].fillna(False).astype(bool)
    resumen = (
        base.groupby(dimension, dropna=False)
        .agg(
            solicitudes=("cumple_kpi", "size"),
            cumple=("cumple_kpi", "sum"),
            promedio_min=("minutos_habiles", "mean"),
        )
        .reset_index()
    )
    resumen["cumplimiento_pct"] = (resumen["cumple"] / resumen["solicitudes"].clip(lower=1) * 100).round(1)
    resumen["no_cumple"] = resumen["solicitudes"] - resumen["cumple"]
    resumen["promedio_min"] = resumen["promedio_min"].fillna(0).round(1)
    resumen = resumen.sort_values(["cumplimiento_pct", "solicitudes"], ascending=[True, False]).head(10)
    resumen = resumen.sort_values("cumplimiento_pct", ascending=True)
    colores = [VERDE if valor >= DISPONIBILIDAD_META_PCT else ROSADO for valor in resumen["cumplimiento_pct"]]
    max_solicitudes = max(float(resumen["solicitudes"].max()), 1.0)
    marker_sizes = 16 + (resumen["solicitudes"] / max_solicitudes * 22)

    fig_dim = go.Figure(go.Scatter(
        x=resumen["cumplimiento_pct"],
        y=resumen[dimension].map(lambda valor: nombre_corto_leyenda(valor, 34)),
        mode="markers+text",
        marker=dict(
            size=marker_sizes,
            color=[rgba(color, 0.86) for color in colores],
            line=dict(color=colores, width=2.2),
            symbol="circle",
            opacity=0.94,
        ),
        text=[f"{pct:.1f}% | {int(total)} sol." for pct, total in zip(resumen["cumplimiento_pct"], resumen["solicitudes"])],
        textposition="middle right",
        textfont=dict(size=11, color="#EAFBFF", family="Segoe UI Semibold"),
        customdata=resumen[["solicitudes", "cumple", "no_cumple", "promedio_min"]].to_numpy(),
        hovertemplate=(
            "%{y}<br>"
            "Cumplimiento KPI: <b>%{x:.1f}%</b><br>"
            "Solicitudes: <b>%{customdata[0]}</b><br>"
            "Cumplen KPI: <b>%{customdata[1]}</b><br>"
            "No cumplen: <b>%{customdata[2]}</b><br>"
            "Promedio habiles: <b>%{customdata[3]:.1f} min</b>"
            "<extra></extra>"
        ),
        showlegend=False,
    ))
    fig_dim.add_vline(x=DISPONIBILIDAD_META_PCT, line=dict(color=VERDE, width=2.2, dash="dot"))
    fig_dim.update_layout(
        title=dict(
            text=f"<b>{titulo}</b><br><span style='font-size:12px;color:#BDEFFF'>Top critico filtrado por menor cumplimiento | meta {DISPONIBILIDAD_META_PCT}%</span>",
            x=0.02,
            xanchor="left",
            font=dict(size=17, color="#DDFBFF", family="Segoe UI Semibold")
        ),
        height=340,
        margin=dict(l=158, r=52, t=82, b=42),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(6,18,34,0.74)",
        hoverlabel=dict(bgcolor="rgba(6,18,34,0.96)", bordercolor="rgba(46,203,242,0.40)", font=dict(size=12, family="Segoe UI", color="#EAFBFF")),
    )
    fig_dim.update_xaxes(
        title=None,
        range=[0, 110],
        ticksuffix="%",
        showgrid=True,
        gridcolor="rgba(143,239,255,0.14)",
        zeroline=False,
        tickfont=dict(size=12, color="#BDEFFF", family="Segoe UI Semibold")
    )
    fig_dim.update_yaxes(
        title=None,
        automargin=True,
        tickfont=dict(size=11, color="#EAFBFF", family="Segoe UI Semibold")
    )
    return fig_dim


def grafico_disponibilidad_region_operacional(df_base):
    if df_base.empty or not {"region", "cumple_kpi"}.issubset(df_base.columns):
        return figura_disponibilidad_vacia("Cumplimiento por region operacional")

    orden_regiones = ["Region de Tarapaca", "Region de Antofagasta"]
    base = df_base.copy()
    base["region"] = base["region"].fillna("").astype(str).str.strip()
    if SERVICIO_ACTUAL == "IBM":
        base = base.loc[base["region"].isin(orden_regiones)].copy()
    else:
        base = base.loc[base["region"].ne("") & base["region"].ne("Sin zona")].copy()
    if base.empty:
        return figura_disponibilidad_vacia("Cumplimiento por region operacional")

    base["_cumple"] = base["cumple_kpi"].fillna(False).astype(bool)
    base["_sin_respuesta"] = base["fecha_respuesta"].isna() if "fecha_respuesta" in base.columns else False
    base["_reiteraciones"] = calcular_reiteraciones_total_operacional(base)

    resumen = (
        base.groupby("region", dropna=False)
        .agg(
            solicitudes=("_cumple", "size"),
            cumple=("_cumple", "sum"),
            sin_respuesta=("_sin_respuesta", "sum"),
            reiteraciones=("_reiteraciones", "sum"),
        )
        .reset_index()
    )
    resumen["no_cumple"] = resumen["solicitudes"] - resumen["cumple"]
    resumen["cumplimiento_pct"] = (resumen["cumple"] / resumen["solicitudes"].clip(lower=1) * 100).round(1)
    resumen["brecha_meta"] = (resumen["cumplimiento_pct"] - DISPONIBILIDAD_META_PCT).round(1)
    if SERVICIO_ACTUAL == "IBM":
        regiones_presentes = [region for region in orden_regiones if region in set(resumen["region"])]
        resumen = resumen.set_index("region").loc[regiones_presentes].reset_index()
    else:
        resumen = resumen.sort_values(["cumplimiento_pct", "solicitudes"], ascending=[True, False]).head(10)

    max_total = max(float(resumen["solicitudes"].max()), 1.0)
    etiqueta_ratio = [
        f"{pct:.1f}% KPI<br>{int(total)} sol."
        for pct, total in zip(resumen["cumplimiento_pct"], resumen["solicitudes"])
    ]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Cumplen",
        x=resumen["region"],
        y=resumen["cumple"],
        marker=dict(color=rgba(VERDE, 0.82), line=dict(color=VERDE, width=1.6)),
        cliponaxis=False,
        customdata=resumen[["solicitudes", "cumplimiento_pct", "sin_respuesta", "reiteraciones", "brecha_meta"]].to_numpy(),
        hovertemplate=(
            "%{x}<br>"
            "Cumplen: <b>%{y}</b><br>"
            "Solicitudes: <b>%{customdata[0]}</b><br>"
            "Cumplimiento: <b>%{customdata[1]:.1f}%</b><br>"
            "Sin respuesta: <b>%{customdata[2]}</b><br>"
            "Reiteraciones: <b>%{customdata[3]}</b><br>"
            "Brecha meta: <b>%{customdata[4]:+.1f} pp</b>"
            "<extra></extra>"
        ),
    ))
    fig.add_trace(go.Bar(
        name="No cumplen",
        x=resumen["region"],
        y=resumen["no_cumple"],
        marker=dict(color=rgba(ROSADO, 0.82), line=dict(color=ROSADO, width=1.6)),
        cliponaxis=False,
        customdata=resumen[["solicitudes", "cumplimiento_pct", "sin_respuesta", "reiteraciones", "brecha_meta"]].to_numpy(),
        hovertemplate=(
            "%{x}<br>"
            "No cumplen: <b>%{y}</b><br>"
            "Solicitudes: <b>%{customdata[0]}</b><br>"
            "Cumplimiento: <b>%{customdata[1]:.1f}%</b><br>"
            "Sin respuesta: <b>%{customdata[2]}</b><br>"
            "Reiteraciones: <b>%{customdata[3]}</b><br>"
            "Brecha meta: <b>%{customdata[4]:+.1f} pp</b>"
            "<extra></extra>"
        ),
    ))
    fig.add_trace(go.Scatter(
        x=resumen["region"],
        y=resumen["solicitudes"] + max_total * 0.08,
        mode="text",
        text=etiqueta_ratio,
        textfont=dict(size=13, color="#EAFBFF", family="Segoe UI Semibold"),
        hoverinfo="skip",
        showlegend=False,
    ))
    fig.update_layout(
        title=dict(
            text=f"<b>Cumplimiento por region operacional</b><br><span style='font-size:12px;color:#BDEFFF'>{'Solo Tarapaca y Antofagasta' if SERVICIO_ACTUAL == 'IBM' else 'Top regiones/zona filtradas'} | meta {DISPONIBILIDAD_META_PCT}% | SLA {DISPONIBILIDAD_SLA_MIN} min habiles</span>",
            x=0.02,
            xanchor="left",
            font=dict(size=17, color="#DDFBFF", family="Segoe UI Semibold")
        ),
        barmode="stack",
        height=330,
        margin=dict(l=42, r=32, t=84, b=54),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(6,18,34,0.74)",
        legend=dict(orientation="h", y=1.15, x=0.56, xanchor="center", font=dict(size=12, color="#EAFBFF", family="Segoe UI Semibold")),
        hoverlabel=dict(bgcolor="rgba(6,18,34,0.96)", bordercolor="rgba(46,203,242,0.40)", font=dict(size=12, family="Segoe UI", color="#EAFBFF")),
        autosize=True,
    )
    fig.update_xaxes(title=None, showgrid=False, zeroline=False, tickfont=dict(size=12, color="#EAFBFF", family="Segoe UI Semibold"))
    fig.update_yaxes(
        title=dict(text="Solicitudes", font=dict(size=12, color="#BDEFFF", family="Segoe UI Semibold")),
        range=[0, max_total * 1.24],
        rangemode="tozero",
        showgrid=True,
        gridcolor="rgba(143,239,255,0.14)",
        zeroline=False,
        tickfont=dict(size=12, color="#BDEFFF", family="Segoe UI Semibold")
    )
    return fig


def preparar_ranking_coordinadores_disponibilidad(df_base):
    columnas_minimas = {"coordinador", "cumple_kpi"}
    if df_base.empty or not columnas_minimas.issubset(df_base.columns):
        return pd.DataFrame()

    base = df_base.copy()
    base["coordinador"] = (
        base["coordinador"]
        .fillna("Sin respuesta")
        .astype(str)
        .str.strip()
        .replace({"": "Sin respuesta"})
    )
    base = base.loc[base["coordinador"].ne("Sin respuesta")].copy()
    if base.empty:
        return pd.DataFrame()

    base["_cumple"] = base["cumple_kpi"].fillna(False).astype(bool)
    base["_exceso"] = serie_numero_segura(base, "exceso_sla_habiles")
    base["_minutos"] = serie_numero_segura(base, "minutos_habiles")
    base["_critico"] = (~base["_cumple"]) & base["_exceso"].gt(0)

    resumen = (
        base.groupby("coordinador", dropna=False)
        .agg(
            total_casos=("_cumple", "size"),
            dentro_sla=("_cumple", "sum"),
            demora_promedio_min=("_minutos", "mean"),
            mayor_desviacion_min=("_exceso", "max"),
            casos_criticos=("_critico", "sum"),
        )
        .reset_index()
    )
    resumen["fuera_sla"] = resumen["total_casos"] - resumen["dentro_sla"]
    resumen["cumplimiento_pct"] = (resumen["dentro_sla"] / resumen["total_casos"].clip(lower=1) * 100).round(1)
    resumen["demora_promedio_min"] = resumen["demora_promedio_min"].fillna(0).round(1)
    resumen["mayor_desviacion_min"] = resumen["mayor_desviacion_min"].fillna(0).round(1)
    return resumen.sort_values(["cumplimiento_pct", "fuera_sla", "total_casos"], ascending=[True, False, False])


def grafico_coordinadores_disponibilidad(df_base):
    resumen = preparar_ranking_coordinadores_disponibilidad(df_base)
    if resumen.empty:
        return figura_disponibilidad_vacia("Ranking coordinadores", "No hay coordinadores con gestion para los filtros seleccionados")

    vista = resumen.sort_values(["cumplimiento_pct", "total_casos"], ascending=[True, False]).head(10)
    vista = vista.sort_values("cumplimiento_pct", ascending=True)
    colores = [VERDE if pct >= DISPONIBILIDAD_META_PCT else ROSADO for pct in vista["cumplimiento_pct"]]

    fig = go.Figure(go.Bar(
        x=vista["cumplimiento_pct"],
        y=vista["coordinador"],
        orientation="h",
        marker=dict(color=[rgba(c, 0.84) for c in colores], line=dict(color=colores, width=1.4)),
        text=[f"{pct:.1f}% | {int(total)} casos" for pct, total in zip(vista["cumplimiento_pct"], vista["total_casos"])],
        textposition="outside",
        cliponaxis=False,
        customdata=vista[["total_casos", "dentro_sla", "fuera_sla", "demora_promedio_min", "mayor_desviacion_min", "casos_criticos"]].to_numpy(),
        hovertemplate=(
            "%{y}<br>"
            "Cumplimiento: <b>%{x:.1f}%</b><br>"
            "Total: <b>%{customdata[0]}</b><br>"
            "Dentro SLA: <b>%{customdata[1]}</b><br>"
            "Fuera SLA: <b>%{customdata[2]}</b><br>"
            "Demora promedio: <b>%{customdata[3]:.1f} min</b><br>"
            "Mayor desviacion: <b>%{customdata[4]:.1f} min</b><br>"
            "Casos criticos: <b>%{customdata[5]}</b>"
            "<extra></extra>"
        ),
    ))
    fig.add_vline(x=DISPONIBILIDAD_META_PCT, line_dash="dot", line_width=2.4, line_color=CELESTE)
    fig.update_layout(
        title=dict(
            text=f"<b>Ranking de coordinadores</b><br><span style='font-size:12px;color:#BDEFFF'>Ordenado de menor a mayor cumplimiento | SLA {DISPONIBILIDAD_SLA_MIN} min habiles</span>",
            x=0.02,
            xanchor="left",
            font=dict(size=17, color="#DDFBFF", family="Segoe UI Semibold")
        ),
        height=360,
        margin=dict(l=178, r=68, t=82, b=42),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(6,18,34,0.74)",
        hoverlabel=dict(bgcolor="rgba(6,18,34,0.96)", bordercolor="rgba(46,203,242,0.40)", font=dict(size=12, family="Segoe UI", color="#EAFBFF")),
    )
    fig.update_xaxes(
        title=None,
        range=[0, 110],
        ticksuffix="%",
        showgrid=True,
        gridcolor="rgba(143,239,255,0.14)",
        zeroline=False,
        tickfont=dict(size=12, color="#BDEFFF", family="Segoe UI Semibold")
    )
    fig.update_yaxes(title=None, automargin=True, tickfont=dict(size=11, color="#EAFBFF", family="Segoe UI Semibold"))
    return fig


def figura_disponibilidad_vacia(titulo, subtitulo="Sin datos para los filtros seleccionados"):
    fig = go.Figure()
    fig.add_annotation(
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        text=f"<b>{titulo}</b><br><span style='font-size:12px;color:#BDEFFF'>{subtitulo}</span>",
        showarrow=False,
        align="center",
        font=dict(size=16, color="#DDFBFF", family="Segoe UI Semibold"),
    )
    fig.update_layout(
        height=330,
        margin=dict(l=24, r=24, t=40, b=30),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(6,18,34,0.74)",
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
    )
    return fig


def grafico_reclamos_motivo(df_base):
    if df_base.empty or "familia_reclamo" not in df_base.columns:
        return figura_disponibilidad_vacia(f"Motivos de reclamo {SERVICIO_TITULO}")

    base = df_base.copy()
    base["familia_reclamo"] = base["familia_reclamo"].fillna("Sin clasificar").astype(str).str.strip().replace({"": "Sin clasificar"})
    resumen = (
        base.groupby("familia_reclamo", dropna=False)
        .agg(
            reclamos=("familia_reclamo", "size"),
            tickets=("ticket_principal", pd.Series.nunique),
        )
        .reset_index()
        .sort_values(["reclamos", "tickets"], ascending=[False, False])
        .head(10)
        .sort_values("reclamos", ascending=True)
    )
    if resumen.empty:
        return figura_disponibilidad_vacia(f"Motivos de reclamo {SERVICIO_TITULO}")

    fig = go.Figure(go.Bar(
        x=resumen["reclamos"],
        y=resumen["familia_reclamo"].map(lambda valor: nombre_corto_leyenda(valor, 34)),
        orientation="h",
        marker=dict(color=rgba(NARANJO, 0.82), line=dict(color=NARANJO, width=1.6)),
        text=[f"{int(rec)} recl. | {int(tkt)} tkt" for rec, tkt in zip(resumen["reclamos"], resumen["tickets"])],
        textposition="outside",
        cliponaxis=False,
        customdata=resumen[["tickets"]].to_numpy(),
        hovertemplate="%{y}<br>Reclamos: <b>%{x}</b><br>Tickets: <b>%{customdata[0]}</b><extra></extra>",
    ))
    fig.update_layout(
        title=dict(
            text=f"<b>Motivos de reclamo {SERVICIO_TITULO}</b><br><span style='font-size:12px;color:#BDEFFF'>Clasificacion por acciones similares de terreno</span>",
            x=0.02,
            xanchor="left",
            font=dict(size=17, color="#DDFBFF", family="Segoe UI Semibold")
        ),
        height=360,
        margin=dict(l=200, r=126, t=82, b=42),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(6,18,34,0.74)",
        hoverlabel=dict(bgcolor="rgba(6,18,34,0.96)", bordercolor="rgba(46,203,242,0.40)", font=dict(size=12, family="Segoe UI", color="#EAFBFF")),
    )
    fig.update_xaxes(title=None, rangemode="tozero", showgrid=True, gridcolor="rgba(143,239,255,0.14)", zeroline=False, tickfont=dict(size=12, color="#BDEFFF", family="Segoe UI Semibold"))
    fig.update_yaxes(title=None, automargin=True, tickfont=dict(size=11, color="#EAFBFF", family="Segoe UI Semibold"))
    return fig


def grafico_reclamos_cliente(df_base):
    if df_base.empty or "cliente" not in df_base.columns:
        return figura_disponibilidad_vacia(f"Clientes con reclamos {SERVICIO_TITULO}")

    base = df_base.copy()
    base["cliente"] = base["cliente"].fillna("Sin dato").astype(str).str.strip().replace({"": "Sin dato"})
    base["_alta"] = base["severidad_reclamo"].astype(str).str.upper().eq("ALTA") if "severidad_reclamo" in base.columns else False
    resumen = (
        base.groupby("cliente", dropna=False)
        .agg(
            reclamos=("cliente", "size"),
            alta=("_alta", "sum"),
            tickets=("ticket_principal", pd.Series.nunique),
        )
        .reset_index()
        .sort_values(["reclamos", "alta"], ascending=[False, False])
        .head(10)
        .sort_values("reclamos", ascending=True)
    )
    if resumen.empty:
        return figura_disponibilidad_vacia(f"Clientes con reclamos {SERVICIO_TITULO}")

    fig = go.Figure(go.Bar(
        x=resumen["reclamos"],
        y=resumen["cliente"].map(lambda valor: nombre_corto_leyenda(valor, 32)),
        orientation="h",
        marker=dict(color=rgba(ROSADO, 0.80), line=dict(color=ROSADO, width=1.6)),
        text=[f"{int(rec)} recl. | {int(tkt)} tkt" for rec, tkt in zip(resumen["reclamos"], resumen["tickets"])],
        textposition="outside",
        cliponaxis=False,
        customdata=resumen[["tickets", "alta"]].to_numpy(),
        hovertemplate="%{y}<br>Reclamos: <b>%{x}</b><br>Tickets: <b>%{customdata[0]}</b><br>Foco cliente: <b>%{y}</b><extra></extra>",
    ))
    fig.update_layout(
        title=dict(
            text="<b>Clientes afectados por reclamos</b><br><span style='font-size:12px;color:#BDEFFF'>Foco ejecutivo por volumen y recurrencia</span>",
            x=0.02,
            xanchor="left",
            font=dict(size=17, color="#DDFBFF", family="Segoe UI Semibold")
        ),
        height=360,
        margin=dict(l=188, r=118, t=82, b=42),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(6,18,34,0.74)",
        hoverlabel=dict(bgcolor="rgba(6,18,34,0.96)", bordercolor="rgba(46,203,242,0.40)", font=dict(size=12, family="Segoe UI", color="#EAFBFF")),
    )
    fig.update_xaxes(title=None, rangemode="tozero", showgrid=True, gridcolor="rgba(143,239,255,0.14)", zeroline=False, tickfont=dict(size=12, color="#BDEFFF", family="Segoe UI Semibold"))
    fig.update_yaxes(title=None, automargin=True, tickfont=dict(size=11, color="#EAFBFF", family="Segoe UI Semibold"))
    return fig


def grafico_reclamos_servicio(df_base, df_atenciones_base=None):
    if df_base.empty or "servicio_tecnico" not in df_base.columns:
        return figura_disponibilidad_vacia("Reclamos por servicio")

    base = df_base.copy()
    base["servicio_tecnico"] = base["servicio_tecnico"].fillna("Sin dato").astype(str).str.strip().replace({"": "Sin dato"})
    base["_alta"] = base["severidad_reclamo"].astype(str).str.upper().eq("ALTA") if "severidad_reclamo" in base.columns else False
    base["_reforzamiento"] = serie_bool_panel(base["reforzamiento"]) if "reforzamiento" in base.columns else False
    resumen = (
        base.groupby("servicio_tecnico", dropna=False)
        .agg(
            reclamos=("servicio_tecnico", "size"),
            alta=("_alta", "sum"),
            reforzamientos=("_reforzamiento", "sum"),
            tickets=("ticket_principal", pd.Series.nunique),
        )
        .reset_index()
    )
    if resumen.empty:
        return figura_disponibilidad_vacia("Reclamos por servicio")

    if df_atenciones_base is not None and not df_atenciones_base.empty and "servicio_tecnico" in df_atenciones_base.columns:
        atenciones = (
            df_atenciones_base.copy()
            .assign(servicio_tecnico=lambda df_tmp: df_tmp["servicio_tecnico"].fillna("Sin dato").astype(str).str.strip().replace({"": "Sin dato"}))
            .groupby("servicio_tecnico", dropna=False)
            .size()
            .reset_index(name="atenciones_asignadas")
        )
        resumen = resumen.merge(atenciones, on="servicio_tecnico", how="left")
    else:
        resumen["atenciones_asignadas"] = pd.NA
    resumen["atenciones_asignadas"] = pd.to_numeric(resumen["atenciones_asignadas"], errors="coerce").fillna(0).astype(int)
    resumen["reclamos_por_100"] = (
        resumen["reclamos"] / resumen["atenciones_asignadas"].replace(0, pd.NA) * 100
    ).fillna(resumen["reclamos"]).round(1)
    usar_tasa = resumen["atenciones_asignadas"].gt(0).any()
    resumen = resumen.sort_values("reclamos_por_100" if usar_tasa else "reclamos", ascending=True)

    colores = [CELESTE if servicio == "IBM" else ROSADO if servicio == "SAO" else NARANJO for servicio in resumen["servicio_tecnico"]]
    fig = go.Figure(go.Bar(
        x=resumen["reclamos_por_100"] if usar_tasa else resumen["reclamos"],
        y=resumen["servicio_tecnico"],
        orientation="h",
        marker=dict(color=[rgba(color, 0.82) for color in colores], line=dict(color=colores, width=1.8)),
        text=[
            f"{valor:.1f}/100 aten. | {int(rec)} señales"
            if usar_tasa else f"{int(rec)} señales"
            for valor, rec, alta in zip(resumen["reclamos_por_100"], resumen["reclamos"], resumen["alta"])
        ],
        textposition="outside",
        cliponaxis=False,
        customdata=resumen[["reclamos", "tickets", "alta", "atenciones_asignadas", "reforzamientos"]].to_numpy(),
        hovertemplate=(
            "%{y}<br>"
            + ("Reclamos por 100 atenciones: <b>%{x:.1f}</b><br>" if usar_tasa else "")
            + "Señales: <b>%{customdata[0]}</b><br>"
            + "Reforzamientos: <b>%{customdata[4]}</b><br>"
            + "Tickets con reclamo: <b>%{customdata[1]}</b><br>"
            + "Atenciones asignadas: <b>%{customdata[3]}</b><extra></extra>"
        ),
    ))
    fig.update_layout(
        title=dict(
            text=(
                "<b>Comparativo de reclamos por contratista</b><br>"
                "<span style='font-size:12px;color:#BDEFFF'>Reclamos + reforzamientos normalizados por 100 atenciones asignadas del periodo filtrado</span>"
            ),
            x=0.02,
            xanchor="left",
            font=dict(size=17, color="#DDFBFF", family="Segoe UI Semibold")
        ),
        height=300,
        margin=dict(l=102, r=132, t=82, b=42),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(6,18,34,0.74)",
        hoverlabel=dict(bgcolor="rgba(6,18,34,0.96)", bordercolor="rgba(46,203,242,0.40)", font=dict(size=12, family="Segoe UI", color="#EAFBFF")),
    )
    fig.update_xaxes(title="Señales por 100 atenciones" if usar_tasa else None, rangemode="tozero", showgrid=True, gridcolor="rgba(143,239,255,0.14)", zeroline=False, tickfont=dict(size=12, color="#BDEFFF", family="Segoe UI Semibold"))
    fig.update_yaxes(title=None, automargin=True, tickfont=dict(size=12, color="#EAFBFF", family="Segoe UI Semibold"))
    return fig


def grafico_reiteraciones_ticket_disponibilidad(df_base):
    if df_base.empty or "numero_ticket" not in df_base.columns:
        return figura_disponibilidad_vacia("Tickets con reiteraciones totales")

    base = df_base.copy()
    base["numero_ticket"] = base["numero_ticket"].fillna("Sin ticket").astype(str).str.strip().replace({"": "Sin ticket"})
    base["cliente"] = base["cliente"].fillna("Sin dato").astype(str).str.strip().replace({"": "Sin dato"}) if "cliente" in base.columns else "Sin dato"
    base["_reiteraciones"] = calcular_reiteraciones_total_operacional(base)
    base["_solicitud_caso_n"] = pd.to_numeric(base["solicitud_caso_n"], errors="coerce").fillna(1) if "solicitud_caso_n" in base.columns else 1
    base["_total_solicitudes_caso"] = pd.to_numeric(base["total_solicitudes_caso"], errors="coerce").fillna(1) if "total_solicitudes_caso" in base.columns else 1
    base["_cumple"] = base["cumple_kpi"].fillna(False).astype(bool) if "cumple_kpi" in base.columns else False
    base["_minutos"] = pd.to_numeric(base["minutos_habiles"], errors="coerce") if "minutos_habiles" in base.columns else pd.NA
    base["_sin_respuesta"] = base["fecha_respuesta"].isna() if "fecha_respuesta" in base.columns else False

    resumen = (
        base.groupby(["numero_ticket", "cliente"], dropna=False)
        .agg(
            solicitudes=("_cumple", "size"),
            reiteraciones=("_reiteraciones", "sum"),
            cumple=("_cumple", "sum"),
            demora_max=("_minutos", "max"),
            sin_respuesta=("_sin_respuesta", "sum"),
            solicitudes_caso=("_total_solicitudes_caso", "max"),
        )
        .reset_index()
    )
    resumen["no_cumple"] = resumen["solicitudes"] - resumen["cumple"]
    resumen["presion_total"] = resumen["reiteraciones"]
    resumen = (
        resumen.loc[resumen["presion_total"].gt(0)]
        .sort_values(["presion_total", "no_cumple", "solicitudes"], ascending=[False, False, False])
        .head(10)
        .sort_values("presion_total", ascending=True)
    )
    if resumen.empty:
        return figura_disponibilidad_vacia("Tickets con reiteraciones totales", "No se detectan re-insistencias en los filtros")

    resumen["_label"] = resumen.apply(
        lambda row: nombre_corto_leyenda(f"{row['numero_ticket']} | {row['cliente']}", 42),
        axis=1,
    )
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=resumen["presion_total"],
        y=resumen["_label"],
        name="Reiteraciones totales",
        orientation="h",
        marker=dict(color=rgba(NARANJO, 0.84), line=dict(color=NARANJO, width=1.4)),
        cliponaxis=False,
        customdata=resumen[["solicitudes", "solicitudes_caso", "no_cumple", "sin_respuesta", "demora_max", "presion_total"]].to_numpy(),
        hovertemplate=(
            "%{y}<br>"
            "Reiteraciones totales: <b>%{x}</b><br>"
            "Solicitudes medidas: <b>%{customdata[0]}</b><br>"
            "Solicitudes del caso: <b>%{customdata[1]}</b><br>"
            "No cumplen: <b>%{customdata[2]}</b><br>"
            "Sin respuesta: <b>%{customdata[3]}</b><br>"
            "Mayor demora habil: <b>%{customdata[4]:.1f} min</b>"
            "<extra></extra>"
        ),
    ))
    fig.add_trace(go.Scatter(
        x=resumen["presion_total"] + 0.08,
        y=resumen["_label"],
        mode="text",
        text=[
            f"{int(total)} gest. | {int(sol)} sol. caso"
            for total, sol in zip(resumen["presion_total"], resumen["solicitudes_caso"])
        ],
        textposition="middle right",
        textfont=dict(size=11, color="#EAFBFF", family="Segoe UI Semibold"),
        hoverinfo="skip",
        showlegend=False,
    ))
    fig.update_layout(
        title=dict(
            text=f"<b>Reiteraciones por falta de respuesta {SERVICIO_TITULO}</b><br><span style='font-size:12px;color:#BDEFFF'>Toda insistencia cuenta: CECOM, PRODRIGUEZA, NPEREZC o RRODRIGUEZB</span>",
            x=0.02,
            xanchor="left",
            font=dict(size=17, color="#DDFBFF", family="Segoe UI Semibold")
        ),
        barmode="stack",
        height=max(385, 92 + len(resumen) * 31),
        margin=dict(l=205, r=128, t=86, b=44),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(6,18,34,0.74)",
        legend=dict(orientation="h", y=1.14, x=0.58, xanchor="center", font=dict(size=12, color="#EAFBFF", family="Segoe UI Semibold")),
        hoverlabel=dict(bgcolor="rgba(6,18,34,0.96)", bordercolor="rgba(46,203,242,0.40)", font=dict(size=12, family="Segoe UI", color="#EAFBFF")),
    )
    max_x = max(float(resumen["presion_total"].max()), 1.0)
    fig.update_xaxes(title=None, range=[0, max_x + 0.95], dtick=1, showgrid=True, gridcolor="rgba(143,239,255,0.14)", zeroline=False, tickfont=dict(size=12, color="#BDEFFF", family="Segoe UI Semibold"))
    fig.update_yaxes(title=None, automargin=True, tickfont=dict(size=11, color="#EAFBFF", family="Segoe UI Semibold"))
    return fig


def color_servicio_uso(servicio):
    servicio = str(servicio or "").upper()
    if servicio == "IBM":
        return CELESTE
    if servicio == "SAO":
        return ROSADO
    if servicio == "ECC":
        return NARANJO
    return "#8FA7FF"


def render_uso_herramienta_kpi_cards():
    color_nota = VERDE if uso_promedio >= USO_HERRAMIENTA_META_PCT else CELESTE if uso_promedio >= 80 else ROSADO
    render_kpi_card_grid([
        {"icono": "&#9673;", "titulo": "Nota OT", "valor": f"{uso_promedio:.1f}", "subtitulo": "Auditoria PDF, escala 0 a 100", "color": color_nota, "badge": f"Meta {USO_HERRAMIENTA_META_PCT}", "progreso": uso_promedio},
        {"icono": "&#9606;", "titulo": "OT auditadas", "valor": uso_total, "subtitulo": f"{uso_tecnicos} tecnicos con evidencia", "color": KPI_TOTAL},
        {"icono": "&#10003;", "titulo": "Excelente/Bueno", "valor": f"{uso_pct_ok:.1f}%", "subtitulo": f"{uso_ok} OT con llenado aceptable", "color": VERDE if uso_pct_ok >= 80 else CELESTE, "progreso": uso_pct_ok},
        {"icono": "&#10005;", "titulo": "Criticas", "valor": uso_criticas, "subtitulo": f"{uso_regulares} regulares para corregir", "color": ROSADO if uso_criticas else VERDE},
        {"icono": "&#33;", "titulo": "Retiros incompletos", "valor": uso_retiros_incompletos, "subtitulo": "Sin cables/cargador/accesorios", "color": ROSADO if uso_retiros_incompletos else VERDE},
        {"icono": "&#9673;", "titulo": "CGE sin activo", "valor": uso_cge_sin_activo, "subtitulo": "Activo fijo requerido en CGE", "color": ROSADO if uso_cge_sin_activo else VERDE},
    ])


def preparar_ranking_uso_tecnico(df_base):
    if df_base.empty or "tecnico" not in df_base.columns:
        return pd.DataFrame()
    base = df_base.copy()
    base["tecnico"] = base["tecnico"].fillna("Sin tecnico").astype(str).str.strip().replace({"": "Sin tecnico"})
    base["servicio_tecnico"] = base.get("servicio_tecnico", base.get("st", "Sin dato")).fillna("Sin dato").astype(str).str.strip().replace({"": "Sin dato"})
    base["region_atendida"] = base.get("region_atendida", "").fillna("Sin region").astype(str).str.strip().replace({"": "Sin region"})
    base["_critico"] = base["estado_calidad"].astype(str).eq("Critico") if "estado_calidad" in base.columns else False
    base["_ok"] = base["estado_calidad"].astype(str).isin(["Excelente", "Bueno"]) if "estado_calidad" in base.columns else False
    resumen = (
        base.groupby(["servicio_tecnico", "tecnico", "region_atendida"], dropna=False)
        .agg(
            ots=("tecnico", "size"),
            nota_promedio=("puntaje_total", "mean"),
            ok=("_ok", "sum"),
            criticas=("_critico", "sum"),
        )
        .reset_index()
    )
    if resumen.empty:
        return resumen
    resumen["nota_promedio"] = resumen["nota_promedio"].fillna(0).round(1)
    resumen["pct_ok"] = (resumen["ok"] / resumen["ots"].clip(lower=1) * 100).round(1)
    resumen = resumen.sort_values(["nota_promedio", "pct_ok", "ots"], ascending=[False, False, False]).reset_index(drop=True)
    resumen["ranking_global"] = range(1, len(resumen) + 1)
    return resumen


def preparar_ranking_uso_region(df_base):
    if df_base.empty or "region_atendida" not in df_base.columns:
        return pd.DataFrame()
    base = df_base.copy()
    base["region_atendida"] = base["region_atendida"].fillna("Sin region").astype(str).str.strip().replace({"": "Sin region"})
    base["servicio_tecnico"] = base.get("servicio_tecnico", base.get("st", "Sin dato")).fillna("Sin dato").astype(str).str.strip().replace({"": "Sin dato"})
    base["_critico"] = base["estado_calidad"].astype(str).eq("Critico") if "estado_calidad" in base.columns else False
    resumen = (
        base.groupby(["servicio_tecnico", "region_atendida"], dropna=False)
        .agg(
            ots=("region_atendida", "size"),
            nota_promedio=("puntaje_total", "mean"),
            criticas=("_critico", "sum"),
        )
        .reset_index()
    )
    resumen["nota_promedio"] = resumen["nota_promedio"].fillna(0).round(1)
    return resumen.sort_values(["nota_promedio", "ots"], ascending=[False, False])


def grafico_uso_herramienta_servicio(df_base):
    if df_base.empty or "servicio_tecnico" not in df_base.columns:
        return figura_disponibilidad_vacia("Comparativo Uso de Herramienta")
    base = df_base.copy()
    base["servicio_tecnico"] = base["servicio_tecnico"].fillna("Sin dato").astype(str).str.strip().replace({"": "Sin dato"})
    base["_ok"] = base["estado_calidad"].astype(str).isin(["Excelente", "Bueno"]) if "estado_calidad" in base.columns else False
    base["_critico"] = base["estado_calidad"].astype(str).eq("Critico") if "estado_calidad" in base.columns else False
    resumen = (
        base.groupby("servicio_tecnico", dropna=False)
        .agg(
            ots=("servicio_tecnico", "size"),
            nota_promedio=("puntaje_total", "mean"),
            ok=("_ok", "sum"),
            criticas=("_critico", "sum"),
        )
        .reset_index()
    )
    if resumen.empty:
        return figura_disponibilidad_vacia("Comparativo Uso de Herramienta")
    resumen["nota_promedio"] = resumen["nota_promedio"].fillna(0).round(1)
    resumen["pct_ok"] = (resumen["ok"] / resumen["ots"].clip(lower=1) * 100).round(1)
    resumen = resumen.sort_values("nota_promedio", ascending=True)
    colores = [color_servicio_uso(servicio) for servicio in resumen["servicio_tecnico"]]
    fig = go.Figure(go.Bar(
        x=resumen["nota_promedio"],
        y=resumen["servicio_tecnico"],
        orientation="h",
        marker=dict(color=[rgba(color, 0.84) for color in colores], line=dict(color=colores, width=1.8)),
        text=[f"{nota:.1f} | {int(ots)} OT | {pct:.0f}% OK" for nota, ots, pct in zip(resumen["nota_promedio"], resumen["ots"], resumen["pct_ok"])],
        textposition="outside",
        cliponaxis=False,
        customdata=resumen[["ots", "ok", "criticas", "pct_ok"]].to_numpy(),
        hovertemplate=(
            "%{y}<br>Nota promedio: <b>%{x:.1f}</b><br>"
            "OT auditadas: <b>%{customdata[0]}</b><br>"
            "Excelente/Bueno: <b>%{customdata[1]}</b> (%{customdata[3]:.1f}%)<br>"
            "Criticas: <b>%{customdata[2]}</b><extra></extra>"
        ),
    ))
    fig.add_vline(x=USO_HERRAMIENTA_META_PCT, line_dash="dot", line_width=2.4, line_color=VERDE)
    fig.update_layout(
        title=dict(
            text="<b>Performance comparado por contratista</b><br><span style='font-size:12px;color:#BDEFFF'>Misma regla: calidad de llenado OT, evidencia de equipo, retiro y activo fijo</span>",
            x=0.02,
            xanchor="left",
            font=dict(size=17, color="#DDFBFF", family="Segoe UI Semibold"),
        ),
        height=310,
        margin=dict(l=104, r=138, t=82, b=42),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(6,18,34,0.74)",
        hoverlabel=dict(bgcolor="rgba(6,18,34,0.96)", bordercolor="rgba(46,203,242,0.40)", font=dict(size=12, family="Segoe UI", color="#EAFBFF")),
    )
    fig.update_xaxes(title=None, range=[0, 112], showgrid=True, gridcolor="rgba(143,239,255,0.14)", zeroline=False, tickfont=dict(size=12, color="#BDEFFF", family="Segoe UI Semibold"))
    fig.update_yaxes(title=None, automargin=True, tickfont=dict(size=12, color="#EAFBFF", family="Segoe UI Semibold"))
    return fig


def grafico_uso_herramienta_dispersion_tecnico(df_base):
    if df_base.empty or "tecnico" not in df_base.columns:
        return figura_disponibilidad_vacia("Dispersion por tecnico")
    base = df_base.copy()
    base["tecnico"] = base["tecnico"].fillna("Sin tecnico").astype(str).str.strip().replace({"": "Sin tecnico"})
    base["servicio_tecnico"] = base.get("servicio_tecnico", base.get("st", "Sin dato")).fillna("Sin dato").astype(str).str.strip().replace({"": "Sin dato"})
    base["_fecha_graf"] = pd.to_datetime(base.get("fecha_atencion"), dayfirst=True, errors="coerce")
    base["_fecha_label"] = base["_fecha_graf"].dt.strftime("%d-%m-%Y").fillna("Sin fecha")
    ranking = preparar_ranking_uso_tecnico(base)
    tecnicos_top = ranking.head(14)["tecnico"].tolist() if not ranking.empty else []
    if tecnicos_top:
        base = base.loc[base["tecnico"].isin(tecnicos_top)].copy()
    if base.empty:
        return figura_disponibilidad_vacia("Dispersion por tecnico")

    fig = go.Figure()
    for servicio, datos in base.groupby("servicio_tecnico", dropna=False):
        color = color_servicio_uso(servicio)
        fig.add_trace(go.Scatter(
            x=datos["tecnico"].map(lambda valor: nombre_corto_leyenda(valor, 24)),
            y=datos["puntaje_total"],
            mode="markers",
            name=str(servicio),
            marker=dict(
                size=15,
                color=rgba(color, 0.82),
                line=dict(color=color, width=2),
            ),
            customdata=datos[["folio_ot", "ticket", "_fecha_label", "estado_calidad", "hallazgos"]].to_numpy(),
            hovertemplate=(
                "%{x}<br>Nota OT: <b>%{y:.1f}</b><br>"
                "Folio: <b>%{customdata[0]}</b><br>"
                "Ticket: <b>%{customdata[1]}</b><br>"
                "Fecha: <b>%{customdata[2]}</b><br>"
                "Clasificacion: <b>%{customdata[3]}</b><br>"
                "%{customdata[4]}<extra></extra>"
            ),
        ))
    fig.add_hrect(y0=USO_HERRAMIENTA_META_PCT, y1=100, fillcolor=rgba(VERDE, 0.10), line_width=0, layer="below")
    fig.add_hline(y=USO_HERRAMIENTA_META_PCT, line_dash="dot", line_width=2.4, line_color=VERDE, annotation_text=f"Meta {USO_HERRAMIENTA_META_PCT}", annotation_position="top left")
    fig.add_hline(y=65, line_dash="dot", line_width=2, line_color=ROSADO, annotation_text="Critico < 65", annotation_position="bottom left")
    fig.update_layout(
        title=dict(
            text="<b>Dispersion de calidad por tecnico</b><br><span style='font-size:12px;color:#BDEFFF'>Cada punto es una OT auditada; permite ver tendencia y variabilidad individual</span>",
            x=0.02,
            xanchor="left",
            font=dict(size=17, color="#DDFBFF", family="Segoe UI Semibold"),
        ),
        height=420,
        margin=dict(l=56, r=126, t=86, b=118),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(6,18,34,0.74)",
        legend=dict(orientation="h", y=1.08, x=0.5, xanchor="center", font=dict(size=12, color="#EAFBFF", family="Segoe UI Semibold")),
        hoverlabel=dict(bgcolor="rgba(6,18,34,0.96)", bordercolor="rgba(46,203,242,0.40)", font=dict(size=12, family="Segoe UI", color="#EAFBFF")),
    )
    fig.update_xaxes(title=None, tickangle=-32, showgrid=False, zeroline=False, automargin=True, tickfont=dict(size=11, color="#BDEFFF", family="Segoe UI Semibold"))
    fig.update_yaxes(title=dict(text="Nota OT", font=dict(size=12, color="#BDEFFF")), range=[0, 105], showgrid=True, gridcolor="rgba(143,239,255,0.14)", zeroline=False, tickfont=dict(size=12, color="#BDEFFF", family="Segoe UI Semibold"))
    return fig


def grafico_uso_herramienta_region(df_base):
    resumen = preparar_ranking_uso_region(df_base)
    if resumen.empty:
        return figura_disponibilidad_vacia("Ranking por region atendida")
    resumen = resumen.sort_values(["nota_promedio", "ots"], ascending=[True, False]).head(14)
    resumen["_label"] = resumen.apply(
        lambda row: nombre_corto_leyenda(f"{row['region_atendida']} | {row['servicio_tecnico']}", 38),
        axis=1,
    )
    colores = [color_servicio_uso(servicio) for servicio in resumen["servicio_tecnico"]]
    fig = go.Figure(go.Bar(
        x=resumen["nota_promedio"],
        y=resumen["_label"],
        orientation="h",
        marker=dict(color=[rgba(color, 0.84) for color in colores], line=dict(color=colores, width=1.6)),
        text=[f"{nota:.1f} | {int(ots)} OT" for nota, ots in zip(resumen["nota_promedio"], resumen["ots"])],
        textposition="outside",
        cliponaxis=False,
        customdata=resumen[["servicio_tecnico", "ots", "criticas"]].to_numpy(),
        hovertemplate="%{y}<br>Nota: <b>%{x:.1f}</b><br>ST: <b>%{customdata[0]}</b><br>OT: <b>%{customdata[1]}</b><br>Criticas: <b>%{customdata[2]}</b><extra></extra>",
    ))
    fig.add_vline(x=USO_HERRAMIENTA_META_PCT, line_dash="dot", line_width=2.4, line_color=VERDE)
    fig.update_layout(
        title=dict(
            text="<b>Ranking por region atendida</b><br><span style='font-size:12px;color:#BDEFFF'>Ordenado desde las regiones que requieren mayor correccion documental</span>",
            x=0.02,
            xanchor="left",
            font=dict(size=17, color="#DDFBFF", family="Segoe UI Semibold"),
        ),
        height=max(360, 90 + len(resumen) * 30),
        margin=dict(l=226, r=110, t=82, b=44),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(6,18,34,0.74)",
        hoverlabel=dict(bgcolor="rgba(6,18,34,0.96)", bordercolor="rgba(46,203,242,0.40)", font=dict(size=12, family="Segoe UI", color="#EAFBFF")),
    )
    fig.update_xaxes(title=None, range=[0, 112], showgrid=True, gridcolor="rgba(143,239,255,0.14)", zeroline=False, tickfont=dict(size=12, color="#BDEFFF", family="Segoe UI Semibold"))
    fig.update_yaxes(title=None, automargin=True, tickfont=dict(size=11, color="#EAFBFF", family="Segoe UI Semibold"))
    return fig


def construir_insights_uso_herramienta_fallback(metricas):
    total_uso = int(metricas.get("uso_total", 0))
    promedio = float(metricas.get("uso_promedio", 0))
    pct_ok = float(metricas.get("uso_pct_ok", 0))
    criticas = int(metricas.get("uso_criticas", 0))
    retiros = int(metricas.get("uso_retiros_incompletos", 0))
    cge_sin_activo = int(metricas.get("uso_cge_sin_activo", 0))
    comparativo = str(metricas.get("comparativo_uso_herramienta_proveedor", "")).strip()

    if total_uso:
        titulo_nota = "Documentacion bajo meta" if promedio < USO_HERRAMIENTA_META_PCT else "Uso de herramienta controlado"
        cuerpo_nota = f"Nota promedio {promedio:.1f} en {total_uso} OT; {pct_ok:.1f}% esta en excelente/bueno."
    else:
        titulo_nota = "Sin auditoria OT"
        cuerpo_nota = "No hay PDF auditados para los filtros actuales o falta actualizar la base OT."

    titulo_riesgo = "Hallazgos documentales"
    cuerpo_riesgo = f"{criticas} OT criticas, {retiros} retiros sin accesorios/cargador y {cge_sin_activo} casos CGE sin activo fijo."

    titulo_comparativo = "Comparativo contratistas"
    cuerpo_comparativo = comparativo or "Actualizar OT permite comparar IBM, SAO y ECC con la misma regla documental."

    return [
        {"indicador": "Nota", "titulo": titulo_nota, "cuerpo": cuerpo_nota, "tono": "mal" if total_uso and promedio < 80 else "accion" if total_uso and promedio < USO_HERRAMIENTA_META_PCT else "bien"},
        {"indicador": "Hallazgos", "titulo": titulo_riesgo, "cuerpo": cuerpo_riesgo, "tono": "mal" if criticas or retiros or cge_sin_activo else "bien"},
        {"indicador": "Contratistas", "titulo": titulo_comparativo, "cuerpo": cuerpo_comparativo, "tono": "accion" if comparativo else "bien"},
    ]


def render_analisis_uso_herramienta(metricas):
    render_analisis_hoja("KPI Uso correcto de herramienta", metricas, construir_insights_uso_herramienta_fallback(metricas))


if mostrar_kpi_inicio:
    render_kpi_card_grid([
        {"icono": "&#9606;", "titulo": "Total asignado", "valor": total, "subtitulo": "Base filtrada vigente", "color": KPI_TOTAL},
        {"icono": "&#9673;", "titulo": "% cumplimiento", "valor": f"{pct:.0f}%", "subtitulo": "Inicio <= 15 min", "color": KPI_CUMPLIMIENTO, "badge": "Meta 80%", "progreso": pct},
        {"icono": "&#10003;", "titulo": "Finalizado 1a visita", "valor": finalizadas_primera_visita, "subtitulo": "Cierre sin visita adicional", "color": KPI_PRIMERA_VISITA, "badge": f"{pct_primera_visita:.0f}%", "progreso": pct_primera_visita},
        {"icono": "&#8635;", "titulo": "Ratio revisitas", "valor": f"{pct_revisitas:.1f}%", "subtitulo": "Tickets con visita adicional", "color": KPI_REVISITA, "badge": revisitas, "progreso": pct_revisitas},
    ])
    render_analisis_inicio({
        "total": total,
        "cumple": cumple,
        "pct": pct,
        "finalizadas": finalizadas,
        "no_finalizadas": no_finalizadas,
        "finalizadas_primera_visita": finalizadas_primera_visita,
        "pct_primera_visita": pct_primera_visita,
        "revisitas": revisitas,
        "pct_revisitas": pct_revisitas,
        "comparativo_inicio_proveedor": comparativo_inicio_proveedor,
    })



if mostrar_kpi_epa:
    st.markdown('<div class="kpi-divider"></div>', unsafe_allow_html=True)

    if True:
        render_kpi_card_grid([
            {"icono": "&#9673;", "titulo": "Satisfaccion EPA", "valor": f"{epa_satisfaccion:.0f}%", "subtitulo": "Nota >= 4 (1 a 5)", "color": VERDE, "badge": "Meta 90%", "progreso": epa_satisfaccion},
            {"icono": "&#10003;", "titulo": "Promedio EPA", "valor": f"{epa_promedio:.1f}", "subtitulo": "Escala 1 a 5", "color": CELESTE, "badge": "Nota", "progreso": epa_promedio * 20},
            {"icono": "&#9606;", "titulo": "Respondidas", "valor": epa_total_respuestas, "subtitulo": "Links completados", "color": AZUL_CLARO},
            {"icono": "&#10005;", "titulo": "Pendientes", "valor": epa_pendientes, "subtitulo": "Links sin respuesta", "color": ROSADO},
        ])
        render_analisis_epa({
            "epa_total_atenciones": epa_total_atenciones,
            "epa_total_respuestas": epa_total_respuestas,
            "epa_pendientes": epa_pendientes,
            "epa_promedio": epa_promedio,
            "epa_satisfechas": epa_satisfechas,
            "epa_satisfaccion": epa_satisfaccion,
            "epa_recomendacion": epa_recomendacion,
        })

        gauge_epa = go.Figure()
        gauge_epa.add_trace(
            go.Indicator(
                mode="gauge+number",
                value=epa_satisfaccion,
                number={"suffix": "%", "font": {"size": 54, "family": "Segoe UI Black", "color": VERDE}},
                title={
                    "text": "<b>Satisfacci\u00f3n EPA</b><br><span style='font-size:0.72em;color:#BDEFFF'>Respuestas con nota promedio >= 4 en escala 1 a 5</span>",
                    "font": {"size": 18, "family": "Segoe UI Semibold", "color": "#DDFBFF"}
                },
                gauge={
                    "axis": {"range": [0, 100], "tickwidth": 0, "tickcolor": "rgba(0,0,0,0)"},
                    "bar": {"color": VERDE, "thickness": 0.24},
                    "bgcolor": "rgba(255,255,255,0.45)",
                    "borderwidth": 0,
                    "steps": [
                        {"range": [0, 60], "color": rgba(ROSADO, 0.13)},
                        {"range": [60, 85], "color": rgba(CELESTE, 0.15)},
                        {"range": [85, 100], "color": rgba(VERDE, 0.18)},
                    ],
                    "threshold": {
                        "line": {"color": ROSADO, "width": 5},
                        "thickness": 0.78,
                        "value": 90,
                    },
                },
                domain={"x": [0.02, 0.48], "y": [0.02, 0.86]},
            )
        )

        titulo_barra_epa = "Promedio EPA por técnico"
        if len(df_epa_respondidas):
            dimension_barra_epa = "servicio_tecnico" if SERVICIO_COMPARATIVO and "servicio_tecnico" in df_epa_respondidas.columns else "tecnico"
            titulo_barra_epa = "Promedio EPA por Servicio Técnico" if dimension_barra_epa == "servicio_tecnico" else "Promedio EPA por técnico"
            por_dimension_epa = (
                df_epa_respondidas.assign(**{
                    dimension_barra_epa: df_epa_respondidas[dimension_barra_epa].fillna("Sin dato").astype(str).str.strip().replace({"": "Sin dato"})
                })
                .groupby(dimension_barra_epa, dropna=False)["promedio"]
                .mean()
                .sort_values(ascending=True)
                .tail(8)
            )
            gauge_epa.add_trace(
                go.Bar(
                    x=por_dimension_epa.values,
                    y=por_dimension_epa.index.astype(str),
                    orientation="h",
                    marker=dict(color=CELESTE, line=dict(color="#FFFFFF", width=1.5)),
                    text=[f"{v:.1f}" for v in por_dimension_epa.values],
                    textposition="outside",
                    cliponaxis=False,
                    hovertemplate="%{y}<br>Promedio EPA: %{x:.2f}<extra></extra>",
                    xaxis="x2",
                    yaxis="y2",
                    showlegend=False,
                )
            )

        gauge_epa.add_shape(
            type="rect",
            x0=0, y0=0, x1=1, y1=1,
            xref="paper", yref="paper",
            fillcolor="rgba(6,18,34,0.82)",
            line=dict(color=rgba(CELESTE, 0.56), width=1.4),
            layer="below"
        )
        gauge_epa.add_shape(
            type="rect",
            x0=0, y0=0.965, x1=1, y1=1,
            xref="paper", yref="paper",
            fillcolor=CELESTE,
            line=dict(width=0),
            layer="below"
        )
        gauge_epa.add_annotation(
            x=0.73, y=0.84,
            xref="paper", yref="paper",
            text=f"<b>{titulo_barra_epa}</b>",
            showarrow=False,
            font=dict(size=16, color="#DDFBFF", family="Segoe UI Semibold")
        )
        gauge_epa.update_layout(
            height=350,
            margin=dict(l=20, r=34, t=42, b=22),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(6,18,34,0.72)",
            xaxis2=dict(
                domain=[0.57, 0.98],
                range=[0, 5],
                showgrid=True,
                gridcolor="rgba(143,239,255,0.14)",
                zeroline=False,
                tickfont=dict(size=11, color="#BDEFFF")
            ),
            yaxis2=dict(
                domain=[0.12, 0.72],
                automargin=True,
                tickfont=dict(size=11, color="#EAFBFF", family="Segoe UI Semibold")
            ),
            showlegend=False
        )

        st.plotly_chart(gauge_epa, use_container_width=True, config=PLOTLY_CONFIG_SOLO_LECTURA)

        if len(df_epa_respondidas):
            if SERVICIO_COMPARATIVO and "servicio_tecnico" in df_epa_respondidas.columns:
                dispersion_servicio = preparar_dispersion_epa(df_epa_respondidas, "servicio_tecnico")
                if len(dispersion_servicio):
                    st.plotly_chart(
                        grafico_dispersion_epa(dispersion_servicio, "servicio_tecnico", "Promedio EPA en el tiempo por Servicio Técnico"),
                        use_container_width=True,
                        config=PLOTLY_CONFIG_SOLO_LECTURA
                    )
                else:
                    st.info("No hay respuestas EPA con fecha y promedio para graficar por Servicio Técnico.")
            else:
                dispersion_cliente = preparar_dispersion_epa(df_epa_respondidas, "cliente")
                dispersion_tecnico = preparar_dispersion_epa(df_epa_respondidas, "tecnico")
                tab_cliente, tab_tecnico = st.tabs(["Dispersi\u00f3n por cliente", "Dispersi\u00f3n por t\u00e9cnico"])

                with tab_cliente:
                    if len(dispersion_cliente):
                        st.plotly_chart(
                            grafico_dispersion_epa(dispersion_cliente, "cliente", "Promedio EPA en el tiempo por cliente"),
                            use_container_width=True,
                            config=PLOTLY_CONFIG_SOLO_LECTURA
                        )
                    else:
                        st.info("No hay respuestas EPA con fecha y promedio para graficar por cliente.")

                with tab_tecnico:
                    if len(dispersion_tecnico):
                        st.plotly_chart(
                            grafico_dispersion_epa(dispersion_tecnico, "tecnico", "Promedio EPA en el tiempo por t\u00e9cnico"),
                            use_container_width=True,
                            config=PLOTLY_CONFIG_SOLO_LECTURA
                        )
                    else:
                        st.info("No hay respuestas EPA con fecha y promedio para graficar por t\u00e9cnico.")

        if not epa_total_atenciones:
            st.info("Aun no hay links EPA creados. Genera atenciones desde la carpeta EPA para alimentar este KPI.")

    with st.expander("Revisi\u00f3n EPA", expanded=False):
        if len(df_epa_f):
            export_col, icon_col = st.columns([0.92, 0.08], gap="small")
            with export_col:
                st.markdown('<div class="filter-mini-note">Detalle EPA filtrado por regi\u00f3n, t\u00e9cnico, periodo y cliente.</div>', unsafe_allow_html=True)
            with icon_col:
                render_boton_exportar_epa_revision(df_epa_export, filtros_export)

            st.dataframe(df_epa_export, use_container_width=True, hide_index=True)
        else:
            st.info("No hay registros EPA para revisar.")


if mostrar_kpi_uso_herramienta:
    st.markdown('<div class="kpi-divider"></div>', unsafe_allow_html=True)

    render_uso_herramienta_kpi_cards()
    render_analisis_uso_herramienta({
        "uso_total": uso_total,
        "uso_promedio": uso_promedio,
        "uso_excelentes": uso_excelentes,
        "uso_buenas": uso_buenas,
        "uso_regulares": uso_regulares,
        "uso_criticas": uso_criticas,
        "uso_pct_ok": uso_pct_ok,
        "uso_retiros_incompletos": uso_retiros_incompletos,
        "uso_cge_sin_activo": uso_cge_sin_activo,
        "uso_brecha_meta": uso_brecha_meta,
        "comparativo_uso_herramienta_proveedor": comparativo_uso_herramienta_proveedor,
    })

    if len(df_uso_f):
        if SERVICIO_COMPARATIVO:
            st.plotly_chart(
                grafico_uso_herramienta_servicio(df_uso_f),
                use_container_width=True,
                config=PLOTLY_CONFIG_SOLO_LECTURA,
            )

        st.plotly_chart(
            grafico_uso_herramienta_dispersion_tecnico(df_uso_f),
            use_container_width=True,
            config=PLOTLY_CONFIG_SOLO_LECTURA,
        )

        col_uso_region, col_uso_ranking = st.columns([0.55, 0.45])
        with col_uso_region:
            st.plotly_chart(
                grafico_uso_herramienta_region(df_uso_f),
                use_container_width=True,
                config=PLOTLY_CONFIG_SOLO_LECTURA,
            )
        with col_uso_ranking:
            ranking_uso = preparar_ranking_uso_tecnico(df_uso_f)
            if len(ranking_uso):
                ranking_vista = ranking_uso.head(15).rename(columns={
                    "ranking_global": "#",
                    "servicio_tecnico": "ST",
                    "tecnico": "Tecnico",
                    "region_atendida": "Region",
                    "ots": "OT",
                    "nota_promedio": "Nota",
                    "pct_ok": "% OK",
                    "criticas": "Criticas",
                })
                st.markdown('<div class="filter-mini-note">Ranking global por tecnico, ordenado por nota promedio y consistencia de OT.</div>', unsafe_allow_html=True)
                st.dataframe(
                    ranking_vista[["#", "ST", "Tecnico", "Region", "OT", "Nota", "% OK", "Criticas"]],
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("No hay ranking tecnico para los filtros seleccionados.")

        with st.expander("Detalle auditoria OT", expanded=False):
            st.markdown('<div class="filter-mini-note">Detalle limpio de auditoria; el export conserva la evidencia completa, descripcion, hallazgos y fuente de clasificacion.</div>', unsafe_allow_html=True)
            columnas_detalle_uso = [
                "Servicio tecnico", "Folio OT", "Ticket", "Cliente", "Region atendida",
                "Tecnico", "Nota OT", "Clasificacion", "Requiere retiro",
                "Cliente CGE", "Activo fijo detectado", "Hallazgos",
            ]
            columnas_detalle_uso = [col for col in columnas_detalle_uso if col in df_uso_export.columns]
            st.dataframe(
                df_uso_export[columnas_detalle_uso].head(DISPONIBILIDAD_TABLA_MAX_FILAS),
                use_container_width=True,
                hide_index=True,
            )
            if len(df_uso_export) > DISPONIBILIDAD_TABLA_MAX_FILAS:
                st.markdown(
                    f'<div class="filter-mini-note">Mostrando {DISPONIBILIDAD_TABLA_MAX_FILAS} de {len(df_uso_export)} OT en pantalla. El export conserva todo el detalle filtrado.</div>',
                    unsafe_allow_html=True,
                )
    else:
        render_estado_sin_datos(
            "No hay datos para mostrar",
            "Sin auditoria OT para los filtros seleccionados. Ejecuta actualizacion completa para leer la PST y refrescar los PDF.",
        )


if mostrar_kpi_disponibilidad:
    st.markdown('<div class="kpi-divider"></div>', unsafe_allow_html=True)

    if disponibilidad_no_aplica_servicio:
        render_estado_sin_datos(
            "No hay datos para mostrar",
            f"{SERVICIO_ACTUAL} no aplica en KPI Disponibilidad porque opera directo con centro de comando.",
            "KPI no aplicable",
        )
    else:
        color_cumplimiento_disp = VERDE if disp_pct >= DISPONIBILIDAD_META_PCT else ROSADO
        render_disponibilidad_kpi_cards(color_cumplimiento_disp, disp_pct, disp_total, disp_cumple, disp_no_cumple, disp_sin_respuesta, disp_reit_cecom_total)
        render_analisis_disponibilidad({
            "disp_total": disp_total,
            "disp_pct": disp_pct,
            "disp_cumple": disp_cumple,
            "disp_no_cumple": disp_no_cumple,
            "disp_sin_respuesta": disp_sin_respuesta,
            "disp_brecha_meta": disp_brecha_meta,
            "disp_reiteraciones": disp_reiteraciones,
            "disp_tickets_reiterados": disp_tickets_reiterados,
            "disp_reit_cecom_total": disp_reit_cecom_total,
            "reclamos_total": reclamos_total,
            "reclamos_alta": reclamos_alta,
            "reclamos_tickets": reclamos_tickets,
            "reclamos_motivo_top": str(reclamos_motivo_top),
            "comparativo_disponibilidad_proveedor": comparativo_disponibilidad_proveedor,
        })

        if not existe_cache_disponibilidad(SERVICIOS_ACTIVOS):
            render_estado_sin_datos(
                "No hay datos para mostrar",
                "Aun no existe extraccion de disponibilidad para el servicio seleccionado.",
                "Base pendiente",
            )
        elif len(df_disp_f):
            if SERVICIO_COMPARATIVO:
                resumen_disp_servicio = preparar_resumen_mensual_disponibilidad_servicio(df_disp_f)
                st.plotly_chart(
                    grafico_disponibilidad_mensual_servicio(resumen_disp_servicio),
                    use_container_width=True,
                    config=PLOTLY_CONFIG_SOLO_LECTURA,
                )
                st.plotly_chart(
                    grafico_disponibilidad_servicio(df_disp_f),
                    use_container_width=True,
                    config=PLOTLY_CONFIG_SOLO_LECTURA,
                )
            else:
                resumen_disp = preparar_resumen_mensual_disponibilidad(df_disp_f)
                if len(resumen_disp):
                    st.plotly_chart(
                        grafico_disponibilidad_mensual(resumen_disp),
                        use_container_width=True,
                        config=PLOTLY_CONFIG_SOLO_LECTURA
                    )
                else:
                    render_estado_sin_datos("No hay datos para mostrar", "No hay fechas de solicitud validas para graficar la tendencia mensual.")
                st.plotly_chart(
                    grafico_disponibilidad_region_operacional(df_disp_f),
                    use_container_width=True,
                    config=PLOTLY_CONFIG_SOLO_LECTURA
                )
        else:
            render_estado_sin_datos("No hay datos para mostrar", "Sin solicitudes de disponibilidad para los filtros seleccionados.")


if mostrar_kpi_reclamos:
    st.markdown('<div class="kpi-divider"></div>', unsafe_allow_html=True)

    if reclamos_no_aplica_servicio:
        render_estado_sin_datos(
            "No hay datos para mostrar",
            f"{SERVICIO_ACTUAL} no se mide en KPI Reclamos dentro de este panel.",
            "KPI no aplicable",
        )
    else:
        render_reclamos_kpi_cards(
            reclamos_total,
            reclamos_reclamos_duros,
            reclamos_reforzamientos,
            reclamos_alta,
            reclamos_tickets,
            reclamos_clientes,
            atenciones_asignadas_reclamos,
            reclamos_ratio_incumplimiento,
            reclamos_cumplimiento_ajustado,
            reclamos_brecha_meta,
            reclamos_cliente_top,
            reclamos_cliente_top_count,
            reclamos_cliente_top_tickets,
            reclamos_proveedor_reforzado_top,
            reclamos_proveedor_reforzado_top_count,
        )
        render_analisis_reclamos({
            "reclamos_total": reclamos_total,
            "reclamos_reclamos_duros": reclamos_reclamos_duros,
            "reclamos_reforzamientos": reclamos_reforzamientos,
            "reclamos_alta": reclamos_alta,
            "reclamos_tickets": reclamos_tickets,
            "reclamos_clientes": reclamos_clientes,
            "reclamos_motivo_top": str(reclamos_motivo_top),
            "reclamos_motivo_top_count": reclamos_motivo_top_count,
            "reclamos_cliente_top": str(reclamos_cliente_top),
            "reclamos_cliente_top_count": reclamos_cliente_top_count,
            "reclamos_proveedor_reforzado_top": str(reclamos_proveedor_reforzado_top),
            "reclamos_proveedor_reforzado_top_count": reclamos_proveedor_reforzado_top_count,
            "atenciones_asignadas_reclamos": atenciones_asignadas_reclamos,
            "reclamos_ratio_incumplimiento": reclamos_ratio_incumplimiento,
            "reclamos_cumplimiento_ajustado": reclamos_cumplimiento_ajustado,
            "reclamos_brecha_meta": reclamos_brecha_meta,
            "comparativo_reclamos_proveedor": comparativo_reclamos_proveedor,
        })

        if len(df_reclamos_f):
            if SERVICIO_COMPARATIVO:
                col_rec_servicio, col_rec_cliente = st.columns([0.34, 0.66])
                with col_rec_servicio:
                    st.plotly_chart(
                        grafico_reclamos_servicio(df_reclamos_f, df_atenciones_reclamos_f),
                        use_container_width=True,
                        config=PLOTLY_CONFIG_SOLO_LECTURA
                    )
                with col_rec_cliente:
                    st.plotly_chart(
                        grafico_reclamos_cliente(df_reclamos_f),
                        use_container_width=True,
                        config=PLOTLY_CONFIG_SOLO_LECTURA
                    )
                st.plotly_chart(
                    grafico_reclamos_motivo(df_reclamos_f),
                    use_container_width=True,
                    config=PLOTLY_CONFIG_SOLO_LECTURA
                )
            else:
                col_rec_motivo, col_rec_cliente = st.columns([0.48, 0.52])
                with col_rec_motivo:
                    st.plotly_chart(
                        grafico_reclamos_motivo(df_reclamos_f),
                        use_container_width=True,
                        config=PLOTLY_CONFIG_SOLO_LECTURA
                    )
                with col_rec_cliente:
                    st.plotly_chart(
                        grafico_reclamos_cliente(df_reclamos_f),
                        use_container_width=True,
                        config=PLOTLY_CONFIG_SOLO_LECTURA
                    )

            st.markdown(f'<div class="filter-mini-note">Detalle reclamos {SERVICIO_TITULO}: cliente, ticket y clasificacion homologada. El export conserva remitentes, asunto, extracto y evidencia completa.</div>', unsafe_allow_html=True)
            df_reclamos_vista = preparar_vista_reclamos_limpia(df_reclamos_export).head(DISPONIBILIDAD_TABLA_MAX_FILAS)
            if len(df_reclamos_export) > DISPONIBILIDAD_TABLA_MAX_FILAS:
                st.markdown(
                    f'<div class="filter-mini-note">Mostrando {DISPONIBILIDAD_TABLA_MAX_FILAS} de {len(df_reclamos_export)} filas en pantalla. El export conserva la vista filtrada completa.</div>',
                    unsafe_allow_html=True,
                )
            st.dataframe(df_reclamos_vista, use_container_width=True, hide_index=True)
        else:
            render_estado_sin_datos("No hay datos para mostrar", "Sin reclamos para los filtros seleccionados.")




if mostrar_kpi_inicio:
    # =====================================================
    # GRAFICO GERENCIAL ENTEL - OPCION 2: COMPARATIVO PREMIUM
    # =====================================================
    # Opción más limpia y ejecutiva: tendencia por región, conectores de brecha
    # mensual, zona de meta Entel y lectura sin títulos sobrepuestos.

    df_graf_inicio = df_f.copy()
    estado_graf_col = "Estado"
    dimension_graf_label = "Región"
    titulo_evolucion_inicio = "Evolución mensual de cumplimiento por región"
    subtitulo_evolucion_inicio = "Comparativo gerencial contra meta operacional Entel 80%"
    if SERVICIO_COMPARATIVO and "servicio_tecnico" in df_graf_inicio.columns:
        df_graf_inicio["_Servicio_Graf"] = (
            df_graf_inicio["servicio_tecnico"]
            .fillna("Sin ST")
            .astype(str)
            .str.strip()
            .replace({"": "Sin ST"})
        )
        estado_graf_col = "_Servicio_Graf"
        dimension_graf_label = "Servicio Técnico"
        titulo_evolucion_inicio = "Evolución mensual de cumplimiento por Servicio Técnico"
        subtitulo_evolucion_inicio = "Comparativo ST vs ST contra meta operacional Entel 80%"
    elif SERVICIO_ACTUAL == "SAO" and "Estado" in df_graf_inicio.columns:
        regiones_top = (
            df_graf_inicio["Estado"]
            .dropna()
            .astype(str)
            .str.strip()
            .replace("", pd.NA)
            .dropna()
            .value_counts()
            .head(6)
            .index
            .tolist()
        )
        df_graf_inicio["_Estado_Graf"] = df_graf_inicio["Estado"].where(
            df_graf_inicio["Estado"].astype(str).isin(regiones_top),
            "Otras regiones",
        )
        estado_graf_col = "_Estado_Graf"

    graf = (
        df_graf_inicio.groupby(["Mes", estado_graf_col])["Cumple"]
            .mean()
            .mul(100)
            .reset_index()
            .rename(columns={estado_graf_col: "Estado"})
    )

    graf["Mes"] = pd.Categorical(graf["Mes"], categories=MESES, ordered=True)
    graf = graf.sort_values(["Mes", "Estado"])

    # Encabezado fuera del gráfico para evitar que Plotly pise títulos o leyendas.
    st.markdown(
        f"""
        <div style="
            background:radial-gradient(circle at 96% 18%,rgba(46,203,242,.18),transparent 24%),linear-gradient(180deg,rgba(255,255,255,.96) 0%,rgba(248,252,255,.94) 100%);
            border-top:6px solid {AZUL};
            border-left:1px solid rgba(46,203,242,0.24);
            border-right:1px solid rgba(253,108,152,0.18);
            border-bottom:1px solid #E6EBF3;
            padding:11px 18px 10px 18px;
            margin-top:4px;
            margin-bottom:0px;
            box-shadow:0 18px 34px rgba(16,6,159,.10),0 0 18px rgba(46,203,242,.14),inset 0 1px 0 rgba(255,255,255,.90);
        ">
            <div style="font-size:20px;font-weight:900;color:{AZUL};letter-spacing:-.2px;text-shadow:0 0 12px rgba(46,203,242,.18);">
                {titulo_evolucion_inicio}
            </div>
            <div style="font-size:12px;font-weight:650;color:#64748B;margin-top:3px;">
                {subtitulo_evolucion_inicio}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    fig = go.Figure()

    # Fondo por capas: da profundidad sin competir con las series regionales.
    for y0, y1, alpha in [(0, 20, 0.018), (20, 40, 0.026), (40, 60, 0.034), (60, 80, 0.042)]:
        fig.add_hrect(
            y0=y0,
            y1=y1,
            fillcolor=rgba(AZUL_CLARO, alpha),
            line_width=0,
            layer="below"
        )

    # Zona objetivo Entel.
    fig.add_hrect(
        y0=80,
        y1=100,
        fillcolor="rgba(253,108,152,0.10)",
        line_width=0,
        layer="below"
    )

    fig.add_hline(
        y=80,
        line_dash="dot",
        line_width=2.8,
        line_color=ROSADO
    )

    st.markdown(
        f"""
        <div style="
            display:flex;
            justify-content:flex-start;
            align-items:center;
            padding:9px 0 0 22px;
            margin:0;
        ">
            <div style="
                display:inline-flex;
                align-items:center;
                gap:8px;
                background:transparent;
                color:{ROSADO};
                font-size:13px;
                font-weight:950;
                font-family:'Segoe UI',sans-serif;
                letter-spacing:.02em;
                border:1px solid rgba(253,108,152,.78);
                border-radius:999px;
                padding:6px 12px;
                box-shadow:0 0 14px rgba(253,108,152,.38), inset 0 0 10px rgba(253,108,152,.10);
                text-shadow:0 0 8px rgba(253,108,152,.90), 0 0 16px rgba(253,108,152,.48);
            ">
                <span style="
                    width:8px;
                    height:8px;
                    border-radius:50%;
                    background:{ROSADO};
                    box-shadow:0 0 10px rgba(253,108,152,.95),0 0 18px rgba(253,108,152,.55);
                    display:inline-block;
                "></span>
                Meta Entel 80%
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    palette = CHART_PALETTE
    regiones_graf = list(graf["Estado"].dropna().unique())
    mostrar_etiquetas_region = SERVICIO_COMPARATIVO or not (SERVICIO_ACTUAL == "SAO" and len(regiones_graf) > 4)

    # Conectores de brecha mensual entre regiones: da lectura gerencial sin usar barras.
    pivot = (
        graf.pivot_table(
            index="Mes",
            columns="Estado",
            values="Cumple",
            aggfunc="mean",
            observed=False
        )
        .reindex(MESES)
        .dropna(how="all")
    )

    if len(regiones_graf) >= 2:
        for mes in pivot.index:
            vals = pivot.loc[mes].dropna()
            if len(vals) >= 2:
                fig.add_trace(go.Scatter(
                    x=[mes, mes],
                    y=[vals.min(), vals.max()],
                    mode="lines",
                    line=dict(color="rgba(15,23,42,0.10)", width=10),
                    hoverinfo="skip",
                    showlegend=False
                ))
                fig.add_trace(go.Scatter(
                    x=[mes, mes],
                    y=[vals.min(), vals.max()],
                    mode="lines",
                    line=dict(color="rgba(148,163,184,0.50)", width=1.6),
                    hoverinfo="skip",
                    showlegend=False
                ))

    # Tendencias por región.
    for i, zona in enumerate(regiones_graf):
        d = graf[graf["Estado"] == zona].copy()
        c = palette[i % len(palette)]

        posiciones = ["top center" if i % 2 == 0 else "bottom center"] * len(d)

        # Sombra desplazada: simula profundidad sin alterar los valores.
        fig.add_trace(go.Scatter(
            x=d["Mes"],
            y=d["Cumple"].sub(1.4).clip(lower=0),
            mode="lines",
            line=dict(color="rgba(15,23,42,0.11)", width=12, shape="spline", smoothing=0.9),
            hoverinfo="skip",
            showlegend=False
        ))

        # Halo de color por serie.
        fig.add_trace(go.Scatter(
            x=d["Mes"],
            y=d["Cumple"],
            mode="lines",
            line=dict(color=rgba(c, 0.18), width=15, shape="spline", smoothing=0.9),
            hoverinfo="skip",
            showlegend=False
        ))

        # Sombra de marcadores.
        fig.add_trace(go.Scatter(
            x=d["Mes"],
            y=d["Cumple"].sub(0.9).clip(lower=0),
            mode="markers",
            marker=dict(size=20, color="rgba(15,23,42,0.16)", line=dict(width=0)),
            hoverinfo="skip",
            showlegend=False
        ))

        # Línea principal.
        fig.add_trace(go.Scatter(
            x=d["Mes"],
            y=d["Cumple"],
            name=str(zona),
            mode="lines+markers+text" if mostrar_etiquetas_region else "lines+markers",
            line=dict(color=c, width=4.4, shape="spline", smoothing=0.9),
            marker=dict(
                size=15,
                color="#FFFFFF",
                line=dict(color=c, width=4)
            ),
            text=[f"<b>{v:.1f}%</b>" for v in d["Cumple"]] if mostrar_etiquetas_region else None,
            textposition=posiciones if mostrar_etiquetas_region else None,
            textfont=dict(size=13, color=c, family="Segoe UI Black"),
            hovertemplate=(
                "<b>%{x}</b><br>"
                f"{dimension_graf_label}: <b>{zona}</b><br>"
                "Cumplimiento: <b>%{y:.1f}%</b><br>"
                "Meta: <b>80%</b><br>"
                "Brecha vs meta: <b>%{customdata:.1f} pp</b>"
                "<extra></extra>"
            ),
            customdata=(d["Cumple"] - 80).round(1)
        ))

    # Resumen ejecutivo discreto en la esquina superior derecha.
    promedio_graf = float(graf["Cumple"].mean()) if len(graf) else 0
    brecha_graf = promedio_graf - 80
    color_brecha = VERDE if brecha_graf >= 0 else NARANJO

    fig.add_annotation(
        visible=False,
        xref="paper",
        yref="paper",
        x=0.985,
        y=1.085,
        xanchor="right",
        yanchor="top",
        showarrow=False,
        align="right",
        text=(
            "<span style='font-size:11px;color:#64748B'>PROMEDIO FILTRADO</span><br>"
            f"<span style='font-size:22px;color:{color_brecha}'><b>{promedio_graf:.1f}%</b></span><br>"
            f"<span style='font-size:10px;color:#64748B'>Brecha: {brecha_graf:+.1f} pp</span>"
        ),
        bgcolor="rgba(6,18,34,0.88)",
        bordercolor="rgba(46,203,242,0.30)",
        borderwidth=1,
        borderpad=8
    )

    # Marcadores ejecutivos: mejor y peor punto sin invadir el título.
    if len(graf):
        mejor = graf.loc[graf["Cumple"].idxmax()]
        critico = graf.loc[graf["Cumple"].idxmin()]

        fig.add_annotation(
            x=mejor["Mes"],
            y=mejor["Cumple"],
            text="Máximo",
            showarrow=True,
            arrowhead=2,
            arrowsize=1,
            arrowwidth=1.4,
            arrowcolor=VERDE,
            ax=22,
            ay=-42,
            font=dict(size=11, color="#EAFBFF", family="Segoe UI Semibold"),
            bgcolor="rgba(6,18,34,0.90)",
            bordercolor="rgba(71,225,144,0.50)",
            borderwidth=1,
            borderpad=4
        )

        fig.add_annotation(
            x=critico["Mes"],
            y=critico["Cumple"],
            text="Mínimo",
            showarrow=True,
            arrowhead=2,
            arrowsize=1,
            arrowwidth=1.4,
            arrowcolor=NARANJO,
            ax=-24,
            ay=38,
            font=dict(size=11, color="#EAFBFF", family="Segoe UI Semibold"),
            bgcolor="rgba(6,18,34,0.90)",
            bordercolor="rgba(255,61,0,0.45)",
            borderwidth=1,
            borderpad=4
        )

    fig.update_layout(
        height=420 if (SERVICIO_ACTUAL == "SAO" and not SERVICIO_COMPARATIVO and len(regiones_graf) > 4) else 330,
        hovermode="x unified",
        paper_bgcolor="rgba(255,255,255,0)",
        plot_bgcolor="rgba(6,18,34,0.74)",
        margin=dict(l=52, r=34, t=62, b=42),
        legend=dict(
            orientation="h",
            x=0.5,
            xanchor="center",
            y=1.085,
            yanchor="top",
            bgcolor="rgba(6,18,34,0.82)",
            bordercolor="rgba(46,203,242,0.42)",
            borderwidth=1,
            font=dict(size=11 if (SERVICIO_ACTUAL == "SAO" and not SERVICIO_COMPARATIVO) else 13, family="Segoe UI Semibold", color="#EAFBFF"),
            itemwidth=130 if (SERVICIO_ACTUAL == "SAO" and not SERVICIO_COMPARATIVO) else 170
        ),
        hoverlabel=dict(
            bgcolor="rgba(6,18,34,0.94)",
            bordercolor="rgba(46,203,242,0.36)",
            font=dict(size=12, family="Segoe UI", color="#EAFBFF")
        ),
        transition=dict(duration=0)
    )

    fig.update_xaxes(
        title=None,
        showgrid=False,
        zeroline=False,
        tickfont=dict(size=14, family="Segoe UI Semibold", color="#DDFBFF"),
        showline=True,
        linecolor="rgba(143,239,255,0.20)",
        linewidth=1,
        ticks=""
    )

    fig.update_yaxes(
        title=None,
        range=[0, 105],
        ticksuffix="%",
        dtick=20,
        showgrid=True,
        gridcolor="rgba(143,239,255,0.14)",
        zeroline=False,
        tickfont=dict(size=13, family="Segoe UI", color="#BDEFFF"),
        showline=False
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
        config=PLOTLY_CONFIG_SOLO_LECTURA
    )





if mostrar_kpi_inicio:
    # =========================================================
    # ESTADO FINAL DE ATENCIONES - PLOTLY PREMIUM BALANCEADO
    # =========================================================

    st.markdown('<div class="estado-final-heading"><h2 class="kpi-title">Estado final de atenciones</h2><div class="kpi-divider"></div></div>', unsafe_allow_html=True)

    def fmt_num(valor):
        return f"{int(valor):,}".replace(",", ".")


    def kpi_plotly(titulo, valor, porcentaje, color, icono, subtitulo, compact=False):
        """Tarjeta KPI premium en Plotly. No usa HTML para evitar que se muestre código."""
        fig_kpi = go.Figure()
        accent = "#2D8CFF" if str(color).upper() == str(AZUL).upper() else color

        fig_kpi.add_shape(
            type="rect",
            x0=0,
            y0=0,
            x1=1,
            y1=1,
            xref="paper",
            yref="paper",
            fillcolor="rgba(7,18,34,0.94)",
            line=dict(color=rgba(accent, 0.58), width=1.35),
            layer="below"
        )

        fig_kpi.add_shape(
            type="rect",
            x0=0,
            y0=0.955,
            x1=1,
            y1=1,
            xref="paper",
            yref="paper",
            fillcolor=accent,
            line=dict(width=0),
            layer="below"
        )

        fig_kpi.add_shape(
            type="circle",
            x0=0.055,
            y0=0.59,
            x1=0.17,
            y1=0.86,
            xref="paper",
            yref="paper",
            fillcolor=rgba(accent, 0.26),
            line=dict(color=rgba(accent, 0.72), width=1.25),
            layer="below"
        )

        fig_kpi.add_annotation(
            x=0.112,
            y=0.725,
            text=icono,
            showarrow=False,
            font=dict(size=17, color="#FFFFFF", family="Arial Black")
        )

        fig_kpi.add_annotation(
            x=0.22,
            y=0.72,
            xanchor="left",
            text=titulo,
            showarrow=False,
            font=dict(size=10 if compact else 12, color="#EAFBFF", family="Segoe UI Semibold")
        )

        fig_kpi.add_annotation(
            x=0.22,
            y=0.43,
            xanchor="left",
            text=fmt_num(valor),
            showarrow=False,
            font=dict(size=21 if compact else 26, color="#F8FAFC", family="Arial Black")
        )

        fig_kpi.add_annotation(
            x=0.94,
            y=0.43,
            xanchor="right",
            text=f"{porcentaje:.1f}%",
            showarrow=False,
            font=dict(size=16 if compact else 19, color=accent, family="Arial Black")
        )

        fig_kpi.add_annotation(
            x=0.22,
            y=0.17,
            xanchor="left",
            text=subtitulo,
            showarrow=False,
            font=dict(size=8 if compact else 9, color="#9BD7EA", family="Segoe UI Semibold")
        )

        fig_kpi.update_xaxes(visible=False, range=[0, 1], fixedrange=True)
        fig_kpi.update_yaxes(visible=False, range=[0, 1], fixedrange=True)
        fig_kpi.update_layout(
            height=76 if compact else 84,
            margin=dict(l=0, r=0, t=0, b=0),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)"
        )

        return fig_kpi


    def encabezado_plotly(titulo):
        """Encabezado del panel de distribución, hecho en Plotly para mantener el mismo estilo."""
        fig_head = go.Figure()

        fig_head.add_shape(
            type="rect",
            x0=0,
            y0=0,
            x1=1,
            y1=1,
            xref="paper",
            yref="paper",
            fillcolor="rgba(7,18,34,0.88)",
            line=dict(color="rgba(46,203,242,0.44)", width=1.1),
            layer="below"
        )

        fig_head.add_shape(
            type="rect",
            x0=0,
            y0=0.90,
            x1=1,
            y1=1,
            xref="paper",
            yref="paper",
            fillcolor=AZUL,
            line=dict(width=0),
            layer="below"
        )

        fig_head.add_annotation(
            x=0.03,
            y=0.48,
            xanchor="left",
            text=titulo,
            showarrow=False,
            font=dict(size=14, color="#DDFBFF", family="Segoe UI Semibold")
        )

        fig_head.update_xaxes(visible=False, range=[0, 1], fixedrange=True)
        fig_head.update_yaxes(visible=False, range=[0, 1], fixedrange=True)
        fig_head.update_layout(
            height=34,
            margin=dict(l=0, r=0, t=0, b=0),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)"
        )

        return fig_head


    left, right = st.columns([0.42, 0.58], gap="medium")

    with left:
        st.plotly_chart(
            encabezado_plotly("Distribución de atenciones"),
            use_container_width=True,
            config=PLOTLY_CONFIG_SOLO_LECTURA
        )

        pie = go.Figure()

        # Donut con profundidad simulada: sombra inferior + base + anillo principal.
        pie.add_trace(
            go.Pie(
                labels=["Finalizadas", "No finalizadas"],
                values=[finalizadas, no_finalizadas],
                hole=0.61,
                sort=False,
                direction="clockwise",
                rotation=90,
            domain=dict(x=[0.160, 0.840], y=[0.015, 0.825]),
                textinfo="none",
                hoverinfo="skip",
                marker=dict(
                    colors=[rgba(AZUL, 0.20), rgba(ROSADO, 0.20)],
                    line=dict(color="rgba(0,0,0,0)", width=0)
                ),
                showlegend=False
            )
        )

        pie.add_trace(
            go.Pie(
                labels=["Finalizadas", "No finalizadas"],
                values=[finalizadas, no_finalizadas],
                hole=0.61,
                sort=False,
                direction="clockwise",
                rotation=90,
                domain=dict(x=[0.160, 0.840], y=[0.055, 0.865]),
                textinfo="none",
                hoverinfo="skip",
                marker=dict(
                    colors=["#064AD8", "#D84C7D"],
                    line=dict(color="rgba(255,255,255,0.20)", width=1.2)
                ),
                showlegend=False
            )
        )

        pie.add_trace(
            go.Pie(
                labels=["Finalizadas", "No finalizadas"],
                values=[finalizadas, no_finalizadas],
                hole=0.64,
                sort=False,
                direction="clockwise",
                rotation=90,
                domain=dict(x=[0.160, 0.840], y=[0.105, 0.940]),
                texttemplate="<b>%{percent:.1%}</b>",
                textposition="inside",
                insidetextorientation="horizontal",
                textfont=dict(size=11, color="#FFFFFF", family="Segoe UI Black"),
                marker=dict(
                    colors=[AZUL_CLARO, ROSADO],
                    line=dict(color="#FFFFFF", width=3.2)
                ),
                pull=[0.008, 0.014],
                showlegend=True,
                hovertemplate="%{label}<br>Cantidad: %{value}<br>Participación: %{percent}<extra></extra>"
            )
        )

        pie.add_annotation(
            x=0.5,
            y=0.505,
            text=f"<b>{fmt_num(total_atenciones)}</b>",
            showarrow=False,
            font=dict(size=31, color=CELESTE, family="Segoe UI Black")
        )

        pie.add_annotation(
            x=0.5,
            y=0.405,
            text="<b>Atenciones</b>",
            showarrow=False,
            font=dict(size=12, color="#BDEFFF", family="Segoe UI Semibold")
        )

        pie.update_layout(
            height=230,
            paper_bgcolor="rgba(255,255,255,0)",
            plot_bgcolor="rgba(6,18,34,0.72)",
            margin=dict(t=20, b=6, l=8, r=8),
            showlegend=True,
            legend=dict(
                orientation="h",
                x=0.5,
                xanchor="center",
                y=1.02,
                yanchor="bottom",
                font=dict(size=10, family="Segoe UI Semibold", color="#EAFBFF"),
                bgcolor="rgba(6,18,34,0.84)",
                bordercolor="rgba(46,203,242,0.40)",
                borderwidth=1
            ),
            uniformtext=dict(minsize=10, mode="hide")
        )

        st.plotly_chart(pie, use_container_width=True, config=PLOTLY_CONFIG_SOLO_LECTURA)

    with right:
        motivo_col = next(
            (c for c in ["Motivo de no realización", "Motivo", "Resultado", "Acción Realizada", "Observación"] if c in df_f.columns),
            None
        )

        if motivo_col:
            motivos_limpios = df_f.loc[~estado.str.contains("FINAL", na=False), motivo_col].fillna("Otros")
            base = consolidar_motivos_no_realizado(motivos_limpios).head(8)
        else:
            base = pd.Series(dtype=int)

        st.plotly_chart(
            encabezado_plotly("Motivo de No Realizado"),
            use_container_width=True,
            config=PLOTLY_CONFIG_SOLO_LECTURA
        )

        if len(base):
            pct_motivos = (base / base.sum() * 100).round(1)
            max_x = max(base.values) if len(base) else 1

            bar = go.Figure(
                go.Bar(
                    x=base.values,
                    y=base.index,
                    orientation="h",
                    text=[f"{v} ({p}%)" for v, p in zip(base.values, pct_motivos)],
                    textposition="outside",
                    cliponaxis=False,
                    textfont=dict(size=12, color="#EAFBFF", family="Segoe UI Semibold"),
                    marker=dict(color=ROSADO, line=dict(color="#FFFFFF", width=1.3)),
                    hovertemplate="%{y}<br>Cantidad: %{x}<extra></extra>"
                )
            )

            bar.update_layout(
                height=230,
                margin=dict(t=12, b=24, l=14, r=86),
                paper_bgcolor="rgba(255,255,255,0)",
                plot_bgcolor="rgba(6,18,34,0.72)",
                xaxis=dict(
                    range=[0, max_x * 1.15],
                    showgrid=True,
                    gridcolor="rgba(143,239,255,0.14)",
                    zeroline=False,
                    tickfont=dict(size=11, color="#BDEFFF", family="Segoe UI Semibold")
                ),
                yaxis=dict(
                    autorange="reversed",
                    automargin=True,
                    tickfont=dict(size=12, color="#EAFBFF", family="Segoe UI Semibold")
                ),
                showlegend=False
            )

            st.plotly_chart(bar, use_container_width=True, config=PLOTLY_CONFIG_SOLO_LECTURA)
        else:
            st.info("No hay motivos de no realización para los filtros aplicados.")

    estado_cards = st.columns([1, 1, 1, 1.18], gap="small")

    with estado_cards[0]:
        st.plotly_chart(
            kpi_plotly("Finalizadas", finalizadas, pct_fin, AZUL_CLARO, "✓", "Del total filtrado", compact=True),
            use_container_width=True,
            config=PLOTLY_CONFIG_SOLO_LECTURA
        )

    with estado_cards[1]:
        st.plotly_chart(
            kpi_plotly("No finalizadas", no_finalizadas, pct_no_fin, ROSADO, "!", "Del total filtrado", compact=True),
            use_container_width=True,
            config=PLOTLY_CONFIG_SOLO_LECTURA
        )

    with estado_cards[2]:
        st.plotly_chart(
            kpi_plotly(
                "Total no finalizadas",
                no_finalizadas,
                pct_no_fin,
                ROSADO,
                "!",
                "Base del gráfico de motivos",
                compact=True
            ),
            use_container_width=True,
            config=PLOTLY_CONFIG_SOLO_LECTURA
        )

    with estado_cards[3]:
        revisita_kpi_col, revisita_export_col = st.columns([0.86, 0.14], gap="small")
        with revisita_kpi_col:
            st.plotly_chart(
                kpi_plotly(
                    "Revisitas",
                    revisitas,
                    pct_revisitas,
                    CELESTE,
                    "R",
                    "Del total filtrado",
                    compact=True
                ),
                use_container_width=True,
                config=PLOTLY_CONFIG_SOLO_LECTURA
            )
        with revisita_export_col:
            render_boton_revisitas(df_revisitas_export, filtros_export)

    st.markdown(
        """
        <div class="estado-info-note">
            <span class="info-icon">i</span>
            <span>Estado final de las atenciones según los filtros aplicados.</span>
        </div>
        """,
        unsafe_allow_html=True
    )


# =========================================================
# FOOTER
# =========================================================


st.markdown("---")

st.caption(
    f"Última actualización: "
    f"{datetime.now().strftime('%d-%m-%Y %H:%M')} | {APP_OWNER}"
)

