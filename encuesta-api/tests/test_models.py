"""
tests/test_models.py
Tests unitarios para los modelos Pydantic.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from pydantic import ValidationError
from models import Encuestado, RespuestaEncuesta, EncuestaCompleta


# ── Encuestado ────────────────────────────────

def test_encuestado_valido():
    e = Encuestado(nombre="Juan", edad=30, estrato=3, departamento="antioquia")
    assert e.departamento == "ANTIOQUIA"
    assert e.estrato == 3

def test_encuestado_edad_invalida():
    with pytest.raises(ValidationError):
        Encuestado(nombre="X", edad=150, estrato=2, departamento="BOGOTÁ D.C.")

def test_encuestado_estrato_invalido():
    with pytest.raises(ValidationError):
        Encuestado(nombre="X", edad=25, estrato=7, departamento="ANTIOQUIA")

def test_encuestado_departamento_invalido():
    with pytest.raises(ValidationError):
        Encuestado(nombre="X", edad=25, estrato=2, departamento="NARNIA")

def test_encuestado_normaliza_departamento_minusculas():
    e = Encuestado(nombre="Ana", edad=22, estrato=1, departamento="cundinamarca")
    assert e.departamento == "CUNDINAMARCA"

def test_encuestado_genero_invalido():
    with pytest.raises(ValidationError):
        Encuestado(nombre="X", edad=25, estrato=2, departamento="ANTIOQUIA", genero="extraterrestre")


# ── RespuestaEncuesta ─────────────────────────

def test_respuesta_likert_valida():
    r = RespuestaEncuesta(
        pregunta_id="P1", pregunta_texto="¿Satisfecho?",
        tipo_pregunta="likert", respuesta=4
    )
    assert r.respuesta == 4

def test_respuesta_likert_fuera_de_rango():
    with pytest.raises(ValidationError):
        RespuestaEncuesta(
            pregunta_id="P1", pregunta_texto="¿Satisfecho?",
            tipo_pregunta="likert", respuesta=6
        )

def test_respuesta_porcentaje_valida():
    r = RespuestaEncuesta(
        pregunta_id="P2", pregunta_texto="¿Porcentaje?",
        tipo_pregunta="porcentaje", respuesta=75.5
    )
    assert r.respuesta == 75.5

def test_respuesta_porcentaje_invalida():
    with pytest.raises(ValidationError):
        RespuestaEncuesta(
            pregunta_id="P2", pregunta_texto="¿Porcentaje?",
            tipo_pregunta="porcentaje", respuesta=110.0
        )

def test_respuesta_tipo_invalido():
    with pytest.raises(ValidationError):
        RespuestaEncuesta(
            pregunta_id="P3", pregunta_texto="¿Algo?",
            tipo_pregunta="escala_del_1_al_10", respuesta=7
        )


# ── EncuestaCompleta ──────────────────────────

def test_encuesta_completa_valida():
    enc = EncuestaCompleta(
        encuestado=Encuestado(nombre="Laura", edad=29, estrato=4, departamento="VALLE DEL CAUCA"),
        respuestas=[
            RespuestaEncuesta(pregunta_id="P1", pregunta_texto="¿Satisfecho?",
                              tipo_pregunta="likert", respuesta=3)
        ]
    )
    assert enc.encuestado.nombre == "Laura"

def test_encuesta_respuestas_duplicadas():
    with pytest.raises(ValidationError):
        EncuestaCompleta(
            encuestado=Encuestado(nombre="Pedro", edad=40, estrato=2, departamento="ANTIOQUIA"),
            respuestas=[
                RespuestaEncuesta(pregunta_id="P1", pregunta_texto="¿Q1?",
                                  tipo_pregunta="likert", respuesta=2),
                RespuestaEncuesta(pregunta_id="P1", pregunta_texto="¿Q1 repetida?",
                                  tipo_pregunta="likert", respuesta=3),
            ]
        )

def test_encuesta_fecha_invalida():
    with pytest.raises(ValidationError):
        EncuestaCompleta(
            encuestado=Encuestado(nombre="X", edad=20, estrato=1, departamento="META"),
            respuestas=[
                RespuestaEncuesta(pregunta_id="P1", pregunta_texto="¿Q?",
                                  tipo_pregunta="texto", respuesta="ok")
            ],
            fecha_diligenciamiento="20-03-2026"  # formato incorrecto
        )
