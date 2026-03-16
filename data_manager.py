# Добавить в конец файла (после cleanup_drafts)

# ---------- Работа с name_store.csv ----------
NAME_STORE_PATH = "name_store.csv"

def get_name_store():
    """Возвращает DataFrame с исполнителями (name, store)."""
    repo = get_repo()
    if repo:
        try:
            contents = repo.get_contents(NAME_STORE_PATH, ref="main")
            content = base64.b64decode(contents.content).decode("utf-8")
            from io import StringIO
            df = pd.read_csv(StringIO(content))
            # Сохраняем локально для кэша
            df.to_csv(NAME_STORE_PATH, index=False)
            return df
        except GithubException as e:
            if e.status == 404:
                # Если файла нет, создаём пустой
                df = pd.DataFrame(columns=["name", "store"])
                df.to_csv(NAME_STORE_PATH, index=False)
                return df
            else:
                # Если ошибка, пробуем локальный файл
                if os.path.exists(NAME_STORE_PATH):
                    return pd.read_csv(NAME_STORE_PATH)
                return pd.DataFrame(columns=["name", "store"])
    else:
        # Нет доступа к GitHub, используем локальный
        if os.path.exists(NAME_STORE_PATH):
            return pd.read_csv(NAME_STORE_PATH)
        return pd.DataFrame(columns=["name", "store"])

def save_name_store(df):
    """Сохраняет DataFrame с исполнителями локально и в GitHub."""
    df.to_csv(NAME_STORE_PATH, index=False)
    # Сохраняем в GitHub
    with open(NAME_STORE_PATH, "rb") as f:
        content_bytes = f.read()
    save_file_to_github(NAME_STORE_PATH, content_bytes, "Update name_store.csv")

def refresh_name_store():
    """Принудительно загружает name_store.csv из GitHub."""
    return get_name_store()  # get_name_store уже обновляет локальный кэш

# ---------- Проверка актуальности назначений ----------
def get_assignments_from_github(import_id):
    """Загружает назначения для import_id напрямую из GitHub."""
    repo = get_repo()
    if not repo:
        return None
    try:
        contents = repo.get_contents(f"data/assignments/{import_id}.json", ref="main")
        content = base64.b64decode(contents.content).decode("utf-8")
        return json.loads(content)
    except GithubException:
        return None
