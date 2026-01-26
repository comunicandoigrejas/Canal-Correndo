import streamlit as st
import datetime
import pandas as pd
from datetime import date

# --- 1. CONFIGURAÇÃO E CSS (Para visual mobile) ---
st.set_page_config(page_title="Running Coach", page_icon="🏃", layout="centered")

# CSS para simular botões grandes estilo "App Mobile"
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

# --- 2. DADOS MOCKADOS (Simulando seu JSON de treino) ---
# Na versão final, isso virá do seu arquivo .json ou .md
AGENDA_TREINOS = {
    "2026-01-26": {"tipo": "Tiro", "detalhes": "10 min aquecimento + 8x 400m forte (p: 1:30) + 10 min desaquecimento"},
    "2026-01-27": {"tipo": "Rodagem", "detalhes": "8km leve Z2"},
    "2026-01-28": {"tipo": "Descanso", "detalhes": "Off total ou alongamento"}
}

# Senha definida (idealmente usar st.secrets)
SENHA_ACESSO = "run2026"

# --- 3. FUNÇÕES AUXILIARES ---

def verificar_senha():
    """Função de callback para verificar senha"""
    if st.session_state["password_input"] == SENHA_ACESSO:
        st.session_state["autenticado"] = True
    else:
        st.error("Senha incorreta!")

def navegar_para(pagina):
    st.session_state["pagina_atual"] = pagina

def voltar_home():
    st.session_state["pagina_atual"] = "dashboard"

# --- 4. CONTROLE DE ESTADO (SESSION STATE) ---
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False
if "pagina_atual" not in st.session_state:
    st.session_state["pagina_atual"] = "dashboard"

# --- 5. TELA DE LOGIN ---
if not st.session_state["autenticado"]:
    st.title("🔒 Acesso Restrito")
    st.text_input("Digite a senha de acesso:", type="password", key="password_input", on_change=verificar_senha)
    st.stop() # Para a execução aqui até logar

# --- 6. TELA PRINCIPAL (DASHBOARD) ---
if st.session_state["pagina_atual"] == "dashboard":
    st.title("🏃 Running Coach AI")

    # === Lógica: Mostrar Treino de Hoje ou Próximo ===
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
        # Lógica simples para achar o próximo (pode ser aprimorada)
        st.info("Hoje não há treino programado. Bom descanso! 💤")
        st.caption("Próximo treino: Verifique a agenda.")

    st.markdown("---")
    
    # === Botões de Navegação (Menu Grid) ===
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

# --- 7. SUB-PÁGINAS ---

# Página: Registrar Treino
elif st.session_state["pagina_atual"] == "registro":
    st.button("⬅ Voltar", on_click=voltar_home)
    st.header("📝 Registrar Execução")
    
    with st.form("form_registro"):
        data_realizada = st.date_input("Data", date.today())
        distancia = st.number_input("Distância (km)", min_value=0.0, step=0.1)
        tempo = st.time_input("Tempo Total", value=datetime.time(0, 30))
        percepcao = st.slider("Cansaço (0=Leve, 10=Exausto)", 0, 10, 5)
        obs = st.text_area("Sensações / Observações")
        
        submitted = st.form_submit_button("Salvar Registro")
        if submitted:
            # AQUI ENTRARÁ A LÓGICA DE SALVAR (Google Sheets ou CSV)
            st.success("Treino registrado! (Simulação)")

# Página: IA Coach (Adaptação)
elif st.session_state["pagina_atual"] == "ia_coach":
    st.button("⬅ Voltar", on_click=voltar_home)
    st.header("🤖 Adaptar Treino")
    st.info("Converse com sua IA para ajustar o treino de hoje caso esteja cansado ou lesionado.")
    
    # Exemplo de chat simples
    user_input = st.chat_input("Ex: Estou com dor no joelho, o que faço?")
    if user_input:
        st.chat_message("user").write(user_input)
        st.chat_message("assistant").write("Entendido. Dado seu histórico, sugiro trocar o tiro por 30min de elíptico.")

# Página: Agenda
elif st.session_state["pagina_atual"] == "agenda":
    st.button("⬅ Voltar", on_click=voltar_home)
    st.header("📅 Próximos Treinos")
    st.json(AGENDA_TREINOS) # Exibição simples por enquanto

# Página: Histórico
elif st.session_state["pagina_atual"] == "historico":
    st.button("⬅ Voltar", on_click=voltar_home)
    st.header("📊 Histórico")
    st.write("Gráficos de evolução virão aqui.")
