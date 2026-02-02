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
NOME = st.session_state["nome_usuario"]
ADMIN = st.session_state["is_admin"]
MODALIDADE = st.session_state["modalidade"] 

# === DASHBOARD ===
if st.session_state["pagina_atual"] == "dashboard":
    c1, c2 = st.columns([3, 1])
    c1.title(f"Olá, {NOME}!")
    if c2.button("Sair"): logout(); st.rerun()

    # Avisos
    for m in carregar_mensagens_usuario(USER):
        st.markdown(f"<div class='message-card'><strong>🔔 {m['Tipo']}:</strong> {m['Mensagem']}</div>", unsafe_allow_html=True)

    # Treino Hoje
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

    st.markdown("---")
    
    # MENU INTELIGENTE
    c1, c2, c3 = st.columns(3)
    with c1:
        st.button("📝 Registrar", on_click=navegar_para, args=("registro",))
        st.button("📅 Agenda", on_click=navegar_para, args=("agenda",))
    with c2:
        st.button("📊 Histórico", on_click=navegar_para, args=("historico",))
        st.button("🤖 IA Coach", on_click=navegar_para, args=("ia_coach",))
    with c3:
        if MODALIDADE == "Corrida":
            st.button("🏅 Provas", on_click=navegar_para, args=("provas",))
        
        if ADMIN:
             st.markdown('<div class="admin-btn">', unsafe_allow_html=True)
             st.button("⚙️ ADMIN", on_click=navegar_para, args=("admin_panel",))
             st.markdown('</div>', unsafe_allow_html=True)

# === REGISTRO INTELIGENTE ===
elif st.session_state["pagina_atual"] == "registro":
    st.button("⬅ Voltar", on_click=navegar_para, args=("dashboard",))
    st.header("📝 Registrar Treino")
    
    # SE FOR MUSCULAÇÃO
    if MODALIDADE == "Musculacao":
        st.info("Confirme a realização do seu treino de hoje.")
        with st.form("reg_musc"):
            dt = st.date_input("Data", date.today())
            obs = st.text_area("Observações (Cargas, sensações, etc)")
            
            if st.form_submit_button("✅ CONFIRMAR TREINO REALIZADO"):
                ss = conectar_gsheets()
                if ss:
                    ss.worksheet("Registros").append_row([USER, dt.strftime("%d/%m/%Y"), 0, "00:00", 5, obs])
                    st.success("Treino de Musculação Registrado!")
                    time.sleep(1.5); navegar_para("dashboard"); st.rerun()

    # SE FOR CORRIDA
    else:
        with st.form("reg_run"):
            d = st.date_input("Data", date.today())
            di = st.number_input("Km", 0.0, step=0.1)
            te = st.text_input("Tempo", "00:00:00")
            pe = st.slider("Cansaço", 0, 10, 5)
            ob = st.text_area("Obs")
            if st.form_submit_button("Salvar Corrida"):
                ss = conectar_gsheets()
                if ss: 
                    ss.worksheet("Registros").append_row([USER, d.strftime("%d/%m/%Y"), di, te, pe, ob])
                    st.success("Corrida Salva!")
                    time.sleep(1.5); navegar_para("dashboard"); st.rerun()

# === OUTRAS TELAS ===
elif st.session_state["pagina_atual"] == "admin_panel":
    if not ADMIN: navegar_para("dashboard"); st.rerun()
    st.button("⬅ Voltar", on_click=navegar_para, args=("dashboard",))
    st.title("⚙️ Painel Admin")
    t1, t2, t3 = st.tabs(["Treinos", "Alunos", "Mensagem"])
    with t1:
        with st.form("at"):
            ss = conectar_gsheets()
            l = [r['Usuario'] for r in ss.worksheet("Usuarios").get_all_records()] if ss else []
            u = st.selectbox("Aluno", l); dt = st.date_input("Data"); tp = st.text_input("Tipo/Treino"); det = st.text_area("Detalhes")
            if st.form_submit_button("Agendar"): ss.worksheet("Agenda").append_row([u, dt.strftime("%d/%m/%Y"), tp, det]); st.success("Feito!")
    with t2:
        if ss:
            ws = ss.worksheet("Usuarios"); df = pd.DataFrame(ws.get_all_records())
            st.dataframe(df)
            with st.form("sts"):
                us = st.selectbox("Aluno", df['Usuario'].tolist()); ns = st.selectbox("Status", ["Ativo", "Bloqueado"])
                if st.form_submit_button("Atualizar"): 
                    c = ws.find(us); ws.update_cell(c.row, 5, ns); st.success("Atualizado!"); st.rerun()
    with t3:
        with st.form("msg"):
            us = st.text_input("Destinatario (Login ou TODOS)"); tx = st.text_area("Msg"); tp = st.selectbox("Tipo", ["Aviso", "Motivacional"])
            if st.form_submit_button("Enviar"): ss.worksheet("Mensagens").append_row([date.today().strftime("%d/%m/%Y"), us, tx, tp]); st.success("Enviado!")

elif st.session_state["pagina_atual"] == "agenda":
    st.button("⬅ Voltar", on_click=navegar_para, args=("dashboard",))
    st.header("📅 Agenda")
    ss = conectar_gsheets()
    if ss:
        df = pd.DataFrame(ss.worksheet("Agenda").get_all_records())
        if not df.empty and 'ID_Usuario' in df.columns:
            dfu = df[df['ID_Usuario'] == USER].drop(columns=['ID_Usuario'])
            if not dfu.empty: st.table(dfu)
            else: st.info("Sem treinos.")

elif st.session_state["pagina_atual"] == "historico":
    st.button("⬅ Voltar", on_click=navegar_para, args=("dashboard",))
    st.header("📊 Histórico")
    ss = conectar_gsheets()
    if ss:
        df = pd.DataFrame(ss.worksheet("Registros").get_all_records())
        if not df.empty and 'ID_Usuario' in df.columns:
            dfu = df[df['ID_Usuario'] == USER].drop(columns=['ID_Usuario'])
            st.dataframe(dfu, use_container_width=True)
            if MODALIDADE == "Corrida" and "Distancia" in dfu.columns:
                dfu["Distancia"] = pd.to_numeric(dfu["Distancia"].astype(str).str.replace(',','.'), errors='coerce')
                st.line_chart(dfu, x="Data", y="Distancia")

elif st.session_state["pagina_atual"] == "provas":
    st.button("⬅ Voltar", on_click=navegar_para, args=("dashboard",))
    st.header("🏅 Provas")
    ss = conectar_gsheets()
    if ss:
        df = pd.DataFrame(ss.worksheet("Provas").get_all_records())
        if not df.empty and 'ID_Usuario' in df.columns:
            st.dataframe(df[df['ID_Usuario'] == USER].drop(columns=['ID_Usuario']), use_container_width=True)
            with st.form("p"):
                d = st.date_input("Data"); n = st.text_input("Nome"); di = st.selectbox("km", ["5k","10k","21k"]); 
                if st.form_submit_button("Add"): ss.worksheet("Provas").append_row([USER, d.strftime("%d/%m/%Y"), n, di, "Pendente", "-"]); st.rerun()

elif st.session_state["pagina_atual"] == "ia_coach":
    st.button("⬅ Voltar", on_click=navegar_para, args=("dashboard",))
    st.header("🤖 Coach IA")
    if "openai_key" in st.secrets:
        client = OpenAI(api_key=st.secrets["openai_key"])
        if not st.session_state["messages"]:
            ctx = carregar_contexto_ia()
            st.session_state["messages"].append({"role": "system", "content": f"Aluno: {NOME} ({MODALIDADE}). Contexto: {ctx}"})
        for m in st.session_state.messages: 
            if m["role"] != "system": st.chat_message(m["role"]).write(m["content"])
        if p := st.chat_input("?"):
            st.session_state.messages.append({"role": "user", "content": p}); st.chat_message("user").write(p)
            try:
                r = client.chat.completions.create(model="gpt-4o", messages=st.session_state.messages)
                st.session_state.messages.append({"role": "assistant", "content": r.choices[0].message.content})
                st.chat_message("assistant").write(r.choices[0].message.content)
            except Exception as e: st.error(e)
