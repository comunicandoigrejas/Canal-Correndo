import streamlit as st
import datetime
from datetime import date
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- CONFIGURAÇÃO INICIAL ---
st.set_page_config(page_title="Running Coach", page_icon="🏃", layout="centered")

# ... (Mantenha o seu CSS de botões aqui) ...

# --- CONEXÃO COM GOOGLE SHEETS ---
def conectar_gsheets():
    """Conecta ao Google Sheets usando os segredos do Streamlit"""
    try:
        # Cria o objeto de credenciais usando os segredos do Streamlit
        # Nota: No Streamlit Cloud, você colará o JSON na área de secrets
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        
        # Transforma o objeto de secrets do Streamlit em credenciais
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        
        client = gspread.authorize(creds)
        
        # Abre a planilha pelo nome (Tem que ser EXATAMENTE o nome que você deu no Google)
        sheet = client.open("Running_Data").sheet1 
        return sheet
    except Exception as e:
        st.error(f"Erro ao conectar no Google Sheets: {e}")
        return None

# ... (Mantenha suas funções de senha e navegação aqui) ...

# --- PÁGINA: REGISTRAR TREINO ---
if st.session_state["pagina_atual"] == "registro":
    st.button("⬅ Voltar", on_click=voltar_home)
    st.header("📝 Registrar Execução")
    
    with st.form("form_registro"):
        # Inputs
        data_realizada = st.date_input("Data", date.today())
        distancia = st.number_input("Distância (km)", min_value=0.0, step=0.1, format="%.2f")
        
        # Input de tempo (formato texto ou time object)
        tempo_input = st.text_input("Tempo Total (ex: 00:45:00)", value="00:00:00")
        
        percepcao = st.slider("Cansaço (0=Leve, 10=Exausto)", 0, 10, 5)
        obs = st.text_area("Sensações / Observações")
        
        submitted = st.form_submit_button("Salvar Registro")
        
        if submitted:
            sheet = conectar_gsheets()
            if sheet:
                try:
                    # Prepara a linha para salvar
                    # Convertendo data para string BR
                    data_str = data_realizada.strftime("%d/%m/%Y")
                    
                    nova_linha = [data_str, distancia, tempo_input, percepcao, obs]
                    
                    # Adiciona a linha na planilha
                    sheet.append_row(nova_linha)
                    
                    st.success("✅ Treino salvo com sucesso na nuvem!")
                    st.balloons() # Um efeito visual de comemoração
                except Exception as e:
                    st.error(f"Erro ao gravar dados: {e}")

# ... (Restante do código das outras páginas) ...
