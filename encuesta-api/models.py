"""
models.py
Modelos Pydantic para el sistema de encuestas poblacionales.
Implementa tipos complejos, modelos anidados y validadores de campo.
"""

from typing import List, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator
from validators import (
    DEPARTAMENTOS_COLOMBIA,
    ESCALA_LIKERT,
    GENEROS_VALIDOS,
    normalizar_departamento,
    PERSONAS_HOGAR_MIN,
    OPCIONES_VIVIENDA,
    OPCIONES_SITUACION_LABORAL,
)


# ─────────────────────────────────────────────
# MODELO 1: Encuestado
# ─────────────────────────────────────────────
class Encuestado(BaseModel):
    """
    Datos demográficos del participante de la encuesta.
    Contexto colombiano: estrato 1-6, departamentos oficiales.
    """

    nombre: str = Field(..., min_length=2, max_length=100, description="Nombre completo del encuestado")
    edad: int = Field(..., ge=0, le=120, description="Edad en años (0-120)")
    genero: Optional[str] = Field(None, description="Género del encuestado")
    estrato: int = Field(..., description="Estrato socioeconómico colombiano (1-6)")
    departamento: str = Field(..., description="Departamento de Colombia donde reside")
    municipio: Optional[str] = Field(None, description="Municipio de residencia")
    nivel_educativo: Optional[str] = Field(
        None,
        description="Nivel educativo: primaria, secundaria, tecnico, universitario, posgrado"
    )
    ingresos_mensuales: Optional[float] = Field(
        None, ge=0, description="Ingresos mensuales en COP (≥ 0)"
    )

    # ── Preguntas fijas de la encuesta ─────────────────────────────────────
    personas_hogar: int = Field(
        ...,
        ge=PERSONAS_HOGAR_MIN,
        description="¿Cuántas personas viven en tu hogar (incluyéndote)? — entero ≥ 1"
    )
    vivienda: str = Field(
        ...,
        description="¿La vivienda es propia o alquilada? — valores: propia | alquilada"
    )
    situacion_laboral: str = Field(
        ...,
        description=(
            "¿Cuál es tu situación laboral actual? — valores: "
            "Empleado | Desempleado | Estudiante | Independiente | Jubilado"
        )
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "nombre": "María García",
                    "edad": 34,
                    "genero": "femenino",
                    "estrato": 3,
                    "departamento": "ANTIOQUIA",
                    "municipio": "Medellín",
                    "nivel_educativo": "universitario",
                    "ingresos_mensuales": 2800000.0,
                    "personas_hogar": 4,
                    "vivienda": "propia",
                    "situacion_laboral": "Empleado"
                }
            ]
        }
    }

    # ── Validador mode='before': se ejecuta ANTES de que Pydantic convierta tipos
    # Sirve para limpiar/transformar el dato crudo antes de validarlo
    @field_validator("departamento", mode="before")
    @classmethod
    def normalizar_y_validar_departamento(cls, v):
        """
        mode='before': recibe el valor RAW (puede venir en minúsculas o con espacios).
        Normaliza a mayúsculas antes de validar → permite 'antioquia' o 'ANTIOQUIA'.
        """
        v_normalizado = normalizar_departamento(str(v))
        if v_normalizado not in DEPARTAMENTOS_COLOMBIA:
            raise ValueError(
                f"'{v}' no es un departamento válido de Colombia. "
                f"Ejemplo de valores válidos: ANTIOQUIA, CUNDINAMARCA, BOGOTÁ D.C."
            )
        return v_normalizado

    # ── Validador mode='after': se ejecuta DESPUÉS de la conversión de tipos
    # El valor ya llegó con el tipo correcto (int), solo validamos la regla de negocio
    @field_validator("estrato", mode="after")
    @classmethod
    def validar_estrato(cls, v):
        """
        mode='after': Pydantic ya convirtió el valor a int.
        Validamos la regla colombiana: solo existen estratos del 1 al 6.
        """
        if v not in range(1, 7):
            raise ValueError(
                f"El estrato '{v}' no es válido. En Colombia los estratos son del 1 al 6."
            )
        return v

    @field_validator("genero", mode="before")
    @classmethod
    def validar_genero(cls, v):
        """Normaliza el género a minúsculas y valida contra lista permitida."""
        if v is None:
            return v
        v_lower = str(v).lower().strip()
        if v_lower not in GENEROS_VALIDOS:
            raise ValueError(
                f"Género '{v}' no reconocido. Valores válidos: {sorted(GENEROS_VALIDOS)}"
            )
        return v_lower

    @field_validator("nombre", mode="before")
    @classmethod
    def limpiar_nombre(cls, v):
        """Elimina espacios extras y valida que no sea solo espacios en blanco."""
        nombre = str(v).strip()
        if not nombre:
            raise ValueError("El nombre no puede estar vacío o ser solo espacios.")
        return nombre

    @field_validator("vivienda", mode="before")
    @classmethod
    def validar_vivienda(cls, v):
        """
        Normaliza a minúsculas y valida que la vivienda sea 'propia' o 'alquilada'.
        """
        v_lower = str(v).strip().lower()
        if v_lower not in OPCIONES_VIVIENDA:
            raise ValueError(
                f"Tipo de vivienda '{v}' no válido. "
                f"Valores permitidos: {sorted(OPCIONES_VIVIENDA)}"
            )
        return v_lower

    @field_validator("situacion_laboral", mode="before")
    @classmethod
    def validar_situacion_laboral(cls, v):
        """
        Valida que la situación laboral sea uno de los valores permitidos.
        Se preserva la capitalización original para las opciones definidas
        (Empleado, Desempleado, Estudiante, Independiente, Jubilado).
        """
        # Buscar coincidencia insensible a mayúsculas
        v_strip = str(v).strip()
        match = next(
            (opcion for opcion in OPCIONES_SITUACION_LABORAL
             if opcion.lower() == v_strip.lower()),
            None
        )
        if match is None:
            raise ValueError(
                f"Situación laboral '{v}' no válida. "
                f"Valores permitidos: {sorted(OPCIONES_SITUACION_LABORAL)}"
            )
        return match


# ─────────────────────────────────────────────
# MODELO 2: RespuestaEncuesta
# ─────────────────────────────────────────────
class RespuestaEncuesta(BaseModel):
    """
    Respuesta individual a una pregunta de la encuesta.
    Soporta tipos mixtos: Likert, porcentaje, texto libre o número.
    """

    pregunta_id: str = Field(..., description="Identificador único de la pregunta")
    pregunta_texto: str = Field(..., min_length=5, description="Enunciado de la pregunta")
    tipo_pregunta: str = Field(
        ..., description="Tipo: 'likert' | 'porcentaje' | 'texto' | 'numero'"
    )
    # Union permite respuestas de múltiples tipos según el tipo de pregunta
    respuesta: Union[int, float, str, None] = Field(
        None, description="Valor de la respuesta (int, float, str o null)"
    )
    observacion: Optional[str] = Field(
        None, max_length=500, description="Comentario libre del encuestado"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "pregunta_id": "P001",
                    "pregunta_texto": "¿Qué tan satisfecho está con los servicios públicos?",
                    "tipo_pregunta": "likert",
                    "respuesta": 4,
                    "observacion": "El acueducto falla a veces"
                }
            ]
        }
    }

    @field_validator("tipo_pregunta", mode="before")
    @classmethod
    def validar_tipo_pregunta(cls, v):
        tipos_validos = {"likert", "porcentaje", "texto", "numero"}
        v_lower = str(v).lower().strip()
        if v_lower not in tipos_validos:
            raise ValueError(
                f"Tipo de pregunta '{v}' no válido. Use: {tipos_validos}"
            )
        return v_lower

    # model_validator valida la coherencia entre campos (cross-field validation)
    @model_validator(mode="after")
    def validar_respuesta_segun_tipo(self):
        """
        Valida que la respuesta sea coherente con el tipo de pregunta.
        Ejemplo: una pregunta Likert debe tener respuesta entera entre 1 y 5.
        """
        tipo = self.tipo_pregunta
        resp = self.respuesta

        if resp is None:
            return self  # Respuesta opcional permitida

        if tipo == "likert":
            if not isinstance(resp, int) or resp not in ESCALA_LIKERT:
                raise ValueError(
                    f"Pregunta Likert requiere entero entre 1 y 5. Recibido: {resp}"
                )

        elif tipo == "porcentaje":
            if not isinstance(resp, (int, float)) or not (0.0 <= float(resp) <= 100.0):
                raise ValueError(
                    f"Pregunta de porcentaje requiere número entre 0.0 y 100.0. Recibido: {resp}"
                )

        elif tipo == "numero":
            if not isinstance(resp, (int, float)):
                raise ValueError(
                    f"Pregunta de tipo 'numero' requiere valor numérico. Recibido: {resp}"
                )

        elif tipo == "texto":
            if not isinstance(resp, str):
                raise ValueError(
                    f"Pregunta de tipo 'texto' requiere cadena de caracteres. Recibido: {resp}"
                )

        return self


# ─────────────────────────────────────────────
# MODELO 3: EncuestaCompleta (modelo contenedor)
# ─────────────────────────────────────────────
class EncuestaCompleta(BaseModel):
    """
    Encuesta completa: combina datos del encuestado + lista de respuestas.
    Este es el modelo principal que se recibe en el POST /encuestas/.
    """

    encuestado: Encuestado = Field(..., description="Datos demográficos del participante")
    respuestas: List[RespuestaEncuesta] = Field(
        default=[], min_length=0, description="Lista de respuestas adicionales a preguntas de la encuesta (opcional)"
    )
    fecha_diligenciamiento: Optional[str] = Field(
        None, description="Fecha en formato YYYY-MM-DD"
    )
    encuesta_version: str = Field(
        default="1.0", description="Versión del formulario de encuesta"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "encuestado": {
                        "nombre": "Carlos Rodríguez",
                        "edad": 28,
                        "genero": "masculino",
                        "estrato": 2,
                        "departamento": "CUNDINAMARCA",
                        "municipio": "Soacha",
                        "nivel_educativo": "tecnico",
                        "ingresos_mensuales": 1500000.0
                    },
                    "respuestas": [
                        {
                            "pregunta_id": "P001",
                            "pregunta_texto": "¿Qué tan satisfecho está con los servicios públicos?",
                            "tipo_pregunta": "likert",
                            "respuesta": 3,
                            "observacion": None
                        },
                        {
                            "pregunta_id": "P002",
                            "pregunta_texto": "¿Qué porcentaje de su ingreso destina a alimentación?",
                            "tipo_pregunta": "porcentaje",
                            "respuesta": 35.5,
                            "observacion": "Varía cada mes"
                        }
                    ],
                    "fecha_diligenciamiento": "2026-03-20",
                    "encuesta_version": "1.0"
                }
            ]
        }
    }

    @field_validator("fecha_diligenciamiento", mode="before")
    @classmethod
    def validar_fecha(cls, v):
        """Valida que la fecha tenga formato YYYY-MM-DD si se proporciona."""
        if v is None:
            return v
        import re
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(v)):
            raise ValueError(
                f"Fecha '{v}' no válida. Use formato YYYY-MM-DD (ej: 2026-03-20)"
            )
        return str(v)

    @field_validator("respuestas", mode="after")
    @classmethod
    def validar_respuestas_no_duplicadas(cls, v):
        """Verifica que no haya dos respuestas con el mismo pregunta_id."""
        ids = [r.pregunta_id for r in v]
        if len(ids) != len(set(ids)):
            raise ValueError(
                "Existen respuestas duplicadas para la misma pregunta. "
                "Cada pregunta_id debe aparecer una sola vez."
            )
        return v


# ─────────────────────────────────────────────
# MODELOS DE RESPUESTA API
# ─────────────────────────────────────────────
class EncuestaResponse(BaseModel):
    """Respuesta que devuelve la API al crear/obtener una encuesta."""
    id: str
    encuesta: EncuestaCompleta
    mensaje: Optional[str] = None


class EstadisticasResponse(BaseModel):
    """Resumen estadístico del repositorio de encuestas."""
    total_encuestas: int
    promedio_edad: Optional[float]
    mediana_edad: Optional[float]
    distribucion_estrato: dict
    distribucion_departamento: dict
    distribucion_genero: dict
    promedio_respuestas_por_encuesta: float
    encuestas_por_version: dict
    # Mapa: promedio de satisfacción con el gobierno por departamento
    # { "ANTIOQUIA": 3.5, "CUNDINAMARCA": 2.0, ... }  — None si no hay respuestas
    satisfaccion_gobierno_por_departamento: dict
