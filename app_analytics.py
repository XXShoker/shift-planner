import streamlit as st
import pandas as pd
from data_manager import (
    get_metadata, save_uploaded_shifts, generate_import_id,
    load_shifts, publish_import, delete_import
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

metadata = get_metadata()
if not metadata:
    st.info("Пока нет загруженных файлов.")
    st.stop()

status_filter = st.selectbox("Статус", ["Все", "draft", "published"])
filtered = [m for m in metadata if status_filter == "Все" or m['status'] == status_filter]

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
                delete_import(item['import_id'])
                st.rerun()
        else:  # published
            if col4.button("📊 Аналитика", key=f"anal_{item['import_id']}"):
                st.session_state['selected_analytics'] = item['import_id']
                st.rerun()
            if col5.button("🗑️ Удалить", key=f"del_pub_{item['import_id']}"):
                delete_import(item['import_id'])
                st.rerun()

# --- Аналитика по выбранному опубликованному файлу ---
if 'selected_analytics' in st.session_state:
    import_id = st.session_state['selected_analytics']
    st.markdown("---")
    st.subheader(f"Аналитика для ID: {import_id}")
    
    shifts = load_shifts(import_id, with_assignments=True)
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
    
    st.subheader("Детальная таблица")
    display = shifts[['Date', 'Start', 'End', 'Duration', 'Employee']].copy()
    display['Start'] = display['Start'].apply(lambda x: f"{x:02d}:00")
    display['End'] = display['End'].apply(lambda x: f"{x:02d}:00")
    st.dataframe(display, use_container_width=True)
    
    st.subheader("Сводка по сотрудникам")
    if assigned > 0:
        emp_stats = shifts[shifts['Employee'] != ''].groupby('Employee').agg(
            Смен=('shift_id', 'count'),
            Часов=('Duration', 'sum')
        ).reset_index()
        st.dataframe(emp_stats, use_container_width=True)
    else:
        st.info("Нет назначенных сотрудников")
    
    if st.button("Закрыть аналитику"):
        st.session_state.pop('selected_analytics')
        st.rerun()
