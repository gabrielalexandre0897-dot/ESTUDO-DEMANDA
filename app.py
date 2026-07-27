import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from docxtpl import DocxTemplate, InlineImage
from docx.shared import Mm
import io

# ==========================================
# 1. CONFIGURAÇÃO E MEMÓRIA (SESSION_STATE)
# ==========================================
st.set_page_config(page_title="Simulador de Energia", layout="wide")

# Garantir que todas as variáveis existam na memória para não perder dados ao mudar de aba
memoria = [
    'cenario1_ee', 'cenario2_ee', 'cenario_adm', 'texto_conclusao', 
    'quadro_conclusao', 'potencia_ve', 'template_upload'
]

for chave in memoria:
    if chave not in st.session_state:
        # Se for a potência, começa com 0.0, senão começa com string vazia / None
        if chave == 'potencia_ve':
            st.session_state[chave] = 0.0
        elif chave == 'template_upload':
            st.session_state[chave] = None
        else:
            st.session_state[chave] = ""

# Função para gerar um gráfico de exemplo para enviar ao Word
def gerar_grafico_simulacao(potencia_adicional):
    fig, ax = plt.subplots(figsize=(6, 4))
    categorias = ['Atual', 'Com Veículos Elétricos']
    valores = [150, 150 + potencia_adicional] # Valores de exemplo para o gráfico
    
    ax.bar(categorias, valores, color=['#1f77b4', '#2ca02c'])
    ax.set_ylabel('Potência (kW)')
    ax.set_title('Quadro de Potências - Resumo da Simulação')
    
    # Guardar gráfico na memória (buffer) para injetar no docx
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    return buf

# ==========================================
# 2. INTERFACE E ABAS
# ==========================================
aba1, aba2, aba3 = st.tabs(["Entrada de Energia", "Quadro ADM", "Conclusão"])

# --- ABA 1: Entrada de Energia ---
with aba1:
    st.header("📝 Análise Completa da Entrada de Energia")
    
    st.session_state.cenario1_ee = st.text_area("Cenário 1 (Entrada de Energia)", value=st.session_state.cenario1_ee)
    st.session_state.cenario2_ee = st.text_area("Cenário 2 (Entrada de Energia)", value=st.session_state.cenario2_ee)
    
    st.markdown("---")
    
    # O Simulador desce para debaixo da análise, como solicitado
    st.header("🚗 Simulador de Cargas VE")
    st.session_state.potencia_ve = st.number_input(
        "Potência total a instalar para VE (kW)", 
        value=st.session_state.potencia_ve, 
        min_value=0.0
    )
    
    st.write(f"**Resumo da Simulação:** Serão adicionados {st.session_state.potencia_ve} kW referentes ao carregamento de veículos elétricos.")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Botão de Geração do Relatório por baixo do simulador
    if st.session_state.template_upload is not None:
        if st.button("📄 Inserir cenário no documento"):
            try:
                # Lê o ficheiro Word que o utilizador enviou na aba de Conclusão
                doc = DocxTemplate(st.session_state.template_upload)
                
                # Gera o gráfico para o relatório
                grafico_stream = gerar_grafico_simulacao(st.session_state.potencia_ve)
                imagem_grafico = InlineImage(doc, grafico_stream, width=Mm(120))
                
                # Dicionário de tags que vão substituir o texto no Word
                contexto = {
                    'cenario1_ee': st.session_state.cenario1_ee,
                    'cenario2_ee': st.session_state.cenario2_ee,
                    'cenario_adm': st.session_state.cenario_adm,
                    'texto_conclusao': st.session_state.texto_conclusao,
                    'quadro_conclusao': st.session_state.quadro_conclusao,
                    'resumo_simulacao': f"Simulação de cargas aponta um aumento de {st.session_state.potencia_ve} kW.",
                    'grafico_simulacao': imagem_grafico
                }
                
                # Preencher o documento com as tags
                doc.render(contexto)
                
                # Preparar para o download
                output = io.BytesIO()
                doc.save(output)
                output.seek(0)
                
                st.success("Documento gerado com sucesso!")
                st.download_button(
                    label="⬇️ Descarregar Relatório (Word)",
                    data=output,
                    file_name="Relatorio_Cenarios_VE.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
            except Exception as e:
                st.error(f"Ocorreu um erro ao gerar o documento: {e}")
    else:
        st.info("⚠️ Para usar a função 'Inserir cenário no documento', faça primeiro o upload do modelo Word na aba 'Conclusão'.")

# --- ABA 2: Quadro ADM ---
with aba2:
    st.header("Quadro ADM")
    st.session_state.cenario_adm = st.text_area("Cenário 1 (Quadro ADM)", value=st.session_state.cenario_adm)

# --- ABA 3: Conclusão ---
with aba3:
    st.header("Conclusão")
    st.session_state.texto_conclusao = st.text_area("Texto de Conclusão", value=st.session_state.texto_conclusao)
    st.session_state.quadro_conclusao = st.text_area("Quadro da Conclusão", value=st.session_state.quadro_conclusao)
    
    st.markdown("---")
    st.subheader("Carregar Modelo de Documento")
    st.write("Faça o upload do seu ficheiro `.docx` contendo as *tags* (ex: `{{ cenario1_ee }}`, `{{ grafico_simulacao }}`, etc.).")
    
    # Campo para carregar o modelo de documento
    ficheiro_modelo = st.file_uploader("Ficheiro Modelo Word (Template)", type=["docx"])
    
    if ficheiro_modelo:
        # Quando um ficheiro é carregado, guarda-se no estado da sessão
        st.session_state.template_upload = ficheiro_modelo
        st.success("Modelo Word guardado na memória com sucesso! Já pode gerar o documento na aba 'Entrada de Energia'.")
