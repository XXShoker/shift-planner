import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(layout="wide")
st.title("Shift Planner – Goodtime style")

# --- Загрузка CSV ---
uploaded = st.file_uploader("Upload shifts CSV", type="csv")
if uploaded:
    df = pd.read_csv(uploaded)
else:
    df = pd.read_csv("shifts.csv")

# --- Разворачиваем count на отдельные позиции ---
df = df.loc[df.index.repeat(df['count'])].reset_index(drop=True)
if "name" not in df.columns:
    df["name"] = ""

# --- Фильтры ---
col1, col2 = st.columns(2)
selected_date = col1.selectbox("Select Date", sorted(df["date"].unique()))
selected_store = col2.selectbox("Select Store", sorted(df["id_store"].unique()))

filtered = df[(df.date == selected_date) & (df.id_store == selected_store)].copy()
filtered.reset_index(drop=True, inplace=True)

# --- Настройка сетки времени ---
start_hour = 6
end_hour = 22
hours = list(range(start_hour, end_hour+1))

num_positions = filtered.shape[0]

# создаём пустую сетку: строки = часы, колонки = позиции
grid = pd.DataFrame("", index=hours, columns=[f"Shift {i+1}" for i in range(num_positions)])

# заполняем сетку текущими именами
for i, row in filtered.iterrows():
    for h in range(row['start'], row['start'] + row['duration']):
        if h in hours:
            grid.iloc[hours.index(h), i] = row['name']

st.subheader("Shift Grid (Time × Positions)")

# --- Редактируемая таблица для директора ---
edited_grid = st.data_editor(grid, use_container_width=True)

# --- Кнопка экспорт ---
export_csv = edited_grid.reset_index().rename(columns={"index": "hour"}).to_csv(index=False)
st.download_button("Download Updated Shifts CSV", export_csv, "updated_shifts.csv", "text/csv")