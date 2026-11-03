import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Configuración de página
st.set_page_config(
    page_title="Simulador de Demanda de Combustibles Lima",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ----------------- CONSTANTES BASE HISTÓRICAS (Marzo 2023, m=0) -----------------
# Referencias fijas congeladas para normalización de logaritmos
R0 = 1.095185          # Relación base PP/PR en marzo 2023
PR0_REAL = 15.691738   # Precio real base de Regular en marzo 2023 (S//gal de dic-2021)
IPC0 = 110.39          # IPC oficial de Lima en marzo 2023

# Parámetros estructurales de la Ecuación de Volumen Total (w)
RHO_W = 0.4090
A_W = 13.2968
C_W = -0.9816
B_W = -0.3214
LAMBDA_W = 0.025123

# Parámetros estructurales de Participación (z): Especificación restringida (delta = 0)
RHO_Z_D0 = 0.9231
ALPHA_D0 = -0.7017
BETA_D0 = 19.8371
DELTA_D0 = 0.0
LAMBDA_Z_D0 = 0.001895

# Parámetros estructurales de Participación (z): Especificación general (delta libre)
RHO_Z_DL = 0.4187
ALPHA_DL = -0.5346
BETA_DL = 2.4000
DELTA_DL = 0.9107
LAMBDA_Z_DL = 0.024510

# Puntos de partida históricos registrados en la base
DATOS_HISTORICOS = {
    "Cierre de Entrenamiento (Junio 2025)": {
        "pr": 14.9484, "pp": 16.3732, "ipc": 115.66,
        "z": -0.698295, "w": 13.333344,
        "qr": 205109.0, "qp": 412335.0, "t": 617444.0, "s": 0.332190,
        "fecha_inicio": "2025-06-01"
    },
    "Último Mes Histórico Registrado (Diciembre 2025)": {
        "pr": 14.0446, "pp": 15.2791, "ipc": 115.89,
        "z": -0.811414, "w": 13.490345,
        "qr": 222205.0, "qp": 500203.0, "t": 722408.0, "s": 0.307589,
        "fecha_inicio": "2025-12-01"
    }
}

# Diccionario de meses en español
MESES_ES = {
    "01": "Ene", "02": "Feb", "03": "Mar", "04": "Abr",
    "05": "May", "06": "Jun", "07": "Jul", "08": "Ago",
    "09": "Set", "10": "Oct", "11": "Nov", "12": "Dic"
}

# ----------------- PANEL LATERAL: CONTROLES INTERACTIVOS -----------------
st.sidebar.title("🎛️ Panel de Simulación")

st.sidebar.markdown("### 1. Especificación Econométrica")
modelo_sel = st.sidebar.radio(
    "Modelo de Participación:",
    ["General (δ libre - Recomendado)", "Parsimoniosa (δ = 0)"],
    help="El modelo general incluye el efecto del precio real sobre la cuota; el restringido solo evalúa el precio relativo."
)

if "libre" in modelo_sel:
    rho_z, alpha_z, beta_z, delta_z, lambda_z = RHO_Z_DL, ALPHA_DL, BETA_DL, DELTA_DL, LAMBDA_Z_DL
    st.sidebar.caption("📊 Ajuste: R² = 91.58% | AICc = -210.02 | MAE = 0.375 p.p.")
else:
    rho_z, alpha_z, beta_z, delta_z, lambda_z = RHO_Z_D0, ALPHA_D0, BETA_D0, DELTA_D0, LAMBDA_Z_D0
    st.sidebar.caption("📊 Ajuste: R² = 84.42% | AICc = -196.18 | MAE = 0.812 p.p.")

st.sidebar.markdown("---")
st.sidebar.markdown("### 2. Punto de Partida de la Simulación")
origen_sel = st.sidebar.selectbox(
    "Estado Inicial:",
    list(DATOS_HISTORICOS.keys()),
    index=1  # Por defecto inicia en Dic-2025 para proyectar de inmediato hacia 2026
)

base = DATOS_HISTORICOS[origen_sel]

st.sidebar.markdown("---")
st.sidebar.markdown("### 3. Modalidad de Escenario")
modo_escenario = st.sidebar.selectbox(
    "Selecciona cómo ingresar los datos:",
    [
        "Proyección Hacia 2026-2027 (Valores Directos)",
        "Choque Porcentual sobre el Estado Base (+% Precios)",
        "Escenario Macroeconómico (Inflación Anual y Spread)"
    ]
)

if modo_escenario == "Proyección Hacia 2026-2027 (Valores Directos)":
    st.sidebar.caption("Ingresa directamente los precios esperados en grifo y el nivel del IPC:")
    pr_input = st.sidebar.number_input(
        "Precio Regular PR (S//gal):",
        min_value=10.0, max_value=30.0, value=float(base["pr"]), step=0.10
    )
    pp_input = st.sidebar.number_input(
        "Precio Premium PP (S//gal):",
        min_value=10.0, max_value=35.0, value=float(base["pp"]), step=0.10
    )
    ipc_input = st.sidebar.number_input(
        "Nivel IPC Lima Metropolitana:",
        min_value=100.0, max_value=160.0, value=float(base["ipc"]), step=0.50,
        help="Nivel del índice publicado por INEI/BCRP (Base dic-2021 = 100)."
    )
    meses_proy = st.sidebar.slider("Meses a simular hacia adelante:", 6, 36, 12)

elif modo_escenario == "Choque Porcentual sobre el Estado Base (+% Precios)":
    st.sidebar.caption(f"Aplica variaciones respecto a los valores de {origen_sel[:15]}:")
    pct_pr = st.sidebar.slider("Variación en Regular PR (%):", -25.0, 40.0, 0.0, 1.0)
    pct_pp = st.sidebar.slider("Variación en Premium PP (%):", -25.0, 40.0, 10.0, 1.0)
    
    st.sidebar.markdown("**Inflación esperada:**")
    tipo_ipc_pct = st.sidebar.radio("Definir IPC mediante:", ["Variación % sobre la base", "Ingresar IPC directo"], horizontal=True)
    if tipo_ipc_pct == "Variación % sobre la base":
        pct_ipc = st.sidebar.slider("Variación en IPC (%):", -5.0, 25.0, 2.5, 0.5)
        ipc_input = base["ipc"] * (1.0 + pct_ipc / 100.0)
    else:
        ipc_input = st.sidebar.number_input("Nivel IPC directo:", 100.0, 160.0, float(base["ipc"]), 0.5)

    pr_input = base["pr"] * (1.0 + pct_pr / 100.0)
    pp_input = base["pp"] * (1.0 + pct_pp / 100.0)
    meses_proy = st.sidebar.slider("Meses a simular:", 6, 36, 12)

else:  # Escenario Macroeconómico
    st.sidebar.caption("Proyección basada en expectativas de inflación y diferencial de comercialización:")
    inflacion_anual = st.sidebar.slider("Tasa de Inflación Anual Esperada (%):", 1.0, 8.0, 3.2, 0.1)
    alza_combustibles = st.sidebar.slider("Variación Anual en Precios Combustibles (%):", -10.0, 20.0, 3.5, 0.5)
    spread = st.sidebar.slider("Diferencial en Grifo (PP - PR en S//gal):", 0.5, 3.5, float(base["pp"] - base["pr"]), 0.05)
    meses_proy = st.sidebar.slider("Meses a simular hacia 2026-2027:", 6, 36, 18)

    pr_input = base["pr"] * (1.0 + alza_combustibles / 100.0)
    pp_input = pr_input + spread
    ipc_input = base["ipc"] * (1.0 + inflacion_anual / 100.0)

# ----------------- MOTOR MATEMÁTICO -----------------
# 1. Variables exógenas normalizadas respecto a Marzo 2023
r_val = pp_input / pr_input
pr_real_val = 100.0 * pr_input / ipc_input
u_val = np.log(r_val / R0)
v_val = np.log(pr_real_val / PR0_REAL)

# 2. Objetivos de equilibrio de largo plazo (estado deseado)
z_star = alpha_z + beta_z * u_val + delta_z * v_val
w_star = A_W + C_W * u_val + B_W * v_val

s_star = 1.0 / (1.0 + np.exp(-z_star))
T_star = np.exp(w_star)
qR_star = T_star * s_star
qP_star = T_star * (1.0 - s_star)

# 3. Elasticidades cruzadas y derivadas parciales de equilibrio
eps_RP = C_W + beta_z * (1.0 - s_star)
eps_PR = B_W - C_W + s_star * (beta_z - delta_z)
dqR_dPP = (qR_star / pp_input) * eps_RP
dqP_dPR = (qP_star / pr_input) * eps_PR

# 4. Simulación temporal mes a mes (Ecuaciones en diferencias con inercia)
z_hist = [base["z"]]
w_hist = [base["w"]]

for m in range(1, meses_proy + 1):
    z_hist.append(rho_z * z_hist[-1] + (1.0 - rho_z) * z_star)
    w_hist.append(RHO_W * w_hist[-1] + (1.0 - RHO_W) * w_star)

z_arr = np.array(z_hist)
w_arr = np.array(w_hist)
s_traj = 1.0 / (1.0 + np.exp(-z_arr))
T_traj = np.exp(w_arr)
qR_traj = T_traj * s_traj
qP_traj = T_traj * (1.0 - s_traj)

# Fechas formateadas en español
fechas_dt = pd.date_range(start=base["fecha_inicio"], periods=meses_proy + 1, freq="MS")
fechas_label = [f"{MESES_ES[d.strftime('%m')]} {d.strftime('%Y')}" for d in fechas_dt]

# ----------------- PANEL PRINCIPAL -----------------
st.title("⛽ Simulador Dinámico: Gasohol Regular vs. Premium")
st.markdown(f"""
*Mercado Minorista de Combustibles en Lima Metropolitana (SCOP / OSINERGMIN).*  
Simulación de trayectorias prospectivas y elasticidad cruzada proyectada desde **{fechas_label[0]}** hasta **{fechas_label[-1]}**.
""")

# Tarjetas KPI de resultados
col1, col2, col3, col4 = st.columns(4)
col1.metric(
    "Participación Regular (s*)",
    f"{s_star * 100:.2f} %",
    f"{(s_star - base['s']) * 100:+.2f} p.p."
)
col2.metric(
    "Volumen Total Mercado (T*)",
    f"{T_star:,.0f} gal/día",
    f"{(T_star - base['t']):+,.0f} gal/d"
)
col3.metric(
    "Despacho Regular (qR*)",
    f"{qR_star:,.0f} gal/día",
    f"{(qR_star - base['qr']):+,.0f} gal/d"
)
col4.metric(
    "Despacho Premium (qP*)",
    f"{qP_star:,.0f} gal/día",
    f"{(qP_star - base['qp']):+,.0f} gal/d"
)

st.markdown("---")

# Pestañas de análisis
tab1, tab2, tab3 = st.tabs([
    "📈 Simulación Temporal de Proyección",
    "⚖️ Elasticidades y Derivadas Cruzadas",
    "📋 Tabla de Despachos Mes a Mes"
])

with tab1:
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=("Proyección de Despachos Físicos (galones/día)", "Evolución de la Cuota de Mercado (%)")
    )
    # Curvas de volumen físico
    fig.add_trace(go.Scatter(x=fechas_label, y=qR_traj, name="Gasohol Regular (qR)", line=dict(color="#1f77b4", width=3)), row=1, col=1)
    fig.add_trace(go.Scatter(x=fechas_label, y=qP_traj, name="Gasohol Premium (qP)", line=dict(color="#ff7f0e", width=3)), row=1, col=1)
    fig.add_trace(go.Scatter(x=fechas_label, y=T_traj, name="Total Mercado (T)", line=dict(color="#2ca02c", width=2, dash="dash")), row=1, col=1)

    # Curvas de cuota de mercado
    fig.add_trace(go.Scatter(x=fechas_label, y=s_traj * 100, name="% Regular", line=dict(color="#1f77b4", width=3)), row=1, col=2)
    fig.add_trace(go.Scatter(x=fechas_label, y=(1.0 - s_traj) * 100, name="% Premium", line=dict(color="#ff7f0e", width=3)), row=1, col=2)

    fig.update_layout(height=480, hovermode="x unified", legend=dict(orientation="h", y=-0.15))
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Sensibilidades Numéricas de Equilibrio")
        st.write(f"**Elasticidad Cruzada Regular ante Premium (ε*RP):** `{eps_RP:+.4f}`")
        st.write(f"**Elasticidad Cruzada Premium ante Regular (ε*PR):** `{eps_PR:+.4f}`")
        st.write(f"**Derivada Parcial ∂qR*/∂PP:** `{dqR_dPP:+,.2f} galones/día por cada S//galón`")
        st.write(f"**Derivada Parcial ∂qP*/∂PR:** `{dqP_dPR:+,.2f} galones/día por cada S//galón`")

    with col_b:
        st.subheader("Diagnóstico Económico y Variables Base")
        if dqR_dPP > 0 and dqP_dPR > 0:
            st.success("✅ **Bienes Sustitutos Brutos:** El aumento de precio en un carburante expande los galones demandados del competidor.")
        else:
            st.warning("⚠️ Signos contradictorios o régimen de complementariedad bajo este vector extremo de precios.")

        st.info(f"""
        * **Precio Relativo Actual (PP/PR):** {r_val:.4f} (Base Mar-2023 r₀ = {R0:.4f})
        * **Precio Real de Regular:** S/ {pr_real_val:.2f} (Base Mar-2023 pR₀ = S/ {PR0_REAL:.2f})
        * **IPC Ingresado:** {ipc_input:.2f} (Base Mar-2023 IPC₀ = {IPC0:.2f})
        * **Variables Exógenas:** u = {u_val:+.4f} | v = {v_val:+.4f}
        """)

with tab3:
    df_proy = pd.DataFrame({
        "Mes": fechas_label,
        "Gasohol Regular (gal/día)": np.round(qR_traj, 0).astype(int),
        "Gasohol Premium (gal/día)": np.round(qP_traj, 0).astype(int),
        "Total Mercado (gal/día)": np.round(T_traj, 0).astype(int),
        "Cuota Regular (%)": np.round(s_traj * 100, 2),
        "Cuota Premium (%)": np.round((1.0 - s_traj) * 100, 2)
    })
    st.dataframe(df_proy, use_container_width=True)
    st.download_button(
        "📥 Descargar Proyección Completa en CSV / Excel",
        df_proy.to_csv(index=False),
        "proyeccion_combustibles_lima.csv",
        "text/csv"
    )