
import os
import re
import io
import json
import uuid
import hashlib
import base64
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


def _asset_base64(path: Path) -> str:
    try:
        return base64.b64encode(path.read_bytes()).decode("utf-8")
    except Exception:
        return ""


def render_alba_avatar(question_list, role_name: str, candidate_name: str = "Candidato"):
    # Renderiza la pantalla visual del avatar Alba + voz del navegador.
    safe_questions = [q for q in question_list if q]
    if not safe_questions:
        safe_questions = ["Hola, soy Alba, tu entrevistadora virtual. Vamos a comenzar la entrevista inicial."]

    avatar_path = Path("assets") / "alba_avatar_scene.png"
    if not avatar_path.exists():
        avatar_path = Path(__file__).parent / "assets" / "alba_avatar_scene.png"
    avatar_b64 = _asset_base64(avatar_path)

    payload = json.dumps(safe_questions, ensure_ascii=False)
    role_payload = json.dumps(role_name, ensure_ascii=False)
    candidate_payload = json.dumps(candidate_name or "Candidato", ensure_ascii=False)

    if avatar_b64:
        avatar_img_css = f"background-image:linear-gradient(180deg,rgba(0,0,0,.03),rgba(0,0,0,.16)),url('data:image/png;base64,{avatar_b64}');"
    else:
        avatar_img_css = "background:linear-gradient(135deg,#dceeff,#ffffff);"

    html = f'''
    <style>
      * {{ box-sizing:border-box; }} body {{ margin:0; }}
      .ai-shell {{ font-family: Inter, Arial, sans-serif; background:#f6f8ff; border:1px solid #e7eaf5; border-radius:24px; overflow:hidden; color:#071735; }}
      .ai-layout {{ display:grid; grid-template-columns: 220px 1fr; min-height:760px; }}
      .ai-sidebar {{ background:linear-gradient(180deg,#06172d,#081c35); color:#fff; padding:22px 16px; position:relative; }}
      .brand {{ display:flex; align-items:center; gap:12px; margin-bottom:34px; }}
      .brand-logo {{ width:44px; height:44px; border-radius:14px; background:linear-gradient(135deg,#25a7ff,#6a39ff); display:flex;align-items:center;justify-content:center;font-weight:900;font-size:28px; }}
      .brand-title {{ font-size:22px; font-weight:800; line-height:1.05; }} .brand-sub {{ font-size:13px; opacity:.9; margin-top:3px; }}
      .nav-item {{ display:flex; align-items:center; gap:12px; padding:12px 10px; border-radius:12px; margin:6px 0; font-size:15px; color:#dfe7ff; }}
      .nav-item.active {{ background:linear-gradient(135deg,#3f4cff,#6d39ff); color:#fff; font-weight:700; box-shadow:0 10px 22px rgba(69,64,255,.35); }}
      .safe-card {{ position:absolute; bottom:16px; left:16px; right:16px; background:rgba(255,255,255,.06); border:1px solid rgba(255,255,255,.1); border-radius:14px; padding:14px; font-size:13px; line-height:1.3; }}
      .main {{ padding:18px 22px 16px; }} .topline {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; }}
      .back {{ color:#4c38f2; font-weight:700; font-size:14px; }} .finish {{ border:1px solid #f25a5a; color:#d71920; background:#fff; border-radius:8px; padding:9px 14px; font-weight:700; }} .exit {{ border:1px solid #d8deee; background:#fff; border-radius:8px; padding:9px 14px; margin-left:8px; color:#344054; }}
      .info-strip {{ background:#fff; border:1px solid #e8ecf7; border-radius:14px; padding:16px 18px; display:grid; grid-template-columns: 1.1fr 1.6fr .8fr .9fr; gap:18px; box-shadow:0 8px 20px rgba(16,24,40,.04); margin-bottom:18px; }}
      .info-label {{ font-size:12px; color:#667085; margin-bottom:5px; }} .info-value {{ font-size:15px; font-weight:800; }} .progress {{ width:100%; height:8px; border-radius:99px; background:#ebe9ff; overflow:hidden; margin-top:7px; }} .progress > div {{ height:100%; background:linear-gradient(90deg,#5645ff,#6b7cff); width:12.5%; }}
      .stage {{ display:grid; grid-template-columns: 1.08fr .95fr; gap:16px; }} .avatar-card {{ min-height:555px; border-radius:18px; overflow:hidden; position:relative; background:#111; box-shadow:0 18px 35px rgba(16,24,40,.12); }} .avatar-photo {{ position:absolute; inset:0; background-size:cover; background-position:center; {avatar_img_css} }}
      .online {{ position:absolute; left:18px; top:18px; background:rgba(7,18,31,.82); color:#fff; border-radius:999px; padding:8px 12px; font-weight:800; font-size:13px; display:flex; gap:7px; align-items:center; }} .dot {{ width:9px; height:9px; border-radius:50%; background:#16d96d; box-shadow:0 0 0 0 rgba(22,217,109,.65); animation:pulse 1.5s infinite; }} .fullscreen {{ position:absolute; right:16px; top:16px; width:36px; height:36px; border-radius:10px; background:rgba(0,0,0,.45); display:flex; align-items:center; justify-content:center; color:#fff; }}
      .subtitle {{ position:absolute; left:10%; right:10%; bottom:84px; background:rgba(0,0,0,.68); color:#fff; border-radius:14px; padding:18px 22px; text-align:center; font-size:18px; line-height:1.34; font-weight:750; backdrop-filter: blur(5px); }}
      .voice-bars {{ display:inline-flex; gap:4px; vertical-align:middle; margin-right:12px; }} .bar {{ display:block; width:4px; height:18px; border-radius:99px; background:#7b61ff; animation:bar .7s infinite ease-in-out; }} .bar:nth-child(2) {{ animation-delay:.12s; }} .bar:nth-child(3) {{ animation-delay:.24s; }} .bar:nth-child(4) {{ animation-delay:.36s; }}
      .controls {{ position:absolute; left:22px; right:22px; bottom:20px; background:rgba(255,255,255,.94); border-radius:14px; padding:10px; display:grid; grid-template-columns:1fr 1.1fr 1fr; gap:10px; }} .ctrl {{ border:0; border-radius:12px; padding:13px 10px; font-weight:750; color:#344054; background:#fff; cursor:pointer; font-size:14px; }} .ctrl.primary {{ color:#fff; background:linear-gradient(135deg,#4f46e5,#743df7); box-shadow:0 8px 18px rgba(80,67,229,.3); }} .ctrl.danger {{ color:#b42318; background:#fff3f3; }}
      .chat-card {{ background:#fff; border:1px solid #e8ecf7; border-radius:18px; min-height:555px; padding:22px; box-shadow:0 18px 35px rgba(16,24,40,.08); }} .chat-head {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:20px; color:#533af5; font-weight:900; }} .bubble-row {{ display:flex; gap:12px; margin:16px 0; align-items:flex-start; }} .bubble-row.user {{ justify-content:flex-end; }} .mini-avatar {{ width:44px; height:44px; border-radius:50%; overflow:hidden; background-size:cover; background-position:center; flex:0 0 44px; border:2px solid #fff; box-shadow:0 4px 12px rgba(16,24,40,.15); {avatar_img_css} }} .bubble {{ max-width:78%; padding:16px 18px; border-radius:16px; font-size:16px; line-height:1.38; background:linear-gradient(135deg,#f6f1ff,#eef2ff); color:#0a1633; }} .bubble.user-b {{ background:#eaf3ff; }} .time {{ text-align:right; color:#667085; margin-top:8px; font-size:12px; }}
      .typing {{ display:flex; gap:6px; align-items:center; width:max-content; background:#f4f2ff; padding:14px 18px; border-radius:14px; color:#667085; font-size:13px; margin-top:18px; }} .typing span {{ width:7px;height:7px;border-radius:50%;background:#6b4cff;display:inline-block;animation:type 1.1s infinite; }} .typing span:nth-child(2){{animation-delay:.15s}} .typing span:nth-child(3){{animation-delay:.3s}}
      .answer {{ margin-top:14px; background:#fff; border:1px solid #e8ecf7; border-radius:16px; padding:14px 16px; display:grid; grid-template-columns:1fr 84px 130px; gap:14px; align-items:center; }} .input-fake {{ border:1px solid #d9dff0; border-radius:10px; padding:14px 16px; color:#98a2b3; }} .mic {{ width:58px; height:58px; border-radius:50%; border:0; color:#fff; font-size:24px; background:linear-gradient(135deg,#6a49ff,#7c3df2); box-shadow:0 12px 22px rgba(91,61,245,.35); }} .send {{ border:0; color:#fff; border-radius:10px; background:linear-gradient(135deg,#6c4cff,#7b49f7); padding:15px 16px; font-weight:800; }}
      .speaking .avatar-card {{ box-shadow:0 0 0 4px rgba(91,61,245,.15), 0 18px 35px rgba(16,24,40,.12); }} .speaking .avatar-photo {{ animation:talking 1.2s infinite ease-in-out; }}
      @keyframes pulse {{ 70% {{ box-shadow:0 0 0 8px rgba(22,217,109,0); }} 100% {{ box-shadow:0 0 0 0 rgba(22,217,109,0); }} }} @keyframes bar {{ 0%,100%{{height:9px}} 50%{{height:22px}} }} @keyframes type {{ 0%,80%,100%{{opacity:.35; transform:translateY(0)}} 40%{{opacity:1; transform:translateY(-4px)}} }} @keyframes talking {{ 0%,100%{{transform:scale(1)}} 50%{{transform:scale(1.012)}} }}
      @media (max-width: 900px) {{ .ai-layout {{ grid-template-columns:1fr; }} .ai-sidebar {{ display:none; }} .stage {{ grid-template-columns:1fr; }} .info-strip {{ grid-template-columns:1fr 1fr; }} }}
    </style>
    <div class="ai-shell" id="albaShell"><div class="ai-layout"><aside class="ai-sidebar"><div class="brand"><div class="brand-logo">A</div><div><div class="brand-title">AI-RRHH</div><div class="brand-sub">Albano Cozzuol</div></div></div><div class="nav-item">⌂ Inicio</div><div class="nav-item">▣ Mis entrevistas</div><div class="nav-item active">☞ Entrevista virtual</div><div class="nav-item">⚙ Filtros iniciales</div><div class="nav-item">▤ Mi CV</div><div class="nav-item">✓ Resultados</div><div class="nav-item">♙ Ranking candidatos</div><div class="nav-item">◴ Dashboard</div><div class="safe-card"><b>🛡 Entorno seguro</b><br/>Tus datos están protegidos y no se usan para entrenar IA.</div></aside><main class="main"><div class="topline"><div class="back">← Volver a mis entrevistas</div><div><button class="finish">Finalizar entrevista</button><button class="exit">Salir</button></div></div><div class="info-strip"><div><div class="info-label">Candidato</div><div class="info-value" id="candName"></div></div><div><div class="info-label">Puesto</div><div class="info-value" id="roleName"></div></div><div><div class="info-label">Tiempo</div><div class="info-value">08:42 min</div></div><div><div class="info-label">Progreso <span id="progText" style="float:right;color:#344054;font-weight:800"></span></div><div class="progress"><div id="progBar"></div></div></div></div><div class="stage"><section class="avatar-card"><div class="avatar-photo"></div><div class="online"><span class="dot"></span> Alba • Online</div><div class="fullscreen">⛶</div><div class="subtitle"><span class="voice-bars"><span class="bar"></span><span class="bar"></span><span class="bar"></span><span class="bar"></span></span><span id="questionText"></span></div><div class="controls"><button class="ctrl" onclick="prevQ()">◀ Anterior</button><button class="ctrl primary" onclick="speakQ()">🔊 Alba habla</button><button class="ctrl danger" onclick="stopSpeak()">Detener</button></div></section><section class="chat-card"><div class="chat-head"><span>Conversación</span><span id="questionCount" style="color:#667085;font-weight:700"></span></div><div class="bubble-row"><div class="mini-avatar"></div><div class="bubble"><span id="chatQ"></span><div class="time">10:21 🔊</div></div></div><div class="bubble-row user"><div class="bubble user-b">Escribí tu respuesta en el campo de Streamlit debajo de esta pantalla para que quede registrada en la evaluación.<div class="time">Ahora ✓✓</div></div></div><div class="bubble-row"><div class="mini-avatar"></div><div class="bubble">Cuando termines, podés avanzar a la siguiente pregunta. Si tu respuesta queda incompleta, Alba puede sugerir una repregunta adaptativa.<div class="time">Ahora 🔊</div></div></div><div class="typing"><span></span><span></span><span></span> Alba está lista para continuar...</div></section></div><div class="answer"><div class="input-fake">Tu respuesta se carga en los campos de abajo para mantener auditoría...</div><button class="mic">🎙</button><button class="send" onclick="nextQ()">Enviar ▶</button></div><div style="text-align:center;color:#667085;font-size:13px;margin-top:12px;">La entrevista es asistida por IA. La decisión final siempre será del equipo de RRHH.</div></main></div></div>
    <script>
      const questions = {payload}; const roleName = {role_payload}; const candidateName = {candidate_payload}; let idx = 0; const shell = document.getElementById('albaShell'); document.getElementById('roleName').innerText = roleName; document.getElementById('candName').innerText = candidateName;
      function render() {{ const text = questions[idx]; document.getElementById('questionText').innerText = text; document.getElementById('chatQ').innerText = text; document.getElementById('questionCount').innerText = 'Pregunta ' + (idx+1) + ' de ' + questions.length; document.getElementById('progText').innerText = (idx+1) + ' / ' + questions.length; document.getElementById('progBar').style.width = (((idx+1)/questions.length)*100) + '%'; }}
      function pickSpanishVoice() {{ const voices = window.speechSynthesis.getVoices(); return voices.find(v => v.lang && v.lang.toLowerCase().startsWith('es-ar')) || voices.find(v => v.lang && v.lang.toLowerCase().startsWith('es')) || voices[0]; }}
      function speakQ() {{ stopSpeak(); if (!('speechSynthesis' in window)) {{ return; }} const intro = idx === 0 ? 'Hola, soy Alba, tu entrevistadora virtual de Recursos Humanos. ' : ''; const u = new SpeechSynthesisUtterance(intro + questions[idx]); u.lang = 'es-AR'; u.rate = 0.95; u.pitch = 1.03; const v = pickSpanishVoice(); if(v) u.voice = v; u.onstart = () => shell.classList.add('speaking'); u.onend = () => shell.classList.remove('speaking'); u.onerror = () => shell.classList.remove('speaking'); window.speechSynthesis.speak(u); }}
      function stopSpeak() {{ if ('speechSynthesis' in window) window.speechSynthesis.cancel(); shell.classList.remove('speaking'); }} function nextQ() {{ stopSpeak(); idx = Math.min(idx + 1, questions.length - 1); render(); }} function prevQ() {{ stopSpeak(); idx = Math.max(idx - 1, 0); render(); }} window.speechSynthesis && (window.speechSynthesis.onvoiceschanged = () => {{}}); render();
    </script>
    '''
    components.html(html, height=790, scrolling=True)

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
    st.subheader("Entrevista virtual estructurada + adaptativa")
    st.caption("Primero validá requisitos excluyentes. Luego usá preguntas base y repreguntas adaptativas.")

    avatar_enabled = st.toggle("Activar avatar entrevistador Alba", value=True)
    if avatar_enabled:
        st.markdown("### Avatar entrevistador")
        avatar_intro_questions = [
            "Hola, soy Alba, tu entrevistadora virtual de Recursos Humanos. Vamos a realizar una entrevista inicial para conocer tu experiencia laboral y disponibilidad.",
            "Antes de comenzar, te recuerdo que esta herramienta asiste la preselección, pero la decisión final siempre será revisada por una persona de Recursos Humanos.",
        ] + profile["questions"]
        render_alba_avatar(avatar_intro_questions, role_name, candidate_name or "Candidato/a")
        st.info("Para usarlo: hacé clic en **Alba pregunta**, escuchá la pregunta y cargá la respuesta en los campos de abajo. El avatar funciona con la voz del navegador.")

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
