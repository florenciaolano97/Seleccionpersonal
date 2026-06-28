# AI-RRHH Alba V13 estable

Versión estable para Streamlit Cloud sin `streamlit-webrtc`, sin `faster-whisper` y sin dependencias pesadas.

## Qué incluye
- Avatar real hablando con D-ID (`/talks`).
- Preguntas estructuradas por puesto.
- Respuesta del candidato por texto.
- Informe final claro: avanzar, revisión humana o rechazar.
- Sin OpenAI API.
- Sin error `removeChild`.
- Sin error de instalación por dependencias pesadas.

## Configuración
En la barra lateral pegar:
- `D_ID_API_KEY`: tu credencial de D-ID.
- `D_ID_SOURCE_URL`: URL pública de la imagen del avatar terminada en `.jpg`, `.jpeg`, `.png` o `.webp`.

Ejemplo URL válida:
https://i.postimg.cc/jSwybb4C/4m0Obqg3KQUKRm1IAm-Ja-Hh-PB3qsae-Ih-TWs-Sc-JW3OMD5R-tsn-TJUy-W-xu-J4W1POFJAj-PGBQyh-Ik48GC4PNg-RGD7z.jpg

## Importante
Streamlit Cloud no es estable para videollamada WebRTC completa con grabación continua. Para eso conviene una app React/Next.js. Esta versión prioriza que no se rompa y funcione como MVP demostrable.
