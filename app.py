import base64
import hashlib
import io
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd
import requests
import streamlit as st

APP_TITLE = "Alba Recruiter AI | Entrevistador virtual universal"
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
HISTORY_FILE = DATA_DIR / "evaluaciones_candidatos.csv"

# =========================================================
# CONFIGURACIÓN GENERAL
# =========================================================
DEFAULT_INDUSTRIES = [
    "Industria / Manufactura",
    "Tecnología / IT",
    "Administración / Finanzas",
    "Comercial / Ventas",
    "Atención al cliente",
    "Logística / Supply Chain",
    "Salud",
    "Educación",
    "Construcción",
    "Gastronomía / Hotelería",
    "Retail",
    "Servicios profesionales",
    "Otro",
]

DEFAULT_LEVELS = [
    "Operativo/a",
    "Técnico/a",
    "Administrativo/a",
    "Analista / Junior",
    "Semi Senior",
    "Senior",
    "Coordinación / Liderazgo",
    "Jefatura / Supervisión",
    "Gerencia",
    "Dirección",
]

# Datos personales que pueden registrarse pero NO usarse para decidir.
ADMINISTRATIVE_CANDIDATE_DATA = [
    "nombre", "dni", "telefono", "email", "fecha_nacimiento", "edad", "domicilio", "localidad"
]

# Datos protegidos/no pertinentes: no se usan para puntuar, rankear ni decidir.
PROTECTED_OR_NON_DECISION_DATA = [
    "edad", "fecha de nacimiento", "dni", "documento", "teléfono", "telefono", "email",
    "domicilio", "dirección", "direccion", "estado civil", "embarazo", "hijos",
    "religión", "religion", "política", "politica", "partido político", "sindicato",
    "orientación sexual", "orientacion sexual", "salud", "discapacidad", "nacionalidad",
    "raza", "etnia", "obra social", "antecedentes médicos", "licencia médica"
]

UNIVERSAL_COMPETENCIES = {
    "Adecuación a requisitos excluyentes": 0.18,
    "Experiencia relevante para el puesto": 0.16,
    "Conocimientos técnicos / funcionales": 0.14,
    "Comunicación y claridad": 0.10,
    "Resolución de problemas": 0.10,
    "Trabajo en equipo": 0.08,
    "Responsabilidad y confiabilidad": 0.08,
    "Adaptabilidad y aprendizaje": 0.08,
    "Orientación a resultados": 0.08,
}

KEYWORDS = {
    "Adecuación a requisitos excluyentes": ["cumplo", "requisito", "disponibilidad", "experiencia", "formación", "certificación", "licencia", "herramienta", "idioma", "horario"],
    "Experiencia relevante para el puesto": ["experiencia", "trabajé", "trabaje", "puesto", "empresa", "tarea", "función", "funcion", "responsabilidad", "proyecto", "sector"],
    "Conocimientos técnicos / funcionales": ["sistema", "herramienta", "proceso", "técnico", "tecnico", "procedimiento", "método", "metodo", "análisis", "analisis", "software", "máquina", "maquina"],
    "Comunicación y claridad": ["explicar", "comunicar", "claro", "equipo", "cliente", "reunión", "reunion", "feedback", "escuchar", "coordinar"],
    "Resolución de problemas": ["problema", "resolver", "solución", "solucion", "mejora", "causa", "prioridad", "decidí", "decidi", "analicé", "analice"],
    "Trabajo en equipo": ["equipo", "compañero", "compañera", "colaborar", "ayudar", "coordinar", "respeto", "grupo", "apoyo"],
    "Responsabilidad y confiabilidad": ["responsable", "cumplir", "puntual", "seguimiento", "orden", "compromiso", "confianza", "registro", "control"],
    "Adaptabilidad y aprendizaje": ["aprender", "adaptar", "cambio", "capacitación", "capacitacion", "nuevo", "mejorar", "flexible", "desafío", "desafio"],
    "Orientación a resultados": ["objetivo", "resultado", "indicador", "meta", "cumplimiento", "productividad", "venta", "cliente", "calidad", "plazo"],
}

RED_FLAGS = {
    "conducta_laboral": [
        r"no acepto indicaciones", r"me pele(o|é)", r"discuto con todos", r"falto mucho", r"llego tarde siempre", r"no sigo instrucciones"
    ],
    "seguridad_o_normas": [
        r"no respeto procedimiento", r"no uso epp", r"sin protecci", r"salte(o|ar) controles", r"anulo alarmas", r"no cumplo normas"
    ],
    "incompatibilidad_excluyente": [
        r"no tengo disponibilidad", r"no puedo viajar", r"no puedo turnos", r"no manejo", r"no tengo licencia", r"no tengo experiencia"
    ],
}

QUESTION_BANK = [
    "Contame brevemente tu experiencia laboral más relacionada con este puesto.",
    "¿Qué tareas concretas realizaste que se parezcan a las responsabilidades de esta posición?",
    "¿Qué conocimientos técnicos, herramientas o sistemas dominás para este puesto?",
    "Contame una situación en la que tuviste que resolver un problema laboral. ¿Qué hiciste y qué resultado obtuviste?",
    "¿Cómo te organizás cuando tenés varias prioridades al mismo tiempo?",
    "Describí una situación en la que trabajaste en equipo para lograr un objetivo.",
    "¿Cómo reaccionás cuando recibís una corrección o feedback sobre tu trabajo?",
    "¿Qué te motiva de esta posición y por qué creés que podrías aportar valor?",
]

# =========================================================
# UTILIDADES
# =========================================================
def get_secret(name: str, default: str = "") -> str:
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.getenv(name, default)


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def stable_code(raw: str) -> str:
    base = raw.strip() if raw else str(time.time())
    return "CAND-" + hashlib.sha256(base.encode("utf-8")).hexdigest()[:10].upper()


def normalize_url(url: str) -> str:
    url = (url or "").strip()
    url = url.replace("[img]", "").replace("[/img]", "")
    if "https://" in url and not url.startswith("https://"):
        url = url[url.find("https://"):]
    if " " in url:
        url = url.split()[0]
    return url


def is_valid_image_url(url: str) -> bool:
    u = normalize_url(url).lower()
    return u.startswith("https://") and any(u.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp"])


def safe_lower(text: str) -> str:
    return (text or "").lower().strip()


def detect_protected_data(text: str) -> List[str]:
    t = safe_lower(text)
    return sorted(set([x for x in PROTECTED_OR_NON_DECISION_DATA if x in t]))


def detect_red_flags(text: str) -> List[str]:
    t = safe_lower(text)
    findings = []
    for group, patterns in RED_FLAGS.items():
        for pat in patterns:
            if re.search(pat, t):
                findings.append(f"{group}: {pat}")
    return findings


def keyword_score(comp: str, text: str) -> int:
    t = safe_lower(text)
    words = KEYWORDS.get(comp, [])
    hits = sum(1 for w in words if w in t)
    length_bonus = min(len(text.split()) / 120, 1.0) * 20
    example_bonus = 15 if any(x in t for x in ["por ejemplo", "una vez", "situación", "situacion", "caso", "resultado"]) else 0
    score = min((hits / max(len(words) * 0.35, 1)) * 65 + length_bonus + example_bonus, 100)
    return int(round(score))


def build_questions(role: str, industry: str, seniority: str, must_have: str, responsibilities: str, extra_questions: str) -> List[str]:
    intro = f"Para el puesto de {role} en la industria {industry}, contame qué experiencia tenés que se relacione directamente con esta posición."
    questions = [intro]
    if must_have.strip():
        questions.append(f"El puesto tiene estos requisitos importantes: {must_have}. ¿Cuáles cumplís y con qué evidencia concreta?")
    if responsibilities.strip():
        questions.append(f"Las responsabilidades principales son: {responsibilities}. ¿Cuáles realizaste antes y con qué nivel de autonomía?")
    questions.extend(QUESTION_BANK[2:])
    if extra_questions.strip():
        for q in extra_questions.split("\n"):
            q = q.strip(" -•\t")
            if q:
                questions.append(q if q.endswith("?") else q + "?")
    # dedupe and limit
    out = []
    for q in questions:
        if q not in out:
            out.append(q)
    return out[:12]


def evaluate_candidate(
    role: str,
    industry: str,
    seniority: str,
    must_have: str,
    responsibilities: str,
    cv_text: str,
    interview_text: str,
    admin_data: Dict[str, str],
) -> Dict:
    # Deliberadamente NO se incorporan datos administrativos al texto de scoring.
    evaluable_text = f"Puesto: {role}\nIndustria: {industry}\nNivel: {seniority}\nRequisitos: {must_have}\nResponsabilidades: {responsibilities}\nCV/experiencia declarada: {cv_text}\nEntrevista: {interview_text}"

    comp_scores = {}
    weighted = 0.0
    for comp, weight in UNIVERSAL_COMPETENCIES.items():
        score = keyword_score(comp, evaluable_text)
        comp_scores[comp] = score
        weighted += score * weight

    score = int(round(weighted))
    red_flags = detect_red_flags(evaluable_text)
    protected_in_evaluable = detect_protected_data(evaluable_text)

    # Penalizaciones laborales, no personales.
    if red_flags:
        score = max(0, score - min(18, len(red_flags) * 8))

    if score >= 75 and not red_flags:
        recommendation = "AVANZAR"
        decision_band = "Perfil competitivo para siguiente etapa"
    elif score < 55 or any("seguridad" in r or "conducta" in r for r in red_flags):
        recommendation = "RECHAZAR PRIMERA INSTANCIA"
        decision_band = "Brecha relevante respecto del puesto"
    else:
        recommendation = "REVISIÓN HUMANA"
        decision_band = "Zona intermedia / requiere criterio humano"

    strengths = []
    gaps = []
    for comp, sc in comp_scores.items():
        if sc >= 70:
            strengths.append(f"{comp}: evidencia favorable ({sc}/100).")
        elif sc < 50:
            gaps.append(f"{comp}: evidencia insuficiente o poco específica ({sc}/100).")

    if recommendation == "AVANZAR":
        rationale = (
            "La recomendación es avanzar porque el candidato presenta evidencia laboral suficiente y consistente "
            "en las competencias centrales del puesto. El puntaje global queda por encima del umbral de avance "
            "y no se detectan alertas críticas asociadas a conducta, cumplimiento de normas o requisitos laborales."
        )
    elif recommendation == "RECHAZAR PRIMERA INSTANCIA":
        rationale = (
            "La recomendación es no avanzar en primera instancia porque la evidencia relevada no alcanza el nivel mínimo "
            "esperado para el puesto o existen alertas laborales relevantes. El rechazo debe ser validado por RR.HH. "
            "y fundamentarse únicamente en requisitos, competencias y evidencias relacionadas con el trabajo."
        )
    else:
        rationale = (
            "La recomendación es revisión humana porque el perfil presenta evidencias mixtas: algunos aspectos son compatibles "
            "con el puesto, pero existen brechas, falta de ejemplos concretos o información insuficiente para decidir de forma confiable."
        )

    next_steps = []
    if recommendation == "AVANZAR":
        next_steps = [
            "Coordinar entrevista humana con RR.HH. o líder del área.",
            "Validar requisitos excluyentes y expectativas salariales/horarias.",
            "Aplicar prueba técnica o caso práctico si el puesto lo requiere.",
        ]
    elif recommendation == "REVISIÓN HUMANA":
        next_steps = [
            "Realizar entrevista breve de profundización sobre las brechas detectadas.",
            "Solicitar ejemplos concretos de experiencia vinculada al puesto.",
            "No tomar decisión final sin revisión humana documentada.",
        ]
    else:
        next_steps = [
            "Validar que el rechazo esté basado en requisitos laborales objetivos.",
            "Registrar motivo de no avance de forma clara y no discriminatoria.",
            "Considerar mantener en base si puede aplicar a otro puesto compatible.",
        ]

    return {
        "fecha_hora": now_str(),
        "codigo_candidato": stable_code(admin_data.get("nombre", "") + admin_data.get("dni", "") + admin_data.get("email", "")),
        "puesto": role,
        "industria": industry,
        "nivel": seniority,
        "recomendacion": recommendation,
        "banda_decision": decision_band,
        "puntaje_global": score,
        "puntajes_competencias": comp_scores,
        "fortalezas": strengths[:7],
        "brechas": gaps[:7],
        "alertas_laborales": red_flags,
        "datos_no_usados_para_decidir_detectados": protected_in_evaluable,
        "fundamento": rationale,
        "proximos_pasos": next_steps,
        "nota_datos_personales": "DNI, teléfono, edad, fecha de nacimiento, email y otros datos administrativos pueden registrarse para gestión, pero no se usan para puntuar, rankear ni decidir.",
    }


def flatten_for_history(admin_data: Dict[str, str], result: Dict, interview_text: str, cv_text: str) -> Dict:
    row = {
        "fecha_hora": result["fecha_hora"],
        "codigo_candidato": result["codigo_candidato"],
        "nombre": admin_data.get("nombre", ""),
        "dni": admin_data.get("dni", ""),
        "telefono": admin_data.get("telefono", ""),
        "email": admin_data.get("email", ""),
        "fecha_nacimiento": admin_data.get("fecha_nacimiento", ""),
        "edad": admin_data.get("edad", ""),
        "puesto": result["puesto"],
        "industria": result["industria"],
        "nivel": result["nivel"],
        "recomendacion": result["recomendacion"],
        "puntaje_global": result["puntaje_global"],
        "banda_decision": result["banda_decision"],
        "fundamento": result["fundamento"],
        "fortalezas": " | ".join(result["fortalezas"]),
        "brechas": " | ".join(result["brechas"]),
        "alertas_laborales": " | ".join(result["alertas_laborales"]),
        "proximos_pasos": " | ".join(result["proximos_pasos"]),
        "cv_texto": cv_text,
        "entrevista_texto": interview_text,
        "json_resultado": json.dumps(result, ensure_ascii=False),
    }
    for comp, score in result["puntajes_competencias"].items():
        row[f"score_{comp}"] = score
    return row


def save_history(row: Dict) -> pd.DataFrame:
    df_new = pd.DataFrame([row])
    if HISTORY_FILE.exists():
        df_old = pd.read_csv(HISTORY_FILE)
        df = pd.concat([df_old, df_new], ignore_index=True)
    else:
        df = df_new
    df.to_csv(HISTORY_FILE, index=False)
    return df


def read_history() -> pd.DataFrame:
    if HISTORY_FILE.exists():
        return pd.read_csv(HISTORY_FILE)
    return pd.DataFrame()


def excel_bytes(df: pd.DataFrame) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Ranking")
    return output.getvalue()

# =========================================================
# D-ID AVATAR
# =========================================================
def did_headers(api_key: str) -> Dict[str, str]:
    api_key = (api_key or "").strip()
    # D-ID acepta Basic <base64 usuario:password>. Si el usuario pega usuario:password, se encodea.
    if ":" in api_key and not api_key.lower().startswith("basic "):
        api_key = base64.b64encode(api_key.encode("utf-8")).decode("utf-8")
    if not api_key.lower().startswith("basic "):
        api_key = "Basic " + api_key
    return {"Authorization": api_key, "Content-Type": "application/json"}


def create_did_talk(api_key: str, source_url: str, text: str, voice_id: str = "es-AR-ElenaNeural") -> Tuple[str, str]:
    source_url = normalize_url(source_url)
    if not api_key:
        return "", "Falta D_ID_API_KEY."
    if not is_valid_image_url(source_url):
        return "", "D_ID_SOURCE_URL debe ser una URL pública HTTPS y terminar en .jpg/.jpeg/.png/.webp."

    payload = {
        "source_url": source_url,
        "script": {
            "type": "text",
            "input": text,
            "provider": {"type": "microsoft", "voice_id": voice_id},
        },
        "config": {"fluent": True, "pad_audio": 0.2},
    }
    try:
        r = requests.post("https://api.d-id.com/talks", headers=did_headers(api_key), json=payload, timeout=30)
        if r.status_code >= 300:
            return "", f"D-ID error {r.status_code}: {r.text}"
        talk_id = r.json().get("id")
        if not talk_id:
            return "", f"D-ID no devolvió ID: {r.text}"
        return talk_id, ""
    except Exception as e:
        return "", str(e)


def poll_did_talk(api_key: str, talk_id: str, max_wait: int = 90) -> Tuple[str, str]:
    try:
        start = time.time()
        while time.time() - start < max_wait:
            r = requests.get(f"https://api.d-id.com/talks/{talk_id}", headers=did_headers(api_key), timeout=20)
            if r.status_code >= 300:
                return "", f"D-ID status error {r.status_code}: {r.text}"
            data = r.json()
            status = data.get("status")
            if status == "done" and data.get("result_url"):
                return data["result_url"], ""
            if status in ["error", "rejected"]:
                return "", f"D-ID no pudo generar video: {json.dumps(data, ensure_ascii=False)}"
            time.sleep(3)
        return "", "Tiempo de espera agotado al generar video."
    except Exception as e:
        return "", str(e)

# =========================================================
# UI
# =========================================================
st.set_page_config(page_title="Alba Recruiter AI", page_icon="🎙️", layout="wide")

st.markdown(
    """
    <style>
    .block-container {padding-top: 1.2rem; max-width: 1300px;}
    .hero {background: linear-gradient(90deg,#24185f,#5c3df5); color:white; padding:1.2rem; border-radius:1rem;}
    .card {border:1px solid #e6e8f0; border-radius:1rem; padding:1rem; background:#fff; box-shadow:0 2px 10px rgba(20,20,50,.04);}
    .alba {background:#eef0ff; border-left:5px solid #5c3df5; padding:1rem; border-radius:1rem; margin:.5rem 0;}
    .cand {background:#eaf4ff; border-left:5px solid #2b8ee8; padding:1rem; border-radius:1rem; margin:.5rem 0;}
    .warn {background:#fff8df; border-left:5px solid #e6a400; padding:1rem; border-radius:1rem;}
    .ok {background:#ecfff4; border-left:5px solid #0aa85a; padding:1rem; border-radius:1rem;}
    .bad {background:#fff0f0; border-left:5px solid #e23d3d; padding:1rem; border-radius:1rem;}
    .muted {color:#6b7280; font-size:.92rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

if "answers" not in st.session_state:
    st.session_state.answers = {}
if "current_q" not in st.session_state:
    st.session_state.current_q = 0
if "last_video_url" not in st.session_state:
    st.session_state.last_video_url = ""
if "last_result" not in st.session_state:
    st.session_state.last_result = None

st.markdown(f"<div class='hero'><h1>{APP_TITLE}</h1><p>Opción A estable: avatar hablando + entrevista estructurada + evaluación completa + ranking. Sin videollamada pesada.</p></div>", unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ Configuración")
    did_api_key = st.text_input("D_ID_API_KEY", value=get_secret("D_ID_API_KEY", ""), type="password")
    did_source_url = st.text_input("D_ID_SOURCE_URL", value=get_secret("D_ID_SOURCE_URL", ""))
    voice_id = st.text_input("Voz D-ID", value="es-AR-ElenaNeural")
    st.caption("La URL debe ser pública HTTPS y terminar en .jpg/.jpeg/.png/.webp.")
    st.divider()
    st.markdown("### Política de datos")
    st.info("Los datos administrativos del candidato pueden registrarse, pero NO se usan para puntuar, rankear ni decidir. La evaluación usa solo evidencias laborales.")

tabs = st.tabs(["1. Configurar búsqueda", "2. Entrevista con Alba", "3. Evaluación", "4. Ranking", "5. Política de uso"])

with tabs[0]:
    st.header("1. Configurar búsqueda universal")
    col1, col2, col3 = st.columns(3)
    with col1:
        company = st.text_input("Empresa / cliente", placeholder="Opcional")
        industry = st.selectbox("Industria", DEFAULT_INDUSTRIES)
    with col2:
        role = st.text_input("Nombre del puesto", placeholder="Ej: Analista de compras, Operario, Vendedor, Desarrollador...")
        seniority = st.selectbox("Nivel", DEFAULT_LEVELS)
    with col3:
        recruiter = st.text_input("Recruiter / evaluador", placeholder="Opcional")
        source = st.selectbox("Fuente", ["Portal", "Referido", "LinkedIn", "Agencia", "Base propia", "Otro"])

    must_have = st.text_area("Requisitos excluyentes o importantes", height=100, placeholder="Ej: experiencia mínima, certificaciones, herramientas, disponibilidad, idioma, licencia, formación...")
    responsibilities = st.text_area("Responsabilidades principales", height=100, placeholder="Ej: tareas del puesto, objetivos, herramientas, interacción con equipos/clientes...")
    extra_questions = st.text_area("Preguntas adicionales opcionales, una por línea", height=100)

    st.subheader("Datos administrativos del candidato")
    st.caption("Se registran para gestión. No se usan para puntuar, rankear ni decidir.")
    c1, c2, c3 = st.columns(3)
    with c1:
        nombre = st.text_input("Nombre y apellido")
        dni = st.text_input("DNI / documento")
    with c2:
        telefono = st.text_input("Teléfono")
        email = st.text_input("Email")
    with c3:
        fecha_nac = st.text_input("Fecha de nacimiento")
        edad = st.text_input("Edad")

    cv_text = st.text_area("CV / antecedentes laborales relevantes", height=160)

    st.session_state.search_config = {
        "company": company,
        "industry": industry,
        "role": role,
        "seniority": seniority,
        "recruiter": recruiter,
        "source": source,
        "must_have": must_have,
        "responsibilities": responsibilities,
        "extra_questions": extra_questions,
    }
    st.session_state.admin_data = {
        "nombre": nombre,
        "dni": dni,
        "telefono": telefono,
        "email": email,
        "fecha_nacimiento": fecha_nac,
        "edad": edad,
    }
    st.session_state.cv_text = cv_text

with tabs[1]:
    cfg = st.session_state.get("search_config", {})
    role = cfg.get("role", "") or "puesto a evaluar"
    industry = cfg.get("industry", "") or "industria"
    seniority = cfg.get("seniority", "") or "nivel"
    questions = build_questions(role, industry, seniority, cfg.get("must_have", ""), cfg.get("responsibilities", ""), cfg.get("extra_questions", ""))
    q_idx = min(st.session_state.current_q, len(questions) - 1)
    question = questions[q_idx]

    st.header("2. Entrevista con Alba")
    st.progress((q_idx + 1) / len(questions))
    col_left, col_right = st.columns([1.2, 1])

    with col_left:
        st.subheader("🎬 Avatar hablando")
        if st.session_state.last_video_url:
            st.video(st.session_state.last_video_url)
        elif is_valid_image_url(did_source_url):
            st.image(normalize_url(did_source_url), caption="Imagen base de Alba. Al generar la pregunta, se mostrará el video con labios sincronizados.")
        else:
            st.markdown("<div class='warn'>Configurá una URL pública válida para el avatar.</div>", unsafe_allow_html=True)

        if st.button("Generar / reproducir pregunta con Alba", type="primary", use_container_width=True):
            with st.spinner("Generando video con D-ID..."):
                talk_id, err = create_did_talk(did_api_key, did_source_url, question, voice_id)
                if err:
                    st.error(err)
                else:
                    video_url, err = poll_did_talk(did_api_key, talk_id)
                    if err:
                        st.error(err)
                    else:
                        st.session_state.last_video_url = video_url
                        st.rerun()

    with col_right:
        st.subheader(f"💬 Conversación | Pregunta {q_idx + 1} de {len(questions)}")
        for i in range(q_idx + 1):
            st.markdown(f"<div class='alba'><b>Alba:</b><br>{questions[i]}</div>", unsafe_allow_html=True)
            ans = st.session_state.answers.get(i, "")
            if ans:
                st.markdown(f"<div class='cand'><b>Candidato:</b><br>{ans}</div>", unsafe_allow_html=True)

    st.subheader("Respuesta del candidato")
    answer = st.text_area("Escribir respuesta", value=st.session_state.answers.get(q_idx, ""), height=140, key=f"answer_{q_idx}")

    b1, b2, b3 = st.columns(3)
    with b1:
        if st.button("Guardar y siguiente", type="primary", use_container_width=True):
            st.session_state.answers[q_idx] = answer
            st.session_state.current_q = min(q_idx + 1, len(questions) - 1)
            st.session_state.last_video_url = ""
            st.rerun()
    with b2:
        if st.button("Volver pregunta anterior", use_container_width=True):
            st.session_state.answers[q_idx] = answer
            st.session_state.current_q = max(q_idx - 1, 0)
            st.session_state.last_video_url = ""
            st.rerun()
    with b3:
        if st.button("Reiniciar entrevista", use_container_width=True):
            st.session_state.answers = {}
            st.session_state.current_q = 0
            st.session_state.last_video_url = ""
            st.session_state.last_result = None
            st.rerun()

with tabs[2]:
    st.header("3. Evaluación e informe completo")
    cfg = st.session_state.get("search_config", {})
    admin = st.session_state.get("admin_data", {})
    cv_text = st.session_state.get("cv_text", "")
    role = cfg.get("role", "") or "puesto a evaluar"
    industry = cfg.get("industry", "") or "industria"
    seniority = cfg.get("seniority", "") or "nivel"
    questions = build_questions(role, industry, seniority, cfg.get("must_have", ""), cfg.get("responsibilities", ""), cfg.get("extra_questions", ""))
    interview_text = "\n\n".join([f"Pregunta: {questions[i]}\nRespuesta: {st.session_state.answers.get(i, '')}" for i in range(len(questions)) if st.session_state.answers.get(i, "").strip()])

    if st.button("Evaluar candidato", type="primary", use_container_width=True):
        result = evaluate_candidate(
            role=role,
            industry=industry,
            seniority=seniority,
            must_have=cfg.get("must_have", ""),
            responsibilities=cfg.get("responsibilities", ""),
            cv_text=cv_text,
            interview_text=interview_text,
            admin_data=admin,
        )
        st.session_state.last_result = result

    result = st.session_state.last_result
    if result:
        rec = result["recomendacion"]
        klass = "ok" if rec == "AVANZAR" else "bad" if rec.startswith("RECHAZAR") else "warn"
        st.markdown(f"<div class='{klass}'><h3>{rec}</h3><p><b>Puntaje global:</b> {result['puntaje_global']}/100</p><p>{result['banda_decision']}</p></div>", unsafe_allow_html=True)

        st.subheader("Fundamento de Alba")
        st.write(result["fundamento"])

        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Fortalezas")
            for x in result["fortalezas"] or ["No se detectaron fortalezas suficientes con evidencia concreta."]:
                st.write("- " + x)
        with c2:
            st.subheader("Brechas / riesgos")
            for x in result["brechas"] or ["No se detectaron brechas relevantes."]:
                st.write("- " + x)
            for x in result["alertas_laborales"]:
                st.warning(x)

        st.subheader("Puntaje por competencia")
        comp_df = pd.DataFrame([{"Competencia": k, "Puntaje": v} for k, v in result["puntajes_competencias"].items()])
        st.dataframe(comp_df, use_container_width=True, hide_index=True)
        st.bar_chart(comp_df.set_index("Competencia"))

        st.subheader("Próximos pasos sugeridos")
        for x in result["proximos_pasos"]:
            st.write("- " + x)

        st.info(result["nota_datos_personales"])
        if result["datos_no_usados_para_decidir_detectados"]:
            st.warning("Se detectaron datos personales/no decisorios en textos evaluables. No se usaron para puntuar: " + ", ".join(result["datos_no_usados_para_decidir_detectados"]))

        row = flatten_for_history(admin, result, interview_text, cv_text)
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            if st.button("Guardar en ranking", use_container_width=True):
                df = save_history(row)
                st.success(f"Guardado. Total candidatos: {len(df)}")
        with col_b:
            st.download_button("Descargar informe Excel", data=excel_bytes(pd.DataFrame([row])), file_name=f"informe_{result['codigo_candidato']}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
        with col_c:
            st.download_button("Descargar informe JSON", data=json.dumps(row, ensure_ascii=False, indent=2).encode("utf-8"), file_name=f"informe_{result['codigo_candidato']}.json", mime="application/json", use_container_width=True)

with tabs[3]:
    st.header("4. Ranking de candidatos")
    hist = read_history()
    if hist.empty:
        st.info("Todavía no hay candidatos guardados.")
    else:
        filters = st.columns(3)
        with filters[0]:
            f_role = st.selectbox("Filtrar por puesto", ["Todos"] + sorted(hist["puesto"].dropna().unique().tolist()))
        with filters[1]:
            f_ind = st.selectbox("Filtrar por industria", ["Todas"] + sorted(hist["industria"].dropna().unique().tolist()))
        with filters[2]:
            f_rec = st.selectbox("Filtrar por recomendación", ["Todas"] + sorted(hist["recomendacion"].dropna().unique().tolist()))

        df = hist.copy()
        if f_role != "Todos":
            df = df[df["puesto"] == f_role]
        if f_ind != "Todas":
            df = df[df["industria"] == f_ind]
        if f_rec != "Todas":
            df = df[df["recomendacion"] == f_rec]

        df = df.sort_values(by="puntaje_global", ascending=False).reset_index(drop=True)
        df.insert(0, "ranking", range(1, len(df) + 1))
        show_cols = ["ranking", "nombre", "codigo_candidato", "puesto", "industria", "nivel", "recomendacion", "puntaje_global", "banda_decision", "fundamento"]
        st.dataframe(df[[c for c in show_cols if c in df.columns]], use_container_width=True, hide_index=True)
        st.download_button("Descargar ranking Excel", data=excel_bytes(df), file_name="ranking_candidatos.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

with tabs[4]:
    st.header("5. Política de uso responsable")
    st.markdown(
        """
        - La herramienta asiste la preselección, pero la decisión final debe ser humana.
        - Los datos de empresa no se requieren para evaluar y no deben cargarse si son confidenciales.
        - Los datos administrativos del candidato pueden registrarse para gestión: nombre, DNI, teléfono, email, fecha de nacimiento o edad.
        - Esos datos administrativos NO se usan para puntuar, rankear, rechazar ni aprobar.
        - La evaluación se basa en evidencias laborales: experiencia, conocimientos, competencias, ejemplos, requisitos y responsabilidades del puesto.
        - Todo rechazo debe tener fundamento laboral claro, verificable y no discriminatorio.
        - Los casos intermedios deben pasar a revisión humana.
        - No se deben inferir emociones, personalidad, salud, ideología, religión, orientación sexual, estado civil, maternidad/paternidad o condición médica.
        """
    )
