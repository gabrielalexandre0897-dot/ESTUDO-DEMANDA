import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import copy
import hashlib
import json
import datetime
from supabase import create_client, Client

# Configuração da Página
st.set_page_config(page_title="Estudo de Demanda - Veículos Elétricos & Ar Condicionado", page_icon="⚡", layout="wide")

# --- CONFIGURAÇÃO DO SUPABASE (BANCO DE DADOS GRATUITO E ILIMITADO) ---
SUPABASE_URL = "https://gnrulqnowyvrlqwlpmtq.supabase.co"      # Substitua pela sua URL do Supabase
SUPABASE_KEY = "sb_publishable_gAIQP7GY098r3dzaFS77-g_IEAje5s5"            # Substitua pela sua API Key (anon/public)

@st.cache_resource
def init_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

try:
    supabase = init_supabase()
except Exception as e:
    st.error(f"Erro ao conectar ao Supabase: {e}")

# Estilização CSS customizada
st.markdown("""
<style>
    .report-table {
        width: 100%;
        border-collapse: collapse;
        font-family: Arial, sans-serif;
        margin: 15px 0;
        background-color: #ffffff;
        box-shadow: 0 2px 5px rgba(0,0,0,0.08);
        border-radius: 6px;
        overflow: hidden;
    }
    .report-table th {
        background-color: #1E3A8A;
        color: white;
        padding: 12px;
        text-align: center;
        font-size: 14px;
        border: 1px solid #1E3A8A;
    }
    .report-table td {
        padding: 10px 12px;
        text-align: center;
        border: 1px solid #E5E7EB;
        font-size: 13px;
        color: #1F2937;
    }
    .report-table tr:nth-child(even) {
        background-color: #F9FAFB;
    }
</style>
""", unsafe_allow_html=True)

# Função auxiliar para gerar configuração de download de imagem com nome personalizado
def get_config_img(nome_arquivo):
    nome_limpo = "".join(c for c in nome_arquivo if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_")
    if not nome_limpo:
        nome_limpo = "imagem_exportada"
    return {
        "toImageButtonOptions": {
            "format": "png",
            "filename": nome_limpo,
            "width": 1400,
            "height": 450,
            "scale": 3
        },
        "displayModeBar": True
    }

# --- FUNÇÕES DE SEGURANÇA E BIND NUVEM ---
def hash_password(password):
    return hashlib.sha256(password.strip().encode()).hexdigest()

def converter_para_json_safe(obj):
    """Converte pandas Series e tipos não serializáveis em estruturas nativas em Python."""
    if isinstance(obj, dict):
        return {k: converter_para_json_safe(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [converter_para_json_safe(i) for i in obj]
    elif isinstance(obj, pd.Series):
        return {"__pd_series__": True, "data": obj.tolist()}
    elif isinstance(obj, (np.integer, np.floating)):
        return obj.item()
    return obj

def restaurar_de_json_safe(obj):
    """Restaura pandas Series a partir da estrutura JSON."""
    if isinstance(obj, dict):
        if obj.get("__pd_series__") is True:
            return pd.Series(obj["data"])
        return {k: restaurar_de_json_safe(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [restaurar_de_json_safe(i) for i in obj]
    return obj

def carregar_dados_nuvem():
    if "SUA_URL_AQUI" in SUPABASE_URL:
        return None
    try:
        response = supabase.table("app_data").select("payload").eq("id", "main_db").execute()
        if response.data and len(response.data) > 0:
            payload = response.data[0]["payload"]
            return restaurar_de_json_safe(payload)
    except Exception as e:
        st.error(f"Erro ao carregar dados do Supabase: {e}")
    return None

def salvar_dados_nuvem(silencioso=False):
    if "SUA_URL_AQUI" in SUPABASE_URL:
        return
    
    dados = {
        "usuarios": st.session_state.get("db_usuarios", {}),
        "relatorios": st.session_state.get("db_relatorios", [])
    }
    
    dados_safe = converter_para_json_safe(dados)
    
    try:
        supabase.table("app_data").upsert({
            "id": "main_db",
            "payload": dados_safe,
            "updated_at": datetime.datetime.now().isoformat()
        }).execute()
        
        if not silencioso:
            st.toast('Dados salvos no Supabase com sucesso!', icon='✅')
    except Exception as e:
        st.error(f"Erro ao salvar no Supabase: {e}")

# --- INICIALIZAÇÃO DE DADOS DA NUVEM ---
if "nuvem_iniciada" not in st.session_state:
    dados_nuvem = carregar_dados_nuvem()
    if dados_nuvem:
        st.session_state["db_usuarios"] = dados_nuvem.get("usuarios", {})
        st.session_state["db_relatorios"] = dados_nuvem.get("relatorios", [])
    else:
        st.session_state["db_usuarios"] = {
            "admin": {"password": hash_password("admin123"), "is_admin": True}
        }
        st.session_state["db_relatorios"] = []
    st.session_state["nuvem_iniciada"] = True

# --- GERENCIAMENTO DE USUÁRIOS E RELATÓRIOS ---
def verificar_login(username, password):
    username = username.strip()
    users = st.session_state.get("db_usuarios", {})
    if username in users:
        if users[username]["password"] == hash_password(password):
            return True, users[username]["is_admin"]
    return False, False

def alterar_senha_usuario(username, senha_atual, nova_senha):
    username = username.strip()
    if not nova_senha.strip():
        return False, "A nova senha não pode estar em branco."
    
    ok, _ = verificar_login(username, senha_atual)
    if not ok:
        return False, "Senha atual incorreta."
        
    st.session_state["db_usuarios"][username]["password"] = hash_password(nova_senha)
    salvar_dados_nuvem(silencioso=True)
    return True, "Senha alterada com sucesso!"

def cadastrar_usuario(username, password, is_admin=False):
    username = username.strip()
    if not username or not password.strip():
        return False, "Preencha usuário e senha."
    if username in st.session_state["db_usuarios"]:
        return False, "Usuário já existe."
    
    st.session_state["db_usuarios"][username] = {
        "password": hash_password(password),
        "is_admin": is_admin
    }
    salvar_dados_nuvem(silencioso=True)
    return True, "Usuário cadastrado com sucesso!"

def excluir_usuario(username):
    username = username.strip()
    if username == "admin":
        return False, "O usuário administrador principal não pode ser excluído."
    if username in st.session_state["db_usuarios"]:
        del st.session_state["db_usuarios"][username]
        st.session_state["db_relatorios"] = [r for r in st.session_state["db_relatorios"] if r["username"] != username]
        salvar_dados_nuvem(silencioso=True)
        return True, "Usuário e seus relatórios excluídos com sucesso!"
    return False, "Usuário não encontrado."

def salvar_relatorio_nuvem(username, nome_relatorio, estado_dict):
    username = username.strip()
    data_atual = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    relatorios = st.session_state["db_relatorios"]
    atualizado = False
    
    for r in relatorios:
        if r["username"] == username and r["nome_relatorio"] == nome_relatorio:
            r["dados"] = copy.deepcopy(estado_dict)
            r["data_criacao"] = data_atual
            atualizado = True
            break
            
    if not atualizado:
        relatorios.append({
            "username": username,
            "nome_relatorio": nome_relatorio,
            "dados": copy.deepcopy(estado_dict),
            "data_criacao": data_atual
        })
        
    salvar_dados_nuvem(silencioso=True)
    return True

def carregar_relatorio_nuvem(username, nome_relatorio):
    username = username.strip()
    for r in st.session_state["db_relatorios"]:
        if r["username"] == username and r["nome_relatorio"] == nome_relatorio:
            return copy.deepcopy(r["dados"])
    return None

def excluir_relatorio_nuvem(username, nome_relatorio):
    username = username.strip()
    st.session_state["db_relatorios"] = [r for r in st.session_state["db_relatorios"] if not (r["username"] == username and r["nome_relatorio"] == nome_relatorio)]
    salvar_dados_nuvem(silencioso=True)
    return True

def renomear_relatorio_nuvem(username, nome_antigo, nome_novo):
    username = username.strip()
    for r in st.session_state["db_relatorios"]:
        if r["username"] == username and r["nome_relatorio"] == nome_antigo:
            r["nome_relatorio"] = nome_novo
            salvar_dados_nuvem(silencioso=True)
            return True
    return False

def listar_meses_relatorios(username=None):
    meses = set()
    for r in st.session_state["db_relatorios"]:
        if username is None or r["username"] == username:
            try:
                dt = datetime.datetime.strptime(r["data_criacao"], "%Y-%m-%d %H:%M:%S")
                meses.add(dt.strftime("%m/%Y"))
            except:
                pass
    return sorted(list(meses), reverse=True)

def listar_relatorios_nuvem(username=None, mes_ano=None):
    resultados = []
    for r in st.session_state["db_relatorios"]:
        cond_user = (username is None or r["username"] == username)
        cond_mes = True
        if mes_ano:
            try:
                dt = datetime.datetime.strptime(r["data_criacao"], "%Y-%m-%d %H:%M:%S")
                cond_mes = (dt.strftime("%m/%Y") == mes_ano)
            except:
                cond_mes = False
        if cond_user and cond_mes:
            resultados.append((r["nome_relatorio"], r["username"], r["data_criacao"]))
    return resultados

# --- CONTROLE DE SESSÃO DE LOGIN ---
if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if "username" not in st.session_state: st.session_state["username"] = ""
if "is_admin" not in st.session_state: st.session_state["is_admin"] = False

if not st.session_state["logged_in"]:
    st.title("🔐 Acesso Restrito - Estudo de Demanda")
    st.markdown("Por favor, faça login para continuar.")
    with st.form("form_login"):
        user_input = st.text_input("Usuário:")
        pass_input = st.text_input("Senha:", type="password")
        submit_login = st.form_submit_button("Entrar", type="primary")
        if submit_login:
            ok, admin_status = verificar_login(user_input, pass_input)
            if ok:
                st.session_state.update({"logged_in": True, "username": user_input.strip(), "is_admin": admin_status})
                st.success("Login efetuado com sucesso!")
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")
    st.stop()

# --- VARIÁVEIS GLOBAIS DE ENGENHARIA ---
TABELA_CABOS = {
    "0,5 mm² - 750V": 8.0, "0,75 mm² - 750V": 10.0, "1 mm² - 750V": 12.0, "1,5 mm² - 750V": 15.5,
    "2,5 mm² - 750V": 21.0, "4 mm² - 750V": 28.0, "6 mm² - 750V": 36.0, "10 mm² - 750V": 50.0,
    "16 mm² - 750V": 68.0, "25 mm² - 750V": 89.0, "35 mm² - 750V": 110.0, "50 mm² - 750V": 134.0,
    "70 mm² - 750V": 171.0, "95 mm² - 750V": 207.0, "120 mm² - 750V": 239.0, "150 mm² - 750V": 275.0,
    "185 mm² - 750V": 314.0, "240 mm² - 750V": 370.0, "300 mm² - 750V": 426.0, "400 mm² - 750V": 510.0,
    "500 mm² - 750V": 587.0, "630 mm² - 750V": 678.0, "800 mm² - 750V": 788.0, "1000 mm² - 750V": 906.0,
    "0,5 mm² - 1kV": 10.0, "0,75 mm² - 1kV": 13.0, "1 mm² - 1kV": 16.0, "1,5 mm² - 1kV": 20.0,
    "2,5 mm² - 1kV": 28.0, "4 mm² - 1kV": 37.0, "6 mm² - 1kV": 48.0, "10 mm² - 1kV": 66.0,
    "16 mm² - 1kV": 88.0, "25 mm² - 1kV": 117.0, "35 mm² - 1kV": 144.0, "50 mm² - 1kV": 175.0,
    "70 mm² - 1kV": 222.0, "95 mm² - 1kV": 269.0, "120 mm² - 1kV": 312.0, "150 mm² - 1kV": 358.0,
    "185 mm² - 1kV": 408.0, "240 mm² - 1kV": 481.0, "300 mm² - 1kV": 553.0, "400 mm² - 1kV": 661.0,
    "500 mm² - 1kV": 760.0, "630 mm² - 1kV": 879.0, "800 mm² - 1kV": 1020.0, "1000 mm² - 1kV": 1173.0,
}
INDEX_PADRAO = list(TABELA_CABOS.keys()).index("35 mm² - 1kV")

def fmt(val, dec=2): return f"{val:.{dec}f}".replace('.', ',')

def update_cap_geral():
    if st.session_state.get('g_bitola') in TABELA_CABOS: st.session_state['g_cap'] = float(TABELA_CABOS[st.session_state['g_bitola']])
def update_cap_adm():
    if st.session_state.get('a_bitola') in TABELA_CABOS: st.session_state['a_cap'] = float(TABELA_CABOS[st.session_state['a_bitola']])
def update_cap_med():
    if st.session_state.get('m_bitola') in TABELA_CABOS: st.session_state['m_cap'] = float(TABELA_CABOS[st.session_state['m_bitola']])

if "tipo_estudo_global" not in st.session_state: st.session_state["tipo_estudo_global"] = "Veículos Elétricos (VE)"
if "current_report_name" not in st.session_state: st.session_state.update({"current_report_name": "", "dados_geral": {}, "dados_adm": {}, "dados_med": {}, "reset_key": 0, "arquivos_data": {}})

def reset_app():
    st.session_state["reset_key"] += 1
    keys_to_keep = ["logged_in", "username", "is_admin", "reset_key", "db_usuarios", "db_relatorios", "nuvem_iniciada"]
    for k in list(st.session_state.keys()):
        if k not in keys_to_keep: del st.session_state[k]
    st.session_state.update({"dados_geral": {}, "dados_adm": {}, "dados_med": {}, "arquivos_data": {}, "current_report_name": "", "tipo_estudo_global": "Veículos Elétricos (VE)"})

# --- BARRA LATERAL ---
st.sidebar.markdown(f"👤 **Logado como:** `{st.session_state['username']}` " + ("*(Admin)*" if st.session_state['is_admin'] else ""))
if st.sidebar.button("🚪 Sair (Logout)", use_container_width=True):
    st.session_state.update({"logged_in": False, "username": "", "is_admin": False})
    st.rerun()

with st.sidebar.expander("🔑 Alterar Minha Senha"):
    with st.form("form_alterar_senha", clear_on_submit=True):
        st_s_atual = st.text_input("Senha Atual:", type="password", key="m_s_atual")
        st_s_nova = st.text_input("Nova Senha:", type="password", key="m_s_nova")
        btn_mudar_senha = st.form_submit_button("Atualizar Senha", use_container_width=True)
        
        if btn_mudar_senha:
            if not st_s_atual or not st_s_nova:
                st.error("Preencha a senha atual e a nova senha.")
            else:
                ok_s, msg_s = alterar_senha_usuario(st.session_state['username'], st_s_atual, st_s_nova)
                if ok_s: 
                    st.success(msg_s)
                else: 
                    st.error(msg_s)

st.sidebar.markdown("---")
st.sidebar.markdown("### 📅 Relatórios Mensais")

user_filtro = None if st.session_state["is_admin"] else st.session_state["username"]
meses_disponiveis = listar_meses_relatorios(user_filtro)

if not meses_disponiveis:
    mes_atual_str = datetime.datetime.now().strftime("%m/%Y")
    meses_disponiveis = [mes_atual_str]

mes_selecionado = st.sidebar.selectbox("Selecione o Mês:", meses_disponiveis, key="sb_mes_filtro")

if st.sidebar.button("➕ Criar Novo Relatório", type="primary", use_container_width=True):
    st.session_state["show_modal_novo_relatorio"] = True

# MODAL CRIAR NOVO RELATÓRIO
if st.session_state.get("show_modal_novo_relatorio", False):
    @st.dialog("➕ Criar Novo Relatório")
    def dialog_novo_relatorio():
        st.write("Selecione o tipo de estudo e defina o nome inicial do relatório:")
        t_sel = st.radio("Tipo de Estudo:", ["Veículos Elétricos (VE)", "Ar Condicionado (AC)", "Ar Condicionado & Veículos Elétricos (AC+VE)"], key="diag_tipo_estudo")
        n_sel = st.text_input("Nome do Relatório:", placeholder="Ex: Condomínio Solar - Bloco A", key="diag_nome_rel")
        
        col_d1, col_d2 = st.columns(2)
        if col_d1.button("Confirmar e Criar", type="primary", use_container_width=True):
            if not n_sel:
                st.error("Informe um nome para o relatório!")
            else:
                reset_app()
                st.session_state["tipo_estudo_global"] = t_sel
                st.session_state["current_report_name"] = n_sel
                st.session_state["show_modal_novo_relatorio"] = False
                st.rerun()
        if col_d2.button("Cancelar", use_container_width=True):
            st.session_state["show_modal_novo_relatorio"] = False
            st.rerun()
    dialog_novo_relatorio()

# MODAIS DE CONFIRMAÇÃO DO ADMIN PARA EXCLUSÃO
if st.session_state.get("show_modal_del_rel", False):
    @st.dialog("🔒 Confirmação do Admin - Excluir Relatório")
    def dialog_del_rel():
        rel_target = st.session_state.get("target_del_rel", "")
        dono_target = st.session_state.get("target_del_dono", "")
        st.warning(f"Deseja realmente excluir o relatório **'{rel_target}'** (Usuário: {dono_target})?")
        p_admin = st.text_input("Digite a sua senha de Admin para confirmar:", type="password", key="pass_adm_del_rel")
        
        c1, c2 = st.columns(2)
        if c1.button("Confirmar Exclusão", type="primary", use_container_width=True):
            if verificar_login(st.session_state["username"], p_admin)[0]:
                if excluir_relatorio_nuvem(dono_target, rel_target):
                    if st.session_state["current_report_name"] == rel_target: st.session_state["current_report_name"] = ""
                    st.session_state["show_modal_del_rel"] = False
                    st.toast("Relatório apagado com sucesso!", icon="🗑️")
                    st.rerun()
                else: st.error("Erro ao excluir relatório.")
            else: st.error("Senha de Admin incorreta!")
        if c2.button("Cancelar", use_container_width=True):
            st.session_state["show_modal_del_rel"] = False
            st.rerun()
    dialog_del_rel()

if st.session_state.get("show_modal_del_usr", False):
    @st.dialog("🔒 Confirmação do Admin - Excluir Usuário")
    def dialog_del_usr():
        usr_target = st.session_state.get("target_del_usr", "")
        st.warning(f"Deseja realmente excluir o usuário **'{usr_target}'** e todos os seus relatórios?")
        p_admin = st.text_input("Digite a sua senha de Admin para confirmar:", type="password", key="pass_adm_del_usr")
        
        c1, c2 = st.columns(2)
        if c1.button("Confirmar Exclusão", type="primary", use_container_width=True):
            if verificar_login(st.session_state["username"], p_admin)[0]:
                ok, msg = excluir_usuario(usr_target)
                if ok:
                    st.session_state["show_modal_del_usr"] = False
                    st.toast(msg, icon="🗑️")
                    st.rerun()
                else: st.error(msg)
            else: st.error("Senha de Admin incorreta!")
        if c2.button("Cancelar", use_container_width=True):
            st.session_state["show_modal_del_usr"] = False
            st.rerun()
    dialog_del_usr()

st.sidebar.markdown("---")
lista_db = listar_relatorios_nuvem(user_filtro, mes_ano=mes_selecionado)

st.sidebar.markdown(f"📂 **Relatórios de {mes_selecionado}:**")

if not lista_db:
    st.sidebar.info(f"Nenhum relatório encontrado em {mes_selecionado}.")
else:
    opcoes_map = {f"{i[0]} (por: {i[1]})" if st.session_state["is_admin"] else i[0]: i for i in lista_db}
    selecao = st.sidebar.selectbox("Selecione um relatório:", list(opcoes_map.keys()), key="selectbox_historico")
    rel_selecionado = opcoes_map[selecao][0]
    dono = opcoes_map[selecao][1] if st.session_state["is_admin"] else st.session_state["username"]
    
    col_b1, col_b2 = st.sidebar.columns(2)
    with col_b1:
        if st.button("📂 Carregar", use_container_width=True, key="btn_load_action"):
            report_data = carregar_relatorio_nuvem(dono, rel_selecionado)
            if report_data:
                keys_to_keep = ["logged_in", "username", "is_admin", "reset_key", "selectbox_historico", "sb_mes_filtro", "db_usuarios", "db_relatorios", "nuvem_iniciada"]
                for k in list(st.session_state.keys()):
                    if k not in keys_to_keep: del st.session_state[k]
                for k, v in report_data.items(): st.session_state[k] = copy.deepcopy(v)
                st.session_state["current_report_name"] = rel_selecionado
                st.session_state["reset_key"] += 1
                st.toast(f"Relatório '{rel_selecionado}' carregado!", icon="📂")
                st.rerun()
    with col_b2:
        if st.session_state["is_admin"]:
            if st.button("🗑️ Excluir", use_container_width=True, key="btn_del_action"):
                st.session_state["target_del_rel"] = rel_selecionado
                st.session_state["target_del_dono"] = dono
                st.session_state["show_modal_del_rel"] = True
                st.rerun()

if st.session_state["is_admin"]:
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 👑 Painel Admin: Usuários")
    with st.sidebar.expander("Gerenciar Usuários"):
        novo_user = st.text_input("Novo Usuário:", key="adm_novo_user")
        nova_senha = st.text_input("Nova Senha:", type="password", key="adm_nova_pass")
        e_admin = st.checkbox("Tornar Administrador", key="adm_e_admin")
        if st.button("Adicionar Usuário"):
            ok, msg = cadastrar_usuario(novo_user, nova_senha, e_admin)
            if ok: st.success(msg)
            else: st.error(msg)
        st.markdown("---")
        st.markdown("**Usuários Cadastrados:**")
        for u, details in st.session_state["db_usuarios"].items():
            col_u1, col_u2 = st.columns([3, 1])
            col_u1.text(f"{u} {'(Admin)' if details.get('is_admin') else ''}")
            if u != "admin" and col_u2.button("X", key=f"del_u_{u}"):
                st.session_state["target_del_usr"] = u
                st.session_state["show_modal_del_usr"] = True
                st.rerun()

def extrair_dados_completos(df):
    try:
        cols_numericas = [col for col in df.columns if len(pd.to_numeric(df[col], errors='coerce').dropna()) > 2]
        if len(cols_numericas) >= 3:
            r = pd.to_numeric(df[cols_numericas[0]], errors='coerce').dropna().values
            s = pd.to_numeric(df[cols_numericas[1]], errors='coerce').dropna().values
            t = pd.to_numeric(df[cols_numericas[2]], errors='coerce').dropna().values
            if len(r)>0 and len(s)>0 and len(t)>0: return pd.Series(r).astype(float), pd.Series(s).astype(float), pd.Series(t).astype(float)
    except: pass
    return None, None, None

st.title("⚡ Estudo de Demanda Elétrica & Capacidade (VE / AC / AC+VE)")

# ALERTA DE TIPO DE ESTUDO SELECIONADO
if "AC+VE" in st.session_state["tipo_estudo_global"]:
    sigla_estudo_global = "AC+VE"
elif "Ar Condicionado" in st.session_state["tipo_estudo_global"]:
    sigla_estudo_global = "AC"
else:
    sigla_estudo_global = "VE"

st.info(f"📋 **Estudo Atual Configurado para:** {st.session_state['tipo_estudo_global']}")

tab1, tab2, tab3, tab4 = st.tabs([
    "🔌 1. Entrada de Energia (Geral)", 
    "🏢 2. Quadro Administrativo (ADM)", 
    "⚡ 3. Caixa de Medidores", 
    "📝 4. Conclusão & Laudo Técnico"
])

# --- ABA 1 ---
with tab1:
    st.header("🔌 1. Entrada de Energia (Geral)")
    sigla = sigla_estudo_global

    file_geral = st.file_uploader("📂 Arraste e solte o arquivo Excel (.xlsx) ou CSV do Analisador de Energia:", type=["xlsx", "csv"], key=f"file_geral_{st.session_state['reset_key']}")
    serie_r_b, serie_s_b, serie_t_b = pd.Series([25.0, 30.2, 31.29, 28.4, 26.1]), pd.Series([4.5, 5.2, 5.81, 5.0, 4.8]), pd.Series([26.0, 31.0, 32.16, 29.5, 27.0])

    if "g_serie_r" in st.session_state["arquivos_data"]:
        serie_r_b = st.session_state["arquivos_data"]["g_serie_r"]
        serie_s_b = st.session_state["arquivos_data"]["g_serie_s"]
        serie_t_b = st.session_state["arquivos_data"]["g_serie_t"]
        if file_geral is None: st.info("ℹ️ Dados do Excel geral recuperados do relatório salvo.")

    if file_geral is not None:
        try:
            df_u = pd.read_csv(file_geral) if file_geral.name.endswith(".csv") else pd.read_excel(file_geral, sheet_name=0)
            sr, ss, st_ser = extrair_dados_completos(df_u)
            if sr is not None and len(sr) > 0:
                serie_r_b, serie_s_b, serie_t_b = sr, ss, st_ser
                st.session_state["arquivos_data"].update({"g_serie_r": sr, "g_serie_s": ss, "g_serie_t": st_ser})
                st.success("✅ Medições carregadas com sucesso!")
        except: st.warning("⚠️ Usando dados padrão de demonstração.")

    col1, col2 = st.columns(2)
    if "g_bitola" not in st.session_state: st.session_state["g_bitola"] = list(TABELA_CABOS.keys())[INDEX_PADRAO]
    if "g_cap" not in st.session_state: st.session_state["g_cap"] = float(TABELA_CABOS[st.session_state["g_bitola"]])

    with col1:
        num_cabos = st.number_input("Número de cabos por fase:", min_value=1, value=3, step=1, key="g_cabos")
        bitola = st.selectbox("Bitola do Condutor:", list(TABELA_CABOS.keys()), key="g_bitola", on_change=update_cap_geral)
        i_cap = st.number_input("Capacidade do cabo por fase (A):", key="g_cap", step=1.0)
        i_prot = st.number_input("Corrente do Dispositivo de Proteção por fase (A):", value=315.0, key="g_prot")
        v_fase = st.number_input("Tensão de Fase (V):", value=127.0, key="g_v")

    min_len = max(1, min(len(serie_r_b), len(serie_s_b), len(serie_t_b)))
    
    ir_am_max = serie_r_b.iloc[:min_len].max()
    is_am_max = serie_s_b.iloc[:min_len].max()
    it_am_max = serie_t_b.iloc[:min_len].max()

    i_pico_r_b = ir_am_max * num_cabos
    i_pico_s_b = is_am_max * num_cabos
    i_pico_t_b = it_am_max * num_cabos
    i_max_pico_base = max(i_pico_r_b, i_pico_s_b, i_pico_t_b)

    p_apar_r_b = i_pico_r_b * v_fase
    p_apar_s_b = i_pico_s_b * v_fase
    p_apar_t_b = i_pico_t_b * v_fase
    p_apar_tot_b = p_apar_r_b + p_apar_s_b + p_apar_t_b

    i_cond_tot = i_cap * num_cabos
    i_prot_tot = i_prot * num_cabos
    
    pct_condutor_base = (i_max_pico_base / i_cond_tot) * 100 if i_cond_tot > 0 else 0
    pct_dispositivo_base = (i_max_pico_base / i_prot_tot) * 100 if i_prot_tot > 0 else 0
    disp_restante_base = i_prot_tot - i_max_pico_base
    bitola_texto = bitola.replace(" mm² - ", "mm²-")

    p_disp_prot_total = max(0.0, (i_prot_tot - i_max_pico_base) * v_fase) * 3
    p_disp_cond_total = max(0.0, (i_cond_tot - i_max_pico_base) * v_fase) * 3
    p_disp_menor_kw = min(p_disp_prot_total, p_disp_cond_total) / 1000.0

    texto_analise_geral = f"""As medições realizadas com o analisador de energia indicaram as correntes de amostragem máximas de {fmt(ir_am_max)}A na fase R, {fmt(is_am_max)}A na fase S e {fmt(it_am_max)}A na fase T.
O padrão de entrada existente no condomínio conta com {num_cabos} dispositivos de proteção, dessa forma, as correntes de pico consideradas totais do sistema são: {fmt(i_pico_r_b)}A na fase R, {fmt(i_pico_s_b)}A na fase S e {fmt(i_pico_t_b)}A na fase T.
A alimentação do sistema é realizada por condutor de seção estimada {bitola_texto}, que possui uma capacidade teórica de condução de corrente na ordem de {fmt(i_cap, 0)}A (por fase) em condições usuais de instalação. Dessa forma, a maior corrente de pico medida ({fmt(i_max_pico_base)}A) representa aproximadamente {fmt(pct_condutor_base)}% da capacidade do condutor.
Considerando a proteção geral da entrada de energia ({num_cabos} x {fmt(i_prot, 0)} = {fmt(i_prot_tot, 0)}A), verifica-se que a maior corrente de pico medida ({fmt(i_max_pico_base)}A) corresponde a aproximadamente {fmt(pct_dispositivo_base)}% da capacidade nominal do dispositivo, restando uma capacidade disponível na ordem de {fmt(disp_restante_base)}A na fase analisada.
Portanto, conclui-se que existe uma potência disponível de {fmt(p_disp_menor_kw)} kW na entrada de energia."""

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("📝 **Análise Completa da Entrada de Energia:**")
    st.success(texto_analise_geral)
    st.code(texto_analise_geral, language="text")

    st.markdown("---")
    if sigla == "AC":
        st.subheader("❄️ Simulador de Cargas AC")
        qtd_add = st.number_input("Quantidade de Ar Condicionado a Adicionar (X):", min_value=0, value=2, step=1, key="g_qtd_ac")
        btu_sel = st.selectbox("Potência do Ar Condicionado:", ["9.000 BTU/h", "12.000 BTU/h", "18.000 BTU/h", "24.000 BTU/h"], key="g_btu_sel")
        if "9.000" in btu_sel: p_kw = 1.0
        elif "12.000" in btu_sel: p_kw = 1.2
        elif "18.000" in btu_sel: p_kw = 1.6
        else: p_kw = 2.0
        st.info(f"Potência unitária considerada para cálculo: **{p_kw:.1f} kW** ({btu_sel})")
        potencia_total_watts = qtd_add * p_kw * 1000
    elif sigla == "VE":
        st.subheader("🚗 Simulador de Cargas VE")
        qtd_add = st.number_input("Quantidade de Carregadores a Adicionar (X):", min_value=0, value=2, step=1, key="g_qtd_ve")
        ve_sel = st.selectbox("Potência por Carregador:", ["3.700W (3.7 kW)", "7.400W (7.4 kW)", "11.000W (11.0 kW)"], key="g_ve_sel")
        if "3.700" in ve_sel: p_kw = 3.7
        elif "7.400" in ve_sel: p_kw = 7.4
        else: p_kw = 11.0
        st.info(f"Potência unitária considerada para cálculo: **{p_kw:.1f} kW**")
        potencia_total_watts = qtd_add * p_kw * 1000
    else: # AC+VE
        st.subheader("⚡ Simulador de Cargas Combinadas (AC + VE)")
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            qtd_ac_misto = st.number_input("Qtd. Ar Condicionado (X):", min_value=0, value=2, step=1, key="g_qtd_ac_misto")
            btu_sel_misto = st.selectbox("Potência por AC:", ["9.000 BTU/h", "12.000 BTU/h", "18.000 BTU/h", "24.000 BTU/h"], key="g_btu_misto")
            p_kw_ac = 1.0 if "9.000" in btu_sel_misto else (1.2 if "12.000" in btu_sel_misto else (1.6 if "18.000" in btu_sel_misto else 2.0))
        with col_s2:
            qtd_ve_misto = st.number_input("Qtd. Carregadores VE (X):", min_value=0, value=2, step=1, key="g_qtd_ve_misto")
            ve_sel_misto = st.selectbox("Potência por VE:", ["3.700W (3.7 kW)", "7.400W (7.4 kW)", "11.000W (11.0 kW)"], key="g_ve_misto")
            p_kw_ve = 3.7 if "3.700" in ve_sel_misto else (7.4 if "7.400" in ve_sel_misto else 11.0)
        
        potencia_total_watts = (qtd_ac_misto * p_kw_ac + qtd_ve_misto * p_kw_ve) * 1000
        st.info(f"Potência Total Adicionada: **{((qtd_ac_misto * p_kw_ac) + (qtd_ve_misto * p_kw_ve)):.1f} kW** ({qtd_ac_misto} ACs + {qtd_ve_misto} VEs)")

    corr_add = potencia_total_watts / (220.0 * np.sqrt(3))

    r_base_total_serie = serie_r_b.iloc[:min_len] * num_cabos
    s_base_total_serie = serie_s_b.iloc[:min_len] * num_cabos
    t_base_total_serie = serie_t_b.iloc[:min_len] * num_cabos

    r_tot_serie = r_base_total_serie + corr_add
    s_tot_serie = s_base_total_serie + corr_add
    t_tot_serie = t_base_total_serie + corr_add

    i_pico_r = float(r_tot_serie.max()) if len(r_tot_serie) > 0 else 0.0
    i_pico_s = float(s_tot_serie.max()) if len(s_tot_serie) > 0 else 0.0
    i_pico_t = float(t_tot_serie.max()) if len(t_tot_serie) > 0 else 0.0
    i_max_pico = max(i_pico_r, i_pico_s, i_pico_t)

    p_apar_r, p_apar_s, p_apar_t = i_pico_r * v_fase, i_pico_s * v_fase, i_pico_t * v_fase
    p_apar_tot = p_apar_r + p_apar_s + p_apar_t

    st.session_state["serie_r_geral"] = r_base_total_serie
    st.session_state["serie_s_geral"] = s_base_total_serie
    st.session_state["serie_t_geral"] = t_base_total_serie

    st.session_state["dados_geral"] = {
        "i_pico_max": i_max_pico, "p_apar_total": p_apar_tot,
        "p_disp_prot_total": p_disp_prot_total, "p_disp_cond_total": p_disp_cond_total,
        "p_disp_menor_kva": p_disp_menor_kw,
        "bitola": bitola, "i_cap_cabo": i_cond_tot, "i_protecao": i_prot_tot,
        "pct_condutor": (i_max_pico / i_cond_tot) * 100 if i_cond_tot > 0 else 0,
        "pct_dispositivo": (i_max_pico / i_prot_tot) * 100 if i_prot_tot > 0 else 0,
        "disp_restante": i_prot_tot - i_max_pico, "sigla_tipo": sigla
    }

    stat_r = "⚠️ ACIMA" if i_pico_r > i_prot_tot or i_pico_r > i_cond_tot else "✅ OK"
    stat_s = "⚠️ ACIMA" if i_pico_s > i_prot_tot or i_pico_s > i_cond_tot else "✅ OK"
    stat_t = "⚠️ ACIMA" if i_pico_t > i_prot_tot or i_pico_t > i_cond_tot else "✅ OK"
    bitola_curta = bitola.split(" - ")[0]

    headers_tabela = ["<b>PARÂMETRO / MÉTRICA</b>", "<b>FASE R</b>", "<b>FASE S</b>", "<b>FASE T</b>", "<b>REFERÊNCIA</b>"]
    valores_tabela = [
        ["Corrente Medida (A)", "Pot. Apar. Medida (kVA)", f"Pot. Apar. (+{sigla}) (kVA)", f"Corr. Pico (+{sigla}) (A)", f"Cap. Cabo ({num_cabos}x {bitola_curta})", "Corrente Proteção (A)", "Status Final"],
        [f"{i_pico_r_b:.1f}", f"{p_apar_r_b/1000:.1f}", f"{p_apar_r/1000:.1f}", f"{i_pico_r:.1f}", f"{i_cond_tot:.1f}", f"{i_prot_tot:.1f}", stat_r],
        [f"{i_pico_s_b:.1f}", f"{p_apar_s_b/1000:.1f}", f"{p_apar_s/1000:.1f}", f"{i_pico_s:.1f}", f"{i_cond_tot:.1f}", f"{i_prot_tot:.1f}", stat_s],
        [f"{i_pico_t_b:.1f}", f"{p_apar_t_b/1000:.1f}", f"{p_apar_t/1000:.1f}", f"{i_pico_t:.1f}", f"{i_cond_tot:.1f}", f"{i_prot_tot:.1f}", stat_t],
        ["Analisador Base", f"Total: {p_apar_tot_b/1000:.1f} kVA", f"Total: {p_apar_tot/1000:.1f} kVA", "Cálculo/Fase", "L. Max Condutor", "L. Max Proteção", "Avaliação"]
    ]

    st.markdown("---")
    st.subheader("📋 Quadro de Potências e Correntes - Entrada de Energia")
    
    col_n1, col_n2 = st.columns([2, 1])
    nome_img_tab1 = col_n2.text_input("Nome da imagem ao baixar:", value="Tabela_Entrada_Energia", key="nome_img_tab1")

    fig_tab = go.Figure(data=[go.Table(
        columnwidth=[3.3, 1.3, 1.3, 1.3, 2.3], 
        header=dict(values=headers_tabela, fill_color='#1E3A8A', align='center', font=dict(color='white', size=21, family="Arial Black")),
        cells=dict(values=valores_tabela, fill_color=[['#F3F4F6', '#ffffff']*4], align='center', font=dict(color='#000000', size=19, family="Arial"), height=37)
    )])
    fig_tab.update_layout(
        title=dict(text="<b>Quadro de Potências e Correntes - Entrada de Energia</b>", font=dict(size=24, color='#000000')),
        margin=dict(l=5, r=5, t=55, b=5), height=380
    ) 
    st.plotly_chart(fig_tab, use_container_width=True, config=get_config_img(nome_img_tab1))

    st.markdown("---")
    st.subheader(f"📈 Gráfico de Evolução de Correntes (Consumo Atual vs Projeção com {sigla})")
    
    col_cb1, col_cb2, col_cb3, col_name_g1 = st.columns([1, 1, 1, 2])
    show_r = col_cb1.checkbox("Exibir Fases R", value=True, key="chk_r_geral")
    show_s = col_cb2.checkbox("Exibir Fases S", value=True, key="chk_s_geral")
    show_t = col_cb3.checkbox("Exibir Fases T", value=True, key="chk_t_geral")
    nome_img_graf1 = col_name_g1.text_input("Nome da imagem ao baixar:", value="Grafico_Entrada_Energia", key="nome_img_graf1")

    fig = go.Figure()
    if show_r:
        fig.add_trace(go.Scatter(y=r_base_total_serie, mode='lines', name='Fase R (Atual)', line=dict(color='#FCA5A5', width=2, dash='dot')))
        fig.add_trace(go.Scatter(y=r_tot_serie, mode='lines+markers', name=f'Fase R (Total + {sigla})', line=dict(color='#DC2626', width=4)))
    if show_s:
        fig.add_trace(go.Scatter(y=s_base_total_serie, mode='lines', name='Fase S (Atual)', line=dict(color='#93C5FD', width=2, dash='dot')))
        fig.add_trace(go.Scatter(y=s_tot_serie, mode='lines+markers', name=f'Fase S (Total + {sigla})', line=dict(color='#2563EB', width=4)))
    if show_t:
        fig.add_trace(go.Scatter(y=t_base_total_serie, mode='lines', name='Fase T (Atual)', line=dict(color='#6EE7B7', width=2, dash='dot')))
        fig.add_trace(go.Scatter(y=t_tot_serie, mode='lines+markers', name=f'Fase T (Total + {sigla})', line=dict(color='#059669', width=4)))

    fig.add_hline(y=i_cond_tot, line_dash="dash", line_color="#D97706", line_width=3, annotation_text=f"<b>Limite Cabos ({i_cond_tot}A)</b>", annotation_font=dict(size=16, color="#D97706"))
    fig.add_hline(y=i_prot_tot, line_dash="dot", line_color="#7C3AED", line_width=3, annotation_text=f"<b>Limite Proteção ({i_prot_tot}A)</b>", annotation_font=dict(size=16, color="#7C3AED"))

    fig.update_layout(
        title=dict(text=f"<b>Perfil de Correntes por Fase - Entrada de Energia</b>", font=dict(size=24, color='#000000'), y=0.98, x=0.01, xanchor='left', yanchor='top'),
        xaxis=dict(title=dict(text="<b>Amostras / Horários</b>", font=dict(size=18, color='#000000')), tickfont=dict(size=16, color='#000000')),
        yaxis=dict(title=dict(text="<b>Corrente por Fase (A)</b>", font=dict(size=18, color='#000000')), tickfont=dict(size=16, color='#000000')),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="center", x=0.5, font=dict(size=15, color='#000000'), bgcolor="rgba(255,255,255,0.9)", borderwidth=1),
        margin=dict(l=10, r=10, t=110, b=10), template="plotly_white", height=480
    )
    st.plotly_chart(fig, use_container_width=True, config=get_config_img(nome_img_graf1))

    ultrapassou_cabo = i_max_pico > i_cond_tot
    ultrapassou_prot = i_max_pico > i_prot_tot
    status_comporta = "NÃO COMPORTA" if (ultrapassou_cabo or ultrapassou_prot) else "COMPORTA"
    
    if sigla == "AC": texto_resumo_cliente = f"O sistema elétrico da Entrada de Energia {status_comporta} o acréscimo de {int(qtd_add)} Unidades de Ar Condicionado de {btu_sel}."
    elif sigla == "VE": texto_resumo_cliente = f"O sistema elétrico da Entrada de Energia {status_comporta} o acréscimo de {int(qtd_add)} Carregadores Veiculares de {fmt(p_kw)}KW."
    else: texto_resumo_cliente = f"O sistema elétrico da Entrada de Energia {status_comporta} o acréscimo simultâneo de {int(qtd_ac_misto)} máquinas de ar-condicionado de {btu_sel_misto} e {int(qtd_ve_misto)} carregadores veiculares de {fmt(p_kw_ve)} kW."

    st.markdown("📋 **Resumo da Simulação (Pronto para Cópia):**")
    st.code(texto_resumo_cliente, language="text")

# --- ABA 2 ---
with tab2:
    st.header("🏢 2. Quadro Administrativo (ADM)")
    sigla_a = sigla_estudo_global

    file_a = st.file_uploader("📂 Arraste e solte o arquivo Excel (.xlsx) ou CSV do Quadro ADM:", type=["xlsx", "csv"], key=f"f_a_{st.session_state['reset_key']}")
    serie_r_base_a, serie_s_base_a, serie_t_base_a = pd.Series([31.46, 28.0, 29.5]), pd.Series([23.06, 21.0, 22.5]), pd.Series([30.53, 27.5, 29.0])

    if "a_serie_r" in st.session_state["arquivos_data"]:
        serie_r_base_a = st.session_state["arquivos_data"]["a_serie_r"]
        serie_s_base_a = st.session_state["arquivos_data"]["a_serie_s"]
        serie_t_base_a = st.session_state["arquivos_data"]["a_serie_t"]
        if file_a is None: st.info("ℹ️ Dados do Excel ADM recuperados do relatório salvo.")

    if file_a is not None:
        try:
            df_u_adm = pd.read_csv(file_a) if file_a.name.endswith(".csv") else pd.read_excel(file_a, sheet_name=0)
            sr, ss, st_ser = extrair_dados_completos(df_u_adm)
            if sr is not None and len(sr) > 0:
                serie_r_base_a, serie_s_base_a, serie_t_base_a = sr, ss, st_ser
                st.session_state["arquivos_data"].update({"a_serie_r": sr, "a_serie_s": ss, "a_serie_t": st_ser})
                st.success("✅ Medições lidas automaticamente!")
        except: st.warning("⚠️ Usando dados padrão de demonstração para o ADM.")

    col1, col2 = st.columns(2)
    if "a_bitola" not in st.session_state: st.session_state["a_bitola"] = list(TABELA_CABOS.keys())[INDEX_PADRAO]
    if "a_cap" not in st.session_state: st.session_state["a_cap"] = float(TABELA_CABOS[st.session_state["a_bitola"]])

    with col1:
        num_cabos_adm = st.number_input("Número de cabos por fase:", min_value=1, value=1, step=1, key="a_cabos")
        bitola_adm = st.selectbox("Bitola do Condutor ADM:", list(TABELA_CABOS.keys()), key="a_bitola", on_change=update_cap_adm)
        i_capacidade_cabo_adm = st.number_input("Capacidade do cabo por fase (A):", key="a_cap", step=1.0)
        i_protecao_adm = st.number_input("Corrente do Dispositivo de Proteção por fase (A):", value=250.0, key="a_prot")
        tensao_fase_adm = st.number_input("Tensão de Fase (V):", value=127.0, key="a_v")

    min_len_a = max(1, min(len(serie_r_base_a), len(serie_s_base_a), len(serie_t_base_a)))
    ir_am_max_a = serie_r_base_a.iloc[:min_len_a].max()
    is_am_max_a = serie_s_base_a.iloc[:min_len_a].max()
    it_am_max_a = serie_t_base_a.iloc[:min_len_a].max()

    i_pico_r_base_a = ir_am_max_a * num_cabos_adm
    i_pico_s_base_a = is_am_max_a * num_cabos_adm
    i_pico_t_base_a = it_am_max_a * num_cabos_adm
    i_max_pico_base_a = max(i_pico_r_base_a, i_pico_s_base_a, i_pico_t_base_a)

    p_apar_r_base_a = i_pico_r_base_a * tensao_fase_adm
    p_apar_s_base_a = i_pico_s_base_a * tensao_fase_adm
    p_apar_t_base_a = i_pico_t_base_a * tensao_fase_adm
    p_apar_total_base_a = p_apar_r_base_a + p_apar_s_base_a + p_apar_t_base_a

    i_cond_total_a = i_capacidade_cabo_adm * num_cabos_adm
    i_prot_total_a = i_protecao_adm * num_cabos_adm
    
    pct_condutor_base_a = (i_max_pico_base_a / i_cond_total_a) * 100 if i_cond_total_a > 0 else 0
    pct_dispositivo_base_a = (i_max_pico_base_a / i_prot_total_a) * 100 if i_prot_total_a > 0 else 0
    disp_restante_base_a = i_prot_total_a - i_max_pico_base_a
    bitola_texto_a = bitola_adm.replace(" mm² - ", "mm²-")

    p_disp_prot_total_a = max(0.0, (i_prot_total_a - i_max_pico_base_a) * tensao_fase_adm) * 3
    p_disp_cond_total_a = max(0.0, (i_cond_total_a - i_max_pico_base_a) * tensao_fase_adm) * 3
    p_disp_menor_kw_a = min(p_disp_prot_total_a, p_disp_cond_total_a) / 1000.0

    texto_analise_adm = f"""As medições realizadas com o analisador de energia indicaram as correntes de amostragem máximas de {fmt(ir_am_max_a)}A na fase R, {fmt(is_am_max_a)}A na fase S e {fmt(it_am_max_a)}A na fase T.
O quadro administrativo existente conta com {num_cabos_adm} dispositivos de proteção, dessa forma, as correntes de pico consideradas totais do sistema são: {fmt(i_pico_r_base_a)}A na fase R, {fmt(i_pico_s_base_a)}A na fase S e {fmt(i_pico_t_base_a)}A na fase T.
A alimentação do sistema é realizada por condutor de seção estimada {bitola_texto_a}, que possui uma capacidade teórica de condução de corrente na ordem de {fmt(i_capacidade_cabo_adm, 0)}A (por fase) em condições usuais de instalação. Dessa forma, a maior corrente de pico medida ({fmt(i_max_pico_base_a)}A) representa aproximadamente {fmt(pct_condutor_base_a)}% da capacidade do condutor.
Considerando a proteção do quadro administrativo ({num_cabos_adm} x {fmt(i_protecao_adm, 0)} = {fmt(i_prot_total_a, 0)}A), verifica-se que a maior corrente de pico medida ({fmt(i_max_pico_base_a)}A) corresponde a aproximadamente {fmt(pct_dispositivo_base_a)}% da capacidade nominal do dispositivo, restando uma capacidade disponível na ordem de {fmt(disp_restante_base_a)}A na fase analisada.
Portanto, conclui-se que existe uma potência disponível de {fmt(p_disp_menor_kw_a)} kW no quadro administrativo."""

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("📝 **Análise Completa do Quadro Administrativo:**")
    st.success(texto_analise_adm)
    st.code(texto_analise_adm, language="text")

    st.markdown("---")
    if sigla_a == "AC":
        st.subheader("❄️ Simulador de Cargas AC (Quadro Administrativo)")
        qtd_carregadores_a = st.number_input("Quantidade de Ar Condicionado a Adicionar (X):", min_value=0, value=1, step=1, key="a_qtd_ac")
        btu_sel_a = st.selectbox("Potência do Ar Condicionado:", ["9.000 BTU/h", "12.000 BTU/h", "18.000 BTU/h", "24.000 BTU/h"], key="a_btu_sel")
        if "9.000" in btu_sel_a: potencia_carregador_kw_a = 1.0
        elif "12.000" in btu_sel_a: potencia_carregador_kw_a = 1.2
        elif "18.000" in btu_sel_a: potencia_carregador_kw_a = 1.6
        else: potencia_carregador_kw_a = 2.0
        st.info(f"Potência unitária considerada para cálculo: **{potencia_carregador_kw_a:.1f} kW** ({btu_sel_a})")
        potencia_total_watts_a = qtd_carregadores_a * potencia_carregador_kw_a * 1000
    elif sigla_a == "VE":
        st.subheader("🚗 Simulador de Cargas VE (Quadro Administrativo)")
        qtd_carregadores_a = st.number_input("Quantidade de Carregadores a Adicionar (X):", min_value=0, value=1, step=1, key="a_qtd_ve")
        ve_sel_a = st.selectbox("Potência por Carregador:", ["3.700W (3.7 kW)", "7.400W (7.4 kW)", "11.000W (11.0 kW)"], key="a_ve_sel")
        if "3.700" in ve_sel_a: potencia_carregador_kw_a = 3.7
        elif "7.400" in ve_sel_a: potencia_carregador_kw_a = 7.4
        else: potencia_carregador_kw_a = 11.0
        st.info(f"Potência unitária considerada para cálculo: **{potencia_carregador_kw_a:.1f} kW**")
        potencia_total_watts_a = qtd_carregadores_a * potencia_carregador_kw_a * 1000
    else: # AC+VE
        st.subheader("⚡ Simulador de Cargas Combinadas (AC + VE - ADM)")
        col_sa1, col_sa2 = st.columns(2)
        with col_sa1:
            qtd_ac_a_misto = st.number_input("Qtd. Ar Condicionado (X):", min_value=0, value=1, step=1, key="a_qtd_ac_misto")
            btu_sel_a_misto = st.selectbox("Potência por AC:", ["9.000 BTU/h", "12.000 BTU/h", "18.000 BTU/h", "24.000 BTU/h"], key="a_btu_misto")
            p_kw_ac_a = 1.0 if "9.000" in btu_sel_a_misto else (1.2 if "12.000" in btu_sel_a_misto else (1.6 if "18.000" in btu_sel_a_misto else 2.0))
        with col_sa2:
            qtd_ve_a_misto = st.number_input("Qtd. Carregadores VE (X):", min_value=0, value=1, step=1, key="a_qtd_ve_misto")
            ve_sel_a_misto = st.selectbox("Potência por VE:", ["3.700W (3.7 kW)", "7.400W (7.4 kW)", "11.000W (11.0 kW)"], key="a_ve_misto")
            p_kw_ve_a = 3.7 if "3.700" in ve_sel_a_misto else (7.4 if "7.400" in ve_sel_a_misto else 11.0)
        
        potencia_total_watts_a = (qtd_ac_a_misto * p_kw_ac_a + qtd_ve_a_misto * p_kw_ve_a) * 1000
        st.info(f"Potência Total Adicionada: **{((qtd_ac_a_misto * p_kw_ac_a) + (qtd_ve_a_misto * p_kw_ve_a)):.1f} kW** ({qtd_ac_a_misto} ACs + {qtd_ve_a_misto} VEs)")

    corrente_por_fase_ve_a = potencia_total_watts_a / (220.0 * np.sqrt(3))

    r_base_total_serie_a = serie_r_base_a.iloc[:min_len_a] * num_cabos_adm
    s_base_total_serie_a = serie_s_base_a.iloc[:min_len_a] * num_cabos_adm
    t_base_total_serie_a = serie_t_base_a.iloc[:min_len_a] * num_cabos_adm

    r_total_a = r_base_total_serie_a + corrente_por_fase_ve_a
    s_total_a = s_base_total_serie_a + corrente_por_fase_ve_a
    t_total_a = t_base_total_serie_a + corrente_por_fase_ve_a

    i_pico_r_a = float(r_total_a.max()) if len(r_total_a) > 0 else 0.0
    i_pico_s_a = float(s_total_a.max()) if len(s_total_a) > 0 else 0.0
    i_pico_t_a = float(t_total_a.max()) if len(t_total_a) > 0 else 0.0
    i_max_pico_a = max(i_pico_r_a, i_pico_s_a, i_pico_t_a)

    p_apar_r_a, p_apar_s_a, p_apar_t_a = i_pico_r_a * tensao_fase_adm, i_pico_s_a * tensao_fase_adm, i_pico_t_a * tensao_fase_adm
    p_apar_total_a = p_apar_r_a + p_apar_s_a + p_apar_t_a

    st.session_state["serie_r_adm"] = r_base_total_serie_a
    st.session_state["serie_s_adm"] = s_base_total_serie_a
    st.session_state["serie_t_adm"] = t_base_total_serie_a

    st.session_state["dados_adm"] = {
        "i_pico_max": i_max_pico_a, "p_apar_total": p_apar_total_a,
        "p_disp_prot_total": p_disp_prot_total_a, "p_disp_cond_total": p_disp_cond_total_a,
        "p_disp_menor_kva": p_disp_menor_kw_a,
        "bitola": bitola_adm, "i_cap_cabo": i_cond_total_a, "i_protecao": i_prot_total_a,
        "pct_condutor": (i_max_pico_a / i_cond_total_a) * 100 if i_cond_total_a > 0 else 0,
        "pct_dispositivo": (i_max_pico_a / i_prot_total_a) * 100 if i_prot_total_a > 0 else 0,
        "disp_restante": i_prot_total_a - i_max_pico_a, "sigla_tipo": sigla_a
    }

    stat_r_a = "⚠️ ACIMA" if i_pico_r_a > i_prot_total_a or i_pico_r_a > i_cond_total_a else "✅ OK"
    stat_s_a = "⚠️ ACIMA" if i_pico_s_a > i_prot_total_a or i_pico_s_a > i_cond_total_a else "✅ OK"
    stat_t_a = "⚠️ ACIMA" if i_pico_t_a > i_prot_total_a or i_pico_t_a > i_cond_total_a else "✅ OK"
    b_c_a = bitola_adm.split(" - ")[0]

    val_tab_a = [
        ["Corrente Medida (A)", "Pot. Apar. Medida (kVA)", f"Pot. Apar. (+{sigla_a}) (kVA)", f"Corr. Pico (+{sigla_a}) (A)", f"Cap. Cabo ({num_cabos_adm}x {b_c_a})", "Corrente Proteção (A)", "Status Final"],
        [f"{i_pico_r_base_a:.1f}", f"{p_apar_r_base_a/1000:.1f}", f"{p_apar_r_a/1000:.1f}", f"{i_pico_r_a:.1f}", f"{i_cond_total_a:.1f}", f"{i_prot_total_a:.1f}", stat_r_a],
        [f"{i_pico_s_base_a:.1f}", f"{p_apar_s_base_a/1000:.1f}", f"{p_apar_s_a/1000:.1f}", f"{i_pico_s_a:.1f}", f"{i_cond_total_a:.1f}", f"{i_prot_total_a:.1f}", stat_s_a],
        [f"{i_pico_t_base_a:.1f}", f"{p_apar_t_base_a/1000:.1f}", f"{p_apar_t_a/1000:.1f}", f"{i_pico_t_a:.1f}", f"{i_cond_total_a:.1f}", f"{i_prot_total_a:.1f}", stat_t_a],
        ["Analisador Base", f"Total: {p_apar_total_base_a/1000:.1f} kVA", f"Total: {p_apar_total_a/1000:.1f} kVA", "Cálculo/Fase", "L. Max Condutor", "L. Max Proteção", "Avaliação"]
    ]

    st.markdown("---")
    st.subheader("📋 Quadro de Potências e Correntes - Quadro Administrativo")
    
    col_na1, col_na2 = st.columns([2, 1])
    nome_img_tab2 = col_na2.text_input("Nome da imagem ao baixar:", value="Tabela_Quadro_ADM", key="nome_img_tab2")

    fig_tab_a = go.Figure(data=[go.Table(
        columnwidth=[3.3, 1.3, 1.3, 1.3, 2.3],
        header=dict(values=headers_tabela, fill_color='#1E3A8A', align='center', font=dict(color='white', size=21, family="Arial Black")),
        cells=dict(values=val_tab_a, fill_color=[['#F3F4F6', '#ffffff']*4], align='center', font=dict(color='#000000', size=19, family="Arial"), height=37)
    )])
    fig_tab_a.update_layout(
        title=dict(text="<b>Quadro de Potências e Correntes - ADM</b>", font=dict(size=24, color='#000000')),
        margin=dict(l=5, r=5, t=55, b=5), height=380
    )
    st.plotly_chart(fig_tab_a, use_container_width=True, config=get_config_img(nome_img_tab2))

    st.markdown("---")
    st.subheader(f"📈 Gráfico de Evolução de Correntes (Consumo Atual vs Projeção com {sigla_a})")
    
    col_cb1_a, col_cb2_a, col_cb3_a, col_name_g2 = st.columns([1, 1, 1, 2])
    show_r_a = col_cb1_a.checkbox("Exibir Fases R (ADM)", value=True, key="chk_r_adm")
    show_s_a = col_cb2_a.checkbox("Exibir Fases S (ADM)", value=True, key="chk_s_adm")
    show_t_a = col_cb3_a.checkbox("Exibir Fases T (ADM)", value=True, key="chk_t_adm")
    nome_img_graf2 = col_name_g2.text_input("Nome da imagem ao baixar:", value="Grafico_Quadro_ADM", key="nome_img_graf2")

    fig_a = go.Figure()
    if show_r_a:
        fig_a.add_trace(go.Scatter(y=r_base_total_serie_a, mode='lines', name='Fase R (Atual)', line=dict(color='#FCA5A5', width=2, dash='dot')))
        fig_a.add_trace(go.Scatter(y=r_total_a, mode='lines+markers', name=f'Fase R (Total + {sigla_a})', line=dict(color='#DC2626', width=4)))
    if show_s_a:
        fig_a.add_trace(go.Scatter(y=s_base_total_serie_a, mode='lines', name='Fase S (Atual)', line=dict(color='#93C5FD', width=2, dash='dot')))
        fig_a.add_trace(go.Scatter(y=s_total_a, mode='lines+markers', name=f'Fase S (Total + {sigla_a})', line=dict(color='#2563EB', width=4)))
    if show_t_a:
        fig_a.add_trace(go.Scatter(y=t_base_total_serie_a, mode='lines', name='Fase T (Atual)', line=dict(color='#6EE7B7', width=2, dash='dot')))
        fig_a.add_trace(go.Scatter(y=t_total_a, mode='lines+markers', name=f'Fase T (Total + {sigla_a})', line=dict(color='#059669', width=4)))

    fig_a.add_hline(y=i_cond_total_a, line_dash="dash", line_color="#D97706", line_width=3, annotation_text=f"<b>Limite Cabos ({i_cond_total_a}A)</b>", annotation_font=dict(size=16, color="#D97706"))
    fig_a.add_hline(y=i_prot_total_a, line_dash="dot", line_color="#7C3AED", line_width=3, annotation_text=f"<b>Limite Proteção ({i_prot_total_a}A)</b>", annotation_font=dict(size=16, color="#7C3AED"))

    fig_a.update_layout(
        title=dict(text=f"<b>Perfil de Correntes por Fase - ADM</b>", font=dict(size=24, color='#000000'), y=0.98, x=0.01, xanchor='left', yanchor='top'),
        xaxis=dict(title=dict(text="<b>Amostras / Horários</b>", font=dict(size=18, color='#000000')), tickfont=dict(size=16, color='#000000')),
        yaxis=dict(title=dict(text="<b>Corrente por Fase (A)</b>", font=dict(size=18, color='#000000')), tickfont=dict(size=16, color='#000000')),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="center", x=0.5, font=dict(size=15, color='#000000'), bgcolor="rgba(255,255,255,0.9)", borderwidth=1),
        margin=dict(l=10, r=10, t=110, b=10), template="plotly_white", height=480
    )
    st.plotly_chart(fig_a, use_container_width=True, config=get_config_img(nome_img_graf2))

    ultrapassou_cabo_a = i_max_pico_a > i_cond_total_a
    ultrapassou_prot_a = i_max_pico_a > i_prot_total_a
    status_comporta_a = "NÃO COMPORTA" if (ultrapassou_cabo_a or ultrapassou_prot_a) else "COMPORTA"
    
    if sigla_a == "AC": texto_resumo_cliente_a = f"O sistema elétrico do Quadro Administrativo {status_comporta_a} o acréscimo de {int(qtd_carregadores_a)} Unidades de Ar Condicionado de {btu_sel_a}."
    elif sigla_a == "VE": texto_resumo_cliente_a = f"O sistema elétrico do Quadro Administrativo {status_comporta_a} o acréscimo de {int(qtd_carregadores_a)} Carregadores Veiculares de {fmt(potencia_carregador_kw_a)}KW."
    else: texto_resumo_cliente_a = f"O sistema elétrico do Quadro Administrativo {status_comporta_a} o acréscimo simultâneo de {int(qtd_ac_a_misto)} máquinas de ar-condicionado de {btu_sel_a_misto} e {int(qtd_ve_a_misto)} carregadores veiculares de {fmt(p_kw_ve_a)} kW."

    st.markdown("📋 **Resumo da Simulação (Pronto para Cópia):**")
    st.code(texto_resumo_cliente_a, language="text")

# --- ABA 3: CAIXA DE MEDIDORES ---
with tab3:
    st.header("⚡ 3. Caixa de Medidores")
    sigla_m = sigla_estudo_global

    c_m1, c_m2 = st.columns(2)
    qtd_total_apts = c_m1.number_input("Quantidade total de unidades do condomínio:", min_value=1, value=50, step=1, key="m_qtd_apt")
    qtd_unid_caixa = c_m2.number_input("Quantidade de unidades na caixa de medidores:", min_value=1, value=16, step=1, key="m_qtd_caixa")

    col1, col2 = st.columns(2)
    if "m_bitola" not in st.session_state: st.session_state["m_bitola"] = list(TABELA_CABOS.keys())[INDEX_PADRAO]
    if "m_cap" not in st.session_state: st.session_state["m_cap"] = float(TABELA_CABOS[st.session_state["m_bitola"]])

    with col1:
        num_cabos_med = st.number_input("Número de cabos por fase:", min_value=1, value=1, step=1, key="m_cabos")
        bitola_med = st.selectbox("Bitola do Condutor (Caixa de Medidores):", list(TABELA_CABOS.keys()), key="m_bitola", on_change=update_cap_med)
        i_capacidade_cabo_med = st.number_input("Capacidade do cabo por fase (A):", key="m_cap", step=1.0)
        i_protecao_med = st.number_input("Corrente do Dispositivo de Proteção por fase (A):", value=100.0, key="m_prot")
        tensao_fase_med = st.number_input("Tensão de Fase (V):", value=127.0, key="m_v")

    sr_g = st.session_state.get("serie_r_geral", pd.Series([25.0, 30.2, 31.29, 28.4, 26.1]))
    ss_g = st.session_state.get("serie_s_geral", pd.Series([4.5, 5.2, 5.81, 5.0, 4.8]))
    st_g = st.session_state.get("serie_t_geral", pd.Series([26.0, 31.0, 32.16, 29.5, 27.0]))

    sr_a = st.session_state.get("serie_r_adm", pd.Series([31.46, 28.0, 29.5]))
    ss_a = st.session_state.get("serie_s_adm", pd.Series([23.06, 21.0, 22.5]))
    st_a = st.session_state.get("serie_t_adm", pd.Series([30.53, 27.5, 29.0]))

    min_l_m = min(len(sr_g), len(sr_a))
    sr_g_sub = sr_g.iloc[:min_l_m].reset_index(drop=True)
    sr_a_sub = sr_a.iloc[:min_l_m].reset_index(drop=True)
    ss_g_sub = ss_g.iloc[:min_l_m].reset_index(drop=True)
    ss_a_sub = ss_a.iloc[:min_l_m].reset_index(drop=True)
    st_g_sub = st_g.iloc[:min_l_m].reset_index(drop=True)
    st_a_sub = st_a.iloc[:min_l_m].reset_index(drop=True)

    fator_proporcao = (qtd_unid_caixa / qtd_total_apts) if qtd_total_apts > 0 else 0

    serie_r_med = (sr_g_sub - sr_a_sub).clip(lower=0) * fator_proporcao
    serie_s_med = (ss_g_sub - ss_a_sub).clip(lower=0) * fator_proporcao
    serie_t_med = (st_g_sub - st_a_sub).clip(lower=0) * fator_proporcao

    ir_am_max_m = serie_r_med.max() if len(serie_r_med) > 0 else 0.0
    is_am_max_m = serie_s_med.max() if len(serie_s_med) > 0 else 0.0
    it_am_max_m = serie_t_med.max() if len(serie_t_med) > 0 else 0.0

    i_pico_r_m = ir_am_max_m * num_cabos_med
    i_pico_s_m = is_am_max_m * num_cabos_med
    i_pico_t_m = it_am_max_m * num_cabos_med

    p_apar_r_m = i_pico_r_m * tensao_fase_med
    p_apar_s_m = i_pico_s_m * tensao_fase_med
    p_apar_t_m = i_pico_t_m * tensao_fase_med

    i_cond_total_m = i_capacidade_cabo_med * num_cabos_med
    i_prot_total_m = i_protecao_med * num_cabos_med
    
    pct_condutor_m = (max(i_pico_r_m, i_pico_s_m, i_pico_t_m) / i_cond_total_m) * 100 if i_cond_total_m > 0 else 0
    pct_dispositivo_m = (max(i_pico_r_m, i_pico_s_m, i_pico_t_m) / i_prot_total_m) * 100 if i_prot_total_m > 0 else 0
    disp_restante_m = i_prot_total_m - max(i_pico_r_m, i_pico_s_m, i_pico_t_m)
    bitola_texto_m = bitola_med.replace(" mm² - ", "mm²-")

    p_disp_prot_total_m = max(0.0, (i_prot_total_m - max(i_pico_r_m, i_pico_s_m, i_pico_t_m)) * tensao_fase_med) * 3
    p_disp_cond_total_m = max(0.0, (i_cond_total_m - max(i_pico_r_m, i_pico_s_m, i_pico_t_m)) * tensao_fase_med) * 3
    p_disp_menor_kw_m = min(p_disp_prot_total_m, p_disp_cond_total_m) / 1000.0

    texto_analise_med = f"""As medições proporcionais calculadas para a caixa de medidores (considerando {qtd_unid_caixa} unidades em um total de {qtd_total_apts} apartamentos) indicaram as correntes máximas de {fmt(ir_am_max_m)}A na fase R, {fmt(is_am_max_m)}A na fase S e {fmt(it_am_max_m)}A na fase T.
A caixa de medidores conta com {num_cabos_med} dispositivos de proteção, totalizando correntes de pico de {fmt(i_pico_r_m)}A na fase R, {fmt(i_pico_s_m)}A na fase S e {fmt(i_pico_t_m)}A na fase T.
A alimentação da caixa é realizada por condutor de seção {bitola_texto_m}, com capacidade teórica de condução de corrente de {fmt(i_capacidade_cabo_med, 0)}A por fase. A maior corrente de pico medida ({fmt(max(i_pico_r_m, i_pico_s_m, i_pico_t_m))}A) representa aproximadamente {fmt(pct_condutor_m)}% da capacidade do condutor.
Considerando a proteção da caixa ({num_cabos_med} x {fmt(i_protecao_med, 0)} = {fmt(i_prot_total_m, 0)}A), verifica-se que a maior corrente de pico corresponde a aproximadamente {fmt(pct_dispositivo_m)}% da capacidade nominal do dispositivo, restando uma capacidade disponível na ordem de {fmt(disp_restante_m)}A na fase analisada.
Portanto, conclui-se que existe uma potência disponível de {fmt(p_disp_menor_kw_m)} kW na caixa de medidores."""

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("📝 **Análise Completa da Caixa de Medidores:**")
    st.success(texto_analise_med)
    st.code(texto_analise_med, language="text")

    st.markdown("---")
    if sigla_m == "AC":
        st.subheader("❄️ Simulador de Cargas AC (Caixa de Medidores)")
        qtd_carregadores_m = st.number_input("Quantidade de Ar Condicionado a Adicionar (X):", min_value=0, value=1, step=1, key="m_qtd_ac")
        btu_sel_m = st.selectbox("Potência do Ar Condicionado:", ["9.000 BTU/h", "12.000 BTU/h", "18.000 BTU/h", "24.000 BTU/h"], key="m_btu_sel")
        if "9.000" in btu_sel_m: potencia_carregador_kw_m = 1.0
        elif "12.000" in btu_sel_m: potencia_carregador_kw_m = 1.2
        elif "18.000" in btu_sel_m: potencia_carregador_kw_m = 1.6
        else: potencia_carregador_kw_m = 2.0
        st.info(f"Potência unitária considerada para cálculo: **{potencia_carregador_kw_m:.1f} kW** ({btu_sel_m})")
        potencia_total_watts_m = qtd_carregadores_m * potencia_carregador_kw_m * 1000
    elif sigla_m == "VE":
        st.subheader("🚗 Simulador de Cargas VE (Caixa de Medidores)")
        qtd_carregadores_m = st.number_input("Quantidade de Carregadores a Adicionar (X):", min_value=0, value=1, step=1, key="m_qtd_ve")
        ve_sel_m = st.selectbox("Potência por Carregador:", ["3.700W (3.7 kW)", "7.400W (7.4 kW)", "11.000W (11.0 kW)"], key="m_ve_sel")
        if "3.700" in ve_sel_m: potencia_carregador_kw_m = 3.7
        elif "7.400" in ve_sel_m: potencia_carregador_kw_m = 7.4
        else: potencia_carregador_kw_m = 11.0
        st.info(f"Potência unitária considerada para cálculo: **{potencia_carregador_kw_m:.1f} kW**")
        potencia_total_watts_m = qtd_carregadores_m * potencia_carregador_kw_m * 1000
    else: # AC+VE
        st.subheader("⚡ Simulador de Cargas Combinadas (AC + VE - Caixa de Medidores)")
        col_sm1, col_sm2 = st.columns(2)
        with col_sm1:
            qtd_ac_m_misto = st.number_input("Qtd. Ar Condicionado (X):", min_value=0, value=1, step=1, key="m_qtd_ac_misto")
            btu_sel_m_misto = st.selectbox("Potência por AC:", ["9.000 BTU/h", "12.000 BTU/h", "18.000 BTU/h", "24.000 BTU/h"], key="m_btu_misto")
            p_kw_ac_m = 1.0 if "9.000" in btu_sel_m_misto else (1.2 if "12.000" in btu_sel_m_misto else (1.6 if "18.000" in btu_sel_m_misto else 2.0))
        with col_sm2:
            qtd_ve_m_misto = st.number_input("Qtd. Carregadores VE (X):", min_value=0, value=1, step=1, key="m_qtd_ve_misto")
            ve_sel_m_misto = st.selectbox("Potência por VE:", ["3.700W (3.7 kW)", "7.400W (7.4 kW)", "11.000W (11.0 kW)"], key="m_ve_misto")
            p_kw_ve_m = 3.7 if "3.700" in ve_sel_m_misto else (7.4 if "7.400" in ve_sel_m_misto else 11.0)
        
        potencia_total_watts_m = (qtd_ac_m_misto * p_kw_ac_m + qtd_ve_m_misto * p_kw_ve_m) * 1000
        st.info(f"Potência Total Adicionada: **{((qtd_ac_m_misto * p_kw_ac_m) + (qtd_ve_m_misto * p_kw_ve_m)):.1f} kW** ({qtd_ac_m_misto} ACs + {qtd_ve_m_misto} VEs)")

    corrente_por_fase_ve_m = potencia_total_watts_m / (220.0 * np.sqrt(3))

    r_total_m = serie_r_med * num_cabos_med + corrente_por_fase_ve_m
    s_total_m = serie_s_med * num_cabos_med + corrente_por_fase_ve_m
    t_total_m = serie_t_med * num_cabos_med + corrente_por_fase_ve_m

    i_pico_r_proj_m = float(r_total_m.max()) if len(r_total_m) > 0 else 0.0
    i_pico_s_proj_m = float(s_total_m.max()) if len(s_total_m) > 0 else 0.0
    i_pico_t_proj_m = float(t_total_m.max()) if len(t_total_m) > 0 else 0.0
    i_max_pico_proj_m = max(i_pico_r_proj_m, i_pico_s_proj_m, i_pico_t_proj_m)

    p_apar_r_m_proj, p_apar_s_m_proj, p_apar_t_m_proj = i_pico_r_proj_m * tensao_fase_med, i_pico_s_proj_m * tensao_fase_med, i_pico_t_proj_m * tensao_fase_med
    p_apar_total_m_proj = p_apar_r_m_proj + p_apar_s_m_proj + p_apar_t_m_proj

    st.session_state["dados_med"] = {
        "i_pico_max": i_max_pico_proj_m, "p_apar_total": p_apar_total_m_proj,
        "p_disp_prot_total": p_disp_prot_total_m, "p_disp_cond_total": p_disp_cond_total_m,
        "p_disp_menor_kva": p_disp_menor_kw_m,
        "bitola": bitola_med, "i_cap_cabo": i_cond_total_m, "i_protecao": i_prot_total_m,
        "pct_condutor": (i_max_pico_proj_m / i_cond_total_m) * 100 if i_cond_total_m > 0 else 0,
        "pct_dispositivo": (i_max_pico_proj_m / i_prot_total_m) * 100 if i_prot_total_m > 0 else 0,
        "disp_restante": i_prot_total_m - i_max_pico_proj_m, "sigla_tipo": sigla_m,
        "qtd_unid_caixa": qtd_unid_caixa, "qtd_total_apts": qtd_total_apts
    }

    stat_r_m = "⚠️ ACIMA" if i_pico_r_proj_m > i_prot_total_m or i_pico_r_proj_m > i_cond_total_m else "✅ OK"
    stat_s_m = "⚠️ ACIMA" if i_pico_s_proj_m > i_prot_total_m or i_pico_s_proj_m > i_cond_total_m else "✅ OK"
    stat_t_m = "⚠️ ACIMA" if i_pico_t_proj_m > i_prot_total_m or i_pico_t_proj_m > i_cond_total_m else "✅ OK"
    b_c_m = bitola_med.split(" - ")[0]

    val_tab_m = [
        ["Corrente Medida (A)", "Pot. Apar. Medida (kVA)", f"Pot. Apar. (+{sigla_m}) (kVA)", f"Corr. Pico (+{sigla_m}) (A)", f"Cap. Cabo ({num_cabos_med}x {b_c_m})", "Corrente Proteção (A)", "Status Final"],
        [f"{i_pico_r_m:.1f}", f"{p_apar_r_m/1000:.1f}", f"{p_apar_r_m_proj/1000:.1f}", f"{i_pico_r_proj_m:.1f}", f"{i_cond_total_m:.1f}", f"{i_prot_total_m:.1f}", stat_r_m],
        [f"{i_pico_s_m:.1f}", f"{p_apar_s_m/1000:.1f}", f"{p_apar_s_m_proj/1000:.1f}", f"{i_pico_s_proj_m:.1f}", f"{i_cond_total_m:.1f}", f"{i_prot_total_m:.1f}", stat_s_m],
        [f"{i_pico_t_m:.1f}", f"{p_apar_t_m/1000:.1f}", f"{p_apar_t_m_proj/1000:.1f}", f"{i_pico_t_proj_m:.1f}", f"{i_cond_total_m:.1f}", f"{i_prot_total_m:.1f}", stat_t_m],
        ["Cálculo Proporcional", f"Total: {p_apar_r_m + p_apar_s_m + p_apar_t_m/1000:.1f} kVA", f"Total: {p_apar_total_m_proj/1000:.1f} kVA", "Cálculo/Fase", "L. Max Condutor", "L. Max Proteção", "Avaliação"]
    ]

    st.markdown("---")
    st.subheader("📋 Quadro de Potências e Correntes - Caixa de Medidores")
    
    col_nm1, col_nm2 = st.columns([2, 1])
    nome_img_tab3 = col_nm2.text_input("Nome da imagem ao baixar:", value="Tabela_Caixa_Medidores", key="nome_img_tab3")

    fig_tab_m = go.Figure(data=[go.Table(
        columnwidth=[3.3, 1.3, 1.3, 1.3, 2.3],
        header=dict(values=headers_tabela, fill_color='#1E3A8A', align='center', font=dict(color='white', size=21, family="Arial Black")),
        cells=dict(values=val_tab_m, fill_color=[['#F3F4F6', '#ffffff']*4], align='center', font=dict(color='#000000', size=19, family="Arial"), height=37)
    )])
    fig_tab_m.update_layout(
        title=dict(text="<b>Quadro de Potências e Correntes - Caixa de Medidores</b>", font=dict(size=24, color='#000000')),
        margin=dict(l=5, r=5, t=55, b=5), height=380
    )
    st.plotly_chart(fig_tab_m, use_container_width=True, config=get_config_img(nome_img_tab3))

    st.markdown("---")
    st.subheader(f"📈 Gráfico de Evolução de Correntes (Consumo Proporcional vs Projeção com {sigla_m})")
    
    col_cb1_m, col_cb2_m, col_cb3_m, col_name_g3 = st.columns([1, 1, 1, 2])
    show_r_m = col_cb1_m.checkbox("Exibir Fases R (Medidores)", value=True, key="chk_r_med")
    show_s_m = col_cb2_m.checkbox("Exibir Fases S (Medidores)", value=True, key="chk_s_med")
    show_t_m = col_cb3_m.checkbox("Exibir Fases T (Medidores)", value=True, key="chk_t_med")
    nome_img_graf3 = col_name_g3.text_input("Nome da imagem ao baixar:", value="Grafico_Caixa_Medidores", key="nome_img_graf3")

    fig_m = go.Figure()
    if show_r_m:
        fig_m.add_trace(go.Scatter(y=serie_r_med*num_cabos_med, mode='lines', name='Fase R (Proporcional)', line=dict(color='#FCA5A5', width=2, dash='dot')))
        fig_m.add_trace(go.Scatter(y=r_total_m, mode='lines+markers', name=f'Fase R (Total + {sigla_m})', line=dict(color='#DC2626', width=4)))
    if show_s_m:
        fig_m.add_trace(go.Scatter(y=serie_s_med*num_cabos_med, mode='lines', name='Fase S (Proporcional)', line=dict(color='#93C5FD', width=2, dash='dot')))
        fig_m.add_trace(go.Scatter(y=s_total_m, mode='lines+markers', name=f'Fase S (Total + {sigla_m})', line=dict(color='#2563EB', width=4)))
    if show_t_m:
        fig_m.add_trace(go.Scatter(y=serie_t_med*num_cabos_med, mode='lines', name='Fase T (Proporcional)', line=dict(color='#6EE7B7', width=2, dash='dot')))
        fig_m.add_trace(go.Scatter(y=t_total_m, mode='lines+markers', name=f'Fase T (Total + {sigla_m})', line=dict(color='#059669', width=4)))

    fig_m.add_hline(y=i_cond_total_m, line_dash="dash", line_color="#D97706", line_width=3, annotation_text=f"<b>Limite Cabos ({i_cond_total_m}A)</b>", annotation_font=dict(size=16, color="#D97706"))
    fig_m.add_hline(y=i_prot_total_m, line_dash="dot", line_color="#7C3AED", line_width=3, annotation_text=f"<b>Limite Proteção ({i_prot_total_m}A)</b>", annotation_font=dict(size=16, color="#7C3AED"))

    fig_m.update_layout(
        title=dict(text=f"<b>Perfil de Correntes por Fase - Caixa de Medidores</b>", font=dict(size=24, color='#000000'), y=0.98, x=0.01, xanchor='left', yanchor='top'),
        xaxis=dict(title=dict(text="<b>Amostras / Horários</b>", font=dict(size=18, color='#000000')), tickfont=dict(size=16, color='#000000')),
        yaxis=dict(title=dict(text="<b>Corrente por Fase (A)</b>", font=dict(size=18, color='#000000')), tickfont=dict(size=16, color='#000000')),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="center", x=0.5, font=dict(size=15, color='#000000'), bgcolor="rgba(255,255,255,0.9)", borderwidth=1),
        margin=dict(l=10, r=10, t=110, b=10), template="plotly_white", height=480
    )
    st.plotly_chart(fig_m, use_container_width=True, config=get_config_img(nome_img_graf3))

    ultrapassou_cabo_m = i_max_pico_proj_m > i_cond_total_m
    ultrapassou_prot_m = i_max_pico_proj_m > i_prot_total_m
    status_comporta_m = "NÃO COMPORTA" if (ultrapassou_cabo_m or ultrapassou_prot_m) else "COMPORTA"
    
    if sigla_m == "AC": texto_resumo_cliente_m = f"O sistema elétrico da Caixa de Medidores {status_comporta_m} o acréscimo de {int(qtd_carregadores_m)} Unidades de Ar Condicionado de {btu_sel_m}."
    elif sigla_m == "VE": texto_resumo_cliente_m = f"O sistema elétrico da Caixa de Medidores {status_comporta_m} o acréscimo de {int(qtd_carregadores_m)} Carregadores Veiculares de {fmt(potencia_carregador_kw_m)}KW."
    else: texto_resumo_cliente_m = f"O sistema elétrico da Caixa de Medidores {status_comporta_m} o acréscimo simultâneo de {int(qtd_ac_m_misto)} máquinas de ar-condicionado de {btu_sel_m_misto} e {int(qtd_ve_m_misto)} carregadores veiculares de {fmt(p_kw_ve_m)} kW."

    st.markdown("📋 **Resumo da Simulação (Pronto para Cópia):**")
    st.code(texto_resumo_cliente_m, language="text")

# --- ABA 4: LAUDO ---
with tab4:
    st.header("📝 4. Quadro Comparativo & Laudo Técnico")

    g = st.session_state.get("dados_geral", {})
    a = st.session_state.get("dados_adm", {})
    m = st.session_state.get("dados_med", {})

    if not g or not a:
        st.warning("⚠️ Acesse as Abas 1 e 2 primeiro para carregar todos os cálculos.")
    else:
        p_disp_entrada_kva = g.get("p_disp_menor_kva", 0)
        p_disp_adm_kva = a.get("p_disp_menor_kva", 0)
        p_disp_med_kva = m.get("p_disp_menor_kva", 0)

        sigla_geral = sigla_estudo_global
        x_medidores = m.get("qtd_unid_caixa", 16)
        total_unidades = m.get("qtd_total_apts", 50)

        st.subheader("📊 Quadro Geral Comparativo")
        
        col_nc1, col_nc2 = st.columns([2, 1])
        nome_img_comp = col_nc2.text_input("Nome da imagem ao baixar:", value="Quadro_Geral_Comparativo", key="nome_img_comp")

        h_comp = ["<b>SETOR ANALISADO</b>", "<b>P. APARENTE (kVA)</b>", "<b>POTÊNCIA DISPONÍVEL NO SISTEMA (kW)</b>"]
        v_comp = [
            ["Entrada de Energia (Geral)", "Quadro Administrativo (ADM)", "Caixa de Medidores"],
            [f"{g.get('p_apar_total',0)/1000:.1f} kVA", f"{a.get('p_apar_total',0)/1000:.1f} kVA", f"{m.get('p_apar_total',0)/1000:.1f} kVA"],
            [f"{p_disp_entrada_kva:.1f} kW", f"{p_disp_adm_kva:.1f} kW", f"{p_disp_med_kva:.1f} kW"]
        ]

        fig_comp = go.Figure(data=[go.Table(
            columnwidth=[2.5, 1.8, 3.5],
            header=dict(values=h_comp, fill_color='#1E3A8A', align='center', font=dict(color='white', size=21, family="Arial Black"), line=dict(width=0)),
            cells=dict(values=v_comp, fill_color=[['#F3F4F6', '#ffffff', '#F3F4F6']], align='center', font=dict(color='#000000', size=19, family="Arial"), height=37, line=dict(width=0))
        )])
        
        fig_comp.update_layout(
            title=dict(text="<b>Quadro Geral Comparativo</b>", font=dict(size=24, color='#000000')),
            margin=dict(l=5, r=5, t=55, b=0), height=220
        )
        st.plotly_chart(fig_comp, use_container_width=True, config=get_config_img(nome_img_comp))

        st.markdown("---")
        st.subheader("📄 Texto Oficial do Laudo Técnico (Passe o mouse no canto superior direito para COPIAR)")

        p_disp_entrada_80 = p_disp_entrada_kva * 0.8
        p_disp_adm_80 = p_disp_adm_kva * 0.8
        p_disp_med_80 = p_disp_med_kva * 0.8

        # --- CONSTRUÇÃO DO TEXTO DO LAUDO ---
        if sigla_geral == "AC":
            # Geral AC
            qtd_geral_9k = int(p_disp_entrada_kva // 1.0) if p_disp_entrada_kva > 0 else 0
            qtd_geral_12k = int(p_disp_entrada_kva // 1.2) if p_disp_entrada_kva > 0 else 0
            qtd_geral_18k = int(p_disp_entrada_kva // 1.6) if p_disp_entrada_kva > 0 else 0
            qtd_geral_24k = int(p_disp_entrada_kva // 2.0) if p_disp_entrada_kva > 0 else 0
            
            paragrafo_geral = f"De acordo com as medições realizadas, verificou-se que o condomínio dispõe de uma potência de {fmt(p_disp_entrada_kva)} kVA na entrada de energia. Para garantir maior segurança e confiabilidade ao sistema elétrico, recomenda-se a utilização de até 80% desse valor ({fmt(p_disp_entrada_80)} kVA), mantendo uma reserva técnica próxima de 20% para suportar eventuais incrementos de demanda sem comprometer o desempenho do sistema. A demanda disponível permite a utilização simultânea de {qtd_geral_9k} aparelhos de ar condicionado de 9.000 BTU/h, {qtd_geral_12k} aparelhos de 12.000 BTU/h, {qtd_geral_18k} aparelhos de 18.000 BTU/h ou, alternativamente, {qtd_geral_24k} aparelhos de 24.000 BTU/h."
            
            # ADM AC
            qtd_adm_9k = int(p_disp_adm_kva // 1.0) if p_disp_adm_kva > 0 else 0
            qtd_adm_12k = int(p_disp_adm_kva // 1.2) if p_disp_adm_kva > 0 else 0
            qtd_adm_18k = int(p_disp_adm_kva // 1.6) if p_disp_adm_kva > 0 else 0
            qtd_adm_24k = int(p_disp_adm_kva // 2.0) if p_disp_adm_kva > 0 else 0
            
            paragrafo_adm = f"De forma similar, o quadro administrativo apresenta uma potência disponível de aproximadamente {fmt(p_disp_adm_kva)} kVA. Sugere-se, pelos mesmos critérios de segurança operacional, limitar o uso a até 80% dessa capacidade ({fmt(p_disp_adm_80)} kVA), mantendo uma reserva técnica próxima de 20% para suportar eventuais incrementos de demanda sem comprometer o desempenho do sistema. A demanda disponível permite a utilização simultânea de {qtd_adm_9k} aparelhos de ar condicionado de 9.000 BTU/h, {qtd_adm_12k} aparelhos de 12.000 BTU/h, {qtd_adm_18k} aparelhos de 18.000 BTU/h ou, alternativamente, {qtd_adm_24k} aparelhos de 24.000 BTU/h instalados diretamente, ou em quadros derivados, do quadro administrativo."

            # Medidores AC
            qtd_med_9k = int(p_disp_med_kva // 1.0) if p_disp_med_kva > 0 else 0
            qtd_med_12k = int(p_disp_med_kva // 1.2) if p_disp_med_kva > 0 else 0
            qtd_med_18k = int(p_disp_med_kva // 1.6) if p_disp_med_kva > 0 else 0
            qtd_med_24k = int(p_disp_med_kva // 2.0) if p_disp_med_kva > 0 else 0
            
            paragrafo_med = f"Adicionalmente, as caixas com {int(x_medidores)} medidores apresentam uma potência disponível de aproximadamente {fmt(p_disp_med_kva)} kVA. A demanda disponível permite a utilização simultânea de {qtd_med_9k} aparelhos de ar condicionado de 9.000 BTU/h, {qtd_med_12k} aparelhos de 12.000 BTU/h, {qtd_med_18k} aparelhos de 18.000 BTU/h ou, alternativamente, {qtd_med_24k} aparelhos de 24.000 BTU/h nas caixas dos medidores."

        elif sigla_geral == "VE":
            # Geral VE
            qtd_geral_74 = int(p_disp_entrada_kva // 7.4) if p_disp_entrada_kva > 0 else 0
            qtd_geral_37 = int(p_disp_entrada_kva // 3.7) if p_disp_entrada_kva > 0 else 0
            paragrafo_geral = f"De acordo com as medições realizadas, verificou-se que o condomínio dispõe de uma potência de {fmt(p_disp_entrada_kva)} kVA na entrada de energia. Para garantir maior segurança e confiabilidade ao sistema elétrico, recomenda-se a utilização de até 80% desse valor ({fmt(p_disp_entrada_80)} kVA), mantendo uma reserva técnica próxima de 20% para suportar eventuais incrementos de demanda sem comprometer o desempenho do sistema. Se o sistema de gerenciamento de carga for desconsiderado, a demanda disponível permite a utilização simultânea de {qtd_geral_74} carregadores veiculares de 7400W, ou alternativamente, {qtd_geral_37} carregadores de 3700W em um quadro novo, a instalar derivado da caixa seccionadora."

            # ADM VE
            qtd_adm_74 = int(p_disp_adm_kva // 7.4) if p_disp_adm_kva > 0 else 0
            qtd_adm_37 = int(p_disp_adm_kva // 3.7) if p_disp_adm_kva > 0 else 0
            paragrafo_adm = f"De forma similar, o quadro administrativo apresenta uma potência disponível de aproximadamente {fmt(p_disp_adm_kva)} kVA. Sugere-se, pelos mesmos critérios de segurança operacional, limitar o uso a até 80% dessa capacidade ({fmt(p_disp_adm_80)} kVA), mantendo uma reserva técnica próxima de 20% para suportar eventuais incrementos de demanda sem comprometer o desempenho do sistema. Se o sistema de gerenciamento de carga for desconsiderado, a demanda disponível permite a utilização simultânea de {qtd_adm_74} carregadores veiculares de 7400W, ou alternativamente, {qtd_adm_37} carregadores de 3700W instalados diretamente, ou em quadros derivados, do quadro administrativo."

            # Medidores VE
            qtd_med_74 = int(p_disp_med_kva // 7.4) if p_disp_med_kva > 0 else 0
            qtd_med_37 = int(p_disp_med_kva // 3.7) if p_disp_med_kva > 0 else 0
            paragrafo_med = f"Adicionalmente, as caixas com {int(x_medidores)} medidores apresentam uma potência disponível de aproximadamente {fmt(p_disp_med_kva)} kVA. Se o sistema de gerenciamento de carga for desconsiderado, a demanda disponível permite a utilização simultânea de {qtd_med_74} carregadores veiculares de 7400W, ou alternativamente, {qtd_med_37} carregadores de 3700W nas caixas dos medidores."

        else: # AC+VE
            # 1. ENTRADA DE ENERGIA (GERAL)
            geral_ac_extremo_12k = int(p_disp_entrada_kva // 1.2) if p_disp_entrada_kva > 0 else 0
            geral_ac_extremo_18k = int(p_disp_entrada_kva // 1.6) if p_disp_entrada_kva > 0 else 0
            geral_ve_extremo_74 = int(p_disp_entrada_kva // 7.4) if p_disp_entrada_kva > 0 else 0
            geral_ve_extremo_37 = int(p_disp_entrada_kva // 3.7) if p_disp_entrada_kva > 0 else 0
            
            pot_2ac_12k_tot = total_unidades * (2 * 1.2)
            pot_2ac_18k_tot = total_unidades * (2 * 1.6)
            
            p_sobra_geral_12k = max(0.0, p_disp_entrada_kva - pot_2ac_12k_tot)
            p_sobra_geral_18k = max(0.0, p_disp_entrada_kva - pot_2ac_18k_tot)
            
            geral_ve_misto_12k_74 = int(p_sobra_geral_12k // 7.4)
            geral_ve_misto_12k_37 = int(p_sobra_geral_12k // 3.7)
            geral_ve_misto_18k_74 = int(p_sobra_geral_18k // 7.4)
            geral_ve_misto_18k_37 = int(p_sobra_geral_18k // 3.7)

            paragrafo_geral = f"De acordo com as medições realizadas, verificou-se que o condomínio dispõe de uma potência de {fmt(p_disp_entrada_kva)} kVA na entrada de energia. Para garantir maior segurança e confiabilidade ao sistema elétrico, recomenda-se a utilização de até 80% desse valor ({fmt(p_disp_entrada_80)} kVA), mantendo uma reserva técnica próxima de 20% para suportar eventuais incrementos de demanda sem comprometer o desempenho do sistema. " \
                              f"Em cenários isolados, se nenhum carregador veicular for instalado, é possível alimentar até {geral_ac_extremo_12k} aparelhos de ar condicionado de 12.000 BTU/h, ou alternativamente, {geral_ac_extremo_18k} aparelhos de 18.000 BTU/h. Por outro lado, caso nenhum ar condicionado seja instalado, o sistema suporta até {geral_ve_extremo_74} carregadores de 7400W, ou alternativamente, {geral_ve_extremo_37} carregadores de 3700W.\n" \
                              f"Em cenários de convivência combinada (AC+VE) considerando a totalidade de {int(total_unidades)} unidades do condomínio:\n" \
                              f"• Com 02 aparelhos de 12.000 BTU/h por unidade (demanda de {fmt(pot_2ac_12k_tot)} kW), restam {fmt(p_sobra_geral_12k)} kW disponíveis, permitindo a instalação de {geral_ve_misto_12k_74} carregadores de 7400W (ou {geral_ve_misto_12k_37} de 3700W).\n" \
                              f"• Com 02 aparelhos de 18.000 BTU/h por unidade (demanda de {fmt(pot_2ac_18k_tot)} kW), restam {fmt(p_sobra_geral_18k)} kW disponíveis, permitindo a instalação de {geral_ve_misto_18k_74} carregadores de 7400W (ou {geral_ve_misto_18k_37} de 3700W)."

            # 2. QUADRO ADMINISTRATIVO
            adm_ac_extremo_12k = int(p_disp_adm_kva // 1.2) if p_disp_adm_kva > 0 else 0
            adm_ac_extremo_18k = int(p_disp_adm_kva // 1.6) if p_disp_adm_kva > 0 else 0
            adm_ve_extremo_74 = int(p_disp_adm_kva // 7.4) if p_disp_adm_kva > 0 else 0
            adm_ve_extremo_37 = int(p_disp_adm_kva // 3.7) if p_disp_adm_kva > 0 else 0

            pot_5ac_12k = 5 * 1.2
            pot_5ac_18k = 5 * 1.6

            p_sobra_adm_12k = max(0.0, p_disp_adm_kva - pot_5ac_12k)
            p_sobra_adm_18k = max(0.0, p_disp_adm_kva - pot_5ac_18k)

            adm_ve_misto_12k_74 = int(p_sobra_adm_12k // 7.4)
            adm_ve_misto_12k_37 = int(p_sobra_adm_12k // 3.7)
            adm_ve_misto_18k_74 = int(p_sobra_adm_18k // 7.4)
            adm_ve_misto_18k_37 = int(p_sobra_adm_18k // 3.7)

            paragrafo_adm = f"De forma similar, o quadro administrativo apresenta uma potência disponível de aproximadamente {fmt(p_disp_adm_kva)} kVA. Sugere-se, pelos mesmos critérios de segurança operacional, limitar o uso a até 80% dessa capacidade ({fmt(p_disp_adm_80)} kVA), mantendo uma reserva técnica próxima de 20% para suportar eventuais incrementos de demanda sem comprometer o desempenho do sistema. " \
                            f"Isoladamente, suporta até {adm_ac_extremo_12k} aparelhos de 12.000 BTU/h, ou {adm_ac_extremo_18k} de 18.000 BTU/h (sem VEs). Por outro lado, caso nenhum ar condicionado seja instalado, suporta até {adm_ve_extremo_74} carregadores de 7400W (ou {adm_ve_extremo_37} de 3700W).\n" \
                            f"Para a infraestrutura da área comum, considerando a instalação de 5 máquinas de ar condicionado:\n" \
                            f"• Com 5 aparelhos de 12.000 BTU/h (demanda de 6,0 kW), restam {fmt(p_sobra_adm_12k)} kW disponíveis, permitindo {adm_ve_misto_12k_74} carregadores de 7400W (ou {adm_ve_misto_12k_37} de 3700W).\n" \
                            f"• Com 5 aparelhos de 18.000 BTU/h (demanda de 8,0 kW), restam {fmt(p_sobra_adm_18k)} kW disponíveis, permitindo {adm_ve_misto_18k_74} carregadores de 7400W (ou {adm_ve_misto_18k_37} de 3700W)."

            # 3. CAIXA DE MEDIDORES
            med_ac_extremo_12k = int(p_disp_med_kva // 1.2) if p_disp_med_kva > 0 else 0
            med_ac_extremo_18k = int(p_disp_med_kva // 1.6) if p_disp_med_kva > 0 else 0
            med_ve_extremo_74 = int(p_disp_med_kva // 7.4) if p_disp_med_kva > 0 else 0
            med_ve_extremo_37 = int(p_disp_med_kva // 3.7) if p_disp_med_kva > 0 else 0

            pot_2ac_12k_cx = x_medidores * (2 * 1.2)
            pot_2ac_18k_cx = x_medidores * (2 * 1.6)

            p_sobra_med_12k = max(0.0, p_disp_med_kva - pot_2ac_12k_cx)
            p_sobra_med_18k = max(0.0, p_disp_med_kva - pot_2ac_18k_cx)

            med_ve_misto_12k_74 = int(p_sobra_med_12k // 7.4)
            med_ve_misto_12k_37 = int(p_sobra_med_12k // 3.7)
            med_ve_misto_18k_74 = int(p_sobra_med_18k // 7.4)
            med_ve_misto_18k_37 = int(p_sobra_med_18k // 3.7)

            paragrafo_med = f"Adicionalmente, as caixas com {int(x_medidores)} medidores apresentam uma potência disponível de aproximadamente {fmt(p_disp_med_kva)} kVA. " \
                            f"Se nenhum carregador for instalado, a caixa comporta até {med_ac_extremo_12k} aparelhos de 12.000 BTU/h, ou {med_ac_extremo_18k} de 18.000 BTU/h. Se nenhum ar condicionado for instalado, suporta até {med_ve_extremo_74} carregadores de 7400W, ou {med_ve_extremo_37} de 3700W.\n" \
                            f"Para o cenário misto na caixa seccionadora analisada:\n" \
                            f"• Considerando 02 aparelhos de 12.000 BTU/h por unidade da caixa ({fmt(pot_2ac_12k_cx)} kW), restam {fmt(p_sobra_med_12k)} kW, possibilitando {med_ve_misto_12k_74} carregadores de 7400W (ou {med_ve_misto_12k_37} de 3700W).\n" \
                            f"• Considerando 02 aparelhos de 18.000 BTU/h por unidade da caixa ({fmt(pot_2ac_18k_cx)} kW), restam {fmt(p_sobra_med_18k)} kW, possibilitando {med_ve_misto_18k_74} carregadores de 7400W (ou {med_ve_misto_18k_37} de 3700W)."

        texto_laudo = f"{paragrafo_geral}\n\n{paragrafo_adm}\n\n{paragrafo_med}"

        st.success(texto_laudo)
        st.code(texto_laudo, language="text")

        st.markdown("---")
        st.subheader("💾 Gerenciar Nome e Salvar Relatório")
        
        n_atual = st.session_state.get("current_report_name", "")
        
        with st.expander("✏️ Alterar Nome do Relatório Atual (Requer Senha)"):
            novo_nome_input = st.text_input("Novo Nome do Relatório:", value=n_atual, key="ren_nome_inp")
            pass_confirm_ren = st.text_input("Sua Senha para Confirmar Renomeação:", type="password", key="ren_pass_inp")
            if st.button("Confirmar Alteração de Nome"):
                if not novo_nome_input.strip():
                    st.error("Digite um nome válido.")
                elif not verificar_login(st.session_state["username"], pass_confirm_ren)[0]:
                    st.error("Senha incorreta!")
                else:
                    if n_atual != "":
                        renomear_relatorio_nuvem(st.session_state["username"], n_atual, novo_nome_input)
                    st.session_state["current_report_name"] = novo_nome_input
                    st.toast("Nome do relatório alterado com sucesso!", icon="✏️")
                    st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        c_s1, c_s2 = st.columns([3, 1])
        c_s1.info(f"Relatório Atual: **{st.session_state.get('current_report_name', 'Sem nome definido')}**")
        
        if c_s2.button("💾 Salvar Progresso", use_container_width=True, type="primary"):
            nome_salvar = st.session_state.get("current_report_name", "")
            if not nome_salvar:
                st.warning("⚠️ O relatório precisa ter um nome antes de ser salvo.")
            else:
                est_salvo = {}
                keys_to_skip = ["logged_in", "username", "is_admin", "reset_key", "selectbox_historico", "sb_mes_filtro", "db_usuarios", "db_relatorios", "nuvem_iniciada"]
                for chave, valor in st.session_state.items():
                    if chave not in keys_to_skip and not chave.startswith("FormSubmitter") and not chave.startswith("file_") and not chave.startswith("btn_") and not chave.startswith("adm_") and not chave.startswith("show_modal_"):
                        est_salvo[chave] = copy.deepcopy(valor)
                
                if salvar_relatorio_nuvem(st.session_state["username"], nome_salvar, est_salvo):
                    st.toast(f"Relatório '{nome_salvar}' salvo na nuvem!", icon="✅")
                    st.rerun()
