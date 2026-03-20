"""
store.py
Almacenamiento en memoria para las encuestas.
Simula una base de datos transaccional (sin persistencia entre reinicios).
"""

from typing import Dict
from models import EncuestaCompleta

# Repositorio principal: key=UUID, value=EncuestaCompleta
encuestas_db: Dict[str, EncuestaCompleta] = {}
