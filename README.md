# AI-RRHH Alba — versión corregida cámara

Esta versión corrige el error de cámara/MediaPipe:

- Si MediaPipe no está disponible o no expone `face_detection`, la cámara sigue funcionando.
- La app no se cae por `AttributeError`.
- El análisis no verbal queda limitado a observables seguros: cámara activa y detección básica de rostro cuando el entorno lo permite.

## Ejecutar

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Configuración obligatoria para avatar D-ID

En el panel lateral:

- `D_ID_API_KEY`: credencial de D-ID.
- `D_ID_SOURCE_URL`: URL directa y pública del avatar. Ejemplo:

```text
https://i.postimg.cc/jSwybb4C/4m0Obqg3KQUKRm1IAm-Ja-Hh-PB3qsae-Ih-TWs-Sc-JW3OMD5R-tsn-TJUy-W-xu-J4W1POFJAj-PGBQyh-Ik48GC4PNg-RGD7z.jpg
```

## Para diálogo sin OpenAI API

Instalar Ollama local:

```bash
ollama pull llama3.1
ollama serve
```

La transcripción usa Faster Whisper local.
