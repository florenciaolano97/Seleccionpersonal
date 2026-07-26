# Guía de Integración — ALBA v2 + Inteligencia Artificial

## Resumen

Esta integración eleva ALBA v2 de una ATS tradicional basada en keywords a una
plataforma de selección con **análisis semántico**, **matching inteligente** y
**entrevistas conversacionales adaptativas**.

## Arquitectura

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Candidato     │────▶│  ALBA Conversacional │────▶│  OpenAI GPT-4o  │
│   (Portal Web)  │◀────│  (Avatar + Chat)     │◀────│  (Evaluación)   │
└─────────────────┘     └──────────────────┘     └─────────────────┘
         │
         ▼
┌─────────────────┐
│  Base de Datos  │  ◀── Transcript, puntajes, decisiones documentadas
│   (SQLite)      │
└─────────────────┘
```

## Configuración

### 1. Streamlit Secrets (`secrets.toml`)

```toml
# OpenAI — Motor de IA
OPENAI_API_KEY = "sk-..."
OPENAI_MODEL = "gpt-4o-mini"  # opcional

# D-ID — Avatar parlante (ya existente)
DID_API_KEY = "usuario:password"
DID_SOURCE_URL = "https://tu-cdn.com/alba.png"
DID_VOICE_ID = "es-AR-ElenaNeural"

# SMTP — Invitaciones por email (ya existente)
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = "465"
SMTP_USERNAME = "tu-cuenta@gmail.com"
SMTP_PASSWORD = "contraseña-de-aplicación"
SMTP_FROM_EMAIL = "tu-cuenta@gmail.com"
APP_BASE_URL = "https://tu-app.streamlit.app"
```

### 2. Instalación

```bash
pip install -r requirements.txt
```

### 3. Ejecución

```bash
streamlit run app.py
```

## Flujos Modificados

### Preselección de CV
- **Antes**: Coincidencia exacta de keywords → descartaba sinónimos y transfer skills.
- **Después**: `AlbaAIEngine.analyze_cv()` extrae skills, logros, gaps y red flags con contexto.
- **Fallback**: Si OpenAI falla, usa el parser clásico.

### Matching Búsqueda ↔ Candidato
- **Antes**: Puntaje por pesos de términos exactos.
- **Después**: `AlbaAIEngine.calculate_semantic_match()` evalúa 4 dimensiones (técnica, experiencial, cultural, brechas) con justificación narrativa.
- **Fallback**: Si OpenAI falla, usa el algoritmo de scoring original.

### Entrevista del Candidato
- **Antes**: Formulario estático con preguntas fijas.
- **Después**: Dos modos:
  1. **Clásica**: formulario tradicional (se mantiene).
  2. **Conversacional con ALBA**: chat adaptativo donde la IA profundiza en respuestas vagas, evalúa estructura STAR y guarda transcript completo.

### Evaluación de Respuestas
- **Antes**: Conteo de keywords + heurística de palabras.
- **Después**: `AlbaAIEngine.evaluate_response()` analiza estructura STAR, profundidad, evidencias y devuelve puntaje 1-5 con justificación.
- **Fallback**: Si OpenAI falla, usa la evaluación clásica por keywords.

## Puntos de Integración en app.py

| Función Original | Nueva Lógica | Línea Aprox. |
|------------------|--------------|--------------|
| `parse_cv_text()` | Inserta llamada a `AlbaAIEngine.analyze_cv()` con fallback | ~Línea 1.800 |
| `calculate_match_score()` | Inserta llamada a `AlbaAIEngine.calculate_semantic_match()` con fallback | ~Línea 2.800 |
| `evaluate_interview_answer()` | Inserta llamada a `AlbaAIEngine.evaluate_response()` con fallback | ~Línea 3.800 |
| `render_candidate_interviews()` | Agrega selector de modo (Clásica / Conversacional) | ~Línea 5.500 |
| `render_company_settings()` | Agrega panel de configuración de IA | ~Línea 2.100 |

## Costos Estimados (OpenAI)

| Operación | Tokens Aprox. | Costo USD (GPT-4o mini) |
|-----------|---------------|------------------------|
| Análisis de 1 CV | ~3.000 | $0.0015 |
| Matching 1 CV vs. job | ~4.000 | $0.0020 |
| Evaluar 1 respuesta | ~2.500 | $0.0012 |
| Informe ejecutivo | ~3.500 | $0.0017 |
| **Entrevista completa (5 preguntas)** | **~15.000** | **~$0.0075** |

## Seguridad y Privacidad

- La API key de OpenAI **nunca** se almacena en código ni en GitHub.
- Se lee exclusivamente desde `st.secrets` o variables de entorno.
- Los CVs y respuestas se procesan por la API pero no se usan para entrenar modelos (OpenAI no entrena con API calls de usuarios de negocio).
- El análisis semántico **no** utiliza nombre, edad, género, ubicación ni foto para puntuar.

## Próximos Pasos Sugeridos

1. **Fine-tuning**: Entrenar un modelo propio con decisiones históricas de RR. HH. para mejorar la calibración.
2. **RAG (Retrieval Augmented Generation)**: Conectar con base de conocimiento interna de la empresa para preguntas sobre cultura y valores.
3. **Voz en tiempo real**: Integrar Whisper (STT) + ElevenLabs (TTS) para entrevista 100% por voz.
4. **Análisis de video**: Evaluación de lenguaje no verbal (con consentimiento explícito y solo como insumo humano).
