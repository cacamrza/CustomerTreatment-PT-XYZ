# PT. XYZ Customer Intelligence Dashboard

Dashboard frontend untuk TA segmentasi pelanggan jasa logistik menggunakan RFM dan K-Means.

## Isi folder
- `index.html` — struktur halaman dashboard
- `style.css` — styling responsive Logistics Tech (navy, putih, oranye)
- `app.js` — fungsi parsing data, pembentukan RFM, normalisasi, K-Means, dan silhouette score
- `script.js` — interaksi upload, pemetaan kolom, grafik, tabel, rekomendasi, dan ekspor CSV

## Cara menjalankan di VS Code
1. Ekstrak folder `pt_xyz_crm_dashboard`.
2. Buka folder tersebut di VS Code.
3. Jalankan `index.html` menggunakan extension **Live Server** (klik kanan → Open with Live Server).
4. Pastikan koneksi internet aktif untuk memuat library XLSX dan Chart.js dari CDN.
5. Klik **Upload data transaksi**, pilih file Excel/CSV, lalu konfirmasi pemetaan kolom.
6. Pilih tanggal analisis dan jumlah cluster, kemudian klik **Analisis data pelanggan**.

## Kolom input
- Identitas shipper / pelanggan
- Nomor invoice
- Tanggal invoice
- Shipping cost

Nama kolom dapat berbeda. Setelah upload, pastikan pemetaan kolom pada dropdown sudah benar.

## Catatan metodologi penting
- Frequency dihitung sebagai jumlah nomor invoice unik per pelanggan.
- Monetary dihitung sebagai jumlah shipping cost dari baris transaksi valid.
- Recency dihitung dari tanggal snapshot dikurangi tanggal transaksi terakhir.
- Untuk K-Means, Recency dibalik setelah normalisasi agar aktivitas yang lebih baru memiliki skor lebih tinggi.
- Silhouette score dihitung pada sampel hingga 500 pelanggan untuk dataset besar; untuk dataset lebih dari 12.000 pelanggan, skor tidak dihitung pada demo ini agar browser tidak berat.
- Hasil cluster K-Means tidak otomatis memiliki makna bisnis. Label dan rekomendasi yang ditampilkan merupakan interpretasi heuristik awal berdasarkan nilai rata-rata RFM dan perlu ditinjau oleh perusahaan.
- Data diproses di browser; demo ini tidak mengirim file ke server. Untuk penggunaan perusahaan, tambahkan autentikasi, kontrol akses, backup, dan tinjauan privasi jika dibutuhkan.

## Batasan
Ini merupakan aplikasi frontend tanpa backend/database. Data hanya tersedia selama halaman dibuka dan tidak tersimpan sebagai histori tahunan. Silhouette score adalah evaluasi internal dan bukan jaminan bahwa cluster paling baik untuk tujuan bisnis. Selalu periksa hasil pemetaan kolom, format tanggal, dan satuan shipping cost.
