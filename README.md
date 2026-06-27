# AI-RRHH Autopartista Plástica - V4 Avatar Visual

App en Streamlit para preselección inicial de personal en una fábrica autopartista de plásticos.

## Novedad V4

Se incorporó la pantalla visual del avatar **Alba** dentro de la pestaña **2. Entrevista virtual**:

- Avatar visible estilo videollamada.
- Estado **Alba Online**.
- Botón **Alba habla** con voz del navegador.
- Animación visual mientras habla.
- Panel de conversación a la derecha.
- Progreso de preguntas.
- Subtítulos de la pregunta actual.
- Imagen local del avatar en `assets/alba_avatar_scene.png`.

> Importante: esta versión usa imagen + voz del navegador. No requiere HeyGen, D-ID ni API externa de avatar. Para un avatar con movimiento labial real en video, habría que integrar un servicio externo.

## Funciones principales

- Perfil por puesto:
  - Operario/a de inyección plástica
  - Control de calidad
  - Mantenimiento / cambio de moldes
  - Depósito / logística interna
  - Supervisor/a o líder de turno
- Entrevista estructurada por competencias.
- Filtro excluyente inicial.
- Repreguntas adaptativas.
- Recomendación:
  - APROBAR PRIMERA INSTANCIA
  - REVISIÓN HUMANA
  - RECHAZAR PRIMERA INSTANCIA
- Decisión humana final obligatoria.
- Ranking de candidatos.
- Dashboard básico.
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

## Cómo usar el avatar

1. Entrar en **2. Entrevista virtual**.
2. Dejar activado **Activar avatar entrevistador Alba**.
3. Hacer clic en **Alba habla**.
4. Alba lee la pregunta en voz alta y se muestra visualmente en pantalla.
5. Cargar la respuesta en los campos de entrevista debajo para que quede registrada.

## Uso responsable

La herramienta debe usarse como asistencia de primera selección, no como decisión automática final. Evitar cargar datos sensibles como edad, salud, embarazo, religión, sindicalización, estado civil, familia o domicilio exacto.
