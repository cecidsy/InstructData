"""ChatBI 对话、图表及工作簿下载。"""

import streamlit as st

from .chat import ChatResult, ModelConfig, environment_model, execute, model_plan
from .model_settings import load_model_settings, save_model_settings


def model_settings():
    read_error = False
    try:
        config = load_model_settings() or environment_model()
    except (OSError, ValueError):
        config = None
        read_error = True
    with st.sidebar.expander("大模型设置", expanded=config is None):
        with st.form("chat_model_settings"):
            url = st.text_input(
                "对话接口 URL",
                value=config.url if config else "",
                placeholder="https://model.example/v1/chat/completions",
                help="填写完整的 HTTP 对话接口地址。常见路径以 /chat/completions 结尾。",
            )
            name = st.text_input(
                "模型 ID", value=config.name if config else "",
                help="复制服务方控制台中的 API 模型 ID，保留原大小写。",
            )
            key = st.text_input(
                "API 密钥", type="password",
                help="密钥会以明文保存在本机。接口和模型不变时，留空会沿用已有密钥。",
            )
            saved = st.form_submit_button("保存模型设置")
        if read_error and not saved:
            st.warning("无法读取模型配置。请检查配置文件或重新填写。")
        if saved:
            try:
                url, name = url.strip(), name.strip()
                if config and (url, name) == (config.url, config.name) and not key:
                    key = config.api_key
                updated = ModelConfig(url, name, key.strip())
                save_model_settings(updated)
                config = updated
                st.success("模型设置已保存，下次启动会自动读取。")
            except ValueError as error:
                st.error(str(error))
            except OSError:
                st.error("无法写入本地模型配置，请检查项目目录的写入权限。")
        st.caption(f"已配置：{config.name}" if config else "尚未配置模型")
    return config


def show_result(result, index):
    with st.chat_message("assistant"):
        st.text(result.message)
        if result.preview is not None and not result.preview.empty:
            st.caption("数据样例")
            st.dataframe(result.preview, hide_index=True)
        if result.table is not None and not result.table.empty:
            st.dataframe(result.table.head(100), hide_index=True)
            if len(result.table) > 100:
                st.caption("表格预览前 100 行。")
            if result.chart:
                chart = result.table.head(100)
                if len(result.table) > len(chart):
                    st.caption("图表展示结果中的前 100 行。")
                x, y = list(chart.columns)
                draw = {"bar": st.bar_chart, "line": st.line_chart, "scatter": st.scatter_chart}[result.chart]
                draw(chart, x=x, y=y)
        if result.download is not None:
            st.download_button(
                "下载处理结果 (.xlsx)", result.download, file_name="处理结果.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"chat_download_{index}",
            )


def show_chat(data, source_id, excel):
    config = model_settings()
    if st.session_state.get("chat_source") != source_id:
        st.session_state.chat_source = source_id
        st.session_state.chat_history = []
        st.session_state.chat_previous = None

    history = st.session_state.chat_history
    if not history:
        if data is None:
            st.info("从侧栏上传 Excel 或连接数据库并读取一张表，就可以开始问数。")
        elif config:
            st.caption("可以先问「这张表有什么数据？」")
    if config is None:
        st.warning("请先在侧栏“大模型设置”填写接口地址和模型名称。")

    question = st.chat_input("输入问题或 Excel 处理指令", disabled=config is None, max_chars=600)
    if question and config is not None:
        with st.spinner("正在请求模型…"):
            try:
                plan = model_plan(question, data, st.session_state.chat_previous, config=config,
                                  previous_question=history[-1][0] if history else None, excel=excel and data is not None)
                result = execute(plan, data, excel)
                if plan["operation"] != "reply":
                    st.session_state.chat_previous = plan
            except (ValueError, TypeError, OverflowError) as error:
                result = ChatResult(str(error))
            history.append((question, result))
            del history[:-12]
    for index, (prompt, result) in enumerate(history):
        with st.chat_message("user"):
            st.text(prompt)
        show_result(result, index)
