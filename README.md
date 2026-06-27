# AI-RRHH Autopartista Plástica - V6 Avatar Dinámico

App Streamlit para preselección inicial de personal con entrevistadora virtual **Alba**.

## Qué incluye esta versión

- Avatar visual visible en pantalla.
- Animación simulada de diálogo: movimiento sutil, boca animada y ondas mientras habla.
- Voz automática mediante Web Speech API del navegador.
- Selección automática de voz en español si el navegador la tiene disponible.
- Botones: repetir respuesta, interrumpir, Alba habla.
- Panel de conversación estilo plataforma moderna.
- Preguntas por puesto y navegación anterior/siguiente.
- Filtro excluyente, evaluación IA/reglas, decisión humana, ranking y dashboard.

## Importante sobre la voz y el avatar

Esta versión funciona sin pagar APIs externas. Usa la voz instalada en el navegador/sistema operativo. Para que la voz suene más humana:

- Usar Google Chrome o Microsoft Edge.
- En Windows, instalar voces en español desde Configuración > Hora e idioma > Voz.
- En Mac, activar voces en español desde Accesibilidad / Voz.

Para un avatar real con labios sincronizados y voz humana premium se requiere integrar servicios externos como HeyGen, D-ID o ElevenLabs.

## Instalación

```bash
python -m venv venv
venv\Scripts\activate   # Windows
# source venv/bin/activate  # Mac/Linux
pip install -r requirements.txt
streamlit run app.py
```

## Configurar OpenAI

En Streamlit Cloud > Settings > Secrets:

```toml
OPENAI_API_KEY = "tu_api_key"
```

La app también funciona sin API key usando motor local por reglas.
