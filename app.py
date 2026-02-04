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

# --- 3. CONEXÃO E LÓGICA (COM CACHE) ---

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
