"""
tests/test_endpoints.py
Tests de integración para los endpoints de la API.
Usa TestClient de FastAPI (sin levantar servidor real).
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient
from main import app
from store import encuestas_db

client = TestClient(app)

# Payload válido reutilizable en todos los tests
ENCUESTA_VALIDA = {
    "encuestado": {
        "nombre": "Laura Martínez",
        "edad": 29,
        "genero": "femenino",
        "estrato": 3,
        "departamento": "ANTIOQUIA",
        "municipio": "Medellín",
        "nivel_educativo": "universitario",
        "ingresos_mensuales": 3200000.0
    },
    "respuestas": [
        {
            "pregunta_id": "P001",
            "pregunta_texto": "¿Qué tan satisfecho está con los servicios públicos?",
            "tipo_pregunta": "likert",
            "respuesta": 4
        },
        {
            "pregunta_id": "P002",
            "pregunta_texto": "¿Porcentaje del ingreso destinado a vivienda?",
            "tipo_pregunta": "porcentaje",
            "respuesta": 30.0
        }
    ],
    "fecha_diligenciamiento": "2026-03-20",
    "encuesta_version": "1.0"
}


@pytest.fixture(autouse=True)
def limpiar_db():
    """Limpia la base de datos en memoria antes de cada test."""
    encuestas_db.clear()
    yield
    encuestas_db.clear()


# ── POST /encuestas/ ──────────────────────────

def test_crear_encuesta_retorna_201():
    resp = client.post("/encuestas/", json=ENCUESTA_VALIDA)
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert data["mensaje"] == "Encuesta registrada exitosamente."


def test_crear_encuesta_datos_invalidos_retorna_422():
    payload = dict(ENCUESTA_VALIDA)
    payload["encuestado"] = dict(ENCUESTA_VALIDA["encuestado"])
    payload["encuestado"]["estrato"] = 10  # inválido
    payload["encuestado"]["departamento"] = "NARNIA"  # inválido
    resp = client.post("/encuestas/", json=payload)
    assert resp.status_code == 422
    body = resp.json()
    assert "errores" in body
    assert body["codigo"] == 422


# ── GET /encuestas/ ───────────────────────────

def test_listar_encuestas_vacio():
    resp = client.get("/encuestas/")
    assert resp.status_code == 200
    assert resp.json() == []


def test_listar_encuestas_con_datos():
    client.post("/encuestas/", json=ENCUESTA_VALIDA)
    resp = client.get("/encuestas/")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


# ── GET /encuestas/{id} ───────────────────────

def test_obtener_encuesta_existente():
    post_resp = client.post("/encuestas/", json=ENCUESTA_VALIDA)
    eid = post_resp.json()["id"]
    resp = client.get(f"/encuestas/{eid}")
    assert resp.status_code == 200
    assert resp.json()["id"] == eid


def test_obtener_encuesta_no_existente_retorna_404():
    resp = client.get("/encuestas/uuid-que-no-existe")
    assert resp.status_code == 404


# ── PUT /encuestas/{id} ───────────────────────

def test_actualizar_encuesta():
    post_resp = client.post("/encuestas/", json=ENCUESTA_VALIDA)
    eid = post_resp.json()["id"]

    actualizado = dict(ENCUESTA_VALIDA)
    actualizado["encuestado"] = dict(ENCUESTA_VALIDA["encuestado"])
    actualizado["encuestado"]["nombre"] = "Laura Actualizada"

    resp = client.put(f"/encuestas/{eid}", json=actualizado)
    assert resp.status_code == 200
    assert resp.json()["encuesta"]["encuestado"]["nombre"] == "Laura Actualizada"


def test_actualizar_encuesta_no_existente_retorna_404():
    resp = client.put("/encuestas/no-existe", json=ENCUESTA_VALIDA)
    assert resp.status_code == 404


# ── DELETE /encuestas/{id} ────────────────────

def test_eliminar_encuesta_existente_retorna_204():
    post_resp = client.post("/encuestas/", json=ENCUESTA_VALIDA)
    eid = post_resp.json()["id"]
    resp = client.delete(f"/encuestas/{eid}")
    assert resp.status_code == 204


def test_eliminar_encuesta_no_existente_retorna_404():
    resp = client.delete("/encuestas/no-existe")
    assert resp.status_code == 404


# ── GET /encuestas/estadisticas/ ──────────────

def test_estadisticas_vacias():
    resp = client.get("/encuestas/estadisticas/")
    assert resp.status_code == 200
    assert resp.json()["total_encuestas"] == 0


def test_estadisticas_con_datos():
    client.post("/encuestas/", json=ENCUESTA_VALIDA)
    resp = client.get("/encuestas/estadisticas/")
    data = resp.json()
    assert data["total_encuestas"] == 1
    assert data["promedio_edad"] == 29.0
    assert "3" in data["distribucion_estrato"]


# ── Health check ──────────────────────────────

def test_health_check():
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["estado"] == "online"
