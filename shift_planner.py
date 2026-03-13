import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import numpy as np

st.set_page_config(layout="wide")
st.title("🎯 Shift Planner – GoodTime Style")

# --- Загружаем CSV от аналитиков ---
st.sidebar.header("📁 Загрузка данных")
uploaded = st.sidebar.file_uploader("Загрузите CSV от аналитиков", type="csv")

if uploaded is not None:
    df = pd.read_csv(uploaded, delimiter=';')
else:
    # Демо-данные, если файл не загружен
    st.sidebar.info("Используются демо-данные. Загрузите свой CSV для работы.")
    data = {
        'Date': ['2024-01-15', '2024-01-15', '2024-01-15', '2024-01-15'],
        'Start': [9, 10, 14, 15],
        'Duration': [8, 6, 6, 4],
        'Count': [2, 1, 3, 1]
    }
    df = pd.DataFrame(data)

# Показываем загруженные данные
st.sidebar.subheader("Исходные данные")
st.sidebar.dataframe(df)

# --- Разворачиваем Count в отдельные строки ---
expanded_rows = []
for idx, row in df.iterrows():
    for i in range(row['Count']):
        expanded_rows.append({
            'Date': row['Date'],
            'Start': row['Start'],
            'Duration': row['Duration'],
            'Employee': ''  # Пустое поле для сборщика
        })

shifts_df = pd.DataFrame(expanded_rows)
shifts_df['End'] = shifts_df['Start'] + shifts_df['Duration']

# --- Фильтры ---
st.header("📅 Выбор даты")
available_dates = sorted(shifts_df['Date'].unique())
selected_date = st.selectbox("Выберите дату", available_dates)

# Фильтруем смены для выбранной даты
daily_shifts = shifts_df[shifts_df['Date'] == selected_date].copy()
daily_shifts.reset_index(drop=True, inplace=True)

# --- Интерфейс GoodTime ---
st.header("📊 Планировщик смен (GoodTime Style)")

# Создаем колонки для визуализации
col_timeline, col_employees = st.columns([3, 1])

with col_timeline:
    # Создаем вертикальную временную шкалу
    fig = go.Figure()
    
    # Цвета для разных сотрудников
    colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8']
    
    # Добавляем блоки смен
    for i, shift in daily_shifts.iterrows():
        start_hour = shift['Start']
        end_hour = shift['End']
        
        # Выбираем цвет в зависимости от сотрудника или серый если не назначен
        if shift['Employee']:
            color_idx = hash(shift['Employee']) % len(colors)
            color = colors[color_idx]
        else:
            color = '#CCCCCC'  # Серый для неназначенных
        
        # Рисуем блок смены
        fig.add_trace(go.Scatter(
            x=[i, i, i, i],
            y=[start_hour, end_hour, end_hour, start_hour],
            fill='toself',
            fillcolor=color,
            line=dict(color='white', width=2),
            mode='lines',
            name=f"Смена {i+1}",
            text=f"{shift['Employee'] if shift['Employee'] else 'Свободно'}<br>{start_hour}:00 - {end_hour}:00",
            hoverinfo='text',
            showlegend=False
        ))
        
        # Добавляем имя сотрудника внутри блока
        if shift['Employee']:
            text_color = 'white'
            bg_color = 'rgba(0,0,0,0.6)'
        else:
            text_color = '#666'
            bg_color = 'rgba(255,255,255,0.9)'
        
        fig.add_annotation(
            x=i,
            y=(start_hour + end_hour) / 2,
            text=shift['Employee'] if shift['Employee'] else '???',
            showarrow=False,
            font=dict(size=11, color=text_color, family='Arial'),
            bgcolor=bg_color,
            bordercolor='white' if shift['Employee'] else '#999',
            borderwidth=1,
            borderpad=3
        )
    
    # Настройка осей
    hours = list(range(24))
    hour_labels = [f"{h:02d}:00" for h in hours]
    
    fig.update_layout(
        xaxis=dict(
            title="Смены",
            tickmode='array',
            tickvals=list(range(len(daily_shifts))),
            ticktext=[f"Смена {i+1}" for i in range(len(daily_shifts))],
            gridcolor='lightgray',
            showgrid=True
        ),
        yaxis=dict(
            title="Время",
            tickmode='array',
            tickvals=hours,
            ticktext=hour_labels,
            range=[24, 0],  # 0:00 сверху
            gridcolor='lightgray',
            showgrid=True,
            dtick=1
        ),
        plot_bgcolor='#F5F5F5',
        height=600,
        margin=dict(l=80, r=20, t=40, b=40),
        hovermode='closest'
    )
    
    # Добавляем разделители между сменами
    for i in range(len(daily_shifts) + 1):
        fig.add_vline(x=i - 0.5, line_width=1, line_color='gray', line_dash='dash')
    
    st.plotly_chart(fig, use_container_width=True)

with col_employees:
    st.subheader("👥 Сотрудники")
    
    # Список доступных сотрудников (можно добавить своих)
    if 'available_employees' not in st.session_state:
        st.session_state.available_employees = ['Иванов', 'Петров', 'Сидоров', 'Смирнов', 'Кузнецов', 'Попов', 'Васильев']
    
    # Показываем статистику
    total_shifts = len(daily_shifts)
    assigned_shifts = len(daily_shifts[daily_shifts['Employee'] != ''])
    unassigned_shifts = total_shifts - assigned_shifts
    
    st.info(f"""
    📊 **Статистика**
    - Всего смен: {total_shifts}
    - Назначено: {assigned_shifts}
    - Свободно: {unassigned_shifts}
    - Часов: {daily_shifts['Duration'].sum()}
    """)
    
    # Кнопка для добавления сотрудника
    new_employee = st.text_input("Добавить сотрудника")
    if new_employee and st.button("➕ Добавить"):
        if new_employee not in st.session_state.available_employees:
            st.session_state.available_employees.append(new_employee)
            st.success(f"Сотрудник {new_employee} добавлен!")
            st.rerun()

# --- Редактор назначений ---
st.header("✏️ Назначение сотрудников")

# Создаем удобный интерфейс для назначения
edited_data = []
for i, shift in daily_shifts.iterrows():
    edited_data.append({
        '№': i + 1,
        'Время': f"{shift['Start']:02d}:00 - {shift['End']:02d}:00",
        'Длительность': f"{shift['Duration']} ч",
        'Сотрудник': shift['Employee'],
        'Статус': '✅ Назначено' if shift['Employee'] else '⭕ Свободно'
    })

display_df = pd.DataFrame(edited_data)

# Создаем редактор с выбором сотрудника
for i, row in display_df.iterrows():
    cols = st.columns([1, 2, 1, 2, 1, 1])
    cols[0].write(f"**{row['№']}**")
    cols[1].write(row['Время'])
    cols[2].write(row['Длительность'])
    
    # Выпадающий список для выбора сотрудника
    current_idx = daily_shifts.index[i]
    current_employee = daily_shifts.loc[current_idx, 'Employee']
    
    # Создаем список опций
    employee_options = [''] + st.session_state.available_employees
    employee_options.sort()
    
    # Индекс текущего выбора
    if current_employee in employee_options:
        default_idx = employee_options.index(current_employee)
    else:
        default_idx = 0
    
    selected = cols[3].selectbox(
        f"employee_{i}",
        options=employee_options,
        index=default_idx,
        label_visibility="collapsed",
        key=f"emp_select_{i}"
    )
    
    # Обновляем назначение
    if selected != current_employee:
        daily_shifts.loc[current_idx, 'Employee'] = selected
        cols[4].success("✓")
    
    cols[5].write(row['Статус'])

# --- Экспорт результатов ---
st.header("📥 Экспорт")

# Создаем итоговый DataFrame
final_df = daily_shifts[['Date', 'Start', 'Duration', 'Employee']].copy()
final_df['Count'] = 1
final_df = final_df.groupby(['Date', 'Start', 'Duration']).agg({
    'Count': 'count',
    'Employee': lambda x: ', '.join(x) if len(x) > 0 else ''
}).reset_index()

col1, col2 = st.columns(2)

with col1:
    # Показываем итоговые данные
    st.subheader("Итоговые данные с назначениями")
    st.dataframe(final_df, use_container_width=True)

with col2:
    st.subheader("Статистика по сотрудникам")
    employee_stats = daily_shifts[daily_shifts['Employee'] != ''].groupby('Employee').agg({
        'Duration': ['count', 'sum']
    }).round(1)
    
    if not employee_stats.empty:
        employee_stats.columns = ['Смен', 'Часов']
        st.dataframe(employee_stats, use_container_width=True)

# Кнопки экспорта
col1, col2 = st.columns(2)

with col1:
    # Экспорт в CSV для аналитиков
    csv_for_analytics = final_df.to_csv(index=False, sep=';')
    st.download_button(
        "📥 Скачать CSV для аналитиков",
        csv_for_analytics,
        f"shifts_with_employees_{selected_date}.csv",
        "text/csv",
        use_container_width=True
    )

with col2:
    # Экспорт в CSV для сотрудников
    employee_view = daily_shifts[['Employee', 'Start', 'End', 'Duration']].copy()
    employee_view = employee_view[employee_view['Employee'] != '']
    employee_view['Время'] = employee_view.apply(
        lambda x: f"{x['Start']:02d}:00 - {x['End']:02d}:00", axis=1
    )
    employee_csv = employee_view[['Employee', 'Время', 'Duration']].to_csv(index=False, sep=';')
    
    st.download_button(
        "📋 Скачать для сотрудников",
        employee_csv,
        f"employee_schedule_{selected_date}.csv",
        "text/csv",
        use_container_width=True
    )

# --- Справка ---
with st.expander("ℹ️ Как пользоваться"):
    st.markdown("""
    1. **Загрузите CSV** от аналитиков (формат: Date;Start;Duration;Count)
    2. **Выберите дату** для планирования
    3. **Назначайте сотрудников** на смены через выпадающие списки
    4. **Скачайте результат** в двух форматах:
       - Для аналитиков (с группировкой)
       - Для сотрудников (индивидуальное расписание)
    
    Формат входного CSV:
    - Date: дата смены
    - Start: час начала (например, 9)
    - Duration: длительность в часах
    - Count: количество человек на эту смену
    """)
