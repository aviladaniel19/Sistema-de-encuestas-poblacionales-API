"""
services.py
Lógica de negocio: CRUD de encuestas y cálculos estadísticos.
"""

import uuid
import statistics
from typing import Optional
from collections import Counter

from models import EncuestaCompleta, EstadisticasResponse
from store import encuestas_db


# ──────────────────────────────────────────────
# CRUD
# ──────────────────────────────────────────────

def crear_encuesta(encuesta: EncuestaCompleta) -> str:
    """Persiste una encuesta en memoria y devuelve su UUID."""
    eid = str(uuid.uuid4())
    encuestas_db[eid] = encuesta
    return eid


def obtener_encuesta(eid: str) -> Optional[EncuestaCompleta]:
    """Devuelve la encuesta o None si no existe."""
    return encuestas_db.get(eid)


def listar_encuestas() -> dict:
    """Retorna un resumen de todas las encuestas."""
    return {
        eid: {
            "id": eid,
            "nombre": enc.encuestado.nombre,
            "departamento": enc.encuestado.departamento,
            "edad": enc.encuestado.edad,
            "estrato": enc.encuestado.estrato,
            "n_respuestas": len(enc.respuestas),
            "fecha": enc.fecha_diligenciamiento,
            "version": enc.encuesta_version,
        }
        for eid, enc in encuestas_db.items()
    }


def actualizar_encuesta(eid: str, nueva: EncuestaCompleta) -> bool:
    """Actualiza una encuesta existente. Devuelve False si no existe."""
    if eid not in encuestas_db:
        return False
    encuestas_db[eid] = nueva
    return True


def eliminar_encuesta(eid: str) -> bool:
    """Elimina una encuesta. Devuelve False si no existía."""
    if eid not in encuestas_db:
        return False
    del encuestas_db[eid]
    return True


# ──────────────────────────────────────────────
# ESTADÍSTICAS
# ──────────────────────────────────────────────

def calcular_estadisticas() -> EstadisticasResponse:
    """
    Genera un resumen estadístico del repositorio de encuestas:
    - Total de encuestas
    - Promedio y mediana de edad
    - Distribución por estrato, departamento y género
    - Promedio de respuestas por encuesta
    """
    encuestas = list(encuestas_db.values())
    total = len(encuestas)

    if total == 0:
        return EstadisticasResponse(
            total_encuestas=0,
            promedio_edad=None,
            mediana_edad=None,
            distribucion_estrato={},
            distribucion_departamento={},
            distribucion_genero={},
            promedio_respuestas_por_encuesta=0.0,
            encuestas_por_version={},
        )

    edades = [e.encuestado.edad for e in encuestas]
    estratos = [str(e.encuestado.estrato) for e in encuestas]
    deptos = [e.encuestado.departamento for e in encuestas]
    generos = [e.encuestado.genero or "no_especificado" for e in encuestas]
    n_respuestas = [len(e.respuestas) for e in encuestas]
    versiones = [e.encuesta_version for e in encuestas]

    return EstadisticasResponse(
        total_encuestas=total,
        promedio_edad=round(sum(edades) / total, 2),
        mediana_edad=statistics.median(edades),
        distribucion_estrato=dict(Counter(estratos)),
        distribucion_departamento=dict(Counter(deptos)),
        distribucion_genero=dict(Counter(generos)),
        promedio_respuestas_por_encuesta=round(sum(n_respuestas) / total, 2),
        encuestas_por_version=dict(Counter(versiones)),
    )
