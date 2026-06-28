# AI Interviewer Platform

Plataforma base para entrevistador virtual aplicable a múltiples industrias, perfiles y niveles de puesto.

## Objetivo

Crear una solución profesional de entrevista inicial asistida por IA con:

- Avatar entrevistador.
- Cámara y micrófono del candidato.
- Grabación de respuestas.
- Transcripción.
- Diálogo adaptativo.
- Evaluación por competencias.
- Informe final auditable.
- Decisión final humana obligatoria.

## Arquitectura

```text
frontend/  React + Vite
backend/   FastAPI
```

## Qué incluye esta versión base

- Frontend moderno tipo videollamada.
- Cámara del candidato vía navegador.
- Grabación de audio/video local del navegador.
- Backend FastAPI con endpoints para:
  - crear entrevista,
  - generar pregunta,
  - guardar respuesta,
  - evaluar candidato,
  - generar informe final,
  - generar video de avatar con D-ID.
- Catálogo configurable de industrias, familias de puesto y competencias.
- Motor local de evaluación por reglas como fallback.
- Preparado para conectar LLM local vía Ollama o API externa.

## Variables de entorno backend

Crear `backend/.env`:

```env
D_ID_API_KEY=tu_key_de_did
D_ID_SOURCE_URL=https://i.postimg.cc/xxxx/avatar.jpg
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1
USE_OLLAMA=false
```

## Instalación backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Mac/Linux
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Instalación frontend

```bash
cd frontend
npm install
npm run dev
```

Abrir:

```text
http://localhost:5173
```

## D-ID

Para que el avatar hable con labios sincronizados necesitás:

- `D_ID_API_KEY`
- `D_ID_SOURCE_URL` con imagen pública HTTPS terminada en `.jpg`, `.jpeg`, `.png` o `.webp`

El backend usa el endpoint `/talks` de D-ID.

## Sobre evaluación no verbal

La plataforma NO infiere personalidad, emociones, honestidad, inteligencia ni salud a partir de la cara o gestos.

Solo deja preparado el lugar para registrar observables seguros, por ejemplo:

- cámara encendida,
- audio claro,
- respuesta completa,
- interrupciones técnicas,
- necesidad de repetir pregunta,
- coherencia verbal.

La decisión final debe ser humana.
