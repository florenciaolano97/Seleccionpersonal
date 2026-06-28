# Alba Recruiter AI — Opción A Universal Estable

Versión estable para Streamlit, pensada para cualquier empresa, industria y puesto.

## Funciones

- Configuración universal de puesto: industria, nivel, responsabilidades, requisitos excluyentes y deseables.
- Carga masiva de CVs en PDF, DOCX o TXT.
- Análisis inicial del CV con motor local explicable.
- Ranking inicial de candidatos del mejor al peor.
- Pase a entrevista con Alba para candidatos aptos o en revisión humana.
- Avatar con D-ID usando endpoint `/talks`.
- Respuesta del candidato por texto o grabación de audio.
- Evaluación de entrevista.
- Ranking final combinando CV + entrevista.
- Informe completo y auditable por candidato.
- Datos administrativos del candidato como DNI, edad, fecha de nacimiento, teléfono o email se pueden registrar, pero no se usan para decidir ni rankear.
- No se requieren datos sensibles de la empresa.

## Instalación

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Configuración D-ID

En el panel izquierdo de Streamlit completar:

```text
D_ID_API_KEY = tu credencial de D-ID
D_ID_SOURCE_URL = URL pública HTTPS de la imagen del avatar, terminada en .jpg/.jpeg/.png/.webp
```

Ejemplo de URL válida:

```text
https://i.postimg.cc/jSwybb4C/4m0Obqg3KQUKRm1IAm-Ja-Hh-PB3qsae-Ih-TWs-Sc-JW3OMD5R-tsn-TJUy-W-xu-J4W1POFJAj-PGBQyh-Ik48GC4PNg-RGD7z.jpg
```

## Uso recomendado

1. Definir el puesto.
2. Subir CVs masivamente.
3. Analizar CVs y revisar ranking inicial.
4. Entrevistar con Alba a candidatos aptos o en revisión humana.
5. Evaluar entrevista.
6. Descargar ranking final e informes.

## Nota de compliance

La herramienta asiste la preselección, pero la decisión final debe ser humana. Los datos administrativos del candidato pueden registrarse para gestión, pero no deben usarse para puntuar, rankear ni decidir. No se deben cargar datos sensibles o confidenciales de la empresa.
