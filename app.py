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

# =====================================================================
# CONFIGURAÇÃO DE EXPORTAÇÃO AJUSTADA (Sem cortes na tabela)
# =====================================================================
CONFIG_IMG_TABELA = {
    "toImageButtonOptions": {
        "format": "png", "width": 1400, "height": 380, "scale": 3
    },
    "displayModeBar": True
}
CONFIG_IMG_GRAFICO = {
    "toImageButtonOptions": {
        "format": "png", "width": 1400, "height": 380, "scale": 3
    },
    "displayModeBar": True
}

# Estilização CSS
st.markdown("""
<style>
    .report-table { width: 100%; border-collapse: collapse; font-family: Arial, sans-serif; margin: 15px 0; }
    .report-table th { background-color: #1E3A8A; color: white; padding: 12px; text-align: center; font-size: 15px; border: 1px solid #1E3A8A; }
    .report-table td { padding: 10px 12px; text-align: center; border: 1px solid #D1D5DB; font-size: 14px; color: #000000; font-weight: 500; }
    .report-table tr:nth-child(even) { background-color: #F3F4F6; }
</style>
""", unsafe_allow_html=True)

# --- CONFIGURAÇÃO DE BANCO DE DADOS SQLITE ---
DB_NAME = "banco_usuarios_relatorios.db"

def init_db():
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS usuarios (username TEXT PRIMARY KEY, password TEXT NOT NULL, is_admin INTEGER NOT NULL)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS relatorios (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL, nome_relatorio TEXT NOT NULL, dados_pickle BLOB NOT NULL)''')
        conn.commit()
        cursor.execute("SELECT COUNT(*) FROM usuarios")
        if cursor.fetchone()[0] == 0:
            hashed_pw = hashlib.sha256("admin123".encode()).hexdigest()
            cursor.execute("INSERT INTO usuarios (username, password, is_admin) VALUES (?, ?, ?)", ("admin", hashed_pw, 1))
            conn.commit()
    except Exception as e: st.error(f"Erro BD: {e}")
    finally: conn.close()

init_db()

def hash_password(password): return hashlib.sha256(password.encode()).hexdigest()

def verificar_login(username, password):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT password, is_admin FROM usuarios WHERE username = ?", (username,))
        row = cursor.fetchone()
        conn.close()
        if row and row[0] == hash_password(password): return True, bool(row[1])
    except: pass
    return False, False

def cadastrar_usuario(username, password, is_admin=0):
    if not username or not password: return False, "Preencha usuário e senha."
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM usuarios WHERE username = ?", (username,))
        if cursor.fetchone():
            conn.close()
            return False, "Usuário já existe."
        cursor.execute("INSERT INTO usuarios (username, password, is_admin) VALUES (?, ?, ?)", (username, hash_password(password), 1 if is_admin else 0))
        conn.commit()
        conn.close()
        return True, "Cadastrado com sucesso!"
    except Exception as e: return False, f"Erro: {e}"

def excluir_usuario(username):
    if username == "admin": return False, "Admin principal não pode ser excluído."
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM usuarios WHERE username = ?", (username,))
        cursor.execute("DELETE FROM relatorios WHERE username = ?", (username,))
        conn.commit()
        conn.close()
        return True, "Usuário excluído!"
    except Exception as e: return False, f"Erro: {e}"

def listar_usuarios():
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT username, is_admin FROM usuarios")
        rows = cursor.fetchall()
        conn.close()
        return rows
    except: return []

def salvar_relatorio_db(username, nome_relatorio, estado_dict):
    try:
        import pickle
        dados_blob = pickle.dumps(estado_dict)
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM relatorios WHERE username = ? AND nome_relatorio = ?", (username, nome_relatorio))
        row = cursor.fetchone()
        if row: cursor.execute("UPDATE relatorios SET dados_pickle = ? WHERE id = ?", (dados_blob, row[0]))
        else: cursor.execute("INSERT INTO relatorios (username, nome_relatorio, dados_pickle) VALUES (?, ?, ?)", (username, nome_relatorio, dados_blob))
        conn.commit()
        conn.close()
        return True
    except: return False

def carregar_relatorio_db(username, nome_relatorio):
    try:
        import pickle
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT dados_pickle FROM relatorios WHERE username = ? AND nome_relatorio = ?", (username, nome_relatorio))
        row = cursor.fetchone()
        conn.close()
        if row: return pickle.loads(row[0])
    except: pass
    return None

def excluir_relatorio_db(username, nome_relatorio):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM relatorios WHERE username = ? AND nome_relatorio = ?", (username, nome_relatorio))
        conn.commit()
        conn.close()
        return True
    except: return False

def listar_relatorios_db(username=None):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        if username: cursor.execute("SELECT nome_relatorio, username FROM relatorios WHERE username = ?", (username,))
        else: cursor.execute("SELECT nome_relatorio, username FROM relatorios")
        rows = cursor.fetchall()
        conn.close()
        return rows
    except: return []

# --- CONTROLE DE SESSÃO DE LOGIN ---
if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if "username" not in st.session_state: st.session_state["username"] = ""
if "is_admin" not in st.session_state: st.session_state["is_admin"] = False

if not st.session_state["logged_in"]:
    st.title("🔐 Acesso Restrito - Estudo de Demanda")
    with st.form("form_login"):
        user_input = st.text_input("Usuário:")
        pass_input = st.text_input("Senha:", type="password")
        if st.form_submit_button("Entrar", type="primary"):
            ok, admin_status = verificar_login(user_input, pass_input)
            if ok:
                st.session_state.update({"logged_in": True, "username": user_input, "is_admin": admin_status})
                st.rerun()
            else: st.error("Usuário ou senha incorretos.")
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

if "current_report_name" not in st.session_state: st.session_state.update({"current_report_name": "", "dados_geral": {}, "dados_adm": {}, "dados_med": {}, "reset_key": 0, "arquivos_data": {}})

def reset_app():
    st.session_state["reset_key"] += 1
    keys_to_keep = ["logged_in", "username", "is_admin", "reset_key"]
    for k in list(st.session_state.keys()):
        if k not in keys_to_keep: del st.session_state[k]
    st.session_state.update({"dados_geral": {}, "dados_adm": {}, "dados_med": {}, "arquivos_data": {}, "current_report_name": ""})

# --- BARRA LATERAL ---
st.sidebar.markdown(f"👤 **Logado:** `{st.session_state['username']}`")
if st.sidebar.button("🚪 Sair", use_container_width=True):
    st.session_state.update({"logged_in": False, "username": "", "is_admin": False})
    st.rerun()

st.sidebar.markdown("---")
if st.sidebar.button("➕ Criar Novo Relatório", type="primary", use_container_width=True):
    reset_app()
    st.rerun()

st.sidebar.markdown("---")
lista_db = listar_relatorios_db(None if st.session_state["is_admin"] else st.session_state["username"])

if not lista_db: st.sidebar.info("Nenhum relatório salvo.")
else:
    opcoes_map = {f"{i[0]} (por: {i[1]})" if st.session_state["is_admin"] else i[0]: i for i in lista_db}
    selecao = st.sidebar.selectbox("📂 Histórico:", list(opcoes_map.keys()), key="selectbox_historico")
    rel_selecionado = opcoes_map[selecao][0] if st.session_state["is_admin"] else opcoes_map[selecao][0]
    dono = opcoes_map[selecao][1] if st.session_state["is_admin"] else st.session_state["username"]
    
    c1, c2 = st.sidebar.columns(2)
    if c1.button("📂 Abrir", use_container_width=True):
        report_data = carregar_relatorio_db(dono, rel_selecionado)
        if report_data:
            keys_to_keep = ["logged_in", "username", "is_admin", "reset_key", "selectbox_historico"]
            for k in list(st.session_state.keys()): 
                if k not in keys_to_keep: del st.session_state[k]
            for k, v in report_data.items(): st.session_state[k] = copy.deepcopy(v)
            st.session_state["current_report_name"] = rel_selecionado
            st.session_state["reset_key"] += 1
            st.rerun()
    if c2.button("🗑️ Apagar", use_container_width=True):
        if excluir_relatorio_db(dono, rel_selecionado):
            if st.session_state["current_report_name"] == rel_selecionado: st.session_state["current_report_name"] = ""
            st.rerun()

if st.session_state["is_admin"]:
    st.sidebar.markdown("---")
    with st.sidebar.expander("👑 Painel Admin"):
        n_user = st.text_input("Novo Usuário:")
        n_pass = st.text_input("Senha:", type="password")
        is_adm = st.checkbox("Admin")
        if st.button("Criar"):
            ok, msg = cadastrar_usuario(n_user, n_pass, is_adm)
            if ok: st.success(msg)
            else: st.error(msg)
        st.markdown("---")
        for u, adm in listar_usuarios():
            c_u1, c_u2 = st.columns([3, 1])
            c_u1.text(f"{u} {'(A)' if adm else ''}")
            if u != "admin" and c_u2.button("X", key=f"del_{u}"):
                excluir_usuario(u)
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

st.title("⚡ Estudo de Demanda Elétrica (VE / AC)")

tab1, tab2, tab3, tab4 = st.tabs(["🔌 1. Entrada de Energia", "🏢 2. Quadro ADM", "⚡ 3. Medidores", "📝 4. Laudo Técnico"])

# --- ABA 1 ---
with tab1:
    st.header("🔌 1. Entrada de Energia (Geral)")
    tipo_analise = st.selectbox("Selecione o tipo:", ["Veículos Elétricos (VE)", "Ar Condicionado (AC)"], key="g_tipo_analise")
    sigla = "VE" if "Veículos" in tipo_analise else "AC"

    file_geral = st.file_uploader("📂 Arquivo do Analisador:", type=["xlsx", "csv"], key=f"f_geral_{st.session_state['reset_key']}")
    serie_r_b, serie_s_b, serie_t_b = pd.Series([25.0, 30.2, 31.29]), pd.Series([4.5, 5.2, 5.81]), pd.Series([26.0, 31.0, 32.16])

    if "g_serie_r" in st.session_state["arquivos_data"]:
        serie_r_b, serie_s_b, serie_t_b = st.session_state["arquivos_data"]["g_serie_r"], st.session_state["arquivos_data"]["g_serie_s"], st.session_state["arquivos_data"]["g_serie_t"]

    if file_geral:
        try:
            df_u = pd.read_csv(file_geral) if file_geral.name.endswith(".csv") else pd.read_excel(file_geral, sheet_name=0)
            sr, ss, st_ser = extrair_dados_completos(df_u)
            if sr is not None:
                serie_r_b, serie_s_b, serie_t_b = sr, ss, st_ser
                st.session_state["arquivos_data"].update({"g_serie_r": sr, "g_serie_s": ss, "g_serie_t": st_ser})
        except: pass

    col1, col2 = st.columns(2)
    if "g_bitola" not in st.session_state: st.session_state["g_bitola"] = list(TABELA_CABOS.keys())[INDEX_PADRAO]
    if "g_cap" not in st.session_state: st.session_state["g_cap"] = float(TABELA_CABOS[st.session_state["g_bitola"]])

    with col1:
        num_cabos = st.number_input("Nº cabos por fase:", min_value=1, value=3, key="g_cabos")
        bitola = st.selectbox("Bitola do Condutor:", list(TABELA_CABOS.keys()), key="g_bitola", on_change=update_cap_geral)
        i_cap = st.number_input("Capacidade do cabo (A):", key="g_cap", step=1.0)
        i_prot = st.number_input("Proteção por fase (A):", value=315.0, key="g_prot")
        v_fase = st.number_input("Tensão (V):", value=127.0, key="g_v")

    min_len = min(len(serie_r_b), len(serie_s_b), len(serie_t_b))
    
    i_pico_r_b = serie_r_b.iloc[:min_len].max() * num_cabos
    i_pico_s_b = serie_s_b.iloc[:min_len].max() * num_cabos
    i_pico_t_b = serie_t_b.iloc[:min_len].max() * num_cabos
    
    p_apar_r_b, p_apar_s_b, p_apar_t_b = i_pico_r_b * v_fase, i_pico_s_b * v_fase, i_pico_t_b * v_fase
    p_apar_tot_b = p_apar_r_b + p_apar_s_b + p_apar_t_b

    i_cond_tot = i_cap * num_cabos
    i_prot_tot = i_prot * num_cabos
    
    st.markdown("---")
    if sigla == "AC":
        qtd_add = st.number_input("Qtd AC a Adicionar:", min_value=0, value=2, key="g_qtd_ac")
        btu_sel = st.selectbox("Potência AC:", ["9.000 BTU/h", "12.000 BTU/h", "18.000 BTU/h", "24.000 BTU/h"], key="g_btu")
        p_kw = 1.0 if "9" in btu_sel else 1.2 if "12" in btu_sel else 1.6 if "18" in btu_sel else 2.0
    else:
        qtd_add = st.number_input("Qtd VE a Adicionar:", min_value=0, value=2, key="g_qtd_ve")
        ve_sel = st.selectbox("Potência VE:", ["3.700W", "7.400W", "11.000W"], key="g_ve")
        p_kw = 3.7 if "3" in ve_sel else 7.4 if "7" in ve_sel else 11.0
    
    corr_add = (qtd_add * p_kw * 1000) / (220.0 * np.sqrt(3))

    r_tot_serie = (serie_r_b.iloc[:min_len] * num_cabos) + corr_add
    s_tot_serie = (serie_s_b.iloc[:min_len] * num_cabos) + corr_add
    t_tot_serie = (serie_t_b.iloc[:min_len] * num_cabos) + corr_add

    i_pico_r = float(r_tot_serie.max())
    i_pico_s = float(s_tot_serie.max())
    i_pico_t = float(t_tot_serie.max())
    i_max_pico = max(i_pico_r, i_pico_s, i_pico_t)

    p_apar_r, p_apar_s, p_apar_t = i_pico_r * v_fase, i_pico_s * v_fase, i_pico_t * v_fase
    p_apar_tot = p_apar_r + p_apar_s + p_apar_t

    st.session_state["serie_r_geral"] = serie_r_b.iloc[:min_len] * num_cabos
    st.session_state["serie_s_geral"] = serie_s_b.iloc[:min_len] * num_cabos
    st.session_state["serie_t_geral"] = serie_t_b.iloc[:min_len] * num_cabos

    p_disp_kw = min(max(0, i_prot_tot - i_max_pico), max(0, i_cond_tot - i_max_pico)) * v_fase * 3 / 1000.0

    st.session_state["dados_geral"] = {
        "p_apar_total": p_apar_tot,
        "p_disp_prot_total": max(0, i_prot_tot - i_max_pico) * v_fase * 3,
        "p_disp_cond_total": max(0, i_cond_tot - i_max_pico) * v_fase * 3,
        "p_disp_menor_kva": p_disp_kw,
        "sigla_tipo": sigla
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
    
    fig_tab = go.Figure(data=[go.Table(
        columnwidth=[3.3, 1.3, 1.3, 1.3, 2.3], 
        header=dict(values=headers_tabela, fill_color='#1E3A8A', align='center', font=dict(color='white', size=21, family="Arial Black")),
        cells=dict(values=valores_tabela, fill_color=[['#F3F4F6', '#ffffff']*4], align='center', font=dict(color='#000000', size=19, family="Arial"), height=37)
    )])
    fig_tab.update_layout(
        title=dict(text="<b>Quadro de Potências e Correntes - Entrada de Energia</b>", font=dict(size=24, color='#000000')),
        margin=dict(l=5, r=5, t=55, b=5), height=380
    ) 
    st.plotly_chart(fig_tab, use_container_width=True, config=CONFIG_IMG_TABELA)

    st.markdown("---")
    st.subheader(f"📈 Perfil de Correntes - Entrada de Energia (+ {sigla})")
    
    # CHECKBOXES RESTAURADOS PARA SELEÇÃO DAS FASES NO GRÁFICO
    col_cb1, col_cb2, col_cb3 = st.columns(3)
    show_r = col_cb1.checkbox("Exibir Fases R", value=True, key="chk_r_geral")
    show_s = col_cb2.checkbox("Exibir Fases S", value=True, key="chk_s_geral")
    show_t = col_cb3.checkbox("Exibir Fases T", value=True, key="chk_t_geral")

    fig = go.Figure()
    if show_r:
        fig.add_trace(go.Scatter(y=serie_r_b.iloc[:min_len]*num_cabos, mode='lines', name='R (Atual)', line=dict(color='#FCA5A5', width=2, dash='dot')))
        fig.add_trace(go.Scatter(y=r_tot_serie, mode='lines', name=f'R (+{sigla})', line=dict(color='#DC2626', width=4)))
    if show_s:
        fig.add_trace(go.Scatter(y=serie_s_b.iloc[:min_len]*num_cabos, mode='lines', name='S (Atual)', line=dict(color='#93C5FD', width=2, dash='dot')))
        fig.add_trace(go.Scatter(y=s_tot_serie, mode='lines', name=f'S (+{sigla})', line=dict(color='#2563EB', width=4)))
    if show_t:
        fig.add_trace(go.Scatter(y=serie_t_b.iloc[:min_len]*num_cabos, mode='lines', name='T (Atual)', line=dict(color='#6EE7B7', width=2, dash='dot')))
        fig.add_trace(go.Scatter(y=t_tot_serie, mode='lines', name=f'T (+{sigla})', line=dict(color='#059669', width=4)))

    fig.add_hline(y=i_cond_tot, line_dash="dash", line_color="#D97706", line_width=3, annotation_text=f"<b>Cabo ({i_cond_tot}A)</b>", annotation_font=dict(size=18, color="#D97706"))
    fig.add_hline(y=i_prot_tot, line_dash="dot", line_color="#7C3AED", line_width=3, annotation_text=f"<b>Prot ({i_prot_tot}A)</b>", annotation_font=dict(size=18, color="#7C3AED"))

    fig.update_layout(
        title=dict(text=f"<b>Perfil de Correntes - Entrada de Energia (+ {sigla})</b>", font=dict(size=24, color='#000000')),
        xaxis=dict(title=dict(text="<b>Amostras</b>", font=dict(size=19, color='#000000')), tickfont=dict(size=18, color='#000000')),
        yaxis=dict(title=dict(text="<b>Corrente (A)</b>", font=dict(size=19, color='#000000')), tickfont=dict(size=18, color='#000000')),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5, font=dict(size=18, color='#000000'), bgcolor="rgba(255,255,255,0.9)", borderwidth=1),
        margin=dict(l=5, r=5, t=55, b=5), template="plotly_white", height=400
    )
    st.plotly_chart(fig, use_container_width=True, config=CONFIG_IMG_GRAFICO)

# --- ABA 2 ---
with tab2:
    st.header("🏢 2. Quadro Administrativo (ADM)")
    tipo_analise_a = st.selectbox("Selecione o tipo:", ["Veículos Elétricos (VE)", "Ar Condicionado (AC)"], key="a_tipo_analise")
    sigla_a = "VE" if "Veículos" in tipo_analise_a else "AC"

    file_a = st.file_uploader("📂 Arquivo do Quadro ADM:", type=["xlsx", "csv"], key=f"f_a_{st.session_state['reset_key']}")
    sr_a, ss_a, st_a = pd.Series([31.4, 28.0, 29.5]), pd.Series([23.0, 21.0, 22.5]), pd.Series([30.5, 27.5, 29.0])

    if "a_serie_r" in st.session_state["arquivos_data"]:
        sr_a, ss_a, st_a = st.session_state["arquivos_data"]["a_serie_r"], st.session_state["arquivos_data"]["a_serie_s"], st.session_state["arquivos_data"]["a_serie_t"]

    if file_a:
        try:
            df_a = pd.read_csv(file_a) if file_a.name.endswith(".csv") else pd.read_excel(file_a, sheet_name=0)
            ex_r, ex_s, ex_t = extrair_dados_completos(df_a)
            if ex_r is not None:
                sr_a, ss_a, st_a = ex_r, ex_s, ex_t
                st.session_state["arquivos_data"].update({"a_serie_r": ex_r, "a_serie_s": ex_s, "a_serie_t": ex_t})
        except: pass

    col1, col2 = st.columns(2)
    if "a_bitola" not in st.session_state: st.session_state["a_bitola"] = list(TABELA_CABOS.keys())[INDEX_PADRAO]
    if "a_cap" not in st.session_state: st.session_state["a_cap"] = float(TABELA_CABOS[st.session_state["a_bitola"]])

    with col1:
        num_cabos_a = st.number_input("Nº cabos por fase:", min_value=1, value=1, key="a_cabos")
        bitola_a = st.selectbox("Bitola do Condutor ADM:", list(TABELA_CABOS.keys()), key="a_bitola", on_change=update_cap_adm)
        i_cap_a = st.number_input("Capacidade do cabo (A):", key="a_cap", step=1.0)
        i_prot_a = st.number_input("Proteção por fase (A):", value=250.0, key="a_prot")
        v_fase_a = st.number_input("Tensão (V):", value=127.0, key="a_v")

    min_l_a = min(len(sr_a), len(ss_a), len(st_a))
    i_pico_r_b_a, i_pico_s_b_a, i_pico_t_b_a = sr_a.iloc[:min_l_a].max() * num_cabos_a, ss_a.iloc[:min_l_a].max() * num_cabos_a, st_a.iloc[:min_l_a].max() * num_cabos_a
    p_apar_r_b_a, p_apar_s_b_a, p_apar_t_b_a = i_pico_r_b_a * v_fase_a, i_pico_s_b_a * v_fase_a, i_pico_t_b_a * v_fase_a
    p_apar_tot_b_a = p_apar_r_b_a + p_apar_s_b_a + p_apar_t_b_a

    i_cond_tot_a = i_cap_a * num_cabos_a
    i_prot_tot_a = i_prot_a * num_cabos_a
    
    st.markdown("---")
    if sigla_a == "AC":
        qtd_add_a = st.number_input("Qtd AC a Adicionar:", min_value=0, value=1, key="a_qtd_ac")
        btu_sel_a = st.selectbox("Potência AC:", ["9.000 BTU/h", "12.000 BTU/h", "18.000 BTU/h", "24.000 BTU/h"], key="a_btu")
        p_kw_a = 1.0 if "9" in btu_sel_a else 1.2 if "12" in btu_sel_a else 1.6 if "18" in btu_sel_a else 2.0
    else:
        qtd_add_a = st.number_input("Qtd VE a Adicionar:", min_value=0, value=1, key="a_qtd_ve")
        ve_sel_a = st.selectbox("Potência VE:", ["3.700W", "7.400W", "11.000W"], key="a_ve")
        p_kw_a = 3.7 if "3" in ve_sel_a else 7.4 if "7" in ve_sel_a else 11.0
    
    corr_add_a = (qtd_add_a * p_kw_a * 1000) / (220.0 * np.sqrt(3))

    r_tot_s_a = (sr_a.iloc[:min_l_a] * num_cabos_a) + corr_add_a
    s_tot_s_a = (ss_a.iloc[:min_l_a] * num_cabos_a) + corr_add_a
    t_tot_s_a = (st_a.iloc[:min_l_a] * num_cabos_a) + corr_add_a

    i_pico_r_a = float(r_tot_s_a.max())
    i_pico_s_a = float(s_tot_s_a.max())
    i_pico_t_a = float(t_tot_s_a.max())
    i_max_p_a = max(i_pico_r_a, i_pico_s_a, i_pico_t_a)

    p_apar_r_a, p_apar_s_a, p_apar_t_a = i_pico_r_a * v_fase_a, i_pico_s_a * v_fase_a, i_pico_t_a * v_fase_a
    p_apar_tot_a = p_apar_r_a + p_apar_s_a + p_apar_t_a

    st.session_state["serie_r_adm"] = sr_a.iloc[:min_l_a] * num_cabos_a
    st.session_state["serie_s_adm"] = ss_a.iloc[:min_l_a] * num_cabos_a
    st.session_state["serie_t_adm"] = st_a.iloc[:min_l_a] * num_cabos_a

    p_disp_kw_a = min(max(0, i_prot_tot_a - i_max_p_a), max(0, i_cond_tot_a - i_max_p_a)) * v_fase_a * 3 / 1000.0

    st.session_state["dados_adm"] = {
        "p_apar_total": p_apar_tot_a,
        "p_disp_prot_total": max(0, i_prot_tot_a - i_max_p_a) * v_fase_a * 3,
        "p_disp_cond_total": max(0, i_cond_tot_a - i_max_p_a) * v_fase_a * 3,
        "p_disp_menor_kva": p_disp_kw_a,
        "sigla_tipo": sigla_a
    }

    stat_r_a = "⚠️ ACIMA" if i_pico_r_a > i_prot_tot_a or i_pico_r_a > i_cond_tot_a else "✅ OK"
    stat_s_a = "⚠️ ACIMA" if i_pico_s_a > i_prot_tot_a or i_pico_s_a > i_cond_tot_a else "✅ OK"
    stat_t_a = "⚠️ ACIMA" if i_pico_t_a > i_prot_tot_a or i_pico_t_a > i_cond_tot_a else "✅ OK"
    b_c_a = bitola_a.split(" - ")[0]

    val_tab_a = [
        ["Corrente Medida (A)", "Pot. Apar. Medida (kVA)", f"Pot. Apar. (+{sigla_a}) (kVA)", f"Corr. Pico (+{sigla_a}) (A)", f"Cap. Cabo ({num_cabos_a}x {b_c_a})", "Corrente Proteção (A)", "Status Final"],
        [f"{i_pico_r_b_a:.1f}", f"{p_apar_r_b_a/1000:.1f}", f"{p_apar_r_a/1000:.1f}", f"{i_pico_r_a:.1f}", f"{i_cond_tot_a:.1f}", f"{i_prot_tot_a:.1f}", stat_r_a],
        [f"{i_pico_s_b_a:.1f}", f"{p_apar_s_b_a/1000:.1f}", f"{p_apar_s_a/1000:.1f}", f"{i_pico_s_a:.1f}", f"{i_cond_tot_a:.1f}", f"{i_prot_tot_a:.1f}", stat_s_a],
        [f"{i_pico_t_b_a:.1f}", f"{p_apar_t_b_a/1000:.1f}", f"{p_apar_t_a/1000:.1f}", f"{i_pico_t_a:.1f}", f"{i_cond_tot_a:.1f}", f"{i_prot_tot_a:.1f}", stat_t_a],
        ["Analisador Base", f"Total: {p_apar_tot_b_a/1000:.1f} kVA", f"Total: {p_apar_tot_a/1000:.1f} kVA", "Cálculo/Fase", "L. Max Condutor", "L. Max Proteção", "Avaliação"]
    ]

    st.markdown("---")
    
    fig_tab_a = go.Figure(data=[go.Table(
        columnwidth=[3.3, 1.3, 1.3, 1.3, 2.3],
        header=dict(values=headers_tabela, fill_color='#1E3A8A', align='center', font=dict(color='white', size=21, family="Arial Black")),
        cells=dict(values=val_tab_a, fill_color=[['#F3F4F6', '#ffffff']*4], align='center', font=dict(color='#000000', size=19, family="Arial"), height=37)
    )])
    fig_tab_a.update_layout(
        title=dict(text="<b>Quadro de Potências e Correntes - ADM</b>", font=dict(size=24, color='#000000')),
        margin=dict(l=5, r=5, t=55, b=5), height=380
    )
    st.plotly_chart(fig_tab_a, use_container_width=True, config=CONFIG_IMG_TABELA)

    st.markdown("---")
    st.subheader(f"📈 Perfil de Correntes - ADM (+ {sigla_a})")
    
    col_cb1_a, col_cb2_a, col_cb3_a = st.columns(3)
    show_r_a = col_cb1_a.checkbox("Exibir Fases R (ADM)", value=True, key="chk_r_adm")
    show_s_a = col_cb2_a.checkbox("Exibir Fases S (ADM)", value=True, key="chk_s_adm")
    show_t_a = col_cb3_a.checkbox("Exibir Fases T (ADM)", value=True, key="chk_t_adm")

    fig_a = go.Figure()
    if show_r_a:
        fig_a.add_trace(go.Scatter(y=sr_a.iloc[:min_l_a]*num_cabos_a, mode='lines', name='R (Atual)', line=dict(color='#FCA5A5', width=2, dash='dot')))
        fig_a.add_trace(go.Scatter(y=r_tot_s_a, mode='lines', name=f'R (+{sigla_a})', line=dict(color='#DC2626', width=4)))
    if show_s_a:
        fig_a.add_trace(go.Scatter(y=ss_a.iloc[:min_l_a]*num_cabos_a, mode='lines', name='S (Atual)', line=dict(color='#93C5FD', width=2, dash='dot')))
        fig_a.add_trace(go.Scatter(y=s_tot_s_a, mode='lines', name=f'S (+{sigla_a})', line=dict(color='#2563EB', width=4)))
    if show_t_a:
        fig_a.add_trace(go.Scatter(y=st_a.iloc[:min_l_a]*num_cabos_a, mode='lines', name='T (Atual)', line=dict(color='#6EE7B7', width=2, dash='dot')))
        fig_a.add_trace(go.Scatter(y=t_tot_s_a, mode='lines', name=f'T (+{sigla_a})', line=dict(color='#059669', width=4)))

    fig_a.add_hline(y=i_cond_tot_a, line_dash="dash", line_color="#D97706", line_width=3, annotation_text=f"<b>Cabo ({i_cond_tot_a}A)</b>", annotation_font=dict(size=18, color="#D97706"))
    fig_a.add_hline(y=i_prot_tot_a, line_dash="dot", line_color="#7C3AED", line_width=3, annotation_text=f"<b>Prot ({i_prot_tot_a}A)</b>", annotation_font=dict(size=18, color="#7C3AED"))

    fig_a.update_layout(
        title=dict(text=f"<b>Perfil de Correntes - ADM (+ {sigla_a})</b>", font=dict(size=24, color='#000000')),
        xaxis=dict(title=dict(text="<b>Amostras</b>", font=dict(size=19, color='#000000')), tickfont=dict(size=18, color='#000000')),
        yaxis=dict(title=dict(text="<b>Corrente (A)</b>", font=dict(size=19, color='#000000')), tickfont=dict(size=18, color='#000000')),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5, font=dict(size=18, color='#000000'), bgcolor="rgba(255,255,255,0.9)", borderwidth=1),
        margin=dict(l=5, r=5, t=55, b=5), template="plotly_white", height=400
    )
    st.plotly_chart(fig_a, use_container_width=True, config=CONFIG_IMG_GRAFICO)

# --- ABA 3: CAIXA DE MEDIDORES ---
with tab3:
    st.header("⚡ 3. Caixa de Medidores")
    tipo_analise_m = st.selectbox("Selecione o tipo:", ["Veículos Elétricos (VE)", "Ar Condicionado (AC)"], key="m_tipo_analise")
    sigla_m = "VE" if "Veículos" in tipo_analise_m else "AC"

    c_m1, c_m2 = st.columns(2)
    qtd_apt = c_m1.number_input("Total apts no condomínio:", min_value=1, value=50, key="m_qtd_apt")
    qtd_cx = c_m2.number_input("Qtd unidades na caixa:", min_value=1, value=6, key="m_qtd_caixa")

    col1, col2 = st.columns(2)
    if "m_bitola" not in st.session_state: st.session_state["m_bitola"] = list(TABELA_CABOS.keys())[INDEX_PADRAO]
    if "m_cap" not in st.session_state: st.session_state["m_cap"] = float(TABELA_CABOS[st.session_state["m_bitola"]])

    with col1:
        num_cabos_m = st.number_input("Nº cabos por fase:", min_value=1, value=1, key="m_cabos")
        bitola_m = st.selectbox("Bitola do Condutor:", list(TABELA_CABOS.keys()), key="m_bitola", on_change=update_cap_med)
        i_cap_m = st.number_input("Capacidade do cabo (A):", key="m_cap", step=1.0)
        i_prot_m = st.number_input("Proteção por fase (A):", value=100.0, key="m_prot")
        v_fase_m = st.number_input("Tensão (V):", value=127.0, key="m_v")

    sr_g, ss_g, st_g = st.session_state.get("serie_r_geral", pd.Series([25]*10)), st.session_state.get("serie_s_geral", pd.Series([25]*10)), st.session_state.get("serie_t_geral", pd.Series([25]*10))
    sr_a, ss_a, st_a = st.session_state.get("serie_r_adm", pd.Series([5]*10)), st.session_state.get("serie_s_adm", pd.Series([5]*10)), st.session_state.get("serie_t_adm", pd.Series([5]*10))

    min_l_m = min(len(sr_g), len(sr_a))
    fator = (qtd_cx / qtd_apt) if qtd_apt > 0 else 0

    sr_med = (sr_g.iloc[:min_l_m].reset_index(drop=True) - sr_a.iloc[:min_l_m].reset_index(drop=True)).clip(lower=0) * fator
    ss_med = (ss_g.iloc[:min_l_m].reset_index(drop=True) - ss_a.iloc[:min_l_m].reset_index(drop=True)).clip(lower=0) * fator
    st_med = (st_g.iloc[:min_l_m].reset_index(drop=True) - st_a.iloc[:min_l_m].reset_index(drop=True)).clip(lower=0) * fator

    i_pico_r_b_m, i_pico_s_b_m, i_pico_t_b_m = (sr_med.max() if len(sr_med)>0 else 0)*num_cabos_m, (ss_med.max() if len(ss_med)>0 else 0)*num_cabos_m, (st_med.max() if len(st_med)>0 else 0)*num_cabos_m
    p_apar_r_b_m, p_apar_s_b_m, p_apar_t_b_m = i_pico_r_b_m * v_fase_m, i_pico_s_b_m * v_fase_m, i_pico_t_b_m * v_fase_m
    p_apar_tot_b_m = p_apar_r_b_m + p_apar_s_b_m + p_apar_t_b_m

    i_cond_tot_m = i_cap_m * num_cabos_m
    i_prot_tot_m = i_prot_m * num_cabos_m
    
    st.markdown("---")
    if sigla_m == "AC":
        qtd_add_m = st.number_input("Qtd AC a Adicionar:", min_value=0, value=1, key="m_qtd_ac")
        btu_sel_m = st.selectbox("Potência AC:", ["9.000 BTU/h", "12.000 BTU/h", "18.000 BTU/h", "24.000 BTU/h"], key="m_btu")
        p_kw_m = 1.0 if "9" in btu_sel_m else 1.2 if "12" in btu_sel_m else 1.6 if "18" in btu_sel_m else 2.0
    else:
        qtd_add_m = st.number_input("Qtd VE a Adicionar:", min_value=0, value=1, key="m_qtd_ve")
        ve_sel_m = st.selectbox("Potência VE:", ["3.700W", "7.400W", "11.000W"], key="m_ve")
        p_kw_m = 3.7 if "3" in ve_sel_m else 7.4 if "7" in ve_sel_m else 11.0
    
    corr_add_m = (qtd_add_m * p_kw_m * 1000) / (220.0 * np.sqrt(3))

    r_tot_s_m = (sr_med * num_cabos_m) + corr_add_m
    s_tot_s_m = (ss_med * num_cabos_m) + corr_add_m
    t_tot_s_m = (st_med * num_cabos_m) + corr_add_m

    i_pico_r_m = float(r_tot_s_m.max()) if len(r_tot_s_m)>0 else 0
    i_pico_s_m = float(s_tot_s_m.max()) if len(r_tot_s_m)>0 else 0
    i_pico_t_m = float(t_tot_s_m.max()) if len(r_tot_s_m)>0 else 0
    i_max_p_m = max(i_pico_r_m, i_pico_s_m, i_pico_t_m)

    p_apar_r_m, p_apar_s_m, p_apar_t_m = i_pico_r_m * v_fase_m, i_pico_s_m * v_fase_m, i_pico_t_m * v_fase_m
    p_apar_tot_m = p_apar_r_m + p_apar_s_m + p_apar_t_m

    p_disp_kw_m = min(max(0, i_prot_tot_m - i_max_p_m), max(0, i_cond_tot_m - i_max_p_m)) * v_fase_m * 3 / 1000.0

    st.session_state["dados_med"] = {
        "p_apar_total": p_apar_tot_m,
        "p_disp_prot_total": max(0, i_prot_tot_m - i_max_p_m) * v_fase_m * 3,
        "p_disp_cond_total": max(0, i_cond_tot_m - i_max_p_m) * v_fase_m * 3,
        "p_disp_menor_kva": p_disp_kw_m,
        "sigla_tipo": sigla_m
    }

    stat_r_m = "⚠️ ACIMA" if i_pico_r_m > i_prot_tot_m or i_pico_r_m > i_cond_tot_m else "✅ OK"
    stat_s_m = "⚠️ ACIMA" if i_pico_s_m > i_prot_tot_m or i_pico_s_m > i_cond_tot_m else "✅ OK"
    stat_t_m = "⚠️ ACIMA" if i_pico_t_m > i_prot_tot_m or i_pico_t_m > i_cond_tot_m else "✅ OK"
    b_c_m = bitola_m.split(" - ")[0]

    val_tab_m = [
        ["Corrente Medida (A)", "Pot. Apar. Medida (kVA)", f"Pot. Apar. (+{sigla_m}) (kVA)", f"Corr. Pico (+{sigla_m}) (A)", f"Cap. Cabo ({num_cabos_m}x {b_c_m})", "Corrente Proteção (A)", "Status Final"],
        [f"{i_pico_r_b_m:.1f}", f"{p_apar_r_b_m/1000:.1f}", f"{p_apar_r_m/1000:.1f}", f"{i_pico_r_m:.1f}", f"{i_cond_tot_m:.1f}", f"{i_prot_tot_m:.1f}", stat_r_m],
        [f"{i_pico_s_b_m:.1f}", f"{p_apar_s_b_m/1000:.1f}", f"{p_apar_s_m/1000:.1f}", f"{i_pico_s_m:.1f}", f"{i_cond_tot_m:.1f}", f"{i_prot_tot_m:.1f}", stat_s_m],
        [f"{i_pico_t_b_m:.1f}", f"{p_apar_t_b_m/1000:.1f}", f"{p_apar_t_m/1000:.1f}", f"{i_pico_t_m:.1f}", f"{i_cond_tot_m:.1f}", f"{i_prot_tot_m:.1f}", stat_t_m],
        ["Cálculo Proporcional", f"Total: {p_apar_tot_b_m/1000:.1f} kVA", f"Total: {p_apar_tot_m/1000:.1f} kVA", "Cálculo/Fase", "L. Max Condutor", "L. Max Proteção", "Avaliação"]
    ]

    st.markdown("---")
    
    fig_tab_m = go.Figure(data=[go.Table(
        columnwidth=[3.3, 1.3, 1.3, 1.3, 2.3],
        header=dict(values=headers_tabela, fill_color='#1E3A8A', align='center', font=dict(color='white', size=21, family="Arial Black")),
        cells=dict(values=val_tab_m, fill_color=[['#F3F4F6', '#ffffff']*4], align='center', font=dict(color='#000000', size=19, family="Arial"), height=37)
    )])
    fig_tab_m.update_layout(
        title=dict(text="<b>Quadro de Potências e Correntes - Medidores</b>", font=dict(size=24, color='#000000')),
        margin=dict(l=5, r=5, t=55, b=5), height=380
    )
    st.plotly_chart(fig_tab_m, use_container_width=True, config=CONFIG_IMG_TABELA)

    st.markdown("---")
    st.subheader(f"📈 Perfil de Correntes - Medidores (+ {sigla_m})")
    
    col_cb1_m, col_cb2_m, col_cb3_m = st.columns(3)
    show_r_m = col_cb1_m.checkbox("Exibir Fases R (Medidores)", value=True, key="chk_r_med")
    show_s_m = col_cb2_m.checkbox("Exibir Fases S (Medidores)", value=True, key="chk_s_med")
    show_t_m = col_cb3_m.checkbox("Exibir Fases T (Medidores)", value=True, key="chk_t_med")

    fig_m = go.Figure()
    if show_r_m:
        fig_m.add_trace(go.Scatter(y=sr_med*num_cabos_m, mode='lines', name='R (Atual)', line=dict(color='#FCA5A5', width=2, dash='dot')))
        fig_m.add_trace(go.Scatter(y=r_tot_s_m, mode='lines', name=f'R (+{sigla_m})', line=dict(color='#DC2626', width=4)))
    if show_s_m:
        fig_m.add_trace(go.Scatter(y=ss_med*num_cabos_m, mode='lines', name='S (Atual)', line=dict(color='#93C5FD', width=2, dash='dot')))
        fig_m.add_trace(go.Scatter(y=s_tot_s_m, mode='lines', name=f'S (+{sigla_m})', line=dict(color='#2563EB', width=4)))
    if show_t_m:
        fig_m.add_trace(go.Scatter(y=st_med*num_cabos_m, mode='lines', name='T (Atual)', line=dict(color='#6EE7B7', width=2, dash='dot')))
        fig_m.add_trace(go.Scatter(y=t_tot_s_m, mode='lines', name=f'T (+{sigla_m})', line=dict(color='#059669', width=4)))

    fig_m.add_hline(y=i_cond_tot_m, line_dash="dash", line_color="#D97706", line_width=3, annotation_text=f"<b>Cabo ({i_cond_tot_m}A)</b>", annotation_font=dict(size=18, color="#D97706"))
    fig_m.add_hline(y=i_prot_tot_m, line_dash="dot", line_color="#7C3AED", line_width=3, annotation_text=f"<b>Prot ({i_prot_tot_m}A)</b>", annotation_font=dict(size=18, color="#7C3AED"))

    fig_m.update_layout(
        title=dict(text=f"<b>Perfil de Correntes - Medidores (+ {sigla_m})</b>", font=dict(size=24, color='#000000')),
        xaxis=dict(title=dict(text="<b>Amostras</b>", font=dict(size=19, color='#000000')), tickfont=dict(size=18, color='#000000')),
        yaxis=dict(title=dict(text="<b>Corrente (A)</b>", font=dict(size=19, color='#000000')), tickfont=dict(size=18, color='#000000')),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5, font=dict(size=18, color='#000000'), bgcolor="rgba(255,255,255,0.9)", borderwidth=1),
        margin=dict(l=5, r=5, t=55, b=5), template="plotly_white", height=400
    )
    st.plotly_chart(fig_m, use_container_width=True, config=CONFIG_IMG_GRAFICO)

# --- ABA 4: LAUDO ---
with tab4:
    st.header("📝 4. Quadro Comparativo & Laudo Técnico")

    g, a, m = st.session_state.get("dados_geral", {}), st.session_state.get("dados_adm", {}), st.session_state.get("dados_med", {})

    if not g or not a: st.warning("⚠️ Acesse as Abas 1 e 2 primeiro.")
    else:
        st.subheader("📊 Quadro Geral Comparativo")
        
        h_comp = ["<b>SETOR ANALISADO</b>", "<b>P. APARENTE (kVA)</b>", "<b>P. DISP. PROTEÇÃO</b>", "<b>P. DISP. CABOS</b>", "<b>P. DISP. REAL (kW)</b>"]
        v_comp = [
            ["Entrada Geral", "Quadro ADM", "Cx. Medidores"],
            [f"{g.get('p_apar_total',0)/1000:.1f}", f"{a.get('p_apar_total',0)/1000:.1f}", f"{m.get('p_apar_total',0)/1000:.1f}"],
            [f"{g.get('p_disp_prot_total',0)/1000:.1f}", f"{a.get('p_disp_prot_total',0)/1000:.1f}", f"{m.get('p_disp_prot_total',0)/1000:.1f}"],
            [f"{g.get('p_disp_cond_total',0)/1000:.1f}", f"{a.get('p_disp_cond_total',0)/1000:.1f}", f"{m.get('p_disp_cond_total',0)/1000:.1f}"],
            [f"{g.get('p_disp_menor_kva',0):.1f} kW", f"{a.get('p_disp_menor_kva',0):.1f} kW", f"{m.get('p_disp_menor_kva',0):.1f} kW"]
        ]

        fig_comp = go.Figure(data=[go.Table(
            columnwidth=[2, 1.5, 1.5, 1.5, 1.5],
            header=dict(values=h_comp, fill_color='#1E3A8A', align='center', font=dict(color='white', size=21, family="Arial Black")),
            cells=dict(values=v_comp, fill_color=[['#F3F4F6', '#ffffff']*2], align='center', font=dict(color='#000000', size=19, family="Arial"), height=37)
        )])
        fig_comp.update_layout(
            title=dict(text="<b>Quadro Geral Comparativo</b>", font=dict(size=24, color='#000000')),
            margin=dict(l=5, r=5, t=55, b=5), height=250
        )
        st.plotly_chart(fig_comp, use_container_width=True, config=CONFIG_IMG_TABELA)

        st.markdown("---")
        st.subheader("💾 Salvar Relatório Atual")
        c_s1, c_s2 = st.columns([3, 1])
        n_atual = st.session_state.get("current_report_name", "")
        n_novo = c_s1.text_input("Nome do relatório:", value=n_atual)
        
        c_s2.markdown("<br>", unsafe_allow_html=True)
        if c_s2.button("Atualizar/Salvar", use_container_width=True, type="primary"):
            if not n_novo: st.warning("⚠️ Digite um nome!")
            else:
                est_salvo = {k: copy.deepcopy(v) for k, v in st.session_state.items() if k not in ["logged_in", "username", "is_admin", "reset_key", "selectbox_historico"] and not k.startswith("Form") and not k.startswith("f_")}
                if salvar_relatorio_db(st.session_state["username"], n_novo, est_salvo):
                    st.session_state["current_report_name"] = n_novo
                    st.toast(f"Relatório '{n_novo}' salvo!", icon="✅")
                    st.rerun()
