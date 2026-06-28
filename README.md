# AI RRHH Alba - V11 corrección Streamlit Cloud

Esta versión corrige el error visual `removeChild` usando versiones más estables de Streamlit + streamlit-webrtc y quitando contenedores HTML alrededor del componente de videollamada.

## Instalación local

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Cloud

Subí estos archivos:

- app.py
- requirements.txt
- runtime.txt
- packages.txt
- carpeta .streamlit/config.toml

Después hacé **Manage app → Reboot app**.

## Si vuelve a aparecer `removeChild`

1. Hacé refresh fuerte: Ctrl + F5.
2. Borrá caché del navegador.
3. Reiniciá la app en Streamlit Cloud.
4. No abras dos pestañas de la app al mismo tiempo.

## Configuración

En el panel izquierdo pegá:

- D_ID_API_KEY
- D_ID_SOURCE_URL

Para diálogo local instalá Ollama en tu computadora si corrés local. En Streamlit Cloud, Ollama local no estará disponible salvo que uses un servidor externo.
