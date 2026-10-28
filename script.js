/* UI wiring for PT. XYZ Customer Intelligence Dashboard */
(function () {
  "use strict";
  const $ = id => document.getElementById(id);
  const state = { workbookRows: [], headers: [], file: null, mapping: null, result: null, page: 0, pageSize: 10, charts: {} };
  const fmtInt = n => new Intl.NumberFormat("id-ID", { maximumFractionDigits: 0 }).format(n);
  const fmtMoney = n => {
    if (!Number.isFinite(n)) return "—";
    const abs = Math.abs(n);
    if (abs >= 1e9) return "Rp " + (n / 1e9).toLocaleString("id-ID", { maximumFractionDigits: 1 }) + " M";
    if (abs >= 1e6) return "Rp " + (n / 1e6).toLocaleString("id-ID", { maximumFractionDigits: 1 }) + " jt";
    if (abs >= 1e3) return "Rp " + (n / 1e3).toLocaleString("id-ID", { maximumFractionDigits: 1 }) + " rb";
    return "Rp " + fmtInt(n);
  };
  const esc = s => String(s ?? "").replace(/[&<>"']/g, ch => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;" }[ch]));
  const show = (el, yes = true) => el.classList.toggle("hidden", !yes);
  const toast = message => {
    const el = $("toast"); el.textContent = message; el.classList.add("show");
    clearTimeout(toast.timer); toast.timer = setTimeout(() => el.classList.remove("show"), 3200);
  };
  const setAlert = (message, type = "error") => {
    const el = $("alertBox"); el.textContent = message; el.className = `alert ${type}`;
  };
  const clearAlert = () => { $("alertBox").className = "alert hidden"; $("alertBox").textContent = ""; };

  function readFile(file) {
    clearAlert();
    if (!file) return;
    const ext = file.name.split(".").pop().toLowerCase();
    if (!["xlsx", "xls", "csv"].includes(ext)) { setAlert("Format file belum didukung. Gunakan .xlsx, .xls, atau .csv."); return; }
    if (file.size > 50 * 1024 * 1024) { setAlert("File lebih dari 50 MB. Coba gunakan file yang lebih kecil agar browser tetap responsif."); return; }
    if (!window.XLSX) { setAlert("Library pembaca Excel belum termuat. Pastikan perangkat terhubung ke internet lalu muat ulang halaman."); return; }
    state.file = file;
    $("fileName").textContent = file.name;
    $("fileMeta").textContent = `${(file.size / 1024).toLocaleString("id-ID", { maximumFractionDigits: 0 })} KB · siap dibaca`;
    show($("filePreview")); $("analyzeButton").disabled = true; show($("mappingCard"), false);
    const reader = new FileReader();
    reader.onload = event => {
      try {
        let workbook;
        if (ext === "csv") workbook = XLSX.read(event.target.result, { type: "string", cellDates: true });
        else workbook = XLSX.read(event.target.result, { type: "array", cellDates: true });
        const sheetName = workbook.SheetNames[0];
        if (!sheetName) throw new Error("File tidak memiliki worksheet.");
        const sheet = workbook.Sheets[sheetName];
        const json = XLSX.utils.sheet_to_json(sheet, { defval: "", raw: true });
        if (!json.length) throw new Error("Worksheet kosong atau header kolom tidak terdeteksi.");
        state.workbookRows = json;
        state.headers = Object.keys(json[0]);
        if (state.headers.length < 4) {
          setAlert(`Terdeteksi ${state.headers.length} kolom. Analisis memerlukan kolom pelanggan, nomor invoice, tanggal invoice, dan shipping cost.`, "error");
        } else {
          setAlert(`File berhasil dibaca: ${fmtInt(json.length)} baris dan ${state.headers.length} kolom. Konfirmasi pemetaan kolom di bawah.`, "success");
        }
        fillMappingSelects();
        $("rowCountLabel").textContent = `${fmtInt(json.length)} baris terdeteksi · sheet: ${sheetName}`;
        show($("mappingCard"));
        $("fileMeta").textContent = `${fmtInt(json.length)} baris · ${state.headers.length} kolom`;
        $("analyzeButton").disabled = true;
        $("mappingCard").scrollIntoView({ behavior: "smooth", block: "nearest" });
      } catch (error) {
        setAlert(error.message || "File gagal dibaca. Periksa struktur file dan coba lagi.");
        show($("mappingCard"), false);
      }
    };
    reader.onerror = () => setAlert("File tidak dapat dibaca oleh browser.");
    if (ext === "csv") reader.readAsText(file); else reader.readAsArrayBuffer(file);
  }

  function fillMappingSelects() {
    const headers = state.headers;
    const fields = [
      ["colCustomer", PTXYZApp.guessColumn(headers, ["shipper", "customer", "pelanggan", "namacustomer", "namapelanggan", "customername", "shippername", "custid", "customerid"])],
      ["colInvoice", PTXYZApp.guessColumn(headers, ["invoice", "noinvoice", "nomorinvoice", "invoicenumber", "invoiceno", "faktur"])],
      ["colDate", PTXYZApp.guessColumn(headers, ["tanggalinvoice", "invoicedate", "tanggal", "date", "tglinvoice", "tgl"])],
      ["colCost", PTXYZApp.guessColumn(headers, ["shippingcost", "biayapengiriman", "ongkirkirim", "cost", "dpp", "revenue", "amount", "nilaiinvoice"])]
    ];
    fields.forEach(([id, guess]) => {
      const select = $(id);
      select.innerHTML = headers.map(h => `<option value="${esc(h)}" ${h === guess ? "selected" : ""}>${esc(h)}</option>`).join("");
    });
  }

  function confirmMapping() {
    const selected = ["colCustomer", "colInvoice", "colDate", "colCost"].map(id => $(id).value);
    if (new Set(selected).size !== 4) { setAlert("Pilih empat kolom yang berbeda untuk pelanggan, invoice, tanggal, dan shipping cost."); return; }
    state.mapping = { customer: selected[0], invoice: selected[1], date: selected[2], cost: selected[3] };
    $("analyzeButton").disabled = false;
    clearAlert();
    setAlert("Pemetaan kolom siap. Klik “Analisis data pelanggan” untuk melanjutkan.", "success");
    toast("Kolom berhasil dipetakan.");
  }

  function analyze() {
    if (!state.workbookRows.length || !state.mapping) { setAlert("Unggah file dan konfirmasi kolom terlebih dahulu."); return; }
    const button = $("analyzeButton");
    button.disabled = true; show($("progressWrap")); clearAlert();
    const progress = value => { $("progressBar").style.width = `${value}%`; $("progressPercent").textContent = `${value}%`; };
    $("progressText").textContent = "Memvalidasi dan membentuk RFM...";
    progress(15);
    // Yield once so progress UI can render before the synchronous clustering step.
    setTimeout(() => {
      try {
        const k = Number($("clusterCount").value);
        const snapshot = $("dateReference").value || null;
        $("progressText").textContent = "Menghitung RFM dan menjalankan K-Means...";
        progress(45);
        const result = PTXYZApp.analyze(state.workbookRows, state.mapping, snapshot, k);
        state.result = result; state.page = 0;
        progress(100); $("progressText").textContent = "Analisis selesai.";
        renderResults();
        show($("results")); show($("treatment-section"), true);
        $("results").scrollIntoView({ behavior: "smooth", block: "start" });
        setAlert(`Analisis selesai. ${fmtInt(result.rfm.length)} pelanggan berhasil diproses dari ${fmtInt(result.transactions.length)} baris transaksi valid.`, "success");
        toast("Analisis pelanggan berhasil diselesaikan.");
      } catch (error) {
        setAlert(error.message || "Analisis gagal. Periksa kembali data dan pemetaan kolom.");
      } finally {
        button.disabled = false;
        setTimeout(() => show($("progressWrap"), false), 900);
      }
    }, 80);
  }

  function getClusterLabel(cluster, all) {
    if (!cluster.count) return "Cluster tanpa anggota";
    const avgR = all.reduce((s, c) => s + c.avgRecency, 0) / all.length;
    const avgF = all.reduce((s, c) => s + c.avgFrequency, 0) / all.length;
    const avgM = all.reduce((s, c) => s + c.avgMonetary, 0) / all.length;
    const active = cluster.avgRecency <= avgR;
    const frequent = cluster.avgFrequency >= avgF;
    const valuable = cluster.avgMonetary >= avgM;
    if (active && frequent && valuable) return "Pelanggan bernilai tinggi";
    if (active && frequent) return "Pelanggan loyal dan aktif";
    if (!active && valuable) return "Bernilai tinggi, perlu perhatian";
    if (!active && !frequent) return "Berisiko tidak aktif";
    if (active && !frequent) return "Pelanggan berkembang";
    if (valuable) return "Kontributor pendapatan";
    return "Perlu pengembangan";
  }

  function renderResults() {
    const r = state.result;
    $("totalCustomers").textContent = fmtInt(r.rfm.length);
    $("totalTransactions").textContent = fmtInt(r.transactions.length);
    $("totalRevenue").textContent = fmtMoney(r.totalMonetary);
    $("totalClusters").textContent = r.clusters.filter(c => c.count > 0).length;
    $("periodPill").textContent = `Snapshot ${r.snapshot.toLocaleDateString("id-ID")}`;
    $("customersNote").textContent = `${fmtInt(r.rfm.length)} shipper unik`;
    $("silhouetteNote").textContent = r.silhouetteScore == null ? "Silhouette tidak tersedia untuk ukuran/hasil ini" : `Silhouette Score: ${r.silhouetteScore.toFixed(3)}`;
    renderCharts(); renderClusterTable(); renderCustomerTable(); renderTreatments();
  }

  function renderCharts() {
    if (!window.Chart) return;
    const r = state.result;
    Object.values(state.charts).forEach(chart => chart.destroy());
    const labels = r.clusters.map(c => `Cluster ${c.id + 1}`);
    state.charts.cluster = new Chart($("clusterChart"), {
      type: "doughnut",
      data: { labels, datasets: [{ data: r.clusters.map(c => c.count), backgroundColor: r.clusters.map(c => PTXYZApp.COLORS[c.id % PTXYZApp.COLORS.length]), borderColor: "#fff", borderWidth: 4, hoverOffset: 7 }] },
      options: { responsive: true, maintainAspectRatio: false, cutout: "67%", plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => `${ctx.label}: ${fmtInt(ctx.raw)} pelanggan` } } } }
    });
    $("clusterLegend").innerHTML = r.clusters.map(c => `<span class="legend-item"><i class="legend-dot" style="background:${PTXYZApp.COLORS[c.id % PTXYZApp.COLORS.length]}"></i>Cluster ${c.id + 1} <b>${fmtInt(c.count)}</b></span>`).join("");
    state.charts.rfm = new Chart($("rfmChart"), {
      type: "bar",
      data: { labels, datasets: [
        { label: "Recency (skor terbalik)", data: r.clusters.map(c => 1 - (c.avgRecency - Math.min(...r.rfm.map(x => x.recency))) / Math.max(1, Math.max(...r.rfm.map(x => x.recency)) - Math.min(...r.rfm.map(x => x.recency)))), backgroundColor: "#3c78e8", borderRadius: 4 },
        { label: "Frequency (normalisasi)", data: r.clusters.map(c => c.centroid[1]), backgroundColor: "#ff8a24", borderRadius: 4 },
        { label: "Monetary (normalisasi)", data: r.clusters.map(c => c.centroid[2]), backgroundColor: "#1eaa78", borderRadius: 4 }
      ] },
      options: { responsive: true, maintainAspectRatio: false, scales: { y: { beginAtZero: true, max: 1, grid: { color: "#edf1f5" }, ticks: { font: { size: 9 }, color: "#91a0af" } }, x: { grid: { display: false }, ticks: { font: { size: 10 }, color: "#718195" } } }, plugins: { legend: { position: "bottom", labels: { boxWidth: 8, boxHeight: 8, usePointStyle: true, pointStyle: "rectRounded", padding: 15, font: { size: 9 } } } } }
    });
  }

  function renderClusterTable() {
    const r = state.result;
    $("segmentTableBody").innerHTML = r.clusters.map(c => {
      const label = getClusterLabel(c, r.clusters);
      return `<tr><td><span class="segment-pill segment-${c.id + 1}">Cluster ${c.id + 1}</span></td><td><strong>${fmtInt(c.count)}</strong></td><td>${fmtInt(Math.round(c.avgRecency))} hari</td><td>${c.avgFrequency.toFixed(1)}x</td><td>${esc(fmtMoney(c.avgMonetary))}</td><td>${esc(label)}</td></tr>`;
    }).join("");
  }

  function renderCustomerTable() {
    const r = state.result;
    const query = $("customerSearch").value.trim().toLowerCase();
    const filtered = r.rfm.filter(c => c.customer.toLowerCase().includes(query)).sort((a, b) => b.monetary - a.monetary);
    const pages = Math.max(1, Math.ceil(filtered.length / state.pageSize));
    state.page = Math.min(state.page, pages - 1);
    const visible = filtered.slice(state.page * state.pageSize, (state.page + 1) * state.pageSize);
    $("customerTableBody").innerHTML = visible.length ? visible.map(c => `<tr><td class="customer-name">${esc(c.customer)}</td><td>${fmtInt(c.recency)}</td><td>${fmtInt(c.frequency)}</td><td>${esc(fmtMoney(c.monetary))}</td><td><span class="segment-pill segment-${c.cluster + 1}">Cluster ${c.cluster + 1}</span></td></tr>`).join("") : `<tr><td colspan="5" class="empty-table">Tidak ada pelanggan yang cocok.</td></tr>`;
    $("customerCount").textContent = `${fmtInt(filtered.length)} pelanggan`;
    $("pageInfo").textContent = filtered.length ? `Menampilkan ${state.page * state.pageSize + 1}–${Math.min((state.page + 1) * state.pageSize, filtered.length)} dari ${fmtInt(filtered.length)} pelanggan` : "Menampilkan 0 pelanggan";
    $("prevPage").disabled = state.page <= 0;
    $("nextPage").disabled = state.page >= pages - 1;
  }

  function renderTreatments() {
    const r = state.result;
    const all = r.clusters;
    const recommendations = all.filter(c => c.count > 0).map(c => {
      const label = getClusterLabel(c, all);
      let data;
      if (label.includes("bernilai tinggi") && !label.includes("perlu")) data = {
        icon: "★", color: "#fff0e2", ink: "#dc7a1e", title: "Pertahankan pelanggan bernilai tinggi",
        intro: "Prioritaskan hubungan jangka panjang dengan pelanggan yang aktif, sering bertransaksi, dan berkontribusi besar.",
        actions: ["Tawarkan komunikasi personal dan evaluasi kebutuhan pengiriman.", "Pantau konsistensi layanan dan tangani keluhan dengan cepat.", "Pertimbangkan benefit loyalitas sesuai kebijakan perusahaan."]
      };
      else if (label.includes("Berisiko") || label.includes("perlu perhatian")) data = {
        icon: "↻", color: "#fce9ef", ink: "#b84d76", title: "Reaktivasi pelanggan",
        intro: "Lakukan pendekatan terarah kepada pelanggan yang sudah lama tidak bertransaksi atau menunjukkan penurunan aktivitas.",
        actions: ["Hubungi pelanggan untuk memahami hambatan penggunaan layanan.", "Kirim pengingat atau penawaran kembali yang relevan jika sesuai kebijakan.", "Pantau apakah pelanggan kembali melakukan transaksi."]
      };
      else if (label.includes("loyal") || label.includes("berkembang")) data = {
        icon: "↗", color: "#e5f8ef", ink: "#1b9568", title: "Tingkatkan pemesanan berulang",
        intro: "Bangun kebiasaan penggunaan layanan dan dorong pertumbuhan transaksi secara bertahap.",
        actions: ["Tanyakan rencana pengiriman atau kebutuhan periode berikutnya.", "Perkenalkan layanan yang relevan dengan pola transaksi pelanggan.", "Evaluasi frekuensi pemesanan dari periode ke periode."]
      };
      else data = {
        icon: "◎", color: "#eaf1ff", ink: "#3c70c8", title: "Kembangkan hubungan pelanggan",
        intro: "Pelajari kebutuhan pelanggan dan cari peluang meningkatkan frekuensi atau nilai transaksi.",
        actions: ["Lakukan follow-up untuk memahami kebutuhan pengiriman.", "Berikan informasi layanan yang relevan dan jelas.", "Tinjau perubahan RFM pada periode analisis berikutnya."]
      };
      return { cluster: c, label, ...data };
    });
    $("treatmentGrid").innerHTML = recommendations.map(x => `<article class="treatment-card"><div class="treatment-card-top"><span class="treatment-icon" style="background:${x.color};color:${x.ink}">${x.icon}</span><span class="segment-pill segment-${x.cluster.id + 1}">Cluster ${x.cluster.id + 1}</span></div><h3>${esc(x.title)}</h3><div class="segment-count">${fmtInt(x.cluster.count)} pelanggan · ${esc(x.label)}</div><p>${esc(x.intro)}</p><ul>${x.actions.map(a => `<li>${esc(a)}</li>`).join("")}</ul></article>`).join("");
  }

  function exportCSV() {
    if (!state.result) { toast("Belum ada hasil untuk diekspor."); return; }
    const rows = [["Pelanggan", "Recency_hari", "Frequency_transaksi", "Monetary_shipping_cost", "Cluster"]];
    state.result.rfm.forEach(c => rows.push([c.customer, c.recency, c.frequency, c.monetary, `Cluster ${c.cluster + 1}`]));
    const csv = "\uFEFF" + rows.map(row => row.map(v => `"${String(v ?? "").replace(/"/g, '""')}"`).join(",")).join("\r\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url; a.download = "pt_xyz_hasil_segmentasi_rfm.csv"; a.click();
    URL.revokeObjectURL(url); toast("File hasil segmentasi berhasil diunduh.");
  }

  function downloadTemplate() {
    const csv = "\uFEFFShipper,Invoice Number,Invoice Date,Shipping Cost\nContoh Shipper A,INV-001,2025-01-15,1500000\nContoh Shipper B,INV-002,2025-01-20,2750000\nContoh Shipper A,INV-003,2025-02-05,1800000\n";
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url; a.download = "template_transaksi_pt_xyz.csv"; a.click();
    URL.revokeObjectURL(url);
  }

  function resetFile() {
    state.workbookRows = []; state.headers = []; state.file = null; state.mapping = null;
    $("fileInput").value = ""; show($("filePreview"), false); show($("mappingCard"), false);
    $("analyzeButton").disabled = true; clearAlert();
  }

  function init() {
    $("yearNow").textContent = new Date().getFullYear();
    $("dateReference").value = new Date().toISOString().slice(0, 10);
    $("fileInput").addEventListener("change", e => readFile(e.target.files[0]));
    const dropzone = $("dropzone");
    dropzone.addEventListener("click", e => { if (e.target.tagName !== "LABEL") $("fileInput").click(); });
    dropzone.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); $("fileInput").click(); } });
    ["dragenter", "dragover"].forEach(name => dropzone.addEventListener(name, e => { e.preventDefault(); dropzone.classList.add("drag-over"); }));
    ["dragleave", "drop"].forEach(name => dropzone.addEventListener(name, e => { e.preventDefault(); dropzone.classList.remove("drag-over"); }));
    dropzone.addEventListener("drop", e => { const file = e.dataTransfer.files[0]; if (file) readFile(file); });
    $("removeFile").addEventListener("click", resetFile);
    $("confirmMapping").addEventListener("click", confirmMapping);
    $("analyzeButton").addEventListener("click", analyze);
    $("exportButton").addEventListener("click", exportCSV);
    $("downloadTemplate").addEventListener("click", e => { e.preventDefault(); downloadTemplate(); });
    $("customerSearch").addEventListener("input", () => { state.page = 0; if (state.result) renderCustomerTable(); });
    $("prevPage").addEventListener("click", () => { state.page--; renderCustomerTable(); });
    $("nextPage").addEventListener("click", () => { state.page++; renderCustomerTable(); });
    $("mobileMenu").addEventListener("click", () => $("sidebar").classList.toggle("open"));
    document.querySelectorAll(".nav-link").forEach(link => link.addEventListener("click", () => {
      document.querySelectorAll(".nav-link").forEach(item => item.classList.remove("active"));
      link.classList.add("active"); $("sidebar").classList.remove("open");
    }));
  }
  document.addEventListener("DOMContentLoaded", init);
})();