"""RAG system for restaurant menu queries"""

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any, Optional
import json
import os


class MenuRAG:
    """RAG system for querying menu items"""
    
    def __init__(self, db_path: str = "./chroma_db", collection_name: str = "menu_items"):
        self.db_path = db_path
        self.collection_name = collection_name
        
        # Initialize ChromaDB
        self.client = chromadb.PersistentClient(
            path=db_path,
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Initialize embedding model
        self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )
    
    def add_menu_items(self, menu_items: List[Dict[str, Any]]):
        """Add menu items to the vector database"""
        if not menu_items:
            return
        
        # Prepare documents, metadata, and IDs
        documents = []
        metadatas = []
        ids = []
        
        for item in menu_items:
            # Create searchable text
            text = f"{item.get('name', '')} {item.get('description', '')} {item.get('category', '')}"
            if item.get('dietary'):
                text += " " + " ".join(item.get('dietary', []))
            
            documents.append(text)
            metadatas.append({
                "name": item.get("name", ""),
                "description": item.get("description", ""),
                "price": str(item.get("price", 0)),
                "category": item.get("category", ""),
                "dietary": json.dumps(item.get("dietary", [])),
                "allergens": json.dumps(item.get("allergens", [])),
                "available": str(item.get("available", True)),
            })
            ids.append(f"item_{item.get('name', '').lower().replace(' ', '_')}")
        
        # Add to collection
        self.collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
    
    def query(self, question: str, n_results: int = 3) -> List[Dict[str, Any]]:
        """Query menu items based on question"""
        results = self.collection.query(
            query_texts=[question],
            n_results=n_results
        )
        
        # Format results
        formatted_results = []
        if results['documents'] and results['documents'][0]:
            for i, doc in enumerate(results['documents'][0]):
                metadata = results['metadatas'][0][i] if results['metadatas'] else {}
                formatted_results.append({
                    "name": metadata.get("name", ""),
                    "description": metadata.get("description", ""),
                    "price": float(metadata.get("price", 0)),
                    "category": metadata.get("category", ""),
                    "dietary": json.loads(metadata.get("dietary", "[]")),
                    "allergens": json.loads(metadata.get("allergens", "[]")),
                    "available": metadata.get("available", "True") == "True",
                    "relevance_score": results['distances'][0][i] if results['distances'] else 0,
                })
        
        return formatted_results
    
    def load_from_file(self, file_path: str):
        """Load menu items from JSON file"""
        with open(file_path, 'r') as f:
            data = json.load(f)
            if 'items' in data:
                self.add_menu_items(data['items'])
            else:
                self.add_menu_items(data)


def create_sample_menu_data(file_path: str = "data/sample_menu.json"):
    """Create sample menu data"""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    menu_data = {
        "items": [
            {
                "name": "Grilled Salmon",
                "description": "Fresh Atlantic salmon with lemon butter sauce, served with seasonal vegetables and rice",
                "price": 28.99,
                "category": "Main Course",
                "dietary": ["gluten-free", "pescatarian"],
                "allergens": ["fish"],
                "available": True
            },
            {
                "name": "Ribeye Steak",
                "description": "12oz prime ribeye, cooked to perfection, served with garlic mashed potatoes and asparagus",
                "price": 34.99,
                "category": "Main Course",
                "dietary": [],
                "allergens": [],
                "available": True
            },
            {
                "name": "Caesar Salad",
                "description": "Crisp romaine lettuce with parmesan cheese, croutons, and house-made Caesar dressing",
                "price": 12.99,
                "category": "Salad",
                "dietary": ["vegetarian"],
                "allergens": ["dairy", "gluten"],
                "available": True
            },
            {
                "name": "Margherita Pizza",
                "description": "Classic pizza with fresh mozzarella, tomato sauce, and basil",
                "price": 16.99,
                "category": "Pizza",
                "dietary": ["vegetarian"],
                "allergens": ["dairy", "gluten"],
                "available": True
            },
            {
                "name": "Chocolate Lava Cake",
                "description": "Warm chocolate cake with molten center, served with vanilla ice cream",
                "price": 9.99,
                "category": "Dessert",
                "dietary": ["vegetarian"],
                "allergens": ["dairy", "eggs", "gluten"],
                "available": True
            },
            {
                "name": "Vegetarian Pasta",
                "description": "Fresh pasta with seasonal vegetables, olive oil, and herbs",
                "price": 18.99,
                "category": "Main Course",
                "dietary": ["vegetarian", "vegan"],
                "allergens": ["gluten"],
                "available": True
            },
            {
                "name": "Chicken Parmesan",
                "description": "Breaded chicken breast with marinara sauce and mozzarella, served with pasta",
                "price": 22.99,
                "category": "Main Course",
                "dietary": [],
                "allergens": ["dairy", "eggs", "gluten"],
                "available": True
            },
            {
                "name": "Tiramisu",
                "description": "Classic Italian dessert with coffee-soaked ladyfingers and mascarpone",
                "price": 8.99,
                "category": "Dessert",
                "dietary": ["vegetarian"],
                "allergens": ["dairy", "eggs", "gluten"],
                "available": True
            }
        ]
    }
    
    with open(file_path, 'w') as f:
        json.dump(menu_data, f, indent=2)
    
    return menu_data
