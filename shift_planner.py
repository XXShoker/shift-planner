import streamlit as st
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(layout="wide")
st.title("Shift Planner – Goodtime Style")

# --- Загружаем CSV ---
uploaded = st.file_uploader("Upload shifts CSV", type="csv")
if uploaded:
    df = pd.read_csv(uploaded)
else:
    df = pd.read_csv("shifts.csv")  # ваш файл по умолчанию

# --- Разворачиваем count на позиции ---
df = df.loc[df.index.repeat(df['count'])].reset_index(drop=True)
if "name" not in df.columns:
    df["name"] = ""

# --- Фильтры ---
col1, col2 = st.columns(2)
selected_date = col1.selectbox("Date", sorted(df["date"].unique()))
selected_store = col2.selectbox("Store", sorted(df["id_store"].unique()))

filtered = df[(df.date == selected_date) & (df.id_store == selected_store)].copy()
filtered.reset_index(drop=True, inplace=True)

# --- Создаём Gantt-подобные блоки ---
fig = go.Figure()

for i, row in filtered.iterrows():
    # каждая смена = колонка i
    fig.add_trace(go.Bar(
        x=[f"Shift {i+1}"],  # колонка смены
        y=[row['duration']],  # высота = продолжительность
        base=row['start'],     # начало смены
        text=[row['name'] if row['name'] else ""],
        textposition='inside',
        marker_color='lightsalmon',
        width=0.5,
        orientation='v',
        hovertemplate="Start: %{base}:00<br>Duration: %{y}h<br>Name: %{text}<extra></extra>"
    ))

fig.update_layout(
    yaxis=dict(title="Hour", autorange='reversed', dtick=1),
    xaxis=dict(title="Shifts"),
    barmode='overlay',
    height=600
)

st.subheader("Shift Blocks – Fill names inside blocks")

st.plotly_chart(fig, use_container_width=True)

# --- Редактируемая таблица для CSV экспорта ---
edited_df = st.data_editor(filtered[['start','duration','name']], use_container_width=True)

csv = edited_df.to_csv(index=False)
st.download_button("Download Updated Shifts CSV", csv, "updated_shifts.csv", "text/csv")
