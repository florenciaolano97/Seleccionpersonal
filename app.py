
import os
import re
import io
import json
import uuid
import hashlib
import base64
import html
from pathlib import Path
from datetime import datetime

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


# =========================================================
# APP RR.HH. - SELECCIÓN INICIAL PARA FÁBRICA AUTOPARTISTA
# =========================================================

APP_TITLE = "AI-RRHH | Selección inicial para fábrica autopartista plástica"
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
HISTORY_FILE = DATA_DIR / "evaluaciones_rrhh.csv"

PROTECTED_OR_FORBIDDEN_TOPICS = [
    "edad",
    "fecha de nacimiento",
    "estado civil",
    "embarazo",
    "hijos",
    "religión",
    "creencia",
    "partido político",
    "sindicato",
    "orientación sexual",
    "salud",
    "discapacidad",
    "nacionalidad",
    "raza",
    "etnia",
    "antecedentes médicos",
    "licencia médica",
    "obra social",
    "domicilio exacto",
]

RED_FLAG_PATTERNS = {
    "seguridad": [
        r"no uso epp",
        r"no usar epp",
        r"sin epp",
        r"me molesta(n)? (los )?guantes",
        r"no respeto procedimiento",
        r"puente(o|ar) seguridad",
        r"anul(o|ar) alarma",
        r"trabajo sin protecci",
    ],
    "conducta": [
        r"me pele(e|o)",
        r"discuto con todos",
        r"falt(e|o) mucho",
        r"llego tarde siempre",
        r"no acepto indicaciones",
        r"no sigo instrucciones",
    ],
    "disponibilidad": [
        r"no puedo turnos",
        r"no puedo rotar",
        r"no trabajo de noche",
        r"no har[ií]a horas extra",
    ],
}

ROLE_PROFILES = {
    "Operario/a de inyección plástica": {
        "descripcion": "Producción en inyectoras, control visual inicial, rebabado, empaque, orden y seguridad.",
        "must_have": [
            "Comprensión de normas de seguridad y uso de EPP.",
            "Capacidad para seguir instrucciones operativas estandarizadas.",
            "Disponibilidad compatible con turnos de fábrica.",
        ],
        "competencies": {
            "Experiencia en producción plástica/autopartista": 0.20,
            "Seguridad industrial y EPP": 0.20,
            "Calidad visual y detección de defectos": 0.15,
            "Disciplina operativa y seguimiento de instrucciones": 0.15,
            "Disponibilidad para turnos": 0.10,
            "Trabajo en equipo": 0.10,
            "Aprendizaje y adaptabilidad": 0.10,
        },
        "questions": [
            "Contame tu experiencia previa en producción, inyección plástica, autopartes o líneas industriales.",
            "¿Qué defectos visuales buscarías en una pieza plástica antes de liberarla o empacarla?",
            "¿Qué elementos de protección personal usarías y qué harías si una máquina parece insegura?",
            "Describí una situación en la que tuviste que seguir una instrucción precisa o un estándar de trabajo.",
            "¿Tenés disponibilidad para turnos rotativos, noche o fines de semana según necesidad productiva?",
            "¿Cómo actuarías si ves que un compañero saltea un paso de seguridad para producir más rápido?",
            "¿Cómo reaccionás cuando un supervisor corrige tu forma de trabajar?",
            "¿Qué te motiva de trabajar en una fábrica autopartista?"
        ],
    },
    "Control de calidad": {
        "descripcion": "Inspección visual/dimensional, registros, no conformidades y comunicación con producción.",
        "must_have": [
            "Rigurosidad en registro y trazabilidad.",
            "Conocimiento básico de medición o disposición para aprender.",
            "Capacidad para detener o escalar una no conformidad.",
        ],
        "competencies": {
            "Calidad visual/dimensional": 0.25,
            "Registro y trazabilidad": 0.20,
            "Comunicación con producción": 0.15,
            "Criterio ante no conformidades": 0.20,
            "Seguridad industrial y EPP": 0.10,
            "Aprendizaje y adaptabilidad": 0.10,
        },
        "questions": [
            "Contame tu experiencia en control de calidad, mediciones, inspección visual o registros.",
            "¿Qué harías si encontrás una pieza fuera de especificación pero producción necesita cumplir el objetivo del turno?",
            "¿Usaste calibre, pie de rey, galgas, plantillas, planillas de control o sistemas de trazabilidad?",
            "¿Cómo documentarías una no conformidad para que sea útil y objetiva?",
            "¿Cómo comunicarías un problema de calidad a un operario o supervisor sin generar conflicto?",
            "¿Qué significa para vos liberar una pieza segura para el cliente?",
            "¿Qué harías si no estás seguro de si un defecto es aceptable o no?",
            "¿Cómo manejás tareas repetitivas que requieren mucha atención?"
        ],
    },
    "Mantenimiento / cambio de moldes": {
        "descripcion": "Soporte técnico a inyectoras, moldes, ajustes, mantenimiento preventivo y correctivo.",
        "must_have": [
            "Cultura de seguridad y bloqueo antes de intervenir equipos.",
            "Experiencia técnica o formación compatible.",
            "Capacidad de diagnóstico y comunicación con producción.",
        ],
        "competencies": {
            "Conocimiento técnico mecánico/eléctrico/neumático": 0.25,
            "Seguridad en intervención de máquinas": 0.20,
            "Diagnóstico de fallas": 0.20,
            "Mantenimiento preventivo": 0.15,
            "Trabajo con producción": 0.10,
            "Registro de intervenciones": 0.10,
        },
        "questions": [
            "Contame tu experiencia en mantenimiento industrial, inyectoras, moldes, neumática, hidráulica o electricidad.",
            "¿Qué pasos de seguridad harías antes de intervenir una máquina?",
            "¿Cómo diagnosticarías una falla repetitiva en una inyectora o periférico?",
            "¿Participaste en cambios de molde, ajustes de proceso o mantenimiento preventivo?",
            "¿Cómo registrás una intervención para que sirva al turno siguiente?",
            "¿Qué harías si producción te presiona para reparar rápido salteando un paso de seguridad?",
            "¿Cómo priorizás varias fallas al mismo tiempo?",
            "¿Qué necesitás para trabajar bien con operarios y supervisores?"
        ],
    },
    "Depósito / logística interna": {
        "descripcion": "Recepción, stock, abastecimiento a línea, movimientos internos, despacho y registros.",
        "must_have": [
            "Orden y trazabilidad de materiales.",
            "Responsabilidad en manejo de cargas y seguridad.",
            "Capacidad de coordinación con producción/calidad.",
        ],
        "competencies": {
            "Orden, stock e inventario": 0.25,
            "Trazabilidad y registros": 0.20,
            "Seguridad en movimiento de materiales": 0.15,
            "Coordinación con producción": 0.15,
            "Responsabilidad y puntualidad": 0.15,
            "Aprendizaje y adaptabilidad": 0.10,
        },
        "questions": [
            "Contame tu experiencia en depósito, logística, inventario, picking, recepción o despacho.",
            "¿Cómo evitarías errores de material o mezcla de lotes en una fábrica autopartista?",
            "¿Qué harías si una línea pide material urgente pero no coincide con el registro de stock?",
            "¿Tenés experiencia con remitos, planillas, códigos, FIFO, lectores o sistemas de stock?",
            "¿Cómo cuidás la seguridad al mover cargas o abastecer una línea?",
            "¿Cómo te organizás cuando hay varias prioridades simultáneas?",
            "¿Qué harías si detectás material mal identificado?",
            "¿Cómo comunicás un faltante a producción sin demorar la operación?"
        ],
    },
    "Supervisor/a o líder de turno": {
        "descripcion": "Coordinación de personas, objetivos de producción, seguridad, calidad, comunicación y escalamiento.",
        "must_have": [
            "Criterio de liderazgo seguro y no autoritario.",
            "Orientación a indicadores con respeto por seguridad y calidad.",
            "Capacidad de resolver conflictos y escalar problemas.",
        ],
        "competencies": {
            "Liderazgo operativo": 0.20,
            "Gestión de seguridad y calidad": 0.20,
            "Planificación del turno": 0.15,
            "Comunicación y manejo de conflictos": 0.15,
            "Uso de indicadores": 0.15,
            "Desarrollo del equipo": 0.10,
            "Registro y escalamiento": 0.05,
        },
        "questions": [
            "Contame tu experiencia coordinando personas, turnos, objetivos de producción o equipos industriales.",
            "¿Qué hacés si el equipo está atrasado y alguien propone saltear un control de calidad o seguridad?",
            "¿Cómo organizás prioridades al inicio de un turno?",
            "¿Qué indicadores usarías para saber si el turno fue bueno?",
            "Describí una situación en la que resolviste un conflicto entre compañeros.",
            "¿Cómo corregís a una persona que no cumple un estándar sin desmotivar al equipo?",
            "¿Cómo registrarías lo ocurrido en el turno para que el siguiente equipo continúe correctamente?",
            "¿Qué significa liderar en una fábrica autopartista?"
        ],
    },
}

KEYWORDS = {
    "Experiencia en producción plástica/autopartista": [
        "inyección", "inyectora", "plástico", "plasticos", "autoparte", "autopartista",
        "molde", "matriz", "rebaba", "rebarbado", "polipropileno", "polietileno", "abs",
        "producción", "linea", "línea", "operario", "extrusora", "soplado"
    ],
    "Seguridad industrial y EPP": [
        "epp", "guantes", "lentes", "protección", "seguridad", "procedimiento",
        "bloqueo", "lockout", "etiquetado", "riesgo", "accidente", "orden", "5s"
    ],
    "Calidad visual y detección de defectos": [
        "calidad", "defecto", "rebaba", "fisura", "mancha", "deformación", "dimensional",
        "visual", "pieza", "rechazo", "no conformidad", "control", "inspección"
    ],
    "Disciplina operativa y seguimiento de instrucciones": [
        "instrucción", "procedimiento", "estándar", "orden", "supervisor", "cumplir",
        "proceso", "pasos", "responsable", "puntual"
    ],
    "Disponibilidad para turnos": [
        "turno", "rotativo", "noche", "mañana", "tarde", "franco", "fines de semana",
        "disponibilidad", "horas extra", "puntualidad"
    ],
    "Trabajo en equipo": [
        "equipo", "compañero", "comunicación", "respeto", "ayuda", "supervisor",
        "grupo", "colaborar", "conflicto"
    ],
    "Aprendizaje y adaptabilidad": [
        "aprender", "capacitación", "adaptar", "mejora", "rápido", "práctica",
        "formación", "manual", "entrenamiento"
    ],
    "Calidad visual/dimensional": [
        "calidad", "dimensional", "calibre", "pie de rey", "vernier", "galga",
        "medición", "plano", "especificación", "tolerancia", "inspección"
    ],
    "Registro y trazabilidad": [
        "registro", "planilla", "trazabilidad", "lote", "sistema", "documentar",
        "remito", "código", "fecha", "firma", "evidencia"
    ],
    "Comunicación con producción": [
        "producción", "operario", "supervisor", "comunicar", "avisar", "escalar",
        "reunión", "equipo", "claro", "respeto"
    ],
    "Criterio ante no conformidades": [
        "no conformidad", "rechazar", "bloquear", "separar", "cuarentena", "escalar",
        "detener", "cliente", "liberar", "criterio"
    ],
    "Conocimiento técnico mecánico/eléctrico/neumático": [
        "mecánica", "eléctrica", "neumática", "hidráulica", "sensor", "plc", "mantenimiento",
        "motor", "bomba", "resistencia", "tablero", "molde"
    ],
    "Seguridad en intervención de máquinas": [
        "bloqueo", "lockout", "energía cero", "seguridad", "epp", "parada", "procedimiento",
        "riesgo", "autorización", "herramienta"
    ],
    "Diagnóstico de fallas": [
        "diagnóstico", "falla", "causa", "síntoma", "prueba", "medir", "repetitiva",
        "corregir", "análisis", "raíz"
    ],
    "Mantenimiento preventivo": [
        "preventivo", "lubricación", "plan", "rutina", "checklist", "inspección",
        "correctivo", "historial", "orden de trabajo"
    ],
    "Trabajo con producción": [
        "producción", "operario", "supervisor", "prioridad", "línea", "turno",
        "comunicación", "coordinar"
    ],
    "Registro de intervenciones": [
        "registro", "orden de trabajo", "reporte", "planilla", "historial", "intervención",
        "observación", "repuesto"
    ],
    "Orden, stock e inventario": [
        "stock", "inventario", "depósito", "orden", "ubicación", "conteo", "picking",
        "fifo", "material", "almacén"
    ],
    "Trazabilidad y registros": [
        "trazabilidad", "lote", "remito", "código", "registro", "planilla", "sistema",
        "etiqueta", "identificación"
    ],
    "Seguridad en movimiento de materiales": [
        "seguridad", "carga", "autoelevador", "zorra", "apiladora", "epp", "peso",
        "pasillo", "movimiento"
    ],
    "Coordinación con producción": [
        "producción", "línea", "abastecer", "supervisor", "prioridad", "material",
        "comunicar", "urgente", "coordinar"
    ],
    "Responsabilidad y puntualidad": [
        "responsable", "puntual", "asistencia", "cumplir", "orden", "compromiso",
        "presentismo"
    ],
    "Liderazgo operativo": [
        "lideré", "liderar", "supervisor", "equipo", "coordiné", "coordinar",
        "personas", "turno", "objetivo"
    ],
    "Gestión de seguridad y calidad": [
        "seguridad", "calidad", "procedimiento", "epp", "no conformidad", "control",
        "estándar", "cliente"
    ],
    "Planificación del turno": [
        "planificar", "prioridad", "turno", "objetivo", "producción", "recursos",
        "organizar", "arranque"
    ],
    "Comunicación y manejo de conflictos": [
        "conflicto", "comunicación", "escuchar", "respeto", "feedback", "corregir",
        "equipo", "acuerdo"
    ],
    "Uso de indicadores": [
        "indicador", "kpi", "scrap", "rechazo", "productividad", "eficiencia",
        "oee", "cumplimiento", "merma", "ausentismo"
    ],
    "Desarrollo del equipo": [
        "capacitar", "entrenar", "desarrollar", "acompañar", "enseñar", "feedback",
        "mejora", "motivación"
    ],
    "Registro y escalamiento": [
        "registro", "escalar", "reporte", "parte", "novedad", "turno", "comunicar",
        "evidencia"
    ],
}


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def stable_candidate_code(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        raw = str(uuid.uuid4())
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:10].upper()
    return f"CAND-{digest}"


def safe_lower(text: str) -> str:
    return (text or "").lower().strip()


def count_keywords(text: str, words):
    t = safe_lower(text)
    total = 0
    for w in words:
        if w.lower() in t:
            total += 1
    return total


def detect_red_flags(text: str):
    t = safe_lower(text)
    findings = []
    for group, patterns in RED_FLAG_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, t):
                findings.append(f"{group}: patrón detectado '{pat}'")
    return findings


def detect_sensitive_data(text: str):
    t = safe_lower(text)
    return [topic for topic in PROTECTED_OR_FORBIDDEN_TOPICS if topic in t]


def local_score_competency(competency: str, text: str) -> int:
    words = KEYWORDS.get(competency, [])
    hits = count_keywords(text, words)
    length_bonus = min(len(text.split()) / 120, 1.0) * 15
    keyword_score = min(hits / 5, 1.0) * 70
    example_bonus = 15 if any(x in safe_lower(text) for x in ["por ejemplo", "situación", "caso", "una vez", "experiencia"]) else 0
    return int(round(min(keyword_score + length_bonus + example_bonus, 100)))


def local_evaluate(role_name: str, candidate_text: str, cv_text: str, strict_binary: bool = False):
    profile = ROLE_PROFILES[role_name]
    full_text = f"{candidate_text}\n{cv_text}".strip()

    red_flags = detect_red_flags(full_text)
    sensitive = detect_sensitive_data(full_text)

    comp_scores = {}
    weighted_sum = 0.0

    for comp, weight in profile["competencies"].items():
        score = local_score_competency(comp, full_text)
        comp_scores[comp] = score
        weighted_sum += score * weight

    final_score = int(round(weighted_sum))

    critical_red_flag = any("seguridad" in rf or "conducta" in rf for rf in red_flags)
    turno_issue = any("disponibilidad" in rf for rf in red_flags)

    if critical_red_flag:
        recommendation = "RECHAZAR PRIMERA INSTANCIA"
        confidence = "Alta"
    elif final_score >= 70 and not turno_issue:
        recommendation = "APROBAR PRIMERA INSTANCIA"
        confidence = "Media" if final_score < 82 else "Alta"
    elif final_score < 55:
        recommendation = "RECHAZAR PRIMERA INSTANCIA"
        confidence = "Media"
    else:
        recommendation = "REVISIÓN HUMANA"
        confidence = "Media"

    if strict_binary and recommendation == "REVISIÓN HUMANA":
        recommendation = "APROBAR PRIMERA INSTANCIA" if final_score >= 62 and not critical_red_flag else "RECHAZAR PRIMERA INSTANCIA"

    strengths = []
    risks = []

    for comp, score in comp_scores.items():
        if score >= 70:
            strengths.append(f"{comp}: evidencia favorable ({score}/100)")
        elif score < 45:
            risks.append(f"{comp}: evidencia insuficiente ({score}/100)")

    if red_flags:
        risks.append("Se detectaron posibles alertas críticas: " + "; ".join(red_flags))
    if sensitive:
        risks.append("El texto incluye posibles datos sensibles/no pertinentes. No deben utilizarse para decidir: " + ", ".join(sensitive))

    if recommendation.startswith("APROBAR"):
        rationale = "El perfil muestra evidencia suficiente para avanzar a una entrevista humana o prueba técnica, con puntaje global compatible con los requisitos del puesto."
    elif recommendation.startswith("RECHAZAR"):
        rationale = "El perfil no reúne evidencia suficiente para avanzar o presenta alertas críticas vinculadas a seguridad, conducta laboral o requisitos operativos del puesto."
    else:
        rationale = "El caso requiere revisión humana porque el puntaje quedó en zona intermedia o existen elementos que no deberían resolverse automáticamente."

    return {
        "recommendation": recommendation,
        "score": final_score,
        "confidence": confidence,
        "competency_scores": comp_scores,
        "strengths": strengths[:6],
        "risks": risks[:6],
        "rationale": rationale,
        "red_flags": red_flags,
        "sensitive_data_detected": sensitive,
        "model_used": "motor_local_reglas",
    }


def get_openai_api_key():
    try:
        if "OPENAI_API_KEY" in st.secrets:
            return st.secrets["OPENAI_API_KEY"]
    except Exception:
        pass
    return os.getenv("OPENAI_API_KEY")



# =========================================================
# FUNCIONES V2 - ENTREVISTADOR VIRTUAL Y CONTROL HUMANO
# =========================================================

KNOCKOUT_RULES = {
    "Operario/a de inyección plástica": [
        ("turnos_rotativos", "¿Puede trabajar turnos rotativos?"),
        ("epp_seguridad", "¿Acepta usar EPP y cumplir procedimientos de seguridad?"),
        ("tareas_repetitivas", "¿Acepta tareas repetitivas de producción y control visual?"),
    ],
    "Control de calidad": [
        ("registro_trazabilidad", "¿Acepta registrar controles y trazabilidad con rigurosidad?"),
        ("criterio_nc", "¿Acepta escalar o bloquear una no conformidad aunque haya presión productiva?"),
        ("atencion_detalle", "¿Puede sostener tareas repetitivas con atención al detalle?"),
    ],
    "Mantenimiento / cambio de moldes": [
        ("seguridad_bloqueo", "¿Acepta bloquear/asegurar la máquina antes de intervenir?"),
        ("formacion_tecnica", "¿Cuenta con formación o experiencia técnica compatible?"),
        ("guardias_turnos", "¿Tiene disponibilidad para urgencias, turnos o guardias según necesidad?"),
    ],
    "Depósito / logística interna": [
        ("orden_stock", "¿Acepta trabajar con registros, stock, lotes y trazabilidad?"),
        ("seguridad_cargas", "¿Acepta normas de seguridad para movimiento de materiales?"),
        ("prioridades", "¿Puede manejar varias prioridades operativas al mismo tiempo?"),
    ],
    "Supervisor/a o líder de turno": [
        ("liderazgo_seguro", "¿Prioriza seguridad y calidad por encima de producir más rápido?"),
        ("gestion_conflictos", "¿Tiene experiencia o criterio para manejar conflictos del equipo?"),
        ("indicadores", "¿Puede trabajar con objetivos, registros e indicadores de turno?"),
    ],
}

NEGATIVE_VALUES = {"No", "No declarado", "No estoy seguro/a"}


def simple_cv_parser(cv_text: str) -> dict:
    """Extrae señales simples del CV para acelerar screening sin usar datos sensibles."""
    t = safe_lower(cv_text)
    signals = {
        "industria": any(w in t for w in ["industria", "fábrica", "fabrica", "producción", "produccion", "planta"]),
        "autopartista_plastica": any(w in t for w in ["autopart", "inyección", "inyeccion", "plástico", "plastico", "molde", "matriz"]),
        "calidad": any(w in t for w in ["calidad", "inspección", "inspeccion", "no conformidad", "control visual"]),
        "mantenimiento": any(w in t for w in ["mantenimiento", "eléctr", "electric", "mecán", "mecan", "neumática", "neumatica", "hidrául"]),
        "logistica": any(w in t for w in ["depósito", "deposito", "logística", "logistica", "stock", "inventario", "picking"]),
        "liderazgo": any(w in t for w in ["supervisor", "líder", "lider", "coordin", "equipo a cargo"]),
        "instrumentos_medicion": any(w in t for w in ["calibre", "pie de rey", "galga", "micrómetro", "micrometro", "vernier"]),
        "turnos_disponibilidad": any(w in t for w in ["turno", "rotativo", "noche", "disponibilidad", "horas extra"]),
    }
    return signals


def build_followup_questions(role_name: str, cv_text: str, answers_text: str, max_questions: int = 4):
    """Genera repreguntas adaptativas locales según brechas detectadas."""
    full = safe_lower(cv_text + "\n" + answers_text)
    cv_signals = simple_cv_parser(cv_text)
    followups = []

    if role_name == "Operario/a de inyección plástica":
        if not cv_signals["autopartista_plastica"]:
            followups.append("No se observa experiencia clara en inyección plástica/autopartista. ¿Qué experiencia similar de producción o línea industrial podés contar?")
        if "epp" not in full and "seguridad" not in full:
            followups.append("¿Qué EPP usarías en planta y qué harías si una máquina o tarea parece insegura?")
        if "defecto" not in full and "calidad" not in full:
            followups.append("¿Qué defectos visuales revisarías antes de liberar o empacar una pieza?")
    elif role_name == "Control de calidad":
        if not cv_signals["instrumentos_medicion"]:
            followups.append("No queda claro si usaste instrumentos de medición. ¿Trabajaste con calibre, galgas, plantillas o registros de control?")
        if "no conformidad" not in full and "rechaz" not in full:
            followups.append("¿Qué harías si encontrás una pieza dudosa pero producción necesita cumplir el objetivo del turno?")
    elif role_name == "Mantenimiento / cambio de moldes":
        if "bloqueo" not in full and "energía cero" not in full and "energia cero" not in full:
            followups.append("Antes de intervenir una máquina, ¿qué pasos de seguridad y bloqueo aplicarías?")
        if not cv_signals["mantenimiento"]:
            followups.append("No se ve experiencia técnica clara. ¿Qué formación o trabajos técnicos hiciste en mecánica, electricidad, neumática o hidráulica?")
    elif role_name == "Depósito / logística interna":
        if "lote" not in full and "trazabilidad" not in full:
            followups.append("¿Cómo evitarías mezcla de lotes o errores de material al abastecer una línea?")
        if not cv_signals["logistica"]:
            followups.append("No queda clara tu experiencia logística. ¿Trabajaste con stock, inventario, recepción, despacho o picking?")
    elif role_name == "Supervisor/a o líder de turno":
        if "conflicto" not in full:
            followups.append("Contame una situación concreta en la que resolviste un conflicto entre compañeros o dentro de un equipo.")
        if "indicador" not in full and "kpi" not in full and "scrap" not in full:
            followups.append("¿Qué indicadores mirarías para saber si un turno productivo fue bueno?")

    if not followups:
        followups.append("Para cerrar, contame un ejemplo concreto de una situación laboral donde tuviste que aprender rápido o adaptarte a una exigencia nueva.")
    return followups[:max_questions]


def knockout_summary(knockout_answers: dict) -> dict:
    negatives = [label for label, value in knockout_answers.items() if value in NEGATIVE_VALUES]
    if len(negatives) >= 2:
        status = "Alerta fuerte: revisar posible rechazo por requisitos excluyentes."
    elif len(negatives) == 1:
        status = "Alerta moderada: requiere validación humana."
    else:
        status = "Sin alertas excluyentes declaradas."
    return {"negatives": negatives, "status": status, "count": len(negatives)}


def human_decision_required_text(ai_recommendation: str) -> str:
    if "REVISIÓN" in ai_recommendation:
        return "Obligatoria: el caso quedó en zona intermedia."
    if "RECHAZAR" in ai_recommendation:
        return "Obligatoria antes de comunicar rechazo."
    return "Obligatoria antes de avanzar formalmente a la siguiente etapa."


def ai_evaluate(role_name: str, candidate_text: str, cv_text: str, strict_binary: bool = False, model: str = "gpt-4.1-mini"):
    api_key = get_openai_api_key()
    if not api_key or OpenAI is None:
        return None, "No hay OPENAI_API_KEY configurada o falta el paquete openai."

    profile = ROLE_PROFILES[role_name]
    client = OpenAI(api_key=api_key)

    schema_instruction = {
        "recommendation": "APROBAR PRIMERA INSTANCIA | REVISIÓN HUMANA | RECHAZAR PRIMERA INSTANCIA",
        "score": "integer 0-100",
        "confidence": "Baja | Media | Alta",
        "competency_scores": {"competencia": "integer 0-100"},
        "strengths": ["lista breve de fortalezas basadas en evidencias laborales"],
        "risks": ["lista breve de riesgos o brechas basadas en requisitos del puesto"],
        "rationale": "fundamento claro, auditable y no discriminatorio",
        "red_flags": ["alertas críticas si existen"],
        "sensitive_data_detected": ["datos sensibles detectados si el texto los incluye"],
        "model_used": "modelo utilizado",
    }

    prompt = f"""
Sos un asistente de RR.HH. para preselección inicial en una fábrica autopartista de plásticos.

Puesto: {role_name}
Descripción: {profile['descripcion']}
Requisitos excluyentes: {profile['must_have']}
Competencias y ponderaciones: {profile['competencies']}

Tarea:
1. Evaluá SOLO evidencias relacionadas con el puesto.
2. No uses ni infieras edad, sexo, embarazo, salud, discapacidad, nacionalidad, religión, política, sindicalización, orientación sexual, estado civil, domicilio exacto ni datos familiares.
3. Si el texto contiene datos sensibles, listalos como "sensitive_data_detected" pero no los uses para puntuar.
4. Fundamentá con razones laborales concretas.
5. Detectá alertas críticas de seguridad, conducta o disponibilidad operacional.
6. Si el caso queda ambiguo, usá "REVISIÓN HUMANA", excepto que strict_binary sea verdadero.
7. strict_binary={strict_binary}. Si strict_binary es verdadero, elegí APROBAR o RECHAZAR, pero explicá la incertidumbre si corresponde.
8. Devolvé EXCLUSIVAMENTE un JSON válido con esta estructura: {json.dumps(schema_instruction, ensure_ascii=False)}

CV / antecedentes declarados:
{cv_text}

Respuestas de entrevista:
{candidate_text}
"""

    try:
        response = client.responses.create(
            model=model,
            input=prompt,
            temperature=0.2,
        )
        raw = getattr(response, "output_text", "")
        if not raw:
            raw = response.model_dump_json()
        match = re.search(r"\{.*\}", raw, re.S)
        if match:
            raw = match.group(0)
        data = json.loads(raw)
        data["model_used"] = model
        return data, None
    except Exception as e:
        return None, str(e)


def make_answers_text(questions, answers):
    blocks = []
    for i, q in enumerate(questions, start=1):
        a = answers.get(f"q_{i}", "")
        blocks.append(f"Pregunta {i}: {q}\nRespuesta {i}: {a}")
    return "\n\n".join(blocks)


def result_to_dataframe(result: dict):
    comp = result.get("competency_scores", {})
    rows = [{"Competencia": k, "Puntaje": v} for k, v in comp.items()]
    return pd.DataFrame(rows)


def history_to_excel_bytes(df: pd.DataFrame):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Evaluaciones", index=False)
    return output.getvalue()


def append_history(row: dict):
    df_new = pd.DataFrame([row])
    if HISTORY_FILE.exists():
        df_old = pd.read_csv(HISTORY_FILE)
        df_all = pd.concat([df_old, df_new], ignore_index=True)
    else:
        df_all = df_new
    df_all.to_csv(HISTORY_FILE, index=False)
    return df_all


def read_history():
    if HISTORY_FILE.exists():
        return pd.read_csv(HISTORY_FILE)
    return pd.DataFrame()


def render_metric_card(label, value, help_text=None):
    st.metric(label, value, help=help_text)


# =========================================================
# AVATAR DINÁMICO ALBA - VISUAL + VOZ DEL NAVEGADOR
# =========================================================
ASSETS_DIR = Path("assets")
AVATAR_IMAGE_PATHS = [
    ASSETS_DIR / "alba_avatar_scene.jpg",
    ASSETS_DIR / "alba_avatar_scene.png",
    Path("/mnt/data/assets/alba_avatar_scene.jpg"),
    Path("/mnt/data/assets/alba_avatar_scene.png"),
]


def image_to_base64(path: Path) -> str:
    try:
        return base64.b64encode(path.read_bytes()).decode("utf-8")
    except Exception:
        return ""


def get_avatar_image_data_uri() -> str:
    """Devuelve la imagen de Alba embebida para que no dependa de rutas relativas."""
    for path in AVATAR_IMAGE_PATHS:
        if path.exists():
            ext = "jpeg" if path.suffix.lower() in [".jpg", ".jpeg"] else "png"
            b64 = image_to_base64(path)
            if b64:
                return f"data:image/{ext};base64,{b64}"
    # SVG fallback si falta la imagen: evita que el panel quede vacío.
    svg = """
    <svg xmlns='http://www.w3.org/2000/svg' width='900' height='700' viewBox='0 0 900 700'>
      <defs><linearGradient id='g' x1='0' x2='1'><stop stop-color='#dff0ff'/><stop offset='1' stop-color='#f3efff'/></linearGradient></defs>
      <rect width='900' height='700' fill='url(#g)'/>
      <circle cx='450' cy='245' r='95' fill='#f2c6a7'/>
      <path d='M340 255c20-125 210-135 235 10 0 0-40-75-125-78-72-2-110 68-110 68z' fill='#3c2415'/>
      <rect x='330' y='345' width='240' height='260' rx='55' fill='#081b33'/>
      <text x='450' y='650' fill='#081b33' font-family='Arial' font-size='28' text-anchor='middle'>Alba AI Recruiter</text>
    </svg>
    """
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def render_alba_dynamic_avatar(question_text: str, candidate_name: str, role_name: str, progress_text: str = "1/10"):
    """Renderiza un avatar visible, con movimiento simulado al hablar y voz natural del navegador.

    Nota: dentro de Streamlit no se puede generar video real con labios sincronizados sin un servicio externo.
    Esta implementación usa imagen + animación CSS + Web Speech API. Para voz humana premium se puede conectar ElevenLabs/HeyGen/D-ID.
    """
    avatar_uri = get_avatar_image_data_uri()
    safe_question = html.escape(question_text or "Hola, soy Alba. Vamos a comenzar la entrevista inicial.")
    safe_candidate = html.escape(candidate_name or "Candidato/a")
    safe_role = html.escape(role_name or "Puesto")
    safe_progress = html.escape(progress_text or "1/10")

    component_html = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
      <meta charset="UTF-8" />
      <style>
        :root {{ --violet:#5b35f5; --blue:#1267ff; --dark:#071b33; --soft:#f3f6ff; }}
        * {{ box-sizing: border-box; }}
        body {{ margin:0; font-family: Inter, Segoe UI, Roboto, Arial, sans-serif; background:#f6f8ff; color:#071b33; }}
        .wrap {{ display:grid; grid-template-columns: 235px 1.15fr 0.9fr; gap:20px; min-height:760px; }}
        .sidebar {{ background:linear-gradient(180deg,#07172d,#061d37); color:white; border-radius:18px; padding:22px 16px; }}
        .brand {{ display:flex; align-items:center; gap:12px; margin-bottom:28px; }}
        .logo {{ width:46px; height:46px; border-radius:12px; background:linear-gradient(135deg,#7b48ff,#00a6ff); display:grid; place-items:center; font-size:30px; font-weight:900; }}
        .brand strong {{ display:block; font-size:22px; }} .brand span {{ opacity:.9; font-size:14px; }}
        .nav {{ display:flex; flex-direction:column; gap:8px; }}
        .nav div {{ padding:13px 14px; border-radius:10px; font-weight:600; opacity:.92; }}
        .nav .active {{ background:linear-gradient(90deg,#6036ff,#324cff); }}
        .safe {{ margin-top:28px; background:rgba(255,255,255,.08); border:1px solid rgba(255,255,255,.08); padding:14px; border-radius:14px; font-size:13px; line-height:1.35; }}
        .main {{ display:flex; flex-direction:column; gap:16px; }}
        .topbar {{ background:white; border:1px solid #e7ebf5; border-radius:16px; padding:16px 18px; display:grid; grid-template-columns: 1fr 1.5fr 1fr 1fr; gap:15px; box-shadow:0 8px 24px rgba(32,46,90,.06); }}
        .topitem .label {{ color:#65708a; font-size:12px; }} .topitem .value {{ font-weight:750; margin-top:5px; }}
        .avatar-card {{ position:relative; min-height:575px; border-radius:18px; overflow:hidden; background:#dfefff; box-shadow:0 12px 35px rgba(22,29,72,.12); }}
        .avatar-bg {{ position:absolute; inset:0; background-image:url('{avatar_uri}'); background-size:cover; background-position:center top; transform:scale(1.01); transition:transform .4s ease; }}
        .avatar-card.speaking .avatar-bg {{ animation: headMove 1.3s ease-in-out infinite; }}
        @keyframes headMove {{ 0%,100%{{ transform:scale(1.015) translateY(0); }} 50%{{ transform:scale(1.025) translateY(-3px); }} }}
        .status {{ position:absolute; top:18px; left:18px; background:rgba(0,0,0,.72); color:white; padding:9px 14px; border-radius:20px; font-weight:800; font-size:14px; }}
        .dot {{ display:inline-block; width:10px; height:10px; background:#25d366; border-radius:999px; margin-right:7px; box-shadow:0 0 0 6px rgba(37,211,102,.14); }}
        .fullscreen {{ position:absolute; top:16px; right:16px; background:rgba(0,0,0,.55); color:white; border:none; border-radius:12px; padding:10px 12px; font-weight:800; }}
        .caption {{ position:absolute; left:9%; right:9%; bottom:92px; background:rgba(0,0,0,.66); color:white; border-radius:16px; padding:18px 22px; text-align:center; font-size:20px; line-height:1.25; font-weight:800; backdrop-filter:blur(7px); }}
        .caption .wave {{ display:inline-flex; gap:4px; margin-right:12px; vertical-align:middle; }}
        .caption .wave i {{ display:block; width:4px; height:19px; border-radius:10px; background:#7a5cff; animation:bar .8s infinite ease-in-out; }}
        .caption .wave i:nth-child(2){{animation-delay:.1s}} .caption .wave i:nth-child(3){{animation-delay:.2s}} .caption .wave i:nth-child(4){{animation-delay:.3s}}
        @keyframes bar {{ 0%,100%{{ transform:scaleY(.45)}} 50%{{ transform:scaleY(1.3)}} }}
        .mouth {{ position:absolute; left:50.2%; top:47.3%; width:28px; height:9px; margin-left:-14px; border-radius:0 0 18px 18px; background:rgba(80,18,26,.65); opacity:0; transform-origin:center; }}
        .avatar-card.speaking .mouth {{ opacity:.85; animation:mouthTalk .18s infinite alternate; }}
        @keyframes mouthTalk {{ from{{ transform:scaleY(.45)}} to{{ transform:scaleY(1.7)}} }}
        .controls {{ position:absolute; bottom:18px; left:22px; right:22px; display:flex; gap:12px; }}
        .btn {{ border:1px solid #dfe4f3; background:white; color:#12234d; border-radius:13px; padding:14px 18px; font-weight:800; cursor:pointer; flex:1; }}
        .btn.primary {{ background:linear-gradient(90deg,#5d35f5,#7b4dff); color:white; border:none; }}
        .btn.danger {{ color:#e51d1d; border-color:#ffb8b8; }}
        .chat {{ background:white; border-radius:18px; border:1px solid #e7ebf5; padding:22px; box-shadow:0 12px 35px rgba(22,29,72,.08); min-height:670px; }}
        .chatHead {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:22px; }}
        .chatHead strong {{ color:#4e35ff; font-size:18px; }} .chatHead span {{ color:#69758e; font-weight:700; }}
        .msgrow {{ display:flex; align-items:flex-start; gap:12px; margin:18px 0; }}
        .miniavatar {{ width:52px; height:52px; border-radius:999px; background-image:url('{avatar_uri}'); background-size:cover; background-position:center top; box-shadow:0 4px 16px rgba(0,0,0,.12); flex:0 0 auto; }}
        .bubble {{ max-width:78%; padding:18px 20px; border-radius:18px; line-height:1.35; font-size:17px; background:#f0ecff; }}
        .bubble.user {{ margin-left:auto; background:#e6f1ff; }}
        .time {{ display:block; text-align:right; color:#6e7890; font-size:12px; margin-top:10px; }}
        .typing {{ display:inline-flex; gap:6px; background:#f3f0ff; padding:13px 18px; border-radius:12px; color:#68748b; font-weight:700; margin-top:14px; }}
        .typing i {{ width:8px; height:8px; background:#6c4cff; border-radius:999px; animation:dotty .9s infinite ease-in-out; }}
        .typing i:nth-child(2){{animation-delay:.13s}} .typing i:nth-child(3){{animation-delay:.26s}}
        @keyframes dotty {{ 0%,80%,100%{{ transform:translateY(0); opacity:.45; }} 40%{{ transform:translateY(-5px); opacity:1; }} }}
        .recorder {{ margin-top:22px; border-top:1px solid #edf0f7; padding-top:18px; display:flex; align-items:center; gap:16px; }}
        .mic {{ width:72px; height:72px; border-radius:999px; border:none; background:linear-gradient(135deg,#5b35f5,#7d61ff); color:white; font-size:34px; cursor:pointer; box-shadow:0 8px 24px rgba(91,53,245,.28); }}
        .listen {{ font-weight:850; color:#5b35f5; }}
        .small {{ color:#69758e; font-size:13px; line-height:1.35; }}
      </style>
    </head>
    <body>
      <div class="wrap">
        <aside class="sidebar">
          <div class="brand"><div class="logo">A</div><div><strong>AI-RRHH</strong><span>Albano Cozzuol</span></div></div>
          <div class="nav">
            <div>⌂ Inicio</div><div>☁ Mis entrevistas</div><div class="active">☞ Entrevista virtual</div><div>⚙ Filtros iniciales</div><div>▤ Mi CV</div><div>✓ Resultados</div><div>♙ Clasificación de candidatos</div><div>◴ Panel de control</div><div>◷ Historial</div>
          </div>
          <div class="safe"><b>🛡 Entorno seguro</b><br><br>Tus datos están protegidos y no se usan para entrenar IA.</div>
        </aside>
        <main class="main">
          <div class="topbar">
            <div class="topitem"><div class="label">Candidato</div><div class="value">{safe_candidate}</div></div>
            <div class="topitem"><div class="label">Puesto</div><div class="value">{safe_role}</div></div>
            <div class="topitem"><div class="label">Duración</div><div class="value">05:32 min</div></div>
            <div class="topitem"><div class="label">Progreso</div><div class="value">{safe_progress}</div></div>
          </div>
          <section id="avatarCard" class="avatar-card">
            <div class="avatar-bg"></div><div class="mouth"></div>
            <div class="status"><span class="dot"></span>Alba • En línea</div><button class="fullscreen">⛶</button>
            <div class="caption"><span class="wave"><i></i><i></i><i></i><i></i></span><span id="captionText">{safe_question}</span></div>
            <div class="controls">
              <button class="btn" onclick="speakAlba()">↻ Repetir última respuesta</button>
              <button class="btn danger" onclick="stopAlba()">■ Interrumpir</button>
              <button class="btn primary" onclick="speakAlba()">▶ Alba habla</button>
            </div>
          </section>
        </main>
        <aside class="chat">
          <div class="chatHead"><strong>Conversación</strong><span>Pregunta {safe_progress}</span></div>
          <div class="msgrow"><div class="miniavatar"></div><div class="bubble">{safe_question}<span class="time">10:21 🔊</span></div></div>
          <div class="msgrow"><div class="bubble user">Escribí tu respuesta en el campo de Streamlit debajo de esta pantalla para que quede registrada.<span class="time">Ahora ✓✓</span></div></div>
          <div class="typing"><i></i><i></i><i></i>&nbsp; Alba está lista para escuchar...</div>
          <div class="recorder"><button class="mic" onclick="startVoice()">🎙</button><div><div class="listen" id="listenState">Grabar audio</div><div class="small">El micrófono del navegador puede transcribir si Chrome lo permite. La respuesta final cargala en Streamlit.</div></div></div>
        </aside>
      </div>
      <script>
        const text = `{safe_question}`;
        const avatarCard = document.getElementById('avatarCard');
        const listenState = document.getElementById('listenState');
        function pickVoice() {{
          const voices = window.speechSynthesis ? speechSynthesis.getVoices() : [];
          const preferred = voices.find(v => /es[-_](AR|ES|MX|US)/i.test(v.lang) && /female|mujer|paulina|monica|helena|sabina|lucia|elvira|laura|google/i.test(v.name));
          return preferred || voices.find(v => /^es/i.test(v.lang)) || voices[0];
        }}
        function speakAlba() {{
          if (!('speechSynthesis' in window)) {{ alert('Tu navegador no soporta voz automática. Probá con Chrome o Edge.'); return; }}
          speechSynthesis.cancel();
          const u = new SpeechSynthesisUtterance(text);
          u.lang = 'es-AR';
          u.rate = 0.92;
          u.pitch = 1.03;
          u.volume = 1;
          const voice = pickVoice(); if (voice) u.voice = voice;
          u.onstart = () => avatarCard.classList.add('speaking');
          u.onend = () => avatarCard.classList.remove('speaking');
          u.onerror = () => avatarCard.classList.remove('speaking');
          speechSynthesis.speak(u);
        }}
        function stopAlba() {{ if ('speechSynthesis' in window) speechSynthesis.cancel(); avatarCard.classList.remove('speaking'); }}
        if ('speechSynthesis' in window) {{ speechSynthesis.onvoiceschanged = () => pickVoice(); setTimeout(speakAlba, 650); }}
        function startVoice() {{
          const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
          if (!SR) {{ listenState.innerText = 'Tu navegador no permite transcripción automática'; return; }}
          const rec = new SR(); rec.lang = 'es-AR'; rec.continuous = false; rec.interimResults = false;
          listenState.innerText = 'Escuchando...';
          rec.onresult = (e) => {{ listenState.innerText = 'Transcripción: ' + e.results[0][0].transcript; }};
          rec.onerror = () => {{ listenState.innerText = 'No se pudo escuchar. Revisá permisos del micrófono.'; }};
          rec.onend = () => {{ if (listenState.innerText === 'Escuchando...') listenState.innerText = 'Grabación finalizada'; }};
          rec.start();
        }}
      </script>
    </body>
    </html>
    """
    components.html(component_html, height=790, scrolling=True)


st.set_page_config(
    page_title="AI-RRHH Autopartista",
    page_icon="🏭",
    layout="wide",
)

st.markdown(
    """
    <style>
    .main {background-color: #fafafa;}
    .block-container {padding-top: 1.2rem;}
    .small-muted {font-size: 0.9rem; color: #666;}
    .risk-box {
        border-left: 5px solid #d9534f;
        background: #fff7f7;
        padding: 0.8rem;
        border-radius: 0.4rem;
    }
    .ok-box {
        border-left: 5px solid #198754;
        background: #f5fff8;
        padding: 0.8rem;
        border-radius: 0.4rem;
    }
    .review-box {
        border-left: 5px solid #f0ad4e;
        background: #fffaf0;
        padding: 0.8rem;
        border-radius: 0.4rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title(APP_TITLE)
st.caption("Preselección estructurada, explicable y auditable. La decisión final debe permanecer en RR.HH. / jefatura de planta.")

with st.sidebar:
    st.header("Configuración")
    role_name = st.selectbox("Puesto a evaluar", list(ROLE_PROFILES.keys()))
    use_ai = st.toggle("Usar IA con OpenAI si hay API key", value=True)
    model_name = st.text_input("Modelo OpenAI", value="gpt-4.1-mini")
    strict_binary = st.toggle("Forzar salida binaria aprobar/rechazar", value=False)
    st.divider()
    st.subheader("Umbrales sugeridos")
    st.write("Aprobar: ≥70 sin alertas críticas")
    st.write("Rechazar: <55 o alerta crítica")
    st.write("Intermedio: revisión humana")
    st.divider()
    st.info("Evitar cargar datos sensibles: edad, salud, embarazo, religión, sindicato, política, estado civil, familia o domicilio exacto.")

profile = ROLE_PROFILES[role_name]

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "1. Puesto y candidato",
    "2. Entrevista virtual",
    "3. Evaluación IA",
    "4. Decisión humana",
    "5. Historial, ranking y dashboard",
])

with tab1:
    st.subheader("Perfil del puesto")
    st.write(profile["descripcion"])

    col_a, col_b = st.columns([1, 1])
    with col_a:
        st.markdown("**Requisitos excluyentes del puesto**")
        for item in profile["must_have"]:
            st.write(f"- {item}")

    with col_b:
        st.markdown("**Competencias ponderadas**")
        comp_df = pd.DataFrame(
            [{"Competencia": k, "Peso": f"{int(v * 100)}%"} for k, v in profile["competencies"].items()]
        )
        st.dataframe(comp_df, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Datos mínimos del candidato")
    st.caption("Usar un código interno o nombre. No es necesario cargar DNI, edad, domicilio exacto ni datos familiares.")

    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        candidate_name = st.text_input("Nombre o código del candidato", value="")
    with col2:
        interviewer = st.text_input("Entrevistador/a", value="")
    with col3:
        source = st.selectbox("Fuente", ["Postulación espontánea", "Referido", "Agencia", "Portal de empleo", "Otro"])

    candidate_code = stable_candidate_code(candidate_name)
    st.write(f"**Código auditable sugerido:** `{candidate_code}`")

    cv_text = st.text_area(
        "CV o antecedentes laborales declarados",
        height=180,
        placeholder="Pegar experiencia laboral relevante, formación técnica, disponibilidad y observaciones objetivas.",
    )

    if cv_text.strip():
        st.markdown("### Lectura rápida del CV")
        cv_signals_df = pd.DataFrame([
            {"Señal detectada": k.replace("_", " ").capitalize(), "Resultado": "Sí" if v else "No"}
            for k, v in simple_cv_parser(cv_text).items()
        ])
        st.dataframe(cv_signals_df, use_container_width=True, hide_index=True)

    consent = st.checkbox(
        "Confirmo que el candidato fue informado de que se usará una herramienta de asistencia para preselección y que la decisión final será humana.",
        value=False,
    )

with tab2:
    st.subheader("Entrevista virtual con avatar dinámico")
    st.caption("Alba aparece en pantalla, habla la pregunta con voz del navegador y se anima mientras dialoga. Abajo queda el registro formal de respuestas para evaluar.")

    if "alba_question_idx" not in st.session_state:
        st.session_state["alba_question_idx"] = 0

    questions = profile["questions"]
    col_prev, col_next = st.columns([1, 1])
    with col_prev:
        if st.button("⬅ Pregunta anterior", use_container_width=True):
            st.session_state["alba_question_idx"] = max(0, st.session_state["alba_question_idx"] - 1)
    with col_next:
        if st.button("Siguiente pregunta ➡", use_container_width=True):
            st.session_state["alba_question_idx"] = min(len(questions) - 1, st.session_state["alba_question_idx"] + 1)

    q_idx = st.session_state["alba_question_idx"]
    current_avatar_question = questions[q_idx] if questions else "Hola, soy Alba. Vamos a comenzar la entrevista inicial."
    render_alba_dynamic_avatar(
        current_avatar_question,
        candidate_name or "Florencia Gómez",
        role_name,
        f"{q_idx + 1}/{len(questions)}",
    )

    st.info("Importante: la imagen se anima y la voz es la voz humana disponible en el navegador. Para video real con labios sincronizados tipo HeyGen/D-ID o voz premium ElevenLabs, hace falta conectar una API externa.")

    st.markdown("### Filtro excluyente inicial")
    knockout_answers = {}
    for rule_key, rule_question in KNOCKOUT_RULES.get(role_name, []):
        knockout_answers[rule_question] = st.selectbox(
            rule_question,
            ["Sí", "No", "No declarado", "No estoy seguro/a"],
            key=f"knockout_{role_name}_{rule_key}",
        )
    ko = knockout_summary(knockout_answers)
    if ko["count"] >= 2:
        st.error(ko["status"])
    elif ko["count"] == 1:
        st.warning(ko["status"])
    else:
        st.success(ko["status"])

    st.divider()
    questions = profile["questions"]
    answers = {}
    for i, q in enumerate(questions, start=1):
        st.markdown(f"**{i}. {q}**")
        answers[f"q_{i}"] = st.text_area(f"Respuesta {i}", key=f"answer_{role_name}_{i}", height=90)

    free_notes = st.text_area(
        "Observaciones objetivas del entrevistador",
        height=120,
        placeholder="Ejemplo: respondió con ejemplos concretos, reconoce uso de EPP, no pudo precisar experiencia en medición, etc.",
    )

    st.divider()
    base_answers_text = make_answers_text(questions, answers)
    followup_questions = build_followup_questions(role_name, cv_text, base_answers_text)
    st.markdown("### Repreguntas adaptativas sugeridas")
    st.caption("Se generan según el CV y las respuestas. Sirven para profundizar antes de evaluar.")
    followup_answers = {}
    for i, q in enumerate(followup_questions, start=1):
        st.markdown(f"**Repregunta {i}. {q}**")
        followup_answers[f"followup_{i}"] = st.text_area(f"Respuesta repregunta {i}", key=f"followup_{role_name}_{i}", height=80)

with tab3:
    st.subheader("Evaluación y recomendación")
    st.caption("La recomendación se basa en evidencias laborales relacionadas con el puesto. No debe reemplazar la decisión humana.")

    if st.button("Evaluar candidato", type="primary", use_container_width=True):
        if not consent:
            st.error("Antes de evaluar, confirmá el consentimiento/información al candidato en la pestaña 1.")
            st.stop()

        candidate_text = (
            make_answers_text(questions, answers)
            + "\n\nFiltro excluyente inicial:\n"
            + json.dumps(knockout_answers, ensure_ascii=False)
            + "\n\nRepreguntas adaptativas:\n"
            + make_answers_text(followup_questions, followup_answers)
            + "\n\nObservaciones entrevistador:\n"
            + free_notes
        )

        result = None
        error = None

        if use_ai:
            with st.spinner("Evaluando con IA..."):
                result, error = ai_evaluate(
                    role_name=role_name,
                    candidate_text=candidate_text,
                    cv_text=cv_text,
                    strict_binary=strict_binary,
                    model=model_name,
                )

        if result is None:
            if error:
                st.warning(f"No se pudo usar IA externa. Se usará motor local de reglas. Detalle: {error}")
            result = local_evaluate(role_name, candidate_text, cv_text, strict_binary=strict_binary)

        st.session_state["last_result"] = result
        st.session_state["last_candidate_text"] = candidate_text
        st.session_state["last_cv_text"] = cv_text
        st.session_state["last_candidate_code"] = candidate_code
        st.session_state["last_role_name"] = role_name
        st.session_state["last_interviewer"] = interviewer
        st.session_state["last_source"] = source

    result = st.session_state.get("last_result")

    if result:
        rec = result.get("recommendation", "Sin recomendación")
        score = result.get("score", 0)
        confidence = result.get("confidence", "No informado")

        col1, col2, col3 = st.columns(3)
        with col1:
            render_metric_card("Recomendación", rec)
        with col2:
            render_metric_card("Puntaje global", f"{score}/100")
        with col3:
            render_metric_card("Confianza", confidence)

        st.info("Decisión humana: " + human_decision_required_text(rec))

        if "APROBAR" in rec:
            st.markdown(f"<div class='ok-box'><b>Resultado:</b> {rec}</div>", unsafe_allow_html=True)
        elif "RECHAZAR" in rec:
            st.markdown(f"<div class='risk-box'><b>Resultado:</b> {rec}</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='review-box'><b>Resultado:</b> {rec}</div>", unsafe_allow_html=True)

        st.markdown("### Fundamento")
        st.write(result.get("rationale", ""))

        col_left, col_right = st.columns(2)
        with col_left:
            st.markdown("### Fortalezas")
            strengths = result.get("strengths", [])
            if strengths:
                for s in strengths:
                    st.write(f"- {s}")
            else:
                st.write("No se identificaron fortalezas relevantes suficientes.")

        with col_right:
            st.markdown("### Riesgos / brechas")
            risks = result.get("risks", [])
            if risks:
                for r in risks:
                    st.write(f"- {r}")
            else:
                st.write("No se identificaron riesgos relevantes.")

        st.markdown("### Puntaje por competencia")
        comp_result_df = result_to_dataframe(result)
        if not comp_result_df.empty:
            st.dataframe(comp_result_df, use_container_width=True, hide_index=True)
            st.bar_chart(comp_result_df.set_index("Competencia"))

        sensitive = result.get("sensitive_data_detected", [])
        if sensitive:
            st.warning(
                "Se detectaron posibles datos sensibles/no pertinentes. No deben utilizarse para decidir: "
                + ", ".join(sensitive)
            )

        st.markdown("### Registro auditable")
        audit_row = {
            "fecha_hora": now_str(),
            "codigo_candidato": st.session_state.get("last_candidate_code", ""),
            "puesto": st.session_state.get("last_role_name", role_name),
            "entrevistador": st.session_state.get("last_interviewer", ""),
            "fuente": st.session_state.get("last_source", ""),
            "recomendacion": rec,
            "puntaje": score,
            "confianza": confidence,
            "fundamento": result.get("rationale", ""),
            "fortalezas": " | ".join(result.get("strengths", [])),
            "riesgos": " | ".join(result.get("risks", [])),
            "alertas": " | ".join(result.get("red_flags", [])),
            "datos_sensibles_detectados": " | ".join(result.get("sensitive_data_detected", [])),
            "filtro_excluyente": json.dumps(knockout_answers, ensure_ascii=False),
            "alerta_filtro_excluyente": ko.get("status", ""),
            "modelo": result.get("model_used", ""),
            "cv_texto": st.session_state.get("last_cv_text", ""),
            "entrevista_texto": st.session_state.get("last_candidate_text", ""),
            "json_resultado": json.dumps(result, ensure_ascii=False),
        }

        st.json(audit_row, expanded=False)

        col_save, col_xlsx, col_json = st.columns(3)
        with col_save:
            if st.button("Guardar en historial", use_container_width=True):
                df_all = append_history(audit_row)
                st.success(f"Evaluación guardada. Total registros: {len(df_all)}")

        current_df = pd.DataFrame([audit_row])
        with col_xlsx:
            st.download_button(
                "Descargar evaluación Excel",
                data=history_to_excel_bytes(current_df),
                file_name=f"evaluacion_{audit_row['codigo_candidato']}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

        with col_json:
            st.download_button(
                "Descargar JSON",
                data=json.dumps(audit_row, ensure_ascii=False, indent=2).encode("utf-8"),
                file_name=f"evaluacion_{audit_row['codigo_candidato']}.json",
                mime="application/json",
                use_container_width=True,
            )

with tab4:
    st.subheader("Decisión humana final")
    st.caption("La recomendación IA no reemplaza la decisión de RR.HH. / jefatura. Registrá siempre la decisión final.")

    result = st.session_state.get("last_result")
    if not result:
        st.info("Primero evaluá un candidato en la pestaña 3.")
    else:
        st.write(f"**Recomendación IA:** {result.get('recommendation', '')}")
        human_final_decision = st.selectbox(
            "Decisión final humana",
            ["Pendiente", "Avanza a entrevista humana", "Avanza a prueba técnica", "Mantener en base", "No avanza"],
        )
        human_reason = st.text_area(
            "Motivo laboral de la decisión humana",
            placeholder="Ejemplo: cumple disponibilidad y seguridad, pero requiere validar experiencia técnica con el líder de planta.",
            height=120,
        )
        decision_owner = st.text_input("Responsable de decisión", value=interviewer)

        if st.button("Guardar decisión humana", type="primary", use_container_width=True):
            decision_row = {
                "fecha_hora": now_str(),
                "codigo_candidato": st.session_state.get("last_candidate_code", ""),
                "puesto": st.session_state.get("last_role_name", role_name),
                "recomendacion_ia": result.get("recommendation", ""),
                "puntaje_ia": result.get("score", ""),
                "decision_humana": human_final_decision,
                "motivo_decision_humana": human_reason,
                "responsable_decision": decision_owner,
            }
            decision_file = DATA_DIR / "decisiones_humanas.csv"
            df_decision = pd.DataFrame([decision_row])
            if decision_file.exists():
                old_decision = pd.read_csv(decision_file)
                df_decision = pd.concat([old_decision, df_decision], ignore_index=True)
            df_decision.to_csv(decision_file, index=False)
            st.success("Decisión humana guardada correctamente.")
            st.json(decision_row, expanded=False)

with tab5:
    st.subheader("Historial, ranking y dashboard")
    hist = read_history()

    if hist.empty:
        st.info("Todavía no hay evaluaciones guardadas.")
    else:
        st.markdown("### Ranking por búsqueda / puesto")
        ranking_cols = [c for c in ["codigo_candidato", "puesto", "fuente", "recomendacion", "puntaje", "confianza"] if c in hist.columns]
        hist_rank = hist.sort_values("puntaje", ascending=False) if "puntaje" in hist.columns else hist
        st.dataframe(hist_rank[ranking_cols], use_container_width=True, hide_index=True)

        st.markdown("### Dashboard básico")
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Evaluaciones", len(hist))
        if "puntaje" in hist.columns:
            col_m2.metric("Score promedio", round(pd.to_numeric(hist["puntaje"], errors="coerce").mean(), 1))
        if "recomendacion" in hist.columns:
            col_m3.metric("Revisión humana", int(hist["recomendacion"].astype(str).str.contains("REVISIÓN", case=False, na=False).sum()))
            rec_counts = hist["recomendacion"].value_counts().reset_index()
            rec_counts.columns = ["Recomendación", "Cantidad"]
            st.bar_chart(rec_counts.set_index("Recomendación"))

        with st.expander("Ver historial completo"):
            st.dataframe(hist, use_container_width=True)

        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                "Descargar historial CSV",
                data=hist.to_csv(index=False).encode("utf-8"),
                file_name="historial_evaluaciones_rrhh.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with col2:
            st.download_button(
                "Descargar historial Excel",
                data=history_to_excel_bytes(hist),
                file_name="historial_evaluaciones_rrhh.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

    st.divider()
    st.markdown("### Política interna sugerida")
    st.write(
        """
        - La app asiste la primera selección, pero no reemplaza a RR.HH.
        - Usar preguntas uniformes por puesto.
        - No cargar ni usar datos sensibles o no relacionados con el trabajo.
        - Toda decisión de rechazo debe tener fundamento laboral verificable.
        - Los casos intermedios o con duda deben pasar a revisión humana.
        - Revisar periódicamente los resultados para detectar sesgos o errores.
        """
    )
