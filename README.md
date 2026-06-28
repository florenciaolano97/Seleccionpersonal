# Alba — videollamada de selección en Streamlit

Versión V9: cámara en vivo, micrófono dentro de la videollamada, grabación de respuestas, transcripción local con Faster Whisper, diálogo local con Ollama y avatar hablado con D-ID.

## Qué hace

- Muestra una videollamada del candidato con cámara y micrófono usando `streamlit-webrtc`.
- Permite grabar la respuesta hablada del candidato desde la misma sesión de cámara.
- Transcribe localmente con `faster-whisper`, sin OpenAI API.
- Genera la siguiente pregunta con Ollama local, si está disponible.
- Genera video de Alba hablando con D-ID usando `/talks`.
- Emite un informe claro con recomendación: avanzar, revisión humana o rechazar primera instancia.
- El informe explica motivos, evidencias, fortalezas, riesgos y brechas.
- La evaluación no verbal se limita a observables técnicos seguros: cámara activa, presencia visible aproximada y estabilidad técnica. No infiere emociones ni personalidad.

## Instalación

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Configuración requerida

En el panel izquierdo de Streamlit completar:

```text
D_ID_API_KEY
D_ID_SOURCE_URL
```

`D_ID_SOURCE_URL` debe ser una URL pública directa HTTPS y terminar en `.jpg`, `.jpeg`, `.png` o `.webp`.

Ejemplo:

```text
https://i.postimg.cc/jSwybb4C/4m0Obqg3KQUKRm1IAm-Ja-Hh-PB3qsae-Ih-TWs-Sc-JW3OMD5R-tsn-TJUy-W-xu-J4W1POFJAj-PGBQyh-Ik48GC4PNg-RGD7z.jpg
```

## Ollama local

Para diálogo/evaluación local:

```bash
ollama pull llama3.1
ollama serve
```

Si Ollama no está activo, la app usa scoring local por reglas.

## Uso

1. Iniciar Streamlit.
2. Completar D-ID API key y URL de imagen.
3. Tocar START en la videollamada y permitir cámara + micrófono.
4. Generar/reproducir pregunta con Alba.
5. Tocar “Iniciar grabación”.
6. El candidato responde hablando.
7. Tocar “Detener”.
8. Tocar “Transcribir”.
9. Revisar/corregir texto.
10. Tocar “Enviar y que Alba responda”.

## Límite importante

Streamlit permite un MVP estilo videollamada, pero no es igual a una videollamada profesional en tiempo real. El flujo recomendado es por turnos: Alba habla, candidato responde, se transcribe, Alba genera la próxima pregunta.
