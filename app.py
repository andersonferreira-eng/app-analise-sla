import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import io

# Configuração da página
st.set_page_config(page_title="Análise de SLA", layout="wide")
sns.set_theme(style="whitegrid")

st.title("📊 Painel de Análise de SLA de Entregas")
st.write("Faça o upload da sua planilha Excel (.xlsx) para gerar os indicadores, gráficos e a base consolidada.")

# Upload do arquivo
uploaded_file = st.file_uploader("Selecione o arquivo Excel", type=['xlsx'])

if uploaded_file is not None:
    with st.spinner('Lendo a planilha e calculando SLA...'):
        colunas_desejadas = ['state', 'occurrence', 'payment_date', 'lot', 'tracking_origin_status']
        
        try:
            df = pd.read_excel(uploaded_file, usecols=colunas_desejadas)

            # 1. PADRONIZAR ESTADOS
            dicionario_estados = {
                'ACRE': 'AC', 'ALAGOAS': 'AL', 'AMAPA': 'AP', 'AMAPÁ': 'AP', 'AMAZONAS': 'AM', 
                'BAHIA': 'BA', 'CEARA': 'CE', 'CEARÁ': 'CE', 'DISTRITO FEDERAL': 'DF', 
                'ESPIRITO SANTO': 'ES', 'ESPÍRITO SANTO': 'ES', 'GOIAS': 'GO', 'GOIÁS': 'GO', 
                'MARANHAO': 'MA', 'MARANHÃO': 'MA', 'MATO GROSSO': 'MT', 'MATO GROSSO DO SUL': 'MS', 
                'MINAS GERAIS': 'MG', 'PARA': 'PA', 'PARÁ': 'PA', 'PARAIBA': 'PB', 'PARAÍBA': 'PB',
                'PARANA': 'PR', 'PARANÁ': 'PR', 'PERNAMBUCO': 'PE', 'PIAUI': 'PI', 'PIAUÍ': 'PI', 
                'RIO DE JANEIRO': 'RJ', 'RIO GRANDE DO NORTE': 'RN', 'RIO GRANDE DO SUL': 'RS', 
                'RONDONIA': 'RO', 'RONDÔNIA': 'RO', 'RORAIMA': 'RR', 'SANTA CATARINA': 'SC', 
                'SAO PAULO': 'SP', 'SÃO PAULO': 'SP', 'SERGIPE': 'SE', 'TOCANTINS': 'TO'
            }
            df['state'] = df['state'].astype(str).str.strip().str.upper()
            df['state'] = df['state'].replace(dicionario_estados)

            # 2. FILTRAR STATUS E CALCULAR PRAZOS
            df['tracking_origin_status'] = df['tracking_origin_status'].astype(str).str.strip().str.lower()
            status_ignorados = ['entregue', 'em devolução', 'extravio']
            df = df[~df['tracking_origin_status'].isin(status_ignorados)].copy()

            df['payment_date'] = pd.to_datetime(df['payment_date'], errors='coerce')
            df['prazo_entrega'] = pd.NaT
            
            mask_lote = df['lot'].astype(str).str.strip().str.lower() == 'lote'
            df.loc[mask_lote, 'prazo_entrega'] = df.loc[mask_lote, 'payment_date'] + pd.Timedelta(days=30)
            mask_boas_vindas = df['lot'].astype(str).str.strip().str.lower() == 'boas vindas'
            df.loc[mask_boas_vindas, 'prazo_entrega'] = df.loc[mask_boas_vindas, 'payment_date'] + pd.offsets.BDay(15)

            data_atualizacao = pd.Timestamp.today().normalize()
            condicoes = [(data_atualizacao <= df['prazo_entrega']), (data_atualizacao > df['prazo_entrega'])]
            df['SLA'] = np.select(condicoes, ['Em andamento no Prazo', 'Em andamento atrasado'], default='Data Inválida/Sem Info')
            df['is_no_prazo'] = df['SLA'] == 'Em andamento no Prazo'

            def formatar_porcentagem(valor):
                return f"{valor:.1f}%".replace('.', ',')

            # 3. RESUMO GERAL
            total_geral = len(df)
            total_no_prazo = df['is_no_prazo'].sum()
            total_atrasado = total_geral - total_no_prazo
            pct_geral = (total_no_prazo / total_geral) * 100 if total_geral > 0 else 0

            resumo_geral = pd.DataFrame({
                'Visão': ['Geral (Brasil - Em Trânsito)'],
                'Total_Pedidos': [total_geral],
                'Pedidos_No_Prazo': [total_no_prazo],
                'SLA_%': [formatar_porcentagem(pct_geral)]
            })

            # LAYOUT EM COLUNAS
            st.markdown("---")
            col1, col2 = st.columns(2)

            with col1:
                st.subheader("Resumo Geral de SLA (Pendentes)")
                st.dataframe(resumo_geral, hide_index=True)
                
                if total_geral > 0:
                    fig1, ax1 = plt.subplots(figsize=(5, 5))
                    ax1.pie([total_no_prazo, total_atrasado], labels=['No Prazo', 'Atrasado'], autopct='%1.1f%%', startangle=90, colors=['#4CAF50', '#F44336'])
                    ax1.set_title('Visão Geral', fontweight='bold')
                    st.pyplot(fig1)

            # 4. RESUMO POR ESTADO
            resumo_estados = df.groupby('state').agg(total_pedidos=('state', 'size'), pedidos_no_prazo=('is_no_prazo', 'sum')).reset_index()
            resumo_estados['SLA_Num'] = (resumo_estados['pedidos_no_prazo'] / resumo_estados['total_pedidos']) * 100
            resumo_estados = resumo_estados.sort_values(by=['SLA_Num', 'total_pedidos'], ascending=[True, False])

            with col2:
                st.subheader("Ranking por Estado")
                resumo_estados_exibicao = resumo_estados.copy()
                resumo_estados_exibicao['SLA_%'] = resumo_estados_exibicao['SLA_Num'].apply(formatar_porcentagem)
                st.dataframe(resumo_estados_exibicao.drop(columns=['SLA_Num']).head(10), hide_index=True)

            if not resumo_estados.empty:
                fig2, ax2 = plt.subplots(figsize=(10, 4))
                sns.barplot(x='state', y='SLA_Num', data=resumo_estados, palette='RdYlGn', ax=ax2)
                ax2.axhline(y=pct_geral, color='blue', linestyle='--', label=f'Média Geral ({pct_geral:.1f}%)')
                ax2.set_title('SLA de Entregas Pendentes por Estado (% No Prazo)', fontweight='bold')
                ax2.set_ylim(0, 105)
                ax2.legend()
                plt.xticks(rotation=45)
                st.pyplot(fig2)

            # 5. LISTAGEM DE ATRASADOS
            st.markdown("---")
            st.subheader("Cenário de Vencimentos")
            
            df_pendentes = df[df['prazo_entrega'].notna()].copy()
            df_pendentes['data_vencimento'] = df_pendentes['prazo_entrega'].dt.floor('D')
            agrupado_vencimentos = df_pendentes.groupby('data_vencimento').size().reset_index(name='qtd_kits')
            
            mask_ja_atrasado = agrupado_vencimentos['data_vencimento'] < data_atualizacao
            df_ja_atrasado = agrupado_vencimentos[mask_ja_atrasado]
            df_a_vencer = agrupado_vencimentos[~mask_ja_atrasado].copy()
            df_a_vencer['dia'] = df_a_vencer['data_vencimento'].dt.strftime('%d/%m')
            df_a_vencer['Status Vencimento'] = 'A Vencer / Hoje'

            if not df_ja_atrasado.empty:
                total_atrasados_lista = df_ja_atrasado['qtd_kits'].sum()
                linha_atrasado = pd.DataFrame({'dia': ['Já Atrasado'], 'qtd_kits': [total_atrasados_lista], 'Status Vencimento': ['Já Atrasado']})
                previsao_vencimentos = pd.concat([linha_atrasado, df_a_vencer[['dia', 'qtd_kits', 'Status Vencimento']]], ignore_index=True)
            else:
                previsao_vencimentos = df_a_vencer[['dia', 'qtd_kits', 'Status Vencimento']]
            
            col_list, col_graf = st.columns([1, 2])
            
            with col_list:
                st.dataframe(previsao_vencimentos, hide_index=True)

            with col_graf:
                df_grafico = previsao_vencimentos.head(15) 
                if not df_grafico.empty:
                    fig3, ax3 = plt.subplots(figsize=(10, 4))
                    cores = ['#F44336' if status == 'Já Atrasado' else '#FF9800' for status in df_grafico['Status Vencimento']]
                    sns.barplot(x='dia', y='qtd_kits', data=df_grafico, palette=cores, ax=ax3)
                    ax3.set_title('Atrasados Consolidados vs Previsão Diária', fontweight='bold')
                    plt.xticks(rotation=45)
                    st.pyplot(fig3)

            # 6. TEXTO EXECUTIVO
            st.markdown("---")
            st.subheader("Texto Executivo (Copie para enviar)")
            
            texto_resumo = f"📊 *RESUMO DE SLA - KITS EM TRÂNSITO* 📊\n\n*Visão Geral:*\n📦 Total de Kits Pendentes: {total_geral}\n✅ No Prazo: {total_no_prazo} ({pct_geral:.1f}%)\n❌ Atrasados: {total_atrasado} ({(100 - pct_geral) if total_geral > 0 else 0:.1f}%)\n\n*Desempenho por Estado:*\n"
            for _, row in resumo_estados.iterrows():
                texto_resumo += f"- {row['state']}: {formatar_porcentagem(row['SLA_Num'])} no prazo (Volume: {row['total_pedidos']} kits)\n"
            
            texto_resumo += "\n*Cenário Completo de Vencimentos:*\n"
            if not previsao_vencimentos.empty:
                for _, row in previsao_vencimentos.iterrows():
                    if row['Status Vencimento'] == 'Já Atrasado':
                        texto_resumo += f"🚨 Já em atraso: {row['qtd_kits']} kits\n"
                    else:
                        texto_resumo += f"📅 Vencendo em {row['dia']}: {row['qtd_kits']} kits\n"
            
            st.code(texto_resumo, language='markdown')

            # 7. DOWNLOAD EXCEL (Usando buffer em memória)
            st.markdown("---")
            resumo_estados['SLA_%'] = resumo_estados['SLA_Num'].apply(formatar_porcentagem)
            resumo_estados = resumo_estados.drop(columns=['SLA_Num'])
            df = df.drop(columns=['is_no_prazo'])

            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                resumo_geral.to_excel(writer, sheet_name='Visao_Geral', index=False)
                resumo_estados.to_excel(writer, sheet_name='SLA_por_Estado', index=False)
                if not previsao_vencimentos.empty:
                    col_exp = previsao_vencimentos.rename(columns={'dia': 'Data Vencimento', 'qtd_kits': 'Qtd. Kits'})
                    col_exp.to_excel(writer, sheet_name='Listagem_Atrasos', index=False)
                df.to_excel(writer, sheet_name='Base_Detalhada', index=False)
            
            st.download_button(
                label="📥 Baixar Planilha Consolidada",
                data=buffer.getvalue(),
                file_name="analise_sla_completa.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        except Exception as e:
            st.error(f"Ocorreu um erro ao processar o arquivo: {e}")
