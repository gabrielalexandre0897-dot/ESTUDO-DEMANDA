import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np

# Configuração da Página
st.set_page_config(
    page_title="Estudo de Demanda - Veículos Elétricos & Ar Condicionado",
    page_icon="⚡",
    layout="wide"
)

# Estilização CSS customizada
st.markdown("""
<style>
    .main {
        background-color: #f8f9fa;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #ffffff;
        border-radius: 4px 4px 0px 0px;
        font-weight: 600;
        padding-left: 20px;
        padding-right: 20px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #0066cc !important;
        color: white !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("⚡ Estudo de Demanda Elétrica & Capacidade (VE / AC)")
st.markdown("---")

TABELA_CABOS = {
    "0,5 mm² - 750V": 8.0,
    "0,75 mm² - 750V": 10.0,
    "1 mm² - 750V": 12.0,
    "1,5 mm² - 750V": 15.5,
    "2,5 mm² - 750V": 21.0,
    "4 mm² - 750V": 28.0,
    "6 mm² - 750V": 36.0,
    "10 mm² - 750V": 50.0,
    "16 mm² - 750V": 68.0,
    "25 mm² - 750V": 89.0,
    "35 mm² - 750V": 110.0,
    "50 mm² - 750V": 134.0,
}

# Criação das abas nativas para manter os dados salvos ao navegar
aba_geral, aba_adm, aba_conclusao = st.tabs(["📝 Geral (Entrada de Energia)", "🏢 Quadro Administrativo (ADM)", "📊 Conclusão & Laudo Técnico"])

with aba_geral:
    st.header("📝 Análise Completa da Entrada de Energia:")
    
    col1, col2 = st.columns(2)
    with col1:
        potencia_instalada_ee = st.number_input("Potência Instalada EE (kVA)", min_value=0.0, value=73.6, step=1.0, key="pot_inst_ee")
    with col2:
        fator_potencia_ee = st.number_input("Fator de Potência EE", min_value=0.1, max_value=1.0, value=0.92, step=0.01, key="fp_ee")

    potencia_util_ee = potencia_instalada_ee * 0.8  # Limitado a 80%
    st.info(f"💡 Potência Disponível com 80% da Carga (Entrada de Energia): **{potencia_util_ee:.2f} kVA**")

    st.markdown("---")
    st.subheader("🚗 Simulador de Cargas VE (Entrada de Energia)")
    
    num_ve_ee = st.number_input("Número de Carregadores de VE (Geral)", min_value=0, value=5, step=1, key="num_ve_ee")
    pot_ve_ee = st.number_input("Potência média por Carregador VE (kW)", min_value=0.0, value=7.4, step=0.5, key="pot_ve_ee")
    
    carga_total_ve_ee = num_ve_ee * pot_ve_ee
    st.metric("Carga Total Estimada VE", f"{carga_total_ve_ee:.2f} kW")

with aba_adm:
    st.header("🏢 Análise Completa do Quadro Administrativo (ADM):")
    
    col1, col2 = st.columns(2)
    with col1:
        potencia_instalada_adm = st.number_input("Potência Instalada ADM (kVA)", min_value=0.0, value=80.26, step=1.0, key="pot_inst_adm")
    with col2:
        fator_potencia_adm = st.number_input("Fator de Potência ADM", min_value=0.1, max_value=1.0, value=0.92, step=0.01, key="fp_adm")

    potencia_util_adm = potencia_instalada_adm * 0.8  # Limitado a 80%
    st.info(f"💡 Potência Disponível com 80% da Carga (Quadro ADM): **{potencia_util_adm:.2f} kVA**")

    st.markdown("---")
    st.subheader("🚗 Simulador de Cargas VE (Quadro Administrativo)")
    
    num_ve_adm = st.number_input("Número de Carregadores de VE (ADM)", min_value=0, value=2, step=1, key="num_ve_adm")
    pot_ve_adm = st.number_input("Potência média por Carregador VE (kW) - ADM", min_value=0.0, value=7.4, step=0.5, key="pot_ve_adm")
    
    carga_total_ve_adm = num_ve_adm * pot_ve_adm
    st.metric("Carga Total Estimada VE (ADM)", f"{carga_total_ve_adm:.2f} kW")

with aba_conclusao:
    st.header("📊 Quadro Geral Comparativo")
    
    # Exibindo as potências totais já calculadas com 80% da carga
    total_pot_util = (st.session_state.get('pot_inst_ee', 73.6) * 0.8) + (st.session_state.get('pot_inst_adm', 80.26) * 0.8)
    
    col_q1, col_q2 = st.columns(2)
    with col_q1:
        st.metric("Potência Disponível Total (80% da Carga)", f"{total_pot_util:.2f} kVA")
    with col_q2:
        total_ve_geral = (st.session_state.get('num_ve_ee', 5) * st.session_state.get('pot_ve_ee', 7.4)) + \
                         (st.session_state.get('num_ve_adm', 2) * st.session_state.get('pot_ve_adm', 7.4))
        st.metric("Carga Total VE (Geral + ADM)", f"{total_ve_geral:.2f} kW")

    st.markdown("---")
    st.subheader("📄 Texto Oficial do Laudo Técnico")
    
    texto_laudo = f"""De acordo com as medições realizadas, verificou-se que o condomínio dispõe de uma potência de {st.session_state.get('pot_inst_ee', 73.6):.1f} kVA na entrada de energia. Para garantir maior segurança e confiabilidade ao sistema elétrico, recomenda-se a utilização de até 80% desse valor ({st.session_state.get('pot_inst_ee', 73.6)*0.8:.2f} kVA), mantendo uma reserva técnica próxima de 20% para suportar eventuais incrementos de demanda sem comprometer o desempenho do sistema.
De forma similar, o quadro administrativo apresenta uma potência disponível de aproximadamente {st.session_state.get('pot_inst_adm', 80.26):.2f} kVA. Sugere-se, pelos mesmos critérios de segurança operacional, limitar o uso a até 80% dessa capacidade ({st.session_state.get('pot_inst_adm', 80.26)*0.8:.2f} kVA), mantendo uma reserva técnica próxima de 20% para suportar eventuais incrementos de demanda sem comprometer o desempenho do sistema."""

    st.text_area("Copie o texto abaixo:", value=texto_laudo, height=180)
