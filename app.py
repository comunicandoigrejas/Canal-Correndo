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
    /* Oculta barra superior e rodapé */
    header {visibility: hidden;}
    footer {visibility: hidden;}
    .block-container {padding-top: 2rem;}

    /* Estilos Globais dos Botões */
    .stButton > button {
        width: 100%;
        height: 80px;
        font-size: 20px;
        border-radius: 12px;
        margin-bottom: 10px;
    }

    /* --- CORREÇÃO DE COR AQUI --- */
    /* Estilo do Card de Destaque */
    .highlight-card {
        background-color: #f0f2f6; /* Fundo Cinza Claro */
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #ff4b4b;
        margin-bottom: 20px;
        
        /* Força a cor do texto para cinza escuro, para não sumir no modo escuro */
        color: #31333F !important; 
    }
    
    /* Força também os títulos e parágrafos dentro do card a serem escuros */
    .highlight-card h3, .highlight-card p, .highlight-card strong {
        color: #31333F !important;
    }
    
    /* Estilos de Status (Tabela) */
    .status-done {
        color: green;
        font-weight: bold;
    }
    .status-pending {
        color: orange;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. GERENCIAMENTO DE SESSÃO ---

if "pagina_atual" not in st.session_state:
    st.session_state["pagina_atual"] = "login" # Começa no login
if "usuario_atual" not in st.session_state:
    st.session_state["usuario_atual"] = None
if "messages" not in st.session_state:
    st.session_state["messages"] = []

def navegar_para(pagina):
    st.session_state["pagina_atual"] = pagina

def logout():
    st.session_state["usuario_atual"] = None
    st.session_state["pagina_atual"] = "login"
    st.session_state["messages"] = []

# --- 3. CONEXÃO E SEGURANÇA ---

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
    """Verifica usuário e senha na aba 'Usuarios'"""
    ss = conectar_gsheets()
    if ss:
        try:
            ws = ss.worksheet("Usuarios")
            todos_usuarios = ws.get_all_records()
            for u in todos_usuarios:
                # Converte para string para evitar erro de tipo
                if str(u['Usuario']) == usuario and str(u['Senha']) == senha:
                    return u['Nome'] # Retorna o nome se achar
            return None
        except:
            st.error("Aba 'Usuarios' não encontrada na planilha.")
            return None
    return None

def carregar_contexto_ia():
    try:
        with open("treino_contexto.md", "r", encoding="utf-8") as f:
            return f.read()
    except: return "Contexto não encontrado."

# --- 4. TELA DE LOGIN (NOVA) ---

if st.session_state["usuario_atual"] is None:
    st.title("🏃 Running Coach - Acesso")
    
    with st.form("login_form"):
        user_input = st.text_input("Usuário")
        pass_input = st.text_input("Senha", type="password")
        submit_login = st.form_submit_button("Entrar")
        
        if submit_login:
            nome_usuario = verificar_login(user_input, pass_input)
            if nome_usuario:
                st.session_state["usuario_atual"] = user_input
                st.session_state["nome_usuario"] = nome_usuario
                st.session_state["pagina_atual"] = "dashboard"
                st.success(f"Bem-vindo, {nome_usuario}!")
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")
    st.stop() # Para o código aqui se não estiver logado

# --- 5. LÓGICA DO APLICATIVO (SÓ CARREGA SE LOGADO) ---

# Atalho para o ID do usuário logado
USER_ID = st.session_state["usuario_atual"]

# === DASHBOARD ===
if st.session_state["pagina_atual"] == "dashboard":
    # Cabeçalho com Logout
    c1, c2 = st.columns([3, 1])
    c1.title(f"Olá, {st.session_state['nome_usuario']}!")
    if c2.button("Sair"): logout(); st.rerun()

    # Busca Treino do Dia (Filtrado pelo Usuário)
    treino_hoje = None
    ss = conectar_gsheets()
    if ss:
        try:
            ws = ss.worksheet("Agenda")
            records = ws.get_all_records()
            hoje_str = date.today().strftime("%d/%m/%Y")
            
            for row in records:
                # Filtra: Só mostra se for do usuário logado E for hoje
                if str(row['ID_Usuario']) == USER_ID and str(row['Data']) == hoje_str:
                    treino_hoje = row
                    break
        except: pass
    
    st.subheader("📅 Status do Dia")
    if treino_hoje:
        st.markdown(f"""
        <div class="highlight-card">
            <h3>Hoje é dia de: {treino_hoje['Tipo']}</h3>
            <p><strong>Treino:</strong> {treino_hoje['Detalhes']}</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.info("Nenhum treino agendado para hoje. Descanso! 💤")

    st.markdown("---")
    
    # Menu Grid
    col1, col2, col3 = st.columns(3)
    with col1:
        st.button("📝 Registrar\nTreino", on_click=navegar_para, args=("registro",))
        st.button("📅 Agenda\nFutura", on_click=navegar_para, args=("agenda",))
    with col2:
        st.button("📊 Histórico\nResultados", on_click=navegar_para, args=("historico",))
        st.button("🤖 Adaptar\nTreino (IA)", on_click=navegar_para, args=("ia_coach",))
    with col3:
        st.button("➕ Cadastrar\nTreinos", on_click=navegar_para, args=("cadastro_agenda",))
        st.button("🏅 Provas\n& Metas", on_click=navegar_para, args=("provas",))

# === REGISTRO (SALVA COM ID_USUARIO) ===
elif st.session_state["pagina_atual"] == "registro":
    st.button("⬅ Voltar", on_click=navegar_para, args=("dashboard",))
    st.header("📝 Registrar Execução")
    
    with st.form("form_reg"):
        d_data = st.date_input("Data", date.today())
        d_dist = st.number_input("Distância (km)", 0.0, step=0.1)
        d_tempo = st.text_input("Tempo (00:00:00)", "00:00:00")
        d_perc = st.slider("Percepção", 0, 10, 5)
        d_obs = st.text_area("Obs")
        
        if st.form_submit_button("Salvar"):
            ss = conectar_gsheets()
            if ss:
                try:
                    # Agora a primeira coluna é o USER_ID
                    ss.worksheet("Registros").append_row([
                        USER_ID, 
                        d_data.strftime("%d/%m/%Y"), 
                        d_dist, d_tempo, d_perc, d_obs
                    ])
                    st.success("Salvo!")
                except Exception as e: st.error(f"Erro: {e}")

# === AGENDA (FILTRA POR USER_ID) ===
elif st.session_state["pagina_atual"] == "agenda":
    st.button("⬅ Voltar", on_click=navegar_para, args=("dashboard",))
    st.header("📅 Sua Agenda")
    
    ss = conectar_gsheets()
    if ss:
        df = pd.DataFrame(ss.worksheet("Agenda").get_all_records())
        if not df.empty and 'ID_Usuario' in df.columns:
            # FILTRO: Mostra apenas dados deste usuário
            df_user = df[df['ID_Usuario'] == USER_ID].drop(columns=['ID_Usuario'])
            st.dataframe(df_user, use_container_width=True)
        else:
            st.info("Agenda vazia.")

# === HISTÓRICO (FILTRA POR USER_ID) ===
elif st.session_state["pagina_atual"] == "historico":
    st.button("⬅ Voltar", on_click=navegar_para, args=("dashboard",))
    st.header("📊 Seu Histórico")
    
    ss = conectar_gsheets()
    if ss:
        df = pd.DataFrame(ss.worksheet("Registros").get_all_records())
        if not df.empty and 'ID_Usuario' in df.columns:
            # FILTRO
            df_user = df[df['ID_Usuario'] == USER_ID].copy()
            
            if not df_user.empty:
                st.dataframe(df_user.drop(columns=['ID_Usuario']), use_container_width=True)
                
                if "Distancia" in df_user.columns:
                    df_user["Distancia"] = pd.to_numeric(
                        df_user["Distancia"].astype(str).str.replace(',','.'), errors='coerce'
                    )
                    st.line_chart(df_user, x="Data", y="Distancia")
            else:
                st.info("Nenhum registro seu encontrado.")

# === PROVAS (FILTRA E SALVA COM ID) ===
elif st.session_state["pagina_atual"] == "provas":
    st.button("⬅ Voltar", on_click=navegar_para, args=("dashboard",))
    st.header("🏅 Suas Provas")
    
    ss = conectar_gsheets()
    if ss:
        ws = ss.worksheet("Provas")
        df = pd.DataFrame(ws.get_all_records())
        
        # Filtra dataframe para mostrar só o usuário
        if not df.empty and 'ID_Usuario' in df.columns:
            df_user = df[df['ID_Usuario'] == USER_ID]
        else:
            df_user = pd.DataFrame()

        # Mostra Tabela
        if not df_user.empty:
            view_df = df_user.drop(columns=['ID_Usuario']) # Esconde o ID na visualização
            def color(val): return f'color: {"green" if val=="Concluída" else "orange"}'
            st.dataframe(view_df.style.applymap(color, subset=['Status']), use_container_width=True)
        
        t1, t2 = st.tabs(["Nova Prova", "Atualizar"])
        
        with t1:
            with st.form("new_race"):
                dt = st.date_input("Data")
                nm = st.text_input("Nome")
                ds = st.selectbox("Dist", ["5km", "10km", "21km", "42km"])
                if st.form_submit_button("Agendar"):
                    # Salva com ID na coluna A
                    ws.append_row([USER_ID, dt.strftime("%d/%m/%Y"), nm, ds, "Pendente", "-"])
                    st.success("Agendado!")
                    st.rerun()

        with t2:
            if not df_user.empty:
                # O usuário só pode selecionar provas DELE
                meus_nomes = df_user['Nome'].tolist()
                sel = st.selectbox("Prova", meus_nomes)
                
                c1, c2 = st.columns(2)
                check = c1.checkbox("Concluída?")
                tempo = c2.text_input("Tempo")
                
                if st.button("Salvar Resultado"):
                    # Busca manual segura: acha a linha que tem o ID E o Nome
                    all_vals = ws.get_all_values()
                    for idx, row in enumerate(all_vals):
                        # row[0] é ID, row[2] é Nome (ajustado para indices da lista)
                        if row[0] == USER_ID and row[2] == sel:
                            # +1 porque planilhas começam no 1
                            ws.update_cell(idx+1, 5, "Concluída" if check else "Pendente")
                            ws.update_cell(idx+1, 6, tempo)
                            st.success("Atualizado!")
                            time.sleep(1)
                            st.rerun()
                            break

# === CADASTRO AGENDA (NOVA) ===
elif st.session_state["pagina_atual"] == "cadastro_agenda":
    st.button("⬅ Voltar", on_click=navegar_para, args=("dashboard",))
    st.header("📅 Alimentar Agenda")
    
    t1, t2 = st.tabs(["Manual", "Upload"])
    with t1:
        with st.form("agenda_man"):
            dt = st.date_input("Data")
            tp = st.selectbox("Tipo", ["Rodagem", "Tiro", "Longo"])
            det = st.text_area("Detalhes")
            if st.form_submit_button("Salvar"):
                ss = conectar_gsheets()
                if ss:
                    ss.worksheet("Agenda").append_row([
                        USER_ID, dt.strftime("%d/%m/%Y"), tp, det
                    ])
                    st.success("Feito!")
    
    with t2:
        up = st.file_uploader("Arquivo", type=['csv','xlsx'])
        if up and st.button("Importar"):
            df_up = pd.read_csv(up) if up.name.endswith('.csv') else pd.read_excel(up)
            ss = conectar_gsheets()
            if ss:
                ws = ss.worksheet("Agenda")
                for _, row in df_up.iterrows():
                    # Adiciona ID_Usuario em cada linha importada
                    ws.append_row([USER_ID, str(row['Data']), row['Tipo'], row['Detalhes']])
                st.success("Importado!")

# === IA COACH ===
elif st.session_state["pagina_atual"] == "ia_coach":
    st.button("⬅ Voltar", on_click=navegar_para, args=("dashboard",))
    st.header("🤖 Coach IA")
    
    if "openai_key" in st.secrets:
        client = OpenAI(api_key=st.secrets["openai_key"])
        if not st.session_state["messages"]:
            ctx = carregar_contexto_ia()
            # Informa a IA quem é o usuário
            st.session_state["messages"].append({
                "role": "system", 
                "content": f"Aluno: {st.session_state['nome_usuario']}. Contexto: {ctx}"
            })
        
        for m in st.session_state.messages:
            if m["role"] != "system": st.chat_message(m["role"]).write(m["content"])
            
        if p := st.chat_input("Dúvida?"):
            st.session_state.messages.append({"role": "user", "content": p})
            st.chat_message("user").write(p)
            try:
                r = client.chat.completions.create(model="gpt-4o", messages=st.session_state.messages)
                st.session_state.messages.append({"role": "assistant", "content": r.choices[0].message.content})
                st.chat_message("assistant").write(r.choices[0].message.content)
            except Exception as e: st.error(e)
