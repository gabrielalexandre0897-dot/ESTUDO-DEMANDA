import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import copy
import pickle
import os

# Configuração da Página
st.set_page_config(
    page_title="Estudo de Demanda - Veículos Elétricos & Ar Condicionado",
    page_icon="⚡",
    layout="wide"
)

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

st.title("⚡ Estudo de Demanda Elétrica & Capacidade (VE / AC)")

# Variáveis Globais
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

ARQUIVO_BANDO_DADOS = "banco_relatorios.pkl"

def carregar_dados():
    if os.path.exists(ARQUIVO_BANDO_DADOS):
        try:
            with open(ARQUIVO_BANDO_DADOS, "rb") as f:
                return pickle.load(f)
        except Exception:
            return {}
    return {}

def salvar_dados_arquivo(dados):
    with open(ARQUIVO_BANDO_DADOS, "wb") as f:
        pickle.dump(dados, f)

def fmt(val, dec=2):
    return f"{val:.{dec}f}".replace('.', ',')

def update_cap_geral():
    if st.session_state.get('g_bitola') in TABELA_CABOS:
        st.session_state['g_cap'] = float(TABELA_CABOS[st.session_state['g_bitola']])

def update_cap_adm():
    if st.session_state.get('a_bitola') in TABELA_CABOS:
        st.session_state['a_cap'] = float(TABELA_CABOS[st.session_state['a_bitola']])

# --- INICIALIZAÇÃO DE VARIÁVEIS NA MEMÓRIA ---
if "saved_reports" not in st.session_state: st.session_state["saved_reports"] = carregar_dados()
if "current_report_name" not in st.session_state: st.session_state["current_report_name"] = ""
if "dados_geral" not in st.session_state: st.session_state["dados_geral"] = {}
if "dados_adm" not in st.session_state: st.session_state["dados_adm"] = {}
if "reset_key" not in st.session_state: st.session_state["reset_key"] = 0
if "arquivos_data" not in st.session_state: st.session_state["arquivos_data"] = {}
if "pending_load_report" not in st.session_state: st.session_state["pending_load_report"] = None

# Se houver um relatório pendente para carregar, executamos a limpeza completa e o carregamento seguro
if st.session_state["pending_load_report"] is not None:
    nome_a_carregar = st.session_state["pending_load_report"]
    st.session_state["pending_load_report"] = None
    
    if nome_a_carregar in st.session_state["saved_reports"]:
        report_data = st.session_state["saved_reports"][nome_a_carregar]
        
        # Limpa todos os widgets da sessão para evitar conflitos
        for k in list(st.session_state.keys()):
            if k not in ["saved_reports", "reset_key", "current_report_name", "pending_load_report"]:
                del st.session_state[k]
        
        # Restaura os dados salvos
        for k, v in report_data.items():
            st.session_state[k] = copy.deepcopy(v)
            
        st.session_state["current_report_name"] = nome_a_carregar
        st.session_state["reset_key"] += 1
        st.rerun()

def reset_app():
    st.session_state["reset_key"] += 1
    keys_to_delete = [k for k in st.session_state.keys() if k not in ["saved_reports", "reset_key", "current_report_name", "pending_load_report"]]
    for k in keys_to_delete:
        del st.session_state[k]
    st.session_state["dados_geral"] = {}
    st.session_state["dados_adm"] = {}
    st.session_state["arquivos_data"] = {}
    st.session_state["current_report_name"] = ""

# --- BARRA LATERAL (MENU DE RELATÓRIOS) ---
st.sidebar.markdown("### 💾 Gerenciador de Relatórios")

if st.sidebar.button("➕ Criar Novo Relatório", type="primary", use_container_width=True):
    reset_app()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("**📂 Histórico Salvo (Permanente)**")

if not st.session_state["saved_reports"]:
    st.sidebar.info("Nenhum relatório salvo no momento.")
else:
    for rep_name in list(st.session_state["saved_reports"].keys()):
        col_name, col_del = st.sidebar.columns([4, 1])
        
        with col_name:
            # Botão sem key customizada na barra lateral para evitar completamente o erro de atribuição de valor
            if st.sidebar.button(f"📄 {rep_name}", use_container_width=True):
                st.session_state["pending_load_report"] = rep_name
                st.rerun()
                
        with col_del:
            if st.sidebar.button("🗑️", key=f"del_{rep_name}", help=f"Excluir '{rep_name}'"):
                del st.session_state["saved_reports"][rep_name]
                salvar_dados_arquivo(st.session_state["saved_reports"])
                if st.session_state["current_report_name"] == rep_name:
                    st.session_state["current_report_name"] = ""
                st.toast(f"Relatório apagado!", icon="🗑️")
                st.rerun()

# Extração de Dados
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

tab1, tab2, tab3 = st.tabs(["🔌 1. Entrada de Energia (Geral)", "🏢 2. Quadro Administrativo (ADM)", "📝 3. Conclusão & Laudo Técnico"])

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

    headers_tabela = ["Parâmetro / Métrica", "Fase R", "Fase S", "Fase T", "Referência de Limite"]
    valores_tabela = [
        ["Corrente Total Medida (A)", "Potência Aparente Referente à Corrente Medida (VA)", f"Potência Aparente Total + {sigla_tipo} (VA)", f"Corrente Pico Total + {sigla_tipo} (A)", f"Capacidade do Cabo ({num_cabos}x {bitola_sel})", "Corrente de Proteção Geral", "Status da Carga vs Limites"],
        [f"{i_pico_r_base:.2f} A", f"{p_apar_r_base:.2f} VA", f"{p_apar_r:.2f} VA", f"{i_pico_r:.2f} A", f"{i_cond_total:.2f} A", f"{i_prot_total:.2f} A", status_r],
        [f"{i_pico_s_base:.2f} A", f"{p_apar_s_base:.2f} VA", f"{p_apar_s:.2f} VA", f"{i_pico_s:.2f} A", f"{i_cond_total:.2f} A", f"{i_prot_total:.2f} A", status_s],
        [f"{i_pico_t_base:.2f} A", f"{p_apar_t_base:.2f} VA", f"{p_apar_t:.2f} VA", f"{i_pico_t:.2f} A", f"{i_cond_total:.2f} A", f"{i_prot_total:.2f} A", status_t],
        ["Amostragem Analisador", f"Total: {p_apar_total_base:.2f} VA", f"Total: {p_apar_total:.2f} VA", "Corrente Calculada por Fase", "Limite Máx. dos Condutores", "Limite Máx. das Proteções", "Avaliação por Fase"]
    ]

    fig_tabela = go.Figure(data=[go.Table(
        header=dict(values=headers_tabela, fill_color='#1E3A8A', align='center', font=dict(color='white', size=13)),
        cells=dict(values=valores_tabela, fill_color=[['#F3F4F6', '#ffffff', '#F9FAFB', '#ffffff', '#F9FAFB', '#ffffff', '#EFF6FF']*1], align='center', font=dict(color='#1F2937', size=12), height=30)
    )])
    fig_tabela.update_layout(title=dict(text="<b>Quadro de Potências e Correntes - Entrada de Energia</b>", font=dict(size=16)), margin=dict(l=10, r=10, t=40, b=10), height=320)

    st.markdown("---")
    st.subheader("📋 Quadro de Potências e Correntes - Entrada de Energia")
    st.plotly_chart(fig_tabela, width='stretch', config={"displayModeBar": True})

    st.markdown("---")
    st.subheader(f"📈 Gráfico de Evolução de Correntes (Consumo Atual vs Projeção com {sigla_tipo})")

    col_cb1, col_cb2, col_cb3 = st.columns(3)
    show_r = col_cb1.checkbox("Exibir Fases R", value=True, key="chk_r_geral")
    show_s = col_cb2.checkbox("Exibir Fases S", value=True, key="chk_s_geral")
    show_t = col_cb3.checkbox("Exibir Fases T", value=True, key="chk_t_geral")

    fig = go.Figure()
    if show_r:
        fig.add_trace(go.Scatter(y=r_base_total_serie, mode='lines', name='Fase R (Atual)', line=dict(color='#FCA5A5', width=1.5, dash='dot')))
        fig.add_trace(go.Scatter(y=r_total, mode='lines+markers', name=f'Fase R (Total + {sigla_tipo})', line=dict(color='#DC2626', width=2)))
    if show_s:
        fig.add_trace(go.Scatter(y=s_base_total_serie, mode='lines', name='Fase S (Atual)', line=dict(color='#93C5FD', width=1.5, dash='dot')))
        fig.add_trace(go.Scatter(y=s_total, mode='lines+markers', name=f'Fase S (Total + {sigla_tipo})', line=dict(color='#2563EB', width=2)))
    if show_t:
        fig.add_trace(go.Scatter(y=t_base_total_serie, mode='lines', name='Fase T (Atual)', line=dict(color='#6EE7B7', width=1.5, dash='dot')))
        fig.add_trace(go.Scatter(y=t_total, mode='lines+markers', name=f'Fase T (Total + {sigla_tipo})', line=dict(color='#059669', width=2)))

    fig.add_hline(y=i_cond_total, line_dash="dash", line_color="#D97706", annotation_text=f"Limite Cabos ({i_cond_total}A)")
    fig.add_hline(y=i_prot_total, line_dash="dot", line_color="#7C3AED", annotation_text=f"Limite Proteção ({i_prot_total}A)")

    fig.update_layout(title=f"Perfil de Correntes por Fase", xaxis_title="Amostras / Horários", yaxis_title="Corrente por Fase (A)", template="plotly_white", height=450)
    st.plotly_chart(fig, width='stretch')

    ultrapassou_cabo = i_max_pico > i_cond_total
    ultrapassou_prot = i_max_pico > i_prot_total
    status_comporta = "NÃO COMPORTA" if (ultrapassou_cabo or ultrapassou_prot) else "COMPORTA"
    
    if sigla_tipo == "AC": texto_resumo_cliente = f"O sistema elétrico da Entrada de Energia {status_comporta} o acréscimo de {int(qtd_carregadores)} Unidades de Ar Condicionado de {btu_sel}."
    else: texto_resumo_cliente = f"O sistema elétrico da Entrada de Energia {status_comporta} o acréscimo de {int(qtd_carregadores)} Carregadores Veiculares de {fmt(potencia_carregador_kw)}KW."

    st.markdown("📋 **Resumo da Simulação (Pronto para Cópia):**")
    st.code(texto_resumo_cliente, language="text")

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

    headers_tabela_a = ["Parâmetro / Métrica", "Fase R", "Fase S", "Fase T", "Referência de Limite"]
    valores_tabela_a = [
        ["Corrente Total Medida (A)", "Potência Aparente Referente à Corrente Medida (VA)", f"Potência Aparente Total + {sigla_tipo_adm} (VA)", f"Corrente Pico Total + {sigla_tipo_adm} (A)", f"Capacidade do Cabo ({num_cabos_adm}x {bitola_adm})", "Corrente de Proteção Geral", "Status da Carga vs Limites"],
        [f"{i_pico_r_base_a:.2f} A", f"{p_apar_r_base_a:.2f} VA", f"{p_apar_r_a:.2f} VA", f"{i_pico_r_a:.2f} A", f"{i_cond_total_a:.2f} A", f"{i_prot_total_a:.2f} A", status_r_a],
        [f"{i_pico_s_base_a:.2f} A", f"{p_apar_s_base_a:.2f} VA", f"{p_apar_s_a:.2f} VA", f"{i_pico_s_a:.2f} A", f"{i_cond_total_a:.2f} A", f"{i_prot_total_a:.2f} A", status_s_a],
        [f"{i_pico_t_base_a:.2f} A", f"{p_apar_t_base_a:.2f} VA", f"{p_apar_t_a:.2f} VA", f"{i_pico_t_a:.2f} A", f"{i_cond_total_a:.2f} A", f"{i_prot_total_a:.2f} A", status_t_a],
        ["Amostragem Analisador", f"Total: {p_apar_total_base_a:.2f} VA", f"Total: {p_apar_total_a:.2f} VA", "Corrente Calculada por Fase", "Limite Máx. dos Condutores", "Limite Máx. das Proteções", "Avaliação por Fase"]
    ]

    fig_tabela_a = go.Figure(data=[go.Table(
        header=dict(values=headers_tabela_a, fill_color='#1E3A8A', align='center', font=dict(color='white', size=13)),
        cells=dict(values=valores_tabela_a, fill_color=[['#F3F4F6', '#ffffff', '#F9FAFB', '#ffffff', '#F9FAFB', '#ffffff', '#EFF6FF']*1], align='center', font=dict(color='#1F2937', size=12), height=30)
    )])
    fig_tabela_a.update_layout(title=dict(text="<b>Quadro de Potências e Correntes - Quadro Administrativo</b>", font=dict(size=16)), margin=dict(l=10, r=10, t=40, b=10), height=320)

    st.markdown("---")
    st.subheader("📋 Quadro de Potências e Correntes - Quadro Administrativo")
    st.plotly_chart(fig_tabela_a, width='stretch', config={"displayModeBar": True})

    st.markdown("---")
    st.subheader(f"📈 Gráfico de Evolução de Correntes (Consumo Atual vs Projeção com {sigla_tipo_adm})")

    col_cb1_a, col_cb2_a, col_cb3_a = st.columns(3)
    show_r_a = col_cb1_a.checkbox("Exibir Fases R (ADM)", value=True, key="chk_r_adm")
    show_s_a = col_cb2_a.checkbox("Exibir Fases S (ADM)", value=True, key="chk_s_adm")
    show_t_a = col_cb3_a.checkbox("Exibir Fases T (ADM)", value=True, key="chk_t_adm")

    fig_a = go.Figure()
    if show_r_a:
        fig_a.add_trace(go.Scatter(y=r_base_total_serie_a, mode='lines', name='Fase R (Atual)', line=dict(color='#FCA5A5', width=1.5, dash='dot')))
        fig_a.add_trace(go.Scatter(y=r_total_a, mode='lines+markers', name=f'Fase R (Total + {sigla_tipo_adm})', line=dict(color='#DC2626', width=2)))
    if show_s_a:
        fig_a.add_trace(go.Scatter(y=s_base_total_serie_a, mode='lines', name='Fase S (Atual)', line=dict(color='#93C5FD', width=1.5, dash='dot')))
        fig_a.add_trace(go.Scatter(y=s_total_a, mode='lines+markers', name=f'Fase S (Total + {sigla_tipo_adm})', line=dict(color='#2563EB', width=2)))
    if show_t_a:
        fig_a.add_trace(go.Scatter(y=t_base_total_serie_a, mode='lines', name='Fase T (Atual)', line=dict(color='#6EE7B7', width=1.5, dash='dot')))
        fig_a.add_trace(go.Scatter(y=t_total_a, mode='lines+markers', name=f'Fase T (Total + {sigla_tipo_adm})', line=dict(color='#059669', width=2)))

    fig_a.add_hline(y=i_cond_total_a, line_dash="dash", line_color="#D97706", annotation_text=f"Limite Cabos ({i_cond_total_a}A)")
    fig_a.add_hline(y=i_prot_total_a, line_dash="dot", line_color="#7C3AED", annotation_text=f"Limite Proteção ({i_prot_total_a}A)")

    fig_a.update_layout(title=f"Perfil de Correntes por Fase - ADM", xaxis_title="Amostras / Horários", yaxis_title="Corrente por Fase (A)", template="plotly_white", height=450)
    st.plotly_chart(fig_a, width='stretch')

    ultrapassou_cabo_a = i_max_pico_a > i_cond_total_a
    ultrapassou_prot_a = i_max_pico_a > i_prot_total_a
    status_comporta_a = "NÃO COMPORTA" if (ultrapassou_cabo_a or ultrapassou_prot_a) else "COMPORTA"
    
    if sigla_tipo_adm == "AC": texto_resumo_cliente_a = f"O sistema elétrico do Quadro Administrativo {status_comporta_a} o acréscimo de {int(qtd_carregadores_a)} Unidades de Ar Condicionado de {btu_sel_a}."
    else: texto_resumo_cliente_a = f"O sistema elétrico do Quadro Administrativo {status_comporta_a} o acréscimo de {int(qtd_carregadores_a)} Carregadores Veiculares de {fmt(potencia_carregador_kw_a)}KW."

    st.markdown("📋 **Resumo da Simulação (Pronto para Cópia):**")
    st.code(texto_resumo_cliente_a, language="text")


with tab3:
    st.header("📝 3. Quadro Comparativo & Laudo Técnico")

    g = st.session_state.get("dados_geral", {})
    a = st.session_state.get("dados_adm", {})
    sigla_tipo = g.get("sigla_tipo", "VE")

    if not g or not a:
        st.warning("⚠️ Acesse as Abas 1 e 2 primeiro para carregar todos os cálculos.")
    else:
        p_disp_entrada_kva = g.get("p_disp_menor_kva", 0)
        p_disp_adm_kva = a.get("p_disp_menor_kva", 0)

        st.subheader("📊 Quadro Geral Comparativo")
        
        headers_comp = ["Setor Analisado", "P. Aparente Medida", "P. Disp. Proteção", "P. Disp. Condutor", "P. Disp. Total (100% Carga)"]
        valores_comp = [
            ["Entrada de Energia (Geral)", "Quadro Administrativo (ADM)"],
            [f"{g.get('p_apar_total',0)/1000:.2f} kVA", f"{a.get('p_apar_total',0)/1000:.2f} kVA"],
            [f"{g.get('p_disp_prot_total',0)/1000:.2f} kVA", f"{a.get('p_disp_prot_total',0)/1000:.2f} kVA"],
            [f"{g.get('p_disp_cond_total',0)/1000:.2f} kVA", f"{a.get('p_disp_cond_total',0)/1000:.2f} kVA"],
            [f"{p_disp_entrada_kva:.2f} kW", f"{p_disp_adm_kva:.2f} kW"]
        ]

        fig_comp = go.Figure(data=[go.Table(
            header=dict(values=headers_comp, fill_color='#1E3A8A', align='center', font=dict(color='white', size=13)),
            cells=dict(values=valores_comp, fill_color=[['#F3F4F6', '#ffffff']*1], align='center', font=dict(color='#1F2937', size=12), height=30)
        )])
        fig_comp.update_layout(title=dict(text="<b>Quadro Geral Comparativo</b>", font=dict(size=16)), margin=dict(l=10, r=10, t=40, b=10), height=200)
        st.plotly_chart(fig_comp, width='stretch')

        col_c1, col_c2 = st.columns(2)
        with col_c1:
            pot_op1 = st.number_input("Opção 1 (kW):", value=7.4, step=0.1, key="c_pot1")
            qtd_op1 = int(p_disp_entrada_kva // pot_op1) if pot_op1 > 0 else 0
            st.success(f"✅ Limite (100%): **{qtd_op1}** unidades de {pot_op1} kW")
        with col_c2:
            pot_op2 = st.number_input("Opção 2 (kW):", value=3.7, step=0.1, key="c_pot2")
            qtd_op2 = int(p_disp_entrada_kva // pot_op2) if pot_op2 > 0 else 0
            st.success(f"✅ Limite (100%): **{qtd_op2}** unidades de {pot_op2} kW")

        st.markdown("---")
        st.subheader("📄 Texto Oficial do Laudo Técnico (Passe o mouse no canto superior direito para COPIAR)")

        p_disp_entrada_80 = p_disp_entrada_kva * 0.8
        p_disp_adm_80 = p_disp_adm_kva * 0.8

        texto_laudo = f"""De acordo com as medições realizadas, verificou-se que o condomínio dispõe de uma potência de {fmt(p_disp_entrada_kva)} kVA na entrada de energia. Para garantir maior segurança e confiabilidade ao sistema elétrico, recomenda-se a utilização de até 80% desse valor ({fmt(p_disp_entrada_80)} kVA), mantendo uma reserva técnica próxima de 20% para suportar eventuais incrementos de demanda sem comprometer o desempenho do sistema.

De forma similar, o quadro administrativo apresenta uma potência disponível de aproximadamente {fmt(p_disp_adm_kva)} kVA. Sugere-se, pelos mesmos critérios de segurança operacional, limitar o uso a até 80% dessa capacidade ({fmt(p_disp_adm_80)} kVA), mantendo uma reserva técnica próxima de 20% para suportar eventuais incrementos de demanda sem comprometer o desempenho do sistema."""

        st.success(texto_laudo)
        st.code(texto_laudo, language="text")

        # --- NOVA SEÇÃO: SALVAR/ATUALIZAR RELATÓRIO ---
        st.markdown("---")
        st.subheader("💾 Salvar Relatório Atual")
        st.info("Salve o progresso atual para consultá-lo depois. Se mantiver o mesmo nome, o relatório será atualizado com os novos dados.")
        
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
                    for chave, valor in st.session_state.items():
                        if chave not in ["saved_reports", "reset_key", "current_report_name", "pending_load_report"] and not chave.startswith("FormSubmitter") and not chave.startswith("file_geral") and not chave.startswith("file_adm"):
                            estado_salvo[chave] = copy.deepcopy(valor)
                    
                    st.session_state["saved_reports"][nome_novo_relatorio] = estado_salvo
                    st.session_state["current_report_name"] = nome_novo_relatorio
                    
                    salvar_dados_arquivo(st.session_state["saved_reports"])
                    
                    if is_updating:
                        st.toast(f"Relatório '{nome_novo_relatorio}' atualizado com sucesso!", icon="🔄")
                    else:
                        st.toast(f"Relatório '{nome_novo_relatorio}' salvo permanentemente!", icon="✅")
                        
                    st.rerun()
