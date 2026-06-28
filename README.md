# AI-RRHH | Alba entrevistadora virtual con cámara, voz y D-ID

Esta versión permite:

- Avatar Alba hablando con labios sincronizados usando D-ID `/talks`.
- Cámara encendida del candidato usando `streamlit-webrtc`.
- Grabación de respuesta por micrófono.
- Transcripción automática con OpenAI Whisper (`whisper-1`).
- Repreguntas adaptativas con OpenAI.
- Evaluación de respuestas verbales y observables no verbales seguros.
- Historial local en `data/entrevistas_alba.csv`.

## Importante sobre evaluación no verbal

La app NO infiere emociones, personalidad, salud, honestidad ni aptitud por gestos o apariencia. Solo registra observables técnicos seguros:

- cámara encendida,
- audio comprensible,
- continuidad técnica,
- respuesta verbal ordenada.

La decisión final debe ser humana.

## Instalación

```bash
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Mac/Linux
pip install -r requirements.txt
streamlit run app.py
```

## Configuración necesaria

Podés pegar las claves directamente en el panel izquierdo de Streamlit.

### D_ID_API_KEY

Pegá la credencial de D-ID con formato:

```text
usuario:password
```

La app la convierte automáticamente a `Basic base64(...)`.

### D_ID_SOURCE_URL

Pegá la URL pública directa de la imagen de Alba. Debe empezar con `https://` y terminar en `.jpg`, `.jpeg`, `.png` o `.webp`.

Ejemplo:

```text
https://i.postimg.cc/jSwybb4C/avatar.jpg
```

### OPENAI_API_KEY

Necesaria para:

- transcribir audio,
- generar repreguntas,
- evaluar respuestas.

## Uso recomendado

1. Completar claves en sidebar.
2. Activar cámara del candidato.
3. Generar video de Alba.
4. El candidato responde con micrófono.
5. Transcribir automáticamente.
6. Revisar o corregir texto.
7. Guardar respuesta y continuar.
8. Al final, evaluar entrevista completa.
