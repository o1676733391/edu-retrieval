# -*- coding: utf-8 -*-
"""
Streamlit Real Estate Sales Agent Testing Dashboard
====================================================
Interactive testing app for the RealEstateConsultantAgent module & REST API endpoints.
Features:
- Dedicated Sale Agent Consultation Tab (POST /api/houses/consult)
- Semantic Vector Search Tab (POST /api/houses/search)
- Multimodal OCR & Vector Ingestion Tab (POST /api/houses/ingest)
"""

import streamlit as st
import os
import sys
import json
import requests
from pathlib import Path

# Add root directory to sys.path
sys.path.append(str(Path(__file__).parent))

# Set Page Config
st.set_page_config(
    page_title="Chuyên viên Bất động sản AI - Test Dashboard",
    layout="wide"
)

# API Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8080").rstrip("/")

# Custom Styling (Icon-free, professional clean UI)
st.markdown("""
<style>
    .main-title {
        font-size: 2.5rem;
        color: #1F2937;
        font-weight: 700;
        text-align: center;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-size: 1.1rem;
        color: #4B5563;
        text-align: center;
        margin-bottom: 1.8rem;
    }
    .card {
        background-color: #F9FAFB;
        border-radius: 8px;
        padding: 1.2rem;
        border-left: 4px solid #2563EB;
        margin-bottom: 1.2rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .metric-value {
        font-size: 1.3rem;
        font-weight: bold;
        color: #1F2937;
    }
    .metric-label {
        font-size: 0.85rem;
        color: #6B7280;
    }
</style>
""", unsafe_allow_html=True)

# Main Header
st.markdown('<div class="main-title">Real Estate Sales Agent Dashboard</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Hệ thống Tư vấn Bán hàng Bất động sản AI & Multimodal RAG Database</div>', unsafe_allow_html=True)

# Tabs
tab_agent, tab_search, tab_ingest = st.tabs([
    "Tư vấn Bán hàng (Sale Agent)", 
    "Tìm kiếm Bất động sản (Semantic Search)", 
    "Ingest & Phân tích OCR"
])

# ==============================================================================
# TAB 1: SALE AGENT CONSULTATION
# ==============================================================================
with tab_agent:
    st.header("Tư vấn Bán hàng Bất động sản (Sale Agent)")
    st.markdown(
        "Chuyên viên Bán hàng Bất động sản AI am hiểu sâu sắc thông tin chi tiết từng căn nhà có trong cơ sở dữ liệu. "
        "Hỗ trợ giải đáp mọi thắc mắc về vị trí, giá bán, tiện ích, so sánh các căn trước khi khách hàng đưa ra quyết định."
    )

    col1, col2 = st.columns([3, 1])
    with col1:
        consult_query = st.text_input(
            "Câu hỏi / Nhu cầu của khách hàng",
            placeholder="Ví dụ: Tìm cho anh nhà đường Bát Khối tầm 11 tỷ có đỗ ô tô và 5 phòng ngủ",
            value="Tìm nhà riêng đường Bát Khối có 5 phòng ngủ và chỗ đỗ ô tô"
        )
    with col2:
        top_k_agent = st.number_input("Top K Search", min_value=1, max_value=10, value=5, key="top_k_agent")

    col_a, col_b = st.columns(2)
    with col_a:
        collection_agent = st.text_input("Collection Name", value="houses", key="col_agent")
    with col_b:
        conv_id = st.text_input("Conversation ID", value="streamlit_sales_session_001", key="conv_agent")

    if st.button("Gửi câu hỏi tới Sale Agent", use_container_width=True, type="primary"):
        payload = {
            "query": consult_query,
            "collection_name": collection_agent,
            "top_k": top_k_agent,
            "conversation_id": conv_id
        }

        st.subheader("Input JSON (API Request Payload)")
        st.json(payload)

        with st.spinner("Chuyên viên Sales AI đang truy vấn cơ sở dữ liệu và tổng hợp tư vấn..."):
            res_data = None
            try:
                res = requests.post(f"{API_BASE_URL}/api/houses/consult", json=payload, timeout=30)
                if res.status_code == 200:
                    res_data = res.json()
            except Exception:
                # Direct agent fallback if API server is offline
                try:
                    from src.agents.real_estate_agent import RealEstateConsultantAgent
                    agent = RealEstateConsultantAgent(collection_name=collection_agent)
                    res_data = agent.consult(user_query=consult_query, conversation_id=conv_id, top_k=top_k_agent)
                except Exception as local_err:
                    st.error(f"Không thể gọi Agent (API & Local Fallback đều thất bại): {local_err}")

            if res_data:
                st.subheader("Output JSON (API Response Payload)")
                st.json(res_data)

                consultation_data = res_data.get("data", {}).get("consultation_json", {})
                message_text = (
                    res_data.get("message") or 
                    consultation_data.get("message") or 
                    res_data.get("output", "")
                )
                intent_val = (
                    res_data.get("intent") or 
                    consultation_data.get("intent") or 
                    "general_inquiry"
                )
                props_extracted = (
                    consultation_data.get("properties") or 
                    res_data.get("data", {}).get("retrieved_properties", [])
                )
                suggested_qs = consultation_data.get("suggested_questions", [])

                st.markdown("---")
                st.subheader("Phản hồi của Sale Agent (Message Text)")
                st.info(f"Intent nhận diện: {intent_val}")
                st.markdown(message_text)

                if props_extracted:
                    st.subheader("Thông tin Bất động sản liên quan (Properties Data)")
                    st.json(props_extracted)

                if suggested_qs:
                    st.subheader("Gợi ý câu hỏi tiếp theo cho khách hàng (Suggested Follow-up Questions)")
                    for q_idx, q_text in enumerate(suggested_qs):
                        st.markdown(f"**{q_idx + 1}.** {q_text}")


# ==============================================================================
# TAB 2: SEMANTIC VECTOR SEARCH
# ==============================================================================
with tab_search:
    st.header("Tìm kiếm ngữ nghĩa (Semantic Search)")
    st.markdown("Truy vấn trực tiếp Vector DB để lấy danh sách các căn nhà khớp ngữ nghĩa.")

    col1, col2 = st.columns([3, 1])
    with col1:
        search_query = st.text_input(
            "Từ khóa / Nhu cầu tìm kiếm",
            placeholder="Ví dụ: Căn nhà mặt tiền đường Bát Khối",
            value="Tìm nhà riêng đường Bát Khối"
        )
    with col2:
        top_k_search = st.number_input("Top K Results", min_value=1, max_value=20, value=3, key="top_k_search")

    search_collection = st.text_input("Collection Name (Search)", value="houses", key="search_col")

    if st.button("Tìm kiếm ngay", use_container_width=True):
        search_payload = {
            "query": search_query,
            "collection_name": search_collection,
            "top_k": top_k_search
        }

        st.subheader("Input JSON (Request)")
        st.json(search_payload)

        with st.spinner("Đang truy vấn Vector DB..."):
            try:
                res = requests.post(f"{API_BASE_URL}/api/houses/search", json=search_payload, timeout=20)
                if res.status_code == 200:
                    output_data = res.json()
                    st.subheader("Output JSON (Response)")
                    st.json(output_data)

                    results = output_data.get("results", [])
                    if results:
                        st.subheader(f"Tìm thấy {len(results)} kết quả phù hợp:")
                        for idx, item in enumerate(results):
                            meta = item.get("metadata", {})
                            dist = item.get("distance", 0.0)
                            
                            st.markdown(f"""
                            <div class="card">
                                <h3 style='margin-top:0; color:#1F2937;'>#{idx+1} {meta.get('placeName', 'Không có tên')}</h3>
                                <p><b>Địa chỉ:</b> {meta.get('streetName', 'Không rõ')} | <b>Distance:</b> {dist:.4f}</p>
                                <div style='display: flex; gap: 1.5rem; margin-bottom: 1rem; flex-wrap: wrap;'>
                                    <div><span class='metric-label'>Diện tích</span><br><span class='metric-value'>{meta.get('area', 0)} m²</span></div>
                                    <div><span class='metric-label'>Số tầng</span><br><span class='metric-value'>{meta.get('floors', 'N/A')} tầng</span></div>
                                    <div><span class='metric-label'>Phòng ngủ</span><br><span class='metric-value'>{meta.get('bedrooms', 'N/A')} PN</span></div>
                                    <div><span class='metric-label'>Giá rao</span><br><span class='metric-value' style='color:#DC2626;'>{meta.get('offeringPrice', 0)} tỷ</span></div>
                                    <div><span class='metric-label'>Đỗ ô tô</span><br><span class='metric-value'>{ 'Có' if meta.get('hasCarParking') else 'Không' }</span></div>
                                </div>
                                <hr style='border: 0; border-top: 1px solid #E5E7EB; margin: 0.8rem 0;'>
                                <p style='font-style: italic; white-space: pre-line; line-height: 1.5; color:#374151;'>{item.get('unified_description', 'Không có mô tả')}</p>
                            </div>
                            """, unsafe_allow_html=True)
                    else:
                        st.warning("Không tìm thấy kết quả phù hợp.")
                else:
                    st.error(f"Lỗi API: {res.status_code} - {res.text}")
            except Exception as e:
                st.error(f"Lỗi kết nối API: {e}")


# ==============================================================================
# TAB 3: INGEST & MULTIMODAL OCR
# ==============================================================================
with tab_ingest:
    st.header("Quy trình Ingest tự động")
    st.markdown("Phân tích Multimodal OCR ảnh nhà ở, tổng hợp mô tả và đưa vào Vector Database.")

    col1, col2 = st.columns(2)
    with col1:
        json_path = st.text_input("Đường dẫn JSON (Houses JSON Path)", value="data-samples/houses/houses.json")
        img_dir = st.text_input("Thư mục chứa ảnh (Images Directory)", value="data-samples/houses")
    with col2:
        collection_name = st.text_input("Collection Name (Ingest)", value="houses", key="ingest_col")
        batch_size = st.number_input("Batch Size xử lý ảnh", min_value=1, max_value=10, value=5)
        force_ocr = st.checkbox("Bắt buộc chạy lại OCR (Force OCR)", value=False)

    if st.button("Bắt đầu Ingest & Embedding", use_container_width=True):
        ingest_payload = {
            "houses_json_path": json_path,
            "images_dir": img_dir,
            "collection_name": collection_name,
            "force": force_ocr,
            "batch_size": batch_size
        }

        st.subheader("Input JSON (Request)")
        st.json(ingest_payload)

        with st.spinner("Đang xử lý Multimodal OCR và Indexing..."):
            try:
                res = requests.post(f"{API_BASE_URL}/api/houses/ingest", json=ingest_payload, timeout=600)
                if res.status_code == 200:
                    output_data = res.json()
                    st.subheader("Output JSON (Response)")
                    st.json(output_data)
                    st.success(f"Đã xử lý thành công {len(output_data.get('processed_houses', []))} căn nhà!")
                else:
                    st.error(f"Lỗi Ingest: {res.status_code} - {res.text}")
            except Exception as e:
                st.error(f"Lỗi kết nối API: {e}")
