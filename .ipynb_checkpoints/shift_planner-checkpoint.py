import streamlit as st
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(layout="wide")
st.title("Planner of Shifts")

# --- Загрузка CSV ---
uploaded = st.file_uploader("Upload shifts CSV", type="csv")
if uploaded:
    df = pd.read_csv(uploaded)
else:
    df = pd.read_csv("shifts.csv")

# --- Разворачиваем count в отдельные смены ---
df = df.loc[df.index.repeat(df['count'])].reset_index(drop=True)

if "name" not in df.columns:
    df["name"] = ""

df["end"] = df["start"] + df["duration"]

# --- Фильтры ---
col1, col2 = st.columns(2)
selected_date = col1.selectbox("Date", sorted(df["date"].unique()))
selected_store = col2.selectbox("Store", sorted(df["id_store"].unique()))

filtered = df[(df.date == selected_date) & (df.id_store == selected_store)].copy()
filtered["shift_index"] = range(len(filtered))

# --- Редактирование сотрудников ---
st.subheader("Assign Employees")
edited = st.data_editor(
    filtered,
    column_config={
        "name": st.column_config.TextColumn("Employee"),
        "start": st.column_config.NumberColumn("Start"),
        "duration": st.column_config.NumberColumn("Duration")
    },
    use_container_width=True
)

edited["end"] = edited["start"] + edited["duration"]

# --- Построение сетки времени ---
st.subheader("Shift Grid")
fig = go.Figure()

for _, row in edited.iterrows():
    fig.add_shape(
        type="rect",
        x0=row["shift_index"],
        x1=row["shift_index"] + 0.9,
        y0=row["start"],
        y1=row["end"],
        line=dict(color="black"),
        fillcolor="lightblue"
    )
    fig.add_annotation(
        x=row["shift_index"] + 0.45,
        y=(row["start"] + row["end"]) / 2,
        text=row["name"],
        showarrow=False
    )

fig.update_yaxes(autorange="reversed", title="Hour")
fig.update_xaxes(title="Shift Index")
fig.update_layout(height=700)
st.plotly_chart(fig, use_container_width=True)

# --- Экспорт CSV ---
st.download_button(
    "Download updated shifts",
    edited.to_csv(index=False),
    file_name="updated_shifts.csv",
    mime="text/csv"
)