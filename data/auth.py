import streamlit as st
import time
from datetime import datetime, timedelta
import pandas as pd
import os

# Файл с данными сотрудников (name, store)
NAME_STORE_CSV = "name_store.csv"

def load_name_store():
    """Загружает name_store.csv из локальной копии (или из GitHub в будущем)."""
    if os.path.exists(NAME_STORE_CSV):
        return pd.read_csv(NAME_STORE_CSV)
    else:
        # Если файла нет, возвращаем пустой DataFrame
        return pd.DataFrame(columns=["name", "store"])

def authenticate(login, password):
    """
    Проверяет логин и пароль.
    Возвращает (role, store) где role: 'admin' или 'director', store: код для директора (или None для admin).
    """
    if login == "admin" and password == "@lternat!v@35":
        return "admin", None

    # Для директора: логин должен быть 'md', пароль — существующий store в name_store.csv
    if login == "md":
        df = load_name_store()
        # Проверяем, есть ли такой store в колонке store (как строка)
        if password in df['store'].astype(str).values:
            return "director", password
    return None, None

def init_session_state():
    """Инициализирует переменные сессии, если их нет."""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "role" not in st.session_state:
        st.session_state.role = None
    if "store" not in st.session_state:
        st.session_state.store = None
    if "last_activity" not in st.session_state:
        st.session_state.last_activity = time.time()

def check_activity_timeout(max_inactive_seconds=12*3600):
    """Проверяет, не превышен ли таймаут неактивности. Если да — выполняет logout."""
    if st.session_state.authenticated:
        now = time.time()
        if now - st.session_state.last_activity > max_inactive_seconds:
            logout()
            st.rerun()
        else:
            st.session_state.last_activity = now

def logout():
    """Очищает сессию (выход)."""
    st.session_state.authenticated = False
    st.session_state.role = None
    st.session_state.store = None
    st.session_state.last_activity = time.time()

def show_login_form():
    """Отображает форму входа и обрабатывает её."""
    st.title("🔐 Вход в систему")
    with st.form("login_form"):
        login = st.text_input("Логин")
        password = st.text_input("Пароль", type="password")
        submitted = st.form_submit_button("Войти")
        if submitted:
            role, store = authenticate(login, password)
            if role:
                st.session_state.authenticated = True
                st.session_state.role = role
                st.session_state.store = store
                st.session_state.last_activity = time.time()
                st.success("Успешный вход!")
                st.rerun()
            else:
                st.error("Неверный логин или пароль")
