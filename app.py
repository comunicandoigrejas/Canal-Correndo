import streamlit as st
import datetime
from datetime import date
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from openai import OpenAI
import pandas as pd
import time

# --- 1. CONFIGURAÇÃO E CSS ---
st.set_page_config(page_title="Running Coach", page_icon="🏃", layout="centered")

st.markdown("""
<style>
    header {visibility: hidden;}
    footer {visibility: hidden;}
    .block-container {padding-top: 2rem;}

    /* Estilos Gerais */
    .stButton > button {
        width: 100%;
        height: 80px;
        font-size: 20px;
        border-radius: 12px;
        margin-bottom: 10px;
    }
    
    .admin-btn > button {
        background-color: #31333F;
        color: white;
        border: 2px solid #ff4b4b;
    }
    
    .small-btn > button {
        height: 50px !important;
        background-color: transparent;
        border: 1px solid #ccc;
        color: #31333F;
    }
    
    /* Botão de Fechar (X) Pequeno */
    .close-btn > button {
        height: 40px !important;
        min-height: 40px !important;
        width: 100% !important;
        background-color: transparent !important;
        border: 1px solid #ff4b4b !important;
        color: #ff4b4b !important;
        font-size: 16px !important;
        font-weight: bold !important;
    }
    .close-btn > button:hover {
        background-color: #ff4b4b !important;
        color: white !important;
    }

    .highlight-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #ff4b4b;
        margin-bottom: 20px;
        color: #31333F !important;
    }
    .highlight-card h3, .highlight-card p, .highlight-card strong {
        color: #31333F !important;
    }
    
    .message-card {
        background-color: #fff3cd;
        padding: 15px;
        border-radius: 10px;
        border-left: 5px solid #ffc107;
        margin-bottom: 5px;
        color: #856404 !important;
        height: 100%;
    }
    
    .success-card {
        background-color: #d4edda;
        padding: 15px;
        border-radius: 10px;
        border-left: 5px solid #28a745;
        margin-bottom: 20px;
        color: #155724 !important;
        text-align: center;
        font-weight: bold;
        font-size: 18px;
    }

    /* --- CORREÇÃO DE TABELA --- */
    [data-testid="stTable"] th:nth-child(1), [data-testid="stTable"] td:nth-child(1) {
        min-width: 15px !important; white-space: nowrap !important;
    }
    [data-testid="stTable"] th:nth-child(2), [data-testid="stTable"] td:nth-child(2) {
        min-width: 30px !important; white-space: nowrap !important; 
    }
    [data-testid="stTable"] th:nth-child(3), [data-testid="stTable"] td:nth-child(3) {
        min-width: 130px !important; white-space: nowrap !important; 
    }
    [data-testid="stTable"] td { vertical-align: top !important; }
</style>
""", unsafe_allow_html=True)

# --- 2. GERENCIAMENTO DE SESSÃO ---

if "pagina_atual" not in st.session_state: st.session_state["pagina_atual"] = "login"
if "usuario_atual" not in st.session_state: st.session_state["usuario_atual"] = None
if "is_admin" not in st.session_state: st.session_state["is_admin"] = False
if "modalidade" not in st.session_state: st.session_state["modalidade"] = "Corrida" 
if "messages" not in st.session_state: st.session_state["messages"] = []
if "messages_admin" not in st.session_state: st.session_state["messages_admin"] = []

def navegar_para(pagina): st.session_state["pagina_atual"] = pagina

def logout():
    st.session_state["usuario_atual"] = None
    st.session_state["pagina_atual"] = "login"
    st.session_state["messages"] = []
    st.session_state["messages_admin"] = []

# --- 3. CONEXÃO E LÓGICA (COM CACHE PARA EVITAR ERRO API) ---

@st.cache_resource(ttl=600)
def conectar_gsheets():
    try:
        if "gcp_service_account" not in st.secrets: 
            st.warning("Segredos off.")
            return None
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gcp_service_account"]), scope)
        client = gspread.authorize(creds)
        return client.open("Running_Data")
    except Exception as e: 
        st.error(f"Conexão instável. Aguarde... ({e})")
        time.sleep(2)
        return None

def verificar_login(usuario, senha):
    ss = conectar_gsheets()
    if ss:
        try:
            ws = ss.worksheet("Usuarios")
            records = ws.get_all_records()
            for u in records:
                u_planilha = str(u['Usuario']).strip()
                s_planilha = str(u['Senha']).strip()
                if u_planilha == usuario and s_planilha == senha:
                    if str(u.get('Status', 'Ativo')) == 'Bloqueado': return "BLOQUEADO", None, None
                    modalidade_raw = str(u.get('Modalidade', 'Corrida')).strip()
                    return u['Nome'], u.get('Funcao', 'aluno'), modalidade_raw
            return None, None, None
        except Exception as e: st.error(f"Erro no Login: {e}"); return None, None, None
    return None, None, None

def carregar_mensagens_usuario(user_id):
    ss = conectar_gsheets(); msgs = []
    if ss:
        try:
            ws = ss.worksheet("Mensagens")
            records = ws.get_all_records()
            for row in reversed(records):
                dest = str(row.get('Destinatario', 'TODOS')).strip()
                if dest in ['TODOS', user_id]:
                    msgs.append(row)
                    if len(msgs) >= 3: break
        except: pass
    return msgs

def excluir_aviso(msg_data):
    ss = conectar_gsheets()
    if ss:
        try:
            ws = ss.worksheet("Mensagens")
            data = ws.get_all_records()
            for i, row in enumerate(data):
                if (str(row.get('Data')) == str(msg_data.get('Data')) and
                    str(row.get('Destinatario')) == str(msg_data.get('Destinatario')) and
                    str(row.get('Mensagem')) == str(msg_data.get('Mensagem')) and
                    str(row.get('Tipo')) == str(msg_data.get('Tipo'))):
                    ws.delete_rows(i + 2)
                    return True
        except Exception as e: st.error(f"Erro ao excluir: {e}")
    return False

def carregar_contexto_ia():
    try:
        with open("treino_contexto.md", "r", encoding="utf-8") as f: return f.read()
    except: return "Sem contexto."

def calcular_pace_medio(tempo_str, distancia_km):
    try:
        tempo_str = tempo_str.strip()
        parts = list(map(int, tempo_str.split(':')))
        total_min = 0
        if len(parts) == 3: total_min = parts[0]*60 + parts[1] + parts[2]/60
        elif len(parts) == 2: total_min = parts[0] + parts[1]/60
        else: return None
        if distancia_km > 0:
            pace_dec = total_min / distancia_km
            pace_min = int(pace_dec)
            pace_sec = int((pace_dec - pace_min) * 60)
            return f"{pace_min:02d}:{pace_sec:02d}"
    except: return None
    return None

# --- 4. LOGIN ---

if st.session_state["usuario_atual"] is None:
    st.title("🏃 Running Coach")
    with st.form("login"):
        u = st.text_input("Usuário").strip()
        s = st.text_input("Senha", type="password").strip()
        if st.form_submit_button("Entrar"):
            nome, funcao, modalidade = verificar_login(u, s)
            if nome == "BLOQUEADO": st.error("Bloqueado.")
            elif nome:
                st.session_state["usuario_atual"] = u
                st.session_state["nome_usuario"] = nome
                st.session_state["is_admin"] = (funcao == 'admin')
                st.session_state["modalidade"] = modalidade 
                st.session_state["pagina_atual"] = "dashboard"
                st.rerun()
            else: st.error("Dados incorretos.")
    st.stop()

# --- 5. APP PRINCIPAL ---

USER = st.session_state["usuario_atual"]
NOME = st.session_state["nome_usuario"]
ADMIN = st.session_state["is_admin"]
MODALIDADE = st.session_state["modalidade"]
IS_MUSCULACAO = "muscula" in str(MODALIDADE).lower()

# === DASHBOARD ===
if st.session_state["pagina_atual"] == "dashboard":
    c1, c2 = st.columns([3, 1])
    c1.title(f"Olá, {NOME}!")
    if c2.button("Sair"): logout(); st.rerun()

    # Avisos do Treinador
    try:
        mensagens = carregar_mensagens_usuario(USER)
        if mensagens:
            st.subheader("🔔 Avisos")
            for i, m in enumerate(mensagens):
                tp = m.get('Tipo', 'Aviso')
                msg = m.get('Mensagem', '')
                
                col_msg, col_x = st.columns([0.85, 0.15])
                with col_msg:
                    st.markdown(f"<div class='message-card'><strong>{tp}:</strong> {msg}</div>", unsafe_allow_html=True)
                with col_x:
                    st.markdown('<div class="close-btn">', unsafe_allow_html=True)
                    if st.button("X", key=f"del_msg_{i}", help="Apagar"):
                        if excluir_aviso(m):
                            st.success("Apagado!")
                            time.sleep(0.5); st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)
            st.markdown("---")
    except Exception as e: st.error(f"Erro ao carregar avisos: {e}")

    # Resposta Aluno
    with st.expander("💬 Falar com o Treinador"):
        with st.form("form_resposta_aluno"):
            texto_resp = st.text_area("Mensagem:")
            if st.form_submit_button("Enviar"):
                ss = conectar_gsheets()
                if ss:
                    try:
                        ss.worksheet("Mensagens").append_row([
                            date.today().strftime("%d/%m/%Y"), "ADMIN", texto_resp, f"De: {NOME}"
                        ])
                        st.success("Enviado!")
                    except Exception as e: st.error(e)
    
    # Treino de Hoje
    treino = None
    ss = conectar_gsheets()
    if ss:
        try:
            ws = ss.worksheet("Agenda")
            hoje = date.today().strftime("%d/%m/%Y")
            for r in ws.get_all_records():
                if str(r['ID_Usuario']) == USER and str(r['Data']) == hoje:
                    treino = r; break
        except: pass
    
    st.subheader("📅 Treino de Hoje")
    if treino:
        st.markdown(f"<div class='highlight-card'><h3>{treino['Tipo']}</h3><p>{treino['Detalhes']}</p></div>", unsafe_allow_html=True)
    else: st.info("Descanso! 💤")

    # Verifica se treinou
    try:
        if ss:
            ws_reg = ss.worksheet("Registros")
            hoje_str = date.today().strftime("%d/%m/%Y")
            records_reg = ws_reg.get_all_records()
            treinou_hoje = False
            for reg in records_reg:
                if str(reg['ID_Usuario']) == USER and str(reg['Data']) == hoje_str:
                    treinou_hoje = True; break
            if treinou_hoje:
                st.markdown(f"<div class='success-card'>🎉 Parabéns! Treino Realizado!</div>", unsafe_allow_html=True)
    except: pass

    st.markdown("---")
    
    c1, c2, c3 = st.columns(3)
    with c1:
        st.button("📝 Registrar", on_click=navegar_para, args=("registro",))
        st.button("📅 Agenda", on_click=navegar_para, args=("agenda",))
    with c2:
        st.button("📊 Histórico", on_click=navegar_para, args=("historico",))
        st.button("🤖 IA Coach", on_click=navegar_para, args=("ia_coach",))
    with c3:
        if not IS_MUSCULACAO:
            st.button("🏅 Provas", on_click=navegar_para, args=("provas",))
        if ADMIN:
             st.markdown('<div class="admin-btn">', unsafe_allow_html=True)
             st.button("⚙️ ADMIN", on_click=navegar_para, args=("admin_panel",))
             st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown('<div class="small-btn">', unsafe_allow_html=True)
    st.button("🔑 Alterar Senha", on_click=navegar_para, args=("trocar_senha",))
    st.markdown('</div>', unsafe_allow_html=True)

# === REGISTRO INTELIGENTE ===
elif st.session_state["pagina_atual"] == "registro":
    st.button("⬅ Voltar", on_click=navegar_para, args=("dashboard",))
    st.header("📝 Registrar Treino")
    
    if IS_MUSCULACAO:
        st.info("Confirme a realização do seu treino de força.")
        with st.form("reg_musc"):
