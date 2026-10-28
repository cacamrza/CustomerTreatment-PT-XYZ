
import re
from datetime import date

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import MinMaxScaler

st.set_page_config(
    page_title="PT. XYZ | Customer Intelligence",
    page_icon="🚚",
    layout="wide"
)

# =========================
# DESIGN & STYLING
# =========================

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
}

.stApp {
    background: #F5F7FA;
    color: #1B2A3B;
}

[data-testid="stSidebar"] {
    background: #0A1B30;
}

[data-testid="stSidebar"] * {
    color: #EAF0F7;
}

.hero {
    background: linear-gradient(112deg, #10253F, #173957 70%, #214A6C);
    border-radius: 18px;
    padding: 30px;
    color: white;
    margin-bottom: 25px;
}

.hero small {
    color: #FFAD60;
    font-weight: 800;
    letter-spacing: 1.5px;
}

.hero h1 {
    color: white !important;
    font-family: Manrope, sans-serif;
    font-size: 34px;
    margin: 12px 0;
}

.hero h1 span {
    color: #FF9B43;
}

.hero p {
    color: #C2D0DE;
    margin-bottom: 0;
}

div[data-testid="stMetric"] {
    background: white;
    padding: 18px;
    border: 1px solid #E7ECF2;
    border-radius: 14px;
    box-shadow: 0 5px 18px #10253F08;
}

h1, h2, h3 {
    font-family: Manrope, sans-serif;
}

.stButton > button,
.stDownloadButton > button {
    border-radius: 9px;
    font-weight: 700;
}

</style>
""", unsafe_allow_html=True)


# =========================
# HELPER FUNCTIONS
# =========================

def normalize_name(value):
    return re.sub(
        r"[\s_\-./()]+",
        "",
        str(value).strip().lower()
    )


def guess_column(columns, hints):
    for hint in hints:
        for column in columns:
            if normalize_name(column) == normalize_name(hint):
                return column

    for hint in hints:
        for column in columns:
            if normalize_name(hint) in normalize_name(column):
                return column

    return columns[0]


def parse_money(series):
    def convert(value):
        if pd.isna(value):
            return np.nan

        if isinstance(value, (int, float, np.number)):
            return float(value)

        value = re.sub(
            r"(?i)rp|\s",
            "",
            str(value)
        )
        value = re.sub(r"[^\d,.\-]", "", value)

        if not value:
            return np.nan

        if "," in value and "." in value:
            if value.rfind(",") > value.rfind("."):
                value = value.replace(".", "").replace(",", ".")
            else:
                value = value.replace(",", "")

        elif "," in value:
            if len(value.split(",")[-1]) == 3:
                value = value.replace(",", "")
            else:
                value = value.replace(",", ".")

        elif re.fullmatch(r"-?\d{1,3}(\.\d{3})+", value):
            value = value.replace(".", "")

        try:
            return float(value)
        except ValueError:
            return np.nan

    return series.map(convert)


def rupiah(value):
    if pd.isna(value):
        return "—"

    value = float(value)

    if abs(value) >= 1_000_000_000:
        return f"Rp {value / 1_000_000_000:.1f} M".replace(".", ",")

    if abs(value) >= 1_000_000:
        return f"Rp {value / 1_000_000:.1f} jt".replace(".", ",")

    return "Rp " + f"{value:,.0f}".replace(",", ".")


def describe_cluster(row, averages):
    avg_r, avg_f, avg_m = averages

    active = row["R rata-rata"] <= avg_r
    frequent = row["F rata-rata"] >= avg_f
    valuable = row["M rata-rata"] >= avg_m

    if active and frequent and valuable:
        return "Pelanggan bernilai tinggi"

    if active and frequent:
        return "Pelanggan loyal dan aktif"

    if not active and valuable:
        return "Bernilai tinggi, perlu perhatian"

    if not active and not frequent:
        return "Berisiko tidak aktif"

    if active and not frequent:
        return "Pelanggan berkembang"

    if valuable:
        return "Kontributor pendapatan"

    return "Perlu pengembangan"


def treatment_recommendation(label):
    if label == "Pelanggan bernilai tinggi":
        return (
            "Pertahankan pelanggan bernilai tinggi",
            [
                "Lakukan komunikasi personal untuk memahami kebutuhan pengiriman.",
                "Pantau kualitas layanan dan tindak lanjuti keluhan dengan cepat.",
                "Pertimbangkan program loyalitas sesuai kebijakan perusahaan."
            ]
        )

    if "Berisiko" in label or "perlu perhatian" in label:
        return (
            "Reaktivasi pelanggan",
            [
                "Hubungi pelanggan untuk memahami hambatan penggunaan layanan.",
                "Tawarkan informasi atau penawaran yang relevan jika sesuai kebijakan.",
                "Pantau apakah pelanggan kembali melakukan transaksi."
            ]
        )

    if "loyal" in label or "berkembang" in label:
        return (
            "Tingkatkan pemesanan berulang",
            [
                "Tanyakan rencana pengiriman pada periode berikutnya.",
                "Perkenalkan layanan yang relevan dengan pola transaksi.",
                "Evaluasi frekuensi pemesanan secara berkala."
            ]
        )

    return (
        "Kembangkan hubungan pelanggan",
        [
            "Lakukan follow-up untuk memahami kebutuhan pengiriman.",
            "Berikan informasi layanan yang relevan dan jelas.",
            "Evaluasi perubahan perilaku transaksi pada periode berikutnya."
        ]
    )


# =========================
# SIDEBAR NAVIGATION
# =========================

st.sidebar.markdown("# 🚚 PT. XYZ")
st.sidebar.caption("CUSTOMER INTELLIGENCE")

page = st.sidebar.radio(
    "WORKSPACE",
    [
        "Ringkasan",
        "Segmentasi Pelanggan",
        "Customer Treatment"
    ]
)

st.sidebar.markdown("---")
st.sidebar.caption("Mode demo · Tanpa login")

st.sidebar.info(
    "Unggah data transaksi untuk menghasilkan "
    "segmentasi RFM dan rekomendasi customer treatment."
)


# =========================
# HEADER
# =========================

st.markdown("""
<div class="hero">
    <small>CUSTOMER RELATIONSHIP MANAGEMENT</small>
    <h1>Customer Intelligence<span>.</span></h1>
    <p>
        Ubah data transaksi menjadi strategi pelanggan
        yang lebih tepat sasaran dengan RFM dan K-Means.
    </p>
</div>
""", unsafe_allow_html=True)


# =========================
# SESSION STATE
# =========================

if "rfm" not in st.session_state:
    st.session_state["rfm"] = None

if "clusters" not in st.session_state:
    st.session_state["clusters"] = None

if "transactions" not in st.session_state:
    st.session_state["transactions"] = None

if "silhouette" not in st.session_state:
    st.session_state["silhouette"] = None


# =========================
# UPLOAD DATA
# =========================

st.subheader("Upload Data Transaksi")

uploaded_file = st.file_uploader(
    "Pilih file Excel atau CSV",
    type=["xlsx", "xls", "csv"],
    help="Kolom yang dibutuhkan: pelanggan, invoice, tanggal, dan shipping cost."
)

if uploaded_file is not None:
    try:
        if uploaded_file.name.lower().endswith(".csv"):
            raw = pd.read_csv(uploaded_file)
        else:
            raw = pd.read_excel(uploaded_file)

        if raw.empty:
            st.error("File kosong. Silakan unggah data transaksi.")
        else:
            st.success(
                f"File terbaca: {uploaded_file.name} | "
                f"{len(raw):,} baris | {len(raw.columns)} kolom"
            )

            columns = list(raw.columns)

            customer_default = guess_column(
                columns,
                [
                    "shipper", "customer", "pelanggan",
                    "namacustomer", "namapelanggan",
                    "customerid"
                ]
            )

            invoice_default = guess_column(
                columns,
                [
                    "invoice", "noinvoice",
                    "nomorinvoice", "invoicenumber",
                    "faktur"
                ]
            )

            date_default = guess_column(
                columns,
                [
                    "tanggalinvoice", "invoicedate",
                    "tanggal", "date", "tgl"
                ]
            )

            cost_default = guess_column(
                columns,
                [
                    "shippingcost", "biayapengiriman",
                    "cost", "dpp", "revenue", "amount"
                ]
            )

            col1, col2 = st.columns(2)

            with col1:
                customer_col = st.selectbox(
                    "Kolom pelanggan / shipper",
                    columns,
                    index=columns.index(customer_default)
                )

                invoice_col = st.selectbox(
                    "Kolom nomor invoice",
                    columns,
                    index=columns.index(invoice_default)
                )

            with col2:
                date_col = st.selectbox(
                    "Kolom tanggal invoice",
                    columns,
                    index=columns.index(date_default)
                )

                cost_col = st.selectbox(
                    "Kolom shipping cost",
                    columns,
                    index=columns.index(cost_default)
                )

            col3, col4 = st.columns(2)

            with col3:
                snapshot_date = st.date_input(
                    "Tanggal analisis",
                    value=date.today()
                )

            with col4:
                k = st.selectbox(
                    "Jumlah cluster K",
                    [2, 3, 4, 5, 6],
                    index=1
                )

            if st.button(
                "✨ Analisis Data Pelanggan",
                type="primary",
                use_container_width=True
            ):
                try:
                    with st.spinner(
                        "Menghitung RFM dan menjalankan K-Means..."
                    ):
                        data = raw[
                            [customer_col, invoice_col, date_col, cost_col]
                        ].copy()

                        data.columns = [
                            "Pelanggan",
                            "Invoice",
                            "Tanggal",
                            "Cost"
                        ]

                        data["Pelanggan"] = (
                            data["Pelanggan"]
                            .astype("string")
                            .str.strip()
                        )

                        data["Invoice"] = (
                            data["Invoice"]
                            .astype("string")
                            .str.strip()
                        )

                        data["Tanggal"] = pd.to_datetime(
                            data["Tanggal"],
                            errors="coerce",
                            dayfirst=True
                        )

                        data["Cost"] = parse_money(data["Cost"])

                        data = data.dropna(
                            subset=["Pelanggan", "Tanggal", "Cost"]
                        )

                        data = data[
                            data["Pelanggan"].ne("")
                            & data["Pelanggan"].ne("<NA>")
                        ].copy()

                        if data.empty:
                            st.error(
                                "Tidak ada baris valid. "
                                "Periksa pemetaan kolom dan format data."
                            )

                        else:
                            # Invoice kosong diberi ID unik per baris.
                            data["Invoice"] = data["Invoice"].replace(
                                {"": pd.NA, "<NA>": pd.NA}
                            )

                            missing_invoice = data["Invoice"].isna()

                            data.loc[missing_invoice, "Invoice"] = (
                                "BARIS_" +
                                data.index[missing_invoice].astype(str)
                            )

                            # =========================
                            # RFM CALCULATION
                            # =========================

                            rfm = data.groupby("Pelanggan").agg(
                                Transaksi=("Invoice", "nunique"),
                                Monetary=("Cost", "sum"),
                                Tanggal_terakhir=("Tanggal", "max")
                            ).reset_index()

                            rfm["Recency (hari)"] = (
                                pd.Timestamp(snapshot_date)
                                - rfm["Tanggal_terakhir"].dt.normalize()
                            ).dt.days.clip(lower=0)

                            if len(rfm) < k:
                                st.error(
                                    f"Jumlah pelanggan unik {len(rfm)} "
                                    f"harus minimal sama dengan K ({k})."
                                )

                            else:
                                # =========================
                                # NORMALIZATION
                                # =========================

                                features = rfm[
                                    [
                                        "Recency (hari)",
                                        "Transaksi",
                                        "Monetary"
                                    ]
                                ].copy()

                                scaler = MinMaxScaler()
                                scaled = scaler.fit_transform(features)

                                # Recency dibalik:
                                # transaksi lebih baru mendapat skor tinggi.
                                scaled[:, 0] = 1 - scaled[:, 0]

                                # =========================
                                # K-MEANS
                                # =========================

                                model = KMeans(
                                    n_clusters=k,
                                    random_state=42,
                                    n_init=10
                                )

                                rfm["Cluster"] = model.fit_predict(scaled)

                                averages = (
                                    rfm["Recency (hari)"].mean(),
                                    rfm["Transaksi"].mean(),
                                    rfm["Monetary"].mean()
                                )

                                cluster_rows = []

                                for cluster_id in range(k):
                                    part = rfm[
                                        rfm["Cluster"] == cluster_id
                                    ]

                                    cluster_rows.append({
                                        "Cluster": cluster_id + 1,
                                        "Jumlah pelanggan": len(part),
                                        "R rata-rata": (
                                            part["Recency (hari)"].mean()
                                            if len(part) else 0
                                        ),
                                        "F rata-rata": (
                                            part["Transaksi"].mean()
                                            if len(part) else 0
                                        ),
                                        "M rata-rata": (
                                            part["Monetary"].mean()
                                            if len(part) else 0
                                        )
                                    })

                                clusters = pd.DataFrame(cluster_rows)

                                clusters["Karakteristik"] = clusters.apply(
                                    lambda row: describe_cluster(
                                        row, averages
                                    ),
                                    axis=1
                                )

                                # =========================
                                # SILHOUETTE SCORE
                                # =========================

                                score = None

                                try:
                                    if (
                                        len(rfm) > k
                                        and rfm["Cluster"].nunique() > 1
                                        and len(rfm) <= 12000
                                    ):
                                        X = scaled
                                        y = rfm["Cluster"].to_numpy()

                                        # Sample untuk mengurangi beban
                                        # komputasi pada dataset besar.
                                        if len(rfm) > 2500:
                                            rng = np.random.default_rng(42)

                                            idx = rng.choice(
                                                len(rfm),
                                                2500,
                                                replace=False
                                            )

                                            X = scaled[idx]
                                            y = y[idx]

                                        if len(np.unique(y)) > 1:
                                            score = float(
                                                silhouette_score(X, y)
                                            )

                                except Exception:
                                    score = None

                                # Simpan hasil ke session.
                                st.session_state["rfm"] = rfm
                                st.session_state["clusters"] = clusters
                                st.session_state["transactions"] = data
                                st.session_state["silhouette"] = score
                                st.session_state["snapshot"] = snapshot_date
                                st.session_state["file_name"] = uploaded_file.name

                                st.success(
                                    "Analisis selesai! "
                                    "Silakan buka menu di sidebar."
                                )

                except Exception as exc:
                    st.error(
                        f"Analisis gagal: {exc}. "
                        "Periksa kembali kolom dan format data."
                    )

    except Exception as exc:
        st.error(
            f"File tidak dapat dibaca: {exc}. "
            "Pastikan format Excel atau CSV valid."
        )


# =========================
# DASHBOARD RESULTS
# =========================

rfm = st.session_state["rfm"]
clusters = st.session_state["clusters"]
transactions = st.session_state["transactions"]

if rfm is None:
    st.subheader("Ringkasan Analisis")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Total pelanggan", "—")
    col2.metric("Total transaksi", "—")
    col3.metric("Total shipping cost", "—")
    col4.metric("Jumlah segmen", "—")

    st.info(
        "Dashboard masih kosong. Unggah file yang memiliki "
        "identitas pelanggan, nomor invoice, tanggal invoice, "
        "dan shipping cost."
    )

    st.markdown("### Alur analisis")

    a, b, c, d = st.columns(4)

    a.markdown("**1. Upload**\n\nUnggah file Excel atau CSV.")
    b.markdown("**2. RFM**\n\nHitung Recency, Frequency, Monetary.")
    c.markdown("**3. K-Means**\n\nBentuk segmen pelanggan.")
    d.markdown("**4. Treatment**\n\nLihat rekomendasi per segmen.")

else:
    st.caption(
        f"Dataset: {st.session_state['file_name']} | "
        f"Tanggal analisis: {st.session_state['snapshot']:%d-%m-%Y}"
    )

    if page == "Ringkasan":
        st.subheader("Ringkasan Analisis")

        col1, col2, col3, col4 = st.columns(4)

        col1.metric(
            "Total pelanggan",
            f"{len(rfm):,}".replace(",", ".")
        )

        col2.metric(
            "Total transaksi valid",
            f"{len(transactions):,}".replace(",", ".")
        )

        col3.metric(
            "Total shipping cost",
            rupiah(transactions["Cost"].sum())
        )

        col4.metric(
            "Jumlah segmen",
            str((clusters["Jumlah pelanggan"] > 0).sum())
        )

        left, right = st.columns(2)

        with left:
            st.markdown("### Distribusi pelanggan")

            pie_data = clusters[
                clusters["Jumlah pelanggan"] > 0
            ].copy()

            pie_data["Nama cluster"] = pie_data["Cluster"].map(
                lambda x: f"Cluster {x}"
            )

            fig = px.pie(
                pie_data,
                names="Nama cluster",
                values="Jumlah pelanggan",
                hole=0.62,
                color_discrete_sequence=[
                    "#3C78E8",
                    "#FF8A24",
                    "#1EAA78",
                    "#8B67D5",
                    "#3E9BB8",
                    "#D45D82"
                ]
            )

            fig.update_layout(
                margin=dict(t=15, b=10, l=5, r=5),
                legend_title_text=""
            )

            st.plotly_chart(fig, use_container_width=True)

        with right:
            st.markdown("### Jumlah pelanggan per cluster")

            fig = px.bar(
                pie_data,
                x="Nama cluster",
                y="Jumlah pelanggan",
                color="Nama cluster",
                color_discrete_sequence=[
                    "#3C78E8",
                    "#FF8A24",
                    "#1EAA78",
                    "#8B67D5",
                    "#3E9BB8",
                    "#D45D82"
                ]
            )

            fig.update_layout(
                showlegend=False,
                margin=dict(t=15, b=10, l=5, r=5),
                xaxis_title="",
                yaxis_title="Jumlah pelanggan"
            )

            st.plotly_chart(fig, use_container_width=True)

        st.markdown("### Evaluasi clustering")

        score = st.session_state["silhouette"]

        if score is None:
            st.warning(
                "Silhouette Score tidak tersedia untuk hasil ini. "
                "Periksa jumlah cluster dan distribusi pelanggan."
            )
        else:
            st.metric("Silhouette Score", f"{score:.3f}")

        st.caption(
            "Silhouette Score berada pada rentang -1 sampai 1. "
            "Nilai ini perlu diinterpretasikan bersama konteks data."
        )

    elif page == "Segmentasi Pelanggan":
        st.subheader("Karakteristik Segmen Pelanggan")

        display = clusters.copy()

        display["Rata-rata Monetary"] = (
            display["M rata-rata"].map(rupiah)
        )

        st.dataframe(
            display[
                [
                    "Cluster",
                    "Jumlah pelanggan",
                    "R rata-rata",
                    "F rata-rata",
                    "Rata-rata Monetary",
                    "Karakteristik"
                ]
            ].rename(columns={
                "R rata-rata": "Recency rata-rata (hari)",
                "F rata-rata": "Frequency rata-rata"
            }),
            use_container_width=True,
            hide_index=True
        )

        st.markdown("### Daftar pelanggan")

        search = st.text_input("Cari nama pelanggan")

        shown = rfm.copy()

        if search:
            shown = shown[
                shown["Pelanggan"].astype(str).str.contains(
                    search,
                    case=False,
                    na=False
                )
            ]

        shown = shown.sort_values(
            "Monetary",
            ascending=False
        )

        st.dataframe(
            shown[
                [
                    "Pelanggan",
                    "Recency (hari)",
                    "Transaksi",
                    "Monetary",
                    "Cluster"
                ]
            ],
            use_container_width=True,
            hide_index=True
        )

        csv_data = shown.to_csv(
            index=False
        ).encode("utf-8-sig")

        st.download_button(
            "⬇ Unduh hasil segmentasi CSV",
            data=csv_data,
            file_name="pt_xyz_hasil_segmentasi.csv",
            mime="text/csv"
        )

    elif page == "Customer Treatment":
        st.subheader("Rekomendasi Customer Treatment")

        st.caption(
            "Rekomendasi berdasarkan pola RFM. "
            "Tinjau sesuai konteks operasional perusahaan."
        )

        for _, row in clusters.iterrows():
            if row["Jumlah pelanggan"] == 0:
                continue

            title, actions = treatment_recommendation(
                row["Karakteristik"]
            )

            with st.container(border=True):
                st.markdown(
                    f"### Cluster {int(row['Cluster'])} — {title}"
                )

                st.write(
                    f"**{int(row['Jumlah pelanggan'])} pelanggan** "
                    f"| {row['Karakteristik']}"
                )

                for action in actions:
                    st.markdown(f"- {action}")

                st.caption(
                    f"Recency rata-rata: {row['R rata-rata']:.0f} hari "
                    f"| Frequency rata-rata: {row['F rata-rata']:.1f} "
                    f"| Monetary rata-rata: {rupiah(row['M rata-rata'])}"
                )

        st.warning(
            "Rekomendasi merupakan saran awal berbasis data, "
            "bukan jaminan hasil bisnis."
        )


# =========================
# FOOTER
# =========================

st.markdown("---")

st.caption(
    "© PT. XYZ | Customer Intelligence Dashboard | "
    "RFM • K-Means • Customer Treatment"
)
