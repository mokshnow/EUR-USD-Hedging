import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy.stats import norm

st.set_page_config(
    page_title="EURC/USDC Hedging Simulator",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -----------------------------------------------------------------------------
# Math
# -----------------------------------------------------------------------------

@st.cache_data
def garman_kohlhagen(S, K, t, r_d, r_f, sigma, option_type="put"):
    # using garman kohlhagen to price currency options
    if t <= 0:
        price = max(0.0, K - S) if option_type == "put" else max(0.0, S - K)
        return price, 0.0, 0.0, 0.0, 0.0

    d1 = (np.log(S / K) + (r_d - r_f + 0.5 * sigma ** 2) * t) / (sigma * np.sqrt(t))
    d2 = d1 - sigma * np.sqrt(t)

    gamma = (np.exp(-r_f * t) * norm.pdf(d1)) / (S * sigma * np.sqrt(t))
    vega = S * np.exp(-r_f * t) * np.sqrt(t) * norm.pdf(d1)

    if option_type == "put":
        price = K * np.exp(-r_d * t) * norm.cdf(-d2) - S * np.exp(-r_f * t) * norm.cdf(-d1)
        delta = -np.exp(-r_f * t) * norm.cdf(-d1)
        theta = (- (S * sigma * np.exp(-r_f * t) * norm.pdf(d1)) / (2 * np.sqrt(t)) 
                 - r_f * S * np.exp(-r_f * t) * norm.cdf(-d1) 
                 + r_d * K * np.exp(-r_d * t) * norm.cdf(-d2))
    else:  
        price = S * np.exp(-r_f * t) * norm.cdf(d1) - K * np.exp(-r_d * t) * norm.cdf(d2)
        delta = np.exp(-r_f * t) * norm.cdf(d1)
        theta = (- (S * sigma * np.exp(-r_f * t) * norm.pdf(d1)) / (2 * np.sqrt(t)) 
                 + r_f * S * np.exp(-r_f * t) * norm.cdf(d1) 
                 - r_d * K * np.exp(-r_d * t) * norm.cdf(d2))

    return price, delta, gamma, vega, theta

@st.cache_data
def calculate_option_payoff(future_spot, strike, option_type, premium, r_d, t, exposure):
    if option_type == 'put':
        return exposure * future_spot + exposure * np.maximum(0, strike - future_spot) - (premium * np.exp(r_d * t))
    elif option_type == 'collar':
        put_strike, call_strike, net_cost = strike
        return (exposure * future_spot 
                + exposure * np.maximum(0, put_strike - future_spot) 
                - exposure * np.maximum(0, future_spot - call_strike) 
                - (net_cost * np.exp(r_d * t)))

# -----------------------------------------------------------------------------
# Sidebar
# -----------------------------------------------------------------------------

st.sidebar.header("Market Parameters")

exposure = st.sidebar.number_input("EURC Exposure (€)", min_value=50000000, value=100000000, step=1000000, format="%d")
spot_rate = st.sidebar.slider("Spot Rate (EUR/USD)", 0.9000, 1.2000, 1.0850, step=0.0005, format="%.4f")
volatility = st.sidebar.slider("FX IV (%)", 2.0, 20.0, 7.5, step=0.1) / 100.0
days_to_mat = st.sidebar.number_input("Days to Maturity", min_value=1, max_value=365, value=90, step=1)
t = days_to_mat / 365.0

st.sidebar.markdown("---")
st.sidebar.header("Interest Rates")
r_usd = st.sidebar.slider("USD Risk-Free Rate", 0.0, 8.0, 4.50, step=0.05) / 100.0
r_eur = st.sidebar.slider("EUR Risk-Free Rate", 0.0, 8.0, 3.25, step=0.05) / 100.0

st.sidebar.markdown("---")
st.sidebar.header("Hedging Parameters")
forward_rate = spot_rate * np.exp((r_usd - r_eur) * t)

# FIXED: Replaced invalid st.sidebar.disabled with the disabled kwarg
st.sidebar.text_input("Fair Forward Rate (Calculated)", f"{forward_rate:.4f}", disabled=True)

put_strike = st.sidebar.slider("Put Strike", 0.9500, 1.1500, 1.0700, step=0.0005, format="%.4f")
call_strike = st.sidebar.slider("Call Strike", 1.0000, 1.2500, 1.1000, step=0.0005, format="%.4f")

# -----------------------------------------------------------------------------
# Calculations
# -----------------------------------------------------------------------------

st.title("EURC/USD Hedging Simulator")
st.markdown("Using Currency Options to Hedge FX Risk")

# FIXED: Unpacking all Greeks for both options to properly calculate Net Collar metrics
put_price_per_unit, p_delta, p_gamma, p_vega, p_theta = garman_kohlhagen(spot_rate, put_strike, t, r_usd, r_eur, volatility, "put")
call_price_per_unit, c_delta, c_gamma, c_vega, c_theta = garman_kohlhagen(spot_rate, call_strike, t, r_usd, r_eur, volatility, "call")

total_put_cost = put_price_per_unit * exposure
total_call_credit = call_price_per_unit * exposure
net_collar_cost = total_put_cost - total_call_credit

z_score = 1.645
daily_vol = volatility / np.sqrt(252)
var_95_usd = exposure * spot_rate * z_score * daily_vol * np.sqrt(days_to_mat)

m1, m2, m3, m4 = st.columns(4)
with m1:
    st.metric("Base Portfolio Value (USD)", f"${exposure * spot_rate:,.2f}")
with m2:
    st.metric(f"95% Unhedged VaR ({days_to_mat}-Day Horizon)", f"${var_95_usd:,.2f}")
with m3:
    st.metric("Protective Put Premium Cost", f"${total_put_cost:,.2f}", 
              help="Upfront cash outlay required to establish the price floor.")
with m4:
    collar_status = "Zero-Cost" if abs(net_collar_cost) < 5000 else f"${net_collar_cost:,.2f}"
    st.metric("Net Collar Premium Structure Cost", collar_status,
              help="Negative means net credit received by treasury.")

# -----------------------------------------------------------------------------
# Graph
# -----------------------------------------------------------------------------

s_future = np.linspace(1.00, 1.16, 200)

unhedged_val = exposure * s_future
forward_val = np.full_like(s_future, exposure * forward_rate)
put_val = exposure * s_future + exposure * np.maximum(0, put_strike - s_future) - (total_put_cost * np.exp(r_usd * t))
collar_val = (exposure * s_future 
              + exposure * np.maximum(0, put_strike - s_future) 
              - exposure * np.maximum(0, s_future - call_strike) 
              - (net_collar_cost * np.exp(r_usd * t)))

fig = go.Figure()

fig.add_trace(go.Scatter(x=s_future, y=unhedged_val, name="Unhedged", line=dict(color="#E5E7EB", width=2, dash="dash")))
fig.add_trace(go.Scatter(x=s_future, y=forward_val, name="Forward", line=dict(color="#3B82F6", width=2.5)))
fig.add_trace(go.Scatter(x=s_future, y=put_val, name="Protective Put", line=dict(color="#10B981", width=2.5)))
fig.add_trace(go.Scatter(x=s_future, y=collar_val, name="Collar", line=dict(color="#8B5CF6", width=2.5)))

fig.add_vline(x=spot_rate, line_width=1.5, line_dash="dot", line_color="#EF4444")
fig.add_annotation(
    x=spot_rate, 
    y=exposure*spot_rate, 
    text="Current Spot", 
    showarrow=True, 
    arrowhead=1, 
    ax=40, 
    ay=-40, 
    bgcolor="#EF4444", 
    font=dict(color="white")
)

fig.update_layout(
    title="EURC Exposure at Various Spot Rates",
    xaxis_title="Future EUR/USD",
    yaxis_title="Total Position Value (USD)",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    hovermode="x unified",
    margin=dict(l=20, r=20, t=60, b=20),
    height=550
)

st.plotly_chart(fig, use_container_width=True)

# -----------------------------------------------------------------------------
# Downside
# -----------------------------------------------------------------------------

st.markdown("---")
st.markdown("### Downside Protection")

downside_spot = st.slider("Spot Rate", 0.8500, spot_rate, spot_rate * 0.95, step=0.0050, format="%.4f")

unhedged_downside = exposure * downside_spot
forward_downside = exposure * forward_rate
put_downside = calculate_option_payoff(downside_spot, put_strike, 'put', total_put_cost, r_usd, t, exposure)
collar_downside = calculate_option_payoff(downside_spot, (put_strike, call_strike, net_collar_cost), 'collar', 0, r_usd, t, exposure)

unhedged_loss = (exposure * spot_rate) - unhedged_downside

downside_df = pd.DataFrame({
    "Strategy": ["Unhedged", "Forward", "Protective Put", "Collar"],
    "Initial Premium Cost ($)": ["$0", "$0", f"${total_put_cost:,.0f}", f"${net_collar_cost:,.0f}"],
    "Value at Downside ($)": [f"${unhedged_downside:,.0f}", f"${forward_downside:,.0f}", f"${put_downside:,.0f}", f"${collar_downside:,.0f}"],
    "Net Downside Protection ($)": [
        f"${unhedged_loss:,.0f}  (Loss)",
        f"${(forward_downside - unhedged_downside):,.0f}",
        f"${(put_downside - unhedged_downside):,.0f}",
        f"${(collar_downside - unhedged_downside):,.0f}"
    ]
})

st.dataframe(downside_df, use_container_width=True, hide_index=True)

# -----------------------------------------------------------------------------
# Sensitivity and Greeks
# -----------------------------------------------------------------------------

st.markdown("---")
st.markdown("### Position Greeks")

g1, g2, g3, g4 = st.columns(4)

with g1:
    st.markdown("**Delta**")
    st.caption("Sensitivity to FX Rates")
    st.metric("Protective Put", f"{(1 + p_delta):.4f}")
    st.metric("Collar", f"{(1 + p_delta - c_delta):.4f}")

with g2:
    st.markdown("**Gamma**")
    st.caption("Slope of Delta")
    st.metric("Protective Put", f"{p_gamma:.4f}")
    # FIXED: Replaced (gamma - gamma) with (p_gamma - c_gamma)
    st.metric("Collar", f"{(p_gamma - c_gamma):.4f}")

with g3:
    st.markdown("**Vega**")
    st.caption("Sensitivity to Volatility")
    st.metric("Protective Put", f"${(p_vega * exposure / 100):,.2f}")
    # FIXED: Replaced (vega - vega) with (p_vega - c_vega)
    st.metric("Collar", f"${((p_vega - c_vega) * exposure / 100):,.2f}")

with g4:
    st.markdown("**Theta**")
    st.caption("Time Decay")
    st.metric("Protective Put", f"${(p_theta * exposure / 365):,.2f}")
    st.metric("Collar", f"${((p_theta - c_theta) * exposure / 365):,.2f}")

# -----------------------------------------------------------------------------
# Data
# -----------------------------------------------------------------------------

st.markdown("---")
with st.expander("View Scenario Data"):
    df_scenarios = pd.DataFrame({
        "Future Spot Price": s_future,
        "Unhedged ($)": unhedged_val,
        "Forward ($)": forward_val,
        "Protective Put ($)": put_val,
        "Collar ($)": collar_val
    }).round(2)
    st.dataframe(df_scenarios, use_container_width=True)