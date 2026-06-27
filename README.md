# AI-RRHH Autopartista Plástica V2

App en Streamlit para preselección inicial de personal en una fábrica autopartista de plásticos.

## Funciones principales

- Perfil por puesto:
  - Operario/a de inyección plástica
  - Control de calidad
  - Mantenimiento / cambio de moldes
  - Depósito / logística interna
  - Supervisor/a o líder de turno
- Entrevista estructurada por competencias.
- Filtro excluyente inicial por puesto.
- Repreguntas adaptativas según CV y respuestas.
- Lectura rápida del CV con señales laborales relevantes.
- Recomendación IA/local:
  - APROBAR PRIMERA INSTANCIA
  - REVISIÓN HUMANA
  - RECHAZAR PRIMERA INSTANCIA
- Decisión humana final obligatoria y registrable.
- Ranking de candidatos por score.
- Dashboard básico de evaluaciones.
- Fundamento laboral auditable.
- Detección de alertas críticas.
- Detección de datos sensibles/no pertinentes.
- Exportación a Excel, CSV y JSON.
- Historial local en `data/evaluaciones_rrhh.csv`.
- Registro de decisiones humanas en `data/decisiones_humanas.csv`.
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

## Uso responsable

La herramienta debe usarse como asistencia de primera selección, no como decisión automática final.

Reglas sugeridas:

- Informar al candidato que se usa una herramienta de asistencia.
- No cargar datos sensibles como edad, salud, embarazo, religión, sindicalización, estado civil, familia o domicilio exacto.
- Toda decisión de rechazo debe ser revisada y validada por RR.HH. o jefatura.
- La decisión final humana debe quedar registrada con motivo laboral.
- Revisar periódicamente falsos positivos, falsos negativos y posibles sesgos.

## Estructura recomendada para GitHub

```text
hr_autopartista_app/
├── app.py
├── requirements.txt
├── README.md
└── data/
```
