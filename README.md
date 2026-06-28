# AI-RRHH Alba V12 — versión estable Streamlit Cloud

Esta versión elimina `streamlit-webrtc`, porque en Streamlit Cloud puede disparar el error de frontend:

`removeChild: The node to be removed is not a child of this node`

## Qué incluye

- Cámara en vivo del navegador con HTML/JS estable.
- Micrófono con `streamlit-mic-recorder`.
- Transcripción local con `faster-whisper`, sin OpenAI API.
- Avatar Alba hablando con D-ID `/talks`.
- Informe claro: avanzar, revisión humana o rechazar primera instancia.

## Configuración

En el panel izquierdo pegá:

- `D_ID_API_KEY`
- `D_ID_SOURCE_URL`

Ejemplo de URL válida:

```text
https://i.postimg.cc/jSwybb4C/4m0Obqg3KQUKRm1IAm-Ja-Hh-PB3qsae-Ih-TWs-Sc-JW3OMD5R-tsn-TJUy-W-xu-J4W1POFJAj-PGBQyh-Ik48GC4PNg-RGD7z.jpg
```

## Instalación local

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Cloud

Subí estos archivos:

- app.py
- requirements.txt
- runtime.txt
- packages.txt
- README.md

Después: **Manage app → Reboot app**.

## Importante

Esta versión muestra cámara en vivo y graba audio por separado. Streamlit no es ideal para una videollamada real 100% sincronizada. Para una experiencia enterprise de videollamada continua, conviene migrar a React + FastAPI.
