import os
import json
import pandas as pd
import uuid
import time
from datetime import datetime
from github import Github, GithubException

GH_TOKEN = os.environ.get("GH_TOKEN")
GH_REPO = os.environ.get("GH_REPO")

DATA_DIR = "data"
SHIFTS_DIR = os.path.join(DATA_DIR, "shifts")
ASSIGNMENTS_DIR = os.path.join(DATA_DIR, "assignments")
DRAFTS_METADATA_FILE = os.path.join(DATA_DIR, "drafts_metadata.json")
PUBLISHED_METADATA_FILE = os.path.join(DATA_DIR, "published_metadata.json")

os.makedirs(SHIFTS_DIR, exist_ok=True)
os.makedirs(ASSIGNMENTS_DIR, exist_ok=True)

def get_repo():
    if not GH_TOKEN or not GH_REPO:
        return None
    g = Github(GH_TOKEN)
    try:
        return g.get_repo(GH_REPO)
    except GithubException:
        return None

def commit_file(repo, file_path, message, content_bytes, max_retries=3):
    for attempt in range(max_retries):
        try:
            try:
                contents = repo.get_contents(file_path, ref="main")
                current_sha = contents.sha
                repo.update_file(contents.path, message, content_bytes, current_sha, branch="main")
            except GithubException as e:
                if e.status == 404:
                    repo.create_file(file_path, message, content_bytes, branch="main")
                else:
                    raise
            return
        except GithubException as e:
            if e.status == 409 and attempt < max_retries - 1:
                time.sleep(1 * (2 ** attempt))
                continue
            else:
                raise

def save_file_locally(relative_path, content_bytes):
    full_path = os.path.join(DATA_DIR, relative_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "wb") as f:
        f.write(content_bytes)

def save_file_to_github(relative_path, content_bytes, commit_message):
    repo = get_repo()
    if repo:
        commit_file(repo, relative_path, commit_message, content_bytes)

def load_json_local(file_path):
    if not os.path.exists(file_path):
        return []
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json_local(file_path, data):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_drafts_metadata():
    return load_json_local(DRAFTS_METADATA_FILE)

def save_drafts_metadata(metadata):
    save_json_local(DRAFTS_METADATA_FILE, metadata)

def get_published_metadata():
    # Сначала пробуем локально, если нет — загружаем из GitHub
    if os.path.exists(PUBLISHED_METADATA_FILE):
        return load_json_local(PUBLISHED_METADATA_FILE)
    repo = get_repo()
    if repo:
        try:
            contents = repo.get_contents("data/published_metadata.json", ref="main")
            import base64
            content = base64.b64decode(contents.content).decode("utf-8")
            metadata = json.loads(content)
            # Сохраняем локально для кэша
            save_json_local(PUBLISHED_METADATA_FILE, metadata)
            return metadata
        except:
            return []
    return []

def save_published_metadata(metadata):
    # Сохраняем локально и в GitHub
    save_json_local(PUBLISHED_METADATA_FILE, metadata)
    content = json.dumps(metadata, indent=2, ensure_ascii=False).encode("utf-8")
    save_file_to_github("data/published_metadata.json", content, "Update published metadata")

def generate_import_id():
    return datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + str(uuid.uuid4())[:8]

def save_uploaded_shifts(import_id, df_analytics):
    """Сохраняет черновик локально, без GitHub."""
    csv_content = df_analytics.to_csv(sep=';', index=False).encode("utf-8")
    save_file_locally(f"shifts/{import_id}.csv", csv_content)
    metadata = get_drafts_metadata()
    metadata.append({
        "import_id": import_id,
        "filename": f"{import_id}.csv",
        "uploaded_at": datetime.now().isoformat(),
        "status": "draft",
        "description": ""
    })
    save_drafts_metadata(metadata)

def load_shifts(import_id, with_assignments=False, published=False):
    """
    Загружает смены. Если published=True, сначала пробует локально,
    если нет — тянет из GitHub.
    """
    csv_path = os.path.join(SHIFTS_DIR, f"{import_id}.csv")
    if not os.path.exists(csv_path) and published:
        # Скачиваем из GitHub
        repo = get_repo()
        if repo:
            try:
                contents = repo.get_contents(f"data/shifts/{import_id}.csv", ref="main")
                import base64
                csv_content = base64.b64decode(contents.content)
                with open(csv_path, "wb") as f:
                    f.write(csv_content)
            except:
                return None
    if not os.path.exists(csv_path):
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
        if not os.path.exists(assign_path) and published:
            repo = get_repo()
            if repo:
                try:
                    contents = repo.get_contents(f"data/assignments/{import_id}.json", ref="main")
                    import base64
                    assign_content = base64.b64decode(contents.content)
                    with open(assign_path, "wb") as f:
                        f.write(assign_content)
                except:
                    pass
        if os.path.exists(assign_path):
            with open(assign_path, "r", encoding="utf-8") as f:
                assignments = json.load(f)
            for sid, emp in assignments.items():
                shifts_df.loc[shifts_df['shift_id'] == int(sid), 'Employee'] = emp
    return shifts_df

def save_assignments(import_id, shifts_df, published=False):
    """Сохраняет назначения. Если published=True, коммитит в GitHub."""
    assignments = {}
    for _, row in shifts_df.iterrows():
        if row['Employee']:
            assignments[int(row['shift_id'])] = row['Employee']
    content = json.dumps(assignments, indent=2, ensure_ascii=False).encode("utf-8")
    save_file_locally(f"assignments/{import_id}.json", content)
    if published:
        save_file_to_github(f"data/assignments/{import_id}.json", content, f"Update assignments {import_id}")

def get_published_imports():
    """Возвращает список опубликованных наборов."""
    return get_published_metadata()

def get_draft_imports():
    """Возвращает список черновиков."""
    return get_drafts_metadata()

def publish_import(import_id):
    """Публикует черновик: копирует файлы в GitHub, обновляет метаданные."""
    drafts = get_drafts_metadata()
    draft = next((item for item in drafts if item['import_id'] == import_id), None)
    if not draft:
        return False

    # Сохраняем CSV в GitHub
    csv_path = os.path.join(SHIFTS_DIR, f"{import_id}.csv")
    if os.path.exists(csv_path):
        with open(csv_path, "rb") as f:
            csv_content = f.read()
        save_file_to_github(f"data/shifts/{import_id}.csv", csv_content, f"Publish shifts {import_id}")

    # Сохраняем назначения, если есть
    assign_path = os.path.join(ASSIGNMENTS_DIR, f"{import_id}.json")
    if os.path.exists(assign_path):
        with open(assign_path, "rb") as f:
            assign_content = f.read()
        save_file_to_github(f"data/assignments/{import_id}.json", assign_content, f"Publish assignments {import_id}")

    # Обновляем опубликованные метаданные
    published = get_published_metadata()
    draft['status'] = 'published'
    published.append(draft)
    save_published_metadata(published)

    # Удаляем из черновиков
    drafts = [item for item in drafts if item['import_id'] != import_id]
    save_drafts_metadata(drafts)

    return True

def delete_import(import_id, published=False):
    """Удаляет набор. Если published=True, удаляет из GitHub."""
    if published:
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
        # Удаляем из опубликованных метаданных
        published_meta = get_published_metadata()
        published_meta = [item for item in published_meta if item['import_id'] != import_id]
        save_published_metadata(published_meta)
    else:
        # Удаляем из черновиков
        drafts = get_drafts_metadata()
        drafts = [item for item in drafts if item['import_id'] != import_id]
        save_drafts_metadata(drafts)

    # Удаляем локальные файлы
    csv_path = os.path.join(SHIFTS_DIR, f"{import_id}.csv")
    if os.path.exists(csv_path):
        os.remove(csv_path)
    assign_path = os.path.join(ASSIGNMENTS_DIR, f"{import_id}.json")
    if os.path.exists(assign_path):
        os.remove(assign_path)
