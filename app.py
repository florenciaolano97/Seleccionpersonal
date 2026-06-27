
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

EMBEDDED_ALBA_AVATAR_JPG = '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'


def _find_avatar_data_uri() -> str:
    candidates = []
    try:
        base = Path(__file__).resolve().parent
        candidates.extend([
            base / "assets" / "alba_avatar_scene.png",
            base / "assets" / "alba_avatar_scene.jpg",
            Path.cwd() / "assets" / "alba_avatar_scene.png",
            Path.cwd() / "assets" / "alba_avatar_scene.jpg",
            Path("/mnt/data/assets/alba_avatar_scene.png"),
            Path("/mnt/data/assets/alba_avatar_scene.jpg"),
        ])
    except Exception:
        candidates.extend([Path("assets/alba_avatar_scene.png"), Path("assets/alba_avatar_scene.jpg")])
    for path in candidates:
        if path.exists():
            ext = path.suffix.lower().replace(".", "")
            mime = "jpeg" if ext in ["jpg", "jpeg"] else "png"
            data = _asset_base64(path)
            if data:
                return f"data:image/{mime};base64,{data}"
    return "data:image/jpeg;base64," + EMBEDDED_ALBA_AVATAR_JPG


def render_alba_avatar(question_list, role_name: str, candidate_name: str = "Candidato"):
    safe_questions = [q for q in question_list if q]
    if not safe_questions:
        safe_questions = ["Hola, soy Alba, tu entrevistadora virtual. Vamos a comenzar la entrevista inicial."]

    avatar_src = _find_avatar_data_uri()
    payload = json.dumps(safe_questions, ensure_ascii=False)
    role_payload = json.dumps(role_name, ensure_ascii=False)
    candidate_payload = json.dumps(candidate_name or "Candidato", ensure_ascii=False)

    html = f'''
    <style>
      * {{ box-sizing:border-box; }} body {{ margin:0; }}
      .ai-shell {{ font-family: Inter, Arial, sans-serif; background:#f6f8ff; border:1px solid #e7eaf5; border-radius:24px; overflow:hidden; color:#071735; }}
      .ai-layout {{ display:grid; grid-template-columns: 250px 1fr; min-height:820px; }}
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
      .stage {{ display:grid; grid-template-columns: 1.05fr .95fr; gap:16px; }}
      .avatar-card {{ min-height:580px; border-radius:18px; overflow:hidden; position:relative; background:#111; box-shadow:0 18px 35px rgba(16,24,40,.12); }}
      .avatar-photo {{ position:absolute; inset:0; width:100%; height:100%; object-fit:cover; object-position:center; display:block; }}
      .avatar-overlay {{ position:absolute; inset:0; background:linear-gradient(180deg,rgba(0,0,0,.03),rgba(0,0,0,.16)); pointer-events:none; }}
      .online {{ position:absolute; left:18px; top:18px; background:rgba(7,18,31,.82); color:#fff; border-radius:999px; padding:8px 12px; font-weight:800; font-size:13px; display:flex; gap:7px; align-items:center; }} .dot {{ width:9px; height:9px; border-radius:50%; background:#16d96d; box-shadow:0 0 0 0 rgba(22,217,109,.65); animation:pulse 1.5s infinite; }} .fullscreen {{ position:absolute; right:16px; top:16px; width:36px; height:36px; border-radius:10px; background:rgba(0,0,0,.45); display:flex; align-items:center; justify-content:center; color:#fff; }}
      .subtitle {{ position:absolute; left:10%; right:10%; bottom:84px; background:rgba(0,0,0,.68); color:#fff; border-radius:14px; padding:18px 22px; text-align:center; font-size:18px; line-height:1.34; font-weight:750; backdrop-filter: blur(5px); }}
      .voice-bars {{ display:inline-flex; gap:4px; vertical-align:middle; margin-right:12px; }} .bar {{ display:block; width:4px; height:18px; border-radius:99px; background:#7b61ff; animation:bar .7s infinite ease-in-out; }} .bar:nth-child(2) {{ animation-delay:.12s; }} .bar:nth-child(3) {{ animation-delay:.24s; }} .bar:nth-child(4) {{ animation-delay:.36s; }}
      .controls {{ position:absolute; left:22px; right:22px; bottom:20px; background:rgba(255,255,255,.94); border-radius:14px; padding:10px; display:grid; grid-template-columns:1fr 1.1fr 1fr; gap:10px; }} .ctrl {{ border:0; border-radius:12px; padding:13px 10px; font-weight:750; color:#344054; background:#fff; cursor:pointer; font-size:14px; }} .ctrl.primary {{ color:#fff; background:linear-gradient(135deg,#4f46e5,#743df7); box-shadow:0 8px 18px rgba(80,67,229,.3); }} .ctrl.danger {{ color:#b42318; background:#fff3f3; }}
      .chat-card {{ background:#fff; border:1px solid #e8ecf7; border-radius:18px; min-height:580px; padding:22px; box-shadow:0 18px 35px rgba(16,24,40,.08); }} .chat-head {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:20px; color:#533af5; font-weight:900; }} .bubble-row {{ display:flex; gap:12px; margin:16px 0; align-items:flex-start; }} .bubble-row.user {{ justify-content:flex-end; }} .mini-avatar {{ width:44px; height:44px; border-radius:50%; overflow:hidden; flex:0 0 44px; border:2px solid #fff; box-shadow:0 4px 12px rgba(16,24,40,.15); object-fit:cover; object-position:center; }} .bubble {{ max-width:78%; padding:16px 18px; border-radius:16px; font-size:16px; line-height:1.38; background:linear-gradient(135deg,#f6f1ff,#eef2ff); color:#0a1633; }} .bubble.user-b {{ background:#eaf3ff; }} .time {{ text-align:right; color:#667085; margin-top:8px; font-size:12px; }}
      .typing {{ display:flex; gap:6px; align-items:center; width:max-content; background:#f4f2ff; padding:14px 18px; border-radius:14px; color:#667085; font-size:13px; margin-top:18px; }} .typing span {{ width:7px;height:7px;border-radius:50%;background:#6b4cff;display:inline-block;animation:type 1.1s infinite; }} .typing span:nth-child(2){{animation-delay:.15s}} .typing span:nth-child(3){{animation-delay:.3s}}
      .answer {{ margin-top:14px; background:#fff; border:1px solid #e8ecf7; border-radius:16px; padding:14px 16px; display:grid; grid-template-columns:1fr 84px 130px; gap:14px; align-items:center; }} .input-fake {{ border:1px solid #d9dff0; border-radius:10px; padding:14px 16px; color:#98a2b3; }} .mic {{ width:58px; height:58px; border-radius:50%; border:0; color:#fff; font-size:24px; background:linear-gradient(135deg,#6a49ff,#7c3df2); box-shadow:0 12px 22px rgba(91,61,245,.35); }} .send {{ border:0; color:#fff; border-radius:10px; background:linear-gradient(135deg,#6c4cff,#7b49f7); padding:15px 16px; font-weight:800; }}
      .speaking .avatar-card {{ box-shadow:0 0 0 4px rgba(91,61,245,.15), 0 18px 35px rgba(16,24,40,.12); }} .speaking .avatar-photo {{ animation:talking 1.2s infinite ease-in-out; transform-origin:center; }}
      @keyframes pulse {{ 70% {{ box-shadow:0 0 0 8px rgba(22,217,109,0); }} 100% {{ box-shadow:0 0 0 0 rgba(22,217,109,0); }} }} @keyframes bar {{ 0%,100%{{height:9px}} 50%{{height:22px}} }} @keyframes type {{ 0%,80%,100%{{opacity:.35; transform:translateY(0)}} 40%{{opacity:1; transform:translateY(-4px)}} }} @keyframes talking {{ 0%,100%{{transform:scale(1)}} 50%{{transform:scale(1.018)}} }}
      @media (max-width: 900px) {{ .ai-layout {{ grid-template-columns:1fr; }} .ai-sidebar {{ display:none; }} .stage {{ grid-template-columns:1fr; }} .info-strip {{ grid-template-columns:1fr 1fr; }} }}
    </style>
    <div class="ai-shell" id="albaShell"><div class="ai-layout"><aside class="ai-sidebar"><div class="brand"><div class="brand-logo">A</div><div><div class="brand-title">AI-RRHH</div><div class="brand-sub">Albano Cozzuol</div></div></div><div class="nav-item">⌂ Inicio</div><div class="nav-item">▣ Mis entrevistas</div><div class="nav-item active">☞ Entrevista virtual</div><div class="nav-item">⚙ Filtros iniciales</div><div class="nav-item">▤ Mi CV</div><div class="nav-item">✓ Resultados</div><div class="nav-item">♙ Ranking candidatos</div><div class="nav-item">◴ Dashboard</div><div class="safe-card"><b>🛡 Entorno seguro</b><br/>Tus datos están protegidos y no se usan para entrenar IA.</div></aside><main class="main"><div class="topline"><div class="back">← Volver a mis entrevistas</div><div><button class="finish">Finalizar entrevista</button><button class="exit">Salir</button></div></div><div class="info-strip"><div><div class="info-label">Candidato</div><div class="info-value" id="candName"></div></div><div><div class="info-label">Puesto</div><div class="info-value" id="roleName"></div></div><div><div class="info-label">Tiempo</div><div class="info-value">08:42 min</div></div><div><div class="info-label">Progreso <span id="progText" style="float:right;color:#344054;font-weight:800"></span></div><div class="progress"><div id="progBar"></div></div></div></div><div class="stage"><section class="avatar-card"><img class="avatar-photo" src="{avatar_src}" alt="Alba, avatar entrevistadora virtual"/><div class="avatar-overlay"></div><div class="online"><span class="dot"></span> Alba • Online</div><div class="fullscreen">⛶</div><div class="subtitle"><span class="voice-bars"><span class="bar"></span><span class="bar"></span><span class="bar"></span><span class="bar"></span></span><span id="questionText"></span></div><div class="controls"><button class="ctrl" onclick="prevQ()">◀ Anterior</button><button class="ctrl primary" onclick="speakQ()">🔊 Alba habla</button><button class="ctrl danger" onclick="stopSpeak()">Detener</button></div></section><section class="chat-card"><div class="chat-head"><span>Conversación</span><span id="questionCount" style="color:#667085;font-weight:700"></span></div><div class="bubble-row"><img class="mini-avatar" src="{avatar_src}" alt="Alba"/><div class="bubble"><span id="chatQ"></span><div class="time">10:21 🔊</div></div></div><div class="bubble-row user"><div class="bubble user-b">Escribí tu respuesta en el campo de Streamlit debajo de esta pantalla para que quede registrada en la evaluación.<div class="time">Ahora ✓✓</div></div></div><div class="bubble-row"><img class="mini-avatar" src="{avatar_src}" alt="Alba"/><div class="bubble">Cuando termines, podés avanzar a la siguiente pregunta. Si tu respuesta queda incompleta, Alba puede sugerir una repregunta adaptativa.<div class="time">Ahora 🔊</div></div></div><div class="typing"><span></span><span></span><span></span> Alba está lista para continuar...</div></section></div><div class="answer"><div class="input-fake">Tu respuesta se carga en los campos de abajo para mantener auditoría...</div><button class="mic">🎙</button><button class="send" onclick="nextQ()">Enviar ▶</button></div><div style="text-align:center;color:#667085;font-size:13px;margin-top:12px;">La entrevista es asistida por IA. La decisión final siempre será del equipo de RRHH.</div></main></div></div>
    <script>
      const questions = {payload}; const roleName = {role_payload}; const candidateName = {candidate_payload}; let idx = 0; const shell = document.getElementById('albaShell'); document.getElementById('roleName').innerText = roleName; document.getElementById('candName').innerText = candidateName;
      function render() {{ const text = questions[idx]; document.getElementById('questionText').innerText = text; document.getElementById('chatQ').innerText = text; document.getElementById('questionCount').innerText = 'Pregunta ' + (idx+1) + ' de ' + questions.length; document.getElementById('progText').innerText = (idx+1) + ' / ' + questions.length; document.getElementById('progBar').style.width = (((idx+1)/questions.length)*100) + '%'; }}
      function pickSpanishVoice() {{ const voices = window.speechSynthesis.getVoices(); return voices.find(v => v.lang && v.lang.toLowerCase().startsWith('es-ar')) || voices.find(v => v.lang && v.lang.toLowerCase().startsWith('es')) || voices[0]; }}
      function speakQ() {{ stopSpeak(); if (!('speechSynthesis' in window)) {{ return; }} const intro = idx === 0 ? 'Hola, soy Alba, tu entrevistadora virtual de Recursos Humanos. ' : ''; const u = new SpeechSynthesisUtterance(intro + questions[idx]); u.lang = 'es-AR'; u.rate = 0.95; u.pitch = 1.03; const v = pickSpanishVoice(); if(v) u.voice = v; u.onstart = () => shell.classList.add('speaking'); u.onend = () => shell.classList.remove('speaking'); u.onerror = () => shell.classList.remove('speaking'); window.speechSynthesis.speak(u); }}
      function stopSpeak() {{ if ('speechSynthesis' in window) window.speechSynthesis.cancel(); shell.classList.remove('speaking'); }} function nextQ() {{ stopSpeak(); idx = Math.min(idx + 1, questions.length - 1); render(); }} function prevQ() {{ stopSpeak(); idx = Math.max(idx - 1, 0); render(); }} window.speechSynthesis && (window.speechSynthesis.onvoiceschanged = () => {{}}); render();
    </script>
    '''
    components.html(html, height=850, scrolling=True)

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
