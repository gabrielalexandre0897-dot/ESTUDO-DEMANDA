import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import copy
import sqlite3
import hashlib
import os

# Configuração da Página
st.set_page_config(page_title="Estudo de Demanda - Veículos Elétricos & Ar Condicionado", page_icon="⚡", layout="wide")

# Configuração Padrão para Download de Imagens em Alta Resolução (300 DPI / HD para Word)
CONFIG_IMAGEM_HD = {
    "toImageButtonOptions": {
        "format": "png",
        "scale": 2.5, # Aumenta a resolução para não borrar ao colar no Word
    },
    "displayModeBar": True
}

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
        font-size: 15px;
        font-weight: bold;
        border: 1px solid #1E3A8A;
    }
    .report-table td {
        padding: 10px 12px;
        text-align: center;
        border: 1px solid #D1D5DB;
        font-size: 14px;
        color: #000000;
        font-weight: 500;
    }
    .report-table tr:nth-child(even) {
        background-color: #F3F4F6;
    }
</style>
""", unsafe_allow_html=True)

# --- CONFIGURAÇÃO DE BANCO DE DADOS SQLITE ---
DB_NAME = "banco_usuarios_relatorios.db"

def init_db():
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS usuarios (
                username TEXT PRIMARY KEY,
                password TEXT NOT NULL,
                is_admin INTEGER NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS relatorios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                nome_relatorio TEXT NOT NULL,
                dados_pickle BLOB NOT NULL
            )
        ''')
        conn.commit()
        
        cursor.execute("SELECT COUNT(*) FROM usuarios")
        if cursor.fetchone()[0] == 0:
            hashed_pw = hashlib.sha256("admin123".encode()).hexdigest()
            cursor.execute("INSERT INTO usuarios (username, password, is_admin) VALUES (?, ?, ?)", ("admin", hashed_pw, 1))
            conn.commit()
    except Exception as e:
        st.error(f"Erro ao inicializar o banco de dados: {e}")
    finally:
        conn.close()

init_db()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verificar_login(username, password):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT password, is_admin FROM usuarios WHERE username = ?", (username,))
        row = cursor.fetchone()
        conn.close()
        if row and row[0] == hash_password(password):
            return True, bool(row[1])
    except Exception:
        pass
    return False, False

def cadastrar_usuario(username, password, is_admin=0):
    if not username or not password:
        return False, "Preencha usuário e senha."
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM usuarios WHERE username = ?", (username,))
        if cursor.fetchone():
            conn.close()
            return False, "Usuário já existe."
        cursor.execute("INSERT INTO usuarios (username, password, is_admin) VALUES (?, ?, ?)", 
                       (username, hash_password(password), 1 if is_admin else 0))
        conn.commit()
        conn.close()
        return True, "Usuário cadastrado com sucesso!"
    except Exception as e:
        return False, f"Erro ao cadastrar: {e}"

def excluir_usuario(username):
    if username == "admin":
        return False, "O usuário administrador principal não pode ser excluído."
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM usuarios WHERE username = ?", (username,))
        cursor.execute("DELETE FROM relatorios WHERE username = ?", (username,))
        conn.commit()
        conn.close()
        return True, "Usuário e seus relatórios excluídos com sucesso!"
    except Exception as e:
        return False, f"Erro ao excluir: {e}"

def listar_usuarios():
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT username, is_admin FROM usuarios")
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception:
        return []

def salvar_relatorio_db(username, nome_relatorio, estado_dict):
    try:
        import pickle
        dados_blob = pickle.dumps(estado_dict)
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM relatorios WHERE username = ? AND nome_relatorio = ?", (username, nome_relatorio))
        row = cursor.fetchone()
        if row:
            cursor.execute("UPDATE relatorios SET dados_pickle = ? WHERE id = ?", (dados_blob, row[0]))
        else:
            cursor.execute("INSERT INTO relatorios (username, nome_relatorio, dados_pickle) VALUES (?, ?, ?)", (username, nome_relatorio, dados_blob))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar no banco: {e}")
        return False

def carregar_relatorio_db(username, nome_relatorio):
    try:
        import pickle
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT dados_pickle FROM relatorios WHERE username = ? AND nome_relatorio = ?", (username, nome_relatorio))
        row = cursor.fetchone()
        conn.close()
        if row:
            return pickle.loads(row[0])
    except Exception:
        pass
    return None

def excluir_relatorio_db(username, nome_relatorio):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM relatorios WHERE username = ? AND nome_relatorio = ?", (username, nome_relatorio))
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False

def listar_relatorios_db(username=None):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        if username:
            cursor.execute("SELECT nome_relatorio, username FROM relatorios WHERE username = ?", (username,))
        else:
            cursor.execute("SELECT nome_relatorio, username FROM relatorios")
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception:
        return []

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
                st.session_state["logged_in"] = True
                st.session_state["username"] = user_input
                st.session_state["is_admin"] = admin_status
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

def fmt(val, dec=2):
    return f"{val:.{dec}f}".replace('.', ',')

def update_cap_geral():
    if st.session_state.get('g_bitola') in TABELA_CABOS:
        st.session_state['g_cap'] = float(TABELA_CABOS[st.session_state['g_bitola']])

def update_cap_adm():
    if st.session_state.get('a_bitola') in TABELA_CABOS:
        st.session_state['a_cap'] = float(TABELA_CABOS[st.session_state['a_bitola']])

def update_cap_med():
    if st.session_state.get('m_bitola') in TABELA_CABOS:
        st.session_state['m_cap'] = float(TABELA_CABOS[st.session_state['m_bitola']])

# Inicialização de Variáveis na Memória
if "current_report_name" not in st.session_state: st.session_state["current_report_name"] = ""
if "dados_geral" not in st.session_state: st.session_state["dados_geral"] = {}
if "dados_adm" not in st.session_state: st.session_state["dados_adm"] = {}
if "dados_med" not in st.session_state: st.session_state["dados_med"] = {}
if "reset_key" not in st.session_state: st.session_state["reset_key"] = 0
if "arquivos_data" not in st.session_state: st.session_state["arquivos_data"] = {}

def reset_app():
    st.session_state["reset_key"] += 1
    keys_to_keep = ["logged_in", "username", "is_admin", "reset_key"]
    keys_to_delete = [k for k in st.session_state.keys() if k not in keys_to_keep]
    for k in keys_to_delete:
        del st.session_state[k]
    st.session_state["dados_geral"] = {}
    st.session_state["dados_adm"] = {}
    st.session_state["dados_med"] = {}
    st.session_state["arquivos_data"] = {}
    st.session_state["current_report_name"] = ""

# --- BARRA LATERAL (MENU DE RELATÓRIOS E PERFIL) ---
st.sidebar.markdown(f"👤 **Logado como:** `{st.session_state['username']}` " + ("*(Admin)*" if st.session_state['is_admin'] else ""))
if st.sidebar.button("🚪 Sair (Logout)", use_container_width=True):
    st.session_state["logged_in"] = False
    st.session_state["username"] = ""
    st.session_state["is_admin"] = False
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("### 💾 Gerenciador de Relatórios")

if st.sidebar.button("➕ Criar Novo Relatório", type="primary", use_container_width=True):
    reset_app()
    st.rerun()

st.sidebar.markdown("---")
if st.session_state["is_admin"]:
    st.sidebar.markdown("**📂 Histórico (Visão Geral de Todos os Usuários)**")
    lista_db = listar_relatorios_db(None)
else:
    st.sidebar.markdown("**📂 Histórico Salvo (Seus Relatórios)**")
    lista_db = listar_relatorios_db(st.session_state["username"])

if not lista_db:
    st.sidebar.info("Nenhum relatório salvo no momento.")
else:
    if st.session_state["is_admin"]:
        opcoes_map = {f"{item[0]} (por: {item[1]})": item for item in lista_db}
        selecao_label = st.sidebar.selectbox("Selecione um relatório:", list(opcoes_map.keys()), key="selectbox_historico")
        relatorio_selecionado, dono_relatorio = opcoes_map[selecao_label]
    else:
        opcoes_map = {item[0]: item for item in lista_db}
        selecao_label = st.sidebar.selectbox("Selecione um relatório:", list(opcoes_map.keys()), key="selectbox_historico")
        relatorio_selecionado = opcoes_map[selecao_label]
        dono_relatorio = st.session_state["username"]
    
    col_b1, col_b2 = st.sidebar.columns(2)
    with col_b1:
        if st.button("📂 Carregar", use_container_width=True, key="btn_load_action"):
            report_data = carregar_relatorio_db(dono_relatorio, relatorio_selecionado)
            if report_data:
                keys_to_keep = ["logged_in", "username", "is_admin", "reset_key", "selectbox_historico"]
                for k in list(st.session_state.keys()):
                    if k not in keys_to_keep:
                        del st.session_state[k]
                for k, v in report_data.items():
                    st.session_state[k] = copy.deepcopy(v)
                st.session_state["current_report_name"] = relatorio_selecionado
                st.session_state["reset_key"] += 1
                st.toast(f"Relatório '{relatorio_selecionado}' carregado!", icon="📂")
                st.rerun()
                
    with col_b2:
        if st.button("🗑️ Excluir", use_container_width=True, key="btn_del_action"):
            if excluir_relatorio_db(dono_relatorio, relatorio_selecionado):
                if st.session_state["current_report_name"] == relatorio_selecionado:
                    st.session_state["current_report_name"] = ""
                st.toast("Relatório apagado!", icon="🗑️")
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
        usuarios_cad = listar_usuarios()
        for u, adm in usuarios_cad:
            col_u1, col_u2 = st.columns([3, 1])
            col_u1.text(f"{u} {'(Admin)' if adm else ''}")
            if u != "admin":
                if col_u2.button("X", key=f"del_u_{u}"):
                    ok, msg = excluir_usuario(u)
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

# Extração de Dados de Arquivos
def extrair_dados_completos(df):
    try:
        cols_numericas = []
        for col in df.columns:
            serie_num = pd.to_numeric(df[col], errors='coerce').dropna()
            if len(serie_num) > 2:
                cols_numericas.append(col)
        if len(cols_numericas) >= 3:
            r = pd.to_numeric(df[cols_numericas[0]], errors='coerce').dropna().values
            s = pd.to_numeric(df[cols_numericas[1]], errors='coerce').dropna().values
            t = pd.to_numeric(df[cols_numericas[2]], errors='coerce').dropna().values
            if len(r) > 0 and len(s) > 0 and len(t) > 0:
                return pd.Series(r).astype(float), pd.Series(s).astype(float), pd.Series(t).astype(float)
    except Exception:
        pass
    return None, None, None

st.title("⚡ Estudo de Demanda Elétrica & Capacidade (VE / AC)")

tab1, tab2, tab3, tab4 = st.tabs([
    "🔌 1. Entrada de Energia (Geral)", 
    "🏢 2. Quadro Administrativo (ADM)", 
    "⚡ 3. Caixa de Medidores", 
    "📝 4. Conclusão & Laudo Técnico"
])

# --- ABA 1 ---
with tab1:
    st.header("🔌 1. Entrada de Energia (Geral)")
    
    tipo_analise = st.selectbox("Selecione o tipo de análise:", ["Veículos Elétricos (VE)", "Ar Condicionado (AC)"], key="g_tipo_analise")
    sigla_tipo = "VE" if "Veículos" in tipo_analise else "AC"

    file_geral = st.file_uploader("📂 Arraste e solte o arquivo Excel (.xlsx) ou CSV do Analisador de Energia:", type=["xlsx", "csv"], key=f"file_geral_{st.session_state['reset_key']}")
    
    serie_r_base, serie_s_base, serie_t_base = pd.Series([25.0, 30.2, 31.29, 28.4, 26.1]), pd.Series([4.5, 5.2, 5.81, 5.0, 4.8]), pd.Series([26.0, 31.0, 32.16, 29.5, 27.0])

    if "g_serie_r" in st.session_state["arquivos_data"]:
        serie_r_base = st.session_state["arquivos_data"]["g_serie_r"]
        serie_s_base = st.session_state["arquivos_data"]["g_serie_s"]
        serie_t_base = st.session_state["arquivos_data"]["g_serie_t"]
        if file_geral is None:
            st.info("ℹ️ Dados do Excel geral recuperados do relatório salvo.")

    if file_geral is not None:
        try:
            df_u = pd.read_csv(file_geral) if file_geral.name.endswith(".csv") else pd.read_excel(file_geral, sheet_name=0)
            sr, ss, st_ser = extrair_dados_completos(df_u)
            if sr is not None and len(sr) > 0:
                serie_r_base, serie_s_base, serie_t_base = sr, ss, st_ser
                st.session_state["arquivos_data"]["g_serie_r"] = sr
                st.session_state["arquivos_data"]["g_serie_s"] = ss
                st.session_state["arquivos_data"]["g_serie_t"] = st_ser
                st.success("✅ Medições carregadas com sucesso!")
        except Exception:
            st.warning("⚠️ Usando dados padrão de demonstração.")

    col1, col2 = st.columns(2)
    
    if "g_bitola" not in st.session_state: st.session_state["g_bitola"] = list(TABELA_CABOS.keys())[INDEX_PADRAO]
    if "g_cap" not in st.session_state: st.session_state["g_cap"] = float(TABELA_CABOS[st.session_state["g_bitola"]])

    with col1:
        num_cabos = st.number_input("Número de cabos por fase:", min_value=1, value=3, step=1, key="g_cabos")
        bitola_sel = st.selectbox("Bitola do Condutor:", list(TABELA_CABOS.keys()), key="g_bitola", on_change=update_cap_geral)
        i_capacidade_cabo = st.number_input("Capacidade do cabo por fase (A):", key="g_cap", step=1.0)
        i_protecao = st.number_input("Corrente do Dispositivo de Proteção por fase (A):", value=315.0, key="g_prot")
        tensao_fase = st.number_input("Tensão de Fase (V):", value=127.0, key="g_v")

    min_len = max(1, min(len(serie_r_base), len(serie_s_base), len(serie_t_base)))
    
    ir_am_max = serie_r_base.iloc[:min_len].max()
    is_am_max = serie_s_base.iloc[:min_len].max()
    it_am_max = serie_t_base.iloc[:min_len].max()

    i_pico_r_base = ir_am_max * num_cabos
    i_pico_s_base = is_am_max * num_cabos
    i_pico_t_base = it_am_max * num_cabos
    i_max_pico_base = max(i_pico_r_base, i_pico_s_base, i_pico_t_base)

    p_apar_r_base = i_pico_r_base * tensao_fase
    p_apar_s_base = i_pico_s_base * tensao_fase
    p_apar_t_base = i_pico_t_base * tensao_fase
    p_apar_total_base = p_apar_r_base + p_apar_s_base + p_apar_t_base

    i_cond_total = i_capacidade_cabo * num_cabos
    i_prot_total = i_protecao * num_cabos
    
    pct_condutor_base = (i_max_pico_base / i_cond_total) * 100 if i_cond_total > 0 else 0
    pct_dispositivo_base = (i_max_pico_base / i_prot_total) * 100 if i_prot_total > 0 else 0
    disp_restante_base = i_prot_total - i_max_pico_base
    
    bitola_texto = bitola_sel.replace(" mm² - ", "mm²-")

    p_disp_prot_total = max(0.0, (i_prot_total - i_max_pico_base) * tensao_fase) * 3
    p_disp_cond_total = max(0.0, (i_cond_total - i_max_pico_base) * tensao_fase) * 3
    p_disp_menor_kw = min(p_disp_prot_total, p_disp_cond_total) / 1000.0

    texto_analise_geral = f"""As medições realizadas com o analisador de energia indicaram as correntes de amostragem máximas de {fmt(ir_am_max)}A na fase R, {fmt(is_am_max)}A na fase S e {fmt(it_am_max)}A na fase T.
O padrão de entrada existente no condomínio conta com {num_cabos} dispositivos de proteção, dessa forma, as correntes de pico consideradas totais do sistema são: {fmt(i_pico_r_base)}A na fase R, {fmt(i_pico_s_base)}A na fase S e {fmt(i_pico_t_base)}A na fase T.
A alimentação do sistema é realizada por condutor de seção estimada {bitola_texto}, que possui uma capacidade teórica de condução de corrente na ordem de {fmt(i_capacidade_cabo, 0)}A (por fase) em condições usuais de instalação. Dessa forma, a maior corrente de pico medida ({fmt(i_max_pico_base)}A) representa aproximadamente {fmt(pct_condutor_base)}% da capacidade do condutor.
Considerando a proteção geral da entrada de energia ({num_cabos} x {fmt(i_protecao, 0)} = {fmt(i_prot_total, 0)}A), verifica-se que a maior corrente de pico medida ({fmt(i_max_pico_base)}A) corresponde a aproximadamente {fmt(pct_dispositivo_base)}% da capacidade nominal do dispositivo, restando uma capacidade disponível na ordem de {fmt(disp_restante_base)}A na fase analisada.
Portanto, conclui-se que existe uma potência disponível de {fmt(p_disp_menor_kw)} kW na entrada de energia."""

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("📝 **Análise Completa da Entrada de Energia:**")
    st.success(texto_analise_geral)
    st.code(texto_analise_geral, language="text")

    st.markdown("---")
    
    if sigla_tipo == "AC":
        st.subheader("❄️ Simulador de Cargas AC")
        qtd_carregadores = st.number_input("Quantidade de Ar Condicionado a Adicionar (X):", min_value=0, value=2, step=1, key="g_qtd_ac")
        btu_sel = st.selectbox("Potência do Ar Condicionado:", ["9.000 BTU/h", "12.000 BTU/h", "18.000 BTU/h", "24.000 BTU/h"], key="g_btu_sel")
        if "9.000" in btu_sel: potencia_carregador_kw = 1.0
        elif "12.000" in btu_sel: potencia_carregador_kw = 1.2
        elif "18.000" in btu_sel: potencia_carregador_kw = 1.6
        else: potencia_carregador_kw = 2.0
        st.info(f"Potência unitária considerada para cálculo: **{potencia_carregador_kw:.1f} kW** ({btu_sel})")
    else:
        st.subheader("🚗 Simulador de Cargas VE")
        qtd_carregadores = st.number_input("Quantidade de Carregadores a Adicionar (X):", min_value=0, value=2, step=1, key="g_qtd_ve")
        ve_sel = st.selectbox("Potência por Carregador:", ["3.700W (3.7 kW)", "7.400W (7.4 kW)", "11.000W (11.0 kW)"], key="g_ve_sel")
        if "3.700" in ve_sel: potencia_carregador_kw = 3.7
        elif "7.400" in ve_sel: potencia_carregador_kw = 7.4
        else: potencia_carregador_kw = 11.0
        st.info(f"Potência unitária considerada para cálculo: **{potencia_carregador_kw:.1f} kW**")
    
    potencia_total_ve_watts = qtd_carregadores * potencia_carregador_kw * 1000
    corrente_por_fase_ve = potencia_total_ve_watts / (220.0 * np.sqrt(3))

    r_base_total_serie = serie_r_base.iloc[:min_len] * num_cabos
    s_base_total_serie = serie_s_base.iloc[:min_len] * num_cabos
    t_base_total_serie = serie_t_base.iloc[:min_len] * num_cabos

    r_total = r_base_total_serie + corrente_por_fase_ve
    s_total = s_base_total_serie + corrente_por_fase_ve
    t_total = t_base_total_serie + corrente_por_fase_ve

    i_pico_r = float(r_total.max()) if len(r_total) > 0 else 0.0
    i_pico_s = float(s_total.max()) if len(s_total) > 0 else 0.0
    i_pico_t = float(t_total.max()) if len(t_total) > 0 else 0.0
    i_max_pico = max(i_pico_r, i_pico_s, i_pico_t)

    p_apar_r, p_apar_s, p_apar_t = i_pico_r * tensao_fase, i_pico_s * tensao_fase, i_pico_t * tensao_fase
    p_apar_total = p_apar_r + p_apar_s + p_apar_t

    st.session_state["serie_r_geral"] = r_base_total_serie
    st.session_state["serie_s_geral"] = s_base_total_serie
    st.session_state["serie_t_geral"] = t_base_total_serie

    st.session_state["dados_geral"] = {
        "i_pico_max": i_max_pico, "p_apar_total": p_apar_total,
        "p_disp_prot_total": p_disp_prot_total, "p_disp_cond_total": p_disp_cond_total,
        "p_disp_menor_kva": p_disp_menor_kw,
        "bitola": bitola_sel, "i_cap_cabo": i_cond_total, "i_protecao": i_prot_total,
        "pct_condutor": (i_max_pico / i_cond_total) * 100 if i_cond_total > 0 else 0,
        "pct_dispositivo": (i_max_pico / i_prot_total) * 100 if i_prot_total > 0 else 0,
        "disp_restante": i_prot_total - i_max_pico, "sigla_tipo": sigla_tipo
    }

    status_r = "⚠️ ULTRAPASSA" if i_pico_r > i_prot_total or i_pico_r > i_cond_total else "✅ OK"
    status_s = "⚠️ ULTRAPASSA" if i_pico_s > i_prot_total or i_pico_s > i_cond_total else "✅ OK"
    status_t = "⚠️ ULTRAPASSA" if i_pico_t > i_prot_total or i_pico_t > i_cond_total else "✅ OK"

    headers_tabela = ["<b>Parâmetro / Métrica</b>", "<b>Fase R</b>", "<b>Fase S</b>", "<b>Fase T</b>", "<b>Referência de Limite</b>"]
    valores_tabela = [
        ["Corrente Total Medida (A)", "Potência Aparente Medida (VA)", f"Potência Aparente Total + {sigla_tipo} (VA)", f"Corrente Pico Total + {sigla_tipo} (A)", f"Capacidade do Cabo ({num_cabos}x {bitola_sel})", "Corrente de Proteção Geral", "Status da Carga vs Limites"],
        [f"{i_pico_r_base:.2f} A", f"{p_apar_r_base:.2f} VA", f"{p_apar_r:.2f} VA", f"{i_pico_r:.2f} A", f"{i_cond_total:.2f} A", f"{i_prot_total:.2f} A", status_r],
        [f"{i_pico_s_base:.2f} A", f"{p_apar_s_base:.2f} VA", f"{p_apar_s:.2f} VA", f"{i_pico_s:.2f} A", f"{i_cond_total:.2f} A", f"{i_prot_total:.2f} A", status_s],
        [f"{i_pico_t_base:.2f} A", f"{p_apar_t_base:.2f} VA", f"{p_apar_t:.2f} VA", f"{i_pico_t:.2f} A", f"{i_cond_total:.2f} A", f"{i_prot_total:.2f} A", status_t],
        ["Amostragem Analisador", f"Total: {p_apar_total_base:.2f} VA", f"Total: {p_apar_total:.2f} VA", "Corrente Calculada por Fase", "Limite Máx. dos Condutores", "Limite Máx. das Proteções", "Avaliação por Fase"]
    ]

    # TABELA FORMATADA COM FONTE PRETA E MAIOR
    fig_tabela = go.Figure(data=[go.Table(
        header=dict(
            values=headers_tabela, 
            fill_color='#1E3A8A', 
            align='center', 
            font=dict(color='white', size=15)
        ),
        cells=dict(
            values=valores_tabela, 
            fill_color=[['#F3F4F6', '#ffffff', '#F9FAFB', '#ffffff', '#F9FAFB', '#ffffff', '#EFF6FF']*1], 
            align='center', 
            font=dict(color='#000000', size=14), # FONTE PRETA E MAIOR (14px)
            height=35
        )
    )])
    fig_tabela.update_layout(
        title=dict(text="<b>Quadro de Potências e Correntes - Entrada de Energia</b>", font=dict(size=18, color='#000000')), 
        margin=dict(l=10, r=10, t=50, b=10), 
        height=360
    )

    st.markdown("---")
    st.subheader("📋 Quadro de Potências e Correntes - Entrada de Energia")
    st.plotly_chart(fig_tabela, width='stretch', config=CONFIG_IMAGEM_HD)

    st.markdown("---")
    st.subheader(f"📈 Gráfico de Evolução de Correntes (Consumo Atual vs Projeção com {sigla_tipo})")

    col_cb1, col_cb2, col_cb3 = st.columns(3)
    show_r = col_cb1.checkbox("Exibir Fases R", value=True, key="chk_r_geral")
    show_s = col_cb2.checkbox("Exibir Fases S", value=True, key="chk_s_geral")
    show_t = col_cb3.checkbox("Exibir Fases T", value=True, key="chk_t_geral")

    # GRÁFICO COM LINHAS E FONTES DESTACADAS
    fig = go.Figure()
    if show_r:
        fig.add_trace(go.Scatter(y=r_base_total_serie, mode='lines', name='Fase R (Atual)', line=dict(color='#FCA5A5', width=2, dash='dot')))
        fig.add_trace(go.Scatter(y=r_total, mode='lines+markers', name=f'Fase R (Total + {sigla_tipo})', line=dict(color='#DC2626', width=3), marker=dict(size=7)))
    if show_s:
        fig.add_trace(go.Scatter(y=s_base_total_serie, mode='lines', name='Fase S (Atual)', line=dict(color='#93C5FD', width=2, dash='dot')))
        fig.add_trace(go.Scatter(y=s_total, mode='lines+markers', name=f'Fase S (Total + {sigla_tipo})', line=dict(color='#2563EB', width=3), marker=dict(size=7)))
    if show_t:
        fig.add_trace(go.Scatter(y=t_base_total_serie, mode='lines', name='Fase T (Atual)', line=dict(color='#6EE7B7', width=2, dash='dot')))
        fig.add_trace(go.Scatter(y=t_total, mode='lines+markers', name=f'Fase T (Total + {sigla_tipo})', line=dict(color='#059669', width=3), marker=dict(size=7)))

    fig.add_hline(y=i_cond_total, line_dash="dash", line_color="#D97706", line_width=2.5, annotation_text=f"<b>Limite Cabos ({i_cond_total}A)</b>", annotation_font=dict(size=13, color="#D97706"))
    fig.add_hline(y=i_prot_total, line_dash="dot", line_color="#7C3AED", line_width=2.5, annotation_text=f"<b>Limite Proteção ({i_prot_total}A)</b>", annotation_font=dict(size=13, color="#7C3AED"))

    # FORMATAÇÃO DO LAYOUT COM TEXTO PRETO E EM NEGRITO
    fig.update_layout(
        title=dict(text=f"<b>Perfil de Correntes por Fase - Entrada de Energia</b>", font=dict(size=18, color='#000000')),
        xaxis=dict(title=dict(text="<b>Amostras / Horários</b>", font=dict(size=15, color='#000000')), tickfont=dict(size=13, color='#000000')),
        yaxis=dict(title=dict(text="<b>Corrente por Fase (A)</b>", font=dict(size=15, color='#000000')), tickfont=dict(size=13, color='#000000')),
        legend=dict(font=dict(size=13, color='#000000'), bgcolor="rgba(255,255,255,0.8)", bordercolor="#000000", borderwidth=1),
        template="plotly_white",
        height=500
    )
    st.plotly_chart(fig, width='stretch', config=CONFIG_IMAGEM_HD)

    ultrapassou_cabo = i_max_pico > i_cond_total
    ultrapassou_prot = i_max_pico > i_prot_total
    status_comporta = "NÃO COMPORTA" if (ultrapassou_cabo or ultrapassou_prot) else "COMPORTA"
    
    if sigla_tipo == "AC": texto_resumo_cliente = f"O sistema elétrico da Entrada de Energia {status_comporta} o acréscimo de {int(qtd_carregadores)} Unidades de Ar Condicionado de {btu_sel}."
    else: texto_resumo_cliente = f"O sistema elétrico da Entrada de Energia {status_comporta} o acréscimo de {int(qtd_carregadores)} Carregadores Veiculares de {fmt(potencia_carregador_kw)}KW."

    st.markdown("📋 **Resumo da Simulação (Pronto para Cópia):**")
    st.code(texto_resumo_cliente, language="text")

# --- ABA 2 ---
with tab2:
    st.header("🏢 2. Quadro Administrativo (ADM)")
    
    tipo_analise_adm = st.selectbox("Selecione o tipo de análise:", ["Veículos Elétricos (VE)", "Ar Condicionado (AC)"], key="a_tipo_analise")
    sigla_tipo_adm = "VE" if "Veículos" in tipo_analise_adm else "AC"

    file_adm = st.file_uploader("📂 Arraste e solte o arquivo Excel (.xlsx) ou CSV do Quadro ADM:", type=["xlsx", "csv"], key=f"file_adm_{st.session_state['reset_key']}")
    
    serie_r_base_a, serie_s_base_a, serie_t_base_a = pd.Series([31.46, 28.0, 29.5]), pd.Series([23.06, 21.0, 22.5]), pd.Series([30.53, 27.5, 29.0])

    if "a_serie_r" in st.session_state["arquivos_data"]:
        serie_r_base_a = st.session_state["arquivos_data"]["a_serie_r"]
        serie_s_base_a = st.session_state["arquivos_data"]["a_serie_s"]
        serie_t_base_a = st.session_state["arquivos_data"]["a_serie_t"]
        if file_adm is None:
            st.info("ℹ️ Dados do Excel ADM recuperados do relatório salvo.")

    if file_adm is not None:
        try:
            df_u_adm = pd.read_csv(file_adm) if file_adm.name.endswith(".csv") else pd.read_excel(file_adm, sheet_name=0)
            sr, ss, st_ser = extrair_dados_completos(df_u_adm)
            if sr is not None and len(sr) > 0:
                serie_r_base_a, serie_s_base_a, serie_t_base_a = sr, ss, st_ser
                st.session_state["arquivos_data"]["a_serie_r"] = sr
                st.session_state["arquivos_data"]["a_serie_s"] = ss
                st.session_state["arquivos_data"]["a_serie_t"] = st_ser
            st.success("✅ Medições lidas automaticamente!")
        except Exception:
            st.warning("⚠️ Usando dados padrão de demonstração para o ADM.")

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
    if sigla_tipo_adm == "AC":
        st.subheader("❄️ Simulador de Cargas AC (Quadro Administrativo)")
        qtd_carregadores_a = st.number_input("Quantidade de Ar Condicionado a Adicionar (X):", min_value=0, value=1, step=1, key="a_qtd_ac")
        btu_sel_a = st.selectbox("Potência do Ar Condicionado:", ["9.000 BTU/h", "12.000 BTU/h", "18.000 BTU/h", "24.000 BTU/h"], key="a_btu_sel")
        if "9.000" in btu_sel_a: potencia_carregador_kw_a = 1.0
        elif "12.000" in btu_sel_a: potencia_carregador_kw_a = 1.2
        elif "18.000" in btu_sel_a: potencia_carregador_kw_a = 1.6
        else: potencia_carregador_kw_a = 2.0
        st.info(f"Potência unitária considerada para cálculo: **{potencia_carregador_kw_a:.1f} kW** ({btu_sel_a})")
    else:
        st.subheader("🚗 Simulador de Cargas VE (Quadro Administrativo)")
        qtd_carregadores_a = st.number_input("Quantidade de Carregadores a Adicionar (X):", min_value=0, value=1, step=1, key="a_qtd_ve")
        ve_sel_a = st.selectbox("Potência por Carregador:", ["3.700W (3.7 kW)", "7.400W (7.4 kW)", "11.000W (11.0 kW)"], key="a_ve_sel")
        if "3.700" in ve_sel_a: potencia_carregador_kw_a = 3.7
        elif "7.400" in ve_sel_a: potencia_carregador_kw_a = 7.4
        else: potencia_carregador_kw_a = 11.0
        st.info(f"Potência unitária considerada para cálculo: **{potencia_carregador_kw_a:.1f} kW**")
    
    potencia_total_ve_watts_a = qtd_carregadores_a * potencia_carregador_kw_a * 1000
    corrente_por_fase_ve_a = potencia_total_ve_watts_a / (220.0 * np.sqrt(3))

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
        "disp_restante": i_prot_total_a - i_max_pico_a, "sigla_tipo": sigla_tipo_adm
    }

    status_r_a = "⚠️ ULTRAPASSA" if i_pico_r_a > i_prot_total_a or i_pico_r_a > i_cond_total_a else "✅ OK"
    status_s_a = "⚠️ ULTRAPASSA" if i_pico_s_a > i_prot_total_a or i_pico_s_a > i_cond_total_a else "✅ OK"
    status_t_a = "⚠️ ULTRAPASSA" if i_pico_t_a > i_prot_total_a or i_pico_t_a > i_cond_total_a else "✅ OK"

    headers_tabela_a = ["<b>Parâmetro / Métrica</b>", "<b>Fase R</b>", "<b>Fase S</b>", "<b>Fase T</b>", "<b>Referência de Limite</b>"]
    valores_tabela_a = [
        ["Corrente Total Medida (A)", "Potência Aparente Medida (VA)", f"Potência Aparente Total + {sigla_tipo_adm} (VA)", f"Corrente Pico Total + {sigla_tipo_adm} (A)", f"Capacidade do Cabo ({num_cabos_adm}x {bitola_adm})", "Corrente de Proteção Geral", "Status da Carga vs Limites"],
        [f"{i_pico_r_base_a:.2f} A", f"{p_apar_r_base_a:.2f} VA", f"{p_apar_r_a:.2f} VA", f"{i_pico_r_a:.2f} A", f"{i_cond_total_a:.2f} A", f"{i_prot_total_a:.2f} A", status_r_a],
        [f"{i_pico_s_base_a:.2f} A", f"{p_apar_s_base_a:.2f} VA", f"{p_apar_s_a:.2f} VA", f"{i_pico_s_a:.2f} A", f"{i_cond_total_a:.2f} A", f"{i_prot_total_a:.2f} A", status_s_a],
        [f"{i_pico_t_base_a:.2f} A", f"{p_apar_t_base_a:.2f} VA", f"{p_apar_t_a:.2f} VA", f"{i_pico_t_a:.2f} A", f"{i_cond_total_a:.2f} A", f"{i_prot_total_a:.2f} A", status_t_a],
        ["Amostragem Analisador", f"Total: {p_apar_total_base_a:.2f} VA", f"Total: {p_apar_total_a:.2f} VA", "Corrente Calculada por Fase", "Limite Máx. dos Condutores", "Limite Máx. das Proteções", "Avaliação por Fase"]
    ]

    fig_tabela_a = go.Figure(data=[go.Table(
        header=dict(values=headers_tabela_a, fill_color='#1E3A8A', align='center', font=dict(color='white', size=15)),
        cells=dict(values=valores_tabela_a, fill_color=[['#F3F4F6', '#ffffff', '#F9FAFB', '#ffffff', '#F9FAFB', '#ffffff', '#EFF6FF']*1], align='center', font=dict(color='#000000', size=14), height=35)
    )])
    fig_tabela_a.update_layout(title=dict(text="<b>Quadro de Potências e Correntes - Quadro Administrativo</b>", font=dict(size=18, color='#000000')), margin=dict(l=10, r=10, t=50, b=10), height=360)

    st.markdown("---")
    st.subheader("📋 Quadro de Potências e Correntes - Quadro Administrativo")
    st.plotly_chart(fig_tabela_a, width='stretch', config=CONFIG_IMAGEM_HD)

    st.markdown("---")
    st.subheader(f"📈 Gráfico de Evolução de Correntes (Consumo Atual vs Projeção com {sigla_tipo_adm})")

    col_cb1_a, col_cb2_a, col_cb3_a = st.columns(3)
    show_r_a = col_cb1_a.checkbox("Exibir Fases R (ADM)", value=True, key="chk_r_adm")
    show_s_a = col_cb2_a.checkbox("Exibir Fases S (ADM)", value=True, key="chk_s_adm")
    show_t_a = col_cb3_a.checkbox("Exibir Fases T (ADM)", value=True, key="chk_t_adm")

    fig_a = go.Figure()
    if show_r_a:
        fig_a.add_trace(go.Scatter(y=r_base_total_serie_a, mode='lines', name='Fase R (Atual)', line=dict(color='#FCA5A5', width=2, dash='dot')))
        fig_a.add_trace(go.Scatter(y=r_total_a, mode='lines+markers', name=f'Fase R (Total + {sigla_tipo_adm})', line=dict(color='#DC2626', width=3), marker=dict(size=7)))
    if show_s_a:
        fig_a.add_trace(go.Scatter(y=s_base_total_serie_a, mode='lines', name='Fase S (Atual)', line=dict(color='#93C5FD', width=2, dash='dot')))
        fig_a.add_trace(go.Scatter(y=s_total_a, mode='lines+markers', name=f'Fase S (Total + {sigla_tipo_adm})', line=dict(color='#2563EB', width=3), marker=dict(size=7)))
    if show_t_a:
        fig_a.add_trace(go.Scatter(y=t_base_total_serie_a, mode='lines', name='Fase T (Atual)', line=dict(color='#6EE7B7', width=2, dash='dot')))
        fig_a.add_trace(go.Scatter(y=t_total_a, mode='lines+markers', name=f'Fase T (Total + {sigla_tipo_adm})', line=dict(color='#059669', width=3), marker=dict(size=7)))

    fig_a.add_hline(y=i_cond_total_a, line_dash="dash", line_color="#D97706", line_width=2.5, annotation_text=f"<b>Limite Cabos ({i_cond_total_a}A)</b>", annotation_font=dict(size=13, color="#D97706"))
    fig_a.add_hline(y=i_prot_total_a, line_dash="dot", line_color="#7C3AED", line_width=2.5, annotation_text=f"<b>Limite Proteção ({i_prot_total_a}A)</b>", annotation_font=dict(size=13, color="#7C3AED"))

    fig_a.update_layout(
        title=dict(text=f"<b>Perfil de Correntes por Fase - ADM</b>", font=dict(size=18, color='#000000')),
        xaxis=dict(title=dict(text="<b>Amostras / Horários</b>", font=dict(size=15, color='#000000')), tickfont=dict(size=13, color='#000000')),
        yaxis=dict(title=dict(text="<b>Corrente por Fase (A)</b>", font=dict(size=15, color='#000000')), tickfont=dict(size=13, color='#000000')),
        legend=dict(font=dict(size=13, color='#000000'), bgcolor="rgba(255,255,255,0.8)", bordercolor="#000000", borderwidth=1),
        template="plotly_white",
        height=500
    )
    st.plotly_chart(fig_a, width='stretch', config=CONFIG_IMAGEM_HD)

    ultrapassou_cabo_a = i_max_pico_a > i_cond_total_a
    ultrapassou_prot_a = i_max_pico_a > i_prot_total_a
    status_comporta_a = "NÃO COMPORTA" if (ultrapassou_cabo_a or ultrapassou_prot_a) else "COMPORTA"
    
    if sigla_tipo_adm == "AC": texto_resumo_cliente_a = f"O sistema elétrico do Quadro Administrativo {status_comporta_a} o acréscimo de {int(qtd_carregadores_a)} Unidades de Ar Condicionado de {btu_sel_a}."
    else: texto_resumo_cliente_a = f"O sistema elétrico do Quadro Administrativo {status_comporta_a} o acréscimo de {int(qtd_carregadores_a)} Carregadores Veiculares de {fmt(potencia_carregador_kw_a)}KW."

    st.markdown("📋 **Resumo da Simulação (Pronto para Cópia):**")
    st.code(texto_resumo_cliente_a, language="text")

# --- ABA 3: CAIXA DE MEDIDORES ---
with tab3:
    st.header("⚡ 3. Caixa de Medidores")
    
    tipo_analise_med = st.selectbox("Selecione o tipo de análise:", ["Veículos Elétricos (VE)", "Ar Condicionado (AC)"], key="m_tipo_analise")
    sigla_tipo_med = "VE" if "Veículos" in tipo_analise_med else "AC"

    col_m1, col_m2 = st.columns(2)
    with col_m1:
        qtd_total_apts = st.number_input("Quantidade total de unidades do condomínio:", min_value=1, value=50, step=1, key="m_qtd_apt")
    with col_m2:
        qtd_unid_caixa = st.number_input("Quantidade de unidades na caixa de medidores:", min_value=1, value=6, step=1, key="m_qtd_caixa")

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
    i_max_pico_m = max(i_pico_r_m, i_pico_s_m, i_pico_t_m)

    p_apar_r_m = i_pico_r_m * tensao_fase_med
    p_apar_s_m = i_pico_s_m * tensao_fase_med
    p_apar_t_m = i_pico_t_m * tensao_fase_med
    p_apar_total_m = p_apar_r_m + p_apar_s_m + p_apar_t_m

    i_cond_total_m = i_capacidade_cabo_med * num_cabos_med
    i_prot_total_m = i_protecao_med * num_cabos_med
    
    pct_condutor_m = (i_max_pico_m / i_cond_total_m) * 100 if i_cond_total_m > 0 else 0
    pct_dispositivo_m = (i_max_pico_m / i_prot_total_m) * 100 if i_prot_total_m > 0 else 0
    disp_restante_m = i_prot_total_m - i_max_pico_m
    bitola_texto_m = bitola_med.replace(" mm² - ", "mm²-")

    p_disp_prot_total_m = max(0.0, (i_prot_total_m - i_max_pico_m) * tensao_fase_med) * 3
    p_disp_cond_total_m = max(0.0, (i_cond_total_m - i_max_pico_m) * tensao_fase_med) * 3
    p_disp_menor_kw_m = min(p_disp_prot_total_m, p_disp_cond_total_m) / 1000.0

    texto_analise_med = f"""As medições proporcionais calculadas para a caixa de medidores (considerando {qtd_unid_caixa} unidades em um total de {qtd_total_apts} apartamentos) indicaram as correntes máximas de {fmt(ir_am_max_m)}A na fase R, {fmt(is_am_max_m)}A na fase S e {fmt(it_am_max_m)}A na fase T.
A caixa de medidores conta com {num_cabos_med} dispositivos de proteção, totalizando correntes de pico de {fmt(i_pico_r_m)}A na fase R, {fmt(i_pico_s_m)}A na fase S e {fmt(i_pico_t_m)}A na fase T.
A alimentação da caixa é realizada por condutor de seção {bitola_texto_m}, com capacidade teórica de condução de corrente de {fmt(i_capacidade_cabo_med, 0)}A por fase. A maior corrente de pico medida ({fmt(i_max_pico_m)}A) representa aproximadamente {fmt(pct_condutor_m)}% da capacidade do condutor.
Considerando a proteção da caixa ({num_cabos_med} x {fmt(i_protecao_med, 0)} = {fmt(i_prot_total_m, 0)}A), verifica-se que a maior corrente de pico corresponde a aproximadamente {fmt(pct_dispositivo_m)}% da capacidade nominal do dispositivo, restando uma capacidade disponível na ordem de {fmt(disp_restante_m)}A na fase analisada.
Portanto, conclui-se que existe uma potência disponível de {fmt(p_disp_menor_kw_m)} kW na caixa de medidores."""

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("📝 **Análise Completa da Caixa de Medidores:**")
    st.success(texto_analise_med)
    st.code(texto_analise_med, language="text")

    st.markdown("---")
    
    if sigla_tipo_med == "AC":
        st.subheader("❄️ Simulador de Cargas AC (Caixa de Medidores)")
        qtd_carregadores_m = st.number_input("Quantidade de Ar Condicionado a Adicionar (X):", min_value=0, value=1, step=1, key="m_qtd_ac")
        btu_sel_m = st.selectbox("Potência do Ar Condicionado:", ["9.000 BTU/h", "12.000 BTU/h", "18.000 BTU/h", "24.000 BTU/h"], key="m_btu_sel")
        if "9.000" in btu_sel_m: potencia_carregador_kw_m = 1.0
        elif "12.000" in btu_sel_m: potencia_carregador_kw_m = 1.2
        elif "18.000" in btu_sel_m: potencia_carregador_kw_m = 1.6
        else: potencia_carregador_kw_m = 2.0
        st.info(f"Potência unitária considerada para cálculo: **{potencia_carregador_kw_m:.1f} kW** ({btu_sel_m})")
    else:
        st.subheader("🚗 Simulador de Cargas VE (Caixa de Medidores)")
        qtd_carregadores_m = st.number_input("Quantidade de Carregadores a Adicionar (X):", min_value=0, value=1, step=1, key="m_qtd_ve")
        ve_sel_m = st.selectbox("Potência por Carregador:", ["3.700W (3.7 kW)", "7.400W (7.4 kW)", "11.000W (11.0 kW)"], key="m_ve_sel")
        if "3.700" in ve_sel_m: potencia_carregador_kw_m = 3.7
        elif "7.400" in ve_sel_m: potencia_carregador_kw_m = 7.4
        else: potencia_carregador_kw_m = 11.0
        st.info(f"Potência unitária considerada para cálculo: **{potencia_carregador_kw_m:.1f} kW**")
    
    potencia_total_ve_watts_m = qtd_carregadores_m * potencia_carregador_kw_m * 1000
    corrente_por_fase_ve_m = potencia_total_ve_watts_m / (220.0 * np.sqrt(3))

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
        "disp_restante": i_prot_total_m - i_max_pico_proj_m, "sigla_tipo": sigla_tipo_med
    }

    status_r_m = "⚠️ ULTRAPASSA" if i_pico_r_proj_m > i_prot_total_m or i_pico_r_proj_m > i_cond_total_m else "✅ OK"
    status_s_m = "⚠️ ULTRAPASSA" if i_pico_s_proj_m > i_prot_total_m or i_pico_s_proj_m > i_cond_total_m else "✅ OK"
    status_t_m = "⚠️ ULTRAPASSA" if i_pico_t_proj_m > i_prot_total_m or i_pico_t_proj_m > i_cond_total_m else "✅ OK"

    headers_tabela_m = ["<b>Parâmetro / Métrica</b>", "<b>Fase R</b>", "<b>Fase S</b>", "<b>Fase T</b>", "<b>Referência de Limite</b>"]
    valores_tabela_m = [
        ["Corrente Proporcional Medida (A)", "Potência Aparente Medida (VA)", f"Potência Aparente Total + {sigla_tipo_med} (VA)", f"Corrente Pico Total + {sigla_tipo_med} (A)", f"Capacidade do Cabo ({num_cabos_med}x {bitola_med})", "Corrente de Proteção Geral", "Status da Carga vs Limites"],
        [f"{i_pico_r_m:.2f} A", f"{p_apar_r_m:.2f} VA", f"{p_apar_r_m_proj:.2f} VA", f"{i_pico_r_proj_m:.2f} A", f"{i_cond_total_m:.2f} A", f"{i_prot_total_m:.2f} A", status_r_m],
        [f"{i_pico_s_m:.2f} A", f"{p_apar_s_m:.2f} VA", f"{p_apar_s_m_proj:.2f} VA", f"{i_pico_s_proj_m:.2f} A", f"{i_cond_total_m:.2f} A", f"{i_prot_total_m:.2f} A", status_s_m],
        [f"{i_pico_t_m:.2f} A", f"{p_apar_t_m:.2f} VA", f"{p_apar_t_m_proj:.2f} VA", f"{i_pico_t_proj_m:.2f} A", f"{i_cond_total_m:.2f} A", f"{i_prot_total_m:.2f} A", status_t_m],
        ["Proporcionalidade Aplicada", f"Total: {p_apar_r_m + p_apar_s_m + p_apar_t_m:.2f} VA", f"Total: {p_apar_total_m_proj:.2f} VA", "Corrente Calculada por Fase", "Limite Máx. dos Condutores", "Limite Máx. das Proteções", "Avaliação por Fase"]
    ]

    fig_tabela_m = go.Figure(data=[go.Table(
        header=dict(values=headers_tabela_m, fill_color='#1E3A8A', align='center', font=dict(color='white', size=15)),
        cells=dict(values=valores_tabela_m, fill_color=[['#F3F4F6', '#ffffff', '#F9FAFB', '#ffffff', '#F9FAFB', '#ffffff', '#EFF6FF']*1], align='center', font=dict(color='#000000', size=14), height=35)
    )])
    fig_tabela_m.update_layout(title=dict(text="<b>Quadro de Potências e Correntes - Caixa de Medidores</b>", font=dict(size=18, color='#000000')), margin=dict(l=10, r=10, t=50, b=10), height=360)

    st.markdown("---")
    st.subheader("📋 Quadro de Potências e Correntes - Caixa de Medidores")
    st.plotly_chart(fig_tabela_m, width='stretch', config=CONFIG_IMAGEM_HD)

    st.markdown("---")
    st.subheader(f"📈 Gráfico de Evolução de Correntes (Consumo Proporcional vs Projeção com {sigla_tipo_med})")

    col_cb1_m, col_cb2_m, col_cb3_m = st.columns(3)
    show_r_m = col_cb1_m.checkbox("Exibir Fases R (Medidores)", value=True, key="chk_r_med")
    show_s_m = col_cb2_m.checkbox("Exibir Fases S (Medidores)", value=True, key="chk_s_med")
    show_t_m = col_cb3_m.checkbox("Exibir Fases T (Medidores)", value=True, key="chk_t_med")

    fig_m = go.Figure()
    if show_r_m:
        fig_m.add_trace(go.Scatter(y=serie_r_med * num_cabos_med, mode='lines', name='Fase R (Proporcional)', line=dict(color='#FCA5A5', width=2, dash='dot')))
        fig_m.add_trace(go.Scatter(y=r_total_m, mode='lines+markers', name=f'Fase R (Total + {sigla_tipo_med})', line=dict(color='#DC2626', width=3), marker=dict(size=7)))
    if show_s_m:
        fig_m.add_trace(go.Scatter(y=serie_s_med * num_cabos_med, mode='lines', name='Fase S (Proporcional)', line=dict(color='#93C5FD', width=2, dash='dot')))
        fig_m.add_trace(go.Scatter(y=s_total_m, mode='lines+markers', name=f'Fase S (Total + {sigla_tipo_med})', line=dict(color='#2563EB', width=3), marker=dict(size=7)))
    if show_t_m:
        fig_m.add_trace(go.Scatter(y=serie_t_med * num_cabos_med, mode='lines', name='Fase T (Proporcional)', line=dict(color='#6EE7B7', width=2, dash='dot')))
        fig_m.add_trace(go.Scatter(y=t_total_m, mode='lines+markers', name=f'Fase T (Total + {sigla_tipo_med})', line=dict(color='#059669', width=3), marker=dict(size=7)))

    fig_m.add_hline(y=i_cond_total_m, line_dash="dash", line_color="#D97706", line_width=2.5, annotation_text=f"<b>Limite Cabos ({i_cond_total_m}A)</b>", annotation_font=dict(size=13, color="#D97706"))
    fig_m.add_hline(y=i_prot_total_m, line_dash="dot", line_color="#7C3AED", line_width=2.5, annotation_text=f"<b>Limite Proteção ({i_prot_total_m}A)</b>", annotation_font=dict(size=13, color="#7C3AED"))

    fig_m.update_layout(
        title=dict(text=f"<b>Perfil de Correntes por Fase - Caixa de Medidores</b>", font=dict(size=18, color='#000000')),
        xaxis=dict(title=dict(text="<b>Amostras / Horários</b>", font=dict(size=15, color='#000000')), tickfont=dict(size=13, color='#000000')),
        yaxis=dict(title=dict(text="<b>Corrente por Fase (A)</b>", font=dict(size=15, color='#000000')), tickfont=dict(size=13, color='#000000')),
        legend=dict(font=dict(size=13, color='#000000'), bgcolor="rgba(255,255,255,0.8)", bordercolor="#000000", borderwidth=1),
        template="plotly_white",
        height=500
    )
    st.plotly_chart(fig_m, width='stretch', config=CONFIG_IMAGEM_HD)

    ultrapassou_cabo_m = i_max_pico_proj_m > i_cond_total_m
    ultrapassou_prot_m = i_max_pico_proj_m > i_prot_total_m
    status_comporta_m = "NÃO COMPORTA" if (ultrapassou_cabo_m or ultrapassou_prot_m) else "COMPORTA"
    
    if sigla_tipo_med == "AC": texto_resumo_cliente_m = f"O sistema elétrico da Caixa de Medidores {status_comporta_m} o acréscimo de {int(qtd_carregadores_m)} Unidades de Ar Condicionado de {btu_sel_m}."
    else: texto_resumo_cliente_m = f"O sistema elétrico da Caixa de Medidores {status_comporta_m} o acréscimo de {int(qtd_carregadores_m)} Carregadores Veiculares de {fmt(potencia_carregador_kw_m)}KW."

    st.markdown("📋 **Resumo da Simulação (Pronto para Cópia):**")
    st.code(texto_resumo_cliente_m, language="text")

# --- ABA 4: CONCLUSÃO & LAUDO TÉCNICO ---
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

        sigla_geral = g.get("sigla_tipo", "VE")
        sigla_adm = a.get("sigla_tipo", "VE")
        sigla_med = m.get("sigla_tipo", "VE")

        st.subheader("📊 Quadro Geral Comparativo")
        
        headers_comp = ["<b>Setor Analisado</b>", "<b>P. Aparente Medida</b>", "<b>P. Disp. Proteção</b>", "<b>P. Disp. Condutor</b>", "<b>P. Disp. Total (100% Carga)</b>"]
        valores_comp = [
            ["Entrada de Energia (Geral)", "Quadro Administrativo (ADM)", "Caixa de Medidores"],
            [f"{g.get('p_apar_total',0)/1000:.2f} kVA", f"{a.get('p_apar_total',0)/1000:.2f} kVA", f"{m.get('p_apar_total',0)/1000:.2f} kVA"],
            [f"{g.get('p_disp_prot_total',0)/1000:.2f} kVA", f"{a.get('p_disp_prot_total',0)/1000:.2f} kVA", f"{m.get('p_disp_prot_total',0)/1000:.2f} kVA"],
            [f"{g.get('p_disp_cond_total',0)/1000:.2f} kVA", f"{a.get('p_disp_cond_total',0)/1000:.2f} kVA", f"{m.get('p_disp_cond_total',0)/1000:.2f} kVA"],
            [f"{p_disp_entrada_kva:.2f} kW", f"{p_disp_adm_kva:.2f} kW", f"{p_disp_med_kva:.2f} kW"]
        ]

        fig_comp = go.Figure(data=[go.Table(
            header=dict(values=headers_comp, fill_color='#1E3A8A', align='center', font=dict(color='white', size=15)),
            cells=dict(values=valores_comp, fill_color=[['#F3F4F6', '#ffffff', '#F9FAFB']*1], align='center', font=dict(color='#000000', size=14), height=35)
        )])
        fig_comp.update_layout(title=dict(text="<b>Quadro Geral Comparativo</b>", font=dict(size=18, color='#000000')), margin=dict(l=10, r=10, t=50, b=10), height=260)
        st.plotly_chart(fig_comp, width='stretch', config=CONFIG_IMAGEM_HD)

        st.markdown("---")
        st.subheader("📄 Texto Oficial do Laudo Técnico (Passe o mouse no canto superior direito para COPIAR)")

        p_disp_entrada_80 = p_disp_entrada_kva * 0.8
        p_disp_adm_80 = p_disp_adm_kva * 0.8
        p_disp_med_80 = p_disp_med_kva * 0.8

        # --- PARÁGRAFO 1: ENTRADA DE ENERGIA ---
        if sigla_geral == "AC":
            qtd_geral_9k = int(p_disp_entrada_kva // 1.0) if p_disp_entrada_kva > 0 else 0
            qtd_geral_12k = int(p_disp_entrada_kva // 1.2) if p_disp_entrada_kva > 0 else 0
            qtd_geral_18k = int(p_disp_entrada_kva // 1.6) if p_disp_entrada_kva > 0 else 0
            paragrafo_geral = f"De acordo com as medições realizadas, verificou-se que o condomínio dispõe de uma potência de {fmt(p_disp_entrada_kva)} kVA na entrada de energia. Para garantir maior segurança e confiabilidade ao sistema elétrico, recomenda-se a utilização de até 80% desse valor ({fmt(p_disp_entrada_80)} kVA), mantendo uma reserva técnica próxima de 20% para suportar eventuais incrementos de demanda sem comprometer o desempenho do sistema. Portanto, a entrada de energia suporta a adição de {qtd_geral_9k} máquinas de ar-condicionado de 9.000 BTU/h, {qtd_geral_12k} máquinas de 12.000 BTU/h e {qtd_geral_18k} máquinas de 18.000 BTU/h."
        else:
            qtd_geral_74 = int(p_disp_entrada_kva // 7.4) if p_disp_entrada_kva > 0 else 0
            qtd_geral_37 = int(p_disp_entrada_kva // 3.7) if p_disp_entrada_kva > 0 else 0
            paragrafo_geral = f"De acordo com as medições realizadas, verificou-se que o condomínio dispõe de uma potência de {fmt(p_disp_entrada_kva)} kVA na entrada de energia. Para garantir maior segurança e confiabilidade ao sistema elétrico, recomenda-se a utilização de até 80% desse valor ({fmt(p_disp_entrada_80)} kVA), mantendo uma reserva técnica próxima de 20% para suportar eventuais incrementos de demanda sem comprometer o desempenho do sistema. Se o sistema de gerenciamento de carga for desconsiderado, o condomínio tem a possibilidade de instalar {qtd_geral_74} carregadores veiculares de 7400W, ou alternativamente, {qtd_geral_37} carregadores de 3700W na entrada de energia."

        # --- PARÁGRAFO 2: QUADRO ADMINISTRATIVO ---
        if sigla_adm == "AC":
            qtd_adm_9k = int(p_disp_adm_kva // 1.0) if p_disp_adm_kva > 0 else 0
            qtd_adm_12k = int(p_disp_adm_kva // 1.2) if p_disp_adm_kva > 0 else 0
            qtd_adm_18k = int(p_disp_adm_kva // 1.6) if p_disp_adm_kva > 0 else 0
            paragrafo_adm = f"De forma similar, o quadro administrativo apresenta uma potência disponível de aproximadamente {fmt(p_disp_adm_kva)} kVA. Sugere-se, pelos mesmos critérios de segurança operacional, limitar o uso a até 80% dessa capacidade ({fmt(p_disp_adm_80)} kVA), mantendo uma reserva técnica próxima de 20% para suportar eventuais incrementos de demanda sem comprometer o desempenho do sistema. Portanto, a entrada de energia suporta a adição de {qtd_adm_9k} máquinas de ar-condicionado de 9.000 BTU/h, {qtd_adm_12k} máquinas de 12.000 BTU/h e {qtd_adm_18k} máquinas de 18.000 BTU/h."
        else:
            qtd_adm_74 = int(p_disp_adm_kva // 7.4) if p_disp_adm_kva > 0 else 0
            qtd_adm_37 = int(p_disp_adm_kva // 3.7) if p_disp_adm_kva > 0 else 0
            paragrafo_adm = f"De forma similar, o quadro administrativo apresenta uma potência disponível de aproximadamente {fmt(p_disp_adm_kva)} kVA. Sugere-se, pelos mesmos critérios de segurança operacional, limitar o uso a até 80% dessa capacidade ({fmt(p_disp_adm_80)} kVA), mantendo uma reserva técnica próxima de 20% para suportar eventuais incrementos de demanda sem comprometer o desempenho do sistema. Se o sistema de gerenciamento de carga for desconsiderado, o condomínio tem a possibilidade de instalar {qtd_adm_74} carregadores veiculares de 7400W, ou alternativamente, {qtd_adm_37} carregadores de 3700W no quadro administrativo."

        # --- PARÁGRAFO 3: CAIXA DE MEDIDORES ---
        if sigla_med == "AC":
            qtd_med_9k = int(p_disp_med_kva // 1.0) if p_disp_med_kva > 0 else 0
            qtd_med_12k = int(p_disp_med_kva // 1.2) if p_disp_med_kva > 0 else 0
            qtd_med_18k = int(p_disp_med_kva // 1.6) if p_disp_med_kva > 0 else 0
            paragrafo_med = f"Adicionalmente, a caixa de medidores apresenta uma potência disponível de aproximadamente {fmt(p_disp_med_kva)} kVA. Sugere-se, pelos mesmos critérios de segurança operacional, limitar o uso a até 80% dessa capacidade ({fmt(p_disp_med_80)} kVA), mantendo uma reserva técnica próxima de 20% para suportar eventuais incrementos de demanda sem comprometer o desempenho do sistema. Portanto, a entrada de energia suporta a adição de {qtd_med_9k} máquinas de ar-condicionado de 9.000 BTU/h, {qtd_med_12k} máquinas de 12.000 BTU/h e {qtd_med_18k} máquinas de 18.000 BTU/h."
        else:
            qtd_med_74 = int(p_disp_med_kva // 7.4) if p_disp_med_kva > 0 else 0
            qtd_med_37 = int(p_disp_med_kva // 3.7) if p_disp_med_kva > 0 else 0
            paragrafo_med = f"Adicionalmente, a caixa de medidores apresenta uma potência disponível de aproximadamente {fmt(p_disp_med_kva)} kVA. Sugere-se, pelos mesmos critérios de segurança operacional, limitar o uso a até 80% dessa capacidade ({fmt(p_disp_med_80)} kVA), mantendo uma reserva técnica próxima de 20% para suportar eventuais incrementos de demanda sem comprometer o desempenho do sistema. Se o sistema de gerenciamento de carga for desconsiderado, o condomínio tem a possibilidade de instalar {qtd_med_74} carregadores veiculares de 7400W, ou alternativamente, {qtd_med_37} carregadores de 3700W na caixa de medidores."

        texto_laudo = f"{paragrafo_geral}\n\n{paragrafo_adm}\n\n{paragrafo_med}"

        st.success(texto_laudo)
        st.code(texto_laudo, language="text")

        # --- SEÇÃO: SALVAR/ATUALIZAR RELATÓRIO NO DB ---
        st.markdown("---")
        st.subheader("💾 Salvar Relatório Atual")
        st.info("Salve o progresso atual vinculado à sua conta. Se mantiver o mesmo nome, o relatório será atualizado.")
        
        col_save1, col_save2 = st.columns([3, 1])
        with col_save1:
            nome_atual = st.session_state.get("current_report_name", "")
            nome_novo_relatorio = st.text_input("Nome do relatório (Ex: Condomínio XYZ - Bloco A):", value=nome_atual)
        
        with col_save2:
            st.markdown("<br>", unsafe_allow_html=True)
            is_updating = (nome_atual != "" and nome_atual == nome_novo_relatorio)
            texto_botao = "Atualizar Relatório" if is_updating else "Salvar Relatório"
            cor_botao = "primary" if is_updating else "secondary"

            if st.button(texto_botao, use_container_width=True, type=cor_botao):
                if not nome_novo_relatorio:
                    st.warning("⚠️ Digite um nome para o relatório antes de salvar.")
                else:
                    estado_salvo = {}
                    keys_to_skip = ["logged_in", "username", "is_admin", "reset_key", "selectbox_historico"]
                    for chave, valor in st.session_state.items():
                        if chave not in keys_to_skip and not chave.startswith("FormSubmitter") and not chave.startswith("file_") and not chave.startswith("btn_") and not chave.startswith("adm_"):
                            estado_salvo[chave] = copy.deepcopy(valor)
                    
                    sucesso = salvar_relatorio_db(st.session_state["username"], nome_novo_relatorio, estado_salvo)
                    if sucesso:
                        st.session_state["current_report_name"] = nome_novo_relatorio
                        if is_updating:
                            st.toast(f"Relatório '{nome_novo_relatorio}' atualizado com sucesso!", icon="🔄")
                        else:
                            st.toast(f"Relatório '{nome_novo_relatorio}' salvo na sua conta!", icon="✅")
                        st.rerun()
