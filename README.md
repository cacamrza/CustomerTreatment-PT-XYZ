# PT. XYZ Streamlit app

## Perbaiki error "This file does not exist"
Upload `streamlit_app.py` dan `requirements.txt` ke root repository GitHub pada branch `main`.
Di Streamlit Community Cloud, isi Main file path dengan persis: `streamlit_app.py`.

## Menjalankan lokal
```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Aplikasi menyediakan upload Excel/CSV, pemetaan kolom, perhitungan RFM, Min-Max normalization, K-Means, evaluasi silhouette jika memungkinkan, tabel segmen, rekomendasi treatment, dan ekspor CSV.
Data tidak disimpan ke database; aplikasi ini tanpa login dan histori akan hilang saat sesi berakhir.
