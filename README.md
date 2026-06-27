# AI-RRHH Autopartista Plástica

App en Streamlit para preselección inicial de personal en una fábrica autopartista de plásticos.

## Funciones principales

- Perfil por puesto:
  - Operario/a de inyección plástica
  - Control de calidad
  - Mantenimiento / cambio de moldes
  - Depósito / logística interna
  - Supervisor/a o líder de turno
- Entrevista estructurada por competencias.
- Recomendación:
  - APROBAR PRIMERA INSTANCIA
  - REVISIÓN HUMANA
  - RECHAZAR PRIMERA INSTANCIA
- Fundamento laboral auditable.
- Detección de alertas críticas.
- Detección de datos sensibles/no pertinentes.
- Exportación a Excel, CSV y JSON.
- Historial local en `data/evaluaciones_rrhh.csv`.
- Modo IA con OpenAI si hay API key.
- Modo local por reglas si no hay API key.

## Instalación local

```bash
python -m venv venv
source venv/bin/activate  # Mac/Linux
# venv\Scripts\activate  # Windows

pip install -r requirements.txt
streamlit run app.py
```

## Configurar OpenAI en Streamlit Cloud

En `Settings > Secrets`, agregar:

```toml
OPENAI_API_KEY = "tu_api_key"
```

La app también funciona sin API key usando el motor local por reglas.

## Recomendación de uso responsable

La herramienta debe usarse como asistencia de primera selección, no como decisión automática final.  
Evitar cargar datos sensibles como edad, salud, embarazo, religión, sindicalización, estado civil, familia o domicilio exacto.

## Estructura recomendada para GitHub

```text
hr_autopartista_app/
├── app.py
├── requirements.txt
├── README.md
└── data/
```
