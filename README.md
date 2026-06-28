# AI-RRHH Autopartista | Streamlit + Avatar D-ID

Esta versión permite usar un avatar real hablando dentro de Streamlit mediante D-ID.

## Qué hace

- Entrevista virtual con avatar llamado **Alba**.
- Genera un video hablado por cada pregunta.
- Usa labios sincronizados y voz humana de Microsoft Neural Voices a través de D-ID.
- Guarda respuestas del candidato.
- Evalúa por competencias.
- Genera recomendación: aprobar, revisión humana o rechazar.
- Exige decisión humana final antes de guardar.
- Exporta historial a CSV/Excel.

## Instalación

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Mac/Linux
source venv/bin/activate

pip install -r requirements.txt
streamlit run app.py
```

## Configuración necesaria

Creá una carpeta `.streamlit` y dentro un archivo `secrets.toml`:

```toml
OPENAI_API_KEY = "tu_openai_key"
D_ID_API_KEY = "tu_did_api_key"
D_ID_SOURCE_URL = "https://url-publica-de-tu-avatar/alba.png"
```

También podés cargar `D_ID_API_KEY` y `D_ID_SOURCE_URL` desde la barra lateral de la app.

## Cómo obtener D_ID_API_KEY

1. Crear cuenta en D-ID.
2. Ir a API / Settings.
3. Copiar la API key.
4. Pegarla en `D_ID_API_KEY`.

## Cómo obtener D_ID_SOURCE_URL

D-ID necesita una imagen pública del avatar. La imagen debe:

- estar de frente,
- tener buena iluminación,
- tener rostro visible,
- estar alojada en una URL pública.

Opciones para alojarla:

- Cloudinary,
- GitHub raw,
- S3,
- cualquier hosting público.

Ejemplo:

```toml
D_ID_SOURCE_URL = "https://res.cloudinary.com/mi-cuenta/image/upload/alba.png"
```

## Uso

1. Abrir la app.
2. Ir a **Datos** y cargar candidato, puesto, CV y consentimiento.
3. Ir a **Avatar entrevistador**.
4. Presionar **Generar avatar hablando esta pregunta**.
5. Reproducir el video.
6. Cargar respuesta del candidato.
7. Guardar respuesta y avanzar.
8. Ir a **Evaluación** y evaluar.
9. Seleccionar decisión humana final.
10. Guardar.

## Importante

Streamlit permite lograr un MVP con avatar real, pero no una conversación 100% en tiempo real. El flujo correcto es por turnos: pregunta → video → respuesta → siguiente pregunta.

Para una experiencia tipo videollamada fluida, conviene migrar a React + FastAPI.
