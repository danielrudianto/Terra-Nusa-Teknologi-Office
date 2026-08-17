import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import utils.config

from utils.logger_utils import log_info
from utils.database import engine, metadata

import models.user_model  # Import the user model to create the table
import models.purchase_model  # Import the purchase model to create the table
import models.supplier_model  # Import the supplier model to create the table
import models.purchase_order_model  # Import the purchase order model to create the table
import models.client_model  # Import the client model to create the table
import models.reimbursement_model  # Import the reimbursement model to create the table
import models.bank_model # Import the bank model to create the table
import models.expense_model # Import the expense model to create the table
import models.payment_outgoing_model  # Import the payment model to create the table
import models.employee_model  # Import the employee model to create the table
import models.expense_opponent_model  # Import the expense opponent model to create the table
import models.salary_slip_model  # Import the salary slip model to create the table
import models.interpayment_model  # Import the interpayment model to create the table
import models.sales_invoice_model  # Import the sales invoice model to create the table
import models.reminder_model  # pengingat agenda beserta orang yang ditandai

# Model di bawah ini sempat TIDAK diimpor, sehingga tabelnya tidak pernah
# ikut dibuat `metadata.create_all`.
#
# Tabel yang sudah lebih dulu ada di produksi tidak terpengaruh — `checkfirst`
# melewatinya. Yang bermasalah adalah tabel BARU: `employee_form_submissions`
# dan `employee_profiles` tidak pernah terbentuk, sehingga penyimpanan
# jawabannya gagal pada basis data yang baru disiapkan.
#
# `mutation_model` sengaja tidak disertakan: tabelnya dibaca lewat
# `autoload_with`, bukan didefinisikan di kode, sehingga tidak ada yang dapat
# dibuat darinya.
import models.asset_model  # aset perusahaan
import models.audit_log_model  # jejak perubahan data
import models.balance_model  # saldo rekening
import models.bank_mutation_model  # mutasi rekening
import models.employee_form_model  # formulir pembaruan data karyawan beserta jawabannya
import models.employee_profile_model  # profil pribadi karyawan
import models.income_model  # pendapatan lain
import models.loans_model  # pinjaman
import models.master_equipment_model  # katalog alat sewa
import models.master_item_model  # katalog barang
import models.payment_incoming_model  # pembayaran masuk
import models.project_model  # proyek
import models.purchase_draft_model  # draf pembelian
import models.purchase_order_item_model  # baris barang purchase order
import models.user_avatar_model  # avatar pengguna
import models.user_department_model  # divisi pengguna
import models.user_permission_model  # izin khusus per pengguna
import models.hr_recruitment_model  # ujian rekrutmen HR

if __name__ == "__main__":
    metadata.create_all(engine, checkfirst=True)
    log_info("All tables created successfully.")
