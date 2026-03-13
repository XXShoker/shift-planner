import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np

st.set_page_config(layout="wide")
st.title("Shift Planner – GoodTime Style")

# --- Загружаем CSV ---
uploaded = st.file_uploader("Upload shifts CSV", type="csv")
if uploaded:
    df = pd.read_csv(uploaded)
else:
    # Создаем пример данных, если файл не загружен
    data = {
        'date': ['2024-01-15', '2024-01-15', '2024-01-15', '2024-01-15'],
        'id_store': ['Store A', 'Store A', 'Store A', 'Store A'],
        'start': [9, 10, 14, 15],
        'duration': [8, 8, 6, 6],
        'count': [1, 1, 2, 1],
        'name': ['John', 'Sarah', 'Mike', 'Emma']
    }
    df = pd.DataFrame(data)

# --- Разворачиваем count на позиции ---
df = df.loc[df.index.repeat(df['count'])].reset_index(drop=True)
if "name" not in df.columns:
    df["name"] = ""

# --- Фильтры ---
col1, col2, col3 = st.columns(3)
selected_date = col1.selectbox("Date", sorted(df["date"].unique()))
selected_store = col2.selectbox("Store", sorted(df["id_store"].unique()))

filtered = df[(df.date == selected_date) & (df.id_store == selected_store)].copy()
filtered.reset_index(drop=True, inplace=True)

# --- Создаем временные слоты для оси Y (сверху вниз) ---
hours = list(range(24))  # 0-24 часа
hour_labels = [f"{h:02d}:00" for h in hours]

# --- Создаем Gantt-подобные блоки (вертикальное расположение) ---
fig = go.Figure()

# Цвета для разных сотрудников
colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8']

for i, row in filtered.iterrows():
    start_hour = row['start']
    end_hour = start_hour + row['duration']
    
    # Создаем вертикальный блок смены
    fig.add_trace(go.Scatter(
        x=[i, i, i, i],  # X позиция для каждой смены
        y=[start_hour, end_hour, end_hour, start_hour],  # Y координаты (время)
        fill='toself',
        fillcolor=colors[i % len(colors)],
        line=dict(color='rgba(255,255,255,0.8)', width=2),
        mode='lines',
        name=f"Shift {i+1}",
        text=[f"{row['name']}<br>{start_hour}:00 - {end_hour}:00" 
              if row['name'] else f"Shift {i+1}<br>{start_hour}:00 - {end_hour}:00"],
        hoverinfo='text',
        showlegend=False
    ))
    
    # Добавляем текст внутри блока
    fig.add_annotation(
        x=i,
        y=(start_hour + end_hour) / 2,
        text=row['name'] if row['name'] else f"Shift {i+1}",
        showarrow=False,
        font=dict(size=12, color='white', family='Arial Black'),
        bgcolor='rgba(0,0,0,0.5)',
        bordercolor='white',
        borderwidth=1,
        borderpad=4
    )

# Настройка макета
fig.update_layout(
    title=f"Shift Schedule - {selected_store} - {selected_date}",
    xaxis=dict(
        title="Shifts",
        tickmode='array',
        tickvals=list(range(len(filtered))),
        ticktext=[f"Shift {i+1}" for i in range(len(filtered))],
        gridcolor='lightgray',
        showgrid=True
    ),
    yaxis=dict(
        title="Time",
        tickmode='array',
        tickvals=hours,
        ticktext=hour_labels,
        range=[24, 0],  # Инвертируем ось, чтобы 0:00 было сверху
        gridcolor='lightgray',
        showgrid=True,
        dtick=1
    ),
    plot_bgcolor='rgba(240,240,240,0.3)',
    height=700,
    margin=dict(l=80, r=20, t=80, b=40),
    hovermode='closest'
)

# Добавляем разделители между сменами
for i in range(len(filtered) + 1):
    fig.add_vline(x=i - 0.5, line_width=1, line_color='gray', line_dash='dash')

st.plotly_chart(fig, use_container_width=True)

# --- Информация о сменах ---
st.subheader("📋 Shift Details")
col1, col2, col3, col4, col5 = st.columns(5)

for i, row in filtered.iterrows():
    with eval(f"col{(i % 5) + 1}"):
        end_time = row['start'] + row['duration']
        color = colors[i % len(colors)]
        st.markdown(
            f"""
            <div style="background-color: {color}20; padding: 10px; border-radius: 5px; margin: 5px 0; border-left: 5px solid {color};">
                <b>Shift {i+1}</b><br>
                👤 {row['name'] if row['name'] else 'Unassigned'}<br>
                ⏰ {row['start']:02d}:00 - {end_time:02d}:00<br>
                📍 Store: {row['id_store']}
            </div>
            """,
            unsafe_allow_html=True
        )

# --- Редактируемая таблица ---
st.subheader("✏️ Edit Shifts")

# Создаем удобную таблицу для редактирования
edited_data = []
for i, row in filtered.iterrows():
    end_time = row['start'] + row['duration']
    edited_data.append({
        'Shift': f"Shift {i+1}",
        'Employee': row['name'],
        'Start': f"{row['start']:02d}:00",
        'End': f"{end_time:02d}:00",
        'Duration': row['duration']
    })

edited_df = pd.DataFrame(edited_data)
edited_result = st.data_editor(
    edited_df,
    use_container_width=True,
    column_config={
        "Shift": st.column_config.TextColumn("Shift", disabled=True),
        "Employee": st.column_config.TextColumn("Employee Name", width="medium"),
        "Start": st.column_config.TextColumn("Start Time", width="small"),
        "End": st.column_config.TextColumn("End Time", disabled=True, width="small"),
        "Duration": st.column_config.NumberColumn("Hours", disabled=True, width="small")
    }
)

# Кнопки для экспорта
col1, col2, col3 = st.columns(3)
with col1:
    csv = filtered.to_csv(index=False)
    st.download_button(
        "📥 Download Updated Shifts CSV",
        csv,
        f"shifts_{selected_store}_{selected_date}.csv",
        "text/csv"
    )

with col2:
    if st.button("🔄 Reset to Original"):
        st.experimental_rerun()

with col3:
    if st.button("📊 Summary Report"):
        total_hours = filtered['duration'].sum()
        assigned = len(filtered[filtered['name'] != ''])
        unassigned = len(filtered[filtered['name'] == ''])
        
        st.info(
            f"**Summary for {selected_date}**\n\n"
            f"Total Shifts: {len(filtered)}\n"
            f"Assigned: {assigned}\n"
            f"Unassigned: {unassigned}\n"
            f"Total Hours: {total_hours}"
        )

# --- Статистика занятости по часам ---
st.subheader("📊 Hourly Occupancy")

hourly_occupancy = []
for hour in range(24):
    employees_at_hour = sum(
        1 for _, row in filtered.iterrows()
        if row['start'] <= hour < row['start'] + row['duration']
    )
    hourly_occupancy.append(employees_at_hour)

# Создаем график занятости
fig_occ = go.Figure()
fig_occ.add_trace(go.Bar(
    x=hour_labels,
    y=hourly_occupancy,
    marker_color='#4ECDC4',
    text=hourly_occupancy,
    textposition='outside'
))

fig_occ.update_layout(
    title="Number of Employees Working per Hour",
    xaxis=dict(title="Hour", tickangle=45),
    yaxis=dict(title="Employees", dtick=1),
    height=300,
    showlegend=False
)

st.plotly_chart(fig_occ, use_container_width=True)
