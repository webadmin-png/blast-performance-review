# Streamlit UI — Blast Performance Report

**Tanggal:** 2026-06-23
**Status:** Disetujui (brainstorming)

## Tujuan
Menyediakan antarmuka web (Streamlit) untuk menjalankan pipeline blast-performance
report secara interaktif: user memilih periode blast & channel, app menarik data
live dari Shopify, membangun report, lalu menampilkan tabel + tombol download CSV.

## Lingkup
- **Full pipeline, fetch live** dari Shopify Admin GraphQL.
- File tunggal `app.py` di root. Tidak mengubah `main.py` maupun fungsi pipeline
  yang ada — hanya memanggil ulang `get_campaign_data()`-style alur dan
  `build_blast_report()`.

## Input (sidebar)
- **Blast date 1** — `st.date_input`, default hari ini.
- **Blast date 2 (opsional)** — diaktifkan via checkbox "Add a 2nd blast date".
  Dua tanggal blast spesifik yang TIDAK harus berurutan; keduanya dianalisis dalam
  satu report, dan blast yang jatuh di antara kedua tanggal TIDAK ikut.
- **Carryover (hari)** — `number_input`, default **7**. Jumlah hari *setelah* blast
  yang ikut dihitung sebagai order carryover. Diterapkan per-blast (window masing-masing).
- **Channel** — pilihan Email / SMS / Keduanya (default Keduanya).
- Tombol **Generate Report**.

## Pemilihan blast & carryover per-blast
`filter_to_blast_dates()` (di `app.py`) menyaring `attentive_orders` agar hanya
berisi baris yang `blast_date`-nya termasuk tanggal terpilih DAN order day jatuh di
`[blast_date, blast_date + carryover_days]`. Ini: (a) mengecualikan blast di antara
dua tanggal, dan (b) mencegah carryover satu blast bocor ke blast lain. Hasil filter
diteruskan ke `build_blast_report` (fungsi report tidak diubah). `all_orders`
("All Sales") tidak difilter — tetap konteks penjualan semua channel di periode.

## Perhitungan tanggal
Dari input `blast_start`, `blast_end`, `carryover_days` (default 7) dan
`FETCH_PAD_DAYS = 7`:

- **Periode report** (dikirim ke `build_blast_report`): `[blast_start, blast_end + carryover_days]`.
  Ini sekaligus membatasi window "All Sales", blast yang ikut, dan batas carryover —
  sesuai desain fungsi report yang sudah ada.
- **Rentang fetch** (Shopify): `[blast_start - FETCH_PAD, blast_end + carryover_days + FETCH_PAD]`.
  Padding ±7 hari sebagai margin aman (padding mundur tidak mengubah output karena
  data sebelum `blast_start` difilter, tapi dipertahankan sebagai pengaman).

## Alur
1. Klik Generate → hitung rentang fetch.
2. `load_raw(fetch_start, fetch_end)` di-cache via `@st.cache_data` (key = rentang
   tanggal). Di dalamnya: `get_token()` → `settings.reload()` → `fetch_orders_utm()`.
   Toggle channel saja tidak memicu fetch ulang.
3. `transform_campaign_data(df)` → `attentive_orders`, `all_orders`.
4. Untuk tiap channel terpilih: `build_blast_report(...)`.

## Output (halaman utama)
- Spinner + status selama fetch (proses lama).
- Per channel: metrik ringkas (total unit & total gross sales) + `st.dataframe`
  report + tombol **Download CSV** (`df.to_csv`).
- Error ditangkap dan ditampilkan rapi (`st.error`) — kredensial gagal, tidak ada
  data, dll. App tidak crash.

## Perubahan lain
- Tambah `streamlit` ke `requirements.txt`.

## Catatan / batasan
- Memperpanjang `end` untuk carryover juga memperlebar window "All Sales" dan dapat
  menyertakan blast lain yang jatuh di rentang carryover. Ini perilaku yang
  diterima (tampilan "performa blast selama periode"), bukan bug.
- Bergantung pada `.env` + `service_account.json` yang sudah benar (sama seperti CLI).
