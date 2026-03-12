import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import os
from fpdf import FPDF
import plotly.express as px

# ===================== CONFIGURATION SYSTÈME =====================
st.set_page_config(page_title="NEO-SCHOOL CLOUD PRO", layout="wide", page_icon="🌐")

st.markdown("""
    <style>
    .main { background: #0e1117; }
    [data-testid="stMetricValue"] { font-size: 28px; color: #00ffc8; }
    .stButton>button { border-radius: 10px; height: 3.5em; background-color: #00ffc8; color: black; font-weight: bold; }
    .stExpander { border: 1px solid #30363d; border-radius: 10px; background: #161b22; }
    </style>
    """, unsafe_allow_html=True)

# Connexion à Google Sheets
# L'URL du Sheet doit être configurée dans les "Secrets" de Streamlit Cloud
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    try:
        # On charge la feuille "Eleves" et "Users"
        df_el = conn.read(worksheet="Eleves", ttl=0)
        df_us = conn.read(worksheet="Users", ttl=0)
        return df_el, df_us
    except:
        st.error("Erreur de connexion au Google Sheet. Vérifiez l'URL dans les Secrets.")
        return pd.DataFrame(), pd.DataFrame()

def save_data(df_el=None, df_us=None):
    if df_el is not None:
        conn.update(worksheet="Eleves", data=df_el)
    if df_us is not None:
        conn.update(worksheet="Users", data=df_us)
    st.cache_data.clear()

# ===================== LOGIQUE MÉTIER =====================

def generer_pdf(el):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "RECU DE PAIEMENT - NEO-SCHOOL", ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, f"Eleve : {el['Nom']} {el['Prenom']}", ln=True)
    pdf.cell(0, 10, f"Classe : {el['Classe']}", ln=True)
    pdf.cell(0, 10, f"Montant Verse : {el['Montant_Paye']:,} FCFA", ln=True)
    pdf.cell(0, 10, f"Reste : {el['Reste']:,} FCFA", ln=True)
    path = f"Recu_{el['Nom']}.pdf"
    pdf.output(path)
    return path

# ===================== AUTHENTIFICATION =====================

df_eleves, df_users = load_data()

if "auth" not in st.session_state: st.session_state["auth"] = False

if not st.session_state["auth"]:
    st.title("🔐 Connexion Cloud")
    u = st.text_input("Identifiant")
    p = st.text_input("Mot de passe", type="password")
    if st.button("ACCÉDER"):
        match = df_users[(df_users['username'] == u) & (df_users['password'].astype(str) == p)]
        if not match.empty:
            st.session_state["auth"] = True
            st.session_state["u"] = u
            st.session_state["r"] = match.iloc[0]['role']
            st.rerun()
        else: st.error("Identifiants incorrects.")
else:
    # --- INTERFACE PRINCIPALE ---
    role = st.session_state["r"]
    st.sidebar.title(f"👤 {st.session_state['u']}")
    menu = st.sidebar.radio("Navigation", ["📊 Dashboard", "📝 Inscriptions", "📋 Gestion & Photos", "💰 Caisse"])

    if st.sidebar.button("Déconnexion 🚪"):
        st.session_state["auth"] = False
        st.rerun()

    # --- MODULES ---
    if menu == "📊 Dashboard":
        st.header("📈 Statistiques en Temps Réel")
        c1, c2, c3 = st.columns(3)
        c1.metric("Effectif", len(df_eleves))
        c2.metric("Total Encaissé", f"{df_eleves['Montant_Paye'].sum():,} F")
        c3.metric("Reste à percevoir", f"{df_eleves['Reste'].sum():,} F")
        
        fig = px.pie(df_eleves, values='Montant_Paye', names='Classe', hole=0.4)
        st.plotly_chart(fig, use_container_width=True)

    elif menu == "📝 Inscriptions":
        st.header("📝 Nouvel Élève")
        with st.form("inscr"):
            nom = st.text_input("Nom").upper()
            prenom = st.text_input("Prénom").title()
            classe = st.selectbox("Classe", ["6ème", "5ème", "4ème", "3ème", "2nde", "1ère", "Tle"])
            total = st.number_input("Scolarité Totale", value=400000)
            if st.form_submit_button("Enregistrer sur le Cloud"):
                new_data = pd.DataFrame([{"Nom": nom, "Prenom": prenom, "Classe": classe, 
                                         "Montant_Total": total, "Montant_Paye": 0, "Reste": total}])
                df_eleves = pd.concat([df_eleves, new_data], ignore_index=True)
                save_data(df_el=df_eleves)
                st.success("Synchronisé avec Google Sheets !")

    elif menu == "📋 Gestion & Photos":
        st.header("📋 Registre des Élèves")
        search = st.text_input("🔍 Rechercher...")
        view = df_eleves[df_eleves['Nom'].str.contains(search.upper())] if search else df_eleves
        
        for i, row in view.iterrows():
            with st.expander(f"👤 {row['Nom']} {row['Prenom']} ({row['Classe']})"):
                col1, col2 = st.columns(2)
                col1.write(f"Scolarité : {row['Montant_Total']:,} F")
                col1.write(f"Payé : {row['Montant_Paye']:,} F")
                
                if col2.button("📄 Reçu PDF", key=f"pdf_{i}"):
                    path = generer_pdf(row)
                    with open(path, "rb") as f: st.download_button("Télécharger", f, file_name=path)
                
                if role == "ADMIN":
                    if col2.button("🗑 Supprimer", key=f"del_{i}"):
                        df_eleves = df_eleves.drop(i)
                        save_data(df_el=df_eleves)
                        st.rerun()

    elif menu == "💰 Caisse":
        st.header("💰 Encaissement")
        if not df_eleves.empty:
            sel = st.selectbox("Élève", df_eleves.index, format_func=lambda x: f"{df_eleves.loc[x, 'Nom']} {df_eleves.loc[x, 'Prenom']}")
            m = st.number_input("Somme versée", min_value=0, max_value=int(df_eleves.loc[sel, 'Reste']))
            if st.button("✅ VALIDER LE PAIEMENT"):
                df_eleves.at[sel, 'Montant_Paye'] += m
                df_eleves.at[sel, 'Reste'] = df_eleves.at[sel, 'Montant_Total'] - df_eleves.at[sel, 'Montant_Paye']
                save_data(df_el=df_eleves)
                st.success("Paiement enregistré sur le Cloud !")