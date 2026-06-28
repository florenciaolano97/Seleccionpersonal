# AI-RRHH | Alba Avatar Entrevistador en Streamlit + D-ID

Esta versión usa el endpoint correcto de D-ID: `POST https://api.d-id.com/talks`.
No usa `/translations`, porque ese endpoint es para traducir videos ya existentes.

## 1. Instalar

```bash
pip install -r requirements.txt
streamlit run app.py
```

## 2. Configurar D-ID

La app puede configurarse de dos formas:

### Opción A: desde la pantalla
Pegá en el panel izquierdo:

- `D_ID_API_KEY`
- `D_ID_SOURCE_URL`

### Opción B: con secrets
Crear el archivo:

```text
.streamlit/secrets.toml
```

Contenido:

```toml
OPENAI_API_KEY = "sk-..." # opcional
D_ID_API_KEY = "tu_api_key_de_did"
D_ID_SOURCE_URL = "https://tu-dominio.com/alba.jpg"
```

## 3. Importante sobre D_ID_SOURCE_URL

Tiene que ser una URL pública HTTPS directa a una imagen:

- Correcto: `https://mi-dominio.com/alba.jpg`
- Correcto: `https://res.cloudinary.com/.../alba.png`
- Incorrecto: `C:\Users\...\alba.jpg`
- Incorrecto: link privado de Drive sin descarga pública directa

La imagen ideal debe ser frontal, con buena iluminación, rostro visible y boca cerrada.

## 4. Flujo

1. Elegís puesto.
2. Pegás `D_ID_API_KEY` y `D_ID_SOURCE_URL`.
3. Hacés clic en **Generar video real de esta pregunta**.
4. D-ID devuelve un video donde Alba habla con labios sincronizados.
5. Cargás la respuesta del candidato.
6. Avanzás a la siguiente pregunta.
7. Evaluás y guardás con decisión humana final.
