import json
from typing import List, Dict, Optional
from config import DATASET_PATH

class DatasetManager:
    def __init__(self):
        self.dataset = self._load_dataset()
    
    def _load_dataset(self) -> List[Dict]:
        with open(DATASET_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def get_image_data(self, index: int) -> Optional[Dict]:
        if 0 <= index < len(self.dataset):
            return self.dataset[index]
        return None
    
    def get_total_images(self) -> int:
        return len(self.dataset)
    
    def search_by_description(self, query: str) -> List[Dict]:
        query_lower = query.lower().strip()
        results = []
        
        # Разбиваем запрос на слова для поиска
        search_terms = query_lower.split()
        
        for idx, item in enumerate(self.dataset):
            score = 0
            comment_lower = item.get("comment", "").lower()
            emotion_lower = item.get("emotion", "").lower()
            mouth_lower = item.get("mouth", "").lower()
            eyes_lower = item.get("eyes", "").lower()
            hands_lower = item.get("hands", "").lower()
            object_lower = item.get("object", "").lower()
            pose_lower = item.get("pose", "").lower()
            
            for term in search_terms:
                if term in comment_lower:
                    score += 10
                if term in emotion_lower or emotion_lower in term:
                    score += 15
                if term in mouth_lower:
                    score += 4
                if term in eyes_lower:
                    score += 4
                if term in hands_lower:
                    score += 3
                if term in object_lower:
                    score += 6
                if term in pose_lower:
                    score += 3
            
            if score > 0:
                results.append({
                    "index": idx,
                    "score": score,
                    "data": item
                })
        
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:10]
    
    def get_file_id(self, index: int) -> Optional[str]:
        data = self.get_image_data(index)
        if data:
            return data.get("file_id")
        return None
    
    def format_image_description(self, index: int) -> str:
        data = self.get_image_data(index)
        if not data:
            return ""
        
        comment = data.get("comment", "")
        return f"🐹 {comment}"

dataset_manager = DatasetManager()
