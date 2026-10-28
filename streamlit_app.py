import re
from datetime import date

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import MinMaxScaler

st.set_page_config(page_title="PT. XYZ | Customer Intelligence", page_icon="🚚", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap');
html, body, [class*="css"] {font-family:'DM Sans',sans-serif}
.stApp {background:#F5F7FA;color:#1B2A3B}
[data-testid="stSidebar"] {background:#0A1B30}
[data-testid="stSidebar"] * {color:#EAF0F7}
.hero {background:linear-gradient(112deg,#10253F,#173957 70%,#214A6C);border-radius:18px;padding:28px 32px;color:white;margin:8px 0 24px}
.hero small {color:#FFAD60;font-weight:800;letter-spacing:1.5px}
.hero h1 {color:white;font-family:Manrope,sans-serif;font-size:34px;margin:10px 0}
.hero h1 span {color:#FF9B43}
.hero p {color:#C2D0DE;margin:0}
div[data-testid="stMetric"] {background:white;padding:16px;border:1px solid #E7ECF2;border-radius:14px}
h1,h2,h3 {font-family:Manrope,sans-serif}
</style>
""", unsafe_allow_html=True)

def norm(x):
    return re.sub(r"[\s_\-./()]+", "", str(x).lower().strip())

def guess(cols, hints):
    for h in hints:
        for c in cols:
            if norm(c) == norm(h): return c
    for h in hints:
        for c in cols:
            if norm(h) in norm(c): return c
    return cols[0]

def money(s):
    def parse(v):
        if pd.isna(v): return np.nan
        if isinstance(v, (int,float,np.number)): return float(v)
        x = re.sub(r"(?i)rp|\s|[^\d,.\-]", "", str(v))
        if not x: return np.nan
        if "," in x and "." in x:
            x = x.replace(".","").replace(",",".") if x.rfind(",") > x.rfind(".") else x.replace(",","")
        elif "," in x:
            x = x.replace(",","") if len(x.split(",")[-1]) == 3 else x.replace(",",".")
        elif re.fullmatch(r"-?\d{1,3}(\.\d{3})+",x): x=x.replace(".","")
        try: return float(x)
        except ValueError: return np.nan
    return s.map(parse)

def idr(v):
    if pd.isna(v): return "—"
    if abs(v)>=1e9: return "Rp "+f"{v/1e9:.1f}".replace(".",",")+" M"
    if abs(v)>=1e6: return "Rp "+f"{v/1e6:.1f}".replace(".",",")+" jt"
    return "Rp "+f"{v:,.0f}".replace(",", ".")

def label_cluster(row, means):
    r,f,m=means
    active=row["R rata-rata"] <= r
    frequent=row["F rata-rata"] >= f
    valuable=row["M rata-rata"] >= m
    if active and frequent and valuable: return "Pelanggan bernilai tinggi"
    if active and frequent: return "Pelanggan loyal dan aktif"
    if not active and valuable: return "Bernilai tinggi, perlu perhatian"
    if not active and not frequent: return "Berisiko tidak aktif"
    if active and not frequent: return "Pelanggan berkembang"
    if valuable: return "Kontributor pendapatan"
    return "Perlu pengembangan"

def treatment(label):
    if label == "Pelanggan bernilai tinggi":
        return "Pertahankan pelanggan bernilai tinggi", ["Komunikasi personal dan evaluasi kebutuhan pengiriman.","Pantau kualitas layanan serta tindak lanjuti keluhan.","Pertimbangkan benefit loyalitas sesuai kebijakan perusahaan."]
    if "Berisiko" in label or "perlu perhatian" in label:
        return "Reaktivasi pelanggan", ["Hubungi pelanggan untuk memahami hambatan penggunaan layanan.","Kirim pengingat atau penawaran relevan jika sesuai kebijakan.","Pantau apakah pelanggan kembali bertransaksi."]
    if "loyal" in label or "berkembang" in label:
        return "Tingkatkan pemesanan berulang", ["Tanyakan rencana pengiriman periode berikutnya.","Tawarkan informasi layanan yang relevan dengan pola transaksi.","Evaluasi frekuensi pemesanan pada periode berikutnya."]
    return "Kembangkan hubungan pelanggan", ["Lakukan follow-up untuk memahami kebutuhan pengiriman.","Berikan informasi layanan yang relevan dan jelas.","Tinjau perubahan RFM pada analisis berikutnya."]

st.sidebar.markdown("# 🚚 PT. XYZ")
st.sidebar.caption("CUSTOMER INTELLIGENCE")
page=st.sidebar.radio("WORKSPACE",["Ringkasan","Segmentasi Pelanggan","Customer Treatment"])
st.sidebar.info("Unggah data transaksi untuk membentuk segmen pelanggan.")

st.markdown('<div class="hero"><small>CUSTOMER RELATIONSHIP MANAGEMENT</small><h1>Customer Intelligence<span>.</span></h1><p>Ubah data transaksi menjadi strategi pelanggan yang lebih tepat sasaran dengan RFM dan K-Means.</p></div>',unsafe_allow_html=True)
st.subheader("Upload data transaksi")
uploaded=st.file_uploader("Pilih file Excel atau CSV",type=["xlsx","xls","csv"])

if uploaded:
    try:
        raw=pd.read_csv(uploaded) if uploaded.name.lower().endswith(".csv") else pd.read_excel(uploaded)
        if raw.empty: st.error("File kosong.")
        else:
            st.success(f"File terbaca: {uploaded.name} · {len(raw):,} baris · {len(raw.columns)} kolom".replace(",","."))
            cols=list(raw.columns)
            a,b=st.columns(2)
            with a:
                customer=st.selectbox("Kolom shipper/pelanggan",cols,index=cols.index(guess(cols,["shipper","customer","pelanggan","namacustomer","namapelanggan","customerid"])))
                invoice=st.selectbox("Kolom nomor invoice",cols,index=cols.index(guess(cols,["invoice","noinvoice","nomorinvoice","invoicenumber","faktur"])))
            with b:
                dt=st.selectbox("Kolom tanggal invoice",cols,index=cols.index(guess(cols,["tanggalinvoice","invoicedate","tanggal","date","tgl"])))
                cost=st.selectbox("Kolom shipping cost",cols,index=cols.index(guess(cols,["shippingcost","biayapengiriman","cost","dpp","revenue","amount"])))
            c,d=st.columns(2)
            with c: snapshot=st.date_input("Tanggal analisis",value=date.today())
            with d: k=st.selectbox("Jumlah cluster K",[2,3,4,5,6],index=1)
            if st.button("✨ Analisis data pelanggan",type="primary",use_container_width=True):
                with st.spinner("Menghitung RFM dan menjalankan K-Means..."):
                    data=raw[[customer,invoice,dt,cost]].copy()
                    data.columns=["Pelanggan","Invoice","Tanggal","Cost"]
                    data["Pelanggan"]=data["Pelanggan"].astype("string").str.strip()
                    data["Invoice"]=data["Invoice"].astype("string").str.strip()
                    data["Tanggal"]=pd.to_datetime(data["Tanggal"],errors="coerce",dayfirst=True)
                    data["Cost"]=money(data["Cost"])
                    data=data.dropna(subset=["Pelanggan","Tanggal","Cost"])
                    data=data[data["Pelanggan"].ne("") & data["Pelanggan"].ne("<NA>")]
                    if data.empty: st.error("Tidak ada baris valid. Periksa pemetaan kolom dan format data.")
                    else:
                        data["Invoice"]=data["Invoice"].replace({"":"", "<NA>":np.nan}).fillna(data.index.astype(str))
                        rfm=data.groupby("Pelanggan").agg(**{"Transaksi":("Invoice","nunique"),"Monetary":("Cost","sum"),"Tanggal terakhir":("Tanggal","max")}).reset_index()
                        rfm["Recency (hari)"]=(pd.Timestamp(snapshot)-rfm["Tanggal terakhir"].dt.normalize()).dt.days.clip(lower=0)
                        features=rfm[["Recency (hari)","Transaksi","Monetary"]].copy()
                        scaled=MinMaxScaler().fit_transform(features)
                        scaled[:,0]=1-scaled[:,0]
                        if len(rfm)<k: st.error(f"Jumlah pelanggan unik ({len(rfm)}) harus minimal sama dengan K ({k}).")
                        else:
                            model=KMeans(n_clusters=k,random_state=42,n_init=10)
                            rfm["Cluster"]=model.fit_predict(scaled)
                            means=(rfm["Recency (hari)"].mean(),rfm["Transaksi"].mean(),rfm["Monetary"].mean())
                            rows=[]
                            for cid in range(k):
                                part=rfm[rfm["Cluster"]==cid]
                                rows.append({"Cluster":cid+1,"Jumlah pelanggan":len(part),"R rata-rata":part["Recency (hari)"].mean() if len(part) else 0,"F rata-rata":part["Transaksi"].mean() if len(part) else 0,"M rata-rata":part["Monetary"].mean() if len(part) else 0})
                            clusters=pd.DataFrame(rows)
                            clusters["Karakteristik"]=clusters.apply(lambda x:label_cluster(x,means),axis=1)
                            st.session_state["rfm"]=rfm
                            st.session_state["clusters"]=clusters
                            st.session_state["transactions"]=data
                            st.session_state["snapshot"]=snapshot
                            st.session_state["silhouette"]=None
                            try:
                                if len(rfm)>k and rfm["Cluster"].nunique()>1 and len(rfm)<=12000:
                                    X,y=scaled,rfm["Cluster"].to_numpy()
                                    if len(rfm)>2500:
                                        rng=np.random.default_rng(42); idx=rng.choice(len(rfm),2500,replace=False); X,y=scaled[idx],y[idx]
                                    if len(np.unique(y))>1: st.session_state["silhouette"]=silhouette_score(X,y)
                            except Exception: pass
                            st.success("Analisis selesai. Pilih halaman di menu kiri untuk melihat hasil.")

if "rfm" not in st.session_state:
    st.subheader("Ringkasan analisis")
    x1,x2,x3,x4=st.columns(4)
    x1.metric("Total pelanggan","—"); x2.metric("Total transaksi","—"); x3.metric("Total shipping cost","—"); x4.metric("Jumlah segmen","—")
    st.info("Dashboard masih kosong. Upload file berisi shipper, nomor invoice, tanggal invoice, dan shipping cost.")
else:
    rfm=st.session_state["rfm"]; clusters=st.session_state["clusters"]; transactions=st.session_state["transactions"]
    if page=="Ringkasan":
        st.subheader("Ringkasan analisis")
        a,b,c,d=st.columns(4)
        a.metric("Total pelanggan",f"{len(rfm):,}".replace(",","."))
        b.metric("Transaksi valid",f"{len(transactions):,}".replace(",","."))
        c.metric("Total shipping cost",idr(transactions["Cost"].sum()))
        d.metric("Jumlah segmen",str((clusters["Jumlah pelanggan"]>0).sum()))
        l,r=st.columns(2)
        with l:
            st.markdown("#### Distribusi pelanggan")
            fig=px.pie(clusters,names=clusters["Cluster"].map(lambda x:f"Cluster {x}"),values="Jumlah pelanggan",hole=.62,color_discrete_sequence=[BLUE for BLUE in ["#3C78E8","#FF8A24","#1EAA78","#8B67D5","#3E9BB8","#D45D82"]])
            fig.update_layout(margin=dict(t=15,b=10,l=5,r=5),legend_title_text="")
            st.plotly_chart(fig,use_container_width=True)
        with r:
            st.markdown("#### Jumlah pelanggan per cluster")
            fig=px.bar(clusters,x=clusters["Cluster"].map(lambda x:f"Cluster {x}"),y="Jumlah pelanggan",color=clusters["Cluster"].map(lambda x:f"Cluster {x}"),color_discrete_sequence=["#3C78E8","#FF8A24","#1EAA78","#8B67D5","#3E9BB8","#D45D82"])
            fig.update_layout(showlegend=False,margin=dict(t=15,b=10,l=5,r=5),xaxis_title="",yaxis_title="Pelanggan")
            st.plotly_chart(fig,use_container_width=True)
        score=st.session_state.get("silhouette")
        if score is None: st.warning("Silhouette Score tidak tersedia untuk hasil ini atau ukuran data ini.")
        else: st.metric("Silhouette Score",f"{score:.3f}")
        st.caption(f"Tanggal analisis: {st.session_state['snapshot'].strftime('%d-%m-%Y')}. Recency rendah berarti transaksi lebih baru.")
    elif page=="Segmentasi Pelanggan":
        st.subheader("Karakteristik segmen")
        display=clusters.copy()
        display["Rata-rata Monetary"]=display["M rata-rata"].map(idr)
        st.dataframe(display[["Cluster","Jumlah pelanggan","R rata-rata","F rata-rata","Rata-rata Monetary","Karakteristik"]].rename(columns={"R rata-rata":"Recency rata-rata (hari)","F rata-rata":"Frequency rata-rata"}),use_container_width=True,hide_index=True)
        st.markdown("#### Daftar pelanggan")
        search=st.text_input("Cari pelanggan")
        view=rfm.copy()
        if search: view=view[view["Pelanggan"].astype(str).str.contains(search,case=False,na=False)]
        view=view.sort_values("Monetary",ascending=False)
        st.dataframe(view[["Pelanggan","Recency (hari)","Transaksi","Monetary","Cluster"]],use_container_width=True,hide_index=True)
        st.download_button("⬇ Unduh hasil segmentasi CSV",view.to_csv(index=False).encode("utf-8-sig"),"pt_xyz_hasil_segmentasi.csv","text/csv")
    else:
        st.subheader("Rekomendasi customer treatment")
        st.caption("Saran awal berdasarkan pola RFM, perlu ditinjau sesuai konteks operasional.")
        for _,row in clusters.iterrows():
            if row["Jumlah pelanggan"]==0: continue
            title,actions=treatment(row["Karakteristik"])
            with st.container(border=True):
                st.markdown(f"### Cluster {int(row['Cluster'])} — {title}")
                st.write(f"**{int(row['Jumlah pelanggan'])} pelanggan** · {row['Karakteristik']}")
                for action in actions: st.markdown(f"- {action}")
        st.warning("Rekomendasi adalah saran awal berbasis data, bukan jaminan hasil bisnis.")

st.markdown("---")
st.caption("© PT. XYZ · Customer Intelligence Dashboard · RFM • K-Means • Customer Treatment")
