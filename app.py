import streamlit as st
import datetime
from datetime import date
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from openai import OpenAI  # <--- NOVA IMPORTAÇÃO NECESSÁRIA

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
</style>
""", unsafe_allow_html=True)

# --- 2. FUNÇÕES AUXILIARES ---

def conectar_gsheets():
    """Conecta ao Google Sheets usando os segredos do Streamlit"""
    try:
        if "gcp_service_account" not in st.secrets:
            st.warning("Segredos do Google não encontrados.")
            return None

        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        sheet = client.open("Running_Data").sheet1 
        return sheet
    except Exception as e:
        st.error(f"Erro ao conectar no Google Sheets: {e}")
        return None

def carregar_contexto_ia():
    """Lê o arquivo de texto com os treinos (NOVA FUNÇÃO)"""
    try:
        with open("treino_contexto.md", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "Erro: Arquivo 'treino_contexto.md' não encontrado na pasta do projeto."

def verificar_senha():
    """Função de callback para verificar senha"""
    SENHA_ACESSO = "run2026" 
    if st.session_state["password_input"] == SENHA_ACESSO:
        st.session_state["autenticado"] = True
    else:
        st.error("Senha incorreta!")

def navegar_para(pagina):
    st.session_state["pagina_atual"] = pagina

def voltar_home():
    st.session_state["pagina_atual"] = "dashboard"

# --- 3. INICIALIZAÇÃO DO ESTADO ---

if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

if "pagina_atual" not in st.session_state:
    st.session_state["pagina_atual"] = "dashboard"

# Inicializa o histórico do chat se não existir
if "messages" not in st.session_state:
    st.session_state["messages"] = []

# --- 4. TELA DE LOGIN ---
if not st.session_state["autenticado"]:
    st.title("🔒 Acesso Restrito")
    st.text_input("Digite a senha de acesso:", type="password", key="password_input", on_change=verificar_senha)
    st.stop() 

# --- 5. LÓGICA DE NAVEGAÇÃO ---

# === PÁGINA: DASHBOARD (HOME) ===
if st.session_state["pagina_atual"] == "dashboard":
    st.title("🏃 Running Coach AI")

    # MOCK DATA (Isso aqui você pode conectar com o Google Sheets depois se quiser)
    AGENDA_TREINOS = {
        "2026-01-26": {"tipo": "Tiro", "detalhes": "10 min aquecimento + 8x 400m forte (p: 1:30) + 10 min desaquecimento"},
        "2026-01-27": {"tipo": "Rodagem", "detalhes": "8km leve Z2"},
        "2026-01-28": {"tipo": "Descanso", "detalhes": "Off total ou alongamento"}
    }
    
    hoje = date.today().strftime("%Y-%m-%d")
    treino_hoje = AGENDA_TREINOS.get(hoje)
    
    st.subheader("📅 Status do Dia")
    
    if treino_hoje:
        st.markdown(f"""
        <div class="highlight-card">
            <h3>Hoje é dia de: {treino_hoje['tipo']}</h3>
            <p>{treino_hoje['detalhes']}</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.info("Hoje não há treino programado na agenda base. Bom descanso! 💤")

    st.markdown("---")
    
    # Menu Grid
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📝 Registrar\nTreino"):
            navegar_para("registro")
        if st.button("📅 Agenda\nFutura"):
            navegar_para("agenda")     
    with col2:
        if st.button("📊 Histórico\nResultados"):
            navegar_para("historico")
        if st.button("🤖 Adaptar\nTreino (IA)"):
            navegar_para("ia_coach")

# === PÁGINA: REGISTRAR TREINO ===
elif st.session_state["pagina_atual"] == "registro":
    st.button("⬅ Voltar", on_click=voltar_home)
    st.header("📝 Registrar Execução")
    
    with st.form("form_registro"):
        data_realizada = st.date_input("Data", date.today())
        distancia = st.number_input("Distância (km)", min_value=0.0, step=0.1, format="%.2f")
        tempo_input = st.text_input("Tempo Total (ex: 00:45:00)", value="00:00:00")
        percepcao = st.slider("Cansaço (0=Leve, 10=Exausto)", 0, 10, 5)
        obs = st.text_area("Sensações / Observações")
        
        submitted = st.form_submit_button("Salvar Registro")
        
        if submitted:
            sheet = conectar_gsheets()
            if sheet:
                try:
                    data_str = data_realizada.strftime("%d/%m/%Y")
                    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    nova_linha = [data_str, distancia, tempo_input, percepcao, obs, timestamp]
                    sheet.append_row(nova_linha)
                    st.success("✅ Treino salvo com sucesso na nuvem!")
                    st.balloons()
                except Exception as e:
                    st.error(f"Erro ao gravar dados: {e}")
            else:
                st.error("Não foi possível conectar à planilha.")

# === PÁGINA: AGENDA ===
elif st.session_state["pagina_atual"] == "agenda":
    st.button("⬅ Voltar", on_click=voltar_home)
    st.header("📅 Próximos Treinos")
    st.info("Aqui você pode implementar um calendário visual ou lista dos próximos treinos.")
    # Exemplo: st.table(AGENDA_TREINOS)

# === PÁGINA: HISTÓRICO ===
elif st.session_state["pagina_atual"] == "historico":
    st.button("⬅ Voltar", on_click=voltar_home)
    st.header("📊 Histórico")
    st.info("Aqui você pode puxar os dados do Google Sheets e criar gráficos com st.line_chart().")

# === PÁGINA: IA COACH (ATUALIZADA) ===
elif st.session_state["pagina_atual"] == "ia_coach":
    st.button("⬅ Voltar", on_click=voltar_home)
    st.header("🤖 Treinador IA")
    
    # Verifica chave da OpenAI
    if "openai_key" in st.secrets:
        client = OpenAI(api_key=st.secrets["openai_key"])
        
        # Se o histórico estiver vazio, carrega o contexto do arquivo .md
        if not st.session_state["messages"]:
            contexto = carregar_contexto_ia()
            st.session_state["messages"].append({
                "role": "system", 
                "content": f"Você é um treinador de corrida experiente. O contexto do aluno é: {contexto}. Responda de forma curta e direta."
            })

        # Exibe mensagens antigas
        for msg in st.session_state.messages:
            if msg["role"] != "system":
                st.chat_message(msg["role"]).write(msg["content"])

        # Input do Usuário
        if prompt := st.chat_input("Dúvida sobre o treino?"):
            st.session_state.messages.append({"role": "user", "content": prompt})
            st.chat_message("user").write(prompt)

            try:
                # Chamada API
                response = client.chat.completions.create(
                    model="gpt-4o", 
                    messages=st.session_state.messages
                )
                msg_resposta = response.choices[0].message.content
                
                st.session_state.messages.append({"role": "assistant", "content": msg_resposta})
                st.chat_message("assistant").write(msg_resposta)
            except Exception as e:
                st.error(f"Erro na comunicação com a IA: {e}")
    else:
        st.warning("⚠️ Chave da OpenAI não encontrada. Adicione 'openai_key' ao secrets.toml.")
