import streamlit as st
import pandas as pd
import numpy as np
import folium
from streamlit_folium import st_folium
import json
from thefuzz import process
import os

st.set_page_config(
    page_title="Dashboard Kerawanan Pangan EWS",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    h1 { font-family: 'Inter', sans-serif; }
    [data-testid="stMetric"] { 
        background-color: var(--secondary-background-color); 
        padding: 15px; 
        border-radius: 10px; 
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1); 
    }
</style>
""", unsafe_allow_html=True)

st.title("🌾SIGAP : EWS Ketahanan Pangan Tahun 2026-2028")
st.markdown("Arahkan kursor ke area kabupaten/kota untuk melihat tingkat kerawanan pangannya.")

@st.cache_data
def load_data(year):
    sheet_name = f'Prediksi_{year}'
    try:
        df = pd.read_excel('EWS_Ketahanan_Pangan_2026_2028.xlsx', sheet_name=sheet_name)
    except Exception as e:
        st.error(f"Gagal memuat data untuk tahun {year}: {e}")
        return pd.DataFrame()
        
    y_pred_col = [col for col in df.columns if col.startswith('Y_pred_')]
    if y_pred_col:
        df['Nilai_Prediksi'] = df[y_pred_col[0]]
    else:
        df['Nilai_Prediksi'] = 6
        
    return df

@st.cache_data
def load_geojson():
    if not os.path.exists('indonesia_kabkota.geojson'):
        return None
    with open('indonesia_kabkota.geojson', 'r', encoding='utf-8') as f:
        return json.load(f)

df = load_data(st.sidebar.selectbox("Pilih Tahun Prediksi:", [2026, 2027, 2028]))
geojson_data = load_geojson()

if df.empty or geojson_data is None:
    st.warning("Data atau file peta GeoJSON tidak ditemukan.")
    st.stop()

col1, col2, col3 = st.columns(3)
with col1: st.metric(label="Total Wilayah Dianalisis", value=len(df))
with col2: st.metric(label="Jumlah Wilayah Sangat Rawan", value=len(df[df['Nilai_Prediksi'] == 1]))
paling_rawan_df = df[df['Nilai_Prediksi'] == df['Nilai_Prediksi'].min()]
with col3: st.metric(label="Contoh Wilayah Prioritas", value=paling_rawan_df.iloc[0]['kabupaten_kota'] if not paling_rawan_df.empty else "-")

st.markdown("---")

excel_kabkota = df['kabupaten_kota'].tolist()

@st.cache_data
def create_name_mapping(geojson_features, excel_names):
    mapping = {}
    excel_names_list = list(excel_names)
    
    manual_overrides = {
        'Maluku Tenggara Barat': 'Kab. Kepulauan Tanimbar'
    }
    
    for feature in geojson_features:
        geo_name = feature['properties']['name']
        
        if geo_name in manual_overrides:
            mapping[geo_name] = manual_overrides[geo_name]
            continue
            
        clean_geo = geo_name.lower().replace('kabupaten', '').replace('kota', '').strip()
        
        best_match, score = process.extractOne(clean_geo, excel_names_list)
        if score > 80:
            mapping[geo_name] = best_match
            
    return mapping

name_map = create_name_mapping(geojson_data['features'], excel_kabkota)

df_dict = df.set_index('kabupaten_kota').to_dict('index')

for feature in geojson_data['features']:
    geo_name = feature['properties']['name']
    matched_name = name_map.get(geo_name)
    if matched_name and matched_name in df_dict:
        row = df_dict[matched_name]
        feature['properties']['Excel_Name'] = matched_name
        feature['properties']['Prediksi'] = row.get('Nilai_Prediksi', '-')
        feature['properties']['Zona'] = row.get('EWS_zona', '-')

        feature['properties']['Padi'] = f"{row.get('produksi_padi', '-'):.2f}" if isinstance(row.get('produksi_padi'), (int, float)) else "-"
        feature['properties']['Hujan'] = f"{row.get('curah_hujan', '-'):.2f}" if isinstance(row.get('curah_hujan'), (int, float)) else "-"
        feature['properties']['Pendapatan'] = f"{row.get('pendapatan', '-'):.2f}" if isinstance(row.get('pendapatan'), (int, float)) else "-"
        feature['properties']['Miskin'] = f"{row.get('tingkat_kemiskinan', '-'):.2f}" if isinstance(row.get('tingkat_kemiskinan'), (int, float)) else "-"
        feature['properties']['AirBersih'] = f"{row.get('tanpa_akses_air_bersih', '-'):.2f}" if isinstance(row.get('tanpa_akses_air_bersih'), (int, float)) else "-"
    else:
        feature['properties']['Excel_Name'] = geo_name
        feature['properties']['Prediksi'] = None
        feature['properties']['Zona'] = "Tidak Ada Data"
        feature['properties']['Padi'] = "-"
        feature['properties']['Hujan'] = "-"
        feature['properties']['Pendapatan'] = "-"
        feature['properties']['Miskin'] = "-"
        feature['properties']['AirBersih'] = "-"

st.subheader("🗺️ Peta Wilayah Interaktif")

colors_dict = {
    1: '#d7191c',
    2: '#fdae61',
    3: '#ffffbf',
    4: '#a6d96a',
    5: '#1a9641',
    6: '#006837'
}

m = folium.Map(location=[-2.5, 118.0], zoom_start=5, tiles="OpenStreetMap")

folium.GeoJson(
    geojson_data,
    style_function=lambda feature: {
        'fillColor': colors_dict.get(feature['properties'].get('Prediksi'), 'transparent'), # Langsung berwarna dari awal
        'color': 'gray',
        'weight': 0.5,
        'fillOpacity': 0.6 if feature['properties'].get('Prediksi') else 0.0
    },
    highlight_function=lambda feature: {
        'fillColor': colors_dict.get(feature['properties'].get('Prediksi'), 'gray'),
        'color': 'black',
        'weight': 2,
        'fillOpacity': 0.9 # Warna menjadi lebih pekat saat disorot kursor
    },
    tooltip=folium.GeoJsonTooltip(
        fields=['Excel_Name', 'Zona', 'Prediksi', 'Padi', 'Hujan', 'Pendapatan', 'Miskin', 'AirBersih'],
        aliases=['Kab/Kota:', 'Status Zona:', 'Nilai Prediksi:', 'Est. Produksi Padi:', 'Est. Curah Hujan:', 'Est. Pendapatan:', 'Est. % Kemiskinan:', 'Tanpa Akses Air Bersih:'],
        localize=True
    )
).add_to(m)

col_map, col_legend = st.columns([8.5, 1.5])

with col_map:
    st.components.v1.html(m._repr_html_(), width=1000, height=600)

with col_legend:
    st.markdown("<br><p style='font-size: 14px; font-weight: bold; margin-bottom: 5px;'>Nilai Prediksi</p>", unsafe_allow_html=True)
    legend_html = '''
    <div style="display: flex; height: 500px; align-items: stretch;">
        <div style="width: 25px; background: linear-gradient(to bottom, #006837, #1a9641, #a6d96a, #ffffbf, #fdae61, #d7191c); border-radius: 5px;"></div>
        <div style="display: flex; flex-direction: column; justify-content: space-between; margin-left: 10px; font-weight: bold; font-size: 14px; padding-bottom: 2px; padding-top: 2px;">
            <span>6 (Aman)</span>
            <span>5</span>
            <span>4</span>
            <span>3</span>
            <span>2</span>
            <span>1 (Rawan)</span>
        </div>
    </div>
    '''
    st.markdown(legend_html, unsafe_allow_html=True)

st.markdown("---")
st.subheader("📋 Detail Data Wilayah")

display_cols = ['provinsi', 'kabupaten_kota', 'Nilai_Prediksi', 'EWS_zona', 'produksi_padi', 'curah_hujan', 'pendapatan', 'tingkat_kemiskinan', 'tanpa_akses_air_bersih']

df_display = df[display_cols].copy()

df_display.columns = [
    'Provinsi', 
    'Kabupaten/Kota', 
    'Nilai Prediksi', 
    'Status Zona', 
    'Produksi Padi', 
    'Curah Hujan', 
    'Pendapatan', 
    '% Kemiskinan', 
    'Tanpa Air Bersih'
]

st.dataframe(df_display, use_container_width=True, hide_index=True)