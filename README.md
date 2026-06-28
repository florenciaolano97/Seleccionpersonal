# AI-RRHH Alba — Streamlit videollamada V10

Esta versión incluye:

- Avatar Alba con D-ID `/talks`.
- Cámara en vivo con `streamlit-webrtc`.
- Micrófono en vivo.
- Transcripción local con `faster-whisper`.
- Diálogo local con Ollama, sin OpenAI API.
- Informe claro de decisión: avanzar, revisión humana o rechazar.

## Importante

El ZIP trae el código y el `requirements.txt`, pero las librerías se instalan cuando ejecutás:

```bash
pip install -r requirements.txt
```

Si estás en Streamlit Cloud, subí también:

- `requirements.txt`
- `runtime.txt`
- `packages.txt`

Después hacé:

**Manage app → Reboot app**

Si no reiniciás la app, Streamlit puede seguir usando dependencias viejas y no aparece el botón START.

## Variables necesarias

En el panel izquierdo de la app pegá:

```text
D_ID_API_KEY=tu_key_de_did
D_ID_SOURCE_URL=https://i.postimg.cc/jSwybb4C/4m0Obqg3KQUKRm1IAm-Ja-Hh-PB3qsae-Ih-TWs-Sc-JW3OMD5R-tsn-TJUy-W-xu-J4W1POFJAj-PGBQyh-Ik48GC4PNg-RGD7z.jpg
```

## Ollama local

Para diálogo sin OpenAI API:

```bash
ollama run llama3.1:8b
```

La app puede funcionar igual con preguntas base si Ollama no está activo.

## Ejecución local

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Nota sobre evaluación no verbal

La app no evalúa emociones, personalidad ni honestidad por la cara. Solo registra observables seguros: cámara activa, presencia, respuesta audible/transcripta y consistencia general de la entrevista.
