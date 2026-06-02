import streamlit as st

st.set_page_config(page_title="Teste Meishu-Sama", layout="wide")
st.title("🕊️ Teste do Assistente")

st.write("Se você está vendo esta mensagem, o Streamlit está funcionando corretamente no Render.")

if st.button("Clique aqui"):
    st.success("Botão funcionou!")
