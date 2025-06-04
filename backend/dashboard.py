import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np

try:
    from config import current_config
    errors = current_config.validar_configuracao()
    if errors:
        st.error("ERROS DE CONFIGURAÇÃO ENCONTRADOS NO DASHBOARD:")
        for error in errors:
            st.error(f"- {error}")
        st.error("Verifique seu arquivo .env ou variáveis de ambiente. O dashboard pode não funcionar corretamente.")
except ImportError:
    st.error("❌ Não foi possível importar o módulo config. Verifique se o arquivo config.py está no mesmo diretório.")
    class MockConfig:
        TEMP_MIN_ALERTA = 5
        TEMP_MAX_ALERTA = 30
    current_config = MockConfig()


try:
    from db_config import get_mongodb_connection
except ImportError:
    st.error("❌ Não foi possível importar o módulo db_config. Verifique se o arquivo db_config.py está no mesmo diretório.")
    def get_mongodb_connection():
        st.error("Função de conexão com MongoDB não disponível (db_config.py não encontrado).")
        return None, None, None

st.set_page_config(
    page_title="Dashboard de Monitoramento ESP32",
    page_icon="🌡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .reportview-container { background-color: #0e1117; color: white; }
    .sidebar .sidebar-content { background-color: #0e1117; }
    h1, h2, h3 { color: white; }
    .stMetric { background-color: #262730; padding: 15px; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.2); color: white; }
    .stMetric label { color: white !important; }
    .stMetric .metric-value { color: white !important; } /* Corrigido para afetar o valor */
    div[data-testid="stExpander"] { background-color: #262730; border-radius: 5px; }
    .streamlit-expanderHeader { color: white !important; }
    .streamlit-expanderContent { background-color: #262730; }
    .status-indicator { padding: 8px 12px; border-radius: 4px; font-weight: bold; display: inline-block; margin: 2px; }
    .status-normal { background-color: #28a745; color: white; }
    .status-alerta-temperatura { background-color: #ffc107; color: black; }
    .status-critico-temperatura { background-color: #dc3545; color: white; }
    .status-erro-sensor { background-color: #6c757d; color: white; }
    .status-erro-leitura { background-color: #17a2b8; color: white; }
    .status-alerta-umidade { background-color: #fd7e14; color: white; } /* Corrigido para alerta_umidade */
    .status-critico-umidade { background-color: #9c27b0; color: white; } /* Corrigido para critico_umidade */
    .data-grid { font-size: 12px; }
</style>
""", unsafe_allow_html=True)


st.title("Dashboard de Monitoramento Ambiental")
st.write("Visualização de temperatura e umidade coletadas pelo ESP32")

mongodb_available = False
collection = None
try:
    _, _, collection_temp = get_mongodb_connection()
    if collection_temp is not None:
        collection = collection_temp
        mongodb_available = True
except Exception as e:
    st.warning(f"⚠️ Não foi possível conectar ao MongoDB devido a um erro: {e}. Usando dados simulados se disponíveis.")
    mongodb_available = False


plotly_template = "plotly_dark"

with st.sidebar:
    if mongodb_available:
        st.success("✅ Conectado ao MongoDB")
    else:
        st.warning("⚠️ MongoDB não disponível, usando dados simulados.")
    
    st.header("Controles")
    period = st.selectbox(
        "Selecione o período:",
        ["Última hora", "Últimas 6 horas", "Últimas 24 horas", "Últimos 7 dias", "Últimos 30 dias", "Todos os dados (CSV)"]
    )
    
    st.subheader("Filtrar por Status")
    status_options = ["Todos", "normal", "alerta_temperatura", "critico_temperatura", 
                      "erro_sensor", "erro_leitura", "alerta_umidade", "critico_umidade"]
    selected_status = st.multiselect("Status", status_options, default=["Todos"])
    
    auto_refresh_interval = st.selectbox(
        "Intervalo de atualização automática (segundos):",
        [0, 10, 30, 60, 300],
        index=0,
        format_func=lambda x: "Desligado" if x == 0 else f"{x}s"
    )

    refresh_button_key = "refresh_button"
    if st.button("🔄 Atualizar Dados", key=refresh_button_key):
        st.cache_data.clear()

@st.cache_data(ttl=300)
def load_simulated_data():
    try:
        csv_path = "dht11_simulated_data_90days.csv"
        df = pd.read_csv(csv_path)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        if 'status' not in df.columns:
            from utils import determinar_status
            config_to_use_for_simulated = current_config if 'current_config' in globals() and hasattr(current_config, 'TEMP_MIN_ALERTA') else None
            if config_to_use_for_simulated:
                 df['status'] = df.apply(lambda row: determinar_status(row['temperatura'], row['umidade'], config_to_use_for_simulated), axis=1)
            else:
                 df['status'] = "normal"
        return df
    except Exception as e:
        st.error(f"Erro ao carregar dados simulados: {e}")
        return pd.DataFrame(columns=['timestamp', 'temperatura', 'umidade', 'status'])


@st.cache_data(ttl=60)
def get_data_for_period(selected_period, use_mongodb=True):
    """
    Função corrigida que não passa o objeto collection diretamente para evitar problemas de hash
    """
    now = datetime.now()
    start_date = now
    
    if selected_period == "Última hora":
        start_date = now - timedelta(hours=1)
    elif selected_period == "Últimas 6 horas":
        start_date = now - timedelta(hours=6)
    elif selected_period == "Últimas 24 horas":
        start_date = now - timedelta(days=1)
    elif selected_period == "Últimos 7 dias":
        start_date = now - timedelta(weeks=1)
    elif selected_period == "Últimos 30 dias":
        start_date = now - timedelta(days=30)

    if use_mongodb and selected_period != "Todos os dados (CSV)":
        try:
            _, _, mongo_collection = get_mongodb_connection()
            if mongo_collection is not None:
                cursor = mongo_collection.find({"timestamp": {"$gte": start_date}}).sort("timestamp", 1)
                data = list(cursor)
                if not data:
                    st.info(f"Nenhum dado do MongoDB encontrado para '{selected_period}'. Tentando dados simulados.")
                    sim_df = load_simulated_data()
                    return sim_df[sim_df['timestamp'] >= start_date] if not sim_df.empty else pd.DataFrame()

                for item in data:
                    if '_id' in item: item['_id'] = str(item['_id'])
                return pd.DataFrame(data)
            else:
                sim_df = load_simulated_data()
                return sim_df[sim_df['timestamp'] >= start_date] if not sim_df.empty else pd.DataFrame()
        except Exception as e:
            st.error(f"Erro ao consultar MongoDB: {e}")
            sim_df = load_simulated_data()
            return sim_df[sim_df['timestamp'] >= start_date] if not sim_df.empty else pd.DataFrame()
    else:
        simulated_df = load_simulated_data()
        if selected_period == "Todos os dados (CSV)":
             return simulated_df
        return simulated_df[simulated_df['timestamp'] >= start_date] if not simulated_df.empty else pd.DataFrame()


df_display = get_data_for_period(period, mongodb_available)

if df_display.empty:
    st.warning(f"⚠️ Nenhum dado encontrado para o período selecionado: '{period}'.")
    if auto_refresh_interval > 0:
        try:
            st.rerun()  
        except AttributeError:
            st.experimental_rerun()
    st.stop()

if 'status' not in df_display.columns:
    st.error("❌ Coluna 'status' não encontrada nos dados. Verifique a fonte dos dados (MongoDB ou CSV).")
    st.dataframe(df_display.head())
    st.stop()

if "Todos" not in selected_status and selected_status:
    df_display = df_display[df_display['status'].isin(selected_status)]
    if df_display.empty:
        st.warning(f"⚠️ Nenhum dado encontrado para os status selecionados: {', '.join(selected_status)}")
        if auto_refresh_interval > 0:
            try:
                st.rerun()
            except AttributeError:
                st.experimental_rerun()
        st.stop()

df_display['temperatura'] = pd.to_numeric(df_display['temperatura'], errors='coerce')
df_display['umidade'] = pd.to_numeric(df_display['umidade'], errors='coerce')
df_display['timestamp'] = pd.to_datetime(df_display['timestamp'], errors='coerce')
df_display.dropna(subset=['timestamp'], inplace=True)

st.write(f"Exibindo {len(df_display)} registros para o período: **{period}**")
if not df_display.empty:
    st.write(f"Primeiro registro: {df_display['timestamp'].min().strftime('%d/%m/%Y %H:%M') if pd.notna(df_display['timestamp'].min()) else 'N/A'}")
    st.write(f"Último registro: {df_display['timestamp'].max().strftime('%d/%m/%Y %H:%M') if pd.notna(df_display['timestamp'].max()) else 'N/A'}")


status_colors = {
    'normal': '#28a745', 'alerta_temperatura': '#ffc107', 'critico_temperatura': '#dc3545',
    'erro_sensor': '#6c757d', 'erro_leitura': '#17a2b8', 'alerta_umidade': '#fd7e14',
    'critico_umidade': '#9c27b0'
}
status_descriptions = {
    'normal': 'Normal', 'alerta_temperatura': 'Alerta Temp.', 'critico_temperatura': 'Crítico Temp.',
    'erro_sensor': 'Erro Sensor', 'erro_leitura': 'Erro Leitura', 'alerta_umidade': 'Alerta Umid.',
    'critico_umidade': 'Crítico Umid.'
}

if not df_display.empty:
    st.header("Status e KPIs Recentes")
    latest_record = df_display.iloc[-1]
    latest_status = latest_record['status']
    
    col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
    with col_kpi1:
        temp_atual = latest_record['temperatura']
        delta_temp = None
        if len(df_display) > 1:
            temp_anterior = df_display['temperatura'].iloc[-2]
            if pd.notna(temp_atual) and pd.notna(temp_anterior):
                delta_temp = temp_atual - temp_anterior
        st.metric("Temperatura Atual", 
                  f"{temp_atual:.1f}°C" if pd.notna(temp_atual) else "N/A",
                  delta=f"{delta_temp:.1f}°C" if pd.notna(delta_temp) else None)

    with col_kpi2:
        umid_atual = latest_record['umidade']
        delta_umid = None
        if len(df_display) > 1:
            umid_anterior = df_display['umidade'].iloc[-2]
            if pd.notna(umid_atual) and pd.notna(umid_anterior):
                delta_umid = umid_atual - umid_anterior
        st.metric("Umidade Atual", 
                  f"{umid_atual:.1f}%" if pd.notna(umid_atual) else "N/A",
                  delta=f"{delta_umid:.1f}%" if pd.notna(delta_umid) else None)

    with col_kpi3:
        status_text = status_descriptions.get(latest_status, latest_status.replace("_", " ").title())
        st.markdown(f"""
        **Status Atual:**
        <div class="status-indicator" style="background-color: {status_colors.get(latest_status, '#6c757d')}; color: {'black' if latest_status == 'alerta_temperatura' else 'white'};">
            {status_text}
        </div>
        """, unsafe_allow_html=True)
        st.markdown(f"<small>Em: {latest_record['timestamp'].strftime('%d/%m/%y %H:%M:%S')}</small>", unsafe_allow_html=True)


    st.header("Análise de Status no Período")
    col_dist, col_time = st.columns([1,2])
    with col_dist:
        status_counts = df_display['status'].value_counts().reset_index()
        status_counts.columns = ['status', 'count']
        fig_status_pie = px.pie(status_counts, values='count', names='status', title="Distribuição de Status",
                                color='status', color_discrete_map=status_colors, template=plotly_template)
        fig_status_pie.update_traces(textposition='inside', textinfo='percent+label')
        fig_status_pie.update_layout(legend_title_text='Status')
        st.plotly_chart(fig_status_pie, use_container_width=True)
    
    with col_time:
        df_timeline = df_display.copy()
        df_timeline['status_label'] = df_timeline['status'].map(status_descriptions).fillna(df_timeline['status'])
        fig_timeline = px.scatter(df_timeline, x='timestamp', y='status_label', color='status',
                                  color_discrete_map=status_colors, title="Timeline de Status",
                                  labels={"timestamp": "Data/Hora", "status_label": "Status"},
                                  template=plotly_template)
        fig_timeline.update_traces(marker=dict(size=8))
        st.plotly_chart(fig_timeline, use_container_width=True)

else:
    st.warning("⚠️ Não há dados suficientes para exibir o status atual e KPIs.")


st.header("Variação de Temperatura e Umidade")
st.header("Temperatura ao Longo do Tempo")

temp_df_chart = df_display.dropna(subset=['temperatura']).copy()
if not temp_df_chart.empty:
    fig_temp = px.line(
        temp_df_chart, 
        x='timestamp', 
        y='temperatura',
        title="Variação de Temperatura",
        labels={"timestamp": "Data/Hora", "temperatura": "Temperatura (°C)"},
        template=plotly_template,
        color_discrete_sequence=['firebrick']
    )
    
    non_normal_temp = temp_df_chart[~temp_df_chart['status'].isin(['normal', 'erro_leitura', 'erro_sensor'])].copy()
    non_normal_temp['marker_color'] = non_normal_temp['status'].map(status_colors)

    if not non_normal_temp.empty:
        fig_temp.add_trace(
            go.Scatter(
                x=non_normal_temp['timestamp'],
                y=non_normal_temp['temperatura'],
                mode='markers',
                marker=dict(
                    size=8,
                    color=non_normal_temp['marker_color'],
                    symbol='circle',
                    line=dict(width=1, color='DarkSlateGrey')
                ),
                name='Status Relevante',
                customdata=non_normal_temp['status'],
                hovertemplate='<b>Status: %{customdata}</b><br>Temp: %{y}°C<br>Hora: %{x|%H:%M:%S}<extra></extra>'
            )
        )
    
    fig_temp.update_layout(height=400, showlegend=True)
    st.plotly_chart(fig_temp, use_container_width=True)
else:
    st.warning("⚠️ Não há dados válidos de temperatura para gerar o gráfico no período.")

st.header("Umidade ao Longo do Tempo")

humid_df_chart = df_display.dropna(subset=['umidade']).copy()
if not humid_df_chart.empty:
    fig_umid = px.line(
        humid_df_chart, 
        x='timestamp', 
        y='umidade',
        title="Variação de Umidade",
        labels={"timestamp": "Data/Hora", "umidade": "Umidade (%)"},
        template=plotly_template,
        color_discrete_sequence=['royalblue']
    )
    
    non_normal_humid = humid_df_chart[~humid_df_chart['status'].isin(['normal', 'erro_leitura', 'erro_sensor'])].copy()
    non_normal_humid['marker_color'] = non_normal_humid['status'].map(status_colors)

    if not non_normal_humid.empty:
        fig_umid.add_trace(
            go.Scatter(
                x=non_normal_humid['timestamp'],
                y=non_normal_humid['umidade'],
                mode='markers',
                marker=dict(
                    size=8,
                    color=non_normal_humid['marker_color'],
                    symbol='circle',
                    line=dict(width=1, color='DarkSlateGrey')
                ),
                name='Status Relevante',
                customdata=non_normal_humid['status'],
                hovertemplate='<b>Status: %{customdata}</b><br>Umid: %{y}%<br>Hora: %{x|%H:%M:%S}<extra></extra>'
            )
        )
    
    fig_umid.update_layout(height=400, showlegend=True)
    st.plotly_chart(fig_umid, use_container_width=True)
else:
    st.warning("⚠️ Não há dados válidos de umidade para gerar o gráfico no período.")

st.header("Comparação de Temperatura e Umidade")

combined_df_chart = df_display.dropna(subset=['temperatura', 'umidade'], how='all').copy()

if not combined_df_chart.empty:
    fig_combined = go.Figure()
    
    temp_valid_combined = combined_df_chart.dropna(subset=['temperatura'])
    if not temp_valid_combined.empty:
        fig_combined.add_trace(go.Scatter(
            x=temp_valid_combined['timestamp'], y=temp_valid_combined['temperatura'],
            name='Temperatura (°C)', line=dict(color='firebrick', width=2), yaxis='y'
        ))
    
    humid_valid_combined = combined_df_chart.dropna(subset=['umidade'])
    if not humid_valid_combined.empty:
        fig_combined.add_trace(go.Scatter(
            x=humid_valid_combined['timestamp'], y=humid_valid_combined['umidade'],
            name='Umidade (%)', line=dict(color='royalblue', width=2), yaxis='y2'
        ))
    
    status_points_combined = combined_df_chart[~combined_df_chart['status'].isin(['normal', 'erro_leitura', 'erro_sensor'])].copy()
    status_points_combined['marker_color'] = status_points_combined['status'].map(status_colors)

    if not status_points_combined.empty:
        temp_status_points = status_points_combined.dropna(subset=['temperatura'])
        if not temp_status_points.empty:
            fig_combined.add_trace(go.Scatter(
                x=temp_status_points['timestamp'], y=temp_status_points['temperatura'],
                mode='markers', marker=dict(size=10, color=temp_status_points['marker_color'], symbol='circle'),
                name='Status Temp.', yaxis='y', showlegend=True,
                customdata=temp_status_points['status'],
                hovertemplate='<b>Status: %{customdata}</b><br>Temp: %{y}°C<extra></extra>'
            ))
        
        humid_status_points = status_points_combined.dropna(subset=['umidade'])
        if not humid_status_points.empty:
            fig_combined.add_trace(go.Scatter(
                x=humid_status_points['timestamp'], y=humid_status_points['umidade'],
                mode='markers', marker=dict(size=10, color=humid_status_points['marker_color'], symbol='triangle-up'),
                name='Status Umid.', yaxis='y2', showlegend=True,
                customdata=humid_status_points['status'],
                hovertemplate='<b>Status: %{customdata}</b><br>Umid: %{y}%<extra></extra>'
            ))

    min_temp_val = combined_df_chart['temperatura'].min()
    max_temp_val = combined_df_chart['temperatura'].max()
    min_umid_val = combined_df_chart['umidade'].min()
    max_umid_val = combined_df_chart['umidade'].max()

    fig_combined.update_layout(
        title='Temperatura e Umidade ao Longo do Tempo', template=plotly_template,
        xaxis=dict(title='Data/Hora'),
        yaxis=dict(title='Temperatura (°C)', color='firebrick', tickfont=dict(color='firebrick'),
                   range=[min_temp_val * 0.9 if pd.notna(min_temp_val) else 0, max_temp_val * 1.1 if pd.notna(max_temp_val) else 50]),
        yaxis2=dict(title='Umidade (%)', color='royalblue', tickfont=dict(color='royalblue'), anchor='x', overlaying='y', side='right',
                    range=[min_umid_val * 0.9 if pd.notna(min_umid_val) else 0, max_umid_val * 1.1 if pd.notna(max_umid_val) else 100]),
        height=500, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig_combined, use_container_width=True)
else:
    st.warning("⚠️ Dados insuficientes para gerar o gráfico combinado no período.")

st.header("Análise de Distribuição")
col_hist1, col_hist2 = st.columns(2)

with col_hist1:
    temp_valid_hist = df_display.dropna(subset=['temperatura'])
    if not temp_valid_hist.empty:
        fig_hist_temp = px.histogram(temp_valid_hist, x="temperatura", nbins=20, title="Distribuição de Temperatura",
                                     labels={"temperatura": "Temperatura (°C)", "count": "Frequência"},
                                     color_discrete_sequence=['firebrick'], template=plotly_template)
        fig_hist_temp.update_layout(bargap=0.1)
        st.plotly_chart(fig_hist_temp, use_container_width=True)
    else:
        st.warning("⚠️ Dados insuficientes para histograma de temperatura no período.")

with col_hist2:
    humid_valid_hist = df_display.dropna(subset=['umidade'])
    if not humid_valid_hist.empty:
        fig_hist_umid = px.histogram(humid_valid_hist, x="umidade", nbins=20, title="Distribuição de Umidade",
                                     labels={"umidade": "Umidade (%)", "count": "Frequência"},
                                     color_discrete_sequence=['royalblue'], template=plotly_template)
        fig_hist_umid.update_layout(bargap=0.1)
        st.plotly_chart(fig_hist_umid, use_container_width=True)
    else:
        st.warning("⚠️ Dados insuficientes para histograma de umidade no período.")

st.header("Análise Média por Status")
status_group = df_display.groupby('status').agg(
    temperatura_media=('temperatura', lambda x: x.dropna().mean()),
    umidade_media=('umidade', lambda x: x.dropna().mean()),
    contagem=('timestamp', 'count')
).reset_index()

col_status_bar1, col_status_bar2 = st.columns(2)
with col_status_bar1:
    fig_temp_status = px.bar(status_group.dropna(subset=['temperatura_media']), x='status', y='temperatura_media',
                             title="Temperatura Média por Status", labels={"status": "Status", "temperatura_media": "Temp. Média (°C)"},
                             color='status', color_discrete_map=status_colors, template=plotly_template)
    st.plotly_chart(fig_temp_status, use_container_width=True)

with col_status_bar2:
    fig_humid_status = px.bar(status_group.dropna(subset=['umidade_media']), x='status', y='umidade_media',
                              title="Umidade Média por Status", labels={"status": "Status", "umidade_media": "Umid. Média (%)"},
                              color='status', color_discrete_map=status_colors, template=plotly_template)
    st.plotly_chart(fig_humid_status, use_container_width=True)

with st.expander("Mostrar dados brutos", expanded=False):
    st.subheader(f"Registros no Dataset ({len(df_display)})")
    if not df_display.empty:
        st.dataframe(df_display.sort_values('timestamp', ascending=False), use_container_width=True, height=300)
        
        csv = df_display.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download dos dados filtrados (CSV)", csv, f"dados_ambientais_{period.replace(' ','_').lower()}.csv",
                           "text/csv", key='download-csv')
    else:
        st.warning("⚠️ Não há dados para exibir.")

st.header("Alertas Recentes (Não 'Normal')")
alerts_df_display = df_display[df_display['status'] != 'normal'].sort_values('timestamp', ascending=False).head(10)

if not alerts_df_display.empty:
    for _, alert in alerts_df_display.iterrows():
        alert_color = status_colors.get(alert['status'], '#6c757d')
        alert_time = alert['timestamp'].strftime('%d/%m/%Y %H:%M:%S') if pd.notna(alert['timestamp']) else "N/A"
        temp_value = f"{alert['temperatura']:.1f}°C" if pd.notna(alert['temperatura']) else "N/A"
        humid_value = f"{alert['umidade']:.1f}%" if pd.notna(alert['umidade']) else "N/A"
        
        st.markdown(f"""
        <div style="background-color: {alert_color}; padding: 10px; border-radius: 5px; margin-bottom: 10px; color: {'black' if alert['status'] == 'alerta_temperatura' else 'white'};">
            <strong>{status_descriptions.get(alert['status'], alert['status'].upper())}</strong> - {alert_time}<br>
            Temperatura: {temp_value} | Umidade: {humid_value}
        </div>
        """, unsafe_allow_html=True)
else:
    st.info("✅ Nenhum alerta (não 'Normal') registrado no período selecionado.")

st.markdown("---")
st.info("✉️ Para dúvidas ou suporte, entre em contato com a equipe técnica.")
''
if auto_refresh_interval > 0:
    import time
    try:
        time.sleep(auto_refresh_interval)
        st.rerun()
    except AttributeError:
        time.sleep(auto_refresh_interval)
        st.experimental_rerun()
