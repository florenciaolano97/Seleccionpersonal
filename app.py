import os
import re
import io
import json
import time
import uuid
import hashlib
from pathlib import Path
from datetime import datetime

import pandas as pd
import requests
import streamlit as st

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

APP_TITLE = "AI-RRHH | Entrevistador virtual autopartista"
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
HISTORY_FILE = DATA_DIR / "evaluaciones_rrhh.csv"

# =========================================================
# PERFILES, PREGUNTAS Y CRITERIOS
# =========================================================

PROTECTED_TOPICS = [
    "edad", "fecha de nacimiento", "estado civil", "embarazo", "hijos", "religión",
    "creencia", "partido político", "sindicato", "orientación sexual", "salud",
    "discapacidad", "nacionalidad", "raza", "etnia", "antecedentes médicos",
    "licencia médica", "obra social", "domicilio exacto",
]

RED_FLAG_PATTERNS = {
    "seguridad": [
        r"no uso epp", r"no usar epp", r"sin epp", r"no respeto procedimiento",
        r"anul(o|ar) alarma", r"trabajo sin protecci", r"saltear seguridad",
    ],
    "conducta": [
        r"me pele(e|o)", r"discuto con todos", r"falt(e|o) mucho",
        r"llego tarde siempre", r"no acepto indicaciones", r"no sigo instrucciones",
    ],
    "disponibilidad": [
        r"no puedo turnos", r"no puedo rotar", r"no trabajo de noche",
        r"no har[ií]a horas extra",
    ],
}

ROLE_PROFILES = {
    "Operario/a de inyección plástica": {
        "descripcion": "Producción en inyectoras, control visual inicial, rebabado, empaque, orden y seguridad.",
        "must_have": [
            "Uso de EPP y respeto por normas de seguridad.",
            "Capacidad para seguir instrucciones operativas.",
            "Disponibilidad compatible con turnos de fábrica.",
        ],
        "competencies": {
            "Experiencia industrial / producción": 0.20,
            "Seguridad industrial y EPP": 0.25,
            "Calidad visual": 0.15,
            "Disciplina operativa": 0.15,
            "Disponibilidad": 0.10,
            "Trabajo en equipo": 0.10,
            "Aprendizaje": 0.05,
        },
        "questions": [
            "Hola, soy Alba, entrevistadora virtual de Recursos Humanos. Para comenzar, contame tu experiencia previa en producción, inyección plástica, autopartes o líneas industriales.",
            "¿Qué elementos de protección personal usarías en una planta y qué harías si una máquina parece insegura?",
            "¿Qué defectos visuales buscarías en una pieza plástica antes de liberarla o empacarla?",
            "Describí una situación en la que tuviste que seguir una instrucción precisa o un estándar de trabajo.",
            "¿Tenés disponibilidad para turnos rotativos, noche o fines de semana según necesidad productiva?",
            "¿Cómo actuarías si ves que un compañero saltea un paso de seguridad para producir más rápido?",
        ],
    },
    "Control de calidad": {
        "descripcion": "Inspección visual/dimensional, registros, no conformidades y comunicación con producción.",
        "must_have": [
            "Rigurosidad en registro y trazabilidad.",
            "Conocimiento básico de medición o disposición para aprender.",
            "Capacidad para escalar una no conformidad.",
        ],
        "competencies": {
            "Calidad visual/dimensional": 0.25,
            "Registro y trazabilidad": 0.20,
            "Criterio ante no conformidades": 0.20,
            "Comunicación": 0.15,
            "Seguridad industrial y EPP": 0.10,
            "Aprendizaje": 0.10,
        },
        "questions": [
            "Hola, soy Alba, entrevistadora virtual de Recursos Humanos. Contame tu experiencia en control de calidad, mediciones, inspección visual o registros.",
            "¿Qué harías si encontrás una pieza fuera de especificación pero producción necesita cumplir el objetivo del turno?",
            "¿Usaste calibre, pie de rey, galgas, plantillas, planillas de control o sistemas de trazabilidad?",
            "¿Cómo documentarías una no conformidad para que sea útil y objetiva?",
            "¿Cómo comunicarías un problema de calidad a un operario o supervisor sin generar conflicto?",
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
            "Conocimiento técnico": 0.25,
            "Seguridad en intervención de máquinas": 0.25,
            "Diagnóstico de fallas": 0.20,
            "Mantenimiento preventivo": 0.15,
            "Trabajo con producción": 0.10,
            "Registro de intervenciones": 0.05,
        },
        "questions": [
            "Hola, soy Alba, entrevistadora virtual de Recursos Humanos. Contame tu experiencia en mantenimiento industrial, inyectoras, moldes, neumática, hidráulica o electricidad.",
            "¿Qué pasos de seguridad harías antes de intervenir una máquina?",
            "¿Cómo diagnosticarías una falla repetitiva en una inyectora o periférico?",
            "¿Participaste en cambios de molde, ajustes de proceso o mantenimiento preventivo?",
            "¿Qué harías si producción te presiona para reparar rápido salteando un paso de seguridad?",
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
            "Responsabilidad": 0.15,
            "Aprendizaje": 0.10,
        },
        "questions": [
            "Hola, soy Alba, entrevistadora virtual de Recursos Humanos. Contame tu experiencia en depósito, logística, inventario, picking, recepción o despacho.",
            "¿Cómo evitarías errores de material o mezcla de lotes en una fábrica autopartista?",
            "¿Qué harías si una línea pide material urgente pero no coincide con el registro de stock?",
            "¿Tenés experiencia con remitos, planillas, códigos, FIFO, lectores o sistemas de stock?",
            "¿Cómo cuidás la seguridad al mover cargas o abastecer una línea?",
        ],
    },
    "Supervisor/a o líder de turno": {
        "descripcion": "Coordinación de personas, objetivos de producción, seguridad, calidad, comunicación y escalamiento.",
        "must_have": [
            "Liderazgo seguro y no autoritario.",
            "Orientación a indicadores con respeto por seguridad y calidad.",
            "Capacidad de resolver conflictos y escalar problemas.",
        ],
        "competencies": {
            "Liderazgo operativo": 0.20,
            "Gestión de seguridad y calidad": 0.20,
            "Planificación del turno": 0.15,
            "Comunicación y conflictos": 0.15,
            "Uso de indicadores": 0.15,
            "Desarrollo del equipo": 0.10,
            "Registro y escalamiento": 0.05,
        },
        "questions": [
            "Hola, soy Alba, entrevistadora virtual de Recursos Humanos. Contame tu experiencia coordinando personas, turnos, objetivos de producción o equipos industriales.",
            "¿Qué hacés si el equipo está atrasado y alguien propone saltear un control de calidad o seguridad?",
            "¿Cómo organizás prioridades al inicio de un turno?",
            "¿Qué indicadores usarías para saber si el turno fue bueno?",
            "Describí una situación en la que resolviste un conflicto entre compañeros.",
        ],
    },
}

KEYWORDS = {
    "Experiencia industrial / producción": ["producción", "línea", "linea", "inyectora", "inyección", "plástico", "autopart", "molde", "operario", "rebaba"],
    "Seguridad industrial y EPP": ["epp", "seguridad", "guantes", "lentes", "protección", "procedimiento", "riesgo", "bloqueo", "5s"],
    "Calidad visual": ["calidad", "defecto", "rebaba", "fisura", "mancha", "deformación", "visual", "rechazo", "inspección"],
    "Disciplina operativa": ["instrucción", "procedimiento", "estándar", "cumplir", "orden", "supervisor", "responsable"],
    "Disponibilidad": ["turno", "rotativo", "noche", "fines de semana", "disponibilidad", "horas extra"],
    "Trabajo en equipo": ["equipo", "compañero", "comunicación", "respeto", "ayuda", "colaborar"],
    "Aprendizaje": ["aprender", "capacitación", "adaptar", "mejora", "formación", "entrenamiento"],
    "Calidad visual/dimensional": ["calidad", "dimensional", "calibre", "pie de rey", "galga", "medición", "tolerancia"],
    "Registro y trazabilidad": ["registro", "planilla", "trazabilidad", "lote", "sistema", "documentar", "código"],
    "Criterio ante no conformidades": ["no conformidad", "rechazar", "bloquear", "separar", "cuarentena", "escalar", "detener"],
    "Comunicación": ["comunicar", "avisar", "explicar", "respeto", "claro", "supervisor", "operario"],
    "Conocimiento técnico": ["mecánica", "eléctrica", "neumática", "hidráulica", "sensor", "plc", "mantenimiento", "molde"],
    "Seguridad en intervención de máquinas": ["bloqueo", "energía cero", "lockout", "seguridad", "epp", "parada", "procedimiento"],
    "Diagnóstico de fallas": ["diagnóstico", "falla", "causa", "síntoma", "prueba", "raíz", "corregir"],
    "Mantenimiento preventivo": ["preventivo", "lubricación", "rutina", "checklist", "correctivo", "orden de trabajo"],
    "Trabajo con producción": ["producción", "operario", "supervisor", "prioridad", "línea", "coordinar"],
    "Registro de intervenciones": ["registro", "orden de trabajo", "reporte", "historial", "intervención"],
    "Orden, stock e inventario": ["stock", "inventario", "depósito", "orden", "ubicación", "conteo", "picking", "fifo"],
    "Trazabilidad y registros": ["trazabilidad", "lote", "remito", "código", "registro", "etiqueta"],
    "Seguridad en movimiento de materiales": ["seguridad", "carga", "autoelevador", "zorra", "apiladora", "epp", "pasillo"],
    "Coordinación con producción": ["producción", "línea", "abastecer", "supervisor", "material", "coordinar"],
    "Responsabilidad": ["responsable", "puntual", "asistencia", "cumplir", "compromiso", "presentismo"],
    "Liderazgo operativo": ["lider", "lideré", "supervisor", "equipo", "coordiné", "personas", "turno"],
    "Gestión de seguridad y calidad": ["seguridad", "calidad", "procedimiento", "epp", "no conformidad", "estándar"],
    "Planificación del turno": ["planificar", "prioridad", "turno", "objetivo", "recursos", "organizar"],
    "Comunicación y conflictos": ["conflicto", "comunicación", "escuchar", "feedback", "corregir", "acuerdo"],
    "Uso de indicadores": ["indicador", "kpi", "scrap", "rechazo", "productividad", "eficiencia", "oee"],
    "Desarrollo del equipo": ["capacitar", "entrenar", "desarrollar", "acompañar", "enseñar", "feedback"],
    "Registro y escalamiento": ["registro", "escalar", "reporte", "parte", "novedad", "turno"],
}

# =========================================================
# CONFIG Y HELPERS
# =========================================================

def get_secret(name: str, default: str = "") -> str:
    try:
        value = st.secrets.get(name, "")
        if value:
            return str(value)
    except Exception:
        pass
    return os.getenv(name, default)


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def stable_candidate_code(raw: str) -> str:
    raw = (raw or "").strip() or str(uuid.uuid4())
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:10].upper()
    return f"CAND-{digest}"


def safe_lower(text: str) -> str:
    return (text or "").lower().strip()


def detect_red_flags(text: str):
    t = safe_lower(text)
    findings = []
    for group, patterns in RED_FLAG_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, t):
                findings.append(f"{group}: {pat}")
    return findings


def detect_sensitive(text: str):
    t = safe_lower(text)
    return [topic for topic in PROTECTED_TOPICS if topic in t]


def count_keywords(text: str, words):
    t = safe_lower(text)
    return sum(1 for w in words if w.lower() in t)


def local_score_competency(competency: str, text: str) -> int:
    words = KEYWORDS.get(competency, [])
    hits = count_keywords(text, words)
    keyword_score = min(hits / 5, 1.0) * 70
    length_bonus = min(len(text.split()) / 120, 1.0) * 15
    example_bonus = 15 if any(x in safe_lower(text) for x in ["por ejemplo", "una vez", "caso", "situación", "experiencia"]) else 0
    return int(round(min(keyword_score + length_bonus + example_bonus, 100)))


def make_transcript_text(transcript):
    blocks = []
    for i, item in enumerate(transcript, start=1):
        blocks.append(f"Pregunta {i}: {item.get('question','')}\nRespuesta {i}: {item.get('answer','')}")
    return "\n\n".join(blocks)


def local_evaluate(role_name: str, cv_text: str, transcript_text: str):
    profile = ROLE_PROFILES[role_name]
    full_text = f"CV:\n{cv_text}\n\nENTREVISTA:\n{transcript_text}"
    red_flags = detect_red_flags(full_text)
    sensitive = detect_sensitive(full_text)

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
        confidence = "Alta" if final_score >= 82 else "Media"
    elif final_score < 55:
        recommendation = "RECHAZAR PRIMERA INSTANCIA"
        confidence = "Media"
    else:
        recommendation = "REVISIÓN HUMANA"
        confidence = "Media"

    strengths = [f"{c}: evidencia favorable ({s}/100)" for c, s in comp_scores.items() if s >= 70][:6]
    risks = [f"{c}: evidencia insuficiente ({s}/100)" for c, s in comp_scores.items() if s < 45][:6]
    if red_flags:
        risks.append("Alertas críticas detectadas: " + "; ".join(red_flags))
    if sensitive:
        risks.append("Datos sensibles detectados, no utilizarlos para decidir: " + ", ".join(sensitive))

    if recommendation.startswith("APROBAR"):
        rationale = "El perfil muestra evidencia suficiente para avanzar a entrevista humana o instancia técnica, manteniendo decisión final en RR.HH."
    elif recommendation.startswith("RECHAZAR"):
        rationale = "El perfil no reúne evidencia suficiente o presenta alertas laborales relevantes para esta primera instancia. Debe validarse por RR.HH."
    else:
        rationale = "El caso queda en zona intermedia y requiere revisión humana antes de definir avance o rechazo."

    return {
        "recommendation": recommendation,
        "score": final_score,
        "confidence": confidence,
        "competency_scores": comp_scores,
        "strengths": strengths,
        "risks": risks,
        "rationale": rationale,
        "red_flags": red_flags,
        "sensitive_data_detected": sensitive,
        "model_used": "motor_local_reglas",
    }


def ai_evaluate(role_name: str, cv_text: str, transcript_text: str, model: str):
    api_key = get_secret("OPENAI_API_KEY")
    if not api_key or OpenAI is None:
        return None, "No hay OPENAI_API_KEY configurada."

    profile = ROLE_PROFILES[role_name]
    client = OpenAI(api_key=api_key)
    schema = {
        "recommendation": "APROBAR PRIMERA INSTANCIA | REVISIÓN HUMANA | RECHAZAR PRIMERA INSTANCIA",
        "score": "integer 0-100",
        "confidence": "Baja | Media | Alta",
        "competency_scores": {"competencia": "integer 0-100"},
        "strengths": ["fortalezas laborales"],
        "risks": ["brechas o riesgos laborales"],
        "rationale": "fundamento claro y auditable",
        "red_flags": ["alertas críticas"],
        "sensitive_data_detected": ["datos sensibles si aparecen"],
        "model_used": model,
    }
    prompt = f"""
Sos un asistente de RR.HH. para preselección inicial en fábrica autopartista plástica.

Puesto: {role_name}
Descripción: {profile['descripcion']}
Requisitos excluyentes: {profile['must_have']}
Competencias y ponderaciones: {profile['competencies']}

Reglas obligatorias:
- Evaluá SOLO evidencias laborales relacionadas con el puesto.
- No uses edad, sexo, embarazo, salud, discapacidad, nacionalidad, religión, política, sindicalización, orientación sexual, estado civil, datos familiares ni domicilio exacto.
- Si aparecen datos sensibles, listalos pero no los uses para puntuar.
- La IA no decide final; la decisión final es humana.
- Si hay duda o evidencia mixta, usá REVISIÓN HUMANA.
- Devolvé exclusivamente JSON válido con esta estructura: {json.dumps(schema, ensure_ascii=False)}

CV:
{cv_text}

Entrevista:
{transcript_text}
"""
    try:
        response = client.responses.create(model=model, input=prompt, temperature=0.2)
        raw = getattr(response, "output_text", "") or response.model_dump_json()
        match = re.search(r"\{.*\}", raw, re.S)
        if match:
            raw = match.group(0)
        data = json.loads(raw)
        data["model_used"] = model
        return data, None
    except Exception as e:
        return None, str(e)

# =========================================================
# D-ID: AVATAR REAL HABLANDO
# =========================================================

def did_headers(api_key: str):
    # D-ID espera el API key en Basic. En la consola de D-ID copiá la API key completa.
    return {
        "Authorization": f"Basic {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def create_did_talk(text: str, source_url: str, api_key: str, voice_id: str, presenter_name: str = "Alba"):
    url = "https://api.d-id.com/talks"
    payload = {
        "source_url": source_url,
        "script": {
            "type": "text",
            "input": text,
            "provider": {
                "type": "microsoft",
                "voice_id": voice_id,
            },
        },
        "config": {
            "fluent": True,
            "pad_audio": 0.0,
            "stitch": True,
        },
        "name": presenter_name,
    }
    r = requests.post(url, headers=did_headers(api_key), json=payload, timeout=45)
    if r.status_code >= 400:
        raise RuntimeError(f"D-ID error {r.status_code}: {r.text}")
    return r.json().get("id")


def poll_did_talk(talk_id: str, api_key: str, max_wait_seconds: int = 90):
    url = f"https://api.d-id.com/talks/{talk_id}"
    start = time.time()
    last_status = "created"
    while time.time() - start < max_wait_seconds:
        r = requests.get(url, headers=did_headers(api_key), timeout=30)
        if r.status_code >= 400:
            raise RuntimeError(f"D-ID polling error {r.status_code}: {r.text}")
        data = r.json()
        last_status = data.get("status", last_status)
        if last_status == "done":
            result_url = data.get("result_url")
            if not result_url:
                raise RuntimeError("D-ID finalizó, pero no devolvió result_url.")
            return result_url, data
        if last_status == "error":
            raise RuntimeError(f"D-ID devolvió error: {json.dumps(data, ensure_ascii=False)}")
        time.sleep(2)
    raise TimeoutError(f"D-ID tardó demasiado. Último estado: {last_status}")


def generate_avatar_video(text: str, source_url: str, api_key: str, voice_id: str):
    talk_id = create_did_talk(text=text, source_url=source_url, api_key=api_key, voice_id=voice_id)
    result_url, raw = poll_did_talk(talk_id=talk_id, api_key=api_key)
    return result_url, talk_id, raw

# =========================================================
# HISTORIAL
# =========================================================

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


def excel_bytes(df: pd.DataFrame):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Evaluaciones", index=False)
    return output.getvalue()

# =========================================================
# UI
# =========================================================

st.set_page_config(page_title="AI-RRHH Avatar", page_icon="🤖", layout="wide")

st.markdown(
    """
    <style>
    .block-container {padding-top: 1.1rem;}
    .hero-card {background: linear-gradient(135deg,#0f172a,#312e81); color:white; padding:1.2rem 1.4rem; border-radius:22px;}
    .avatar-card {background:#ffffff; border:1px solid #e5e7eb; border-radius:24px; padding:1rem; box-shadow:0 10px 30px rgba(15,23,42,.08);}
    .chat-bubble-a {background:#eef2ff; padding:0.8rem 1rem; border-radius:18px; margin-bottom:.6rem; border-left:4px solid #6366f1;}
    .chat-bubble-c {background:#f8fafc; padding:0.8rem 1rem; border-radius:18px; margin-bottom:.6rem; border-left:4px solid #94a3b8;}
    .ok-box {border-left:5px solid #16a34a; background:#f0fdf4; padding:1rem; border-radius:12px;}
    .risk-box {border-left:5px solid #dc2626; background:#fef2f2; padding:1rem; border-radius:12px;}
    .review-box {border-left:5px solid #f59e0b; background:#fffbeb; padding:1rem; border-radius:12px;}
    </style>
    """,
    unsafe_allow_html=True,
)

if "transcript" not in st.session_state:
    st.session_state.transcript = []
if "question_index" not in st.session_state:
    st.session_state.question_index = 0
if "avatar_videos" not in st.session_state:
    st.session_state.avatar_videos = {}
if "last_result" not in st.session_state:
    st.session_state.last_result = None

st.markdown(f"<div class='hero-card'><h1>{APP_TITLE}</h1><p>Avatar real con D-ID + entrevista estructurada + evaluación asistida por IA. La decisión final queda siempre en RR.HH.</p></div>", unsafe_allow_html=True)
st.write("")

with st.sidebar:
    st.header("Configuración")
    role_name = st.selectbox("Puesto", list(ROLE_PROFILES.keys()))
    use_openai = st.toggle("Usar OpenAI para evaluación", value=True)
    openai_model = st.text_input("Modelo OpenAI", value="gpt-4.1-mini")
    st.divider()
    st.subheader("Avatar D-ID")
    did_api_key = st.text_input("D_ID_API_KEY", value=get_secret("D_ID_API_KEY"), type="password")
    did_source_url = st.text_input("D_ID_SOURCE_URL", value=get_secret("D_ID_SOURCE_URL"), placeholder="https://.../alba.png")
    voice_id = st.selectbox(
        "Voz humana",
        [
            "es-AR-ElenaNeural",
            "es-AR-TomasNeural",
            "es-ES-ElviraNeural",
            "es-ES-AlvaroNeural",
            "es-MX-DaliaNeural",
            "es-MX-JorgeNeural",
        ],
        index=0,
    )
    st.caption("Para que el avatar hable de verdad necesitás una imagen pública en D_ID_SOURCE_URL y una API key válida de D-ID.")

profile = ROLE_PROFILES[role_name]
questions = profile["questions"]

# Reset si cambia el puesto
if st.session_state.get("active_role") != role_name:
    st.session_state.active_role = role_name
    st.session_state.question_index = 0
    st.session_state.transcript = []
    st.session_state.avatar_videos = {}
    st.session_state.last_result = None

tab1, tab2, tab3, tab4 = st.tabs(["1. Datos", "2. Avatar entrevistador", "3. Evaluación", "4. Historial"])

with tab1:
    st.subheader("Datos mínimos del candidato")
    col1, col2, col3 = st.columns(3)
    with col1:
        candidate_name = st.text_input("Nombre o código", value="")
    with col2:
        interviewer = st.text_input("Responsable RR.HH.", value="")
    with col3:
        source = st.selectbox("Fuente", ["Hiring Room", "Referido", "Portal de empleo", "Agencia", "Postulación espontánea", "Otro"])
    candidate_code = stable_candidate_code(candidate_name)
    st.info(f"Código auditable: {candidate_code}")

    st.markdown("### Perfil del puesto")
    st.write(profile["descripcion"])
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Requisitos excluyentes**")
        for item in profile["must_have"]:
            st.write(f"- {item}")
    with c2:
        st.markdown("**Competencias ponderadas**")
        st.dataframe(pd.DataFrame([{"Competencia": k, "Peso": f"{int(v*100)}%"} for k, v in profile["competencies"].items()]), hide_index=True, use_container_width=True)

    cv_text = st.text_area("CV / antecedentes relevantes", height=170, placeholder="Pegá experiencia laboral, formación técnica, herramientas, disponibilidad y observaciones objetivas.")
    consent = st.checkbox("Confirmo que el candidato fue informado del uso de una herramienta de asistencia y que la decisión final será humana.")

with tab2:
    st.subheader("Alba — Avatar entrevistador")
    st.caption("Flujo: generar video de Alba → reproducir pregunta → cargar respuesta → avanzar a la siguiente pregunta.")

    if not did_api_key or not did_source_url:
        st.warning("Falta configurar D_ID_API_KEY y/o D_ID_SOURCE_URL. Sin eso, no se puede generar video real con labios sincronizados.")

    q_idx = st.session_state.question_index
    total_q = len(questions)
    if q_idx >= total_q:
        st.success("Entrevista finalizada. Ya podés ir a la pestaña Evaluación.")
    else:
        current_question = questions[q_idx]
        left, right = st.columns([1.05, 0.95])
        with left:
            st.markdown("<div class='avatar-card'>", unsafe_allow_html=True)
            st.markdown(f"### Pregunta {q_idx + 1} de {total_q}")
            video_key = f"{role_name}_{q_idx}"
            if video_key in st.session_state.avatar_videos:
                st.video(st.session_state.avatar_videos[video_key])
            else:
                st.info("Todavía no se generó el video de esta pregunta.")
                st.markdown(f"<div class='chat-bubble-a'><b>Alba dirá:</b><br>{current_question}</div>", unsafe_allow_html=True)

            if st.button("🎥 Generar avatar hablando esta pregunta", type="primary", use_container_width=True, disabled=not bool(did_api_key and did_source_url)):
                try:
                    with st.spinner("D-ID está generando el video de Alba. Puede tardar entre 10 y 60 segundos..."):
                        result_url, talk_id, raw = generate_avatar_video(current_question, did_source_url, did_api_key, voice_id)
                    st.session_state.avatar_videos[video_key] = result_url
                    st.success(f"Video generado correctamente. ID: {talk_id}")
                    st.rerun()
                except Exception as e:
                    st.error(f"No se pudo generar el avatar hablando: {e}")
            st.markdown("</div>", unsafe_allow_html=True)

        with right:
            st.markdown("### Respuesta del candidato")
            answer = st.text_area("Escribir respuesta", key=f"answer_{role_name}_{q_idx}", height=210)
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("Guardar respuesta", use_container_width=True):
                    if not answer.strip():
                        st.warning("Cargá una respuesta antes de guardar.")
                    else:
                        # Si ya había una respuesta para esta pregunta, la reemplaza
                        found = False
                        for item in st.session_state.transcript:
                            if item.get("index") == q_idx:
                                item["answer"] = answer.strip()
                                found = True
                                break
                        if not found:
                            st.session_state.transcript.append({"index": q_idx, "question": current_question, "answer": answer.strip()})
                        st.success("Respuesta guardada.")
            with col_b:
                if st.button("Siguiente pregunta", use_container_width=True):
                    saved_indexes = {x.get("index") for x in st.session_state.transcript}
                    if q_idx not in saved_indexes:
                        st.warning("Primero guardá la respuesta de esta pregunta.")
                    else:
                        st.session_state.question_index += 1
                        st.rerun()

    st.divider()
    st.markdown("### Conversación registrada")
    if st.session_state.transcript:
        for item in sorted(st.session_state.transcript, key=lambda x: x.get("index", 0)):
            st.markdown(f"<div class='chat-bubble-a'><b>Alba:</b><br>{item['question']}</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='chat-bubble-c'><b>Candidato:</b><br>{item['answer']}</div>", unsafe_allow_html=True)
    else:
        st.info("Todavía no hay respuestas guardadas.")

with tab3:
    st.subheader("Evaluación asistida")
    transcript_text = make_transcript_text(sorted(st.session_state.transcript, key=lambda x: x.get("index", 0)))

    if st.button("Evaluar entrevista", type="primary", use_container_width=True):
        if not consent:
            st.error("Primero confirmá el consentimiento en la pestaña Datos.")
            st.stop()
        if not transcript_text.strip():
            st.error("Primero completá al menos una respuesta en la entrevista.")
            st.stop()
        result = None
        error = None
        if use_openai:
            with st.spinner("Evaluando con OpenAI..."):
                result, error = ai_evaluate(role_name, cv_text, transcript_text, openai_model)
        if result is None:
            if error:
                st.warning(f"No se pudo usar OpenAI. Se usará motor local. Detalle: {error}")
            result = local_evaluate(role_name, cv_text, transcript_text)
        st.session_state.last_result = result

    result = st.session_state.last_result
    if result:
        rec = result.get("recommendation", "Sin recomendación")
        score = result.get("score", 0)
        conf = result.get("confidence", "No informado")
        col1, col2, col3 = st.columns(3)
        col1.metric("Recomendación IA", rec)
        col2.metric("Puntaje", f"{score}/100")
        col3.metric("Confianza", conf)

        box = "review-box"
        if "APROBAR" in rec:
            box = "ok-box"
        elif "RECHAZAR" in rec:
            box = "risk-box"
        st.markdown(f"<div class='{box}'><b>Fundamento:</b><br>{result.get('rationale','')}</div>", unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### Fortalezas")
            for s in result.get("strengths", []) or ["Sin fortalezas suficientes detectadas."]:
                st.write(f"- {s}")
        with c2:
            st.markdown("### Riesgos / brechas")
            for r in result.get("risks", []) or ["Sin riesgos relevantes detectados."]:
                st.write(f"- {r}")

        comp = result.get("competency_scores", {})
        if comp:
            comp_df = pd.DataFrame([{"Competencia": k, "Puntaje": v} for k, v in comp.items()])
            st.markdown("### Puntaje por competencia")
            st.dataframe(comp_df, hide_index=True, use_container_width=True)
            st.bar_chart(comp_df.set_index("Competencia"))

        st.divider()
        st.markdown("### Decisión humana final obligatoria")
        human_decision = st.selectbox("Decisión final RR.HH.", ["Pendiente", "Avanza", "No avanza", "Mantener en base", "Requiere entrevista técnica"])
        human_reason = st.text_area("Motivo de decisión humana", height=100)

        audit_row = {
            "fecha_hora": now_str(),
            "codigo_candidato": candidate_code,
            "puesto": role_name,
            "entrevistador": interviewer,
            "fuente": source,
            "recomendacion_ia": rec,
            "puntaje": score,
            "confianza": conf,
            "decision_humana": human_decision,
            "motivo_decision_humana": human_reason,
            "fundamento_ia": result.get("rationale", ""),
            "fortalezas": " | ".join(result.get("strengths", [])),
            "riesgos": " | ".join(result.get("risks", [])),
            "alertas": " | ".join(result.get("red_flags", [])),
            "datos_sensibles_detectados": " | ".join(result.get("sensitive_data_detected", [])),
            "modelo": result.get("model_used", ""),
            "cv_texto": cv_text,
            "entrevista_texto": transcript_text,
            "json_resultado": json.dumps(result, ensure_ascii=False),
        }

        col_save, col_xlsx = st.columns(2)
        with col_save:
            if st.button("Guardar evaluación", use_container_width=True):
                if human_decision == "Pendiente":
                    st.warning("Seleccioná una decisión humana final antes de guardar.")
                else:
                    df_all = append_history(audit_row)
                    st.success(f"Evaluación guardada. Total registros: {len(df_all)}")
        with col_xlsx:
            st.download_button("Descargar evaluación Excel", data=excel_bytes(pd.DataFrame([audit_row])), file_name=f"evaluacion_{candidate_code}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

with tab4:
    st.subheader("Historial y ranking")
    hist = read_history()
    if hist.empty:
        st.info("Todavía no hay evaluaciones guardadas.")
    else:
        if "puntaje" in hist.columns:
            hist_rank = hist.sort_values("puntaje", ascending=False)
        else:
            hist_rank = hist
        st.dataframe(hist_rank, use_container_width=True)
        col1, col2 = st.columns(2)
        col1.download_button("Descargar CSV", data=hist_rank.to_csv(index=False).encode("utf-8"), file_name="historial_evaluaciones_rrhh.csv", mime="text/csv", use_container_width=True)
        col2.download_button("Descargar Excel", data=excel_bytes(hist_rank), file_name="historial_evaluaciones_rrhh.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

st.caption("Uso responsable: esta herramienta asiste la primera selección. La decisión final debe ser humana, auditable y basada en criterios laborales pertinentes.")
