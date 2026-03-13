import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(layout="wide")
st.title("🎯 Shift Planner – GoodTime Style")

# --- Инициализация session state ---
if 'shifts_df' not in st.session_state:
    st.session_state.shifts_df = None
if 'available_employees' not in st.session_state:
    # Пустой список сотрудников по умолчанию
    st.session_state.available_employees = []
if 'temp_employee' not in st.session_state:
    st.session_state.temp_employee = ""

# --- ШАГ 1: Загрузка файла от аналитиков ---
st.header("📁 Шаг 1: Загрузите файл от аналитиков")

# Показываем пример правильного формата
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

if uploaded_file is not None:
    try:
        # Пробуем разные разделители
        content = uploaded_file.getvalue().decode('utf-8')
        
        # Определяем разделитель
        if ';' in content.split('\n')[0]:
            df_analytics = pd.read_csv(uploaded_file, delimiter=';')
        elif ',' in content.split('\n')[0]:
            df_analytics = pd.read_csv(uploaded_file, delimiter=',')
        else:
            df_analytics = pd.read_csv(uploaded_file, delimiter=';')  # пробуем стандартный
        
        # Очищаем названия колонок от пробелов
        df_analytics.columns = df_analytics.columns.str.strip()
        
        # Проверяем формат
        required_columns = ['Date', 'Start', 'Duration', 'Count']
        
        # Проверяем наличие колонок (без учета регистра)
        df_columns_lower = [col.lower() for col in df_analytics.columns]
        required_lower = [col.lower() for col in required_columns]
        
        if all(col in df_columns_lower for col in required_lower):
            # Приводим названия колонок к нужному виду
            column_mapping = {}
            for req_col in required_columns:
                for df_col in df_analytics.columns:
                    if df_col.lower() == req_col.lower():
                        column_mapping[df_col] = req_col
                        break
            
            if column_mapping:
                df_analytics = df_analytics.rename(columns=column_mapping)
            
            st.success("✅ Файл успешно загружен!")
            
            # Показываем загруженные данные
            st.subheader("Загруженные данные от аналитиков")
            st.dataframe(df_analytics, use_container_width=True)
            
            # --- Разворачиваем Count в отдельные строки ---
            expanded_rows = []
            for idx, row in df_analytics.iterrows():
                for i in range(int(row['Count'])):
                    expanded_rows.append({
                        'Date': row['Date'],
                        'Start': int(row['Start']),
                        'Duration': int(row['Duration']),
                        'Employee': ''  # Пустое поле для сборщика
                    })
            
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
    st.header("📅 Шаг 2: Планирование смен")
    
    # Выбор даты
    available_dates = sorted(st.session_state.shifts_df['Date'].unique())
    
    if len(available_dates) > 0:
        col1, col2 = st.columns([1, 3])
        with col1:
            selected_date = st.selectbox("Выберите дату", available_dates)
        
        # Фильтруем смены для выбранной даты
        daily_shifts = st.session_state.shifts_df[st.session_state.shifts_df['Date'] == selected_date].copy()
        daily_shifts.reset_index(drop=True, inplace=True)
        
        # --- Интерфейс GoodTime ---
        col_timeline, col_employees = st.columns([3, 1])
        
        with col_timeline:
            st.subheader("Визуализация смен")
            
            # Создаем вертикальную временную шкалу
            fig = go.Figure()
            
            # Цвета для сотрудников
            colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8']
            
            # Добавляем блоки смен
            for i, shift in daily_shifts.iterrows():
                start_hour = shift['Start']
                end_hour = shift['End']
                
                # Выбираем цвет
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
                    range=[24, 0],
                    gridcolor='lightgray',
                    showgrid=True,
                    dtick=1
                ),
                plot_bgcolor='#F5F5F5',
                height=600,
                margin=dict(l=80, r=20, t=40, b=40),
                hovermode='closest'
            )
            
            # Добавляем разделители
            for i in range(len(daily_shifts) + 1):
                fig.add_vline(x=i - 0.5, line_width=1, line_color='gray', line_dash='dash')
            
            st.plotly_chart(fig, use_container_width=True)
        
        with col_employees:
            st.subheader("👥 Сотрудники")
            
            # Статистика
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
            
            # Список добавленных сотрудников
            if st.session_state.available_employees:
                st.write("**Добавленные сотрудники:**")
                for emp in st.session_state.available_employees:
                    st.write(f"• {emp}")
            else:
                st.write("_Нет добавленных сотрудников_")
            
            st.markdown("---")
            
            # Добавление нового сотрудника - ИСПРАВЛЕНО!
            st.subheader("➕ Добавить сотрудника")
            
            # Используем текстовое поле и кнопку
            new_employee = st.text_input("Имя сотрудника", key="new_emp_input", value=st.session_state.temp_employee)
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Добавить", use_container_width=True):
                    if new_employee and new_employee.strip():
                        if new_employee not in st.session_state.available_employees:
                            st.session_state.available_employees.append(new_employee.strip())
                            st.session_state.temp_employee = ""  # Очищаем поле
                            st.success(f"Сотрудник {new_employee} добавлен!")
                            st.rerun()
                        else:
                            st.warning("Такой сотрудник уже есть")
                    else:
                        st.warning("Введите имя сотрудника")
            
            with col2:
                if st.button("🗑️ Очистить", use_container_width=True):
                    st.session_state.temp_employee = ""
                    st.rerun()
        
        # --- Редактор назначений ---
        st.markdown("---")
        st.header("✏️ Назначение сотрудников на смены")
        
        # Проверяем, есть ли сотрудники для назначения
        if not st.session_state.available_employees:
            st.warning("⚠️ Сначала добавьте сотрудников в правой панели")
        
        # Создаем таблицу для назначений
        for i, shift in daily_shifts.iterrows():
            cols = st.columns([1, 2, 1, 3, 1])
            
            cols[0].write(f"**Смена {i+1}**")
            cols[1].write(f"{shift['Start']:02d}:00 - {shift['End']:02d}:00")
            cols[2].write(f"{shift['Duration']} ч")
            
            # Выбор сотрудника (только если есть добавленные сотрудники)
            if st.session_state.available_employees:
                employee_options = [''] + sorted(st.session_state.available_employees)
                
                # Находим индекс текущего сотрудника
                if shift['Employee'] in employee_options:
                    current_idx = employee_options.index(shift['Employee'])
                else:
                    current_idx = 0
                
                selected = cols[3].selectbox(
                    f"emp_{i}",
                    options=employee_options,
                    index=current_idx,
                    label_visibility="collapsed",
                    key=f"assign_{i}_{selected_date}"
                )
                
                # Обновляем назначение
                if selected != shift['Employee']:
                    # Находим все смены с такими же параметрами (для правильного обновления)
                    mask = ((st.session_state.shifts_df['Date'] == selected_date) & 
                           (st.session_state.shifts_df['Start'] == shift['Start']) & 
                           (st.session_state.shifts_df['Duration'] == shift['Duration']) &
                           (st.session_state.shifts_df['Employee'] == shift['Employee']))
                    
                    # Обновляем первую подходящую смену
                    indices = st.session_state.shifts_df[mask].index
                    if len(indices) > 0:
                        st.session_state.shifts_df.loc[indices[0], 'Employee'] = selected
                    
                    cols[4].success("✓")
                else:
                    if shift['Employee']:
                        cols[4].success("✅")
                    else:
                        cols[4].info("⭕")
            else:
                cols[3].info("Нет сотрудников")
                cols[4].write("")
        
        # --- Экспорт результатов ---
        st.markdown("---")
        st.header("📥 Шаг 3: Экспорт результатов")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Формат для аналитиков (с группировкой)
            st.subheader("Для аналитиков")
            
            # Группируем обратно
            final_df = daily_shifts.copy()
            final_df = final_df.groupby(['Date', 'Start', 'Duration']).agg({
                'Employee': lambda x: ', '.join([e for e in x if e != '']) if any(x != '') else '',
            }).reset_index()
            final_df['Count'] = daily_shifts.groupby(['Date', 'Start', 'Duration']).size().values
            
            st.dataframe(final_df, use_container_width=True)
            
            csv_analytics = final_df.to_csv(index=False, sep=';')
            st.download_button(
                "📥 Скачать для аналитиков",
                csv_analytics,
                f"analytics_shifts_{selected_date}.csv",
                "text/csv",
                use_container_width=True
            )
        
        with col2:
            # Формат для сотрудников
            st.subheader("Для сотрудников")
            
            employee_view = daily_shifts[daily_shifts['Employee'] != ''].copy()
            if not employee_view.empty:
                employee_view['Время'] = employee_view.apply(
                    lambda x: f"{x['Start']:02d}:00 - {x['End']:02d}:00", axis=1
                )
                employee_view = employee_view[['Employee', 'Время', 'Duration']]
                employee_view.columns = ['Сотрудник', 'Время работы', 'Часов']
                
                st.dataframe(employee_view, use_container_width=True)
                
                csv_employees = employee_view.to_csv(index=False, sep=';')
                st.download_button(
                    "📋 Скачать для сотрудников",
                    csv_employees,
                    f"employee_schedule_{selected_date}.csv",
                    "text/csv",
                    use_container_width=True
                )
            else:
                st.info("Нет назначенных сотрудников")
        
        # --- Кнопка сброса ---
        if st.button("🔄 Начать заново (загрузить новый файл)"):
            st.session_state.shifts_df = None
            st.session_state.available_employees = []
            st.rerun()
    
    else:
        st.warning("В загруженном файле нет данных")

else:
    # Показываем инструкцию, если файл еще не загружен
    st.info("👆 Пожалуйста, загрузите файл от аналитиков для начала работы")        # Пробуем разные разделители
        content = uploaded_file.getvalue().decode('utf-8')
        
        # Определяем разделитель
        if ';' in content.split('\n')[0]:
            df_analytics = pd.read_csv(uploaded_file, delimiter=';')
        elif ',' in content.split('\n')[0]:
            df_analytics = pd.read_csv(uploaded_file, delimiter=',')
        else:
            df_analytics = pd.read_csv(uploaded_file, delimiter=';')  # пробуем стандартный
        
        # Очищаем названия колонок от пробелов
        df_analytics.columns = df_analytics.columns.str.strip()
        
        # Проверяем формат
        required_columns = ['Date', 'Start', 'Duration', 'Count']
        
        # Проверяем наличие колонок (без учета регистра)
        df_columns_lower = [col.lower() for col in df_analytics.columns]
        required_lower = [col.lower() for col in required_columns]
        
        if all(col in df_columns_lower for col in required_lower):
            # Приводим названия колонок к нужному виду
            column_mapping = {}
            for req_col in required_columns:
                for df_col in df_analytics.columns:
                    if df_col.lower() == req_col.lower():
                        column_mapping[df_col] = req_col
                        break
            
            if column_mapping:
                df_analytics = df_analytics.rename(columns=column_mapping)
            
            st.success("✅ Файл успешно загружен!")
            
            # Показываем загруженные данные
            st.subheader("Загруженные данные от аналитиков")
            st.dataframe(df_analytics, use_container_width=True)
            
            # --- Разворачиваем Count в отдельные строки ---
            expanded_rows = []
            for idx, row in df_analytics.iterrows():
                for i in range(int(row['Count'])):
                    expanded_rows.append({
                        'Date': row['Date'],
                        'Start': int(row['Start']),
                        'Duration': int(row['Duration']),
                        'Employee': ''  # Пустое поле для сборщика
                    })
            
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
    st.header("📅 Шаг 2: Планирование смен")
    
    # Выбор даты
    available_dates = sorted(st.session_state.shifts_df['Date'].unique())
    
    if len(available_dates) > 0:
        col1, col2 = st.columns([1, 3])
        with col1:
            selected_date = st.selectbox("Выберите дату", available_dates)
        
        # Фильтруем смены для выбранной даты
        daily_shifts = st.session_state.shifts_df[st.session_state.shifts_df['Date'] == selected_date].copy()
        daily_shifts.reset_index(drop=True, inplace=True)
        
        # --- Интерфейс GoodTime ---
        col_timeline, col_employees = st.columns([3, 1])
        
        with col_timeline:
            st.subheader("Визуализация смен")
            
            # Создаем вертикальную временную шкалу
            fig = go.Figure()
            
            # Цвета для сотрудников
            colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8']
            
            # Добавляем блоки смен
            for i, shift in daily_shifts.iterrows():
                start_hour = shift['Start']
                end_hour = shift['End']
                
                # Выбираем цвет
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
                    range=[24, 0],
                    gridcolor='lightgray',
                    showgrid=True,
                    dtick=1
                ),
                plot_bgcolor='#F5F5F5',
                height=600,
                margin=dict(l=80, r=20, t=40, b=40),
                hovermode='closest'
            )
            
            # Добавляем разделители
            for i in range(len(daily_shifts) + 1):
                fig.add_vline(x=i - 0.5, line_width=1, line_color='gray', line_dash='dash')
            
            st.plotly_chart(fig, use_container_width=True)
        
        with col_employees:
            st.subheader("👥 Сотрудники")
            
            # Статистика
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
            
            # Добавление нового сотрудника
            new_employee = st.text_input("Добавить сотрудника")
            if new_employee and st.button("➕ Добавить"):
                if new_employee not in st.session_state.available_employees:
                    st.session_state.available_employees.append(new_employee)
                    st.success(f"Сотрудник {new_employee} добавлен!")
                    st.rerun()
        
        # --- Редактор назначений ---
        st.markdown("---")
        st.header("✏️ Назначение сотрудников на смены")
        
        # Создаем таблицу для назначений
        for i, shift in daily_shifts.iterrows():
            cols = st.columns([1, 2, 1, 3, 1])
            
            cols[0].write(f"**Смена {i+1}**")
            cols[1].write(f"{shift['Start']:02d}:00 - {shift['End']:02d}:00")
            cols[2].write(f"{shift['Duration']} ч")
            
            # Выбор сотрудника
            employee_options = [''] + sorted(st.session_state.available_employees)
            current_idx = employee_options.index(shift['Employee']) if shift['Employee'] in employee_options else 0
            
            selected = cols[3].selectbox(
                f"emp_{i}",
                options=employee_options,
                index=current_idx,
                label_visibility="collapsed",
                key=f"assign_{i}"
            )
            
            # Обновляем назначение
            if selected != shift['Employee']:
                daily_shifts.loc[i, 'Employee'] = selected
                
                # Обновляем в основном DataFrame
                mask = ((st.session_state.shifts_df['Date'] == selected_date) & 
                       (st.session_state.shifts_df['Start'] == shift['Start']) & 
                       (st.session_state.shifts_df['Duration'] == shift['Duration']) &
                       (st.session_state.shifts_df['Employee'] == ''))
                
                # Находим первую свободную смену с такими параметрами
                indices = st.session_state.shifts_df[mask].index
                if len(indices) > 0:
                    st.session_state.shifts_df.loc[indices[0], 'Employee'] = selected
                
                cols[4].success("✓")
            else:
                if shift['Employee']:
                    cols[4].success("✅")
                else:
                    cols[4].info("⭕")
        
        # --- Экспорт результатов ---
        st.markdown("---")
        st.header("📥 Шаг 3: Экспорт результатов")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Формат для аналитиков (с группировкой)
            st.subheader("Для аналитиков")
            
            # Группируем обратно
            final_df = daily_shifts.copy()
            final_df = final_df.groupby(['Date', 'Start', 'Duration']).agg({
                'Employee': lambda x: ', '.join(x) if any(x != '') else '',
            }).reset_index()
            final_df['Count'] = daily_shifts.groupby(['Date', 'Start', 'Duration']).size().values
            
            st.dataframe(final_df, use_container_width=True)
            
            csv_analytics = final_df.to_csv(index=False, sep=';')
            st.download_button(
                "📥 Скачать для аналитиков",
                csv_analytics,
                f"analytics_shifts_{selected_date}.csv",
                "text/csv",
                use_container_width=True
            )
        
        with col2:
            # Формат для сотрудников
            st.subheader("Для сотрудников")
            
            employee_view = daily_shifts[daily_shifts['Employee'] != ''].copy()
            if not employee_view.empty:
                employee_view['Время'] = employee_view.apply(
                    lambda x: f"{x['Start']:02d}:00 - {x['End']:02d}:00", axis=1
                )
                employee_view = employee_view[['Employee', 'Время', 'Duration']]
                employee_view.columns = ['Сотрудник', 'Время работы', 'Часов']
                
                st.dataframe(employee_view, use_container_width=True)
                
                csv_employees = employee_view.to_csv(index=False, sep=';')
                st.download_button(
                    "📋 Скачать для сотрудников",
                    csv_employees,
                    f"employee_schedule_{selected_date}.csv",
                    "text/csv",
                    use_container_width=True
                )
            else:
                st.info("Нет назначенных сотрудников")
        
        # --- Кнопка сброса ---
        if st.button("🔄 Начать заново (загрузить новый файл)"):
            st.session_state.shifts_df = None
            st.rerun()
    
    else:
        st.warning("В загруженном файле нет данных")

else:
    # Показываем инструкцию, если файл еще не загружен
    st.info("👆 Пожалуйста, загрузите файл от аналитиков для начала работы")
