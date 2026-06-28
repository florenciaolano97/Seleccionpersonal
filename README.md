# Alba RRHH — Streamlit sin OpenAI API

Esta versión reemplaza OpenAI API por:

- **Faster Whisper local** para transcribir audio.
- **Ollama local** para diálogo adaptativo y evaluación.
- **D-ID** para generar el video del avatar hablando con labios sincronizados.
- **Streamlit WebRTC** para cámara del candidato.

## 1. Instalar dependencias

```bash
pip install -r requirements.txt
```

> La primera transcripción puede tardar porque `faster-whisper` descarga el modelo elegido.

## 2. Instalar Ollama

Descargar desde: https://ollama.com

Luego ejecutar:

```bash
ollama pull llama3.1
ollama serve
```

En la app usar:

```text
Modelo Ollama: llama3.1
URL Ollama: http://localhost:11434/api/generate
```

## 3. Configurar D-ID

En el panel izquierdo de Streamlit completar:

```text
D_ID_API_KEY = tu credencial D-ID con formato usuario:password
D_ID_SOURCE_URL = URL pública directa de la imagen .jpg/.png/.webp
```

Ejemplo de URL válida:

```text
https://i.postimg.cc/jSwybb4C/4m0Obqg3KQUKRm1IAm-Ja-Hh-PB3qsae-Ih-TWs-Sc-JW3OMD5R-tsn-TJUy-W-xu-J4W1POFJAj-PGBQyh-Ik48GC4PNg-RGD7z.jpg
```

## 4. Ejecutar

```bash
streamlit run app.py
```

## Alcance de evaluación no verbal

La app **no infiere emociones, personalidad, honestidad ni rasgos sensibles** por cámara. Solo registra observables seguros y técnicos: cámara activa, audio comprensible y respuesta ordenada.
