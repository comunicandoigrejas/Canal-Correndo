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

    .stButton > button {
        width: 100%;
        height: 80px;
        font-size: 20px;
        border-radius: 12px;
        margin-bottom: 10px;
    }
    
    /* Botão de Admin diferenciado */
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
    
    /* Estilo do Aviso/Mensagem */
    .message-card {
        background-color: #fff3cd;
        padding: 15px;
        border-radius: 10px;
        border-left: 5px solid #ffc107;
        margin-bottom: 20px;
        color: #856404 !important;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. GERENCIAMENTO DE SESSÃO ---

if "pagina_atual" not in st.session_state:
    st.session_state["pagina_atual"] = "login"
if "usuario_atual" not in st.session_state:
    st.session_state["usuario_atual"] = None
if "is_admin" not in st.session_state:
    st.session_state["is_admin"] = False
if "messages" not in st.session_state:
    st.session_state["messages"] = []

def navegar_para(pagina):
    st.session_state["pagina_atual"] = pagina

def logout():
    st.session_state["usuario_atual"] = None
    st.session_state["is_admin"] = False
    st.session_state["pagina_atual"] = "login"
    st.session_state["messages"] = []

# --- 3. CONEXÃO E LÓGICA DE DADOS ---

def conectar_gsheets():
    try:
        if "gcp_service_account" not in st.secrets:
            st.warning("Segredos não configurados.")
            return None
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client.open("Running_Data")
    except Exception as e:
        st.error(f"Erro de conexão: {e}")
        return None

def verificar_login(usuario, senha):
    """Verifica credenciais, status e função na aba 'Usuarios'"""
    ss = conectar_gsheets()
    if ss:
        try:
            ws = ss.worksheet("Usuarios")
            todos = ws.get_all_records()
            for u in todos:
                if str(u['Usuario']) == usuario and str(u['Senha']) == senha:
                    # Verifica se está bloqueado
                    if str(u.get('Status', 'Ativo')) == 'Bloqueado':
                        return "BLOQUEADO", None
                    
                    # Retorna Nome e Função (admin/aluno)
                    return u['Nome'], u.get('Funcao', 'aluno')
            return None, None
        except:
            st.error("Erro na aba 'Usuarios'. Verifique as colunas.")
            return None, None
    return None, None

def carregar_mensagens_usuario(user_id):
    """Busca mensagens para o usuário logado ou TODOS"""
    ss = conectar_gsheets()
    msgs_para_exibir = []
    if ss:
        try:
            ws = ss.worksheet("Mensagens")
            records = ws.get_all_records()
            # Pega as últimas mensagens (inverte a lista)
            for row in reversed(records):
                if row['Destinatario'] == 'TODOS' or row['Destinatario'] == user_id:
                    msgs_para_exibir.append(row)
                    if len(msgs_para_exibir) >= 3: break # Mostra só as 3 últimas
        except: pass
    return msgs_para_exibir

def carregar_contexto_ia():
    try:
        with open("treino_contexto.md", "r", encoding="utf-8") as f:
            return f.read()
    except: return "Contexto não encontrado."

# --- 4. TELA DE LOGIN ---

if st.session_state["usuario_atual"] is None:
    st.title("🏃 Running Coach - Acesso")
    with st.form("login"):
        u = st.text_input("Usuário")
        s = st.text_input("Senha", type="password")
        if st.form_submit_button("Entrar"):
            nome, funcao = verificar_login(u, s)
            if nome == "BLOQUEADO":
                st.error("🚫 Acesso negado. Contate o treinador.")
            elif nome:
                st.session_state["usuario_atual"] = u
                st.session_state["nome_usuario"] = nome
                st.session_state["is_admin"] = (funcao == 'admin')
                st.session_state["pagina_atual"] = "dashboard"
                st.rerun()
            else:
                st.error("Dados incorretos.")
    st.stop()

# --- 5. APLICAÇÃO ---

USER_ID = st.session_state["usuario_atual"]
NOME_USER = st.session_state["nome_usuario"]
IS_ADMIN = st.session_state["is_admin"]

# === DASHBOARD ===
if st.session_state["pagina_atual"] == "dashboard":
    c1, c2 = st.columns([3, 1])
    c1.title(f"Olá, {NOME_USER}!")
    if c2.button("Sair"): logout(); st.rerun()

    # 1. MURAL DE AVISOS (NOVO)
    mensagens = carregar_mensagens_usuario(USER_ID)
    if mensagens:
        for msg in mensagens:
            st.markdown(f"""
            <div class="message-card">
                <strong>🔔 {msg['Tipo'] or 'Aviso'}:</strong> {msg['Mensagem']} <br>
                <small>Em: {msg['Data']}</small>
            </div>
            """, unsafe_allow_html=True)

    # 2. TREINO DO DIA
    treino_hoje = None
    ss = conectar_gsheets()
    if ss:
        try:
            ws = ss.worksheet("Agenda")
            recs = ws.get_all_records()
            hoje = date.today().strftime("%d/%m/%Y") # Ajuste se precisar de fuso
            for r in recs:
                if str(r['ID_Usuario']) == USER_ID and str(r['Data']) == hoje:
                    treino_hoje = r
                    break
        except: pass
    
    st.subheader("📅 Treino de Hoje")
    if treino_hoje:
        st.markdown(f"""
        <div class="highlight-card">
            <h3>{treino_hoje['Tipo']}</h3>
            <p>{treino_hoje['Detalhes']}</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.info("Descanso hoje! 💤")

    st.markdown("---")
    
    # 3. MENU
    c1, c2, c3 = st.columns(3)
    with c1:
        st.button("📝 Registrar", on_click=navegar_para, args=("registro",))
        st.button("📅 Agenda", on_click=navegar_para, args=("agenda",))
    with c2:
        st.button("📊 Histórico", on_click=navegar_para, args=("historico",))
        st.button("🤖 IA Coach", on_click=navegar_para, args=("ia_coach",))
    with c3:
        st.button("🏅 Provas", on_click=navegar_para, args=("provas",))
        # BOTÃO EXCLUSIVO DE ADMIN
        if IS_ADMIN:
             # Usando markdown para injetar classe CSS especifica se possível, ou apenas botão
             st.markdown('<div class="admin-btn">', unsafe_allow_html=True)
             st.button("⚙️ PAINEL\nADMIN", on_click=navegar_para, args=("admin_panel",))
             st.markdown('</div>', unsafe_allow_html=True)

# === PAINEL ADMIN (NOVO) ===
elif st.session_state["pagina_atual"] == "admin_panel":
    if not IS_ADMIN: navegar_para("dashboard"); st.rerun()
    
    st.button("⬅ Voltar ao App", on_click=navegar_para, args=("dashboard",))
    st.title("⚙️ Painel do Treinador")
    st.markdown("---")

    tab1, tab2, tab3 = st.tabs(["🏋️ Atribuir Treinos", "👥 Gerenciar Alunos", "📢 Enviar Mensagem"])

    # ABA 1: ATRIBUIR TREINOS PARA OUTROS
    with tab1:
        st.subheader("Cadastrar Treino para Aluno")
        ss = conectar_gsheets()
        if ss:
            ws_users = ss.worksheet("Usuarios")
            lista_users = [row['Usuario'] for row in ws_users.get_all_records()]
            
            with st.form("admin_add_treino"):
                aluno_alvo = st.selectbox("Selecione o Aluno", lista_users)
                dt = st.date_input("Data do Treino")
                tp = st.selectbox("Tipo", ["Rodagem", "Tiro", "Longo", "Regenerativo", "Descanso"])
                det = st.text_area("Detalhes do Treino")
                
                if st.form_submit_button("Agendar Treino"):
                    ws_agenda = ss.worksheet("Agenda")
                    ws_agenda.append_row([aluno_alvo, dt.strftime("%d/%m/%Y"), tp, det])
                    st.success(f"Treino agendado para {aluno_alvo}!")

    # ABA 2: GERENCIAR ALUNOS (BLOQUEAR)
    with tab2:
        st.subheader("Controle de Acesso")
        if ss:
            ws_users = ss.worksheet("Usuarios")
            df_users = pd.DataFrame(ws_users.get_all_records())
            
            # Edição visual
            st.dataframe(df_users)
            
            st.write("### Alterar Status")
            with st.form("edit_user"):
                u_sel = st.selectbox("Aluno", df_users['Usuario'].tolist())
                novo_status = st.selectbox("Novo Status", ["Ativo", "Bloqueado"])
                
                if st.form_submit_button("Atualizar Status"):
                    cell = ws_users.find(u_sel)
                    if cell:
                        # Coluna 5 é Status
                        ws_users.update_cell(cell.row, 5, novo_status)
                        st.success(f"Status de {u_sel} alterado para {novo_status}!")
                        time.sleep(1)
                        st.rerun()

    # ABA 3: ENVIAR MENSAGENS
    with tab3:
        st.subheader("Mural de Avisos")
        if ss:
            ws_users = ss.worksheet("Usuarios")
            lista_users = ["TODOS"] + [row['Usuario'] for row in ws_users.get_all_records()]
            
            with st.form("msg_form"):
                dest = st.selectbox("Para quem?", lista_users)
                tipo = st.selectbox("Tipo", ["Aviso Geral", "Motivacional", "Cobrança", "Parabéns"])
                txt = st.text_area("Mensagem")
                
                if st.form_submit_button("Enviar Mensagem"):
                    ws_msg = ss.worksheet("Mensagens")
                    ws_msg.append_row([date.today().strftime("%d/%m/%Y"), dest, txt, tipo])
                    st.success("Mensagem enviada!")

# === OUTRAS PÁGINAS (REGISTRO, AGENDA, ETC - MANTIDAS IGUAIS) ===
elif st.session_state["pagina_atual"] == "registro":
    st.button("⬅ Voltar", on_click=navegar_para, args=("dashboard",))
    st.header("📝 Registrar")
    with st.form("reg"):
        d = st.date_input("Data", date.today())
        di = st.number_input("Km", 0.0, step=0.1)
        te = st.text_input("Tempo", "00:00:00")
        pe = st.slider("Cansaço", 0, 10, 5)
        ob = st.text_area("Obs")
        if st.form_submit_button("Salvar"):
            ss = conectar_gsheets()
            if ss: ss.worksheet("Registros").append_row([USER_ID, d.strftime("%d/%m/%Y"), di, te, pe, ob]); st.success("Salvo!")

if ss:
        # Pega todos os dados
        df = pd.DataFrame(ss.worksheet("Agenda").get_all_records())
        
        if not df.empty and 'ID_Usuario' in df.columns:
            # FILTRO: Mostra apenas dados deste usuário e remove a coluna ID
            df_user = df[df['ID_Usuario'] == USER_ID].drop(columns=['ID_Usuario'])
            
            if not df_user.empty:
                # --- CORREÇÃO AQUI ---
                # Usamos st.table ao invés de st.dataframe.
                # O st.table força a quebra de linha automática para caber todo o texto.
                st.table(df_user)
            else:
                st.info("Nenhum treino agendado.")
        else:
            st.info("Agenda vazia.")

elif st.session_state["pagina_atual"] == "historico":
    st.button("⬅ Voltar", on_click=navegar_para, args=("dashboard",))
    st.header("📊 Histórico")
    ss = conectar_gsheets()
    if ss:
        df = pd.DataFrame(ss.worksheet("Registros").get_all_records())
        if not df.empty and 'ID_Usuario' in df.columns:
            dfu = df[df['ID_Usuario'] == USER_ID]
            if not dfu.empty:
                st.dataframe(dfu.drop(columns=['ID_Usuario']), use_container_width=True)
                if "Distancia" in dfu.columns:
                     dfu["Distancia"] = pd.to_numeric(dfu["Distancia"].astype(str).str.replace(',','.'), errors='coerce')
                     st.line_chart(dfu, x="Data", y="Distancia")

elif st.session_state["pagina_atual"] == "provas":
    st.button("⬅ Voltar", on_click=navegar_para, args=("dashboard",))
    st.header("🏅 Provas")
    ss = conectar_gsheets()
    if ss:
        df = pd.DataFrame(ss.worksheet("Provas").get_all_records())
        if not df.empty and 'ID_Usuario' in df.columns:
            dfu = df[df['ID_Usuario'] == USER_ID]
            st.dataframe(dfu.drop(columns=['ID_Usuario']), use_container_width=True)
            
            with st.form("np"):
                dt = st.date_input("Data"); nm = st.text_input("Nome"); ds = st.selectbox("Dist", ["5k","10k","21k","42k"])
                if st.form_submit_button("Agendar"): ss.worksheet("Provas").append_row([USER_ID, dt.strftime("%d/%m/%Y"), nm, ds, "Pendente", "-"]); st.rerun()

elif st.session_state["pagina_atual"] == "ia_coach":
    st.button("⬅ Voltar", on_click=navegar_para, args=("dashboard",))
    st.header("🤖 Coach IA")
    if "openai_key" in st.secrets:
        client = OpenAI(api_key=st.secrets["openai_key"])
        if not st.session_state["messages"]:
            ctx = carregar_contexto_ia()
            st.session_state["messages"].append({"role": "system", "content": f"Aluno: {NOME_USER}. Contexto: {ctx}"})
        for m in st.session_state.messages: 
            if m["role"] != "system": st.chat_message(m["role"]).write(m["content"])
        if p := st.chat_input("?"):
            st.session_state.messages.append({"role": "user", "content": p}); st.chat_message("user").write(p)
            try:
                r = client.chat.completions.create(model="gpt-4o", messages=st.session_state.messages)
                st.session_state.messages.append({"role": "assistant", "content": r.choices[0].message.content})
                st.chat_message("assistant").write(r.choices[0].message.content)
            except Exception as e: st.error(e)
