
import os
import re
import io
import json
import uuid
import hashlib
from pathlib import Path
from datetime import datetime

import pandas as pd
import streamlit as st

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

tab1, tab2, tab3, tab4 = st.tabs([
    "1. Puesto y candidato",
    "2. Entrevista estructurada",
    "3. Evaluación IA",
    "4. Historial y exportación",
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

    consent = st.checkbox(
        "Confirmo que el candidato fue informado de que se usará una herramienta de asistencia para preselección y que la decisión final será humana.",
        value=False,
    )

with tab2:
    st.subheader("Entrevista estructurada sugerida")
    st.caption("Usar las mismas preguntas para candidatos del mismo puesto mejora la comparabilidad y reduce sesgos.")

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

with tab3:
    st.subheader("Evaluación y recomendación")
    st.caption("La recomendación se basa en evidencias laborales relacionadas con el puesto. No debe reemplazar la decisión humana.")

    if st.button("Evaluar candidato", type="primary", use_container_width=True):
        if not consent:
            st.error("Antes de evaluar, confirmá el consentimiento/información al candidato en la pestaña 1.")
            st.stop()

        candidate_text = make_answers_text(questions, answers) + "\n\nObservaciones entrevistador:\n" + free_notes

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
    st.subheader("Historial de evaluaciones")
    hist = read_history()

    if hist.empty:
        st.info("Todavía no hay evaluaciones guardadas.")
    else:
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
