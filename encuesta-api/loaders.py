"""
loaders.py
Motor de ingesta multi-fuente para encuestas poblacionales.

Soporta:
  • Archivos locales: CSV, XLSX, TXT (TSV/delimitado), JSON, Parquet, ODS
  • URLs de nube: Google Drive, Dropbox, OneDrive, S3 presignado, URL directa
  • APIs externas: endpoint REST que devuelva JSON con lista de encuestas
"""

import io
import re
import json
import logging
from typing import Any

import httpx
import pandas as pd

logger = logging.getLogger("encuesta_api.loaders")

# ──────────────────────────────────────────────
# CONSTANTES
# ──────────────────────────────────────────────

# Tipos de archivo soportados → función lectora de pandas
EXTENSIONES_SOPORTADAS = {
    ".csv":    "csv",
    ".tsv":    "tsv",
    ".txt":    "txt",
    ".xlsx":   "xlsx",
    ".xls":    "xls",
    ".ods":    "ods",
    ".json":   "json",
    ".parquet":"parquet",
}

# Tamaño máximo permitido para archivos (10 MB)
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024


# ──────────────────────────────────────────────
# LECTOR DE BYTES → DataFrame
# ──────────────────────────────────────────────

def leer_bytes_a_dataframe(contenido: bytes, extension: str) -> pd.DataFrame:
    """
    Convierte bytes de un archivo al formato correspondiente en un DataFrame.

    Args:
        contenido: bytes del archivo cargado
        extension:  extensión del archivo (con punto, ej: '.csv')

    Returns:
        pd.DataFrame con los datos del archivo

    Raises:
        ValueError si la extensión no es soportada o el archivo está vacío/corrupto
    """
    if len(contenido) > MAX_FILE_SIZE_BYTES:
        raise ValueError(
            f"El archivo supera el límite de {MAX_FILE_SIZE_BYTES // (1024*1024)} MB."
        )

    ext = extension.lower()
    buf = io.BytesIO(contenido)

    try:
        if ext == ".csv":
            # Detecta automáticamente separador: coma, punto y coma o pipe
            sample = contenido[:2048].decode("utf-8", errors="ignore")
            sep = _detectar_separador(sample)
            return pd.read_csv(buf, sep=sep, encoding="utf-8", on_bad_lines="skip")

        elif ext in (".tsv", ".txt"):
            # TXT puede ser TSV o espacio-separado; intentamos los dos
            sample = contenido[:2048].decode("utf-8", errors="ignore")
            sep = _detectar_separador(sample, default="\t")
            return pd.read_csv(buf, sep=sep, encoding="utf-8", on_bad_lines="skip")

        elif ext in (".xlsx", ".xls"):
            return pd.read_excel(buf, engine="openpyxl" if ext == ".xlsx" else "xlrd")

        elif ext == ".ods":
            return pd.read_excel(buf, engine="odf")

        elif ext == ".json":
            data = json.loads(contenido.decode("utf-8"))
            # Acepta lista de registros o dict con llave "data"/"encuestas"/"records"
            if isinstance(data, list):
                return pd.DataFrame(data)
            elif isinstance(data, dict):
                for clave in ("data", "encuestas", "records", "results", "items"):
                    if clave in data and isinstance(data[clave], list):
                        return pd.DataFrame(data[clave])
            raise ValueError("JSON no tiene estructura de lista o clave reconocida (data/encuestas/records).")

        elif ext == ".parquet":
            return pd.read_parquet(buf)

        else:
            raise ValueError(
                f"Extensión '{ext}' no soportada. "
                f"Use: {', '.join(EXTENSIONES_SOPORTADAS.keys())}"
            )

    except Exception as exc:
        raise ValueError(f"Error leyendo archivo '{ext}': {exc}") from exc


def _detectar_separador(muestra: str, default: str = ",") -> str:
    """
    Detecta el separador más probable en un CSV/TXT a partir de una muestra de texto.
    Revisa: coma, punto y coma, tabulador y pipe.
    """
    candidatos = {",": 0, ";": 0, "\t": 0, "|": 0}
    for sep in candidatos:
        candidatos[sep] = muestra.count(sep)
    mejor = max(candidatos, key=candidatos.get)
    return mejor if candidatos[mejor] > 0 else default


# ──────────────────────────────────────────────
# CARGA DESDE URL (Google Drive, Dropbox, etc.)
# ──────────────────────────────────────────────

def transformar_url_nube(url: str) -> str:
    """
    Convierte URLs de compartición de Google Drive / Dropbox / OneDrive
    en URLs de descarga directa.

    - Google Drive:  /file/d/<ID>/view  →  /uc?export=download&id=<ID>
    - Dropbox:       ?dl=0              →  ?dl=1
    - OneDrive:      redir?resid=...    →  download?resid=...
    """
    # Google Drive: https://drive.google.com/file/d/<ID>/view
    gd_match = re.search(r"drive\.google\.com/file/d/([^/]+)", url)
    if gd_match:
        file_id = gd_match.group(1)
        return f"https://drive.google.com/uc?export=download&confirm=t&id={file_id}"

    # Google Drive: /open?id=<ID>
    gd_open = re.search(r"drive\.google\.com/open\?id=([^&]+)", url)
    if gd_open:
        file_id = gd_open.group(1)
        return f"https://drive.google.com/uc?export=download&confirm=t&id={file_id}"

    # Dropbox: ?dl=0 → ?dl=1
    if "dropbox.com" in url:
        return re.sub(r"[?&]dl=0", "?dl=1", url)

    # OneDrive share: 1drv.ms o sharepoint
    if "1drv.ms" in url or "onedrive.live.com" in url:
        return url.replace("redir?", "download?")

    # Otros (S3 presignado, GitHub raw, etc.) → retorna tal cual
    return url


async def cargar_desde_url(url: str, extension: str | None = None) -> pd.DataFrame:
    """
    Descarga un archivo desde una URL y lo lee como DataFrame.

    Admite:
      - URLs directas (CSV/XLSX públicos)
      - Google Drive (links de compartición)
      - Dropbox (links ?dl=0)
      - OneDrive / SharePoint
      - S3 pre-signed URLs
      - GitHub raw

    Args:
        url:       URL original (puede ser link de compartición)
        extension: Extensión forzada (ej: '.csv'). Si es None, se infiere de la URL.

    Returns:
        pd.DataFrame con los datos descargados

    Raises:
        ValueError si la descarga falla o el formato no es soportado
    """
    url_descarga = transformar_url_nube(url)
    logger.info(f"[URL LOADER] Descargando desde: {url_descarga}")

    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=30.0,
            headers={"User-Agent": "EncuestaAPI/1.0"}
        ) as client:
            respuesta = await client.get(url_descarga)
            respuesta.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise ValueError(
            f"Error HTTP {e.response.status_code} al descargar '{url}': {e.response.text[:200]}"
        ) from e
    except httpx.RequestError as e:
        raise ValueError(f"No se pudo conectar a '{url}': {e}") from e

    # Determinar extensión: forzada > Content-Disposition > URL path
    ext = extension
    if not ext:
        content_disp = respuesta.headers.get("content-disposition", "")
        cd_match = re.search(r'filename[^;=\n]*=(["\']?)([^;\n"\']+)\1', content_disp)
        if cd_match:
            fname = cd_match.group(2).strip()
            ext = "." + fname.rsplit(".", 1)[-1].lower() if "." in fname else None

    if not ext:
        path = url.split("?")[0]  # quitar query params
        ext = "." + path.rsplit(".", 1)[-1].lower() if "." in path.split("/")[-1] else None

    if not ext or ext not in EXTENSIONES_SOPORTADAS:
        # Último intento: Content-Type del servidor
        ct = respuesta.headers.get("content-type", "")
        ext = _ext_desde_content_type(ct)

    if not ext:
        raise ValueError(
            "No se pudo determinar el tipo de archivo. "
            "Proporcione el parámetro 'extension' (ej: '.csv', '.xlsx')."
        )

    return leer_bytes_a_dataframe(respuesta.content, ext)


def _ext_desde_content_type(ct: str) -> str | None:
    """Infiere extensión de archivo a partir del Content-Type HTTP."""
    mapeo = {
        "text/csv":                "csv",
        "text/plain":              "txt",
        "application/json":        "json",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
        "application/vnd.ms-excel": "xls",
        "application/octet-stream": None,
    }
    for clave, ext in mapeo.items():
        if clave in ct:
            return f".{ext}" if ext else None
    return None


# ──────────────────────────────────────────────
# CARGA DESDE API EXTERNA
# ──────────────────────────────────────────────

async def cargar_desde_api_externa(
    api_url: str,
    metodo: str = "GET",
    headers: dict | None = None,
    payload: dict | None = None,
    campo_datos: str | None = None,
    params: dict | None = None,
) -> list[dict]:
    """
    Consume un endpoint REST externo y extrae una lista de registros de encuesta.

    Args:
        api_url:     URL del endpoint externo (ej: https://mi-sistema.com/api/encuestas)
        metodo:      Verbo HTTP ('GET' o 'POST'). Default: 'GET'
        headers:     Cabeceras HTTP adicionales (Authorization, API-Key, etc.)
        payload:     Cuerpo JSON para peticiones POST
        campo_datos: Clave del JSON que contiene la lista de registros.
                     Si es None, se detecta automáticamente.
        params:      Query parameters adicionales (?page=1&limit=100, etc.)

    Returns:
        Lista de dicts con los registros de encuesta

    Raises:
        ValueError si la API falla o el JSON no tiene la estructura esperada
    """
    _headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if headers:
        _headers.update(headers)

    logger.info(f"[API LOADER] {metodo} → {api_url}")

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
            if metodo.upper() == "GET":
                resp = await client.get(api_url, headers=_headers, params=params)
            elif metodo.upper() == "POST":
                resp = await client.post(api_url, headers=_headers, json=payload, params=params)
            else:
                raise ValueError(f"Método HTTP '{metodo}' no soportado. Use GET o POST.")

            resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise ValueError(
            f"La API externa respondió con error {e.response.status_code}: {e.response.text[:300]}"
        ) from e
    except httpx.RequestError as e:
        raise ValueError(f"No se pudo conectar a la API externa '{api_url}': {e}") from e

    try:
        data: Any = resp.json()
    except Exception:
        raise ValueError("La API externa no devolvió JSON válido.")

    # Si ya es lista → ok
    if isinstance(data, list):
        return data

    # Si es dict → buscar campo de datos
    if isinstance(data, dict):
        if campo_datos and campo_datos in data:
            registros = data[campo_datos]
        else:
            # Detección automática: busca lista más larga en el dict
            listas = {k: v for k, v in data.items() if isinstance(v, list)}
            if not listas:
                raise ValueError(
                    "La API externa devolvió un objeto JSON sin listas de registros. "
                    "Especifique 'campo_datos' con la clave correcta."
                )
            campo_auto = max(listas, key=lambda k: len(listas[k]))
            logger.info(f"[API LOADER] Campo detectado automáticamente: '{campo_auto}'")
            registros = listas[campo_auto]

        if not isinstance(registros, list):
            raise ValueError(
                f"El campo '{campo_datos or campo_auto}' no contiene una lista de registros."
            )
        return registros

    raise ValueError(
        f"Estructura JSON no reconocida. Se esperaba lista o dict, recibido: {type(data).__name__}"
    )
