# Alba Recruiter AI — Opción A estable universal

Plataforma Streamlit estable para entrevista inicial con avatar D-ID, evaluación por competencias, informe completo y ranking de candidatos.

## Qué incluye

- Avatar Alba hablando con D-ID (`/talks`).
- Entrevista estructurada por puesto, industria y nivel.
- Sirve para cualquier industria, empresa y perfil.
- Datos administrativos del candidato: nombre, DNI, teléfono, email, fecha de nacimiento y edad.
- Esos datos se registran, pero **no se usan para puntuar, rankear ni decidir**.
- Informe claro: avanzar, revisión humana o rechazar primera instancia.
- Ranking de candidatos del mejor al peor.
- Exportación a Excel y JSON.
- Sin videollamada pesada, sin `streamlit-webrtc`, sin librerías complejas.

## Instalación local

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Cloud

Subir estos archivos:

```text
app.py
requirements.txt
README.md
```

Luego ir a `Manage app > Reboot app`.

## D-ID

Completar en el panel izquierdo:

```text
D_ID_API_KEY
D_ID_SOURCE_URL
```

La URL debe ser pública y terminar en `.jpg`, `.jpeg`, `.png` o `.webp`.

Ejemplo:

```text
https://i.postimg.cc/jSwybb4C/4m0Obqg3KQUKRm1IAm-Ja-Hh-PB3qsae-Ih-TWs-Sc-JW3OMD5R-tsn-TJUy-W-xu-J4W1POFJAj-PGBQyh-Ik48GC4PNg-RGD7z.jpg
```

## Política de datos

- No cargar información confidencial de empresa si no es necesaria.
- Los datos personales administrativos del candidato pueden registrarse para gestión.
- No se usan para score ni ranking: DNI, teléfono, edad, fecha de nacimiento, email, domicilio.
- La evaluación se basa solo en evidencias laborales.
- La decisión final debe ser humana.
