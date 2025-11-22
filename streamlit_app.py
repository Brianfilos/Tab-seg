import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# -------------------------------------------------------------------
# 0. CONFIGURACIÓN GENERAL
# -------------------------------------------------------------------
st.set_page_config(
    page_title="Análisis Impuesto Predial Unificado - Segovia",
    layout="wide",
    initial_sidebar_state="expanded",
)

LOGO_LEGAL_PATH = "logo_legal.png"
LOGO_MUNICIPIO_PATH = "logo_segovia.png"

# -------------------------------------------------------------------
# 1. ESTILOS Y ENCABEZADO
# -------------------------------------------------------------------
st.markdown(
    """
<style>
.header-container { text-align: center; padding-bottom: 10px; }
.main-title { font-size: 2.4em; font-weight: bold; color: #004c99; margin-bottom: 0px; }
.subtitle { font-size: 1.1em; color: #555555; margin-top: 5px; }
.ica-description { font-size: 0.95em; color: #333333; margin-top: 15px; margin-bottom: 25px;
  padding: 10px 0; border-top: 1px solid #dddddd; text-align: justify; }
</style>
""",
    unsafe_allow_html=True,
)

col_logo_legal, col_title, col_logo_mun = st.columns([1, 4, 1])

with col_logo_legal:
    try:
        st.image(LOGO_LEGAL_PATH, width=100)
    except Exception:
        st.write("")

with col_title:
    st.markdown(
        '<div class="header-container">'
        '<p class="main-title">ANÁLISIS DEL IMPUESTO PREDIAL UNIFICADO</p>'
        '<p class="subtitle">Municipio de Segovia, Antioquia</p>'
        "</div>",
        unsafe_allow_html=True,
    )

with col_logo_mun:
    try:
        st.image(LOGO_MUNICIPIO_PATH, width=100)
    except Exception:
        st.write("")

st.markdown(
    """
<p class="ica-description">
El Impuesto Predial Unificado se viene calculando con avalúos desactualizados y el esquema
tarifario definido en 2018, diferenciando zonas urbana y rural por destinación.
La propuesta actual introduce una estructura más gradual basada en el área construida
y en un avalúo ajustado (2026), respetando el tope de la Ley 44
(no se puede cobrar más del doble del impuesto actual al contribuyente).
<br><br>
Este tablero permite:
(1) visualizar dónde se concentran hoy los predios según su avalúo,
(2) analizar la relación entre estrato, avalúo y área construida,
y (3) comparar la tarifa anterior frente a la tarifa propuesta y el efecto
en el impuesto a pagar.
</p>
""",
    unsafe_allow_html=True,
)

# -------------------------------------------------------------------
# 2. CARGA Y PREPARACIÓN DE DATOS
# -------------------------------------------------------------------
@st.cache_data
def load_data(path: str = "MATRIZ PREDIAL_resumida.xlsx") -> pd.DataFrame:
    """
    Lee la hoja MATRIZ, filtra los predios que NO se usan en el análisis
    y crea columnas derivadas para el tablero.
    """
    df = pd.read_excel(path, sheet_name="MATRIZ")

    # Excluir predios marcados como NO
    if "NO" in df.columns:
        df = df[df["NO"] != "NO"].copy()
    else:
        df = df.copy()

    # Mapear clase a zona
    df["zona"] = df["clase"].map({1: "URBANO", 2: "RURAL"}).fillna("SIN CLASE")

    # Estrato como texto (0 lo tratamos como "SIN ESTRATO")
    df["estrato_cat"] = df["ESTRATO"].fillna(0).astype(int).astype(str)
    df["estrato_cat"] = df["estrato_cat"].replace({"0": "SIN ESTRATO"})

    # Rangos de avalúo 2024 (en pesos) usando quantiles para ver concentración
    if df["avaluo2024"].notna().sum() > 0:
        qs = df["avaluo2024"].quantile([0, 0.2, 0.4, 0.6, 0.8, 1]).values
        # Evitar bins duplicados
        qs = np.unique(qs)
        labels = []
        for i in range(len(qs) - 1):
            labels.append(
                f"${qs[i]:,.0f} - ${qs[i+1]:,.0f}".replace(",", ".")
            )
        df["rango_avaluo_2024"] = pd.cut(
            df["avaluo2024"],
            bins=qs,
            labels=labels,
            include_lowest=True,
            duplicates="drop",
        )
    else:
        df["rango_avaluo_2024"] = "SIN AVALUO"

    # Rangos de área construida (basado en los cortes típicos 35 y 70 m2)
    area_bins = [0, 35, 70, 120, np.inf]
    area_labels = [
        "0 - 35 m²",
        "35 - 70 m²",
        "70 - 120 m²",
        "Más de 120 m²",
    ]
    df["rango_area_const"] = pd.cut(
        df["area_const"],
        bins=area_bins,
        labels=area_labels,
        include_lowest=True,
    )

    # Cambio en la TARIFA (milaJe) propuesta vs anterior
    df["cambio_tarifa"] = df["TARIFA PROPUESTA"] - df["tarifa"]
    df["situacion_tarifa"] = np.select(
        [
            df["cambio_tarifa"] < 0,
            df["cambio_tarifa"] == 0,
            df["cambio_tarifa"] > 0,
        ],
        ["Baja tarifa", "Misma tarifa", "Sube tarifa"],
        default="Sin dato",
    )

    # Situación del impuesto (comparando valores monetarios)
    if "DIFERENCIA EN EL VALOR" in df.columns:
        # Se asume DIFERENCIA = IPU_nuevo - IPU_vigente
        df["situacion_ipu"] = np.select(
            [
                df["DIFERENCIA EN EL VALOR"] < 0,
                df["DIFERENCIA EN EL VALOR"] == 0,
                df["DIFERENCIA EN EL VALOR"] > 0,
            ],
            ["Baja IPU", "IPU igual", "Sube IPU"],
            default="Sin dato",
        )
    else:
        df["situacion_ipu"] = "Sin dato"

    return df


try:
    data = load_data()
except FileNotFoundError:
    st.error(
        "No se encontró el archivo 'MATRIZ PREDIAL_resumida.xlsx' en el directorio. "
        "Súbelo al repositorio (misma carpeta que este archivo) y vuelve a ejecutar."
    )
    st.stop()

# -------------------------------------------------------------------
# 3. SIDEBAR (FILTROS)
# -------------------------------------------------------------------
st.sidebar.header("Filtros")

zonas = sorted(data["zona"].dropna().unique().tolist())
zona_sel = st.sidebar.multiselect("Zona", opciones := zonas, default=zonas)

estratos = sorted(data["estrato_cat"].dropna().unique().tolist())
estrato_sel = st.sidebar.multiselect("Estrato", estratos, default=estratos)

destinaciones = sorted(data["DESTINACION"].dropna().unique().tolist())
dest_sel = st.sidebar.multiselect("Destinación", destinaciones, default=destinaciones)

# Rango de avalúo 2024
aval_min = float(data["avaluo2024"].min())
aval_max = float(data["avaluo2024"].max())
aval_rango = st.sidebar.slider(
    "Rango de avalúo 2024 (en pesos)",
    min_value=int(aval_min),
    max_value=int(aval_max),
    value=(int(aval_min), int(aval_max)),
    step=1_000_000,
)

# Rango de área construida
area_min = float(data["area_const"].min())
area_max = float(data["area_const"].max())
area_rango = st.sidebar.slider(
    "Rango de área construida (m²)",
    min_value=float(int(area_min)),
    max_value=float(int(area_max)),
    value=(float(int(area_min)), float(int(area_max))),
)

# Aplicar filtros
df_filt = data.copy()
df_filt = df_filt[df_filt["zona"].isin(zona_sel)]
df_filt = df_filt[df_filt["estrato_cat"].isin(estrato_sel)]
df_filt = df_filt[df_filt["DESTINACION"].isin(dest_sel)]
df_filt = df_filt[
    (df_filt["avaluo2024"] >= aval_rango[0])
    & (df_filt["avaluo2024"] <= aval_rango[1])
]
df_filt = df_filt[
    (df_filt["area_const"] >= area_rango[0])
    & (df_filt["area_const"] <= area_rango[1])
]

st.sidebar.write(f"Predios filtrados: **{len(df_filt):,}**".replace(",", "."))

# -------------------------------------------------------------------
# 4. TABS PRINCIPALES
# -------------------------------------------------------------------
tab_resumen, tab_avaluo, tab_area, tab_estrato, tab_tarifas = st.tabs(
    [
        "📌 Resumen general",
        "💰 Rangos de avalúo actuales",
        "🏠 Área construida (propuesta)",
        "📊 Estrato vs avalúo",
        "📉 Cambio de tarifas",
    ]
)

# -------------------------------------------------------------------
# TAB 1: RESUMEN GENERAL
# -------------------------------------------------------------------
with tab_resumen:
    st.subheader("Resumen general del impacto en el impuesto")

    total_predios = len(df_filt)

    rec_actual = df_filt["VLR_IPU_2025"].sum()
    rec_propuesta = df_filt["IPU LEY 44"].sum()
    delta_recaudo = rec_propuesta - rec_actual

    col1, col2, col3 = st.columns(3)
    col1.metric("Predios analizados", f"{total_predios:,}".replace(",", "."))
    col2.metric(
        "Recaudo actual (VLR_IPU_2025)",
        f"${rec_actual:,.0f}".replace(",", "."),
    )
    col3.metric(
        "Recaudo propuesto (IPU LEY 44)",
        f"${rec_propuesta:,.0f}".replace(",", "."),
        delta=f"${delta_recaudo:,.0f}".replace(",", "."),
    )

    # Gráfico de barras: recaudo actual vs propuesto por zona
    st.markdown("#### Recaudo por zona (actual vs propuesto)")
    agg = (
        df_filt.groupby("zona")[["VLR_IPU_2025", "IPU LEY 44"]]
        .sum()
        .reset_index()
        .melt(id_vars="zona", var_name="Escenario", value_name="Recaudo")
    )

    fig_bar = px.bar(
        agg,
        x="zona",
        y="Recaudo",
        color="Escenario",
        barmode="group",
        labels={"zona": "Zona", "Recaudo": "Recaudo (COP)"},
    )
    fig_bar.update_layout(legend_title_text="")
    st.plotly_chart(fig_bar, use_container_width=True)

    st.markdown(
        """
En esta vista se observa cómo cambia el recaudo total entre el esquema vigente
y el propuesto (aplicando el tope de la Ley 44), diferenciando zona urbana y rural.
"""
    )

# -------------------------------------------------------------------
# TAB 2: RANGOS DE AVALÚO ACTUALES
# -------------------------------------------------------------------
with tab_avaluo:
    st.subheader("Distribución de predios según rangos de avalúo 2024")

    # Conteo por rango de avalúo (torta)
    dist_aval = (
        df_filt.groupby("rango_avaluo_2024")
        .size()
        .reset_index(name="predios")
        .dropna(subset=["rango_avaluo_2024"])
    )

    col_a, col_b = st.columns([2, 1])

    with col_a:
        fig_pie = px.pie(
            dist_aval,
            names="rango_avaluo_2024",
            values="predios",
            title="Predios por rangos de avalúo 2024",
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_b:
        st.dataframe(dist_aval.sort_values("predios", ascending=False))

    st.markdown(
        """
Esta gráfica responde a la pregunta:
**“¿Dónde se encuentran hoy los predios en cuanto a rangos de avalúo?”**  
Permite mostrar la concentración de predios en ciertos niveles de avalúo,
lo que ayuda a justificar la necesidad de un esquema tarifario gradual.
"""
    )

# -------------------------------------------------------------------
# TAB 3: ÁREA CONSTRUIDA (PROPUESTA)
# -------------------------------------------------------------------
with tab_area:
    st.subheader("Distribución de predios según área construida")

    dist_area = (
        df_filt.groupby("rango_area_const")
        .size()
        .reset_index(name="predios")
        .dropna(subset=["rango_area_const"])
    )

    col1, col2 = st.columns([2, 1])

    with col1:
        fig_bar_area = px.bar(
            dist_area,
            x="rango_area_const",
            y="predios",
            labels={"rango_area_const": "Rango de área construida", "predios": "Número de predios"},
        )
        st.plotly_chart(fig_bar_area, use_container_width=True)

    with col2:
        st.dataframe(dist_area.sort_values("predios", ascending=False))

    st.markdown(
        """
La propuesta tarifaria está construida sobre rangos de **área construida**.
Aquí se observa cuántos predios caen en cada rango (por ejemplo 0–35 m²,
35–70 m², etc.), lo que permite sustentar que los cortes escogidos sí
responden a la realidad física del municipio.
"""
    )

# -------------------------------------------------------------------
# TAB 4: ESTRATO VS AVALÚO / ÁREA
# -------------------------------------------------------------------
with tab_estrato:
    st.subheader("Relación entre estrato, avalúo y área construida")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("##### Dispersión avalúo vs estrato")
        fig_scatter_aval = px.scatter(
            df_filt,
            x="avaluo2024",
            y="estrato_cat",
            color="zona",
            labels={
                "avaluo2024": "Avalúo 2024 (COP)",
                "estrato_cat": "Estrato",
            },
        )
        st.plotly_chart(fig_scatter_aval, use_container_width=True)

    with col2:
        st.markdown("##### Dispersión área construida vs estrato")
        fig_scatter_area = px.scatter(
            df_filt,
            x="area_const",
            y="estrato_cat",
            color="zona",
            labels={
                "area_const": "Área construida (m²)",
                "estrato_cat": "Estrato",
            },
        )
        st.plotly_chart(fig_scatter_area, use_container_width=True)

    st.markdown(
        """
Estas gráficas permiten mostrar la **dispersión por estrato** y sirven para
argumentar por qué los mismos rangos de avalúo/área se repiten en los estratos 1 al 3:
la mayoría de predios se concentran en bandas similares, por lo que un esquema escalonado
por área y avalúo resulta más equitativo que uno plano.
"""
    )

# -------------------------------------------------------------------
# TAB 5: CAMBIO DE TARIFAS
# -------------------------------------------------------------------
with tab_tarifas:
    st.subheader("Comparación de tarifa anterior vs tarifa propuesta")

    # Situación de la TARIFA (milaJe)
    dist_tarifa = (
        df_filt.groupby("situacion_tarifa")
        .size()
        .reset_index(name="predios")
        .sort_values("predios", ascending=False)
    )

    col1, col2 = st.columns([2, 1])

    with col1:
        fig_tarifa = px.bar(
            dist_tarifa,
            x="situacion_tarifa",
            y="predios",
            text="predios",
            labels={
                "situacion_tarifa": "Situación de la tarifa",
                "predios": "Número de predios",
            },
        )
        fig_tarifa.update_traces(textposition="outside")
        st.plotly_chart(fig_tarifa, use_container_width=True)

    with col2:
        st.dataframe(dist_tarifa)

    st.markdown(
        """
Aquí se responde directamente a la pregunta:
**“¿A cuántos usuarios les estamos rebajando la tarifa?”**  
Se clasifica cada predio según si su tarifa propuesta (milaJe) **baja, se mantiene
o sube** respecto a la tarifa actual.

> Nota: esta comparación se hace sobre la **tarifa por mil**, no sobre el valor total
del impuesto, que también depende del avalúo y del proindiviso.
"""
    )

    st.markdown("##### Tabla resumida de tarifas por zona y destinación")

    resumen_tarifas = (
        df_filt.groupby(["zona", "DESTINACION"])
        .agg(
            predios=("clase", "size"),
            tarifa_prom_actual=("tarifa", "mean"),
            tarifa_prom_propuesta=("TARIFA PROPUESTA", "mean"),
        )
        .reset_index()
    )
    st.dataframe(resumen_tarifas)

    st.markdown(
        """
Esta tabla permite mostrar, por zona y tipo de destinación, cómo se mueven en promedio
las tarifas entre el esquema anterior y la propuesta, útil para sustentar que la carga
fiscal se redistribuye de forma más alineada con el uso del suelo.
"""
    )
