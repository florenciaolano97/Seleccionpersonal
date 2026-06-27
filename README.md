# AI-RRHH Autopartista Plástica V3 - Avatar Alba

App en Streamlit para preselección inicial de personal en una fábrica autopartista de plásticos.

## Novedad V3

Se agregó **Alba**, un avatar entrevistador virtual integrado en la app.

Alba permite:

- Mostrar una entrevistadora virtual dentro de Streamlit.
- Leer las preguntas en voz alta usando el motor de voz del navegador.
- Guiar la entrevista inicial con un flujo más humano y profesional.
- Mantener la carga de respuestas en campos auditables de Streamlit.
- Usar el sistema sin APIs externas de avatar.

> Importante: esta versión usa Web Speech API del navegador. Funciona mejor en Chrome o Edge. No requiere HeyGen, D-ID ni Synthesia.

## Funciones principales

- Perfil por puesto:
  - Operario/a de inyección plástica
  - Control de calidad
  - Mantenimiento / cambio de moldes
  - Depósito / logística interna
  - Supervisor/a o líder de turno
- Avatar entrevistador Alba con voz del navegador.
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

## Cómo activar el avatar

1. Ejecutar la app.
2. Ir a la pestaña **2. Entrevista virtual**.
3. Activar el switch **Activar avatar entrevistador Alba**.
4. Presionar **Alba pregunta** para que el avatar lea la pregunta en voz alta.
5. Cargar la respuesta del candidato en el campo correspondiente.

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

## Evolución recomendada para avatar profesional

Esta V3 incluye un avatar local simple. Para una versión enterprise, se recomienda evolucionar a:

- Avatar con API externa: D-ID, HeyGen o Synthesia.
- Reconocimiento de voz del candidato con Whisper.
- Text-to-Speech corporativo.
- Frontend React/Next.js para experiencia más fluida.
- Backend FastAPI para separar lógica de negocio, IA y auditoría.

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
