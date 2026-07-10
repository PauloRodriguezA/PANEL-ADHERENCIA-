from __future__ import annotations

import re
import unicodedata
from typing import Any


REGION_LABELS = {
    "ARICA": "Region de Arica y Parinacota",
    "TARAPACA": "Region de Tarapaca",
    "ANTOFAGASTA": "Region de Antofagasta",
    "ATACAMA": "Region de Atacama",
    "COQUIMBO": "Region de Coquimbo",
    "VALPARAISO": "Region de Valparaiso",
    "METROPOLITANA": "Region Metropolitana",
    "OHIGGINS": "Region de O'Higgins",
    "MAULE": "Region del Maule",
    "NUBLE": "Region de Nuble",
    "BIOBIO": "Region del Biobio",
    "ARAUCANIA": "Region de La Araucania",
    "LOS RIOS": "Region de Los Rios",
    "LOS LAGOS": "Region de Los Lagos",
    "AYSEN": "Region de Aysen",
    "MAGALLANES": "Region de Magallanes",
}

REGION_ALIASES = {
    "ARICA": ["ARICA", "PARINACOTA", "XV REGION"],
    "TARAPACA": ["TARAPACA", "I REGION", "IQUIQUE", "ALTO HOSPICIO"],
    "ANTOFAGASTA": ["ANTOFAGASTA", "II REGION", "CALAMA", "TOCOPILLA", "MEJILLONES"],
    "ATACAMA": ["ATACAMA", "III REGION", "COPIAPO", "VALLENAR"],
    "COQUIMBO": ["COQUIMBO", "IV REGION", "LA SERENA", "SERENA", "OVALLE", "ILLAPEL"],
    "VALPARAISO": ["VALPARAISO", "V REGION", "VINA DEL MAR", "QUILLOTA", "LOS ANDES", "SAN FELIPE"],
    "METROPOLITANA": ["METROPOLITANA", "XIII REGION", "REGION RM", "SANTIAGO", "PROVIDENCIA"],
    "OHIGGINS": ["OHIGGINS", "O HIGGINS", "VI REGION", "RANCAGUA", "MACHALI"],
    "MAULE": ["MAULE", "VII REGION", "TALCA", "CURICO", "LINARES"],
    "NUBLE": ["NUBLE", "XVI REGION", "CHILLAN"],
    "BIOBIO": ["BIO BIO", "BIOBIO", "VIII REGION", "CONCEPCION", "LOS ANGELES", "CANETE"],
    "ARAUCANIA": ["ARAUCANIA", "IX REGION", "TEMUCO", "VILLARRICA"],
    "LOS RIOS": ["LOS RIOS", "XIV REGION", "VALDIVIA"],
    "LOS LAGOS": ["LOS LAGOS", "X REGION", "PUERTO MONTT", "OSORNO", "CASTRO", "QUELLON"],
    "AYSEN": ["AYSEN", "XI REGION", "COYHAIQUE"],
    "MAGALLANES": ["MAGALLANES", "XII REGION", "PUNTA ARENAS"],
}

COMUNA_REGION = {
    "ARICA": "ARICA",
    "IQUIQUE": "TARAPACA",
    "ALTO HOSPICIO": "TARAPACA",
    "POZO ALMONTE": "TARAPACA",
    "ANTOFAGASTA": "ANTOFAGASTA",
    "CALAMA": "ANTOFAGASTA",
    "TOCOPILLA": "ANTOFAGASTA",
    "MEJILLONES": "ANTOFAGASTA",
    "TALTAL": "ANTOFAGASTA",
    "COPIAPO": "ATACAMA",
    "VALLENAR": "ATACAMA",
    "CHAÑARAL": "ATACAMA",
    "CHANARAL": "ATACAMA",
    "LA SERENA": "COQUIMBO",
    "SERENA": "COQUIMBO",
    "COQUIMBO": "COQUIMBO",
    "OVALLE": "COQUIMBO",
    "ILLAPEL": "COQUIMBO",
    "VALPARAISO": "VALPARAISO",
    "VINA DEL MAR": "VALPARAISO",
    "VIÑA DEL MAR": "VALPARAISO",
    "QUILLOTA": "VALPARAISO",
    "LOS ANDES": "VALPARAISO",
    "SAN FELIPE": "VALPARAISO",
    "SANTIAGO": "METROPOLITANA",
    "PROVIDENCIA": "METROPOLITANA",
    "LAS CONDES": "METROPOLITANA",
    "LA REINA": "METROPOLITANA",
    "PUENTE ALTO": "METROPOLITANA",
    "MAIPU": "METROPOLITANA",
    "TALAGANTE": "METROPOLITANA",
    "RANCAGUA": "OHIGGINS",
    "MACHALI": "OHIGGINS",
    "SAN FERNANDO": "OHIGGINS",
    "TALCA": "MAULE",
    "CURICO": "MAULE",
    "LINARES": "MAULE",
    "CHILLAN": "NUBLE",
    "CONCEPCION": "BIOBIO",
    "LOS ANGELES": "BIOBIO",
    "CANETE": "BIOBIO",
    "CAÑETE": "BIOBIO",
    "TEMUCO": "ARAUCANIA",
    "VILLARRICA": "ARAUCANIA",
    "VALDIVIA": "LOS RIOS",
    "PUERTO MONTT": "LOS LAGOS",
    "OSORNO": "LOS LAGOS",
    "CASTRO": "LOS LAGOS",
    "QUELLON": "LOS LAGOS",
    "COYHAIQUE": "AYSEN",
    "PUNTA ARENAS": "MAGALLANES",
}


def normalizar_texto(valor: Any) -> str:
    texto = str(valor or "").upper().strip().replace("\xa0", " ")
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    texto = re.sub(r"[^A-Z0-9]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def normalizar_region_chile(valor: Any) -> str:
    norm = normalizar_texto(valor)
    if not norm:
        return ""
    for key, aliases in REGION_ALIASES.items():
        if any(alias in norm for alias in aliases):
            return REGION_LABELS[key]
    return str(valor or "").strip()


def region_desde_ciudad(ciudad: Any) -> str:
    norm = normalizar_texto(ciudad)
    if not norm:
        return ""
    for comuna, region_key in sorted(COMUNA_REGION.items(), key=lambda item: len(item[0]), reverse=True):
        comuna_norm = normalizar_texto(comuna)
        if re.search(rf"(?<![A-Z0-9]){re.escape(comuna_norm)}(?![A-Z0-9])", norm):
            return REGION_LABELS[region_key]
    region = normalizar_region_chile(norm)
    return region if region.startswith("Region ") else ""


def region_por_ciudad_o_comuna(ciudad: Any, region_actual: Any = "") -> str:
    por_ciudad = region_desde_ciudad(ciudad)
    if por_ciudad:
        return por_ciudad
    por_region = normalizar_region_chile(region_actual)
    return por_region or str(region_actual or "").strip()


def corregir_region_por_ciudad(df: Any, ciudad_col: str = "Ciudad", region_col: str = "Estado") -> Any:
    if df is None or ciudad_col not in df.columns or region_col not in df.columns:
        return df
    df[region_col] = df.apply(
        lambda row: region_por_ciudad_o_comuna(row.get(ciudad_col, ""), row.get(region_col, "")),
        axis=1,
    )
    return df
