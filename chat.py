import sys
from pathlib import Path

# Add src to python path if needed
sys.path.append(str(Path(__file__).parent))

from src.vector_store.search import book_knowledge_search
from src import config

def check_database() -> bool:
    """
    Checks if Vector DB exists and contains indexed pages.
    """
    try:
        from src.vector_store.client import get_vector_store
        vector_store = get_vector_store("math")
        docs = vector_store.get_all()
        return len(docs.get("ids", [])) > 0
    except Exception as e:
        print(f"[Warning] Database check failed: {e}")
        return False

def print_welcome():
    print("=" * 60)
    print("       CÔNG CỤ TRA CỨU RAG SGK TOÁN 3 - KẾT NỐI TRI THỨC")
    print("=" * 60)
    print("Chào mừng bạn! Đây là công cụ tra cứu cơ sở kiến thức SGK Toán 3.")
    print("Công cụ này giúp bạn tìm kiếm các bài học, phép tính, và bài tập")
    print("phù hợp nhất từ cơ sở dữ liệu Vector.")
    print("\n* Hướng dẫn:")
    print("  - Đặt câu hỏi trực tiếp (Ví dụ: 'Giải bài 2 trang 15 tập 1')")
    print("  - Gõ '/help' để xem hướng dẫn.")
    print("  - Gõ '/exit' hoặc '/quit' để thoát.")
    print("=" * 60)

def main():
    # 1. Check API Key
    if not config.GEMINI_API_KEY and not config.OPENAI_API_KEY:
        print("❌ Lỗi: Chưa cấu hình khóa API trong hệ thống.")
        print("Vui lòng sao chép tệp '.env.template' thành '.env' và điền khóa API.")
        sys.exit(1)
        
    # 2. Check Database Population
    if not check_database():
        print("⚠️ Cảnh báo: Cơ sở dữ liệu Vector chưa có dữ liệu sách.")
        print("Vui lòng chạy lệnh sau để nạp dữ liệu sách giáo khoa vào cơ sở dữ liệu:")
        print("  python run_ingest.py")
        print("\nBạn có muốn tiếp tục chạy thử tìm kiếm không? (y/n): ", end="")
        choice = input().strip().lower()
        if choice != 'y':
            sys.exit(0)

    # 3. Initialize RAG Search
    try:
        print("🔄 Đang khởi động Công cụ Tra cứu RAG...")
        from src.vector_store.client import get_vector_store
        vector_store = get_vector_store("math")
        print("✅ Cơ sở dữ liệu đã sẵn sàng!")
    except Exception as e:
        print(f"❌ Khởi tạo cơ sở dữ liệu thất bại: {e}")
        sys.exit(1)

    # 4. Chat Loop
    while True:
        try:
            print("\n🧑 Truy vấn: ", end="")
            user_input = input().strip()
            
            if not user_input:
                continue
                
            if user_input.lower() in ['/exit', '/quit']:
                print("Tạm biệt! Chúc bạn học tập tốt! 🌟")
                break
                
            if user_input.lower() == '/help':
                print("\n📖 Hướng dẫn sử dụng:")
                print("- Hãy đưa ra câu hỏi cụ thể về toán lớp 3.")
                print("- Mẹo: Thêm số trang và tập để trợ lý tìm kiếm chính xác hơn.")
                print("  Ví dụ: 'Bài 1 trang 24 tập 2 làm thế nào?'")
                print("- Các lệnh hệ thống:")
                print("  /help : Xem hướng dẫn này.")
                print("  /exit hoặc /quit : Thoát chương trình.")
                continue
                
            print("🔍 Đang tra cứu cơ sở dữ liệu sách giáo khoa... 💭")
            results = book_knowledge_search(user_input, field="math", user_role="student")
            
            if not results:
                print("\n❌ Không tìm thấy nội dung phù hợp trong sách giáo khoa.")
            else:
                print(f"\n✅ Tìm thấy {len(results)} trang tài liệu phù hợp:")
                for idx, res in enumerate(results):
                    meta = res["metadata"]
                    print("-" * 50)
                    print(f"Kết quả {idx + 1}:")
                    print(f"  - Bài học: {meta.get('lesson_name', 'Chưa rõ')}")
                    print(f"  - Vị trí: Trang {meta.get('physical_page', 'Chưa rõ')} (Tập {meta.get('volume', 'Chưa rõ')})")
                    print(f"  - Quyền truy cập: {meta.get('visibility', 'public')}")
                    if "description" in meta:
                        print(f"  - Mô tả: {meta['description']}")
                    if "file_name" in meta:
                        print(f"  - File nguồn: {meta['file_name']}")
                    print(f"  - Nội dung trích xuất:\n{res['text']}")
                print("-" * 50)
            
        except KeyboardInterrupt:
            print("\nTạm biệt! Chúc bạn học tập tốt! 🌟")
            break
        except Exception as e:
            print(f"\n❌ Đã xảy ra lỗi: {e}")

if __name__ == "__main__":
    main()
