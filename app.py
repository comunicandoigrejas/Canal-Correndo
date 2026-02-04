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
    except Exception as e: 
        st.error(f"Conexão instável. Aguarde... ({e})")
        time.sleep(2)
        st.cache_resource.clear()
        return None

def verificar_login(usuario, senha):
    ss = conectar_gsheets()
    if ss:
        try:
            ws = ss.worksheet("Usuarios")
            records = ws.get_all_records()
            for u in records:
                u_planilha = str(u['Usuario']).strip()
                s_planilha = str(u['Senha']).strip()
                if u_planilha == usuario and s_planilha == senha:
                    if str(u.get('Status', 'Ativo')) == 'Bloqueado': return "BLOQUEADO", None, None
                    modalidade_raw = str(u.get('Modalidade', 'Corrida')).strip()
                    return u['Nome'], u.get('Funcao', 'aluno'), modalidade_raw
            return None, None, None
        except Exception as e: st.error(f"Erro no Login: {e}"); return None, None, None
    return None, None, None

def carregar_mensagens_usuario(user_id):
    ss = conectar_gsheets(); msgs = []
    if ss:
        try:
            ws = ss.worksheet("Mensagens")
            records = ws.get_all_records()
            for row in reversed(records):
                dest = str(row.get('Destinatario', 'TODOS')).strip()
                if dest in ['TODOS', user_id]:
                    msgs.append(row)
                    if len(msgs) >= 3: break
        except: pass
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
                    str(row.get('Mensagem')) == str(msg_data.get('Mensagem')) and
                    str(row.get('Tipo')) == str(msg_data.get('Tipo'))):
                    ws.delete_rows(i + 2)
                    return True
        except Exception as e: st.error(f"Erro ao excluir: {e}")
    return False

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

# --- 4. LOGIN ---

if st.session_state["usuario_atual"] is None:
    st.title("🏃 Running Coach")
    with st.form("login"):
        u = st.text_input("Usuário").strip()
        s = st.text_input("Senha", type="password").strip()
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
IS_MUSCULACAO = "muscula" in str(MODALIDADE).lower()

# === DASHBOARD ===
if st.session_state["pagina_atual"] == "dashboard":
    c1, c2 = st.columns([3, 1])
    c1.title(f"Olá, {NOME}!")
    if c2.button("Sair"): logout(); st.rerun()

    # Avisos do Treinador
    try:
        mensagens = carregar_mensagens_usuario(USER)
        if mensagens:
            st.subheader("🔔 Avisos")
            for i, m in enumerate(mensagens):
                tp = m.get('Tipo', 'Aviso')
                msg = m.get('Mensagem', '')
                
                col_msg, col_x = st.columns([0.85, 0.15])
                with col_msg:
                    st.markdown(f"<div class='message-card'><strong>{tp}:</strong> {msg}</div>", unsafe_allow_html=True)
                with col_x:
                    st.markdown('<div class="close-btn">', unsafe_allow_html=True)
                    if st.button("X", key=f"del_msg_{i}", help="Apagar"):
                        if excluir_aviso(m):
                            st.success("Apagado!")
                            time.sleep(0.5); st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)
            st.markdown("---")
    except Exception as e: st.error(f"Erro ao carregar avisos: {e}")

    # Resposta Aluno
    with st.expander("💬 Falar com o Treinador"):
        with st.form("form_resposta_aluno"):
            texto_resp = st.text_area("Mensagem:")
            if st.form_submit_button("Enviar"):
                ss = conectar_gsheets()
                if ss:
                    try:
                        ss.worksheet("Mensagens").append_row([
                            date.today().strftime("%d/%m/%Y"), "ADMIN", texto_resp, f"De: {NOME}"
                        ])
                        st.success("Enviado!")
                    except Exception as e: st.error(e)
    
    # Treino de Hoje
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

    # Verifica se treinou
    try:
        if ss:
            ws_reg = ss.worksheet("Registros")
            hoje_str = date.today().strftime("%d/%m/%Y")
            records_reg = ws_reg.get_all_records()
            treinou_hoje = False
            for reg in records_reg:
                if str(reg['ID_Usuario']) == USER and str(reg['Data']) == hoje_str:
                    treinou_hoje = True; break
            if treinou_hoje:
                st.markdown(f"<div class='success-card'>🎉 Parabéns! Treino Realizado!</div>", unsafe_allow_html=True)
    except: pass

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
            dt = st.date_input("Data", date.today())
            obs = st.text_area("Observações (Cargas, sensações, etc)")
            if st.form_submit_button("✅ CONFIRMAR TREINO REALIZADO"):
                ss = conectar_gsheets()
                if ss:
                    ss.worksheet("Registros").append_row([USER, dt.strftime("%d/%m/%Y"), 0, "00:00", 5, obs])
                    st.success("Registrado!")
                    time.sleep(1.5); navegar_para("dashboard"); st.rerun()
    else:
        with st.form("reg_run"):
            d = st.date_input("Data", date.today())
            di = st.number_input("Km", 0.0, step=0.1)
            te = st.text_input("Tempo Total", "00:00:00", help="HH:MM:SS ou MM:SS")
            pe = st.slider("Cansaço", 0, 10, 5)
            ob = st.text_area("Obs")
            if st.form_submit_button("Salvar Corrida"):
                pace_calc = calcular_pace_medio(te, di)
                if pace_calc: ob = f"{ob} | Pace Médio: {pace_calc} min/km"
                ss = conectar_gsheets()
                if ss: 
                    ss.worksheet("Registros").append_row([USER, d.strftime("%d/%m/%Y"), di, te, pe, ob])
                    st.success("Salvo!")
                    time.sleep(1.5); navegar_para("dashboard"); st.rerun()

# === HISTÓRICO COM EXCLUSÃO ===
elif st.session_state["pagina_atual"] == "historico":
    st.button("⬅ Voltar", on_click=navegar_para, args=("dashboard",))
    st.header("📊 Histórico")
    ss = conectar_gsheets()
    if ss:
        try:
            ws = ss.worksheet("Registros")
            all_records = ws.get_all_records()
            df = pd.DataFrame(all_records)
            
            if not df.empty and 'ID_Usuario' in df.columns:
                dfu = df[df['ID_Usuario'] == USER].drop(columns=['ID_Usuario'])
                if not dfu.empty:
                    if IS_MUSCULACAO:
                        st.metric("Total de Treinos", len(dfu))
                        colunas_musc = [c for c in ["Data", "Observacoes"] if c in dfu.columns]
                        st.dataframe(dfu[colunas_musc], use_container_width=True, hide_index=True)
                    else:
                        st.dataframe(dfu, use_container_width=True)
                        if "Distancia" in dfu.columns:
                            dfu["Distancia"] = pd.to_numeric(dfu["Distancia"].astype(str).str.replace(',','.'), errors='coerce')
                            st.line_chart(dfu, x="Data", y="Distancia")
                    
                    st.markdown("---")
                    with st.expander("🗑️ Gerenciar / Excluir Treinos"):
                        st.warning("Cuidado: A exclusão é permanente.")
                        opcoes_exclusao = []
                        for i, reg in enumerate(all_records):
                            if str(reg['ID_Usuario']) == USER:
                                label = f"{reg['Data']} - {str(reg.get('Observacoes',''))[:30]}..."
                                opcoes_exclusao.append((i + 2, label))
                        opcoes_exclusao.reverse()
                        
                        if opcoes_exclusao:
                            labels = [opt[1] for opt in opcoes_exclusao]
                            ids = [opt[0] for opt in opcoes_exclusao]
                            escolha = st.selectbox("Selecione para apagar:", labels)
                            if st.button("Confirmar Exclusão"):
                                idx = labels.index(escolha)
                                row_del = ids[idx]
                                try:
                                    ws.delete_rows(row_del)
                                    st.success("Apagado!"); time.sleep(1); st.rerun()
                                except Exception as e: st.error(f"Erro: {e}")
                        else: st.info("Nada para excluir.")
                else: st.info("Nenhum histórico.")
            else: st.info("Nenhum registro.")
        except Exception as e: st.error(f"Erro: {e}")

# === PAINEL ADMIN ===
elif st.session_state["pagina_atual"] == "admin_panel":
    if not ADMIN: navegar_para("dashboard"); st.rerun()
    st.button("⬅ Voltar", on_click=navegar_para, args=("dashboard",))
    st.title("⚙️ Painel Admin")
    
    ss = conectar_gsheets()
    t1, t2, t3, t4, t5 = st.tabs(["Treinos", "Alunos", "Mensagem", "🔎 Monitorar", "🤖 IA Criadora"])
    
    with t1:
        with st.form("at"):
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
        st.subheader("📢 Enviar Mensagem")
        if ss:
            ws_users = ss.worksheet("Usuarios")
            lista_dest = ["TODOS"] + [r['Usuario'] for r in ws_users.get_all_records()]
            with st.form("msg"):
                us = st.selectbox("Destinatário", lista_dest)
                tx = st.text_area("Mensagem")
                tp = st.selectbox("Tipo", ["Aviso Geral", "Motivacional", "Cobrança", "Parabéns", "Dica Técnica"])
                if st.form_submit_button("Enviar"): 
                    ss.worksheet("Mensagens").append_row([date.today().strftime("%d/%m/%Y"), us, tx, tp])
                    st.success("Enviado!")
            
            st.markdown("---")
            st.subheader("📥 Caixa de Entrada")
            ws_msg = ss.worksheet("Mensagens")
            all_msgs = ws_msg.get_all_records()
            inbox = [m for m in all_msgs if str(m.get('Destinatario','')) == "ADMIN"]
            if inbox:
                df_inbox = pd.DataFrame(inbox)
                cols = [c for c in ["Data", "Tipo", "Mensagem"] if c in df_inbox.columns]
                st.dataframe(df_inbox[cols], use_container_width=True)
            else: st.info("Nenhuma resposta.")

    with t4:
        st.subheader("Acompanhar Alunos")
        if ss:
            ws_users = ss.worksheet("Usuarios")
            records_users = ws_users.get_all_records()
            mapa_modalidades = {str(r['Usuario']): str(r.get('Modalidade', 'Corrida')) for r in records_users}
            lista_alunos = list(mapa_modalidades.keys())
            
            aluno_selecionado = st.selectbox("Selecione o Aluno:", lista_alunos)
            modalidade_aluno = mapa_modalidades.get(aluno_selecionado, 'Corrida')
            is_musc_aluno = "muscula" in modalidade_aluno.lower()

            ws_reg = ss.worksheet("Registros")
            df_reg = pd.DataFrame(ws_reg.get_all_records())
            
            if not df_reg.empty and 'ID_Usuario' in df_reg.columns:
                df_aluno = df_reg[df_reg['ID_Usuario'] == aluno_selecionado].drop(columns=['ID_Usuario'])
                if not df_aluno.empty:
                    st.write(f"**Histórico de {aluno_selecionado} ({modalidade_aluno}):**")
                    if is_musc_aluno:
                        cols_view = [c for c in ["Data", "Observacoes"] if c in df_aluno.columns]
                        st.dataframe(df_aluno[cols_view], use_container_width=True, hide_index=True)
                    else:
                        st.dataframe(df_aluno, use_container_width=True)
                else: st.warning(f"Sem registros.")
            else: st.info("Sem registros.")
    
    # --- ABA 5: IA CHAT CORRIGIDO ---
    with t5:
        st.subheader("🤖 Assistente Expert (Chat)")
        st.info("Converse com sua IA Treinada.")
        
        ASSISTANT_ID = st.secrets.get("assistant_id")
        
        if not ASSISTANT_ID:
            st.warning("Falta 'assistant_id' no secrets.toml.")
        elif ss:
            ws_users = ss.worksheet("Usuarios")
            records_users = ws_users.get_all_records()
            mapa_contexto = {str(r['Usuario']): str(r.get('Modalidade', 'Corrida')) for r in records_users}
            lista_contexto = list(mapa_contexto.keys())
            
            aluno_foco = st.selectbox("Foco no aluno:", lista_contexto)
            modalidade_foco = mapa_contexto.get(aluno_foco, 'Geral')

            if "openai_key" in st.secrets:
                client = OpenAI(api_key=st.secrets["openai_key"])
                
                if "thread_id" not in st.session_state:
                    thread = client.beta.threads.create()
                    st.session_state["thread_id"] = thread.id

                if st.button("🧹 Limpar Chat"):
                    thread = client.beta.threads.create()
                    st.session_state["thread_id"] = thread.id
                    st.session_state["messages_admin"] = []
                    st.rerun()

                # Mostra histórico
                for m in st.session_state.messages_admin:
                    with st.chat_message(m["role"]):
                        st.write(m["content"])
                
                # --- CHAT INPUT CORRIGIDO ---
                if prompt := st.chat_input("Converse com a IA (Ex: Monte o treino de perna)"):
                    st.session_state.messages_admin.append({"role": "user", "content": prompt})
                    with st.chat_message("user"):
                        st.write(prompt)

                    full_prompt = f"Contexto: Aluno {aluno_foco} ({modalidade_foco}). Mensagem: {prompt}"

                    try:
                        with st.spinner("IA pensando..."):
                            client.beta.threads.messages.create(
                                thread_id=st.session_state["thread_id"],
                                role="user",
                                content=full_prompt
                            )
                            run = client.beta.threads.runs.create(
                                thread_id=st.session_state["thread_id"],
                                assistant_id=ASSISTANT_ID
                            )
                            while run.status in ['queued', 'in_progress', 'cancelling']:
                                time.sleep(1)
                                run = client.beta.threads.runs.retrieve(
                                    thread_id=st.session_state["thread_id"],
                                    run_id=run.id
                                )
                            
                            if run.status == 'completed':
                                messages = client.beta.threads.messages.list(
                                    thread_id=st.session_state["thread_id"]
                                )
                                resp = messages.data[0].content[0].text.value
                                
                                st.session_state.messages_admin.append({"role": "assistant", "content": resp})
                                with st.chat_message("assistant"):
                                    st.write(resp)
                            else:
                                st.error(f"Erro IA: {run.status}")
                    except Exception as e:
                        st.error(f"Erro conexão: {e}")

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

elif st.session_state["pagina_atual"] == "trocar_senha":
    st.button("⬅ Voltar", on_click=navegar_para, args=("dashboard",))
    st.header("🔑 Alterar Senha")
    with st.form("form_senha"):
        senha_atual = st.text_input("Senha Atual", type="password")
        nova_senha = st.text_input("Nova Senha", type="password")
        confirma_senha = st.text_input("Confirme a Nova Senha", type="password")
        if st.form_submit_button("Alterar Senha"):
            ss = conectar_gsheets()
            if ss:
                try:
                    ws = ss.worksheet("Usuarios")
                    cell = ws.find(USER)
                    if cell:
                        senha_banco = ws.cell(cell.row, 2).value
                        if str(senha_banco).strip() == senha_atual.strip():
                            if nova_senha == confirma_senha and len(nova_senha)>0:
                                ws.update_cell(cell.row, 2, nova_senha)
                                st.success("Sucesso!"); time.sleep(2); logout(); st.rerun()
                            else: st.error("Erro na nova senha.")
                        else: st.error("Senha atual errada.")
                    else: st.error("Usuário não encontrado.")
                except Exception as e: st.error(f"Erro: {e}")
