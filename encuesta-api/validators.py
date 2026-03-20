"""
validators.py
Listas de referencia y funciones auxiliares de validación para el dominio colombiano.
"""

# Lista oficial de los 32 departamentos de Colombia + Bogotá D.C.
DEPARTAMENTOS_COLOMBIA = {
    "AMAZONAS", "ANTIOQUIA", "ARAUCA", "ATLÁNTICO", "BOLÍVAR",
    "BOYACÁ", "CALDAS", "CAQUETÁ", "CASANARE", "CAUCA",
    "CESAR", "CHOCÓ", "CÓRDOBA", "CUNDINAMARCA", "GUAINÍA",
    "GUAVIARE", "HUILA", "LA GUAJIRA", "MAGDALENA", "META",
    "NARIÑO", "NORTE DE SANTANDER", "PUTUMAYO", "QUINDÍO",
    "RISARALDA", "SAN ANDRÉS Y PROVIDENCIA", "SANTANDER", "SUCRE",
    "TOLIMA", "VALLE DEL CAUCA", "VAUPÉS", "VICHADA",
    "BOGOTÁ D.C.", "BOGOTA D.C."
}

# Escala Likert válida (1 = Muy en desacuerdo, 5 = Muy de acuerdo)
ESCALA_LIKERT = {1, 2, 3, 4, 5}

# Tipos de pregunta soportados
TIPOS_PREGUNTA = {"likert", "porcentaje", "texto", "numero"}

# Géneros reconocidos
GENEROS_VALIDOS = {"masculino", "femenino", "no_binario", "prefiero_no_decir", "otro"}


def normalizar_departamento(valor: str) -> str:
    """Normaliza el departamento a mayúsculas y sin espacios extras."""
    return valor.strip().upper()


def es_departamento_valido(departamento: str) -> bool:
    """Verifica si el departamento pertenece a la lista oficial."""
    return normalizar_departamento(departamento) in DEPARTAMENTOS_COLOMBIA


def es_likert_valido(valor: int) -> bool:
    """Verifica que el puntaje esté en escala Likert (1-5)."""
    return valor in ESCALA_LIKERT


def es_porcentaje_valido(valor: float) -> bool:
    """Verifica que el valor esté en rango de porcentaje (0.0-100.0)."""
    return 0.0 <= valor <= 100.0
