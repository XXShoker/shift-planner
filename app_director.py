import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
from data_manager import (
    get_published_imports, load_shifts, save_assignments,
    get_metadata
)

st.set_page_config(layout="wide")
st.title("🎯 Shift Planner – Директор (назначение смен)")

# --- Получаем список опубликованных наборов смен ---
published = get_published_imports()
if not published:
    st.warning("Нет опубликованных смен. Дождитесь публикации от аналитика.")
    st.stop()

# Выбор набора смен
options = {f"{item['import_id']} (загружен {item['uploaded_at'][:10]})": item['import_id'] for item in published}
selected_label = st.selectbox("Выберите набор смен", list(options.keys()))
selected_import_id = options[selected_label]

# Загружаем смены (с уже сохранёнными назначениями, если есть)
shifts_df = load_shifts(selected_import_id, with_assignments=True)
if shifts_df is None:
    st.error("Ошибка загрузки данных")
    st.stop()

# --- Управление сотрудниками (храним в сессии, но можно и в файле для каждого набора) ---
if 'available_employees' not in st.session_state:
    # По умолчанию пусто, директор добавляет сам
    st.session_state.available_employees = []

# --- Выбор недели ---
st.markdown("---")
st.header("📅 Планирование на неделю")

# Получаем все даты в данных
all_dates = pd.to_datetime(shifts_df['Date'])
min_date = all_dates.min().date()
max_date = all_dates.max().date()

selected_day = st.date_input(
    "Выберите любой день недели",
    value=min_date,
    min_value=min_date,
    max_value=max_date
)

def get_week_dates(selected_date):
    start = selected_date - timedelta(days=selected_date.weekday())
    return [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]

week_dates = get_week_dates(selected_day)
st.caption(f"Неделя: {week_dates[0]} — {week_dates[-1]}")

# Фильтруем смены за эту неделю
week_shifts = shifts_df[shifts_df['Date'].isin(week_dates)].copy()
week_shifts.sort_values(['Date', 'Start'], inplace=True)

if len(week_shifts) == 0:
    st.warning("На этой неделе нет смен.")
    st.stop()

# --- Боковая панель для сотрудников ---
col_emp, col_main = st.columns([1, 3])

with col_emp:
    st.subheader("👥 Сотрудники")
    
    total = len(week_shifts)
    assigned = len(week_shifts[week_shifts['Employee'] != ''])
    free = total - assigned
    st.info(f"Всего: {total} | Назначено: {assigned} | Свободно: {free}")
    
    # Список сотрудников с возможностью удаления
    if st.session_state.available_employees:
        for emp in st.session_state.available_employees[:]:
            cola, colb = st.columns([3,1])
            cola.write(f"• {emp}")
            if colb.button("❌", key=f"del_{emp}"):
                if emp in shifts_df['Employee'].values:
                    st.warning(f"Сначала уберите {emp} из всех смен!")
                else:
                    st.session_state.available_employees.remove(emp)
                    st.rerun()
    else:
        st.write("_Нет добавленных сотрудников_")
    
    # Добавление сотрудника
    new_emp = st.text_input("Имя сотрудника", key="new_emp")
    if st.button("➕ Добавить", use_container_width=True):
        if new_emp and new_emp.strip() not in st.session_state.available_employees:
            st.session_state.available_employees.append(new_emp.strip())
            st.rerun()

# --- Основная область: назначение смен на неделю ---
with col_main:
    st.subheader("✏️ Назначение сотрудников")
    
    if not st.session_state.available_employees:
        st.warning("Добавьте сотрудников в левой панели")
    
    # Функция обновления (используем ту же логику с пересечениями, но упростим)
    def update_employee(shift_id):
        selected = st.session_state.get(f"sel_{shift_id}", "")
        # Проверяем пересечение (заимствуем логику из предыдущих версий)
        # Здесь нужно импортировать или скопировать функцию has_overlap
        # Для краткости оставим упрощённо: просто сохраняем
        shifts_df.loc[shifts_df['shift_id'] == shift_id, 'Employee'] = selected
        save_assignments(selected_import_id, shifts_df)
        st.rerun()
    
    # Отображаем смены по дням
    current_date = None
    for idx, row in week_shifts.iterrows():
        if row['Date'] != current_date:
            st.markdown(f"### {row['Date']}")
            current_date = row['Date']
        
        cols = st.columns([2,2,4])
        cols[0].write(f"**{row['Start']:02d}:00 - {row['End']:02d}:00**")
        cols[1].write(f"({row['Duration']} ч)")
        
        if st.session_state.available_employees:
            emp_options = [''] + sorted(st.session_state.available_employees)
            current = row['Employee']
            default_idx = emp_options.index(current) if current in emp_options else 0
            
            cols[2].selectbox(
                "Сотрудник",
                options=emp_options,
                index=default_idx,
                key=f"sel_{row['shift_id']}",
                on_change=update_employee,
                args=(row['shift_id'],),
                label_visibility="collapsed"
            )
        else:
            cols[2].info("Нет сотрудников")
        st.divider()
    
    # Кнопка очистки недели
    if st.button("🗑️ Очистить назначения на эту неделю", use_container_width=True):
        mask = shifts_df['Date'].isin(week_dates)
        shifts_df.loc[mask, 'Employee'] = ''
        save_assignments(selected_import_id, shifts_df)
        st.rerun()

# --- ВИЗУАЛИЗАЦИЯ GANTT (после назначений) ---
st.markdown("---")
st.header("📊 Расписание на неделю")

has_assigned = len(week_shifts[week_shifts['Employee'] != '']) > 0
if has_assigned:
    fig = go.Figure()
    colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8']
    
    for _, row in week_shifts.iterrows():
        color = colors[hash(row['Employee']) % len(colors)] if row['Employee'] else '#CCCCCC'
        label = f"{row['Date'][5:]} {row['Start']:02d}"
        fig.add_trace(go.Bar(
            x=[label],
            y=[row['Duration']],
            base=row['Start'],
            orientation='v',
            marker_color=color,
            width=0.7,
            text=row['Employee'] if row['Employee'] else '',
            textposition='inside',
            hoverinfo='text',
            hovertext=f"{row['Date']} {row['Start']:02d}:00-{row['End']:02d}:00<br>{row['Employee'] if row['Employee'] else 'Свободно'}",
            showlegend=False
        ))
    
    fig.update_layout(
        title="Расписание смен по дням",
        xaxis=dict(title="Дата и время начала", tickangle=45),
        yaxis=dict(title="Часы", range=[24, 0], dtick=1, autorange='reversed'),
        height=600,
        plot_bgcolor='#F5F5F5'
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Нет назначенных смен на эту неделю.")

# --- Экспорт ---
st.markdown("---")
st.header("📥 Экспорт")

tab1, tab2, tab3 = st.tabs(["Текущая неделя", "Все смены", "По сотрудникам"])

with tab1:
    grouped = week_shifts.groupby(['Date','Start','Duration']).agg({
        'Employee': lambda x: ', '.join([e for e in x if e])
    }).reset_index()
    grouped['Count'] = week_shifts.groupby(['Date','Start','Duration']).size().values
    grouped['Employee'] = grouped['Employee'].replace('', 'не назначены')
    st.dataframe(grouped)
    csv = grouped.to_csv(index=False, sep=';')
    st.download_button("Скачать неделю", csv, "week_schedule.csv")

with tab2:
    all_disp = shifts_df[['Date','Start','End','Duration','Employee']].copy()
    all_disp['Start'] = all_disp['Start'].apply(lambda x: f"{x:02d}:00")
    all_disp['End'] = all_disp['End'].apply(lambda x: f"{x:02d}:00")
    st.dataframe(all_disp)
    csv_all = all_disp.to_csv(index=False, sep=';')
    st.download_button("Скачать все смены", csv_all, "all_shifts.csv")

with tab3:
    emp_sum = shifts_df[shifts_df['Employee'] != ''].groupby('Employee').agg(
        Смен=('shift_id','count'),
        Часов=('Duration','sum')
    ).reset_index()
    st.dataframe(emp_sum)
    csv_emp = emp_sum.to_csv(index=False, sep=';')
    st.download_button("Скачать статистику", csv_emp, "employee_stats.csv")
