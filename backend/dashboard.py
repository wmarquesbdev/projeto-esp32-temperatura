import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np

try:
    from db_config import get_mongodb_connection
except ImportError:
    st.error("❌ Não foi possível importar o módulo db_config. Verifique se o arquivo db_config.py está no mesmo diretório.")
    
    def get_mongodb_connection():
        st.error("Função de conexão com MongoDB não disponível.")
        return None, None, None

st.set_page_config(
    page_title="Dashboard de Monitoramento ESP32",
    page_icon="🌡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .reportview-container {
        background-color: #0e1117;
        color: white;
    }
    .sidebar .sidebar-content {
        background-color: #0e1117;
    }
    h1, h2, h3 {
        color: white;
    }
    .stMetric {
        background-color: #262730;
        padding: 15px;
        border-radius: 5px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.2);
        color: white;
    }
    .stMetric label {
        color: white !important;
    }
    .stMetric .metric-value {
        color: white !important;
    }
    div[data-testid="stExpander"] {
        background-color: #262730;
        border-radius: 5px;
    }
    .streamlit-expanderHeader {
        color: white !important;
    }
    .streamlit-expanderContent {
        background-color: #262730;
    }
    .status-indicator {
        padding: 8px 12px;
        border-radius: 4px;
        font-weight: bold;
        display: inline-block;
        margin: 2px;
    }
    .status-normal {
        background-color: #28a745;
        color: white;
    }
    .status-alerta-temperatura {
        background-color: #ffc107;
        color: black;
    }
    .status-critico-temperatura {
        background-color: #dc3545;
        color: white;
    }
    .status-erro-sensor {
        background-color: #6c757d;
        color: white;
    }
    .status-erro-leitura {
        background-color: #17a2b8;
        color: white;
    }
    .status-alerta-umidade {
        background-color: #fd7e14;
        color: white;
    }
    .status-critico-umidade {
        background-color: #9c27b0;
        color: white;
    }
    .data-grid {
        font-size: 12px;
    }
</style>
""", unsafe_allow_html=True)

st.title("Dashboard de Monitoramento Ambiental")
st.write("Visualização em tempo real de temperatura e umidade coletadas pelo ESP32")

# Tentar carregar dados do MongoDB ou usar dados simulados do arquivo CSV
try:
    _, _, collection = get_mongodb_connection()
    mongodb_available = collection is not None
except:
    mongodb_available = False

# Configuração de estilo para os gráficos Plotly
plotly_template = "plotly_dark"

# Sidebar
with st.sidebar:
    if mongodb_available:
        st.sidebar.success("✅ Conectado ao MongoDB")
    else:
        st.sidebar.warning("⚠️ MongoDB não disponível, usando dados simulados")
    
    st.header("Controles")
    period = st.selectbox(
        "Selecione o período:",
        ["Última hora", "Últimas 24 horas", "Última semana", "Último mês"]
    )
    
    # Filtro por status
    st.subheader("Filtrar por Status")
    status_options = ["Todos", "normal", "alerta_temperatura", "critico_temperatura", 
                      "erro_sensor", "erro_leitura", "alerta_umidade", "critico_umidade"]
    selected_status = st.multiselect("Status", status_options, default=["Todos"])
    
    refresh = st.button("🔄 Atualizar Dados")

# Funções auxiliares
def load_simulated_data():
    """Carrega dados simulados de um arquivo CSV"""
    try:
        # Caminho para o arquivo CSV de dados simulados
        csv_path = "dht11_simulated_data_90days.csv"
        df = pd.read_csv(csv_path)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df
    except Exception as e:
        st.error(f"Erro ao carregar dados simulados: {e}")
        return pd.DataFrame()

def get_data_for_period(period, collection=None):
    """Busca dados do MongoDB ou carrega dados simulados baseado no período selecionado"""
    now = datetime.now()
    
    if period == "Última hora":
        start_date = now - timedelta(hours=1)
    elif period == "Últimas 24 horas":
        start_date = now - timedelta(days=1)
    elif period == "Última semana":
        start_date = now - timedelta(weeks=1)
    else:
        start_date = now - timedelta(days=30)
    
    # Se temos acesso ao MongoDB, tentamos buscar os dados de lá
    if collection is not None:
        try:
            cursor = collection.find({
                "timestamp": {"$gte": start_date}
            }).sort("timestamp", 1)
            
            data = list(cursor)
            for item in data:
                item['_id'] = str(item['_id'])
            
            return pd.DataFrame(data)
        except Exception as e:
            st.error(f"Erro ao consultar MongoDB: {e}")
            
    # Se não conseguimos do MongoDB, usamos dados simulados
    simulated_df = load_simulated_data()
    if simulated_df.empty:
        return simulated_df
        
    # Filtrar pelo período
    filtered_df = simulated_df[simulated_df['timestamp'] >= start_date]
    return filtered_df

# Carregar os dados
if mongodb_available:
    df = get_data_for_period(period, collection)
else:
    df = get_data_for_period(period)

# Verificar se temos dados
if df is None or df.empty:
    st.warning("⚠️ Nenhum dado encontrado para o período selecionado.")
    st.stop()

# Verificar se a coluna 'status' existe no DataFrame
if 'status' not in df.columns:
    st.error("❌ Coluna 'status' não encontrada nos dados. Verifique o formato dos dados.")
    st.stop()

# Filtrar por status, se necessário
if "Todos" not in selected_status and selected_status:
    df = df[df['status'].isin(selected_status)]
    if df.empty:
        st.warning(f"⚠️ Nenhum dado encontrado para os status selecionados: {', '.join(selected_status)}")
        st.stop()

# Tratar valores nulos
df['temperatura'] = pd.to_numeric(df['temperatura'], errors='coerce')
df['umidade'] = pd.to_numeric(df['umidade'], errors='coerce')

st.write(f"Exibindo {len(df)} registros para o período: **{period}**")
st.write(f"Primeiro registro: {df['timestamp'].min().strftime('%d/%m/%Y %H:%M')}")
st.write(f"Último registro: {df['timestamp'].max().strftime('%d/%m/%Y %H:%M')}")

# Exibição do Status Atual
st.header("Status do Sistema")

# Verificar se temos registros antes de acessar o último
if len(df) > 0:
    latest_status = df['status'].iloc[-1]

    status_colors = {
        'normal': '#28a745',
        'alerta_temperatura': '#ffc107',
        'critico_temperatura': '#dc3545',
        'erro_sensor': '#6c757d',
        'erro_leitura': '#17a2b8',
        'alerta_umidade': '#fd7e14',
        'critico_umidade': '#9c27b0'
    }

    status_descriptions = {
        'normal': 'Sistema operando normalmente',
        'alerta_temperatura': 'Temperatura em nível de alerta',
        'critico_temperatura': 'Temperatura em nível crítico',
        'erro_sensor': 'Falha no sensor de leitura',
        'erro_leitura': 'Erro na leitura de dados',
        'alerta_umidade': 'Umidade em nível de alerta',
        'critico_umidade': 'Umidade em nível crítico'
    }

    col1, col2 = st.columns([1, 3])
    with col1:
        st.metric("Status Atual", latest_status)
    with col2:
        st.markdown(f"""
        <div class="status-indicator" style="background-color: {status_colors.get(latest_status, '#6c757d')}; color: white;">
            {status_descriptions.get(latest_status, 'Status desconhecido')}
        </div>
        """, unsafe_allow_html=True)

    # Contagem de status nos últimos registros
    status_counts = df['status'].value_counts().reset_index()
    status_counts.columns = ['status', 'count']

    col1, col2 = st.columns([2, 2])

    with col1:
        fig_status = px.pie(
            status_counts, 
            values='count', 
            names='status',
            title="Distribuição de Status",
            color='status',
            color_discrete_map=status_colors,
            template=plotly_template
        )
        fig_status.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_status, use_container_width=True)

    with col2:
        # Timeline de status
        status_timeline = df.copy()
        status_timeline['color'] = status_timeline['status'].map(status_colors)
        
        fig_timeline = px.scatter(
            status_timeline,
            x='timestamp',
            y='status',
            color='status',
            color_discrete_map=status_colors,
            title="Timeline de Status",
            template=plotly_template
        )
        fig_timeline.update_traces(marker=dict(size=10))
        st.plotly_chart(fig_timeline, use_container_width=True)
else:
    st.warning("⚠️ Não há dados suficientes para exibir o status atual.")

# Estatísticas de Temperatura
st.header("Estatísticas de Temperatura")

# Verificar valores válidos de temperatura para estatísticas
valid_temp = df['temperatura'].dropna()
if len(valid_temp) > 0:
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        current_temp = valid_temp.iloc[-1] if not valid_temp.empty else "N/A"
        delta_temp = None
        if len(valid_temp) > 1 and not pd.isna(valid_temp.iloc[-2]):
            delta_temp = current_temp - valid_temp.iloc[-2]
        
        st.metric("Temperatura Atual", 
                 f"{current_temp:.1f}°C" if isinstance(current_temp, (int, float)) else current_temp, 
                 delta=f"{delta_temp:.1f}°C" if delta_temp is not None else None)
    
    with col2:
        max_temp = valid_temp.max() if not valid_temp.empty else "N/A"
        st.metric("Temperatura Máxima", f"{max_temp:.1f}°C" if isinstance(max_temp, (int, float)) else max_temp)
    
    with col3:
        min_temp = valid_temp.min() if not valid_temp.empty else "N/A"
        st.metric("Temperatura Mínima", f"{min_temp:.1f}°C" if isinstance(min_temp, (int, float)) else min_temp)
    
    with col4:
        mean_temp = valid_temp.mean() if not valid_temp.empty else "N/A"
        st.metric("Média", f"{mean_temp:.1f}°C" if isinstance(mean_temp, (int, float)) else mean_temp)
else:
    st.warning("⚠️ Não há dados válidos de temperatura para o período selecionado.")

# Estatísticas de Umidade
st.header("Estatísticas de Umidade")

# Verificar valores válidos de umidade para estatísticas
valid_humid = df['umidade'].dropna()
if len(valid_humid) > 0:
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        current_humid = valid_humid.iloc[-1] if not valid_humid.empty else "N/A"
        delta_humid = None
        if len(valid_humid) > 1 and not pd.isna(valid_humid.iloc[-2]):
            delta_humid = current_humid - valid_humid.iloc[-2]
        
        st.metric("Umidade Atual", 
                 f"{current_humid:.1f}%" if isinstance(current_humid, (int, float)) else current_humid, 
                 delta=f"{delta_humid:.1f}%" if delta_humid is not None else None)
    
    with col2:
        max_humid = valid_humid.max() if not valid_humid.empty else "N/A"
        st.metric("Umidade Máxima", f"{max_humid:.1f}%" if isinstance(max_humid, (int, float)) else max_humid)
    
    with col3:
        min_humid = valid_humid.min() if not valid_humid.empty else "N/A"
        st.metric("Umidade Mínima", f"{min_humid:.1f}%" if isinstance(min_humid, (int, float)) else min_humid)
    
    with col4:
        mean_humid = valid_humid.mean() if not valid_humid.empty else "N/A"
        st.metric("Média", f"{mean_humid:.1f}%" if isinstance(mean_humid, (int, float)) else mean_humid)
else:
    st.warning("⚠️ Não há dados válidos de umidade para o período selecionado.")

# Gráficos de série temporal
st.header("Temperatura ao Longo do Tempo")

# Criar um dataframe filtrado para o gráfico de temperatura (removendo valores nulos)
temp_df = df.dropna(subset=['temperatura']).copy()
if not temp_df.empty:
    # Marcar status não-normais com cores diferentes
    temp_df['status_color'] = temp_df['status'].apply(
        lambda x: 'red' if x != 'normal' else 'firebrick'
    )
    
    fig_temp = px.line(
        temp_df, 
        x='timestamp', 
        y='temperatura',
        title="Variação de Temperatura",
        labels={"timestamp": "Data/Hora", "temperatura": "Temperatura (°C)"},
        template=plotly_template,
        color_discrete_sequence=['firebrick']
    )
    
    # Adicionar marcadores para destacar pontos de status não-normal
    non_normal = temp_df[temp_df['status'] != 'normal']
    if not non_normal.empty:
        fig_temp.add_trace(
            go.Scatter(
                x=non_normal['timestamp'],
                y=non_normal['temperatura'],
                mode='markers',
                marker=dict(
                    size=8,
                    color='yellow',
                    symbol='circle',
                    line=dict(width=2, color='black')
                ),
                name='Status de Alerta'
            )
        )
    
    fig_temp.update_layout(height=400)
    st.plotly_chart(fig_temp, use_container_width=True)
else:
    st.warning("⚠️ Não há dados válidos de temperatura para gerar o gráfico.")

st.header("Umidade ao Longo do Tempo")

# Criar um dataframe filtrado para o gráfico de umidade (removendo valores nulos)
humid_df = df.dropna(subset=['umidade']).copy()
if not humid_df.empty:
    # Marcar status não-normais com cores diferentes
    humid_df['status_color'] = humid_df['status'].apply(
        lambda x: 'orange' if x != 'normal' else 'royalblue'
    )
    
    fig_umid = px.line(
        humid_df, 
        x='timestamp', 
        y='umidade',
        title="Variação de Umidade",
        labels={"timestamp": "Data/Hora", "umidade": "Umidade (%)"},
        template=plotly_template,
        color_discrete_sequence=['royalblue']
    )
    
    # Adicionar marcadores para destacar pontos de status não-normal
    non_normal = humid_df[humid_df['status'] != 'normal']
    if not non_normal.empty:
        fig_umid.add_trace(
            go.Scatter(
                x=non_normal['timestamp'],
                y=non_normal['umidade'],
                mode='markers',
                marker=dict(
                    size=8,
                    color='yellow',
                    symbol='circle',
                    line=dict(width=2, color='black')
                ),
                name='Status de Alerta'
            )
        )
    
    fig_umid.update_layout(height=400)
    st.plotly_chart(fig_umid, use_container_width=True)
else:
    st.warning("⚠️ Não há dados válidos de umidade para gerar o gráfico.")

st.header("Comparação de Temperatura e Umidade")

# Filtrar valores válidos para o gráfico combinado
combined_df = df.dropna(subset=['temperatura', 'umidade'], how='all').copy()

if not combined_df.empty:
    fig = go.Figure()
    
    # Adicionar linha de temperatura apenas para pontos válidos
    temp_valid = combined_df.dropna(subset=['temperatura'])
    if not temp_valid.empty:
        fig.add_trace(go.Scatter(
            x=temp_valid['timestamp'], 
            y=temp_valid['temperatura'],
            name='Temperatura (°C)',
            line=dict(color='firebrick', width=2),
            yaxis='y'
        ))
    
    # Adicionar linha de umidade apenas para pontos válidos
    humid_valid = combined_df.dropna(subset=['umidade'])
    if not humid_valid.empty:
        fig.add_trace(go.Scatter(
            x=humid_valid['timestamp'], 
            y=humid_valid['umidade'],
            name='Umidade (%)',
            line=dict(color='royalblue', width=2),
            yaxis='y2'
        ))
    
    # Adicionar marcadores de status
    status_colors = {
        'alerta_temperatura': 'yellow',
        'critico_temperatura': 'red',
        'erro_sensor': 'gray',
        'erro_leitura': 'cyan',
        'alerta_umidade': 'orange',
        'critico_umidade': 'purple'
    }
    
    for status, color in status_colors.items():
        status_points = combined_df[combined_df['status'] == status]
        if not status_points.empty:
            # Adicionar pontos de temperatura se disponíveis
            temp_points = status_points.dropna(subset=['temperatura'])
            if not temp_points.empty:
                fig.add_trace(go.Scatter(
                    x=temp_points['timestamp'],
                    y=temp_points['temperatura'],
                    mode='markers',
                    marker=dict(size=10, color=color, symbol='circle'),
                    name=f'{status} (Temp)',
                    yaxis='y',
                    showlegend=True
                ))
            
            # Adicionar pontos de umidade se disponíveis
            humid_points = status_points.dropna(subset=['umidade'])
            if not humid_points.empty:
                fig.add_trace(go.Scatter(
                    x=humid_points['timestamp'],
                    y=humid_points['umidade'],
                    mode='markers',
                    marker=dict(size=10, color=color, symbol='triangle-up'),
                    name=f'{status} (Umid)',
                    yaxis='y2',
                    showlegend=True
                ))
    
    fig.update_layout(
        title='Temperatura e Umidade ao Longo do Tempo',
        template=plotly_template,
        xaxis=dict(title='Data/Hora'),
        yaxis=dict(
            title='Temperatura (°C)',
            color='firebrick',
            tickfont=dict(color='firebrick'),
            range=[combined_df['temperatura'].min() * 0.9 if not pd.isna(combined_df['temperatura'].min()) else 0, 
                  combined_df['temperatura'].max() * 1.1 if not pd.isna(combined_df['temperatura'].max()) else 50]
        ),
        yaxis2=dict(
            title='Umidade (%)',
            color='royalblue',
            tickfont=dict(color='royalblue'),
            anchor='x',
            overlaying='y',
            side='right',
            range=[combined_df['umidade'].min() * 0.9 if not pd.isna(combined_df['umidade'].min()) else 0, 
                  combined_df['umidade'].max() * 1.1 if not pd.isna(combined_df['umidade'].max()) else 100]
        ),
        height=500,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    st.plotly_chart(fig, use_container_width=True)
else:
    st.warning("⚠️ Dados insuficientes para gerar o gráfico combinado.")

st.header("Análise de Distribuição")
col1, col2 = st.columns(2)

with col1:
    temp_valid = df.dropna(subset=['temperatura'])
    if not temp_valid.empty:
        fig_hist_temp = px.histogram(
            temp_valid, 
            x="temperatura", 
            nbins=20,
            title="Distribuição de Temperatura",
            labels={"temperatura": "Temperatura (°C)", "count": "Frequência"},
            color_discrete_sequence=['firebrick'],
            template=plotly_template
        )
        fig_hist_temp.update_layout(bargap=0.1)
        st.plotly_chart(fig_hist_temp, use_container_width=True)
    else:
        st.warning("⚠️ Dados insuficientes para gerar o histograma de temperatura.")

with col2:
    humid_valid = df.dropna(subset=['umidade'])
    if not humid_valid.empty:
        fig_hist_umid = px.histogram(
            humid_valid, 
            x="umidade", 
            nbins=20,
            title="Distribuição de Umidade",
            labels={"umidade": "Umidade (%)", "count": "Frequência"},
            color_discrete_sequence=['royalblue'],
            template=plotly_template
        )
        fig_hist_umid.update_layout(bargap=0.1)
        st.plotly_chart(fig_hist_umid, use_container_width=True)
    else:
        st.warning("⚠️ Dados insuficientes para gerar o histograma de umidade.")

# Gráficos por status
st.header("Análise por Status")

# Agrupar por status e calcular média de temperatura e umidade
status_group = df.groupby('status').agg({
    'temperatura': lambda x: x.dropna().mean() if len(x.dropna()) > 0 else np.nan,
    'umidade': lambda x: x.dropna().mean() if len(x.dropna()) > 0 else np .nan,
    'timestamp': 'count'
}).reset_index()
status_group.columns = ['status', 'temperatura_media', 'umidade_media', 'contagem']

col1, col2 = st.columns(2)

with col1:
    # Gráfico de barras para temperatura média por status
    fig_temp_status = px.bar(
        status_group.dropna(subset=['temperatura_media']), 
        x='status', 
        y='temperatura_media',
        title="Temperatura Média por Status",
        labels={"status": "Status", "temperatura_media": "Temperatura Média (°C)"},
        color='status',
        color_discrete_map=status_colors,
        template=plotly_template
    )
    st.plotly_chart(fig_temp_status, use_container_width=True)

with col2:
    # Gráfico de barras para umidade média por status
    fig_humid_status = px.bar(
        status_group.dropna(subset=['umidade_media']), 
        x='status', 
        y='umidade_media',
        title="Umidade Média por Status",
        labels={"status": "Status", "umidade_media": "Umidade Média (%)"},
        color='status',
        color_discrete_map=status_colors,
        template=plotly_template
    )
    st.plotly_chart(fig_humid_status, use_container_width=True)

with st.expander("Mostrar dados brutos"):
    st.subheader("Registros no Dataset")
    
    # Colorir a coluna de status
    def highlight_status(s):
        return [f"background-color: {status_colors.get(val, '#f8f9fa')}" if col == 'status' else '' 
                for col, val in zip(s.index, s.values)]
    
    # Verificar se temos registros antes de exibir o dataframe
    if not df.empty:
        styled_df = df.style.apply(highlight_status, axis=1)
        st.dataframe(styled_df, use_container_width=True, height=300)
        
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            "📥 Download dos dados (CSV)",
            csv,
            "dados_ambientais.csv",
            "text/csv",
            key='download-csv'
        )
    else:
        st.warning("⚠️ Não há dados para exibir.")

# Adicionar seção de alertas
st.header("Alertas Recentes")
alerts_df = df[df['status'] != 'normal'].sort_values('timestamp', ascending=False).head(10)

if not alerts_df.empty:
    for _, alert in alerts_df.iterrows():
        alert_color = status_colors.get(alert['status'], '#6c757d')
        alert_time = alert['timestamp'].strftime('%d/%m/%Y %H:%M:%S')
        temp_value = f"{alert['temperatura']:.1f}°C" if pd.notna(alert['temperatura']) else "N/A"
        humid_value = f"{alert['umidade']:.1f}%" if pd.notna(alert['umidade']) else "N/A"
        
        st.markdown(f"""
        <div style="background-color: {alert_color}; padding: 10px; border-radius: 5px; margin-bottom: 10px; color: white;">
            <strong>{alert['status'].upper()}</strong> - {alert_time}<br>
            Temperatura: {temp_value} | Umidade: {humid_value}
        </div>
        """, unsafe_allow_html=True)
else:
    st.info("✅ Nenhum alerta registrado no período selecionado.")

st.markdown("---")
st.info("✉️ Para dúvidas ou suporte, entre em contato com a equipe técnica.")