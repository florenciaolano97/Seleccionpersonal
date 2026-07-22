# ALBA v2 — Módulo 6

## Reforma de experiencia

- Navegación con íconos y flujo de trabajo visible.
- Panel inicial con métricas y acciones rápidas.
- Centro de entrevistas unificado.
- Asignación rápida de candidatos:
  - subir CV y asignar;
  - elegir del banco;
  - aceptar sugerencias de ALBA;
  - seleccionar etapa inicial.

## Evaluación por competencias

Escala visible para todos los usuarios:

1. Muy por debajo de lo esperado.
2. Bajo.
3. Cumple lo esperado.
4. Sobre lo esperado.
5. Excelente.

Promedio final:

`Suma de puntajes / cantidad de competencias`

Semáforo:

- Verde: 4,0 a 5,0.
- Amarillo: 3,0 a 3,9.
- Rojo: 1,0 a 2,9.

Reglas críticas:

- Crítica con 1: rojo.
- Crítica con 2: amarillo como máximo.
- Críticas con 3 o más: se aplica el promedio.

## Guía de competencias

Incluye Comunicación, Trabajo en equipo, Orientación a resultados,
Adaptabilidad, Resolución de problemas, Organización e Iniciativa.

## Sala de entrevista

- Avatar visible para candidato y entrevistador.
- URL o código oficial de D-ID Agent Embed.
- Videollamada en tiempo real mediante D-ID Agent.
- Vista previa de cámara del candidato.
- Grabación desde el dispositivo del entrevistador.
- Carga de grabaciones exportadas desde Meet, Teams, Zoom, etc.
- Notas y transcripción.
- Análisis de evidencias por competencia.
- Puntaje humano obligatorio de 1 a 5.
- Evidencia por competencia.
- Informe automático con promedio, semáforo, fortalezas,
  aspectos de desarrollo y alertas críticas.
- Descarga del informe en Markdown.

## Streamlit Secrets

Para la videollamada:

DID_AGENT_PUBLIC_URL = "https://..."
DID_AGENT_EMBED_HTML = "<script oficial de D-ID></script>"

Utilizar únicamente el código oficial obtenido desde D-ID Studio.

## Grabación

La grabación WebRTC registra la cámara y micrófono del dispositivo actual.
Para registrar una videollamada externa completa, se recomienda cargar el
archivo exportado por la plataforma utilizada.

## Instalación

Reemplazar app.py, requirements.txt, runtime.txt y README.md.

Hacer commit y reiniciar Streamlit Cloud. Verificar Versión 6.0.0.
