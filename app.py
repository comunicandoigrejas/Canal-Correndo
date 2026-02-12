import streamlit as st
import datetime
from datetime import date, timedelta, timezone
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from openai import OpenAI
import pandas as pd
import time
import requests # Necessário para o Telegram

# --- 1. CONFIGURAÇÃO E CSS ---
st.set_page_config(page_title="Running Coach", page_icon="🏃", layout="centered")

st.markdown("""
<style>
    header {visibility: hidden;}
    footer {visibility: hidden;}
    .block-container {padding-top: 2rem;}
    .stButton > button {
        width: 100%; height: 80px; font-size: 20px; border-radius: 12px; margin-bottom: 10px;
    }
    .admin-btn > button { background-color: #31333F; color: white; border: 2px solid #ff4b4b; }
    .small-btn > button { height: 50px !important; background-color: transparent; border: 1px solid #ccc; color: #31333F; }
    .close-btn > button {
        height: 40px !important; min-height: 40px !important; width: 100% !important;
        background-color: transparent !important; border: 1px solid #ff4b4b !important;
        color: #ff4b4b !important; font-size: 16px !important; font-weight: bold !important;
    }
    .close-btn > button:hover { background-color: #ff4b4b !important; color: white !important; }
    .highlight-card {
        background-color: #f0f2f6; padding: 20px; border-radius: 10px;
        border-left: 5px solid #ff4b4b; margin-bottom: 20px; color: #31333F !important;
    }
    .highlight-card h3, .highlight-card p, .highlight-card strong { color: #31333F !important; }
    .message-card {
        background-color: #fff3cd; padding: 15px; border-radius: 10px;
        border-left: 5px solid #ffc107; margin-bottom: 5px; color: #856404 !important; height: 100%;
    }
    .success-card {
        background-color: #d4edda; padding: 15px; border-radius: 10px;
        border-left: 5px solid #28a745; margin-bottom: 20px; color: #155724 !important;
        text-align: center; font-weight: bold; font-size: 18px;
    }
    [data-testid="stTable"] th:nth-child(1), [data-testid="stTable"] td:nth-child(1) { min-width: 15px !important; white-space: nowrap !important; }
    [data-testid="stTable"] th:nth-child(2), [data-testid="stTable"] td:nth-child(2) { min-width: 30px !important; white-space: nowrap !important; }
    [data-testid="stTable"] td { vertical-align: top !important; }
</style>
""", unsafe_allow_html=True)

# --- 2. CONFIGURAÇÃO DE FUSO HORÁRIO (BRASÍLIA) ---
FUSO_BR = timezone(timedelta(hours=-3))

def data_hoje_br():
    """Retorna a data atual no Brasil"""
    return datetime.datetime.now(FUSO_BR).date()

def data_hora_br():
    """Retorna data e hora atuais no Brasil"""
    return datetime.datetime.now(FUSO_BR)

# --- 3. GERENCIAMENTO DE SESSÃO ---

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

# --- 4. CONEXÃO E LÓGICA (COM NOTIFICAÇÃO) ---

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
    except Exception as e: 
        st.error(f"Conexão instável. Aguarde... ({e})")
        time.sleep(2)
        st.cache_resource.clear()
        return None

def safe_get_records(worksheet_name):
    ss = conectar_gsheets()
    if not ss: return []
    try:
        ws = ss.worksheet(worksheet_name)
        return ws.get_all_records()
    except Exception:
        return []

def verificar_login(usuario, senha):
    records = safe_get_records("Usuarios")
    for u in records:
        try:
            u_planilha = str(u.get('Usuario', '')).strip()
            s_planilha = str(u.get('Senha', '')).strip()
            if u_planilha == usuario and s_planilha == senha:
                if str(u.get('Status', 'Ativo')) == 'Bloqueado': return "BLOQUEADO", None, None
                modalidade_raw = str(u.get('Modalidade', 'Corrida')).strip()
                return u.get('Nome', 'Aluno'), u.get('Funcao', 'aluno'), modalidade_raw
        except: continue
    return None, None, None

def carregar_mensagens_usuario(user_id):
    records = safe_get_records("Mensagens")
    msgs = []
    for row in reversed(records):
        dest = str(row.get('Destinatario', 'TODOS')).strip()
        if dest in ['TODOS', user_id]:
            msgs.append(row)
            if len(msgs) >= 3: break
    return msgs

def excluir_aviso(msg_data):
    ss = conectar_gsheets()
    if ss:
        try:
            ws = ss.worksheet("Mensagens")
            data = ws.get_all_records()
            for i, row in enumerate(data):
                if (str(row.get('Data')) == str(msg_data.get('Data')) and
                    str(row.get('Destinatario')) == str(msg_data.get('Destinatario')) and
                    str(row.get('Mensagem')) == str(msg_data.get('Mensagem'))):
                    ws.delete_rows(i + 2)
                    return True
        except: pass
    return False

def notificar_telegram(mensagem):
    """Envia notificação para o Treinador"""
    token = st.secrets.get("telegram_token")
    chat_id = st.secrets.get("telegram_chat_id")
    
    if not token or not chat_id:
        return # Silencioso se não tiver configurado

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": mensagem}
    try:
        requests.post(url, data=payload)
    except:
        pass

def carregar_contexto_ia():
    try:
        with open("treino_contexto.md", "r", encoding="utf-8") as f: return f.read()
    except: return "Sem contexto."

def calcular_pace_medio(tempo_str, distancia_km):
    try:
        tempo_str = tempo_str.strip()
        parts = list(map(int, tempo_str.split(':')))
        total_min = 0
        if len(parts) == 3: total_min = parts[0]*60 + parts[1] + parts[2]/60
        elif len(parts) == 2: total_min = parts[0] + parts[1]/60
        else: return None
        if distancia_km > 0:
            pace_dec = total_min / distancia_km
            pace_min = int(pace_dec)
            pace_sec = int((pace_dec - pace_min) * 60)
            return f"{pace_min:02d}:{pace_sec:02d}"
    except: return None
    return None

# --- 5. TELA DE LOGIN ---

if st.session_state["usuario_atual"] is None:
    st.title("🏃 Running Coach")
    with st.form("login"):
        u = st.text_input("Usuário").strip()
        s = st.text_input("Senha", type="password").strip()
        if st.form_submit_button("Entrar"):
            nome, funcao, modalidade = verificar_login(u, s)
            if nome == "BLOQUEADO": st.error("Acesso Bloqueado. Contate o treinador.")
            elif nome:
                st.session_state["usuario_atual"] = u
                st.session_state["nome_usuario"] = nome
                st.session_state["is_admin"] = (funcao == 'admin')
                st.session_state["modalidade"] = modalidade 
                st.session_state["pagina_atual"] = "dashboard"
                st.rerun()
            else: st.error("Dados incorretos.")
    st.stop()

# --- 6. APP PRINCIPAL ---

USER = st.session_state["usuario_atual"]
NOME = st.session_state["nome_usuario"]
ADMIN = st.session_state["is_admin"]
MODALIDADE = st.session_state["modalidade"]
IS_MUSCULACAO = "muscula" in str(MODALIDADE).lower()

# === DASHBOARD ===
if st.session_state["pagina_atual"] == "dashboard":
    c1, c2 = st.columns([3, 1])
    c1.title(f"Olá, {NOME}!")
    if c2.button("Sair"): logout(); st.rerun()

    # Avisos
    msgs = carregar_mensagens_usuario(USER)
    if msgs:
        st.subheader("🔔 Avisos")
        for i, m in enumerate(msgs):
            tp = m.get('Tipo', 'Aviso')
            msg = m.get('Mensagem', '')
            col_msg, col_x = st.columns([0.85, 0.15])
            with col_msg:
                st.markdown(f"<div class='message-card'><strong>{tp}:</strong> {msg}</div>", unsafe_allow_html=True)
            with col_x:
                st.markdown('<div class="close-btn">', unsafe_allow_html=True)
                if st.button("X", key=f"d{i}"):
                    if excluir_aviso(m):
                        st.success("Apagado!")
                        time.sleep(0.5); st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
        st.markdown("---")

    # Resposta Aluno (Com Notificação Telegram)
    with st.expander("💬 Falar com o Treinador"):
        with st.form("form_resp"):
            tx = st.text_area("Mensagem:")
            if st.form_submit_button("Enviar"):
                ss = conectar_gsheets()
                if ss:
                    try:
                        ss.worksheet("Mensagens").append_row([
                            data_hoje_br().strftime("%d/%m/%Y"), 
                            "ADMIN", 
                            tx, 
                            f"De: {NOME}"
                        ])
                        
                        # Notifica Admin
                        notificar_telegram(f"🔔 Nova mensagem de {NOME}:\n\n{tx}")
                        
                        st.success("Enviado!")
                    except: st.error("Erro ao enviar")
    
    # Treino de Hoje (Fuso BR)
    treino = None
    agenda_records = safe_get_records("Agenda")
    hoje = data_hoje_br().strftime("%d/%m/%Y")
    
    for r in agenda_records:
        r_data = str(r.get('Data')).strip()
        r_id = str(r.get('ID_Usuario')).strip()
        if r_id == USER and r_data == hoje:
            treino = r; break
    
    st.subheader("📅 Treino de Hoje")
    if treino:
        st.markdown(f"<div class='highlight-card'><h3>{treino.get('Tipo','Treino')}</h3><p>{treino.get('Detalhes','')}</p></div>", unsafe_allow_html=True)
    else: st.info("Descanso! 💤")

    # Verifica Treino Realizado
    reg_records = safe_get_records("Registros")
    treinou_hoje = False
    for reg in reg_records:
        reg_data = str(reg.get('Data')).strip()
        reg_id = str(reg.get('ID_Usuario')).strip()
        if reg_id == USER and reg_data == hoje:
            treinou_hoje = True; break
            
    if treinou_hoje:
        st.markdown(f"<div class='success-card'>🎉 Parabéns! Treino Realizado!</div>", unsafe_allow_html=True)

    st.markdown("---")
    
    c1, c2, c3 = st.columns(3)
    with c1:
        st.button("📝 Registrar", on_click=navegar_para, args=("registro",))
        st.button("📅 Agenda", on_click=navegar_para, args=("agenda",))
    with c2:
        st.button("📊 Histórico", on_click=navegar_para, args=("historico",))
        st.button("🤖 IA Coach", on_click=navegar_para, args=("ia_coach",))
    with c3:
        if not IS_MUSCULACAO:
            st.button("🏅 Provas", on_click=navegar_para, args=("provas",))
        if ADMIN:
             st.markdown('<div class="admin-btn">', unsafe_allow_html=True)
             st.button("⚙️ ADMIN", on_click=navegar_para, args=("admin_panel",))
             st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown('<div class="small-btn">', unsafe_allow_html=True)
    st.button("🔑 Alterar Senha", on_click=navegar_para, args=("trocar_senha",))
    st.markdown('</div>', unsafe_allow_html=True)

# === REGISTRO INTELIGENTE ===
elif st.session_state["pagina_atual"] == "registro":
    st.button("⬅ Voltar", on_click=navegar_para, args=("dashboard",))
    st.header("📝 Registrar Treino")
    
    if IS_MUSCULACAO:
        st.info("Confirme a realização do seu treino de força.")
        with st.form("reg_musc"):
            dt = st.date_input("Data", data_hoje_br())
            obs = st.text_area("Observações (Cargas, sensações, etc)")
            if st.form_submit_button("✅ CONFIRMAR TREINO REALIZADO"):
                ss = conectar_gsheets()
                if ss:
                    ss.worksheet("Registros").append_row([USER, dt.strftime("%d/%m/%Y"), 0, "00:00", 5, obs])
                    
                    # Notifica
                    notificar_telegram(f"💪 {NOME} registrou MUSCULAÇÃO!\nObs: {obs}")
                    
                    st.success("Registrado!")
                    time.sleep(1.5); navegar_para("dashboard"); st.rerun()
    else:
        with st.form("reg_run"):
            d = st.date_input("Data", data_hoje_br())
            di = st.number_input("Km", 0.0, step=0.1)
            te = st.text_input("Tempo Total", "00:00:00", help="HH:MM:SS")
            pe = st.slider("Cansaço", 0, 10, 5)
            ob = st.text_area("Obs")
            if st.form_submit_button("Salvar Corrida"):
                pace_calc = calcular_pace_medio(te, di)
                if pace_calc: ob = f"{ob} | Pace Médio: {pace_calc} min/km"
                ss = conectar_gsheets()
                if ss: 
                    ss.worksheet("Registros").append_row([USER, d.strftime("%d/%m/%Y"), di, te, pe, ob])
                    
                    # Notifica
                    notificar_telegram(f"🏃 {NOME} registrou CORRIDA!\nKm: {di}\nTempo: {te}\nObs: {ob}")
                    
                    st.success("Salvo!")
                    time.sleep(1.5); navegar_para("dashboard"); st.rerun()

# === HISTÓRICO ===
elif st.session_state["pagina_atual"] == "historico":
    st.button("⬅ Voltar", on_click=navegar_para, args=("dashboard",))
    st.header("📊 Histórico")
    all_records = safe_get_records("Registros")
    df = pd.DataFrame(all_records)
    
    if not df.empty and 'ID_Usuario' in df.columns:
        dfu = df[df['ID_Usuario'] == USER].drop(columns=['ID_Usuario'])
        if not dfu.empty:
            if IS_MUSCULACAO:
                st.metric("Total de Treinos", len(dfu))
                cols_view = [c for c in ["Data", "Observacoes"] if c in dfu.columns]
                st.dataframe(dfu[cols_view], use_container_width=True, hide_index=True)
            else:
                st.dataframe(dfu, use_container_width=True)
                if "Distancia" in dfu.columns:
                    dfu["Distancia"] = pd.to_numeric(dfu["Distancia"].astype(str).str.replace(',','.'), errors='coerce')
                    st.line_chart(dfu, x="Data", y="Distancia")
            
            st.markdown("---")
            with st.expander("🗑️ Excluir Treinos"):
                st.warning("A exclusão é permanente.")
                opts = []
                for i, reg in enumerate(all_records):
                    if str(reg.get('ID_Usuario')) == USER:
                        opts.append((i + 2, f"{reg.get('Data')} - {str(reg.get('Observacoes',''))[:20]}"))
                opts.reverse()
                if opts:
                    labels = [o[1] for o in opts]
                    ids = [o[0] for o in opts]
                    sel = st.selectbox("Apagar:", labels)
                    if st.button("Confirmar Exclusão"):
                        ss = conectar_gsheets()
                        if ss:
                            try:
                                ss.worksheet("Registros").delete_rows(ids[labels.index(sel)])
                                st.success("Apagado!"); time.sleep(1); st.rerun()
                            except: st.error("Erro")
                else: st.info("Nada para excluir.")
        else: st.info("Sem histórico.")
    else: st.info("Sem registros.")

# === ADMIN ===
elif st.session_state["pagina_atual"] == "admin_panel":
    if not ADMIN: navegar_para("dashboard"); st.rerun()
    st.button("⬅ Voltar", on_click=navegar_para, args=("dashboard",))
    st.title("⚙️ Painel Admin")
    
    ss = conectar_gsheets()
    t1, t2, t3, t4, t5 = st.tabs(["Treinos", "Alunos", "Mensagem", "🔎 Monitorar", "🤖 IA"])
    
    with t1:
        with st.form("at"):
            users = safe_get_records("Usuarios")
            l = [r['Usuario'] for r in users]
            # Agenda com Data Brasil
            u = st.selectbox("Aluno", l); dt = st.date_input("Data", data_hoje_br()); tp = st.text_input("Tipo"); det = st.text_area("Detalhes")
            if st.form_submit_button("Agendar"): 
                if ss: ss.worksheet("Agenda").append_row([u, dt.strftime("%d/%m/%Y"), tp, det]); st.success("Feito!")
    
    with t2:
        users = safe_get_records("Usuarios")
        df = pd.DataFrame(users)
        st.dataframe(df)
        with st.form("sts"):
            us = st.selectbox("Aluno", [u['Usuario'] for u in users] if users else []); ns = st.selectbox("Status", ["Ativo", "Bloqueado"])
            if st.form_submit_button("Atualizar"): 
                if ss: 
                    ws = ss.worksheet("Usuarios")
                    c = ws.find(us); ws.update_cell(c.row, 5, ns); st.success("Atualizado!"); st.rerun()
    
    with t3:
        st.subheader("📢 Enviar")
        users = safe_get_records("Usuarios")
        dest = ["TODOS"] + [u['Usuario'] for u in users]
        with st.form("msg"):
            us = st.selectbox("Para", dest); tx = st.text_area("Msg"); tp = st.selectbox("Tipo", ["Aviso Geral", "Motivacional", "Cobrança"])
            if st.form_submit_button("Enviar"): 
                if ss: ss.worksheet("Mensagens").append_row([data_hoje_br().strftime("%d/%m/%Y"), us, tx, tp]); st.success("Enviado!")
        
        st.subheader("📥 Recebidas")
        msgs = safe_get_records("Mensagens")
        inbox = [m for m in msgs if str(m.get('Destinatario')) == "ADMIN"]
        if inbox: st.dataframe(pd.DataFrame(inbox))
        else: st.info("Nenhuma msg.")

    with t4:
        st.subheader("Monitorar")
        users = safe_get_records("Usuarios")
        map_mod = {str(r['Usuario']): str(r.get('Modalidade', 'Corrida')) for r in users}
        sel = st.selectbox("Aluno:", list(map_mod.keys()) if map_mod else [])
        
        recs = safe_get_records("Registros")
        df_reg = pd.DataFrame(recs)
        if not df_reg.empty and 'ID_Usuario' in df_reg.columns:
            df_aluno = df_reg[df_reg['ID_Usuario'] == sel].drop(columns=['ID_Usuario'])
            if not df_aluno.empty:
                st.write(f"Histórico ({map_mod.get(sel, '')}):")
                st.dataframe(df_aluno, use_container_width=True)
            else: st.warning("Sem treinos.")
        else: st.info("Sem dados.")

    with t5:
        st.subheader("🤖 Assistente Expert (Chat)")
        ASSISTANT_ID = st.secrets.get("assistant_id")
        if not ASSISTANT_ID: st.warning("Configure assistant_id nos secrets.")
        elif ss:
            users = safe_get_records("Usuarios")
            map_mod = {str(r['Usuario']): str(r.get('Modalidade', 'Corrida')) for r in users}
            sel = st.selectbox("Contexto Aluno:", list(map_mod.keys()) if map_mod else [])
            
            if "openai_key" in st.secrets:
                client = OpenAI(api_key=st.secrets["openai_key"])
                if "thread_id" not in st.session_state:
                    th = client.beta.threads.create(); st.session_state["thread_id"] = th.id
                
                if st.button("Limpar Chat"):
                    th = client.beta.threads.create(); st.session_state["thread_id"] = th.id
                    st.session_state["messages_admin"] = []; st.rerun()

                for m in st.session_state.messages_admin:
                    with st.chat_message(m["role"]): st.write(m["content"])
                
                if p := st.chat_input("Mensagem para IA:"):
                    st.session_state.messages_admin.append({"role": "user", "content": p})
                    with st.chat_message("user"): st.write(p)
                    
                    full_p = f"Contexto: Aluno {sel} ({map_mod.get(sel)}). Msg: {p}"
                    try:
                        with st.spinner("IA pensando..."):
                            client.beta.threads.messages.create(thread_id=st.session_state["thread_id"], role="user", content=full_p)
                            run = client.beta.threads.runs.create(thread_id=st.session_state["thread_id"], assistant_id=ASSISTANT_ID)
                            while run.status in ['queued', 'in_progress', 'cancelling']:
                                time.sleep(1); run = client.beta.threads.runs.retrieve(thread_id=st.session_state["thread_id"], run_id=run.id)
                            
                            if run.status == 'completed':
                                msgs = client.beta.threads.messages.list(thread_id=st.session_state["thread_id"])
                                resp = msgs.data[0].content[0].text.value
                                st.session_state.messages_admin.append({"role": "assistant", "content": resp})
                                with st.chat_message("assistant"): st.write(resp)
                    except Exception as e: st.error(f"Erro: {e}")

# === AGENDA ===
elif st.session_state["pagina_atual"] == "agenda":
    st.button("⬅ Voltar", on_click=navegar_para, args=("dashboard",))
    st.header("📅 Agenda")
    recs = safe_get_records("Agenda")
    df = pd.DataFrame(recs)
    if not df.empty and 'ID_Usuario' in df.columns:
        dfu = df[df['ID_Usuario'] == USER].drop(columns=['ID_Usuario'])
        if not dfu.empty: st.table(dfu)
        else: st.info("Sem treinos.")
    else: st.info("Sem dados.")

# === PROVAS ===
elif st.session_state["pagina_atual"] == "provas":
    st.button("⬅ Voltar", on_click=navegar_para, args=("dashboard",))
    st.header("🏅 Provas")
    recs = safe_get_records("Provas")
    df = pd.DataFrame(recs)
    if not df.empty and 'ID_Usuario' in df.columns:
        st.dataframe(df[df['ID_Usuario'] == USER].drop(columns=['ID_Usuario']), use_container_width=True)
    with st.form("p"):
        d = st.date_input("Data", data_hoje_br()); n = st.text_input("Nome"); di = st.selectbox("km", ["5k","10k","21k"]); 
        if st.form_submit_button("Add"): 
            ss = conectar_gsheets()
            if ss: ss.worksheet("Provas").append_row([USER, d.strftime("%d/%m/%Y"), n, di, "Pendente", "-"]); st.rerun()

# === IA ALUNO ===
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

# === TROCAR SENHA ===
elif st.session_state["pagina_atual"] == "trocar_senha":
    st.button("⬅ Voltar", on_click=navegar_para, args=("dashboard",))
    st.header("🔑 Alterar Senha")
    with st.form("form_senha"):
        sa = st.text_input("Senha Atual", type="password")
        nn = st.text_input("Nova Senha", type="password")
        cn = st.text_input("Confirmar", type="password")
        if st.form_submit_button("Alterar"):
            ss = conectar_gsheets()
            if ss:
                try:
                    ws = ss.worksheet("Usuarios"); cell = ws.find(USER)
                    if cell and str(ws.cell(cell.row, 2).value).strip() == sa.strip():
                        if nn == cn and len(nn)>0: ws.update_cell(cell.row, 2, nn); st.success("Sucesso!"); time.sleep(2); logout(); st.rerun()
                        else: st.error("Erro na nova senha.")
                    else: st.error("Senha atual errada.")
                except: st.error("Erro")
