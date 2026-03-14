import os
import json
import pandas as pd
import uuid
import time
from datetime import datetime
from github import Github, GithubException
import streamlit as st

GH_TOKEN = os.environ.get("GH_TOKEN")
GH_REPO = os.environ.get("GH_REPO")

DATA_DIR = "data"
SHIFTS_DIR = os.path.join(DATA_DIR, "shifts")
ASSIGNMENTS_DIR = os.path.join(DATA_DIR, "assignments")
METADATA_FILE = os.path.join(DATA_DIR, "metadata.json")

os.makedirs(SHIFTS_DIR, exist_ok=True)
os.makedirs(ASSIGNMENTS_DIR, exist_ok=True)

@st.cache_resource(ttl=60)  # кешируем репозиторий на 60 секунд, чтобы не дёргать GitHub постоянно
def get_repo():
    if not GH_TOKEN or not GH_REPO:
        st.warning("GitHub токен или репозиторий не заданы. Данные будут сохраняться только локально.")
        return None
    try:
        g = Github(GH_TOKEN)
        repo = g.get_repo(GH_REPO)
        # Проверим доступ, сделав простой запрос
        _ = repo.full_name
        return repo
    except GithubException as e:
        st.error(f"Ошибка доступа к GitHub: {e}")
        return None

def commit_file(repo, file_path, message, content_bytes):
    try:
        contents = repo.get_contents(file_path, ref="main")
        repo.update_file(contents.path, message, content_bytes, contents.sha, branch="main")
    except GithubException as e:
        if e.status == 404:
            repo.create_file(file_path, message, content_bytes, branch="main")
        else:
            st.error(f"GitHub ошибка при коммите {file_path}: {e}")
            raise

def save_file_locally_and_github(relative_path, content_bytes, commit_message):
    full_path = os.path.join(DATA_DIR, relative_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "wb") as f:
        f.write(content_bytes)
    repo = get_repo()
    if repo:
        try:
            commit_file(repo, relative_path, commit_message, content_bytes)
        except Exception as e:
            st.error(f"Не удалось сохранить файл на GitHub: {e}")

def get_metadata():
    if not os.path.exists(METADATA_FILE):
        return []
    with open(METADATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_metadata(metadata):
    content = json.dumps(metadata, indent=2, ensure_ascii=False).encode("utf-8")
    save_file_locally_and_github("data/metadata.json", content, "Update metadata")

def generate_import_id():
    return datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + str(uuid.uuid4())[:8]

def save_uploaded_shifts(import_id, df_analytics):
    # Проверяем, не существует ли уже такой import_id (на всякий случай)
    metadata = get_metadata()
    if any(item['import_id'] == import_id for item in metadata):
        st.error(f"Import ID {import_id} уже существует. Попробуйте ещё раз.")
        return False
    csv_content = df_analytics.to_csv(sep=';', index=False).encode("utf-8")
    with st.spinner("Сохранение файла..."):
        save_file_locally_and_github(f"data/shifts/{import_id}.csv", csv_content, f"Upload shifts {import_id}")
    metadata.append({
        "import_id": import_id,
        "filename": f"{import_id}.csv",
        "uploaded_at": datetime.now().isoformat(),
        "status": "draft",
        "description": ""
    })
    save_metadata(metadata)
    return True

def load_shifts(import_id, with_assignments=False):
    csv_path = os.path.join(SHIFTS_DIR, f"{import_id}.csv")
    if not os.path.exists(csv_path):
        # Попробуем скачать из GitHub, если есть репозиторий
        repo = get_repo()
        if repo:
            try:
                contents = repo.get_contents(f"data/shifts/{import_id}.csv", ref="main")
                os.makedirs(os.path.dirname(csv_path), exist_ok=True)
                with open(csv_path, "wb") as f:
                    f.write(contents.decoded_content)
            except:
                return None
        else:
            return None
    df = pd.read_csv(csv_path, delimiter=';')
    df.columns = df.columns.str.strip()
    expanded = []
    shift_id = 0
    for _, row in df.iterrows():
        for i in range(int(row['Count'])):
            expanded.append({
                'shift_id': shift_id,
                'Date': row['Date'],
                'Start': int(row['Start']),
                'Duration': int(row['Duration']),
                'Employee': ''
            })
            shift_id += 1
    shifts_df = pd.DataFrame(expanded)
    shifts_df['End'] = shifts_df['Start'] + shifts_df['Duration']
    if with_assignments:
        assign_path = os.path.join(ASSIGNMENTS_DIR, f"{import_id}.json")
        if os.path.exists(assign_path):
            with open(assign_path, "r", encoding="utf-8") as f:
                assignments = json.load(f)
            for sid, emp in assignments.items():
                shifts_df.loc[shifts_df['shift_id'] == int(sid), 'Employee'] = emp
        else:
            # Попробуем скачать из GitHub
            repo = get_repo()
            if repo:
                try:
                    contents = repo.get_contents(f"data/assignments/{import_id}.json", ref="main")
                    os.makedirs(os.path.dirname(assign_path), exist_ok=True)
                    with open(assign_path, "wb") as f:
                        f.write(contents.decoded_content)
                    with open(assign_path, "r", encoding="utf-8") as f:
                        assignments = json.load(f)
                    for sid, emp in assignments.items():
                        shifts_df.loc[shifts_df['shift_id'] == int(sid), 'Employee'] = emp
                except:
                    pass
    return shifts_df

def save_assignments(import_id, shifts_df):
    assignments = {}
    for _, row in shifts_df.iterrows():
        if row['Employee']:
            assignments[int(row['shift_id'])] = row['Employee']
    content = json.dumps(assignments, indent=2, ensure_ascii=False).encode("utf-8")
    save_file_locally_and_github(f"data/assignments/{import_id}.json", content, f"Update assignments {import_id}")

def get_published_imports():
    metadata = get_metadata()
    return [item for item in metadata if item['status'] == 'published']

def publish_import(import_id):
    metadata = get_metadata()
    for item in metadata:
        if item['import_id'] == import_id:
            item['status'] = 'published'
            break
    save_metadata(metadata)

def delete_import(import_id):
    # Удаляем локальные файлы
    csv_path = os.path.join(SHIFTS_DIR, f"{import_id}.csv")
    assign_path = os.path.join(ASSIGNMENTS_DIR, f"{import_id}.json")
    if os.path.exists(csv_path):
        os.remove(csv_path)
    if os.path.exists(assign_path):
        os.remove(assign_path)
    # Удаляем из GitHub
    repo = get_repo()
    if repo:
        try:
            contents = repo.get_contents(f"data/shifts/{import_id}.csv", ref="main")
            repo.delete_file(contents.path, f"Delete shifts {import_id}", contents.sha, branch="main")
        except:
            pass
        try:
            contents = repo.get_contents(f"data/assignments/{import_id}.json", ref="main")
            repo.delete_file(contents.path, f"Delete assignments {import_id}", contents.sha, branch="main")
        except:
            pass
    # Удаляем из метаданных
    metadata = get_metadata()
    metadata = [item for item in metadata if item['import_id'] != import_id]
    save_metadata(metadata)
