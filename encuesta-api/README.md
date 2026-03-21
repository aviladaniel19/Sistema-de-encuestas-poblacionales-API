# 📊 API de Encuestas Poblacionales

API REST construida con **FastAPI + Pydantic v2** para gestionar encuestas poblacionales colombianas. Actúa como aduana transaccional: valida rigurosamente cada dato antes de persistirlo.

---

## 🗂️ Estructura del proyecto

```
encuesta-api/
├── main.py          # FastAPI, endpoints, decoradores, puerto aleatorio
├── models.py        # Modelos Pydantic (Encuestado, RespuestaEncuesta, EncuestaCompleta)
├── validators.py    # Departamentos de Colombia y reglas auxiliares
├── services.py      # Lógica de negocio y estadísticas
├── store.py         # Almacenamiento en memoria
├── loaders.py       # Motor de ingesta multi-formato y multi-fuente
├── requirements.txt
├── .gitignore
└── tests/
    ├── test_models.py
    └── test_endpoints.py
```

---

## ⚙️ Instalación y ejecución

### 1. Clonar el repositorio
```bash
git clone <url-del-repo>
cd encuesta-api
```

### 2. Crear entorno virtual
**Usamos `venv`** (incluido en Python estándar, sin dependencias externas):
```bash
python -m venv .venv

# Activar en macOS/Linux:
source .venv/bin/activate

# Activar en Windows:
.venv\Scripts\activate
```

> **¿Por qué `venv` y no `conda`?**  
> `venv` es suficiente para proyectos Python puro. `conda` agrega valor cuando se necesita gestionar versiones de Python o dependencias de paquetes no-Python (como CUDA, R, etc.).

### 3. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 4. Ejecutar la API
```bash
python main.py
```

El servidor selecciona **automáticamente un puerto libre** entre 8100 y 9900.  
La salida en consola mostrará el puerto asignado:

```
=======================================================
  🚀 API de Encuestas Poblacionales
  📡 Puerto asignado: 8347
  📖 Swagger UI:  http://localhost:8347/docs
  📘 Redoc:       http://localhost:8347/redoc
=======================================================
```

---

## 📡 Endpoints disponibles

### Encuestas (CRUD)
| Verbo | Ruta | Descripción | Status |
|-------|------|-------------|--------|
| `POST` | `/encuestas/` | Crear encuesta | 201 |
| `GET` | `/encuestas/` | Listar todas | 200 |
| `GET` | `/encuestas/estadisticas/` | Estadísticas | 200 |
| `GET` | `/encuestas/{id}` | Obtener por ID | 200/404 |
| `PUT` | `/encuestas/{id}` | Actualizar | 200/404 |
| `DELETE` | `/encuestas/{id}` | Eliminar | 204/404 |

### Carga Masiva
| Verbo | Ruta | Descripción |
|-------|------|-------------|
| `POST` | `/encuestas/cargar/archivo` | Archivo local (CSV, XLSX, JSON, Parquet…) |
| `POST` | `/encuestas/cargar/url` | URL pública o nube (Google Drive, Dropbox…) |
| `POST` | `/encuestas/cargar/api-externa` | Endpoint REST externo |

---

## 📋 Ejemplo de payload

```json
{
  "encuestado": {
    "nombre": "María García",
    "edad": 34,
    "genero": "femenino",
    "estrato": 3,
    "departamento": "ANTIOQUIA",
    "municipio": "Medellín",
    "nivel_educativo": "universitario",
    "ingresos_mensuales": 2800000.0
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
      "pregunta_texto": "¿Qué porcentaje del ingreso destina a vivienda?",
      "tipo_pregunta": "porcentaje",
      "respuesta": 30.5
    }
  ],
  "fecha_diligenciamiento": "2026-03-20",
  "encuesta_version": "1.0"
}
```

---

## 🧪 Ejecutar tests
```bash
pytest tests/ -v
```

---

## 🌐 Documentación interactiva

- **Swagger UI:** `http://localhost:<puerto>/docs`
- **Redoc:** `http://localhost:<puerto>/redoc`
