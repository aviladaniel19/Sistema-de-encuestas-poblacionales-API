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
    e = Encuestado(
        nombre="Juan", edad=30, estrato=3, departamento="antioquia",
        personas_hogar=4, vivienda="propia", situacion_laboral="Empleado"
    )
    assert e.departamento == "ANTIOQUIA"
    assert e.estrato == 3
    assert e.personas_hogar == 4
    assert e.vivienda == "propia"
    assert e.situacion_laboral == "Empleado"

def test_encuestado_edad_invalida():
    with pytest.raises(ValidationError):
        Encuestado(nombre="X", edad=150, estrato=2, departamento="BOGOTÁ D.C.",
                   personas_hogar=2, vivienda="alquilada", situacion_laboral="Estudiante")

def test_encuestado_estrato_invalido():
    with pytest.raises(ValidationError):
        Encuestado(nombre="X", edad=25, estrato=7, departamento="ANTIOQUIA",
                   personas_hogar=1, vivienda="propia", situacion_laboral="Empleado")

def test_encuestado_departamento_invalido():
    with pytest.raises(ValidationError):
        Encuestado(nombre="X", edad=25, estrato=2, departamento="NARNIA",
                   personas_hogar=1, vivienda="propia", situacion_laboral="Empleado")

def test_encuestado_normaliza_departamento_minusculas():
    e = Encuestado(nombre="Ana", edad=22, estrato=1, departamento="cundinamarca",
                   personas_hogar=2, vivienda="alquilada", situacion_laboral="Estudiante")
    assert e.departamento == "CUNDINAMARCA"

def test_encuestado_genero_invalido():
    with pytest.raises(ValidationError):
        Encuestado(nombre="X", edad=25, estrato=2, departamento="ANTIOQUIA",
                   genero="extraterrestre",
                   personas_hogar=1, vivienda="propia", situacion_laboral="Empleado")

# ── Nuevas preguntas fijas ──────────────────

def test_personas_hogar_invalido_cero():
    with pytest.raises(ValidationError):
        Encuestado(nombre="X", edad=25, estrato=2, departamento="ANTIOQUIA",
                   personas_hogar=0, vivienda="propia", situacion_laboral="Empleado")

def test_personas_hogar_invalido_negativo():
    with pytest.raises(ValidationError):
        Encuestado(nombre="X", edad=25, estrato=2, departamento="META",
                   personas_hogar=-3, vivienda="propia", situacion_laboral="Empleado")

def test_vivienda_valida_normaliza_mayusculas():
    e = Encuestado(nombre="Ana López", edad=30, estrato=1, departamento="TOLIMA",
                   personas_hogar=2, vivienda="PROPIA", situacion_laboral="Jubilado")
    assert e.vivienda == "propia"

def test_vivienda_invalida():
    with pytest.raises(ValidationError):
        Encuestado(nombre="Ana López", edad=30, estrato=1, departamento="CAUCA",
                   personas_hogar=2, vivienda="prestada", situacion_laboral="Empleado")

def test_situacion_laboral_valida_insensible_mayusculas():
    e = Encuestado(nombre="Luis Mora", edad=20, estrato=2, departamento="BOYACÁ",
                   personas_hogar=3, vivienda="alquilada", situacion_laboral="estudiante")
    assert e.situacion_laboral == "Estudiante"

def test_situacion_laboral_invalida():
    with pytest.raises(ValidationError):
        Encuestado(nombre="Luis Mora", edad=40, estrato=3, departamento="NARIÑO",
                   personas_hogar=1, vivienda="propia", situacion_laboral="Freelancer")


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
        encuestado=Encuestado(
            nombre="Laura", edad=29, estrato=4, departamento="VALLE DEL CAUCA",
            personas_hogar=2, vivienda="alquilada", situacion_laboral="Independiente"
        ),
        respuestas=[
            RespuestaEncuesta(pregunta_id="P1", pregunta_texto="¿Satisfecho?",
                              tipo_pregunta="likert", respuesta=3)
        ]
    )
    assert enc.encuestado.nombre == "Laura"

def test_encuesta_respuestas_duplicadas():
    with pytest.raises(ValidationError):
        EncuestaCompleta(
            encuestado=Encuestado(
                nombre="Pedro", edad=40, estrato=2, departamento="ANTIOQUIA",
                personas_hogar=5, vivienda="propia", situacion_laboral="Desempleado"
            ),
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
            encuestado=Encuestado(
                nombre="X", edad=20, estrato=1, departamento="META",
                personas_hogar=1, vivienda="propia", situacion_laboral="Estudiante"
            ),
            respuestas=[
                RespuestaEncuesta(pregunta_id="P1", pregunta_texto="¿Q?",
                                  tipo_pregunta="texto", respuesta="ok")
            ],
            fecha_diligenciamiento="20-03-2026"
        )
