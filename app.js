/* PT. XYZ Customer Intelligence - data processing utilities.
   Browser-only demo: no uploaded data is sent to a server. */
(function () {
  "use strict";

  const COLORS = ["#3c78e8", "#ff8a24", "#1eaa78", "#8b67d5", "#3e9bb8", "#d45d82"];
  const norm = (v) => String(v ?? "").trim().toLowerCase().replace(/[\s_\-./()]+/g, "");
  const DATE_HINTS = ["tanggalinvoice", "invoicedate", "tanggal", "date", "tglinvoice", "tgl"];
  const CUSTOMER_HINTS = ["shipper", "customer", "pelanggan", "namacustomer", "namapelanggan", "customername", "shippername", "custid", "customerid"];
  const INVOICE_HINTS = ["invoice", "noinvoice", "nomorinvoice", "invoicenumber", "invoiceno", "faktur"];
  const COST_HINTS = ["shippingcost", "shippingcostidr", "biayapengiriman", "ongkirkirim", "cost", "dpp", "revenue", "amount", "nilaiinvoice"];

  function parseNumber(value) {
    if (typeof value === "number" && Number.isFinite(value)) return value;
    if (value == null || value === "") return NaN;
    let s = String(value).trim().replace(/[Rp\s]/gi, "").replace(/[^\d,.-]/g, "");
    if (!s) return NaN;
    // Handle Indonesian numbers (1.234.567,89) and plain decimal numbers.
    if (s.includes(",") && s.includes(".")) {
      if (s.lastIndexOf(",") > s.lastIndexOf(".")) s = s.replace(/\./g, "").replace(",", ".");
      else s = s.replace(/,/g, "");
    } else if (s.includes(",")) {
      const tail = s.split(",").pop();
      s = tail.length === 3 ? s.replace(/,/g, "") : s.replace(",", ".");
    } else if (/^-?\d{1,3}(\.\d{3})+$/.test(s)) {
      s = s.replace(/\./g, "");
    }
    const n = Number(s);
    return Number.isFinite(n) ? n : NaN;
  }

  function parseDate(value) {
    if (value instanceof Date && !isNaN(value)) return value;
    if (typeof value === "number" && window.XLSX && XLSX.SSF) {
      const p = XLSX.SSF.parse_date_code(value);
      if (p) return new Date(p.y, p.m - 1, p.d);
    }
    if (value == null || value === "") return null;
    const s = String(value).trim();
    // Explicitly parse common Indonesian date format dd/mm/yyyy.
    const m = s.match(/^(\d{1,2})[\/.-](\d{1,2})[\/.-](\d{2,4})$/);
    if (m) {
      let year = Number(m[3]); if (year < 100) year += year < 50 ? 2000 : 1900;
      const d = new Date(year, Number(m[2]) - 1, Number(m[1]));
      return isNaN(d) ? null : d;
    }
    const d = new Date(s);
    return isNaN(d) ? null : d;
  }

  function guessColumn(headers, hints) {
    const normalized = headers.map(norm);
    // Prefer exact matches first, then substring matches.
    for (const hint of hints) {
      const idx = normalized.findIndex(h => h === norm(hint));
      if (idx >= 0) return headers[idx];
    }
    for (const hint of hints) {
      const idx = normalized.findIndex(h => h.includes(norm(hint)));
      if (idx >= 0) return headers[idx];
    }
    return headers[0] || "";
  }

  function minMax(values) {
    const min = Math.min(...values), max = Math.max(...values);
    return values.map(v => max === min ? 0 : (v - min) / (max - min));
  }

  function distance(a, b) {
    let total = 0;
    for (let i = 0; i < a.length; i++) total += (a[i] - b[i]) ** 2;
    return Math.sqrt(total);
  }

  function kmeans(points, k, maxIterations = 100) {
    if (points.length < k) throw new Error(`Jumlah pelanggan (${points.length}) harus minimal sama dengan jumlah cluster (${k}).`);
    // Deterministic farthest-first initialization, more stable than arbitrary random starts.
    const centroids = [points[0].slice()];
    while (centroids.length < k) {
      let farthest = null, farthestDistance = -1;
      for (const point of points) {
        const nearest = Math.min(...centroids.map(c => distance(point, c)));
        if (nearest > farthestDistance) { farthestDistance = nearest; farthest = point; }
      }
      centroids.push(farthest.slice());
    }
    let labels = new Array(points.length).fill(-1);
    for (let iter = 0; iter < maxIterations; iter++) {
      let changed = false;
      for (let i = 0; i < points.length; i++) {
        let best = 0, bestDist = Infinity;
        for (let c = 0; c < centroids.length; c++) {
          const d = distance(points[i], centroids[c]);
          if (d < bestDist) { bestDist = d; best = c; }
        }
        if (labels[i] !== best) { labels[i] = best; changed = true; }
      }
      const sums = Array.from({ length: k }, () => [0, 0, 0]);
      const counts = new Array(k).fill(0);
      points.forEach((p, i) => { counts[labels[i]]++; p.forEach((v, j) => sums[labels[i]][j] += v); });
      for (let c = 0; c < k; c++) {
        if (counts[c]) centroids[c] = sums[c].map(v => v / counts[c]);
        else {
          // Re-seed empty cluster to the point farthest from its nearest centroid.
          let idx = 0, maxD = -1;
          points.forEach((p, i) => {
            const d = Math.min(...centroids.filter((_, ci) => ci !== c).map(center => distance(p, center)));
            if (d > maxD) { maxD = d; idx = i; }
          });
          centroids[c] = points[idx].slice();
        }
      }
      if (!changed && iter > 0) break;
    }
    return { labels, centroids };
  }

  function silhouette(points, labels, k) {
    // Exact silhouette can be expensive for large datasets; use a deterministic sample up to 500 rows.
    const n = points.length;
    if (k < 2 || n <= k || n > 12000) return null;
    const indices = n <= 500 ? Array.from({ length: n }, (_, i) => i) :
      Array.from({ length: 500 }, (_, i) => Math.floor(i * (n - 1) / 499));
    const clusterMembers = Array.from({ length: k }, () => []);
    labels.forEach((label, i) => clusterMembers[label].push(i));
    if (clusterMembers.some(group => group.length === 0)) return null;
    let total = 0, valid = 0;
    for (const i of indices) {
      const own = clusterMembers[labels[i]];
      if (own.length <= 1) { total += 0; valid++; continue; }
      let aSum = 0;
      for (const j of own) if (j !== i) aSum += distance(points[i], points[j]);
      const a = aSum / (own.length - 1);
      let b = Infinity;
      for (let c = 0; c < k; c++) {
        if (c === labels[i] || !clusterMembers[c].length) continue;
        let sum = 0;
        for (const j of clusterMembers[c]) sum += distance(points[i], points[j]);
        b = Math.min(b, sum / clusterMembers[c].length);
      }
      if (Number.isFinite(b)) { total += (b - a) / Math.max(a, b, 1e-12); valid++; }
    }
    return valid ? total / valid : null;
  }

  function buildRFM(rows, mapping, snapshotDate) {
    const transactions = [];
    const invalid = { customer: 0, date: 0, cost: 0 };
    for (const row of rows) {
      const customer = String(row[mapping.customer] ?? "").trim();
      const invoice = String(row[mapping.invoice] ?? "").trim();
      const date = parseDate(row[mapping.date]);
      const cost = parseNumber(row[mapping.cost]);
      if (!customer) { invalid.customer++; continue; }
      if (!date) { invalid.date++; continue; }
      if (!Number.isFinite(cost)) { invalid.cost++; continue; }
      transactions.push({ customer, invoice: invoice || `${customer}-${date.getTime()}`, date, cost });
    }
    if (!transactions.length) throw new Error("Tidak ada transaksi valid. Periksa kolom pelanggan, tanggal invoice, dan shipping cost.");
    const customers = new Map();
    for (const tx of transactions) {
      if (!customers.has(tx.customer)) customers.set(tx.customer, { customer: tx.customer, invoices: new Set(), lastDate: tx.date, monetary: 0, transactionCount: 0 });
      const c = customers.get(tx.customer);
      c.invoices.add(tx.invoice);
      if (tx.date > c.lastDate) c.lastDate = tx.date;
      c.monetary += tx.cost;
      c.transactionCount++;
    }
    const snapshot = snapshotDate ? new Date(`${snapshotDate}T23:59:59`) :
      new Date(Math.max(...transactions.map(t => t.date.getTime())));
    const rfm = Array.from(customers.values()).map(c => ({
      customer: c.customer,
      recency: Math.max(0, Math.floor((snapshot - c.lastDate) / 86400000)),
      frequency: c.invoices.size,
      monetary: c.monetary,
      lastDate: c.lastDate,
      transactionRows: c.transactionCount
    }));
    return { transactions, rfm, invalid, snapshot };
  }

  function analyze(rows, mapping, snapshotDate, k) {
    const built = buildRFM(rows, mapping, snapshotDate);
    const r = built.rfm.map(x => x.recency), f = built.rfm.map(x => x.frequency), m = built.rfm.map(x => x.monetary);
    // Recency is reversed so a smaller normalized value means more recent activity and higher score.
    const nr = minMax(r).map(v => 1 - v), nf = minMax(f), nm = minMax(m);
    const points = built.rfm.map((_, i) => [nr[i], nf[i], nm[i]]);
    const clustered = kmeans(points, k);
    const labels = clustered.labels;
    built.rfm.forEach((customer, i) => { customer.cluster = labels[i]; });
    const clusters = Array.from({ length: k }, (_, id) => {
      const members = built.rfm.filter(c => c.cluster === id);
      const avg = key => members.length ? members.reduce((sum, c) => sum + c[key], 0) / members.length : 0;
      return {
        id, count: members.length,
        avgRecency: avg("recency"), avgFrequency: avg("frequency"), avgMonetary: avg("monetary"),
        totalMonetary: members.reduce((s, c) => s + c.monetary, 0),
        centroid: clustered.centroids[id]
      };
    });
    const silhouetteScore = silhouette(points, labels, k);
    const totalMonetary = built.transactions.reduce((s, t) => s + t.cost, 0);
    return { ...built, clusters, silhouetteScore, k, totalMonetary, normalizedPoints: points };
  }

  window.PTXYZApp = { COLORS, parseNumber, parseDate, guessColumn, analyze, norm };
})();