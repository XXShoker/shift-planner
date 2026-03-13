import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(layout="wide")
st.title("🎯 Shift Planner – GoodTime Style (Недельное планирование)")

# --- Инициализация session state ---
if 'shifts_df' not in st.session_state:
    st.session_state.shifts_df = None
if 'available_employees' not in st.session_state:
    st.session_state.available_employees = []
if 'last_update' not in st.session_state:
    st.session_state.last_update = "—"
if 'debug_log' not in st.session_state:
    st.session_state.debug_log = []

# --- Функция проверки пересечения смен ---
def has_overlap(shift_id, employee, shifts_df):
    if not employee:
        return False, []
    current_shift = shifts_df[shifts_df['shift_id'] == shift_id].iloc[0]
    current_date = current_shift['Date']
    current_start = current_shift['Start']
    current_end = current_shift['End']

    other_shifts = shifts_df[
        (shifts_df['Date'] == current_date) &
        (shifts_df['Employee'] == employee) &
        (shifts_df['shift_id'] != shift_id)
    ]

    overlapping = []
    for _, other in other_shifts.iterrows():
        if not (current_end <= other['Start'] or current_start >= other['End']):
            overlapping.append(other)
    return len(overlapping) > 0, overlapping

# --- Функция обновления сотрудника ---
def update_employee(shift_id):
    try:
        shift_id = int(shift_id)
    except:
        pass

    selected = st.session_state.get(f"select_{shift_id}", "")
    log_entry = f"update_employee called: shift_id={shift_id}, selected={selected}"
    st.session_state.debug_log.append(log_entry)

    if st.session_state.shifts_df is None:
        st.session_state.last_update = "❌ Ошибка: shifts_df is None"
        st.toast(st.session_state.last_update)
        st.rerun()
        return

    mask = st.session_state.shifts_df['shift_id'] == shift_id
    if not mask.any():
        st.session_state.last_update = f"❌ shift_id {shift_id} не найден"
        st.toast(st.session_state.last_update)
        st.rerun()
        return

    old_value = st.session_state.shifts_df.loc[mask, 'Employee'].iloc[0]

    # Если выбрали пустого сотрудника — всегда разрешаем
    if not selected:
        st.session_state.shifts_df.loc[mask, 'Employee'] = ''
        if f"select_{shift_id}" in st.session_state:
            st.session_state[f"select_{shift_id}"] = ''
        st.session_state.last_update = f"✅ Смена {shift_id} очищена"
        st.toast(st.session_state.last_update)
        st.rerun()
        return

    # Если выбран тот же сотрудник — ничего не делаем
    if selected == old_value:
        st.session_state.last_update = f"⏭️ Смена {shift_id}: без изменений"
        st.toast(st.session_state.last_update)
        st.rerun()
        return

    # Проверка пересечения для нового сотрудника
    overlap, overlapping_shifts = has_overlap(shift_id, selected, st.session_state.shifts_df)
    if overlap:
        st.session_state.shifts_df.loc[mask, 'Employee'] = ''
        if f"select_{shift_id}" in st.session_state:
            st.session_state[f"select_{shift_id}"] = ''
        msg = f"⚠️ Пересечение: {selected} уже работает "
        for o in overlapping_shifts:
            msg += f"{o['Start']:02d}:00-{o['End']:02d}:00 "
        st.session_state.last_update = msg
        st.toast(msg, icon="⚠️")
        st.rerun()
        return

    # Всё хорошо — назначаем
    st.session_state.shifts_df.loc[mask, 'Employee'] = selected
    st.session_state.last_update = f"✅ Смена {shift_id} → {selected}"
    st.toast(st.session_state.last_update)
    st.rerun()

# --- Функция получения дат недели по выбранному дню ---
def get_week_dates(selected_date):
    # Находим понедельник недели, содержащей selected_date
    start_of_week = selected_date - timedelta(days=selected_date.weekday())
    # Создаём список дат с понедельника по воскресенье
    week_dates = [(start_of_week + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
    return week_dates

# --- ШАГ 1: Загрузка файла от аналитиков ---
st.header("📁 Шаг 1: Загрузите файл от аналитиков")

with st.expander("📋 Пример правильного формата файла (CSV с разделителем ;)"):
    example_data = """Date;Start;Duration;Count
2024-01-15;9;8;2
2024-01-15;10;6;1
2024-01-15;14;6;3
2024-01-16;9;8;1
2024-01-16;15;4;2"""
    st.code(example_data, language="csv")
    st.caption("Файл должен быть в формате CSV с разделителем ';'")

uploaded_file = st.file_uploader(
    "Загрузите CSV файл",
    type="csv",
    key="file_uploader"
)

if uploaded_file is not None and st.session_state.shifts_df is None:
    try:
        content = uploaded_file.getvalue().decode('utf-8')
        
        if ';' in content.split('\n')[0]:
            df_analytics = pd.read_csv(uploaded_file, delimiter=';')
        elif ',' in content.split('\n')[0]:
            df_analytics = pd.read_csv(uploaded_file, delimiter=',')
        else:
            df_analytics = pd.read_csv(uploaded_file, delimiter=';')
        
        df_analytics.columns = df_analytics.columns.str.strip()
        
        required_columns = ['Date', 'Start', 'Duration', 'Count']
        df_columns_lower = [col.lower() for col in df_analytics.columns]
        required_lower = [col.lower() for col in required_columns]
        
        if all(col in df_columns_lower for col in required_lower):
            column_mapping = {}
            for req_col in required_columns:
                for df_col in df_analytics.columns:
                    if df_col.lower() == req_col.lower():
                        column_mapping[df_col] = req_col
                        break
            
            if column_mapping:
                df_analytics = df_analytics.rename(columns=column_mapping)
            
            st.success("✅ Файл успешно загружен!")
            st.subheader("Загруженные данные от аналитиков")
            st.dataframe(df_analytics, use_container_width=True)
            
            expanded_rows = []
            shift_id = 0
            for idx, row in df_analytics.iterrows():
                for i in range(int(row['Count'])):
                    expanded_rows.append({
                        'shift_id': shift_id,
                        'Date': row['Date'],
                        'Start': int(row['Start']),
                        'Duration': int(row['Duration']),
                        'Employee': ''
                    })
                    shift_id += 1
            
            st.session_state.shifts_df = pd.DataFrame(expanded_rows)
            st.session_state.shifts_df['End'] = st.session_state.shifts_df['Start'] + st.session_state.shifts_df['Duration']
            
            st.info(f"📊 Создано {len(st.session_state.shifts_df)} отдельных смен для назначения")
            
        else:
            missing = [col for col in required_columns if col.lower() not in df_columns_lower]
            st.error(f"❌ Неверный формат файла. Отсутствуют колонки: {', '.join(missing)}")
            st.write("Найденные колонки в файле:", list(df_analytics.columns))
            st.stop()
            
    except Exception as e:
        st.error(f"❌ Ошибка при чтении файла: {str(e)}")
        st.stop()

# --- ШАГ 2: Если файл загружен, показываем интерфейс планировщика ---
if st.session_state.shifts_df is not None:
    
    st.markdown("---")
    st.header("📅 Шаг 2: Планирование на неделю")
    
    # Выбор недели: используем календарь для выбора любого дня, затем определяем неделю
    min_date = datetime.strptime(st.session_state.shifts_df['Date'].min(), "%Y-%m-%d").date()
    max_date = datetime.strptime(st.session_state.shifts_df['Date'].max(), "%Y-%m-%d").date()
    
    selected_day = st.date_input(
        "Выберите любой день недели",
        value=min_date,
        min_value=min_date,
        max_value=max_date
    )
    
    # Получаем даты недели
    week_dates = get_week_dates(selected_day)
    st.caption(f"Неделя: {week_dates[0]} — {week_dates[-1]}")
    
    # Фильтруем смены за эту неделю
    week_shifts = st.session_state.shifts_df[st.session_state.shifts_df['Date'].isin(week_dates)].copy()
    week_shifts.reset_index(drop=True, inplace=True)
    
    if len(week_shifts) == 0:
        st.warning("На этой неделе нет смен.")
        st.stop()
    
    # --- Боковая панель для управления сотрудниками (оставим справа, но можно и слева) ---
    col_employees, col_main = st.columns([1, 3])
    
    with col_employees:
        st.subheader("👥 Управление сотрудниками")
        
        total_shifts = len(week_shifts)
        assigned_shifts = len(week_shifts[week_shifts['Employee'] != ''])
        unassigned_shifts = total_shifts - assigned_shifts
        
        st.info(f"""
        📊 **Статистика за неделю**
        - Всего смен: {total_shifts}
        - Назначено: {assigned_shifts}
        - Свободно: {unassigned_shifts}
        - Часов: {week_shifts['Duration'].sum()}
        """)
        
        st.markdown("---")
        st.subheader("📋 Список сотрудников")
        
        if st.session_state.available_employees:
            for emp in st.session_state.available_employees[:]:
                col1, col2 = st.columns([3, 1])
                col1.write(f"• {emp}")
                if col2.button("❌", key=f"del_{emp}"):
                    if emp in st.session_state.shifts_df['Employee'].values:
                        st.warning(f"Сначала уберите {emp} из всех смен!")
                    else:
                        st.session_state.available_employees.remove(emp)
                        st.rerun()
        else:
            st.write("_Нет добавленных сотрудников_")
        
        st.markdown("---")
        st.subheader("➕ Добавить сотрудника")
        
        new_employee = st.text_input("Имя сотрудника", key="new_emp_input")
        
        if st.button("✅ Добавить сотрудника", use_container_width=True):
            if new_employee and new_employee.strip():
                if new_employee not in st.session_state.available_employees:
                    st.session_state.available_employees.append(new_employee.strip())
                    st.success(f"Сотрудник {new_employee} добавлен!")
                    st.rerun()
                else:
                    st.warning("Такой сотрудник уже есть")
            else:
                st.warning("Введите имя сотрудника")
    
    # --- Основная область: назначение смен на неделю ---
    with col_main:
        st.subheader("✏️ Назначение сотрудников на смены (неделя)")
        
        if not st.session_state.available_employees:
            st.warning("⚠️ Сначала добавьте сотрудников в левой панели")
        
        # Группируем по дням для удобства
        week_shifts_sorted = week_shifts.sort_values(['Date', 'Start']).reset_index(drop=True)
        
        # Отображаем смены сгруппированно по дням
        current_date = None
        for idx, shift in week_shifts_sorted.iterrows():
            if shift['Date'] != current_date:
                st.markdown(f"### {shift['Date']}")
                current_date = shift['Date']
            
            cols = st.columns([2, 2, 4])
            cols[0].write(f"**{shift['Start']:02d}:00 - {shift['End']:02d}:00**")
            cols[1].write(f"({shift['Duration']} ч)")
            
            if st.session_state.available_employees:
                employee_options = [''] + sorted(st.session_state.available_employees)
                current = shift['Employee']
                if current in employee_options:
                    default_idx = employee_options.index(current)
                else:
                    default_idx = 0
                
                cols[2].selectbox(
                    f"Сотрудник",
                    options=employee_options,
                    index=default_idx,
                    key=f"select_{shift['shift_id']}",
                    on_change=update_employee,
                    args=(shift['shift_id'],),
                    label_visibility="collapsed"
                )
            else:
                cols[2].info("Нет сотрудников")
            
            st.divider()
        
        # Кнопка очистки всех назначений на неделю
        if st.button("🗑️ Очистить все назначения на эту неделю", use_container_width=True):
            mask = st.session_state.shifts_df['Date'].isin(week_dates)
            st.session_state.shifts_df.loc[mask, 'Employee'] = ''
            for shift_id in st.session_state.shifts_df.loc[mask, 'shift_id']:
                key = f"select_{shift_id}"
                if key in st.session_state:
                    st.session_state[key] = ''
            st.rerun()
    
    # --- ВИЗУАЛИЗАЦИЯ (Gantt) после назначения ---
    st.markdown("---")
    st.header("📊 Визуализация расписания на неделю")
    
    # Проверяем, есть ли назначенные смены на неделе
    has_assigned_week = len(week_shifts[week_shifts['Employee'] != '']) > 0
    
    if has_assigned_week:
        fig = go.Figure()
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8']
        
        # Для удобства добавим номер смены в подпись, но можно и по-другому
        for i, shift in week_shifts_sorted.iterrows():
            start_hour = shift['Start']
            end_hour = shift['End']
            
            if shift['Employee']:
                color_idx = hash(shift['Employee']) % len(colors)
                color = colors[color_idx]
            else:
                color = '#CCCCCC'
            
            # Подпись на оси X: день + время начала
            x_label = f"{shift['Date'][5:]} {shift['Start']:02d}"
            
            fig.add_trace(go.Bar(
                x=[x_label],
                y=[shift['Duration']],
                base=start_hour,
                orientation='v',
                marker_color=color,
                width=0.7,
                text=shift['Employee'] if shift['Employee'] else '',
                textposition='inside',
                hoverinfo='text',
                hovertext=f"{shift['Date']} {start_hour}:00-{end_hour}:00<br>{shift['Employee'] if shift['Employee'] else 'Свободно'}",
                showlegend=False
            ))
        
        fig.update_layout(
            title="Расписание смен по дням",
            xaxis=dict(title="Дата и время начала", tickangle=45),
            yaxis=dict(title="Часы", range=[24, 0], dtick=1, autorange='reversed'),
            height=600,
            plot_bgcolor='#F5F5F5',
            margin=dict(l=80, r=20, t=80, b=100)
        )
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("👆 Нет назначенных смен на эту неделю. Визуализация появится после назначения.")
    
    # --- Экспорт (по неделе и все данные) ---
    st.markdown("---")
    st.header("📥 Экспорт данных")
    
    tab1, tab2, tab3 = st.tabs(["Текущая неделя", "Все даты", "Сводка по сотрудникам"])
    
    with tab1:
        st.subheader("Смены на текущую неделю (сгруппировано)")
        grouped_week = []
        for (date, start, duration), group in week_shifts.groupby(['Date', 'Start', 'Duration']):
            employees = [e for e in group['Employee'] if e != '']
            grouped_week.append({
                'Date': date,
                'Start': start,
                'Duration': duration,
                'Count': len(group),
                'Employees': ', '.join(employees) if employees else 'не назначены'
            })
        week_grouped_df = pd.DataFrame(grouped_week)
        st.dataframe(week_grouped_df, use_container_width=True)
        
        csv_week = week_grouped_df.to_csv(index=False, sep=';')
        st.download_button(
            "📥 Скачать CSV (текущая неделя)",
            csv_week,
            f"week_{week_dates[0]}_to_{week_dates[-1]}.csv",
            "text/csv",
            use_container_width=True
        )
    
    with tab2:
        st.subheader("Все смены (детально)")
        all_shifts_display = st.session_state.shifts_df[['Date', 'Start', 'End', 'Duration', 'Employee']].copy()
        all_shifts_display['Start'] = all_shifts_display['Start'].apply(lambda x: f"{x:02d}:00")
        all_shifts_display['End'] = all_shifts_display['End'].apply(lambda x: f"{x:02d}:00")
        all_shifts_display.columns = ['Дата', 'Начало', 'Конец', 'Длительность', 'Сотрудник']
        st.dataframe(all_shifts_display, use_container_width=True)
        
        # Группировка по всем датам
        all_grouped = []
        for (date, start, duration), group in st.session_state.shifts_df.groupby(['Date', 'Start', 'Duration']):
            employees = [e for e in group['Employee'] if e != '']
            all_grouped.append({
                'Date': date,
                'Start': start,
                'Duration': duration,
                'Count': len(group),
                'Employees': ', '.join(employees) if employees else 'не назначены'
            })
        all_grouped_df = pd.DataFrame(all_grouped)
        csv_all = all_grouped_df.to_csv(index=False, sep=';')
        st.download_button(
            "📥 Скачать CSV (все даты, сгруппировано)",
            csv_all,
            "analytics_shifts_all_dates.csv",
            "text/csv",
            use_container_width=True
        )
    
    with tab3:
        st.subheader("Сводка по сотрудникам (все даты)")
        emp_summary = st.session_state.shifts_df[st.session_state.shifts_df['Employee'] != ''].groupby('Employee').agg(
            Смен=('shift_id', 'count'),
            Часов=('Duration', 'sum')
        ).reset_index()
        emp_summary.columns = ['Сотрудник', 'Количество смен', 'Всего часов']
        st.dataframe(emp_summary, use_container_width=True)
    
    # --- Кнопка полного сброса ---
    if st.button("🔄 Начать заново (загрузить новый файл)"):
        st.session_state.shifts_df = None
        st.session_state.available_employees = []
        st.rerun()

else:
    st.info("👆 Пожалуйста, загрузите файл от аналитиков для начала работы")
