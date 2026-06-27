# AI-RRHH Autopartista Plástica - V5 Avatar visible

App en Streamlit para preselección inicial con entrevistadora virtual **Alba**.

## Corrección V5

- El avatar ahora se renderiza como imagen `<img>` visible, no como fondo CSS.
- Se agregó fallback embebido dentro de `app.py`, por lo que Alba se ve incluso si falta la carpeta `assets`.
- La carpeta `assets/` sigue incluida para mejor calidad.
- Botón **Alba habla** usa la voz del navegador.

## Ejecutar

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Activar avatar

Ingresar a la pestaña **2. Entrevista virtual** y activar **Activar avatar entrevistador Alba**.
