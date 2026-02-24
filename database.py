import json
import uuid
from pathlib import Path
from typing import Dict, List, Optional
from config import DATABASE_DIR
from datetime import datetime, timezone, timedelta

MSK = timezone(timedelta(hours=3))

class Database:
    def __init__(self):
        self.users_file = DATABASE_DIR / "users.json"
        self.sessions_file = DATABASE_DIR / "sessions.json"
        self._init_files()
    
    def _init_files(self):
        if not self.users_file.exists():
            self._save_json(self.users_file, {})
        if not self.sessions_file.exists():
            self._save_json(self.sessions_file, {})
    
    def _load_json(self, filepath: Path) -> dict:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    
    def _save_json(self, filepath: Path, data: dict):
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def get_user(self, user_id: int) -> Optional[Dict]:
        users = self._load_json(self.users_file)
        return users.get(str(user_id))
    
    def save_user(self, user_id: int, username: str, first_name: str):
        users = self._load_json(self.users_file)
        user_key = str(user_id)
        
        if user_key not in users:
            users[user_key] = {
                "user_id": user_id,
                "username": username,
                "first_name": first_name,
                "total_voiced": 0,
                "sessions": []
            }
        else:
            users[user_key]["username"] = username
            users[user_key]["first_name"] = first_name
        
        self._save_json(self.users_file, users)
        return users[user_key]
    
    def create_session(self, user_id: int) -> str:
        session_id = str(uuid.uuid4())
        sessions = self._load_json(self.sessions_file)
        
        sessions[session_id] = {
            "session_id": session_id,
            "user_id": user_id,
            "current_index": 0,
            "voiced_images": [],
            "completed": False,
            "created_at": datetime.now(MSK).isoformat()
        }
        
        self._save_json(self.sessions_file, sessions)
        
        users = self._load_json(self.users_file)
        user_key = str(user_id)
        if user_key in users:
            users[user_key]["sessions"].append(session_id)
            self._save_json(self.users_file, users)
        
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        sessions = self._load_json(self.sessions_file)
        return sessions.get(session_id)
    
    def update_session(self, session_id: str, data: Dict):
        sessions = self._load_json(self.sessions_file)
        if session_id in sessions:
            sessions[session_id].update(data)
            self._save_json(self.sessions_file, sessions)
    
    def add_voiced_image(self, session_id: str, image_index: int, voice_file: str):
        sessions = self._load_json(self.sessions_file)
        if session_id in sessions:
            sessions[session_id]["voiced_images"].append({
                "index": image_index,
                "voice_file": voice_file
            })
            sessions[session_id]["current_index"] = image_index + 1
            self._save_json(self.sessions_file, sessions)
    
    def complete_session(self, session_id: str):
        sessions = self._load_json(self.sessions_file)
        if session_id in sessions:
            sessions[session_id]["completed"] = True
            sessions[session_id]["completed_at"] = datetime.now(MSK).isoformat()
            user_id = sessions[session_id]["user_id"]
            voiced_count = len(sessions[session_id]["voiced_images"])
            
            self._save_json(self.sessions_file, sessions)
            
            users = self._load_json(self.users_file)
            user_key = str(user_id)
            if user_key in users:
                users[user_key]["total_voiced"] += voiced_count
                self._save_json(self.users_file, users)
    
    def get_user_sessions(self, user_id: int) -> List[Dict]:
        users = self._load_json(self.users_file)
        user_key = str(user_id)
        
        if user_key not in users:
            return []
        
        session_ids = users[user_key].get("sessions", [])
        sessions = self._load_json(self.sessions_file)
        
        return [sessions[sid] for sid in session_ids if sid in sessions]
    
    def delete_session(self, session_id: str, user_id: int, voiced_count: int):
        sessions = self._load_json(self.sessions_file)
        
        if session_id in sessions:
            del sessions[session_id]
            self._save_json(self.sessions_file, sessions)
        
        users = self._load_json(self.users_file)
        user_key = str(user_id)
        
        if user_key in users:
            if session_id in users[user_key].get("sessions", []):
                users[user_key]["sessions"].remove(session_id)
            
            users[user_key]["total_voiced"] = max(0, users[user_key].get("total_voiced", 0) - voiced_count)
            self._save_json(self.users_file, users)

db = Database()
