import streamlit as st
import datetime
from datetime import date
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from openai import OpenAI
import pandas as pd

# --- 1. CONFIGURAÇÃO E CSS ---
st.set_page_config(page_title="Running Coach", page_icon="🏃", layout="centered")

st.markdown("""
<style>
    .stButton > button {
        width: 100%;
        height: 80px;
        font-size: 20px;
        border-radius: 12px;
        margin-bottom: 10px;
    }
    .highlight-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #ff4b4b;
        margin-bottom: 20px;
    }
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

# --- 2. GERENCIAMENTO DE ESTADO E NAVEGAÇÃO (A SOLUÇÃO DO CLIQUE ÚNICO) ---

if "pagina_atual" not in st.session_state:
    st.session_state["pagina_atual"] = "dashboard"
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False
if "messages" not in st.session_state:
    st.session_state["messages"] = []

def navegar_para(pagina):
    """Callback para navegação instantânea"""
    st.session_state["pagina_atual"] = pagina

def voltar_home():
    """Callback para voltar"""
    st.session_state["pagina_atual"] = "dashboard"

# --- 3. CONEXÃO COM GOOGLE SHEETS ---

def conectar_gsheets():
    try:
        if "gcp_service_account" not in st.secrets:
            st.warning("Segredos do Google não encontrados.")
            return None
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client.open("Running_Data")
    except Exception as e:
        st.error(f"Erro de conexão: {e}")
        return None

def carregar_agenda_hoje():
    try:
        spreadsheet = conectar_gsheets()
        if spreadsheet:
            try:
                worksheet = spreadsheet.worksheet("Agenda")
            except:
                return None
            treinos = worksheet.get_all_records()
            hoje_str = date.today().strftime("%d/%m/%Y")
            for treino in treinos:
                if str(treino['Data']) == hoje_str:
                    return treino
            return None
    except:
        return None

def carregar_contexto_ia():
    try:
        with open("treino_contexto.md", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "Aviso: Arquivo de contexto não encontrado."

# --- 4. TELA DE LOGIN ---
def verificar_senha():
    SENHA_ACESSO = "run2026" 
    if st.session_state["password_input"] == SENHA_ACESSO:
        st.session_state["autenticado"] = True
    else:
        st.error("Senha incorreta!")

if not st.session_state["autenticado"]:
    st.title("🔒 Acesso Restrito")
    st.text_input("Digite a senha:", type="password", key="password_input", on_change=verificar_senha)
    st.stop() 

# --- 5. ROTEAMENTO DE PÁGINAS ---

# === DASHBOARD ===
if st.session_state["pagina_atual"] == "dashboard":
    st.title("🏃 Running Coach AI")

    with st.spinner("Sincronizando..."):
        treino_hoje = carregar_agenda_hoje()
    
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
    
    # MENU GRID COM CALLBACKS (ISSO RESOLVE O PROBLEMA DOS 2 CLIQUES)
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.button("📝 Registrar\nTreino", on_click=navegar_para, args=("registro",))
        st.button("📅 Agenda\nFutura", on_click=navegar_para, args=("agenda",))
    with col2:
        st.button("📊 Histórico\nResultados", on_click=navegar_para, args=("historico",))
        st.button("🤖 Adaptar\nTreino (IA)", on_click=navegar_para, args=("ia_coach",))
    with col3:
        st.button("➕ Cadastrar\nTreinos", on_click=navegar_para, args=("cadastro_agenda",))
        # NOVO BOTÃO DE PROVAS
        st.button("🏅 Provas\n& Metas", on_click=navegar_para, args=("provas",))

# === PÁGINA: PROVAS (NOVA) ===
elif st.session_state["pagina_atual"] == "provas":
    st.button("⬅ Voltar", on_click=voltar_home)
    st.header("🏅 Calendário de Provas")

    spreadsheet = conectar_gsheets()
    if spreadsheet:
        try:
            worksheet = spreadsheet.worksheet("Provas")
            dados = worksheet.get_all_records()
            
            # --- SEÇÃO 1: VISUALIZAR PROVAS ---
            if dados:
                df = pd.DataFrame(dados)
                # Formatação visual do status
                def color_status(val):
                    color = 'green' if val == 'Concluída' else 'orange'
                    return f'color: {color}; font-weight: bold'
                
                st.dataframe(df.style.applymap(color_status, subset=['Status']), use_container_width=True)
            else:
                st.info("Nenhuma prova cadastrada.")
                df = pd.DataFrame()

            st.markdown("---")
            
            tab_add, tab_update = st.tabs(["➕ Nova Prova", "✏️ Atualizar Resultado"])

            # --- ABA 1: CADASTRAR NOVA PROVA ---
            with tab_add:
                with st.form("nova_prova"):
                    c1, c2 = st.columns(2)
                    data_prova = c1.date_input("Data da Prova")
                    nome_prova = c2.text_input("Nome da Prova")
                    distancia_prova = c1.selectbox("Distância", ["5km", "10km", "15km", "21km", "42km", "Outra"])
                    submit_prova = st.form_submit_button("Agendar Prova")
                    
                    if submit_prova:
                        data_fmt = data_prova.strftime("%d/%m/%Y")
                        # Ordem: Data, Nome, Distancia, Status, Tempo
                        worksheet.append_row([data_fmt, nome_prova, distancia_prova, "Pendente", "-"])
                        st.success("Prova agendada!")
                        st.rerun() # Atualiza a tabela na hora

            # --- ABA 2: ATUALIZAR RESULTADO ---
            with tab_update:
                if not df.empty:
                    # Cria uma lista de provas pendentes para selecionar
                    provas_nomes = df['Nome'].tolist()
                    prova_selecionada = st.selectbox("Selecione a Prova", provas_nomes)
                    
                    c1, c2 = st.columns(2)
                    foi_realizada = c1.checkbox("✅ Prova Realizada?")
                    tempo_realizado = c2.text_input("Tempo Oficial (ex: 01:55:00)")
                    
                    if st.button("Salvar Resultado"):
                        # Lógica para encontrar a linha e atualizar
                        cell = worksheet.find(prova_selecionada)
                        if cell:
                            linha = cell.row
                            # Atualiza colunas D (Status) e E (Tempo)
                            status = "Concluída" if foi_realizada else "Pendente"
                            worksheet.update_cell(linha, 4, status) # Coluna 4
                            worksheet.update_cell(linha, 5, tempo_realizado) # Coluna 5
                            st.success("Resultado atualizado!")
                            st.rerun()
                else:
                    st.warning("Cadastre uma prova primeiro.")

        except Exception as e:
            st.error(f"Aba 'Provas' não encontrada ou erro de conexão: {e}. Crie a aba na planilha com cabeçalho: Data, Nome, Distancia, Status, Tempo")

# === PÁGINA: REGISTRAR TREINO ===
elif st.session_state["pagina_atual"] == "registro":
    st.button("⬅ Voltar", on_click=voltar_home)
    st.header("📝 Registrar Execução")
    
    with st.form("form_registro"):
        data_realizada = st.date_input("Data", date.today())
        distancia = st.number_input("Distância (km)", min_value=0.0, step=0.1, format="%.2f")
        tempo_input = st.text_input("Tempo Total (ex: 00:45:00)", value="00:00:00")
        percepcao = st.slider("Cansaço (0=Leve, 10=Exausto)", 0, 10, 5)
        obs = st.text_area("Sensações")
        if st.form_submit_button("Salvar Registro"):
            ss = conectar_gsheets()
            if ss:
                ss.sheet1.append_row([data_realizada.strftime("%d/%m/%Y"), distancia, tempo_input, percepcao, obs, str(datetime.datetime.now())])
                st.success("Salvo!")

# === PÁGINA: AGENDA ===
elif st.session_state["pagina_atual"] == "agenda":
    st.button("⬅ Voltar", on_click=voltar_home)
    st.header("📅 Agenda Futura")
    ss = conectar_gsheets()
    if ss:
        try:
            df = pd.DataFrame(ss.worksheet("Agenda").get_all_records())
            st.dataframe(df, use_container_width=True)
        except: st.error("Erro ao ler Agenda.")

# === PÁGINA: CADASTRO DE TREINOS ===
elif st.session_state["pagina_atual"] == "cadastro_agenda":
    st.button("⬅ Voltar", on_click=voltar_home)
    st.header("📅 Alimentar Agenda")
    tab1, tab2 = st.tabs(["Manual", "Upload"])
    
    with tab1:
        with st.form("manual"):
            dt = st.date_input("Data")
            tp = st.selectbox("Tipo", ["Rodagem", "Tiro", "Longo", "Descanso"])
            det = st.text_area("Detalhes")
            if st.form_submit_button("Salvar"):
                ss = conectar_gsheets()
                if ss:
                    ss.worksheet("Agenda").append_row([dt.strftime("%d/%m/%Y"), tp, det])
                    st.success("Adicionado!")
    
    with tab2:
        up = st.file_uploader("Arquivo CSV/Excel", type=['csv','xlsx'])
        if up and st.button("Importar"):
            df = pd.read_csv(up) if up.name.endswith('.csv') else pd.read_excel(up)
            ss = conectar_gsheets()
            if ss:
                ws = ss.worksheet("Agenda")
                for _, row in df.iterrows():
                    ws.append_row([str(row['Data']), row['Tipo'], row['Detalhes']])
                st.success("Importado!")

# === PÁGINA: HISTÓRICO ===
elif st.session_state["pagina_atual"] == "historico":
    st.button("⬅ Voltar", on_click=voltar_home)
    st.header("📊 Histórico")
    ss = conectar_gsheets()
    if ss:
        df = pd.DataFrame(ss.sheet1.get_all_records())
        if not df.empty:
            st.dataframe(df)
            if "Distancia" in df.columns:
                # Tratamento simples para garantir números no gráfico
                df["Distancia"] = pd.to_numeric(df["Distancia"].astype(str).str.replace(',','.'), errors='coerce')
                st.line_chart(df, x="Data", y="Distancia")

# === PÁGINA: IA COACH ===
elif st.session_state["pagina_atual"] == "ia_coach":
    st.button("⬅ Voltar", on_click=voltar_home)
    st.header("🤖 Treinador IA")
    if "openai_key" in st.secrets:
        client = OpenAI(api_key=st.secrets["openai_key"])
        if not st.session_state["messages"]:
            ctx = carregar_contexto_ia()
            st.session_state["messages"].append({"role": "system", "content": f"Treinador de corrida. Contexto: {ctx}"})
        
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
