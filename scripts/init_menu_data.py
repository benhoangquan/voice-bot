"""Initialize menu data in RAG database"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.rag.menu_rag import MenuRAG, create_sample_menu_data
from src.config import Config


def main():
    """Initialize menu data"""
    print("Initializing menu RAG database...")
    
    # Create sample menu data if it doesn't exist
    if not os.path.exists(Config.MENU_DATA_PATH):
        print(f"Creating sample menu data at {Config.MENU_DATA_PATH}")
        create_sample_menu_data(Config.MENU_DATA_PATH)
    
    # Initialize RAG
    menu_rag = MenuRAG(Config.CHROMA_DB_PATH)
    
    # Load menu data
    print(f"Loading menu data from {Config.MENU_DATA_PATH}")
    menu_rag.load_from_file(Config.MENU_DATA_PATH)
    
    # Test query
    print("\nTesting menu query...")
    results = menu_rag.query("What vegetarian options do you have?")
    print(f"Found {len(results)} results:")
    for result in results:
        print(f"  - {result['name']}: ${result['price']:.2f}")
    
    print("\nMenu RAG database initialized successfully!")


if __name__ == "__main__":
    main()
