#!/usr/bin/env bash
# Kembalikan routes/salary_slip_routes.py ke versi sebelum zip kemarin
# (yang masih punya rute /bank/{employee_id}), lalu pasang ulang HANYA
# perubahan `keadaan`.
set -euo pipefail

git checkout 63d5e146 -- routes/salary_slip_routes.py

python3 - <<'PY'
import io
p = 'routes/salary_slip_routes.py'
s = io.open(p, encoding='utf-8').read()

assert '@router.get("/bank/{employee_id}")' in s, \
    'rute /bank/ tidak ada — periksa lagi commit yang dipulihkan'

lama = '''    sortBy: str = Query(None, description="Kolom: name, basicSalary, isPaid, department, position"),
    sortByDirection: str = Query("asc", description="asc atau desc"),
):
    """
    Fetch salary slips with pagination and optional keyword filtering.
    """
    try:
        result = await SalarySlipController.fetch(page, pageSize, keyword, month, year, sortBy, sortByDirection)'''

baru = '''    sortBy: str = Query(None, description="Kolom: name, basicSalary, isPaid, department, position"),
    sortByDirection: str = Query("asc", description="asc atau desc"),
    keadaan: str = Query(
        "aktif", description="aktif (bawaan), dihapus, atau semua"
    ),
):
    """
    Fetch salary slips with pagination and optional keyword filtering.

    Bawaan `keadaan` adalah "aktif" — pemanggil lama yang tidak menyebutnya
    karena itu berhenti menerima slip yang sudah dihapus, dan itu memang
    yang seharusnya sejak awal.
    """
    try:
        result = await SalarySlipController.fetch(page, pageSize, keyword, month, year, sortBy, sortByDirection, keadaan)'''

assert s.count(lama) == 1, f'pola fetch tidak cocok ({s.count(lama)} kemunculan)'
s = s.replace(lama, baru)
io.open(p, 'w', encoding='utf-8').write(s)

import ast
ast.parse(s)
print('OK — rute /bank/ kembali, parameter keadaan terpasang')
PY

python3 -m pytest test/slip_gaji_hapus_test.py -q 2>&1 | tail -5
