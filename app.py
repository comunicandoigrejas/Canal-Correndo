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
        margin-bottom: 20px;
        color: #856404 !important;
    }

    /* --- CORREÇÃO DE TABELA (DEFINITIVA - AJUSTE USUÁRIO) --- */
    
    /* Coluna 1 (Data): Força largura mínima de 15px */
    [data-testid="stTable"] th:nth-child(1), [data-testid="stTable"] td:nth-child(1) {
        min-width: 15px !important;
        white-space: nowrap !important;
    }
    
    /* Coluna 2 (Tipo): Força largura mínima de 30px */
    [data-testid="stTable"] th:nth-child(2), [data-testid="stTable"] td:nth-child(2) {
        min-width: 30px !important;
        white-space: nowrap !important; 
    }
    /* Coluna 3 (Detalhes): Força largura mínima de 130px */
    [data-testid="stTable"] th:nth-child(3), [data-testid="stTable"] td:nth-child(3) {
        min-width: 130px !important;
        white-space: nowrap !important; 
    }
    
    /* Alinha o texto da tabela no topo para facilitar a leitura */
    [data-testid="stTable"] td {
        vertical-align: top !important;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. GERENCIAMENTO DE SESSÃO ---

if "pagina_atual" not in st.session_state: st.session_state["pagina_atual"] = "login"
if "usuario_atual" not in st.session_state: st.session_state["usuario_atual"] = None
if "is_admin" not in st.session_state: st.session_state["is_admin"] = False
if "modalidade" not in st.session_state: st.session_state["modalidade"] = "Corrida" 
if "messages" not in st.session_state: st.session_state["messages"] = []

def navegar_para(pagina): st.session_state["pagina_atual"] = pagina

def logout():
    st.session_state["usuario_atual"] = None
    st.session_state["pagina_atual"] = "login"
    st.session_state["messages"] = []

# --- 3. CONEXÃO E LÓGICA ---

def conectar_gsheets():
    try:
        if "gcp_service_account" not in st.secrets: st.warning("Segredos off."); return None
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gcp_service_account"]), scope)
        return gspread.authorize(creds).open("Running_Data")
    except Exception as e: st.error(f"Erro: {e}"); return None

def verificar_login(usuario, senha):
    """Retorna: Nome, Funcao, Modalidade"""
    ss = conectar_gsheets()
    if ss:
        try:
            ws = ss.worksheet("Usuarios")
            for u in ws.get_all_records():
                if str(u['Usuario']) == usuario and str(u['Senha']) == senha:
                    if str(u.get('Status', 'Ativo')) == 'Bloqueado': return "BLOQUEADO", None, None
                    # Pega Modalidade (padrao Corrida se vazio)
                    modalidade = u.get('Modalidade', 'Corrida')
                    if modalidade == "": modalidade = "Corrida"
                    return u['Nome'], u.get('Funcao', 'aluno'), modalidade
            return None, None, None
        except: return None, None, None
    return None, None, None

def carregar_mensagens_usuario(user_id):
    ss = conectar_gsheets(); msgs = []
    if ss:
        try:
            ws = ss.worksheet("Mensagens")
            for row in reversed(ws.get_all_records()):
                if row['Destinatario'] in ['TODOS', user_id]:
                    msgs.append(row)
                    if len(msgs) >= 3: break
        except: pass
    return msgs

def carregar_contexto_ia():
    try:
        with open("treino_contexto.md", "r", encoding="utf-8") as f: return f.read()
    except: return "Sem contexto."

# --- 4. LOGIN ---

if st.session_state["usuario_atual"] is None:
    st.title("🏃 Running Coach")
    with st.form("login"):
        u = st.text_input("Usuário")
        s = st.text_input("Senha", type="password")
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
NOME = st.session_state["nome
