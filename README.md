# AI-RRHH Autopartista — Streamlit + Avatar D-ID

Esta versión usa **Streamlit** y el endpoint correcto de D-ID para generar un avatar real hablando desde texto:

```text
POST https://api.d-id.com/talks
GET  https://api.d-id.com/talks/{id}
```

No uses `POST /translations`: ese endpoint es para traducir videos existentes, no para crear un avatar entrevistador desde una imagen.

## Qué hace la app

- Entrevistador virtual **Alba**.
- Genera un video hablado por cada pregunta usando D-ID.
- Usa voz humana Microsoft en español.
- Muestra el video del avatar en Streamlit.
- Registra respuestas del candidato.
- Evalúa el perfil con OpenAI o motor local de reglas.
- Genera recomendación: aprobar primera instancia, revisión humana o rechazar primera instancia.
- Mantiene decisión humana final obligatoria.
- Exporta evaluación a Excel.

## Archivos

```text
ai_rrhh_streamlit_did_final/
├── app.py
├── requirements.txt
├── README.md
└── .streamlit/
    └── secrets.toml   # crear localmente, no subir a GitHub
```

## 1. Instalar

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate

pip install -r requirements.txt
```

## 2. Configurar D-ID

Necesitás dos datos:

### D_ID_API_KEY

En D-ID:

1. Entrar a la cuenta.
2. Ir a API / API Keys.
3. Copiar la API Key.

Podés pegarla con o sin la palabra `Basic`; la app la normaliza automáticamente.

### D_ID_SOURCE_URL

Es la imagen base de Alba.

Debe ser:

- URL pública.
- HTTPS.
- Link directo a imagen.
- Terminación `.jpg`, `.jpeg`, `.png` o `.webp`.

Ejemplo válido:

```text
https://res.cloudinary.com/tu-cuenta/image/upload/alba.png
```

No sirve una imagen local como:

```text
assets/alba.png
```

D-ID necesita acceder a la imagen desde internet.

## 3. Crear `.streamlit/secrets.toml`

Crear una carpeta llamada `.streamlit` y dentro un archivo `secrets.toml`:

```toml
OPENAI_API_KEY = "tu_openai_key_opcional"
D_ID_API_KEY = "tu_did_api_key"
D_ID_SOURCE_URL = "https://tu-url-publica/alba.png"
```

OpenAI es opcional: si no lo cargás, la app evalúa con motor local de reglas.

## 4. Ejecutar

```bash
streamlit run app.py
```

## 5. Uso dentro de la app

1. Entrar a la pestaña **1. Datos**.
2. Cargar puesto, candidato, CV y consentimiento.
3. Ir a **2. Avatar entrevistador**.
4. Presionar **Generar avatar hablando esta pregunta**.
5. Esperar a que D-ID genere el video.
6. Reproducir el video.
7. Escribir la respuesta del candidato.
8. Guardar respuesta y avanzar.
9. Al finalizar, ir a **3. Evaluación**.

## Voces disponibles

La app incluye voces Microsoft, por ejemplo:

- `es-AR-ElenaNeural`
- `es-AR-TomasNeural`
- `es-ES-ElviraNeural`
- `es-ES-AlvaroNeural`
- `es-MX-DaliaNeural`
- `es-MX-JorgeNeural`

## Importante

Streamlit permite hacerlo, pero no es una videollamada en tiempo real. El flujo correcto es:

```text
Texto de pregunta → D-ID genera video → Streamlit muestra video → candidato responde → siguiente pregunta
```

Para conversación en tiempo real con avatar continuo, conviene React + FastAPI. Para MVP y demo funcional, Streamlit + D-ID es suficiente.
