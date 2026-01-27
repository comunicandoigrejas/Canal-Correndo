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
</style>
""", unsafe_allow_html=True)

# --- 2. FUNÇÕES DE CONEXÃO E DADOS ---

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
        # Abre a planilha principal
        return client.open("Running_Data")
    except Exception as e:
        st.error(f"Erro ao conectar no Google Sheets: {e}")
        return None

def carregar_agenda_hoje():
    """Busca na aba 'Agenda' do Google Sheets se há treino para hoje"""
    try:
        spreadsheet = conectar_gsheets()
        if spreadsheet:
            # Tenta acessar a aba específica 'Agenda'
            try:
                worksheet = spreadsheet.worksheet("Agenda")
            except:
                st.warning("Aba 'Agenda' não encontrada na planilha. Crie uma aba com colunas: Data, Tipo, Detalhes.")
                return None

            treinos = worksheet.get_all_records()
            # Formato brasileiro para comparação: DD/MM/AAAA
            hoje_str = date.today().strftime("%d/%m/%Y") 
            
            for treino in treinos:
                # Converte a data da planilha para string para comparar
                if str(treino['Data']) == hoje_str:
                    return treino
            return None
    except Exception as e:
        st.error(f"Erro ao ler agenda: {e}")
        return None

def carregar_contexto_ia():
    """Lê o arquivo de texto com os treinos"""
    try:
        with open("treino_contexto.md", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "Aviso: Arquivo 'treino_contexto.md' não encontrado. A IA está sem contexto."

# --- 3. FUNÇÕES DE UTILIDADE ---

def verificar_senha():
    SENHA_ACESSO = "run2026" 
    if st.session_state["password_input"] == SENHA_ACESSO:
        st.session_state["autenticado"] = True
    else:
        st.error("Senha incorreta!")

def navegar_para(pagina):
    st.session_state["pagina_atual"] = pagina

def voltar_home():
    st.session_state["pagina_atual"] = "dashboard"

# --- 4. INICIALIZAÇÃO DO ESTADO ---

if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

if "pagina_atual" not in st.session_state:
    st.session_state["pagina_atual"] = "dashboard"

if "messages" not in st.session_state:
    st.session_state["messages"] = []

# --- 5. TELA DE LOGIN ---
if not st.session_state["autenticado"]:
    st.title("🔒 Acesso Restrito")
    st.text_input("Digite a senha de acesso:", type="password", key="password_input", on_change=verificar_senha)
    st.stop() 

# --- 6. LÓGICA DE NAVEGAÇÃO ---

# === PÁGINA: DASHBOARD (HOME) ===
if st.session_state["pagina_atual"] == "dashboard":
    st.title("🏃 Running Coach AI")

    # Busca treino real
    with st.spinner("Sincronizando agenda..."):
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
        st.info("Nenhum treino agendado para hoje (verifique a aba 'Agenda' ou a data). Bom descanso! 💤")

    st.markdown("---")
    
    # Menu Grid
    col1, col2, col3 = st.columns(3) # <--- Mudei para 3 colunas para caber tudo
    
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
    with col3:
        # NOVO BOTÃO AQUI
        if st.button("➕ Cadastrar\nNovos Treinos"):
            navegar_para("cadastro_agenda")

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
            spreadsheet = conectar_gsheets()
            if spreadsheet:
                try:
                    # Usa a primeira aba (padrão) para salvar registros
                    sheet = spreadsheet.sheet1
                    
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
    
    spreadsheet = conectar_gsheets()
    if spreadsheet:
        try:
            worksheet = spreadsheet.worksheet("Agenda")
            dados = worksheet.get_all_records()
            if dados:
                df = pd.DataFrame(dados)
                st.dataframe(df, use_container_width=True)
            else:
                st.info("A agenda está vazia.")
        except:
            st.error("Aba 'Agenda' não encontrada.")

# === PÁGINA: HISTÓRICO ===
elif st.session_state["pagina_atual"] == "historico":
    st.button("⬅ Voltar", on_click=voltar_home)
    st.header("📊 Histórico de Execução")
    
    spreadsheet = conectar_gsheets()
    if spreadsheet:
        try:
            # Pega dados da aba de registros (sheet1)
            sheet = spreadsheet.sheet1
            dados = sheet.get_all_records()
            if dados:
                df = pd.DataFrame(dados)
                st.dataframe(df, use_container_width=True)
                
                # Exemplo simples de gráfico se tiver a coluna Distancia
                if "Distancia" in df.columns:
                     # Limpeza básica para garantir que é número
                     # df["Distancia"] = pd.to_numeric(df["Distancia"], errors='coerce')
                     st.line_chart(df, x="Data", y="Distancia")
            else:
                st.info("Nenhum registro encontrado ainda.")
        except Exception as e:
            st.error(f"Erro ao carregar histórico: {e}")

# === PÁGINA: IA COACH ===
elif st.session_state["pagina_atual"] == "ia_coach":
    st.button("⬅ Voltar", on_click=voltar_home)
    st.header("🤖 Treinador IA")
    
    if "openai_key" in st.secrets:
        client = OpenAI(api_key=st.secrets["openai_key"])
        
        # Inicializa Chat com Contexto
        if not st.session_state["messages"]:
            contexto = carregar_contexto_ia()
            # Adiciona prompt do sistema (invisível ao usuário)
            st.session_state["messages"].append({
                "role": "system", 
                "content": f"Você é um treinador de corrida experiente e motivador. O contexto técnico do aluno é: {contexto}. Responda de forma curta."
            })

        # Exibe mensagens
        for msg in st.session_state.messages:
            if msg["role"] != "system":
                st.chat_message(msg["role"]).write(msg["content"])

        # Input
        if prompt := st.chat_input("Dúvida sobre o treino?"):
            st.session_state.messages.append({"role": "user", "content": prompt})
            st.chat_message("user").write(prompt)

            try:
                response = client.chat.completions.create(
                    model="gpt-4o", 
                    messages=st.session_state.messages
                )
                msg_resposta = response.choices[0].message.content
                
                st.session_state.messages.append({"role": "assistant", "content": msg_resposta})
                st.chat_message("assistant").write(msg_resposta)
            except Exception as e:
                st.error(f"Erro na API OpenAI: {e}")
    else:
        st.warning("⚠️ Chave da OpenAI não encontrada. Adicione 'openai_key' ao secrets.toml.")
