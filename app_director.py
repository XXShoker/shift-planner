import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time
from data_manager import (
    get_published_imports, load_shifts, save_assignments,
    get_name_store, save_name_store, refresh_name_store,
    get_assignments_from_github
)
from auth import init_session_state, check_activity_timeout, logout, show_login_form

st.set_page_config(layout="wide")

# Инициализация сессии и проверка таймаута
init_session_state()
check_activity_timeout()

# Если не аутентифицирован — показываем форму входа и останавливаем выполнение
if not st.session_state.authenticated:
    show_login_form()
    st.stop()

# Главное приложение (после входа)
st.title("🎯 Shift Planner")

# Боковая панель с информацией о пользователе и кнопкой выхода
with st.sidebar:
    if st.session_state.role == "admin":
        st.write(f"**Администратор**")
    else:
        st.write(f"**Директор** (store: {st.session_state.store})")
    if st.button("🚪 Выйти"):
        logout()
        st.rerun()

# Загружаем список опубликованных наборов смен
published = get_published_imports()
if not published:
    st.warning("Нет опубликованных смен. Дождитесь публикации от аналитика.")
    st.stop()

# Выбор набора смен (общий для всех)
options = {f"{item['import_id']} (загружен {item['uploaded_at'][:10]})": item['import_id'] for item in published}
selected_label = st.selectbox("Выберите набор смен", list(options.keys()))
selected_import_id = options[selected_label]

# Загружаем смены с уже сохранёнными назначениями
shifts_df = load_shifts(selected_import_id, with_assignments=True, published=True)
if shifts_df is None:
    st.error("Ошибка загрузки данных")
    st.stop()

# Если пользователь директор, показываем только смены с его store
if st.session_state.role == "director":
    shifts_df = shifts_df[shifts_df['Store'] == st.session_state.store].copy()

# Загружаем список исполнителей из name_store.csv
employees_df = get_name_store()
if st.session_state.role == "director":
    # Фильтруем только тех, у кого store совпадает с store директора
    employees_df = employees_df[employees_df['store'].astype(str) == st.session_state.store]

# Сохраняем employees_df в сессии для использования в функциях обратного вызова
st.session_state.employees_df = employees_df

# Создаём список имён для выпадающего списка
employee_names = [''] + sorted(employees_df['name'].unique().tolist())

# --- Раздел для администратора: управление исполнителями ---
if st.session_state.role == "admin":
    st.header("👥 Управление исполнителями")
    with st.expander("Добавить/редактировать исполнителя", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            new_name = st.text_input("Имя исполнителя")
        with col2:
            new_store = st.text_input("Store (код)")
        if st.button("➕ Добавить исполнителя"):
            if new_name and new_store:
                # Проверяем, нет ли уже такого имени
                if new_name in employees_df['name'].values:
                    st.warning("Исполнитель с таким именем уже существует. Используйте редактирование.")
                else:
                    new_row = pd.DataFrame({"name": [new_name], "store": [new_store]})
                    employees_df = pd.concat([employees_df, new_row], ignore_index=True)
                    save_name_store(employees_df)
                    # Обновляем сессию
                    st.session_state.employees_df = employees_df
                    st.success(f"Исполнитель {new_name} добавлен")
                    st.rerun()
            else:
                st.error("Заполните оба поля")

    # Таблица существующих исполнителей с возможностью удаления
    st.subheader("Список исполнителей")
    if not employees_df.empty:
        # Для удаления используем колонку с кнопками
        for idx, row in employees_df.iterrows():
            cola, colb, colc = st.columns([3, 1, 1])
            cola.write(f"**{row['name']}** (store: {row['store']})")
            if colb.button("✏️", key=f"edit_{idx}"):
                st.info("Редактирование пока не реализовано, удалите и добавьте заново.")
            if colc.button("🗑️", key=f"del_{idx}"):
                # Проверим, не назначен ли этот исполнитель на смены в текущем наборе
                if row['name'] in shifts_df['Employee'].values:
                    st.warning(f"Нельзя удалить {row['name']}, он уже назначен на смены в этом наборе. Сначала уберите его из всех смен.")
                else:
                    employees_df = employees_df.drop(idx).reset_index(drop=True)
                    save_name_store(employees_df)
                    st.session_state.employees_df = employees_df
                    st.rerun()
    else:
        st.info("Нет исполнителей")

    st.markdown("---")

# --- Основной интерфейс планирования (общий для всех) ---
st.header("📅 Планирование смен")

# Выбор недели
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

week_shifts = shifts_df[shifts_df['Date'].isin(week_dates)].copy()
week_shifts.sort_values(['Date', 'Start'], inplace=True)

if len(week_shifts) == 0:
    st.warning("На этой неделе нет смен.")
    st.stop()

# --- Функции для обработки назначений с проверкой конфликтов ---
def has_overlap(shift_id, employee, shifts_df):
    if not employee:
        return False, []
    cur = shifts_df[shifts_df['shift_id'] == shift_id].iloc[0]
    others = shifts_df[
        (shifts_df['Date'] == cur['Date']) &
        (shifts_df['Employee'] == employee) &
        (shifts_df['shift_id'] != shift_id)
    ]
    overlapping = []
    for _, o in others.iterrows():
        if not (cur['End'] <= o['Start'] or cur['Start'] >= o['End']):
            overlapping.append(o)
    return len(overlapping) > 0, overlapping

def update_employee(shift_id):
    selected = st.session_state.get(f"sel_{shift_id}", "")
    if not selected:
        # Если выбрали пустоту, просто очищаем
        shifts_df.loc[shifts_df['shift_id'] == shift_id, 'Employee'] = ''
        save_assignments(selected_import_id, shifts_df, published=True)
        st.rerun()
        return

    # Получаем информацию о смене
    shift_row = shifts_df[shifts_df['shift_id'] == shift_id].iloc[0]
    shift_store = shift_row['Store']

    # Проверяем, что выбранный сотрудник принадлежит нужному store (если не admin)
    if st.session_state.role != "admin":
        emp_store_row = st.session_state.employees_df[st.session_state.employees_df['name'] == selected]
        if emp_store_row.empty:
            st.error(f"Сотрудник {selected} не найден в базе")
            st.session_state[f"sel_{shift_id}"] = ''
            return
        emp_store = str(emp_store_row.iloc[0]['store'])
        if emp_store != shift_store:
            st.error(f"Сотрудник {selected} принадлежит store {emp_store}, но смена требует store {shift_store}. Назначение невозможно.")
            st.session_state[f"sel_{shift_id}"] = ''
            return

    # Проверяем актуальные назначения из GitHub
    current_assignments = get_assignments_from_github(selected_import_id)
    if current_assignments is not None:
        str_shift_id = str(shift_id)
        if str_shift_id in current_assignments and current_assignments[str_shift_id] != '':
            # Конфликт: смена уже занята
            st.error(f"⚠️ Смена {shift_id} уже занята сотрудником {current_assignments[str_shift_id]}. Обновите страницу.")
            # Сбрасываем selectbox
            st.session_state[f"sel_{shift_id}"] = ''
            st.rerun()
            return

    # Проверяем пересечения с другими сменами того же сотрудника
    overlap, overlaps = has_overlap(shift_id, selected, shifts_df)
    if overlap:
        msg = f"⚠️ Пересечение: {selected} уже работает "
        for o in overlaps:
            msg += f"{o['Start']:02d}:00-{o['End']:02d}:00 "
        st.toast(msg, icon="⚠️")
        # Сбрасываем selectbox
        st.session_state[f"sel_{shift_id}"] = ''
        return

    # Повторная проверка перед сохранением (на случай, если состояние изменилось за время проверки)
    current_assignments_final = get_assignments_from_github(selected_import_id)
    if current_assignments_final is not None:
        str_shift_id = str(shift_id)
        if str_shift_id in current_assignments_final and current_assignments_final[str_shift_id] != '':
            st.error(f"⚠️ Смена {shift_id} только что была занята. Попробуйте ещё раз.")
            st.session_state[f"sel_{shift_id}"] = ''
            st.rerun()
            return

    # Всё хорошо, назначаем
    shifts_df.loc[shifts_df['shift_id'] == shift_id, 'Employee'] = selected
    st.toast(f"✅ Смена {shift_id} → {selected}")
    save_assignments(selected_import_id, shifts_df, published=True)
    st.rerun()

# Отображение смен по дням с учётом доступности сотрудников
current_date = None
for _, row in week_shifts.iterrows():
    if row['Date'] != current_date:
        st.markdown(f"### {row['Date']} (store: {row['Store']})")
        current_date = row['Date']
    
    current_employee = row['Employee']
    
    # Проверяем, есть ли текущий сотрудник в списке доступных для этого пользователя
    if current_employee and current_employee not in employee_names:
        # Смена занята сотрудником, недоступным для выбора
        cols = st.columns([2, 2, 4])
        cols[0].write(f"**{row['Start']:02d}:00 - {row['End']:02d}:00**")
        cols[1].write(f"({row['Duration']} ч)")
        cols[2].info(f"👤 Занято: {current_employee}")
        st.divider()
        continue
    
    # Иначе показываем selectbox для назначения
    cols = st.columns([2, 2, 4])
    cols[0].write(f"**{row['Start']:02d}:00 - {row['End']:02d}:00**")
    cols[1].write(f"({row['Duration']} ч)")
    if employee_names:
        current = row['Employee']
        default_idx = employee_names.index(current) if current in employee_names else 0
        cols[2].selectbox(
            "Сотрудник",
            options=employee_names,
            index=default_idx,
            key=f"sel_{row['shift_id']}",
            on_change=update_employee,
            args=(row['shift_id'],),
            label_visibility="collapsed"
        )
    else:
        cols[2].info("Нет доступных сотрудников")
    st.divider()

if st.button("🗑️ Очистить назначения на эту неделю", use_container_width=True):
    mask = shifts_df['Date'].isin(week_dates)
    shifts_df.loc[mask, 'Employee'] = ''
    save_assignments(selected_import_id, shifts_df, published=True)
    st.rerun()

# --- Визуализация Gantt ---
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
    st.dataframe(grouped, width='stretch')
    csv = grouped.to_csv(index=False, sep=';')
    st.download_button("Скачать неделю", csv, "week_schedule.csv", width='stretch')

with tab2:
    all_disp = shifts_df[['Date','Start','End','Duration','Employee','Store']].copy()
    all_disp['Start'] = all_disp['Start'].apply(lambda x: f"{x:02d}:00")
    all_disp['End'] = all_disp['End'].apply(lambda x: f"{x:02d}:00")
    st.dataframe(all_disp, width='stretch')
    csv_all = all_disp.to_csv(index=False, sep=';')
    st.download_button("Скачать все смены", csv_all, "all_shifts.csv", width='stretch')

with tab3:
    emp_sum = shifts_df[shifts_df['Employee'] != ''].groupby('Employee').agg(
        Смен=('shift_id','count'),
        Часов=('Duration','sum')
    ).reset_index()
    st.dataframe(emp_sum, width='stretch')
    csv_emp = emp_sum.to_csv(index=False, sep=';')
    st.download_button("Скачать статистику", csv_emp, "employee_stats.csv", width='stretch')
