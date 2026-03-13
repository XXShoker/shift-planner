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
    st.session_state.available_employees = ['Иванов', 'Петров', 'Сидоров', 'Смирнов', 'Кузнецов', 'Попов', 'Васильев']

# --- ШАГ 1: Загрузка файла от аналитиков ---
st.header("📁 Шаг 1: Загрузите файл от аналитиков")

uploaded_file = st.file_uploader(
    "Загрузите CSV файл (формат: Date;Start;Duration;Count)",
    type="csv",
    key="file_uploader"
)

if uploaded_file is not None:
    # Читаем файл
    df_analytics = pd.read_csv(uploaded_file, delimiter=';')
    
    # Проверяем формат
    required_columns = ['Date', 'Start', 'Duration', 'Count']
    if all(col in df_analytics.columns for col in required_columns):
        st.success("✅ Файл успешно загружен!")
        
        # Показываем загруженные данные
        st.subheader("Загруженные данные от аналитиков")
        st.dataframe(df_analytics, use_container_width=True)
        
        # --- Разворачиваем Count в отдельные строки ---
        expanded_rows = []
        for idx, row in df_analytics.iterrows():
            for i in range(row['Count']):
                expanded_rows.append({
                    'Date': row['Date'],
                    'Start': row['Start'],
                    'Duration': row['Duration'],
                    'Employee': ''  # Пустое поле для сборщика
                })
        
        st.session_state.shifts_df = pd.DataFrame(expanded_rows)
        st.session_state.shifts_df['End'] = st.session_state.shifts_df['Start'] + st.session_state.shifts_df['Duration']
        
        st.info(f"📊 Создано {len(st.session_state.shifts_df)} отдельных смен для назначения")
        
    else:
        st.error(f"❌ Неверный формат файла. Должны быть колонки: {', '.join(required_columns)}")
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
                st.session_state.shifts_df.loc[
                    (st.session_state.shifts_df['Date'] == selected_date) & 
                    (st.session_state.shifts_df['Start'] == shift['Start']) & 
                    (st.session_state.shifts_df['Duration'] == shift['Duration']) & 
                    (st.session_state.shifts_df['Employee'] == shift['Employee']), 
                    'Employee'
                ] = selected
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
            final_df = daily_shifts.groupby(['Date', 'Start', 'Duration']).agg({
                'Employee': lambda x: ', '.join(x) if any(x != '') else '',
                'Date': 'first'
            }).reset_index(drop=True)
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
    
    with st.expander("📋 Пример формата файла"):
        example_data = pd.DataFrame({
            'Date': ['2024-01-15', '2024-01-15', '2024-01-16', '2024-01-16'],
            'Start': [9, 14, 10, 15],
            'Duration': [8, 6, 8, 4],
            'Count': [2, 3, 1, 2]
        })
        st.dataframe(example_data)
        st.caption("Файл должен быть в формате CSV с разделителем ';'")
