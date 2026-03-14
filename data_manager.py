import os
import json
import pandas as pd
import uuid
from datetime import datetime

DATA_DIR = "data"
SHIFTS_DIR = os.path.join(DATA_DIR, "shifts")
ASSIGNMENTS_DIR = os.path.join(DATA_DIR, "assignments")
METADATA_FILE = os.path.join(DATA_DIR, "metadata.json")

os.makedirs(SHIFTS_DIR, exist_ok=True)
os.makedirs(ASSIGNMENTS_DIR, exist_ok=True)

def get_metadata():
    if not os.path.exists(METADATA_FILE):
        return []
    with open(METADATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_metadata(metadata):
    with open(METADATA_FILE, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

def generate_import_id():
    return datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + str(uuid.uuid4())[:8]

def save_uploaded_shifts(import_id, df_analytics):
    csv_path = os.path.join(SHIFTS_DIR, f"{import_id}.csv")
    df_analytics.to_csv(csv_path, sep=';', index=False)
    metadata = get_metadata()
    metadata.append({
        "import_id": import_id,
        "filename": os.path.basename(csv_path),
        "uploaded_at": datetime.now().isoformat(),
        "status": "draft",
        "description": ""
    })
    save_metadata(metadata)

def load_shifts(import_id, with_assignments=False):
    csv_path = os.path.join(SHIFTS_DIR, f"{import_id}.csv")
    if not os.path.exists(csv_path):
        return None
    df = pd.read_csv(csv_path, delimiter=';')
    df.columns = df.columns.str.strip()
    # Разворачиваем Count
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
    return shifts_df

def save_assignments(import_id, shifts_df):
    assignments = {}
    for _, row in shifts_df.iterrows():
        if row['Employee']:
            assignments[int(row['shift_id'])] = row['Employee']
    assign_path = os.path.join(ASSIGNMENTS_DIR, f"{import_id}.json")
    with open(assign_path, "w", encoding="utf-8") as f:
        json.dump(assignments, f, indent=2, ensure_ascii=False)

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
    csv_path = os.path.join(SHIFTS_DIR, f"{import_id}.csv")
    if os.path.exists(csv_path):
        os.remove(csv_path)
    assign_path = os.path.join(ASSIGNMENTS_DIR, f"{import_id}.json")
    if os.path.exists(assign_path):
        os.remove(assign_path)
    metadata = get_metadata()
    metadata = [item for item in metadata if item['import_id'] != import_id]
    save_metadata(metadata)
