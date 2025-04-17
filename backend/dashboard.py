import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

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
</style>
""", unsafe_allow_html=True)

st.title("Dashboard de Monitoramento Ambiental")
st.write("Visualização em tempo real de temperatura e umidade coletadas pelo ESP32")

_, _, collection = get_mongodb_connection()

if collection is None:
    st.error("❌ Não foi possível conectar ao MongoDB. Verifique se o arquivo db_config.py está configurado corretamente e se o MongoDB está em execução.")
    st.stop()
else:
    st.sidebar.success("✅ Conectado ao MongoDB")

# Funções auxiliares
def get_data_for_period(period):
    """Busca dados do MongoDB baseado no período selecionado"""
    now = datetime.now()
    
    if period == "Última hora":
        start_date = now - timedelta(hours=1)
    elif period == "Últimas 24 horas":
        start_date = now - timedelta(days=1)
    elif period == "Última semana":
        start_date = now - timedelta(weeks=1)
    else:
        start_date = now - timedelta(days=30)
    
    try:
        cursor = collection.find({
            "timestamp": {"$gte": start_date}
        }).sort("timestamp", 1)
        
        data = list(cursor)
        for item in data:
            item['_id'] = str(item['_id'])
        
        return data
    except Exception as e:
        st.error(f"Erro ao consultar dados: {e}")
        return []

def create_dataframe(data):
    """Converte dados do MongoDB para DataFrame pandas"""
    if not data:
        return None
        
    df = pd.DataFrame(data)
    
    if 'timestamp' in df.columns:
        if df['timestamp'].dtype == 'object':
            df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    return df

plotly_template = "plotly_dark"

with st.sidebar:
    st.header("Controles")
    period = st.selectbox(
        "Selecione o período:",
        ["Última hora", "Últimas 24 horas", "Última semana", "Último mês"]
    )
    
    refresh = st.button("🔄 Atualizar Dados")

data = get_data_for_period(period)
df = create_dataframe(data)

if df is None or df.empty:
    st.warning("⚠️ Nenhum dado encontrado para o período selecionado.")
    st.stop()

st.write(f"Exibindo {len(df)} registros para o período: **{period}**")
st.write(f"Primeiro registro: {df['timestamp'].min().strftime('%d/%m/%Y %H:%M')}")
st.write(f"Último registro: {df['timestamp'].max().strftime('%d/%m/%Y %H:%M')}")

st.header("Estatísticas de Temperatura")
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Temperatura Atual", f"{df['temperatura'].iloc[-1]:.1f}°C", 
             delta=f"{df['temperatura'].iloc[-1] - df['temperatura'].iloc[-2]:.1f}°C" if len(df) > 1 else None)
with col2:
    st.metric("Temperatura Máxima", f"{df['temperatura'].max():.1f}°C")
with col3:
    st.metric("Temperatura Mínima", f"{df['temperatura'].min():.1f}°C")
with col4:
    st.metric("Média", f"{df['temperatura'].mean():.1f}°C")

st.header("Estatísticas de Umidade")
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Umidade Atual", f"{df['umidade'].iloc[-1]:.1f}%", 
             delta=f"{df['umidade'].iloc[-1] - df['umidade'].iloc[-2]:.1f}%" if len(df) > 1 else None)
with col2:
    st.metric("Umidade Máxima", f"{df['umidade'].max():.1f}%")
with col3:
    st.metric("Umidade Mínima", f"{df['umidade'].min():.1f}%")
with col4:
    st.metric("Média", f"{df['umidade'].mean():.1f}%")

st.header("Temperatura ao Longo do Tempo")
fig_temp = px.line(df, x='timestamp', y='temperatura', 
            title="Variação de Temperatura",
            labels={"timestamp": "Data/Hora", "temperatura": "Temperatura (°C)"},
            template=plotly_template)
fig_temp.update_traces(line=dict(color='firebrick', width=2))
fig_temp.update_layout(height=400)
st.plotly_chart(fig_temp, use_container_width=True)

st.header("Umidade ao Longo do Tempo")
fig_umid = px.line(df, x='timestamp', y='umidade', 
            title="Variação de Umidade",
            labels={"timestamp": "Data/Hora", "umidade": "Umidade (%)"},
            template=plotly_template)
fig_umid.update_traces(line=dict(color='royalblue', width=2))
fig_umid.update_layout(height=400)
st.plotly_chart(fig_umid, use_container_width=True)

st.header("Comparação de Temperatura e Umidade")

if len(df) > 0:
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=df['timestamp'], 
        y=df['temperatura'],
        name='Temperatura (°C)',
        line=dict(color='firebrick', width=2),
        yaxis='y'
    ))
    
    fig.add_trace(go.Scatter(
        x=df['timestamp'], 
        y=df['umidade'],
        name='Umidade (%)',
        line=dict(color='royalblue', width=2),
        yaxis='y2'
    ))
    
    fig.update_layout(
        title='Temperatura e Umidade ao Longo do Tempo',
        template=plotly_template,
        xaxis=dict(title='Data/Hora'),
        yaxis=dict(
            title='Temperatura (°C)',
            color='firebrick',
            tickfont=dict(color='firebrick')
        ),
        yaxis2=dict(
            title='Umidade (%)',
            color='royalblue',
            tickfont=dict(color='royalblue'),
            anchor='x',
            overlaying='y',
            side='right'
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
    fig_hist_temp = px.histogram(df, x="temperatura", nbins=20,
                        title="Distribuição de Temperatura",
                        labels={"temperatura": "Temperatura (°C)", "count": "Frequência"},
                        color_discrete_sequence=['firebrick'],
                        template=plotly_template)
    st.plotly_chart(fig_hist_temp, use_container_width=True)

with col2:
    fig_hist_umid = px.histogram(df, x="umidade", nbins=20,
                        title="Distribuição de Umidade",
                        labels={"umidade": "Umidade (%)", "count": "Frequência"},
                        color_discrete_sequence=['royalblue'],
                        template=plotly_template)
    st.plotly_chart(fig_hist_umid, use_container_width=True)

with st.expander("Mostrar dados brutos"):
    st.subheader("Registros no MongoDB")
    st.dataframe(df, use_container_width=True)
    
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button(
        "📥 Download dos dados (CSV)",
        csv,
        "dados_ambientais.csv",
        "text/csv",
        key='download-csv'
    )

st.markdown("---")
st.info("✉️ Para dúvidas ou suporte, entre em contato com a equipe técnica.")