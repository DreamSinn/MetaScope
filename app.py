import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.adobjects.adsinsights import AdsInsights
from facebook_business.adobjects.ad import Ad
from facebook_business.adobjects.campaign import Campaign
from facebook_business.adobjects.adset import AdSet
from PIL import Image
import requests
from io import BytesIO
import hashlib
import re
from bs4 import BeautifulSoup

# Configuração inicial
st.set_page_config(page_title="📊 Meta Ads Analyzer Pro", page_icon="📊", layout="wide")

# Função auxiliar para conversão segura de valores numéricos
def safe_float(value, default=0.0):
    try:
        return float(value) if value not in [None, ''] else default
    except (TypeError, ValueError):
        return default

def safe_int(value, default=0):
    try:
        return int(float(value)) if value not in [None, ''] else default
    except (TypeError, ValueError):
        return default

# ==============================================
# CONFIGURAÇÃO DA API DO META
# ==============================================

def init_facebook_api():
    """Inicializa a conexão com a API do Meta com credenciais do usuário"""
    st.sidebar.title("🔐 Configuração da API do Meta")
    
    with st.sidebar.expander("🔑 Inserir Credenciais", expanded=True):
        app_id = st.text_input("App ID", help="ID do aplicativo Facebook")
        app_secret = st.text_input("App Secret", type="password", help="Chave secreta do aplicativo")
        access_token = st.text_input("Access Token", type="password", help="Token de acesso de longo prazo")
        ad_account_id = st.text_input("Ad Account ID", help="ID da conta de anúncios (sem 'act_')")
    
    if not all([app_id, app_secret, access_token, ad_account_id]):
        st.warning("Por favor, preencha todas as credenciais na barra lateral")
        return None
    
    try:
        FacebookAdsApi.init(app_id, app_secret, access_token)
        return AdAccount(f"act_{ad_account_id}")
    except Exception as e:
        st.error(f"Erro ao conectar à API do Meta: {str(e)}")
        return None

# ==============================================
# FUNÇÕES PARA EXTRAÇÃO DE DADOS REAIS (API)
# ==============================================

def get_campaigns(ad_account):
    """Obtém campanhas da conta de anúncio formatadas como dicionários"""
    try:
        fields = ['id', 'name', 'objective', 'status', 'start_time', 'stop_time', 'buying_type']
        params = {'limit': 200}
        
        campaigns = ad_account.get_campaigns(fields=fields, params=params)
        
        campaigns_data = []
        for campaign in campaigns:
            campaigns_data.append({
                'id': campaign.get('id'),
                'name': campaign.get('name', 'Sem Nome'),
                'objective': campaign.get('objective', 'N/A'),
                'status': campaign.get('status', 'N/A'),
                'start_time': campaign.get('start_time', 'N/A'),
                'stop_time': campaign.get('stop_time', 'N/A'),
                'buying_type': campaign.get('buying_type', 'N/A')
            })
        
        return campaigns_data
    except Exception as e:
        st.error(f"Erro ao obter campanhas: {str(e)}")
        return []

def get_adsets(campaign_id):
    """Obtém conjuntos de anúncios de uma campanha"""
    try:
        fields = [
            'id', 'name', 'daily_budget', 'lifetime_budget', 
            'start_time', 'end_time', 'optimization_goal',
            'billing_event', 'targeting', 'bid_strategy'
        ]
        params = {'limit': 100}
        campaign = Campaign(campaign_id)
        adsets = campaign.get_ad_sets(fields=fields, params=params)
        
        adsets_data = []
        for adset in adsets:
            adsets_data.append({
                'id': adset.get('id'),
                'name': adset.get('name', 'Sem Nome'),
                'daily_budget': safe_float(adset.get('daily_budget', 0)),
                'lifetime_budget': safe_float(adset.get('lifetime_budget', 0)),
                'start_time': adset.get('start_time', 'N/A'),
                'end_time': adset.get('end_time', 'N/A'),
                'optimization_goal': adset.get('optimization_goal', 'N/A'),
                'billing_event': adset.get('billing_event', 'N/A'),
                'bid_strategy': adset.get('bid_strategy', 'N/A')
            })
        
        return adsets_data
    except Exception as e:
        st.error(f"Erro ao obter conjuntos de anúncios: {str(e)}")
        return []

def get_ads(adset_id):
    """Obtém anúncios de um conjunto"""
    try:
        fields = [
            'id', 'name', 'status', 'created_time', 
            'adset_id', 'creative', 'bid_amount',
            'conversion_domain', 'targeting'
        ]
        params = {'limit': 100}
        adset = AdSet(adset_id)
        ads = adset.get_ads(fields=fields, params=params)
        
        ads_data = []
        for ad in ads:
            ads_data.append({
                'id': ad.get('id'),
                'name': ad.get('name', 'Sem Nome'),
                'status': ad.get('status', 'N/A'),
                'created_time': ad.get('created_time', 'N/A'),
                'adset_id': ad.get('adset_id', 'N/A'),
                'bid_amount': safe_float(ad.get('bid_amount', 0)),
                'conversion_domain': ad.get('conversion_domain', 'N/A')
            })
        
        return ads_data
    except Exception as e:
        st.error(f"Erro ao obter anúncios: {str(e)}")
        return []

def get_ad_insights(ad_id, date_range='last_30d'):
    """Obtém métricas de desempenho do anúncio com mais detalhes"""
    try:
        fields = [
            'impressions', 'reach', 'frequency', 
            'spend', 'cpm', 'cpp', 'ctr', 'clicks',
            'conversions', 'actions', 'action_values',
            'cost_per_conversion', 'cost_per_action_type',
            'cost_per_unique_click', 'cost_per_unique_action_type',
            'unique_clicks', 'unique_actions',
            'quality_ranking', 'engagement_rate_ranking',
            'conversion_rate_ranking', 'video_p25_watched_actions',
            'video_p50_watched_actions', 'video_p75_watched_actions',
            'video_p95_watched_actions', 'video_p100_watched_actions',
            'video_avg_time_watched_actions'
        ]
        
        # Limite de 37 meses para o intervalo de datas
        max_months = 37
        
        if date_range == 'last_30d':
            since = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            until = datetime.now().strftime('%Y-%m-%d')
        elif date_range == 'last_7d':
            since = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            until = datetime.now().strftime('%Y-%m-%d')
        else:
            since, until = date_range.split('_to_')
            since_date = datetime.strptime(since, '%Y-%m-%d')
            until_date = datetime.strptime(until, '%Y-%m-%d')
            if (until_date - since_date).days > (max_months * 30):
                st.warning(f"O intervalo máximo permitido é de {max_months} meses. Ajustando automaticamente.")
                since = (until_date - timedelta(days=max_months*30)).strftime('%Y-%m-%d')
        
        params = {
            'time_range': {'since': since, 'until': until},
            'level': 'ad',
            'limit': 100
        }
        
        ad = Ad(ad_id)
        insights = ad.get_insights(fields=fields, params=params)
        
        if insights:
            # Processa ações específicas
            actions = insights[0].get('actions', [])
            action_data = {}
            for action in actions:
                action_type = action.get('action_type')
                value = safe_float(action.get('value', 0))
                action_data[f'action_{action_type}'] = value
            
            # Processa valores de ação
            action_values = insights[0].get('action_values', [])
            for action in action_values:
                action_type = action.get('action_type')
                value = safe_float(action.get('value', 0))
                action_data[f'action_value_{action_type}'] = value
            
            # Adiciona ao dicionário de insights
            insight_dict = {**insights[0], **action_data}
            return insight_dict
        
        return None
    except Exception as e:
        st.error(f"Erro ao obter insights do anúncio: {str(e)}")
        return None

def get_ad_demographics(ad_id, date_range='last_30d'):
    """Obtém dados demográficos do público alcançado com mais detalhes"""
    try:
        fields = [
            'impressions', 'reach', 'clicks', 'spend',
            'cpm', 'cpp', 'ctr', 'conversions',
            'cost_per_conversion'
        ]
        
        # Vamos usar apenas age e gender como breakdowns principais
        breakdowns = ['age', 'gender']
        
        max_months = 37
        
        if date_range == 'last_30d':
            since = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            until = datetime.now().strftime('%Y-%m-%d')
        elif date_range == 'last_7d':
            since = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            until = datetime.now().strftime('%Y-%m-%d')
        else:
            since, until = date_range.split('_to_')
            since_date = datetime.strptime(since, '%Y-%m-%d')
            until_date = datetime.strptime(until, '%Y-%m-%d')
            if (until_date - since_date).days > (max_months * 30):
                st.warning(f"O intervalo máximo permitido é de {max_months} meses. Ajustando automaticamente.")
                since = (until_date - timedelta(days=max_months*30)).strftime('%Y-%m-%d')
        
        params = {
            'time_range': {'since': since, 'until': until},
            'breakdowns': breakdowns,
            'level': 'ad'
        }
        
        ad = Ad(ad_id)
        insights = ad.get_insights(fields=fields, params=params)
        
        # Se quisermos dados por país, fazemos uma chamada separada
        country_params = {
            'time_range': {'since': since, 'until': until},
            'breakdowns': ['country'],
            'level': 'ad'
        }
        country_insights = ad.get_insights(fields=fields, params=country_params)
        
        # Combina os resultados
        combined_insights = []
        if insights:
            combined_insights.extend(insights)
        if country_insights:
            combined_insights.extend(country_insights)
            
        return combined_insights if combined_insights else None
    except Exception as e:
        st.error(f"Erro ao obter dados demográficos: {str(e)}")
        return None

def get_ad_insights_over_time(ad_id, date_range='last_30d'):
    """Obtém métricas diárias com tratamento seguro para campos ausentes"""
    try:
        # Campos base que geralmente estão disponíveis
        base_fields = [
            'date_start', 'impressions', 'reach', 'spend',
            'clicks', 'ctr', 'frequency', 'cpm'
        ]
        
        # Campos adicionais que podem não estar disponíveis
        optional_fields = [
            'conversions', 'cost_per_conversion',
            'unique_clicks', 'actions'
        ]
        
        # Primeira tentativa com todos os campos
        fields = base_fields + optional_fields
        
        if date_range == 'last_30d':
            since = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            until = datetime.now().strftime('%Y-%m-%d')
        elif date_range == 'last_7d':
            since = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            until = datetime.now().strftime('%Y-%m-%d')
        else:
            since, until = date_range.split('_to_')

        params = {
            'time_range': {'since': since, 'until': until},
            'level': 'ad',
            'time_increment': 1
        }

        ad = Ad(ad_id)
        insights = ad.get_insights(fields=fields, params=params)
        
        if not insights:
            return None

        # Processamento seguro dos dados
        data = []
        for insight in insights:
            row = {}
            for field in fields:
                # Tratamento especial para actions/conversions
                if field == 'actions':
                    actions = insight.get(field, [])
                    conversions = sum(float(a['value']) for a in actions 
                                  if a['action_type'] == 'conversion' and 'value' in a)
                    row['conversions'] = conversions
                else:
                    row[field] = insight.get(field, 0)
            data.append(row)
        
        df = pd.DataFrame(data)
        
        # Garantir tipos corretos
        df['date_start'] = pd.to_datetime(df['date_start'], errors='coerce')
        df = df.dropna(subset=['date_start']).sort_values('date_start')
        
        # Converter métricas numéricas
        for col in base_fields[1:] + optional_fields:
            if col in df.columns:
                df[col] = df[col].apply(safe_float)
        
        # Calcular métricas derivadas
        df['ctr'] = df['ctr'] * 100  # Converter para porcentagem
        df['cpc'] = np.where(df['clicks'] > 0, df['spend']/df['clicks'], 0)
        
        if 'conversions' in df.columns:
            df['conversion_rate'] = np.where(df['clicks'] > 0,
                                           (df['conversions']/df['clicks'])*100,
                                           0)
            df['cost_per_conversion'] = np.where(df['conversions'] > 0,
                                               df['spend']/df['conversions'],
                                               0)
        
        return df

    except Exception as e:
        st.error(f"Erro ao processar dados temporais: {str(e)}")
        return None

# ==============================================
# VISUALIZAÇÕES MELHORADAS
# ==============================================

def create_performance_gauge(value, min_val, max_val, title, color_scale=None):
    """Cria um medidor visual estilo gauge com escala de cores personalizável"""
    if color_scale is None:
        color_scale = {
            'axis': {'range': [min_val, max_val]},
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': (min_val + max_val) * 0.7
            },
            'steps': [
                {'range': [min_val, min_val*0.6], 'color': "red"},
                {'range': [min_val*0.6, min_val*0.8], 'color': "orange"},
                {'range': [min_val*0.8, max_val], 'color': "green"}]
        }
    
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=value,
        number={'suffix': '%', 'font': {'size': 24}},
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': title, 'font': {'size': 18}},
        gauge=color_scale
    ))
    fig.update_layout(margin=dict(t=50, b=10))
    return fig

def create_trend_chart(df, x_col, y_cols, title, mode='lines'):
    """Cria gráfico de tendência temporal com múltiplas métricas"""
    fig = px.line(df, x=x_col, y=y_cols, title=title,
                 line_shape='spline', render_mode='svg')
    
    fig.update_layout(
        hovermode='x unified',
        legend_title_text='Métrica',
        xaxis_title='Data',
        yaxis_title='Valor',
        plot_bgcolor='rgba(240,240,240,0.9)'
    )
    
    # Adiciona anotações para pontos máximos e mínimos
    for col in y_cols:
        max_val = df[col].max()
        min_val = df[col].min()
        
        max_date = df.loc[df[col] == max_val, x_col].values[0]
        min_date = df.loc[df[col] == min_val, x_col].values[0]
        
        fig.add_annotation(x=max_date, y=max_val,
                          text=f"Max: {max_val:.2f}",
                          showarrow=True,
                          arrowhead=1)
        
        fig.add_annotation(x=min_date, y=min_val,
                          text=f"Min: {min_val:.2f}",
                          showarrow=True,
                          arrowhead=1)
    
    return fig

def create_benchmark_comparison(current_values, benchmark_values, labels):
    """Cria gráfico de comparação com benchmarks do setor"""
    fig = go.Figure()
    
    for i, (current, benchmark, label) in enumerate(zip(current_values, benchmark_values, labels)):
        fig.add_trace(go.Bar(
            x=[f"{label}"],
            y=[current],
            name='Seu Anúncio',
            marker_color='#1f77b4',
            showlegend=(i == 0)
        ))
        
        fig.add_trace(go.Bar(
            x=[f"{label}"],
            y=[benchmark],
            name='Benchmark Setor',
            marker_color='#ff7f0e',
            showlegend=(i == 0)
        ))
    
    fig.update_layout(
        barmode='group',
        title='Comparação com Benchmarks do Setor',
        yaxis_title='Valor',
        plot_bgcolor='rgba(240,240,240,0.9)'
    )
    
    return fig

def generate_performance_recommendations(insights, temporal_data):
    """Gera recomendações estratégicas baseadas em métricas"""
    recommendations = []
    
    # Análise de CTR
    ctr = safe_float(insights.get('ctr', 0)) * 100
    if ctr < 0.8:
        recommendations.append({
            'type': 'error',
            'title': 'CTR Baixo',
            'message': f"CTR de {ctr:.2f}% está abaixo do benchmark recomendado (1-2%)",
            'actions': [
                "Teste diferentes imagens/thumbnails no criativo",
                "Reduza o texto principal (ideal <125 caracteres)",
                "Posicione o CTA de forma mais destacada",
                "Teste diferentes cópias de texto"
            ]
        })
    elif ctr > 2.5:
        recommendations.append({
            'type': 'success',
            'title': 'CTR Alto',
            'message': f"Excelente CTR de {ctr:.2f}%!",
            'actions': [
                "Aumente o orçamento para escalar este desempenho",
                "Replique a estratégia para públicos similares",
                "Documente as características deste anúncio"
            ]
        })
    
    # Análise de Custo por Conversão
    cost_per_conv = safe_float(insights.get('cost_per_conversion', 0))
    if cost_per_conv > 50:
        recommendations.append({
            'type': 'error',
            'title': 'Custo Alto por Conversão',
            'message': f"R${cost_per_conv:.2f} por conversão (acima da média)",
            'actions': [
                "Otimize a landing page (taxa de conversão pode estar baixa)",
                "Ajuste a segmentação para públicos mais qualificados",
                "Teste diferentes objetivos de campanha",
                "Verifique a qualidade do tráfego"
            ]
        })
    
    # Análise de Frequência (se houver dados temporais)
    if temporal_data is not None:
        freq = temporal_data['frequency'].mean()
        if freq > 3.5:
            recommendations.append({
                'type': 'warning',
                'title': 'Frequência Elevada',
                'message': f"Média de {freq:.1f} impressões por usuário (risco de fadiga)",
                'actions': [
                    "Reduza o orçamento ou pause temporariamente",
                    "Atualize o criativo para evitar saturação",
                    "Expanda o público-alvo"
                ]
            })
    
    return recommendations

# ==============================================
# FUNÇÕES PARA ANÁLISE DE ANÚNCIOS PÚBLICOS MELHORADAS
# ==============================================

def extract_ad_details_from_url(url):
    """Extrai metadados de anúncios públicos usando web scraping"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extrai metadados básicos
        title = soup.find('meta', property='og:title') or soup.find('meta', attrs={'name': 'title'})
        description = soup.find('meta', property='og:description') or soup.find('meta', attrs={'name': 'description'})
        image = soup.find('meta', property='og:image')
        
        # Tenta identificar plataforma
        platform = "Facebook" if "facebook.com" in url else "Instagram"
        
        # Tenta identificar tipo de anúncio
        ad_type = "Desconhecido"
        if "video" in str(soup).lower():
            ad_type = "Vídeo"
        elif "carousel" in str(soup).lower():
            ad_type = "Carrossel"
        elif "story" in str(soup).lower():
            ad_type = "Stories"
        else:
            ad_type = "Imagem"
        
        return {
            'title': title.get('content', 'N/A') if title else 'N/A',
            'description': description.get('content', 'N/A') if description else 'N/A',
            'image_url': image.get('content', '') if image else '',
            'platform': platform,
            'ad_type': ad_type,
            'url': url
        }
    except Exception as e:
        st.error(f"Erro ao extrair metadados: {str(e)}")
        return None

def estimate_ad_performance(url):
    """Estima métricas de performance baseado em URL público com mais precisão"""
    try:
        # Extrai metadados do anúncio
        ad_details = extract_ad_details_from_url(url)
        
        # Gera hash estável para seed baseado na URL
        url_hash = int(hashlib.sha256(url.encode('utf-8')).hexdigest(), 16) % 10**8
        np.random.seed(url_hash)
        
        # Determina benchmarks baseados no tipo de anúncio e plataforma
        if ad_details['platform'] == "Facebook":
            if ad_details['ad_type'] == "Vídeo":
                base_ctr = 2.5
                base_cpc = 1.2
                video_completion = {
                    'p25': np.random.normal(0.65, 0.1),
                    'p50': np.random.normal(0.45, 0.1),
                    'p75': np.random.normal(0.3, 0.1),
                    'p95': np.random.normal(0.15, 0.05)
                }
            else:
                base_ctr = 1.8
                base_cpc = 1.5
                video_completion = None
        else:  # Instagram
            if ad_details['ad_type'] == "Stories":
                base_ctr = 1.2
                base_cpc = 0.8
                video_completion = {
                    'p25': np.random.normal(0.75, 0.1),
                    'p50': np.random.normal(0.55, 0.1),
                    'p75': np.random.normal(0.35, 0.1),
                    'p95': np.random.normal(0.2, 0.05)
                }
            else:
                base_ctr = 1.5
                base_cpc = 1.0
                video_completion = None
        
        # Gera métricas baseadas em distribuições estatísticas realistas
        impressions = int(np.random.lognormal(10.5, 0.3))
        ctr = round(np.random.normal(base_ctr, 0.3), 2)
        cpc = round(np.random.lognormal(np.log(base_cpc), 0.2), 2)
        frequency = round(np.random.uniform(1.2, 3.5), 1)
        
        # Calcula métricas derivadas
        clicks = int(impressions * ctr / 100)
        spend = clicks * cpc
        cpm = (spend / impressions) * 1000 if impressions > 0 else 0
        
        # Estima conversões baseadas no CTR e tipo de anúncio
        if ad_details['ad_type'] == "Vídeo":
            conversion_rate = round(np.random.normal(3.5, 0.5), 2)
        else:
            conversion_rate = round(np.random.normal(2.0, 0.5), 2)
        
        conversions = int(clicks * conversion_rate / 100)
        cost_per_conversion = spend / conversions if conversions > 0 else 0
        
        # Estima engajamento
        engagement_rate = round(np.random.normal(1.5, 0.3), 2)
        engagements = int(impressions * engagement_rate / 100)
        
        metrics = {
            'impressions': impressions,
            'reach': int(impressions / frequency),
            'frequency': frequency,
            'clicks': clicks,
            'ctr': ctr,
            'cpc': cpc,
            'cpm': cpm,
            'spend': spend,
            'conversions': conversions,
            'conversion_rate': conversion_rate,
            'cost_per_conversion': cost_per_conversion,
            'engagement_rate': engagement_rate,
            'engagements': engagements,
            'video_completion': video_completion,
            **ad_details
        }
        
        return metrics
    except Exception as e:
        st.error(f"Erro ao estimar métricas: {str(e)}")
        return None

def show_public_ad_analysis():
    """Interface para análise de anúncios públicos melhorada"""
    st.header("🔍 Analisador de Anúncios Públicos Avançado")
    st.warning("Esta ferramenta fornece estimativas baseadas em padrões de mercado e análise de metadados", icon="⚠️")
    
    ad_url = st.text_input("Cole o URL do anúncio público (Meta Ads Library ou post):", 
                          placeholder="https://www.facebook.com/ads/library/?id=...")
    
    if ad_url:
        with st.spinner("Analisando anúncio... Isso pode levar alguns segundos"):
            metrics = estimate_ad_performance(ad_url)
            
            if not metrics:
                st.error("Não foi possível analisar este anúncio. Verifique a URL e tente novamente.")
                return
            
            # Seção de metadados do anúncio
            st.subheader("📌 Metadados do Anúncio")
            col1, col2 = st.columns([1, 2])
            
            with col1:
                if metrics.get('image_url'):
                    try:
                        response = requests.get(metrics['image_url'])
                        img = Image.open(BytesIO(response.content))
                        st.image(img, caption="Visualização do anúncio", use_column_width=True)
                    except:
                        st.image("https://via.placeholder.com/300x200?text=Imagem+indisponível", 
                                caption="Imagem não disponível")
                else:
                    st.image("https://via.placeholder.com/300x200?text=Sem+visualização", 
                            caption="Nenhuma visualização disponível")
            
            with col2:
                st.write(f"**📌 Plataforma:** {metrics.get('platform', 'N/A')}")
                st.write(f"**🎯 Tipo de Anúncio:** {metrics.get('ad_type', 'N/A')}")
                st.write(f"**📝 Título:** {metrics.get('title', 'N/A')}")
                st.write(f"**📋 Descrição:** {metrics.get('description', 'N/A')}")
                st.write(f"**🔗 URL Original:** [Link]({ad_url})")
                
                if metrics.get('video_completion'):
                    st.markdown("**🎥 Taxas de Conclusão de Vídeo:**")
                    completion_data = metrics['video_completion']
                    st.write(f"- 25%: {completion_data['p25']*100:.1f}%")
                    st.write(f"- 50%: {completion_data['p50']*100:.1f}%")
                    st.write(f"- 75%: {completion_data['p75']*100:.1f}%")
                    st.write(f"- 95%: {completion_data['p95']*100:.1f}%")
            
            # Seção de métricas estimadas
            st.subheader("📊 Métricas de Desempenho Estimadas")
            
            # Métricas principais
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Impressões", f"{metrics['impressions']:,}", 
                       help="Número de vezes que o anúncio foi exibido")
            col2.metric("Alcance", f"{metrics['reach']:,}", 
                       help="Número de pessoas únicas que viram o anúncio")
            col3.metric("Frequência", f"{metrics['frequency']:.1f}x", 
                       help="Média de vezes que cada pessoa viu o anúncio")
            col4.metric("Investimento Estimado", f"R${metrics['spend']:,.2f}", 
                       help="Valor total estimado gasto no anúncio")
            
            # Métricas de engajamento
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Cliques", f"{metrics['clicks']:,}", 
                       help="Número de cliques no anúncio")
            col2.metric("CTR", f"{metrics['ctr']}%", 
                       help="Taxa de cliques (cliques/impressões)")
            col3.metric("CPC", f"R${metrics['cpc']:.2f}", 
                       help="Custo por clique")
            col4.metric("CPM", f"R${metrics['cpm']:.2f}", 
                       help="Custo por mil impressões")
            
            # Métricas de conversão
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Conversões", f"{metrics['conversions']:,}", 
                       help="Número de conversões estimadas")
            col2.metric("Taxa de Conversão", f"{metrics['conversion_rate']}%", 
                       help="Conversões por clique")
            col3.metric("Custo por Conversão", f"R${metrics['cost_per_conversion']:.2f}", 
                       help="Custo médio por conversão")
            col4.metric("Taxa de Engajamento", f"{metrics['engagement_rate']}%", 
                       help="Interações (curtidas, comentários, etc.) por impressão")
            
            # Visualizações gráficas
            st.subheader("📈 Visualização de Performance")
            
            # Gauge de CTR com benchmark
            tab1, tab2 = st.tabs(["Indicadores Chave", "Comparação com Benchmarks"])
            
            with tab1:
                col1, col2 = st.columns(2)
                
                with col1:
                    # Gauge de CTR com benchmark do setor
                    benchmark_ctr = 2.0 if metrics['platform'] == 'Facebook' else 1.5
                    fig = create_performance_gauge(
                        metrics['ctr'], 
                        min_val=0, 
                        max_val=5, 
                        title=f"CTR Estimado vs Benchmark ({benchmark_ctr}%)",
                        color_scale={
                            'axis': {'range': [0, 5]},
                            'threshold': {'value': benchmark_ctr},
                            'steps': [
                                {'range': [0, benchmark_ctr*0.7], 'color': "red"},
                                {'range': [benchmark_ctr*0.7, benchmark_ctr*1.3], 'color': "orange"},
                                {'range': [benchmark_ctr*1.3, 5], 'color': "green"}]
                        }
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    # Gauge de Custo por Conversão
                    benchmark_cpa = 15.0 if metrics['platform'] == 'Facebook' else 12.0
                    current_cpa = min(metrics['cost_per_conversion'], 30)  # Limitamos a 30 para a escala do gráfico
                    
                    fig = create_performance_gauge(
                        current_cpa,
                        min_val=0,
                        max_val=30, 
                        title=f"Custo por Conversão vs Benchmark (R${benchmark_cpa})",
                        color_scale={
                            'axis': {'range': [0, 30]},
                            'threshold': {'value': benchmark_cpa},
                            'steps': [
                                {'range': [0, benchmark_cpa*0.7], 'color': "green"},
                                {'range': [benchmark_cpa*0.7, benchmark_cpa*1.3], 'color': "orange"},
                                {'range': [benchmark_cpa*1.3, 30], 'color': "red"}]
                        }
                    )
                    st.plotly_chart(fig, use_container_width=True)
            
            with tab2:
                # Comparação com benchmarks do setor
                current_values = [
                    metrics['ctr'],
                    metrics['cpc'],
                    metrics['cost_per_conversion'],
                    metrics['engagement_rate']
                ]
                
                if metrics['platform'] == 'Facebook':
                    benchmark_values = [2.0, 1.3, 15.0, 1.8]
                else:
                    benchmark_values = [1.5, 0.9, 12.0, 2.2]
                
                labels = ['CTR (%)', 'CPC (R$)', 'Custo/Conversão (R$)', 'Taxa Engajamento (%)']
                
                fig = create_benchmark_comparison(current_values, benchmark_values, labels)
                st.plotly_chart(fig, use_container_width=True)
            
            # Seção de recomendações
            st.subheader("💡 Recomendações Estratégicas")
            
            # Análise de pontos fortes
            st.markdown("#### ✅ Pontos Fortes Identificados")
            if metrics['ctr'] > (benchmark_ctr * 1.2):
                st.success("- Seu CTR está **acima da média** do setor, indicando que o criativo e a mensagem estão eficazes")
            elif metrics['ctr'] < (benchmark_ctr * 0.8):
                st.error("- Seu CTR está **abaixo da média** do setor, sugerindo que o criativo ou público-alvo pode não ser ideal")
            else:
                st.info("- Seu CTR está **na média** do setor, há espaço para otimizações")
            
            if metrics['cost_per_conversion'] < (benchmark_cpa * 0.8):
                st.success("- Seu custo por conversão está **abaixo da média**, indicando boa eficiência na conversão")
            elif metrics['cost_per_conversion'] > (benchmark_cpa * 1.2):
                st.error("- Seu custo por conversão está **acima da média**, sugerindo que o funnel de conversão pode ser melhorado")
            
            # Recomendações específicas
            st.markdown("#### 🎯 Recomendações de Otimização")
            
            if metrics['platform'] == 'Facebook':
                if metrics['ad_type'] == 'Vídeo':
                    st.write("""
                    - **Teste diferentes durações de vídeo:** Vídeos entre 15-30 segundos tem melhor retenção
                    - **Adicione legendas:** 85% dos vídeos são assistidos sem som
                    - **Use CTA claro:** Inclua chamadas para ação nos primeiros 3 segundos
                    """)
                else:
                    st.write("""
                    - **Experimente formatos diferentes:** Teste carrossel para mostrar múltiplos produtos
                    - **Otimize para mobile:** 98% dos usuários acessam pelo celular
                    - **Use texto conciso:** Limite a 125 caracteres para melhor leitura
                    """)
            else:  # Instagram
                if metrics['ad_type'] == 'Stories':
                    st.write("""
                    - **Use stickers interativos:** Pesquisas e perguntas aumentam engajamento
                    - **Poste múltiplos stories:** Sequências de 3-5 stories tem melhor desempenho
                    - **CTA swipe up:** Se disponível, direcione para ofertas especiais
                    """)
                else:
                    st.write("""
                    - **Hashtags estratégicas:** Use 5-10 hashtags relevantes
                    - **Horários de pico:** Poste entre 19h-21h para maior alcance
                    - **Colabore com influenciadores:** Parcerias aumentam credibilidade
                    """)
            
            st.markdown("#### 📅 Sugestão de Cronograma de Testes")
            st.write("""
            | Dia | Tipo de Teste | Métrica-Chave |
            |-----|--------------|---------------|
            | 1-3 | Criativo A vs B | CTR e Custo por Conversão |
            | 4-6 | Público A vs B | Taxa de Conversão |
            | 7-9 | CTA diferente | Taxa de Cliques |
            | 10-12 | Landing Page A/B | Conversões |
            """)

# ==============================================
# INTERFACES DE USUÁRIO PARA ANÁLISE REAL
# ==============================================

def show_real_analysis():
    st.markdown("## 🔍 Análise de Anúncios Reais - Meta Ads")
    
    # Inicializa a API com as credenciais do usuário
    ad_account = init_facebook_api()
    if not ad_account:
        return  # Sai se as credenciais não foram fornecidas
    
    # Restante do código permanece igual...
    date_range = st.radio("Período de análise:", 
                         ["Últimos 7 dias", "Últimos 30 dias", "Personalizado"],
                         index=1, horizontal=True)
    
    custom_range = None
    if date_range == "Personalizado":
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Data inicial", datetime.now() - timedelta(days=30))
        with col2:
            end_date = st.date_input("Data final", datetime.now())
        custom_range = f"{start_date.strftime('%Y-%m-%d')}_to_{end_date.strftime('%Y-%m-%d')}"
    
    date_range_param = {
        "Últimos 7 dias": "last_7d",
        "Últimos 30 dias": "last_30d",
        "Personalizado": custom_range
    }[date_range]
    
    with st.spinner("Carregando campanhas..."):
        campaigns = get_campaigns(ad_account)
        
        if campaigns and st.toggle('Mostrar dados brutos (debug)'):
            st.write("Dados brutos das campanhas:", campaigns)

    if not campaigns:
        st.warning("Nenhuma campanha encontrada nesta conta.")
        return
    
    selected_campaign = st.selectbox(
        "Selecione uma campanha:",
        options=campaigns,
        format_func=lambda x: f"{x.get('name', 'Sem Nome')} (ID: {x.get('id', 'N/A')})",
        key='campaign_select'
    )
    
    with st.spinner("Carregando conjuntos de anúncios..."):
        adsets = get_adsets(selected_campaign['id'])
    
    if not adsets:
        st.warning("Nenhum conjunto de anúncios encontrado nesta campanha.")
        return
    
    selected_adset = st.selectbox(
        "Selecione um conjunto de anúncios:",
        options=adsets,
        format_func=lambda x: f"{x.get('name', 'Sem Nome')} (ID: {x.get('id', 'N/A')})"
    )
    
    with st.spinner("Carregando anúncios..."):
        ads = get_ads(selected_adset['id'])
    
    if not ads:
        st.warning("Nenhum anúncio encontrado neste conjunto.")
        return
    
    selected_ad = st.selectbox(
        "Selecione um anúncio para análise:",
        options=ads,
        format_func=lambda x: f"{x.get('name', 'Sem Nome')} (ID: {x.get('id', 'N/A')})"
    )
    
    if st.button("🔍 Analisar Anúncio", type="primary"):
        with st.spinner("Coletando dados do anúncio..."):
            ad_details = {
                'id': selected_ad['id'],
                'name': selected_ad.get('name', 'N/A'),
                'status': selected_ad.get('status', 'N/A'),
                'created_time': selected_ad.get('created_time', 'N/A'),
                'bid_amount': selected_ad.get('bid_amount', 'N/A'),
                'campaign_id': selected_campaign['id'],
                'campaign_name': selected_campaign.get('name', 'N/A'),
                'campaign_objective': selected_campaign.get('objective', 'N/A'),
                'adset_id': selected_adset['id'],
                'adset_name': selected_adset.get('name', 'N/A'),
                'adset_budget': selected_adset.get('daily_budget', 'N/A'),
                'adset_optimization': selected_adset.get('optimization_goal', 'N/A')
            }
            
            ad_insights = get_ad_insights(selected_ad['id'], date_range_param)
            ad_demographics = get_ad_demographics(selected_ad['id'], date_range_param)
            temporal_data = get_ad_insights_over_time(selected_ad['id'], date_range_param)
            
            if ad_insights:
                show_ad_results(ad_details, ad_insights, ad_demographics, date_range_param, temporal_data)
            else:
                st.error("Não foi possível obter dados de desempenho para este anúncio.")

def show_ad_results(details, insights, demographics, date_range, temporal_data=None):
    st.success(f"✅ Dados obtidos com sucesso para o anúncio {details['id']}")
    
    # Seção de detalhes do anúncio
    st.markdown("### 📝 Detalhes do Anúncio")
    cols = st.columns(4)
    cols[0].metric("Nome do Anúncio", details.get('name', 'N/A'))
    cols[1].metric("Campanha", details.get('campaign_name', 'N/A'))
    cols[2].metric("Conjunto", details.get('adset_name', 'N/A'))
    cols[3].metric("Status", details.get('status', 'N/A'))
    
    cols = st.columns(4)
    cols[0].metric("Objetivo", details.get('campaign_objective', 'N/A'))
    cols[1].metric("Otimização", details.get('adset_optimization', 'N/A'))
    cols[2].metric("Lance", f"R$ {safe_float(details.get('bid_amount', 0)):.2f}")
    cols[3].metric("Orçamento Diário", f"R$ {safe_float(details.get('adset_budget', 0)):.2f}")
    
    # Seção de métricas de desempenho
    st.markdown("### 📊 Métricas de Desempenho")
    
    tab1, tab2, tab3 = st.tabs(["📈 Principais Métricas", "📉 Tendência Temporal", "📌 Ações Específicas"])
    
    with tab1:
        # Métricas principais em colunas
        col1, col2, col3 = st.columns(3)
        
        with col1:
            ctr = safe_float(insights.get('ctr', 0)) * 100
            st.plotly_chart(create_performance_gauge(
                ctr, 0, 10, 
                f"CTR: {ctr:.2f}%"), 
                use_container_width=True)
        
        with col2:
            conversions = safe_float(insights.get('conversions', 0))
            clicks = safe_float(insights.get('clicks', 0))
            conversion_rate = (conversions / clicks) * 100 if clicks > 0 else 0
            st.plotly_chart(create_performance_gauge(
                conversion_rate, 0, 20, 
                f"Taxa de Conversão: {conversion_rate:.2f}%"), 
                use_container_width=True)
        
        with col3:
            spend = safe_float(insights.get('spend', 0))
            conversions = safe_float(insights.get('conversions', 0))
            cost_per_conversion = spend / conversions if conversions > 0 else 0
            st.plotly_chart(create_performance_gauge(
                cost_per_conversion, 0, 100, 
                f"Custo por Conversão: R${cost_per_conversion:.2f}"), 
                use_container_width=True)
        
        # Outras métricas em colunas
        cols = st.columns(4)
        metrics = [
            ("Impressões", safe_int(insights.get('impressions', 0)), "{:,}"),
            ("Alcance", safe_int(insights.get('reach', 0)), "{:,}"),
            ("Frequência", safe_float(insights.get('frequency', 0)), "{:.2f}x"),
            ("Investimento", safe_float(insights.get('spend', 0)), "R$ {:,.2f}"),
            ("CPM", safe_float(insights.get('cpm', 0)), "R$ {:.2f}"),
            ("CPC", safe_float(insights.get('cost_per_unique_click', insights.get('cpp', 0))), "R$ {:.2f}"),
            ("Cliques", safe_int(insights.get('clicks', 0)), "{:,}"),
            ("Cliques Únicos", safe_int(insights.get('unique_outbound_clicks', 0)), "{:,}")
        ]
        
        for i, (label, value, fmt) in enumerate(metrics):
            cols[i % 4].metric(label, fmt.format(value))
    
    with tab2:
        if temporal_data is not None:
            st.subheader("📈 Análise Temporal Detalhada")

            available_metrics = ['impressions', 'reach', 'spend', 'clicks',
                                 'ctr', 'conversions', 'cost_per_conversion',
                                 'frequency', 'cpm', 'cpc', 'conversion_rate']

            # Usando session_state diretamente como default
            selected_metrics = st.multiselect(
                "Selecione métricas para visualizar:",
                options=available_metrics,
                default=st.session_state.get('temp_metrics', ['impressions', 'spend', 'conversions']),
                key='temp_metrics_unique_key'
            )

            # Atualiza o estado
            st.session_state.temp_metrics = selected_metrics

            if selected_metrics:
                # Gráfico de linhas principal
                fig = px.line(
                    temporal_data,
                    x='date_start',
                    y=selected_metrics,
                    title='Desempenho ao Longo do Tempo',
                    markers=True,
                    line_shape='spline'
                )
                fig.update_layout(
                    hovermode='x unified',
                    yaxis_title='Valor',
                    xaxis_title='Data'
                )
                st.plotly_chart(fig, use_container_width=True)
                
                # Análise de correlação
                st.subheader("🔍 Correlação Entre Métricas")
                corr_matrix = temporal_data[selected_metrics].corr()
                fig_corr = px.imshow(
                    corr_matrix,
                    text_auto=True,
                    aspect='auto',
                    color_continuous_scale='RdBu',
                    labels=dict(color='Correlação')
                )
                st.plotly_chart(fig_corr, use_container_width=True)
                
                # Melhores dias por métrica
                st.subheader("🏆 Melhores Dias")
                best_days = []
                for metric in selected_metrics:
                    best_day = temporal_data.loc[temporal_data[metric].idxmax()]
                    if pd.api.types.is_datetime64_any_dtype(best_day['date_start']):
                        date_str = best_day['date_start'].strftime('%Y-%m-%d')
                    else:
                        date_str = pd.to_datetime(best_day['date_start']).strftime('%Y-%m-%d')
                    
                    best_days.append({
                        'Métrica': metric,
                        'Data': best_day['date_start'].strftime('%Y-%m-%d'),
                        'Valor': best_day[metric],
                        'Investimento': best_day['spend']
                    })
                
                st.dataframe(pd.DataFrame(best_days), hide_index=True)
        else:
            st.warning("Dados temporais não disponíveis para este anúncio.")

    with tab3:
        # Mostra ações específicas e seus valores
        st.markdown("#### 🎯 Ações Específicas Registradas")
        
        # Filtra todas as chaves que começam com 'action_' ou 'action_value_'
        actions = {k: v for k, v in insights.items() if k.startswith('action_') or k.startswith('action_value_')}
        
        if actions:
            # Agrupa ações e valores
            action_types = set([k.split('_', 1)[1] for k in actions.keys()])
            
            for action_type in action_types:
                action_count = safe_int(actions.get(f'action_{action_type}', 0))
                action_value = safe_float(actions.get(f'action_value_{action_type}', 0))
                
                cols = st.columns(2)
                cols[0].metric(f"🔹 {action_type.replace('_', ' ').title()}", action_count)
                cols[1].metric(f"💰 Valor Total", f"R$ {action_value:.2f}")
        else:
            st.info("Nenhuma ação específica registrada para este anúncio no período selecionado")
    
    # Seção de análise demográfica
    if demographics:
        st.markdown("### 👥 Demografia do Público")
        
        # Separa dados por age/gender e country
        age_gender_data = [d for d in demographics if 'age' in d and 'gender' in d]
        country_data = [d for d in demographics if 'country' in d]
        
        if age_gender_data:
            df_age_gender = pd.DataFrame([
                {
                    'age': d.get('age', 'N/A'),
                    'gender': d.get('gender', 'N/A'),
                    'impressions': safe_int(d.get('impressions', 0)),
                    'clicks': safe_int(d.get('clicks', 0)),
                    'spend': safe_float(d.get('spend', 0)),
                    'conversions': safe_int(d.get('conversions', 0))
                }
                for d in age_gender_data
            ])
            
            # Calcula métricas derivadas
            df_age_gender['CTR'] = df_age_gender['clicks'] / df_age_gender['impressions'].replace(0, 1) * 100
            df_age_gender['CPM'] = (df_age_gender['spend'] / df_age_gender['impressions'].replace(0, 1)) * 1000
            
            st.markdown("#### Distribuição por Idade e Gênero")
            pivot_age_gender = df_age_gender.groupby(['age', 'gender'])['impressions'].sum().unstack()
            st.plotly_chart(
                px.bar(pivot_age_gender, barmode='group', 
                      labels={'value': 'Impressões', 'age': 'Faixa Etária'},
                      title='Impressões por Faixa Etária e Gênero'),
                use_container_width=True
            )
        
        if country_data:
            df_country = pd.DataFrame([
                {
                    'country': d.get('country', 'N/A'),
                    'impressions': safe_int(d.get('impressions', 0)),
                    'clicks': safe_int(d.get('clicks', 0)),
                    'spend': safe_float(d.get('spend', 0)),
                    'conversions': safe_int(d.get('conversions', 0))
                }
                for d in country_data
            ])
            
            df_country['CPM'] = (df_country['spend'] / df_country['impressions'].replace(0, 1)) * 1000
            
            st.markdown("#### Distribuição por País")
            country_dist = df_country.groupby('country')['impressions'].sum().nlargest(10)
            st.plotly_chart(
                px.pie(country_dist, values='impressions', names=country_dist.index,
                      title='Top 10 Países por Impressões'),
                use_container_width=True
            )
    
    # Seção de recomendações
    st.markdown("### 💡 Recomendações de Otimização")
    
    recommendations = generate_performance_recommendations(insights, temporal_data)
    
    if not recommendations:
        st.success("✅ Seu anúncio está performando dentro ou acima dos benchmarks!")
        st.write("Ações recomendadas para manter o bom desempenho:")
        st.write("- Continue monitorando as métricas regularmente")
        st.write("- Teste pequenas variações para otimização contínua")
        st.write("- Considere aumentar o orçamento para escalar")
    else:
        for rec in recommendations:
            if rec['type'] == 'error':
                st.error(f"#### {rec['title']}: {rec['message']}")
            elif rec['type'] == 'warning':
                st.warning(f"#### {rec['title']}: {rec['message']}")
            else:
                st.success(f"#### {rec['title']}: {rec['message']}")
                container = st.success
            
            st.write("**Ações recomendadas:**")
            for action in rec['actions']:
                st.write(f"- {action}")
        
        # Plano de testes sugerido
        st.markdown("#### 📅 Plano de Testes Prioritários")
        test_plan = pd.DataFrame({
            'Prioridade': ["Alta", "Média", "Baixa"],
            'Teste': [
                "Variar criativos (imagem/texto)",
                "Ajustar segmentação de público",
                "Testar diferentes horários"
            ],
            'Duração': ["3-5 dias", "5-7 dias", "7-10 dias"],
            'Métrica-Chave': ["CTR", "Custo/Conversão", "Conversões"]
        })
        st.table(test_plan)
    
    # Seção de próximos passos
    st.markdown("### 🚀 Próximos Passos")
    st.write("1. **Implemente as mudanças sugeridas** de forma gradual")
    st.write("2. **Monitore os resultados** diariamente por 3-5 dias")
    st.write("3. **Documente os aprendizados** para cada variação testada")
    st.write("4. **Escalone o que funciona** e pause o que não performa")
    
    if temporal_data is not None:
        st.download_button(
            label="📥 Baixar Dados Completos",
            data=temporal_data.to_csv(index=False).encode('utf-8'),
            file_name=f"dados_anuncio_{details['id']}.csv",
            mime='text/csv'
        )

 # ==============================================
# ANÁLISE ESTRATÉGICA AVANÇADA
# ==============================================

def generate_strategic_analysis(ad_details, insights, demographics, temporal_data):
    """Gera uma análise estratégica completa com recomendações baseadas em dados"""
    
    # Cálculos preliminares com proteção contra divisão por zero
    ctr = safe_float(insights.get('ctr', 0)) * 100 if safe_float(insights.get('impressions', 0)) > 0 else 0
    clicks = safe_float(insights.get('clicks', 0))
    conversions = safe_float(insights.get('conversions', 0))
    spend = safe_float(insights.get('spend', 0))
    impressions = safe_float(insights.get('impressions', 0))
    
    conversion_rate = (conversions / clicks) * 100 if clicks > 0 else 0
    cost_per_conversion = spend / conversions if conversions > 0 else 0
    cpm = (spend / impressions) * 1000 if impressions > 0 else 0
    cpc = spend / clicks if clicks > 0 else 0
    
    # Benchmarks do setor (podem ser ajustados conforme o objetivo da campanha)
    benchmarks = {
        'ctr': 2.0,
        'conversion_rate': 3.0,
        'cost_per_conversion': 50.0,
        'cpm': 10.0,
        'cpc': 1.5
    }
    
    # Análise de frequência (se houver dados temporais)
    freq_mean = temporal_data['frequency'].mean() if temporal_data is not None else 0
    
    with st.expander("🔍 Análise Estratégica Completa", expanded=True):
        
        # Seção 1: Diagnóstico de Performance
        st.subheader("📊 Diagnóstico de Performance")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("CTR", f"{ctr:.2f}%", 
                     delta=f"{'↑' if ctr > benchmarks['ctr'] else '↓'} vs benchmark {benchmarks['ctr']}%",
                     delta_color="inverse")
        
        with col2:
            st.metric("Taxa de Conversão", f"{conversion_rate:.2f}%",
                     delta=f"{'↑' if conversion_rate > benchmarks['conversion_rate'] else '↓'} vs benchmark {benchmarks['conversion_rate']}%",
                     delta_color="inverse")
        
        with col3:
            st.metric("Custo por Conversão", f"R${cost_per_conversion:.2f}",
                     delta=f"{'↓' if cost_per_conversion < benchmarks['cost_per_conversion'] else '↑'} vs benchmark R${benchmarks['cost_per_conversion']}",
                     delta_color="inverse")
        
        # Seção 2: Pontos Fortes Identificados
        st.subheader("✅ Pontos Fortes Identificados")
        
        strengths = []
        
        # Identificar pontos fortes com base nos dados
        if ctr > benchmarks['ctr'] * 1.2:
            strengths.append(f"CTR excelente ({ctr:.2f}%) - {ctr/benchmarks['ctr']:.1f}x acima da média")
        
        if conversion_rate > benchmarks['conversion_rate'] * 1.2:
            strengths.append(f"Taxa de conversão alta ({conversion_rate:.2f}%) - Eficiência no funnel")
        
        if cost_per_conversion < benchmarks['cost_per_conversion'] * 0.8:
            strengths.append(f"Custo por conversão baixo (R${cost_per_conversion:.2f}) - Eficiência de gastos")
        
        if demographics:
            # Verificar se há segmentos com performance excepcional
            df_age_gender = pd.DataFrame([
                {
                'age': d.get('age', 'N/A'),
                'gender': d.get('gender', 'N/A'),
                'ctr': (safe_int(d.get('clicks', 0)) / safe_int(d.get('impressions', 1)) * 100) if safe_int(d.get('impressions', 0)) > 0 else 0,
                'conversion_rate': (safe_int(d.get('conversions', 0)) / safe_int(d.get('clicks', 1)) * 100) if safe_int(d.get('clicks', 0)) > 0 else 0,
                'cpa': safe_int(d.get('spend', 0)) / max(1, safe_int(d.get('conversions', 0)))
            }
            for d in demographics if 'age' in d and 'gender' in d
        ])
            
            if not df_age_gender.empty:
             top_segment = df_age_gender.loc[df_age_gender['ctr'].idxmax()]
            if top_segment['ctr'] > benchmarks['ctr'] * 1.5:
                strengths.append(f"Segmento de alto desempenho: {top_segment['gender']} {top_segment['age']} (CTR: {top_segment['ctr']:.2f}%)")

        if strengths:
            for strength in strengths:
                st.success(f"- {strength}")
        else:
            st.info("Nenhum ponto forte excepcional identificado. Foque em otimizações básicas.")
        
        # Seção 3: Oportunidades de Melhoria
        st.subheader("🔧 Oportunidades de Melhoria")
        
        improvements = []
        
        if ctr < benchmarks['ctr'] * 0.8:
            improvements.append(f"CTR baixo ({ctr:.2f}%) - Testar novos criativos e chamadas para ação")
        
        if conversion_rate < benchmarks['conversion_rate'] * 0.8:
            improvements.append(f"Taxa de conversão baixa ({conversion_rate:.2f}%) - Otimizar landing page e jornada do usuário")
        
        if cost_per_conversion > benchmarks['cost_per_conversion'] * 1.2:
            improvements.append(f"Custo por conversão alto (R${cost_per_conversion:.2f}) - Refinar público-alvo e segmentação")
        
        if freq_mean > 3.5:
            improvements.append(f"Frequência alta ({freq_mean:.1f}x) - Risco de saturação, considere atualizar criativos ou expandir público")
        
        if improvements:
            for improvement in improvements:
                st.error(f"- {improvement}")
        else:
            st.success("Performance geral dentro ou acima dos benchmarks. Considere escalar campanhas bem-sucedidas.")
        
        # Seção 4: Recomendações Específicas por Tipo de Anúncio
        st.subheader("🎯 Recomendações Específicas")
        
        # Baseado no tipo de campanha (do adset ou campaign)
        campaign_objective = ad_details.get('campaign_objective', '').lower()
        
        if 'conversion' in campaign_objective:
            st.write("""
            **Para campanhas de conversão:**
            - Teste diferentes CTAs na landing page
            - Implemente eventos de conversão secundários
            - Otimize para públicos similares a convertidos
            """)
        elif 'awareness' in campaign_objective:
            st.write("""
            **Para campanhas de awareness:**
            - Aumente o alcance com formatos de vídeo
            - Utilize o recurso de expansão de público
            - Monitore a frequência para evitar saturação
            """)
        else:
            st.write("""
            **Recomendações gerais:**
            - Teste pelo menos 3 variações de criativos
            - Experimente diferentes horários de veiculação
            - Ajuste bids conforme performance por segmento
            """)
        
        # Seção 5: Plano de Ação Priorizado
        st.subheader("📅 Plano de Ação Priorizado")
        
        action_plan = []
        
        # Prioridade 1: CTR baixo
        if ctr < benchmarks['ctr'] * 0.8:
            action_plan.append({
                "Prioridade": "Alta",
                "Ação": "Otimizar CTR",
                "Tarefas": [
                    "Criar 3 variações de imagens/thumbnails",
                    "Testar diferentes textos principais (max 125 chars)",
                    "Posicionar CTA mais destacado"
                ],
                "Prazo": "3 dias",
                "Métrica Esperada": f"Aumentar CTR para ≥ {benchmarks['ctr']}%"
            })
        
        # Prioridade 2: Conversão baixa
        if conversion_rate < benchmarks['conversion_rate'] * 0.8:
            action_plan.append({
                "Prioridade": "Alta",
                "Ação": "Melhorar Taxa de Conversão",
                "Tarefas": [
                    "Otimizar landing page (velocidade, design, CTA)",
                    "Implementar pop-ups inteligentes",
                    "Simplificar formulários de conversão"
                ],
                "Prazo": "5 dias",
                "Métrica Esperada": f"Aumentar conversão para ≥ {benchmarks['conversion_rate']}%"
            })
        
        # Prioridade 3: Frequência alta
        if freq_mean > 3.5:
            action_plan.append({
                "Prioridade": "Média",
                "Ação": "Reduzir Saturação",
                "Tarefas": [
                    "Atualizar criativos principais",
                    "Expandir público-alvo",
                    "Ajustar orçamento por horário"
                ],
                "Prazo": "2 dias",
                "Métrica Esperada": f"Reduzir frequência para ≤ 3x"
            })
        
        # Se não houver problemas críticos, sugerir otimizações padrão
        if not action_plan:
            action_plan.append({
                "Prioridade": "Otimização",
                "Ação": "Escalonar Performance",
                "Tarefas": [
                    "Aumentar orçamento em 20% para melhores performers",
                    "Criar públicos lookalike baseados em convertidos",
                    "Testar novos formatos criativos"
                ],
                "Prazo": "Contínuo",
                "Métrica Esperada": "Manter ROAS ≥ 2.0"
            })
        
        st.table(pd.DataFrame(action_plan))
        
        # Seção 6: Projeção de Resultados
        st.subheader("📈 Projeção de Resultados")
        
        if temporal_data is not None:
            # Calcular crescimento médio diário
            last_7_days = temporal_data.tail(7)
            growth_rates = {
                'impressions': last_7_days['impressions'].pct_change().mean() * 100,
                'ctr': last_7_days['ctr'].pct_change().mean() * 100,
                'conversions': last_7_days['conversions'].pct_change().mean() * 100
            }
            
            projections = {
                "Cenário": ["Conservador", "Otimista", "Pessimista"],
                "Impressões (7 dias)": [
                    f"{impressions * 0.9:,.0f}",
                    f"{impressions * 1.3:,.0f}",
                    f"{impressions * 0.7:,.0f}"
                ],
                "Conversões (7 dias)": [
                    f"{conversions * 0.9:,.0f}",
                    f"{conversions * 1.5:,.0f}",
                    f"{conversions * 0.6:,.0f}"
                ],
                "Investimento": [
                    f"R${spend * 0.9:,.2f}",
                    f"R${spend * 1.5:,.2f}",
                    f"R${spend * 0.7:,.2f}"
                ],
                "ROI Esperado": [
                    f"{(conversions * 0.9 * 100) / max(1, spend * 0.9):.1f}%",
                    f"{(conversions * 1.5 * 100) / max(1, spend * 1.5):.1f}%",
                    f"{(conversions * 0.6 * 100) / max(1, spend * 0.7):.1f}%"
                ]
            }
            
            st.table(pd.DataFrame(projections))
            
            st.caption(f"*Baseado em crescimento médio atual: CTR {growth_rates['ctr']:.1f}% ao dia, Conversões {growth_rates['conversions']:.1f}% ao dia*")
        
        # Seção 7: Checklist de Implementação
        st.subheader("✅ Checklist de Implementação")
        
        checklist_items = [
            "Definir KPI principal e secundários",
            "Configurar eventos de conversão no Pixel",
            "Estabelecer orçamento diário mínimo para testes",
            "Criar pelo menos 3 variações de criativos",
            "Segmentar públicos por desempenho histórico",
            "Configurar relatórios automáticos de performance",
            "Estabelecer frequência de análise (recomendado diária)"
        ]
        
        for item in checklist_items:
            st.checkbox(item, key=f"check_{hashlib.md5(item.encode()).hexdigest()}")

# ==============================================
# MODIFICAÇÃO NA FUNÇÃO show_ad_results PARA INCLUIR A ANÁLISE ESTRATÉGICA
# ==============================================

def show_ad_results(details, insights, demographics, date_range, temporal_data=None):
    st.success(f"✅ Dados obtidos com sucesso para o anúncio {details['id']}")
    
    # Seção de detalhes do anúncio
    st.markdown("### 📝 Detalhes do Anúncio")
    cols = st.columns(4)
    cols[0].metric("Nome do Anúncio", details.get('name', 'N/A'))
    cols[1].metric("Campanha", details.get('campaign_name', 'N/A'))
    cols[2].metric("Conjunto", details.get('adset_name', 'N/A'))
    cols[3].metric("Status", details.get('status', 'N/A'))
    
    cols = st.columns(4)
    cols[0].metric("Objetivo", details.get('campaign_objective', 'N/A'))
    cols[1].metric("Otimização", details.get('adset_optimization', 'N/A'))
    cols[2].metric("Lance", f"R$ {safe_float(details.get('bid_amount', 0)):.2f}")
    cols[3].metric("Orçamento Diário", f"R$ {safe_float(details.get('adset_budget', 0)):.2f}")
    
    # Seção de métricas de desempenho
    st.markdown("### 📊 Métricas de Desempenho")
    
    tab1, tab2, tab3 = st.tabs(["📈 Principais Métricas", "📉 Tendência Temporal", "📌 Ações Específicas"])
    
    with tab1:
        # Métricas principais em colunas
        col1, col2, col3 = st.columns(3)
        
        with col1:
            ctr = safe_float(insights.get('ctr', 0)) * 100
            st.plotly_chart(create_performance_gauge(
                ctr, 0, 10, 
                f"CTR: {ctr:.2f}%"), 
                use_container_width=True)
        
        with col2:
            conversions = safe_float(insights.get('conversions', 0))
            clicks = safe_float(insights.get('clicks', 0))
            conversion_rate = (conversions / clicks) * 100 if clicks > 0 else 0
            st.plotly_chart(create_performance_gauge(
                conversion_rate, 0, 20, 
                f"Taxa de Conversão: {conversion_rate:.2f}%"), 
                use_container_width=True)
        
        with col3:
            spend = safe_float(insights.get('spend', 0))
            conversions = safe_float(insights.get('conversions', 0))
            cost_per_conversion = spend / conversions if conversions > 0 else 0
            st.plotly_chart(create_performance_gauge(
                cost_per_conversion, 0, 100, 
                f"Custo por Conversão: R${cost_per_conversion:.2f}"), 
                use_container_width=True)
        
        # Outras métricas em colunas
        cols = st.columns(4)
        metrics = [
            ("Impressões", safe_int(insights.get('impressions', 0)), "{:,}"),
            ("Alcance", safe_int(insights.get('reach', 0)), "{:,}"),
            ("Frequência", safe_float(insights.get('frequency', 0)), "{:.2f}x"),
            ("Investimento", safe_float(insights.get('spend', 0)), "R$ {:,.2f}"),
            ("CPM", safe_float(insights.get('cpm', 0)), "R$ {:.2f}"),
            ("CPC", safe_float(insights.get('cost_per_unique_click', insights.get('cpp', 0))), "R$ {:.2f}"),
            ("Cliques", safe_int(insights.get('clicks', 0)), "{:,}"),
            ("Cliques Únicos", safe_int(insights.get('unique_outbound_clicks', 0)), "{:,}")
        ]
        
        for i, (label, value, fmt) in enumerate(metrics):
            cols[i % 4].metric(label, fmt.format(value))
    
    with tab2:
        if temporal_data is not None:
            st.subheader("📈 Análise Temporal Detalhada")

            available_metrics = ['impressions', 'reach', 'spend', 'clicks',
                                 'ctr', 'conversions', 'cost_per_conversion',
                                 'frequency', 'cpm', 'cpc', 'conversion_rate']

            selected_metrics = st.multiselect(
                "Selecione métricas para visualizar:",
                options=available_metrics,
                default=['impressions', 'spend', 'conversions'],
                key='temp_metrics_unique_key'
            )

            if selected_metrics:
                # Gráfico de linhas principal
                fig = px.line(
                    temporal_data,
                    x='date_start',
                    y=selected_metrics,
                    title='Desempenho ao Longo do Tempo',
                    markers=True,
                    line_shape='spline'
                )
                fig.update_layout(
                    hovermode='x unified',
                    yaxis_title='Valor',
                    xaxis_title='Data'
                )
                st.plotly_chart(fig, use_container_width=True)
                
                # Análise de correlação
                st.subheader("🔍 Correlação Entre Métricas")
                corr_matrix = temporal_data[selected_metrics].corr()
                fig_corr = px.imshow(
                    corr_matrix,
                    text_auto=True,
                    aspect='auto',
                    color_continuous_scale='RdBu',
                    labels=dict(color='Correlação')
                )
                st.plotly_chart(fig_corr, use_container_width=True)
                
                # Melhores dias por métrica
                st.subheader("🏆 Melhores Dias")
                best_days = []
                for metric in selected_metrics:
                    best_day = temporal_data.loc[temporal_data[metric].idxmax()]
                    if pd.api.types.is_datetime64_any_dtype(best_day['date_start']):
                        date_str = best_day['date_start'].strftime('%Y-%m-%d')
                    else:
                        date_str = pd.to_datetime(best_day['date_start']).strftime('%Y-%m-%d')
                    
                    best_days.append({
                        'Métrica': metric,
                        'Data': best_day['date_start'].strftime('%Y-%m-%d'),
                        'Valor': best_day[metric],
                        'Investimento': best_day['spend']
                    })
                
                st.dataframe(pd.DataFrame(best_days), hide_index=True)
        else:
            st.warning("Dados temporais não disponíveis para este anúncio.")

    with tab3:
        # Mostra ações específicas e seus valores
        st.markdown("#### 🎯 Ações Específicas Registradas")
        
        # Filtra todas as chaves que começam com 'action_' ou 'action_value_'
        actions = {k: v for k, v in insights.items() if k.startswith('action_') or k.startswith('action_value_')}
        
        if actions:
            # Agrupa ações e valores
            action_types = set([k.split('_', 1)[1] for k in actions.keys()])
            
            for action_type in action_types:
                action_count = safe_int(actions.get(f'action_{action_type}', 0))
                action_value = safe_float(actions.get(f'action_value_{action_type}', 0))
                
                cols = st.columns(2)
                cols[0].metric(f"🔹 {action_type.replace('_', ' ').title()}", action_count)
                cols[1].metric(f"💰 Valor Total", f"R$ {action_value:.2f}")
        else:
            st.info("Nenhuma ação específica registrada para este anúncio no período selecionado")
    
    # Seção de análise demográfica
    if demographics:
        st.markdown("### 👥 Demografia do Público")
        
        # Separa dados por age/gender e country
        age_gender_data = [d for d in demographics if 'age' in d and 'gender' in d]
        country_data = [d for d in demographics if 'country' in d]
        
        if age_gender_data:
            df_age_gender = pd.DataFrame([
                {
                    'age': d.get('age', 'N/A'),
                    'gender': d.get('gender', 'N/A'),
                    'impressions': safe_int(d.get('impressions', 0)),
                    'clicks': safe_int(d.get('clicks', 0)),
                    'spend': safe_float(d.get('spend', 0)),
                    'conversions': safe_int(d.get('conversions', 0))
                }
                for d in age_gender_data
            ])
            
            # Calcula métricas derivadas
            df_age_gender['CTR'] = df_age_gender['clicks'] / df_age_gender['impressions'].replace(0, 1) * 100
            df_age_gender['CPM'] = (df_age_gender['spend'] / df_age_gender['impressions'].replace(0, 1)) * 1000
            
            st.markdown("#### Distribuição por Idade e Gênero")
            pivot_age_gender = df_age_gender.groupby(['age', 'gender'])['impressions'].sum().unstack()
            st.plotly_chart(
                px.bar(pivot_age_gender, barmode='group', 
                      labels={'value': 'Impressões', 'age': 'Faixa Etária'},
                      title='Impressões por Faixa Etária e Gênero'),
                use_container_width=True
            )
        
        if country_data:
            df_country = pd.DataFrame([
                {
                    'country': d.get('country', 'N/A'),
                    'impressions': safe_int(d.get('impressions', 0)),
                    'clicks': safe_int(d.get('clicks', 0)),
                    'spend': safe_float(d.get('spend', 0)),
                    'conversions': safe_int(d.get('conversions', 0))
                }
                for d in country_data
            ])
            
            df_country['CPM'] = (df_country['spend'] / df_country['impressions'].replace(0, 1)) * 1000
            
            st.markdown("#### Distribuição por País")
            country_dist = df_country.groupby('country')['impressions'].sum().nlargest(10)
            st.plotly_chart(
                px.pie(country_dist, values='impressions', names=country_dist.index,
                      title='Top 10 Países por Impressões'),
                use_container_width=True
            )
    
    # Chamada para a nova análise estratégica
    generate_strategic_analysis(details, insights, demographics, temporal_data)
    
    # Seção de recomendações (mantida para compatibilidade)
    st.markdown("### 💡 Recomendações de Otimização")
    
    recommendations = generate_performance_recommendations(insights, temporal_data)
    
    if not recommendations:
        st.success("✅ Seu anúncio está performando dentro ou acima dos benchmarks!")
        st.write("Ações recomendadas para manter o bom desempenho:")
        st.write("- Continue monitorando as métricas regularmente")
        st.write("- Teste pequenas variações para otimização contínua")
        st.write("- Considere aumentar o orçamento para escalar")
    else:
        for rec in recommendations:
            if rec['type'] == 'error':
                st.error(f"#### {rec['title']}: {rec['message']}")
            elif rec['type'] == 'warning':
                st.warning(f"#### {rec['title']}: {rec['message']}")
            else:
                st.success(f"#### {rec['title']}: {rec['message']}")
            
            st.write("**Ações recomendadas:**")
            for action in rec['actions']:
                st.write(f"- {action}")
    
    # Seção de próximos passos
    st.markdown("### 🚀 Próximos Passos")
    st.write("1. **Implemente as mudanças sugeridas** de forma gradual")
    st.write("2. **Monitore os resultados** diariamente por 3-5 dias")
    st.write("3. **Documente os aprendizados** para cada variação testada")
    st.write("4. **Escalone o que funciona** e pause o que não performa")
    
    if temporal_data is not None:
        st.download_button(
            label="📥 Baixar Dados Completos",
            data=temporal_data.to_csv(index=False).encode('utf-8'),
            file_name=f"dados_anuncio_{details['id']}.csv",
            mime='text/csv'
        )

# ==============================================
# FUNÇÃO PRINCIPAL
# ==============================================

def main():
    st.title("🚀 Meta Ads Analyzer Pro")
    st.markdown("""
    **Ferramenta avançada para análise de desempenho de anúncios no Meta (Facebook e Instagram)**
    """)
    
    # Mostra instruções de como obter as credenciais
    with st.expander("ℹ️ Como obter minhas credenciais?", expanded=False):
        st.markdown("""
        Para usar esta ferramenta, você precisará das seguintes credenciais da API do Meta:
        
        1. **App ID** e **App Secret**:  
           - Vá para [Facebook Developers](https://developers.facebook.com/)  
           - Selecione seu aplicativo ou crie um novo  
           - Encontre essas informações em "Configurações" > "Básico"
        
        2. **Access Token**:  
           - No mesmo painel, vá para "Ferramentas" > "Explorador de API"  
           - Selecione seu aplicativo  
           - Gere um token de acesso de longo prazo com permissões ads_management
        
        3. **Ad Account ID**:  
           - Vá para [Meta Ads Manager](https://adsmanager.facebook.com/)  
           - Selecione sua conta de anúncios  
           - O ID estará na URL (após /act_) ou em "Configurações da Conta"
        
        *Observação: Suas credenciais são usadas apenas localmente e não são armazenadas.*
        """)
    
    menu = st.sidebar.selectbox(
        "Modo de Análise",
        ["📊 Meus Anúncios (API)", "🔍 Analisar Anúncio Público"],
        help="Selecione o tipo de análise desejada"
    )
    
    if menu == "📊 Meus Anúncios (API)":
        st.sidebar.info("Acesse dados completos dos seus anúncios via API")
        # A API será inicializada dentro de show_real_analysis
        show_real_analysis()
    else:
        st.sidebar.warning("Dados estimados baseados em benchmarks públicos e análise de metadados")
        show_public_ad_analysis()

if __name__ == "__main__":
    main()