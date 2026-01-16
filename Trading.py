import streamlit as st
import yfinance as yf
import pandas as pd
import os
from datetime import datetime, timedelta

# --- SIDKONFIGURATION ---
st.set_page_config(page_title="Min Trading Bot", layout="wide")

st.title("📈 Min Aktiebevakare & Loggbok")

# --- INSTÄLLNINGAR (SIDEBAR) ---
st.sidebar.header("Inställningar")

# OMXS30 Lista
default_tickers = "ABB.ST, ALFA.ST, ALIV-SDB.ST, ASSA-B.ST, ATCO-A.ST, ATCO-B.ST, AZN.ST, BOL.ST, ELUX-B.ST, ERIC-B.ST, ESSITY-B.ST, EVO.ST, GETI-B.ST, HEXA-B.ST, HM-B.ST, INVE-B.ST, KINV-B.ST, NDA-SE.ST, NIBE-B.ST, SAAB-B.ST, SAND.ST, SBB-B.ST, SCA-B.ST, SEB-A.ST, SHB-A.ST, SINCH.ST, SKF-B.ST, SWED-A.ST, TEL2-B.ST, TELIA.ST, VOLV-B.ST"

user_tickers = st.sidebar.text_area("Bevakningslista:", value=default_tickers, height=150)
dagar_framat = st.sidebar.slider("Rapporter inom dagar:", 1, 60, 25)
starta = st.sidebar.button("Kör Analys")

# --- LOGG-HANTERING (CSV) ---
LOGG_FIL = "mina_affarer.csv"

def ladda_logg():
    if os.path.exists(LOGG_FIL):
        return pd.read_csv(LOGG_FIL)
    else:
        return pd.DataFrame(columns=["Datum", "Ticker", "Pris_vid_Spar", "Typ"])

def spara_till_logg(ticker, pris, typ):
    df = ladda_logg()
    ny_rad = pd.DataFrame({
        "Datum": [datetime.now().strftime("%Y-%m-%d %H:%M")],
        "Ticker": [ticker],
        "Pris_vid_Spar": [pris],
        "Typ": [typ]
    })
    # Slå ihop och spara
    df = pd.concat([df, ny_rad], ignore_index=True)
    df.to_csv(LOGG_FIL, index=False)
    return df

# Knapp för att rensa loggen
if st.sidebar.button("🗑️ Rensa hela loggen"):
    if os.path.exists(LOGG_FIL):
        os.remove(LOGG_FIL)
        st.sidebar.success("Loggen raderad!")

# --- ANALYS-FUNKTION ---
@st.cache_data(ttl=3600)
def hamta_data(ticker_lista, dagar):
    resultat = []
    clean_list = [x.strip().upper() for x in ticker_lista.split(',')]
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    total = len(clean_list)
    
    for i, ticker in enumerate(clean_list):
        progress_bar.progress((i + 1) / total)
        status_text.text(f"Analyserar {ticker}...")
        
        try:
            stock = yf.Ticker(ticker)
            
            # 1. RAPPORTDATUM
            kalender = stock.calendar
            rapport_datum = None
            if kalender is not None and 'Earnings Date' in kalender:
                dates = kalender['Earnings Date']
                if len(dates) > 0:
                    first_date = dates[0]
                    if hasattr(first_date, "date"): rapport_datum = first_date.date()
                    else: rapport_datum = first_date

            if not rapport_datum: continue
                
            idag = datetime.now().date()
            grans = idag + timedelta(days=dagar)
            if not (idag <= rapport_datum <= grans): continue 

            # 2. TREND
            hist = stock.history(period="1y")
            if len(hist) < 200: continue

            nuvarande_pris = hist['Close'].iloc[-1]
            ma200 = hist['Close'].rolling(window=200).mean().iloc[-1]
            distans_ma200 = ((nuvarande_pris - ma200) / ma200) * 100
            
            # 3. FUNDAMENTA
            info = stock.info
            vinstmarginal = info.get('profitMargins', 0)
            if vinstmarginal is None: vinstmarginal = 0
            
            # LÄNKAR
            fi_lank = f"https://marknadssok.fi.se/Publiceringsklient/sv-SE/Search/Search?SearchFunctionType=Insyn&Utgivare={ticker.replace('.ST', '').replace('-B', '').replace('-A', '')}"

            is_buy = (nuvarande_pris > ma200) and (vinstmarginal > 0)
            
            resultat.append({
                "Ticker": ticker,
                "Rapport": rapport_datum,
                "Pris": round(nuvarande_pris, 2),
                "MA200": round(ma200, 2),
                "Trend %": round(distans_ma200, 1),
                "Signal": "KÖP" if is_buy else "AVVAKTA",
                "FI_Lank": fi_lank
            })
            
        except Exception:
            pass
            
    progress_bar.empty()
    status_text.empty()
    return pd.DataFrame(resultat)

# --- HUVUDPROGRAM ---

# 1. Kör Analys
if starta:
    st.session_state['analys_klar'] = True
    st.session_state['df_resultat'] = hamta_data(user_tickers, dagar_framat)

# 2. Visa Resultat (om analys är gjord)
if 'analys_klar' in st.session_state and not st.session_state['df_resultat'].empty:
    df = st.session_state['df_resultat']
    df = df.sort_values(by=["Signal", "Trend %"], ascending=[False, False])
    
    st.subheader("🔎 Analysresultat")
    
    # Loopa igenom resultaten för att skapa knappar
    for index, row in df.iterrows():
        # Färgkodning baserat på signal
        farg = "🟢" if row['Signal'] == "KÖP" else "⚪"
        
        with st.expander(f"{farg} {row['Ticker']} - Pris: {row['Pris']} kr"):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.write(f"**Rapport:** {row['Rapport']}")
                st.write(f"**Trend:** {row['Trend %']}% över MA200")
                st.markdown(f"[🔗 Kolla Insiderköp (FI)]({row['FI_Lank']})")
            
            with col2:
                # UNIK KNAPP för varje aktie
                # Vi använder ticker som nyckel så Streamlit vet vilken knapp som är vilken
                if st.button(f"💾 Spara {row['Ticker']}", key=f"btn_{row['Ticker']}"):
                    spara_till_logg(row['Ticker'], row['Pris'], row['Signal'])
                    st.toast(f"Sparade {row['Ticker']} till loggen!", icon="✅")

else:
    if 'analys_klar' not in st.session_state:
        st.info("Tryck på 'Kör Analys' i menyn för att starta.")

# --- 3. VISA LOGGBOKEN ---
st.divider()
st.subheader("📜 Min Loggbok (Sparade case)")

logg_df = ladda_logg()

if not logg_df.empty:
    # Visa loggen snyggt, senaste överst
    st.dataframe(logg_df.iloc[::-1], use_container_width=True)
    
    # Enkel uträkning (bara exempel, kräver att man uppdaterar dagens pris för att bli "live")
    st.caption("Här ser du de kurser du 'låste fast' när du sparade.")
else:
    st.text("Loggen är tom. Kör en analys och klicka på 'Spara' för att lägga till aktier.")
    
    # Progress bar
    progress_bar = st.progress(0)
    total = len(clean_list)
    
    for i, ticker in enumerate(clean_list):
        # Uppdatera progress bar
        progress_bar.progress((i + 1) / total)
        
        try:
            stock = yf.Ticker(ticker)
            
            # 1. Hämta Rapportdatum
            kalender = stock.calendar
            rapport_datum = None
            
            # Hantera olika format från yfinance
            if kalender is not None and 'Earnings Date' in kalender:
                dates = kalender['Earnings Date']
                if len(dates) > 0:
                    first_date = dates[0]
                    # Omvandla till datumobjekt om det behövs
                    if hasattr(first_date, "date"):
                        rapport_datum = first_date.date()
                    else:
                        rapport_datum = first_date

            # Om inget datum finns, hoppa över
            if not rapport_datum:
                continue
                
            # Kolla om datumet är inom intervallet
            idag = datetime.now().date()
            grans = idag + timedelta(days=dagar_framat)
            
            if not (idag <= rapport_datum <= grans):
                continue # Inte aktuellt datum

            # 2. Hämta Pris och MA200
            hist = stock.history(period="1y")
            if len(hist) < 200:
                continue # För ny aktie

            nuvarande_pris = hist['Close'].iloc[-1]
            ma200 = hist['Close'].rolling(window=200).mean().iloc[-1]
            distans_ma200 = ((nuvarande_pris - ma200) / ma200) * 100
            
            # 3. Hämta Fundamenta
            info = stock.info
            vinstmarginal = info.get('profitMargins', 0)
            if vinstmarginal is None: vinstmarginal = 0
            
            # 4. Bygg status
            trend_signal = "🟢 Upp" if nuvarande_pris > ma200 else "🔴 Ner"
            lonsam_signal = "✅ Ja" if vinstmarginal > 0 else "❌ Nej"
            
            # ÄR DET EN KÖPSIGNAL? (Både trend och vinst)
            is_buy = (nuvarande_pris > ma200) and (vinstmarginal > 0)

            resultat.append({
                "Ticker": ticker,
                "Rapportdatum": rapport_datum,
                "Pris": round(nuvarande_pris, 2),
                "MA200": round(ma200, 2),
                "Distans MA200 (%)": round(distans_ma200, 1),
                "Trend": trend_signal,
                "Lönsam": lonsam_signal,
                "Signal": "KÖP" if is_buy else "AVVAKTA"
            })
            
        except Exception as e:
            st.error(f"Fel vid hämtning av {ticker}: {e}")
            
    return pd.DataFrame(resultat)

# --- HUVUDPROGRAM ---

if starta:
    st.write(f"🔍 Analyserar marknaden... Letar rapporter kommande {dagar_framat} dagarna.")
    
    df = hamta_data(user_tickers)
    
    if not df.empty:
        # Sortera så KÖP-kandidater hamnar överst
        df = df.sort_values(by=["Signal", "Distans MA200 (%)"], ascending=[False, False])
        
        # Visa statistiken
        st.subheader(f"Hittade {len(df)} intressanta aktier")
        
        # Färgläggning av tabellen
        def highlight_buy(row):
            return ['background-color: #d4edda; color: black' if row['Signal'] == 'KÖP' else '' for _ in row]

        st.dataframe(df.style.apply(highlight_buy, axis=1), use_container_width=True)
        
        # Detaljerad vy för köp-kandidater
        st.divider()
        st.subheader("💡 Dina bästa case just nu")
        
        best_cases = df[df['Signal'] == 'KÖP']
        
        if not best_cases.empty:
            for index, row in best_cases.iterrows():
                with st.expander(f"🚀 {row['Ticker']} - Rapport: {row['Rapportdatum']}"):
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Pris", f"{row['Pris']} SEK")
                    col2.metric("Trend vs MA200", f"{row['Distans MA200 (%)']}%")
                    col3.write(f"Denna aktie ligger i en **positiv trend** och bolaget går med vinst. Rapporten släpps snart. Håll koll på volymen!")
        else:
            st.info("Inga solklara köp-case hittades just nu enligt din strategi.")
            
    else:
        st.warning("Inga aktier i din lista har rapport det kommande datumintervallet.")

else:
    st.info("👈 Ändra inställningar i menyn till vänster och tryck på 'Kör Analys'.")
