# AI-RRHH | Alba Avatar Entrevistador con diálogo por voz

Esta versión funciona en Streamlit y permite:

- Avatar real hablando con D-ID (`/talks`).
- Imagen pública del avatar con labios sincronizados.
- Voz humana Microsoft en español.
- Grabación de respuesta del candidato con micrófono.
- Transcripción automática con OpenAI Whisper.
- Diálogo adaptativo: Alba puede repreguntar según la respuesta.
- Evaluación final RRHH con recomendación IA + decisión humana obligatoria.

## Instalación

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Configuración rápida desde la app

En el panel izquierdo de Streamlit pegá:

```text
D_ID_API_KEY = tu credencial D-ID
D_ID_SOURCE_URL = URL pública directa de la imagen del avatar
OPENAI_API_KEY = tu API key de OpenAI
```

`D_ID_SOURCE_URL` debe empezar con `https://` y terminar en `.jpg`, `.jpeg`, `.png` o `.webp`.

Ejemplo válido:

```text
https://i.postimg.cc/hXnXLNwq/alba.jpg
```

## Configuración con secrets

También podés crear `.streamlit/secrets.toml`:

```toml
D_ID_API_KEY = "tu_key_de_did"
D_ID_SOURCE_URL = "https://i.postimg.cc/xxxx/alba.jpg"
OPENAI_API_KEY = "sk-..."
```

## Cómo usar

1. Seleccioná el puesto.
2. Generá el video de Alba para la pregunta actual.
3. El candidato responde por micrófono.
4. Tocá **Transcribir audio**.
5. Revisá el texto.
6. Tocá **Guardar respuesta y continuar diálogo**.
7. Alba genera una repregunta o avanza a la siguiente pregunta.
8. Al finalizar, tocá **Evaluar entrevista**.

## Importante

- Streamlit no es una videollamada en tiempo real. Genera un video hablado por cada pregunta.
- Para que escuche/transcriba, necesitás `OPENAI_API_KEY`.
- La decisión final debe quedar en RR.HH.; la IA solo recomienda.
- No cargar ni usar datos sensibles para decidir.
