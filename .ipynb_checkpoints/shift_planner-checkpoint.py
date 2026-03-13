import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(layout="wide")
st.title("Shift Planner – Vertical Grid for Director")

# --- Загрузка CSV ---
uploaded = st.file_uploader("Upload shifts CSV", type="csv")
if uploaded:
    df = pd.read_csv(uploaded)
else:
    df = pd.read_csv("shifts.csv")  # файл по умолчанию

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
start_hour = int(df['start'].min())
end_hour = int((df['start'] + df['duration']).max())
hours = list(range(start_hour, end_hour + 1))

num_positions = filtered.shape[0]

# создаём пустую сетку: строки = часы, колонки = позиции сотрудников
grid = pd.DataFrame("", index=hours, columns=[f"Position {i+1}" for i in range(num_positions)])

# заполняем сетку сменами (имя пока пустое, но ячейки видны)
for i, row in filtered.iterrows():
    for h in range(row['start'], row['start'] + row['duration']):
        if h in hours:
            grid.iloc[hours.index(h), i] = row['name']

st.subheader("Shift Grid (Time × Positions)")

# --- Редактируемая таблица для директора ---
edited_grid = st.data_editor(grid, use_container_width=True)

# --- Экспорт CSV ---
export_csv = edited_grid.reset_index().rename(columns={"index": "hour"}).to_csv(index=False)
st.download_button("Download Updated Shifts CSV", export_csv, "updated_shifts.csv", "text/csv")