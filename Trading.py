import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

# --- SIDKONFIGURATION ---
st.set_page_config(page_title="Min Trading Bot", layout="wide")

st.title("📈 Min Aktiebevakare: Rapporter & Trend")
st.markdown("""
Denna app skannar dina favoritaktier för att hitta:
1. **Rapporter** som släpps snart.
2. **Positiv trend** (Pris > MA200).
3. **Lönsamhet** (Vinstmarginal > 0).
""")

# --- SIDOFÄLT (INPUT) ---
st.sidebar.header("Inställningar")

# Standardlista med aktier
default_tickers = "ABB.ST, ALFA.ST, ALIV-SDB.ST, ASSA-B.ST, ATCO-A.ST, ATCO-B.ST, AZN.ST, BOL.ST, ELUX-B.ST, ERIC-B.ST, ESSITY-B.ST, EVO.ST, GETI-B.ST, HEXA-B.ST, HM-B.ST, INVE-B.ST, KINV-B.ST, NDA-SE.ST, NIBE-B.ST, SAAB-B.ST, SAND.ST, SBB-B.ST, SCA-B.ST, SEB-A.ST, SHB-A.ST, SINCH.ST, SKF-B.ST, SWED-A.ST, TEL2-B.ST, TELIA.ST, VOLV-B.ST"
user_tickers = st.sidebar.text_area("Ange aktier (separera med komman):", value=default_tickers, height=150)

dagar_framat = st.sidebar.slider("Sök rapporter inom antal dagar:", min_value=1, max_value=60, value=21)

# Knapp för att starta
starta = st.sidebar.button("Kör Analys")

# --- FUNKTIONER ---

@st.cache_data(ttl=3600) # Sparar data i 1 timme så det går snabbare
def hamta_data(ticker_lista):
    resultat = []
    
    # Rensa listan från mellanslag och gör stora bokstäver
    clean_list = [x.strip().upper() for x in ticker_lista.split(',')]
    
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
