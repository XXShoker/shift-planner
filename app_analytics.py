import streamlit as st
import pandas as pd
from data_manager import (
    get_drafts_metadata,
    get_published_metadata,
    save_uploaded_shifts,
    generate_import_id,
    load_shifts,
    publish_import,
    delete_import,
    refresh_published_metadata,
    cleanup_drafts  # добавлено
)

st.set_page_config(layout="wide")
st.title("📊 Shift Planner – Аналитика")

# --- Загрузка нового файла ---
st.header("📁 Загрузить новый файл смен")
with st.expander("Требуемый формат CSV (разделитель ;)"):
    st.code("Date;Start;Duration;Count\n2024-01-15;9;8;2")

uploaded = st.file_uploader("Выберите CSV файл", type="csv")
if uploaded:
    try:
        df = pd.read_csv(uploaded, delimiter=';')
        if set(df.columns) >= {'Date', 'Start', 'Duration', 'Count'}:
            import_id = generate_import_id()
            save_uploaded_shifts(import_id, df)
            st.success(f"Файл загружен. ID: {import_id}")
            st.rerun()
        else:
            st.error("Неверный формат. Нужны колонки: Date, Start, Duration, Count")
    except Exception as e:
        st.error(f"Ошибка чтения: {e}")

# --- Список загруженных файлов ---
st.markdown("---")
st.header("📋 Управление загруженными сменами")

# Кнопка принудительной синхронизации с GitHub
col1, col2 = st.columns([3, 1])
with col2:
    if st.button("🔄 Синхронизировать с GitHub", use_container_width=True):
        if refresh_published_metadata():
            st.success("Метаданные синхронизированы")
            st.rerun()
        else:
            st.error("Ошибка синхронизации")

# Кнопка очистки битых черновиков
col1, col2, col3 = st.columns(3)
with col1:
    if st.button("🧹 Очистить битые черновики", use_container_width=True):
        removed = cleanup_drafts()
        if removed > 0:
            st.success(f"Удалено {removed} битых записей")
        else:
            st.info("Битых записей не найдено")
        st.rerun()

# Получаем черновики (локально) и опубликованные (из GitHub, всегда свежие)
drafts = get_drafts_metadata()
published = get_published_metadata(force_refresh=True)
all_items = drafts + published

if not all_items:
    st.info("Пока нет загруженных файлов.")
    st.stop()

status_filter = st.selectbox("Статус", ["Все", "draft", "published"])
filtered = [item for item in all_items if status_filter == "Все" or item['status'] == status_filter]

for item in filtered:
    with st.container(border=True):
        col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1, 1])
        col1.write(f"**ID:** {item['import_id']}")
        col2.write(f"📅 {item['uploaded_at'][:10]}")
        col3.write(f"Статус: **{item['status']}**")

        if item['status'] == 'draft':
            if col4.button("📢 Опубликовать", key=f"pub_{item['import_id']}"):
                publish_import(item['import_id'])
                st.rerun()
            if col5.button("🗑️ Удалить", key=f"del_{item['import_id']}"):
                delete_import(item['import_id'], published=False)
                st.rerun()
        else:  # published
            if col4.button("📊 Аналитика", key=f"anal_{item['import_id']}"):
                st.session_state['selected_analytics'] = item['import_id']
                st.rerun()
            if col5.button("🗑️ Удалить", key=f"del_pub_{item['import_id']}"):
                delete_import(item['import_id'], published=True)
                st.rerun()

# --- Аналитика по выбранному опубликованному файлу ---
if 'selected_analytics' in st.session_state:
    import_id = st.session_state['selected_analytics']
    st.markdown("---")
    st.subheader(f"Аналитика для набора: {import_id}")

    # Загружаем смены с назначениями (published=True, чтобы при необходимости скачать из GitHub)
    shifts = load_shifts(import_id, with_assignments=True, published=True)
    if shifts is None:
        st.error("Данные не найдены")
        st.session_state.pop('selected_analytics')
        st.rerun()

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

    # Группированная таблица (как в исходном CSV)
    st.subheader("Сводка по исходным сменам (сгруппировано)")
    grouped = shifts.groupby(['Date', 'Start', 'Duration']).agg(
        Всего_смен=('shift_id', 'count'),
        Назначено=('Employee', lambda x: (x != '').sum()),
        Сотрудники=('Employee', lambda x: ', '.join([e for e in x if e != '']) if any(x != '') else '—')
    ).reset_index()
    grouped['Свободно'] = grouped['Всего_смен'] - grouped['Назначено']
    st.dataframe(grouped, use_container_width=True)

    # Детальная таблица (под спойлером)
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
        delete_import(import_id, published=True)
        st.session_state.pop('selected_analytics')
        st.rerun()

    if st.button("Закрыть аналитику"):
        st.session_state.pop('selected_analytics')
        st.rerun()
