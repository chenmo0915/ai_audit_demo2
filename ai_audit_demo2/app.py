import os
os.environ["PYTHONUTF8"] = "1"  # 强制 Python 使用 UTF-8 编码
import streamlit as st
import PyPDF2
#import pytesseract
#import cv2
import numpy as np
from dashscope import Generation
from dashscope.api_entities.dashscope_response import Role
import json
from datetime import datetime

# DASHSCOPE_API_KEY = "sk-c506656f5b7c4b41a4dc64177f25d27a"

def call_qwen(system_prompt, user_prompt):
    messages = [
        {'role': Role.SYSTEM, 'content': system_prompt},
        {'role': Role.USER, 'content': user_prompt}
    ]
    response = Generation.call(
        model='qwen-max',
        api_key=DASHSCOPE_API_KEY,
        messages=messages,
        temperature=0,
        result_format='message'
    )
    if response.status_code == 200:
        return response.output.choices[0]['message']['content']
    else:
        st.error(f"通义千问调用失败：{response.message}")
        return ""

def read_file(uploaded_file):
    file_type = uploaded_file.type
    if file_type == "text/plain":
        return uploaded_file.read().decode("utf-8")
    elif file_type == "application/pdf":
        reader = PyPDF2.PdfReader(uploaded_file)
        text = ""
        for page in reader.pages:
            text += page.extract_text()
        return text
    elif file_type.startswith("image/"):
        img = cv2.imdecode(np.frombuffer(uploaded_file.read(), np.uint8), cv2.IMREAD_GRAYSCALE)
        _, img_bin = cv2.threshold(img, 127, 255, cv2.THRESH_BINARY)
        text = pytesseract.image_to_string(img_bin, lang="chi_sim+eng")
        return text
    else:
        st.error("不支持的文件格式")
        return ""

def extract_info(file_text, doc_type="发票"):
    system_prompt = f"""你是专业审计数据提取专家，严格从{doc_type}文本中提取结构化信息，仅输出JSON格式，不要额外内容。
提取字段如下：
- 文档编号
- 日期（格式YYYY-MM-DD）
- 交易对方名称
- 金额
- 核心业务描述
- 关联凭证号
字段不存在时填空字符串。
"""
    user_prompt = f"请提取以下{doc_type}的信息：\n{file_text}"
    response_content = call_qwen(system_prompt, user_prompt)
    try:
        return json.loads(response_content)
    except:
        st.error("信息提取失败")
        return {}

def check_consistency(doc1_info, doc2_info):
    issues = []
    try:
        amt1 = float(str(doc1_info.get("价税合计", doc1_info.get("金额", "0"))).replace("¥","").replace(",",""))
        amt2 = float(str(doc2_info.get("金额", "0")).replace("¥","").replace(",",""))
        if abs(amt1 - amt2) > 0.01:
            issues.append(f"金额不一致：{amt1} vs {amt2}")
    except:
        pass
    return issues

def check_anomalies(doc_info):
    anomalies = []
    if not doc_info.get("文档编号"):
        anomalies.append("缺少文档编号")
    if not doc_info.get("日期"):
        anomalies.append("缺少日期")
    return anomalies

st.title("望舒")

uploaded_files = st.file_uploader("上传文件", type=["txt","pdf","png","jpg"], accept_multiple_files=True)

if uploaded_files:
    doc_data = []
    for f in uploaded_files:
        st.write("处理："+f.name)
        txt = read_file(f)
        tp = st.selectbox("类型", ["发票","记账凭证","合同"], key=f.name)
        info = extract_info(txt, tp)
        doc_data.append({"name":f.name, "type":tp, "info":info})
        st.json(info)

    if len(doc_data)>=2:
        st.subheader("一致性检查")
        ret = check_consistency(doc_data[0]["info"], doc_data[1]["info"])
        for r in ret: st.warning(r)

    st.subheader("异常检查")
    for d in doc_data:
        st.write(d["name"])
        anom = check_anomalies(d["info"])
        for a in anom: st.error(a)
if __name__ == "__main__":
    import streamlit.web.cli as stcli
    import sys
    sys.argv = ["streamlit", "run", "app.py", "--server.address", "0.0.0.0", "--server.port", "8080"]
    stcli.main()
