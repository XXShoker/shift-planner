import streamlit as st
import pandas as pd
from data_manager import (
    get_metadata, save_uploaded_shifts, generate_import_id,
    load_shifts, publish_import, delete_import
)

st.set_page_config(layout="wide")
st.title("📊 Shift Planner – Аналитика")

# --- Инициализация session state для предотвращения повторной загрузки ---
if 'upload_success' not in st.session_state:
    st.session_state.upload_success = False

# --- Загрузка нового файла ---
st.header("📁 Загрузить новый файл смен")
with st.expander("Требуемый формат CSV (разделитель ;)"):
    st.code("Date;Start;Duration;Count\n2024-01-15;9;8;2")

uploaded = st.file_uploader("Выберите CSV файл", type="csv", key="file_uploader")

if uploaded is not None and not st.session_state.upload_success:
    # Показываем спиннер во время обработки
    with st.spinner("Загрузка и сохранение файла..."):
        try:
            df = pd.read_csv(uploaded, delimiter=';')
            # Проверяем наличие необходимых колонок
            required = {'Date', 'Start', 'Duration', 'Count'}
            if required.issubset(df.columns):
                import_id = generate_import_id()
                # Сохраняем файл и метаданные (включая запись в GitHub)
                save_uploaded_shifts(import_id, df)
                st.session_state.upload_success = True
                st.success(f"✅ Файл успешно загружен. ID: {import_id}")
                # Сбрасываем загрузчик, очищая ключ
                st.rerun()
            else:
                st.error("❌ Неверный формат. Нужны колонки: Date, Start, Duration, Count")
        except Exception as e:
            st.error(f"❌ Ошибка при обработке файла: {e}")
            st.session_state.upload_success = False

# Если загрузка прошла успешно, сбрасываем флаг, чтобы можно было загрузить следующий файл
if st.session_state.upload_success:
    st.session_state.upload_success = False

# --- Список загруженных файлов ---
st.markdown("---")
st.header("📋 Управление загруженными сменами")

metadata = get_metadata()
if not metadata:
    st.info("Пока нет загруженных файлов.")
    st.stop()

# Фильтр по статусу
status_filter = st.selectbox("Статус", ["Все", "draft", "published"])
filtered = [m for m in metadata if status_filter == "Все" or m['status'] == status_filter]

# Отображаем каждый набор в отдельном контейнере
for item in filtered:
    with st.container(border=True):
        col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1, 1])
        col1.write(f"**ID:** {item['import_id']}")
        col2.write(f"📅 {item['uploaded_at'][:10]}")
        col3.write(f"Статус: **{item['status']}**")
        
        if item['status'] == 'draft':
            # Для черновиков: кнопки Опубликовать и Удалить
            if col4.button("📢 Опубликовать", key=f"pub_{item['import_id']}"):
                with st.spinner("Публикация..."):
                    publish_import(item['import_id'])
                st.rerun()
            if col5.button("🗑️ Удалить", key=f"del_{item['import_id']}"):
                with st.spinner("Удаление..."):
                    delete_import(item['import_id'])
                st.rerun()
        else:  # published
            # Для опубликованных: кнопки Аналитика и Удалить
            if col4.button("📊 Аналитика", key=f"anal_{item['import_id']}"):
                st.session_state['selected_analytics'] = item['import_id']
                st.rerun()
            if col5.button("🗑️ Удалить", key=f"del_pub_{item['import_id']}"):
                with st.spinner("Удаление..."):
                    delete_import(item['import_id'])
                st.rerun()

# --- Аналитика по выбранному опубликованному файлу ---
if 'selected_analytics' in st.session_state:
    import_id = st.session_state['selected_analytics']
    st.markdown("---")
    st.subheader(f"Аналитика для набора: {import_id}")

    # Загружаем смены с назначениями
    with st.spinner("Загрузка данных..."):
        shifts = load_shifts(import_id, with_assignments=True)
    
    if shifts is None:
        st.error("Данные не найдены. Возможно, файл был удалён.")
        st.session_state.pop('selected_analytics')
        st.rerun()

    # Статистика
    total = len(shifts)
    assigned = len(shifts[shifts['Employee'] != ''])
    free = total - assigned
    total_hours = shifts['Duration'].sum()
    assigned_hours = shifts[shifts['Employee'] != '']['Duration'].sum()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Всего смен", total)
    col2.metric("Назначено", assigned)
    col3.metric("Свободно", free)
    col4.metric("Всего часов", total_hours)
    st.metric("Часов назначено", assigned_hours)

    # Группированная таблица (исходные строки из CSV + сводка по сотрудникам)
    st.subheader("Сводка по исходным сменам (сгруппировано)")
    grouped = shifts.groupby(['Date', 'Start', 'Duration']).agg(
        Всего_смен=('shift_id', 'count'),
        Назначено=('Employee', lambda x: (x != '').sum()),
        Сотрудники=('Employee', lambda x: ', '.join([e for e in x if e != '']) if any(x != '') else '—')
    ).reset_index()
    grouped['Свободно'] = grouped['Всего_смен'] - grouped['Назначено']
    st.dataframe(grouped, use_container_width=True)

    # Детальная таблица (по желанию, можно свернуть)
    with st.expander("Показать детальную таблицу всех смен"):
        detailed = shifts[['Date', 'Start', 'End', 'Duration', 'Employee']].copy()
        detailed['Start'] = detailed['Start'].apply(lambda x: f"{x:02d}:00")
        detailed['End'] = detailed['End'].apply(lambda x: f"{x:02d}:00")
        st.dataframe(detailed, use_container_width=True)

    # Сводка по сотрудникам
    st.subheader("Сводка по сотрудникам")
    if assigned > 0:
        emp_stats = shifts[shifts['Employee'] != ''].groupby('Employee').agg(
            Смен=('shift_id', 'count'),
            Часов=('Duration', 'sum')
        ).reset_index()
        st.dataframe(emp_stats, use_container_width=True)
    else:
        st.info("Нет назначенных сотрудников")

    # Кнопка удаления всего набора прямо из аналитики
    if st.button("🗑️ Удалить этот набор", use_container_width=True, type="primary"):
        with st.spinner("Удаление..."):
            delete_import(import_id)
        st.session_state.pop('selected_analytics')
        st.rerun()

    if st.button("Закрыть аналитику"):
        st.session_state.pop('selected_analytics')
        st.rerun()
