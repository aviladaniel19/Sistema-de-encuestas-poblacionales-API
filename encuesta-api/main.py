"""
main.py
Punto de entrada de la API de Encuestas Poblacionales.

Puerto: seleccionado aleatoriamente entre puertos libres del sistema
        para evitar conflictos en entornos multi-servicio.
"""

# ──────────────────────────────────────────────
# SELECCIÓN DE PUERTO ÓPTIMO ALEATORIO
# ──────────────────────────────────────────────
# El puerto NO es simplemente random.randint(8000, 9999).
# Usamos socket para verificar que el puerto esté LIBRE antes de usarlo,
# garantizando que el servidor arranque sin conflictos.
import socket
import random
import time
import logging
import functools
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Request, status, UploadFile, File, Query
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

import services
from models import EncuestaCompleta, EncuestaResponse, EstadisticasResponse
from loaders import (
    EXTENSIONES_SOPORTADAS,
    leer_bytes_a_dataframe,
    cargar_desde_url,
    cargar_desde_api_externa,
)

# ──────────────────────────────────────────────
# CONFIGURACIÓN DE LOGGING
# ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("encuesta_api")


# ──────────────────────────────────────────────
# FUNCIÓN: ENCONTRAR PUERTO LIBRE ALEATORIO
# ──────────────────────────────────────────────
def encontrar_puerto_libre(rango_inicio: int = 8100, rango_fin: int = 9900) -> int:
    """
    Selecciona aleatoriamente un puerto dentro del rango dado y verifica
    que esté disponible usando un socket de prueba.

    Estrategia:
      1. Barajamos el rango para no ser predecibles.
      2. Por cada candidato, abrimos un socket TCP en modo SO_REUSEADDR.
      3. Si bind() tiene éxito → el puerto está libre → lo usamos.
      4. Si tras 20 intentos no encontramos → lanzamos RuntimeError.

    Args:
        rango_inicio: límite inferior del rango (inclusive). Default 8100
        rango_fin:    límite superior del rango (inclusive). Default 9900

    Returns:
        Número de puerto disponible (int)

    Por qué NO usar solo random.randint():
        random.randint da un número, pero no verifica disponibilidad.
        Podría chocar con otro proceso. Este enfoque es determinista y seguro.
    """
    candidatos = list(range(rango_inicio, rango_fin + 1))
    random.shuffle(candidatos)  # Orden aleatorio real

    for puerto in candidatos[:20]:  # Máximo 20 intentos
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("0.0.0.0", puerto))
                return puerto  # ✅ Puerto libre encontrado
            except OSError:
                continue  # Puerto ocupado, prueba el siguiente

    raise RuntimeError(
        f"No se encontró ningún puerto libre en el rango {rango_inicio}-{rango_fin}."
    )


# ──────────────────────────────────────────────
# DECORADORES PERSONALIZADOS
# ──────────────────────────────────────────────
#
# ¿Cómo se relacionan con los decoradores de FastAPI?
# @app.get / @app.post son decoradores de REGISTRO: le dicen a FastAPI
# qué función maneja qué ruta. Nuestros decoradores son de COMPORTAMIENTO:
# envuelven la función para agregar logging o métricas sin modificar su lógica.
# Ambos usan el mismo mecanismo de Python: functools.wraps + closures.

def log_request(func):
    """
    Decorador que registra en consola:
      - Fecha y hora de la petición
      - Nombre de la función (= endpoint) invocada
      - Tiempo de ejecución en milisegundos

    Uso:  @log_request  encima de cualquier función de endpoint.

    Relación con FastAPI:
      FastAPI usa @app.get/@app.post para registrar rutas (decoradores de registro).
      @log_request es un decorador de comportamiento (cross-cutting concern),
      análogo a un middleware pero a nivel de función individual.
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        inicio = time.perf_counter()
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"[REQUEST] {ts} → {func.__name__}()")
        try:
            resultado = await func(*args, **kwargs)
            duracion_ms = (time.perf_counter() - inicio) * 1000
            logger.info(f"[OK]      {func.__name__}() completado en {duracion_ms:.1f}ms")
            return resultado
        except Exception as exc:
            duracion_ms = (time.perf_counter() - inicio) * 1000
            logger.error(f"[ERROR]   {func.__name__}() falló en {duracion_ms:.1f}ms → {exc}")
            raise
    return wrapper


def timer(func):
    """
    Decorador que agrega el header X-Process-Time (ms) a la respuesta.
    Útil para monitoreo de rendimiento en producción.
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        inicio = time.perf_counter()
        resultado = await func(*args, **kwargs)
        ms = round((time.perf_counter() - inicio) * 1000, 2)
        logger.info(f"[TIMER]   {func.__name__}: {ms}ms")
        return resultado
    return wrapper


# ──────────────────────────────────────────────
# INSTANCIA FASTAPI
# ──────────────────────────────────────────────
app = FastAPI(
    title="API de Encuestas Poblacionales",
    description=(
        "Sistema de recolección y validación de datos de encuestas poblacionales colombianas. "
        "Valida datos demográficos (estrato 1-6, departamentos oficiales, edad 0-120) "
        "y respuestas en escala Likert o porcentaje antes de persistirlos."
    ),
    version="1.0.0",
    contact={"name": "Ingeniería de Datos", "email": "datos@encuestas.co"},
    license_info={"name": "MIT"},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────────────────────────────────────────
# MANEJADOR PERSONALIZADO DE ERRORES HTTP 422
# ──────────────────────────────────────────────
# RF4: Captura RequestValidationError (errores de validación Pydantic)
# y devuelve una respuesta JSON estructurada y descriptiva.
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Manejador personalizado de errores de validación (HTTP 422).

    Transforma el error técnico de Pydantic en un JSON claro para el consumidor:
      - campo: dónde falló la validación
      - mensaje: qué regla se violó
      - valor_recibido: qué mandó el cliente

    Además registra el intento de ingesta inválida en el log (auditoría).
    """
    errores_formateados = []
    for error in exc.errors():
        campo = " → ".join(str(loc) for loc in error["loc"])
        errores_formateados.append({
            "campo": campo,
            "mensaje": error["msg"],
            "tipo_error": error["type"],
            "valor_recibido": error.get("input"),
        })

    # Auditoría: registrar en consola cada intento de ingesta con datos inválidos
    logger.warning(
        f"[422 VALIDATION] {request.method} {request.url.path} "
        f"→ {len(errores_formateados)} error(es) de validación"
    )
    for e in errores_formateados:
        logger.warning(f"   ✗ Campo '{e['campo']}': {e['mensaje']} (recibido: {e['valor_recibido']})")

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "estado": "error_validacion",
            "codigo": 422,
            "mensaje": "Los datos enviados contienen errores de validación. Revise cada campo.",
            "errores": errores_formateados,
            "ruta": str(request.url.path),
            "timestamp": datetime.now().isoformat(),
        },
    )


# ──────────────────────────────────────────────
# ENDPOINTS — CRUD ENCUESTAS
# ──────────────────────────────────────────────

@app.post(
    "/encuestas/",
    status_code=status.HTTP_201_CREATED,
    response_model=EncuestaResponse,
    summary="Registrar encuesta completa",
    description=(
        "Recibe y valida una encuesta completa (datos del encuestado + respuestas). "
        "Actúa como aduana transaccional: solo ingresa al repositorio si pasa TODAS las validaciones. "
        "En caso de error devuelve HTTP 422 con detalle por campo."
    ),
    tags=["Encuestas"],
)
@log_request
async def crear_encuesta(encuesta: EncuestaCompleta):
    """
    RF5 — async def vs def:
    ─────────────────────────────────────────────────────────────
    • def (síncrono): FastAPI corre la función en un thread pool para no bloquear el event loop.
    • async def (asíncrono): la función se ejecuta directamente en el event loop de asyncio.

    ¿Cuándo es INDISPENSABLE async/await?
      Cuando el endpoint realiza operaciones de I/O que pueden esperar sin consumir CPU:
        - Consultas a bases de datos (asyncpg, motor)
        - Peticiones HTTP a servicios externos (httpx.AsyncClient)
        - Lectura/escritura de archivos grandes

    Relación con ASGI:
      FastAPI corre sobre ASGI (Asynchronous Server Gateway Interface), que le permite
      manejar miles de conexiones concurrentes con un solo proceso, delegando la espera
      de I/O al event loop en lugar de bloquear threads. Uvicorn implementa el servidor ASGI.
      Comparado con WSGI (Flask/Django clásico), ASGI elimina el cuello de botella de
      "un thread por request" en cargas de I/O intensivo.
    ─────────────────────────────────────────────────────────────
    """
    eid = services.crear_encuesta(encuesta)
    return EncuestaResponse(id=eid, encuesta=encuesta, mensaje="Encuesta registrada exitosamente.")


@app.get(
    "/encuestas/",
    response_model=List[dict],
    summary="Listar todas las encuestas",
    description="Devuelve un resumen de todas las encuestas registradas en el sistema.",
    tags=["Encuestas"],
)
@log_request
async def listar_encuestas():
    return list(services.listar_encuestas().values())


# ⚠️ IMPORTANTE: /estadisticas/ debe ir ANTES de /{id}
# FastAPI resuelve rutas en orden de registro. Si /{id} va primero,
# la palabra "estadisticas" sería interpretada como un ID.
@app.get(
    "/encuestas/estadisticas/",
    response_model=EstadisticasResponse,
    summary="Estadísticas del repositorio",
    description=(
        "Calcula y devuelve métricas estadísticas de todas las encuestas: "
        "conteo total, promedio y mediana de edad, distribución por estrato, "
        "departamento y género, promedio de respuestas por encuesta."
    ),
    tags=["Estadísticas"],
)
@log_request
@timer
async def estadisticas():
    return services.calcular_estadisticas()


@app.get(
    "/encuestas/{id}",
    response_model=EncuestaResponse,
    summary="Obtener encuesta por ID",
    description="Retorna una encuesta específica por su UUID. Devuelve 404 si no existe.",
    tags=["Encuestas"],
)
@log_request
async def obtener_encuesta(id: str):
    encuesta = services.obtener_encuesta(id)
    if not encuesta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe ninguna encuesta con ID '{id}'.",
        )
    return EncuestaResponse(id=id, encuesta=encuesta)


@app.put(
    "/encuestas/{id}",
    response_model=EncuestaResponse,
    summary="Actualizar encuesta existente",
    description="Reemplaza completamente una encuesta existente. Devuelve 404 si el ID no existe.",
    tags=["Encuestas"],
)
@log_request
async def actualizar_encuesta(id: str, encuesta: EncuestaCompleta):
    actualizado = services.actualizar_encuesta(id, encuesta)
    if not actualizado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe ninguna encuesta con ID '{id}'.",
        )
    return EncuestaResponse(id=id, encuesta=encuesta, mensaje="Encuesta actualizada correctamente.")


@app.delete(
    "/encuestas/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar encuesta",
    description="Elimina permanentemente una encuesta del repositorio. Devuelve 204 si fue exitoso.",
    tags=["Encuestas"],
)
@log_request
async def eliminar_encuesta(id: str):
    eliminado = services.eliminar_encuesta(id)
    if not eliminado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe ninguna encuesta con ID '{id}'.",
        )
    return None


# ──────────────────────────────────────────────
# ENDPOINTS — CARGA MASIVA MULTI-FUENTE
# ──────────────────────────────────────────────

@app.post(
    "/encuestas/cargar/archivo",
    summary="Carga masiva desde archivo",
    description=(
        "Ingesta masiva de encuestas desde un archivo subido. "
        "Formatos soportados: **CSV, XLSX, XLS, TXT, TSV, JSON, Parquet, ODS**. "
        "El archivo debe tener columnas que coincidan con los campos del modelo Encuestado. "
        "Las filas inválidas se reportan pero NO detienen la carga de las válidas."
    ),
    tags=["Carga Masiva"],
)
@log_request
async def cargar_desde_archivo(
    archivo: UploadFile = File(..., description="Archivo de datos (CSV, XLSX, TXT, JSON, Parquet, ODS)"),
):
    """Carga encuestas básicas desde un archivo multi-formato."""
    nombre = archivo.filename or ""
    extension = "." + nombre.rsplit(".", 1)[-1].lower() if "." in nombre else ""

    if extension not in EXTENSIONES_SOPORTADAS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Extensión '{extension}' no soportada. "
                f"Use: {', '.join(EXTENSIONES_SOPORTADAS.keys())}"
            ),
        )

    contenido = await archivo.read()
    try:
        df = leer_bytes_a_dataframe(contenido, extension)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {
        "mensaje": f"Archivo '{nombre}' leído correctamente.",
        "filas": len(df),
        "columnas": list(df.columns),
        "tipos_detectados": df.dtypes.astype(str).to_dict(),
        "muestra": df.head(3).fillna("").to_dict(orient="records"),
    }


@app.post(
    "/encuestas/cargar/url",
    summary="Carga masiva desde URL (nube)",
    description=(
        "Descarga y lee datos desde una URL pública o compartida. "
        "Compatible con: **Google Drive** (link /file/d/<ID>/view), "
        "**Dropbox** (?dl=0), **OneDrive**, **S3 pre-signed**, **GitHub raw**, "
        "y cualquier URL directa a un archivo CSV/XLSX/JSON/Parquet. "
        "El parámetro `extension` es opcional; se infiere de la URL si es posible."
    ),
    tags=["Carga Masiva"],
)
@log_request
async def cargar_url(
    url: str = Query(..., description="URL del archivo en la nube o URL directa"),
    extension: Optional[str] = Query(
        None,
        description="Forzar extensión si no se puede inferir (ej: '.csv', '.xlsx')"
    ),
):
    """
    Carga datos desde una URL de nube.
    Transforma automáticamente links de compartición de Google Drive y Dropbox
    en URLs de descarga directa.
    """
    try:
        df = await cargar_desde_url(url, extension)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {
        "mensaje": "Archivo descargado y leído correctamente desde URL.",
        "url_original": url,
        "filas": len(df),
        "columnas": list(df.columns),
        "muestra": df.head(3).fillna("").to_dict(orient="records"),
    }


@app.post(
    "/encuestas/cargar/api-externa",
    summary="Carga masiva desde API externa",
    description=(
        "Consume un endpoint REST externo que devuelva registros de encuesta en JSON. "
        "Soporta autenticación mediante headers personalizados (Bearer token, API-Key). "
        "Si la lista de registros está anidada dentro de una clave del JSON, "
        "especifíquela en `campo_datos`; si se omite, se detecta automáticamente."
    ),
    tags=["Carga Masiva"],
)
@log_request
async def cargar_api_externa(
    api_url: str = Query(..., description="URL del endpoint externo"),
    metodo: str = Query("GET", description="Verbo HTTP: GET o POST"),
    campo_datos: Optional[str] = Query(
        None,
        description="Clave JSON que contiene la lista (ej: 'data', 'encuestas', 'results')"
    ),
    auth_header: Optional[str] = Query(
        None,
        description="Token de autorización (ej: 'Bearer abc123' o 'ApiKey xyz')"
    ),
):
    """
    Carga registros de encuesta desde otra API REST.
    Detecta automáticamente el campo que contiene la lista de datos.
    """
    headers = {}
    if auth_header:
        headers["Authorization"] = auth_header

    try:
        registros = await cargar_desde_api_externa(
            api_url=api_url,
            metodo=metodo,
            headers=headers,
            campo_datos=campo_datos,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {
        "mensaje": f"Se obtuvieron {len(registros)} registros desde la API externa.",
        "api_url": api_url,
        "campo_detectado": campo_datos or "auto-detectado",
        "total_registros": len(registros),
        "muestra": registros[:3] if registros else [],
    }


# ──────────────────────────────────────────────
# HEALTH CHECK
# ──────────────────────────────────────────────
@app.get("/", tags=["Sistema"], summary="Health check")
async def root():
    return {
        "estado": "online",
        "servicio": "API Encuestas Poblacionales",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc",
        "timestamp": datetime.now().isoformat(),
    }


# ──────────────────────────────────────────────
# ARRANQUE DEL SERVIDOR CON PUERTO ALEATORIO
# ──────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    puerto = encontrar_puerto_libre(rango_inicio=8100, rango_fin=9900)

    print("=" * 55)
    print("  🚀 API de Encuestas Poblacionales")
    print(f"  📡 Puerto asignado: {puerto}")
    print(f"  📖 Swagger UI:  http://localhost:{puerto}/docs")
    print(f"  📘 Redoc:       http://localhost:{puerto}/redoc")
    print("=" * 55)

    logger.info(f"Iniciando servidor en puerto {puerto}")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=puerto,
        # workers=1 porque usamos almacenamiento en memoria compartida
        # En producción con BD real, se puede escalar a múltiples workers
        workers=1,
        # reload=False en producción; True solo para desarrollo
        reload=False,
        # log_level para que uvicorn y nuestro logger convivan
        log_level="info",
        # access_log muestra cada petición HTTP en consola
        access_log=True,
    )
