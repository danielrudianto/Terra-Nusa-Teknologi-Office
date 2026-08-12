"""
Modul yang menjadi wilayah tiap departemen.

Ini KEBIJAKAN, bukan aturan teknis — susunannya menentukan siapa melihat apa,
jadi ubahannya perlu sepengetahuan pemilik proses, bukan sekadar keputusan
teknis di tengah pengerjaan.

Cara membacanya bersama matriks level:

    departemen -> modul apa yang menjadi urusannya
    level      -> sejauh apa yang boleh dilakukan pada modul itu

Keduanya harus terpenuhi. Seorang level 3 di accounting boleh menghapus data
pembelian, tetapi tidak melihat modul procurement sama sekali; sebaliknya
level 3 di procurement boleh menghapus purchase order, tetapi tidak menyentuh
pembukuan.

Modul yang tidak tercantum pada departemen mana pun hanya dapat dibuka lewat
izin khusus per pengguna, atau oleh level 5.
"""

# Beberapa modul dipakai lintas departemen dan tidak menyimpan data yang perlu
# dibatasi wilayahnya.
UMUM = {
    "dashboard",
    "calendar",
    "user_avatar",
}

DEPARTMENT_MODULES: dict[str, set[str]] = {
    "procurement": UMUM
    | {
        "purchase_order",
        "purchase_draft",
        "supplier",
        "master_item",
        "master_equipment",
        "asset",
        "client",
    },
    "accounting": UMUM
    | {
        "purchase",
        "expenses",
        "expense_opponent",
        "income",
        "sales_invoice",
        "reimbursement",
        "interpayment",
        "client",
        "supplier",
        "purchase_order",
    },
    "finance": UMUM
    | {
        "bank",
        "payment_incoming",
        "payment_outgoing",
        "interpayment",
        "loan",
        "expenses",
        "reimbursement",
    },
    "taxing": UMUM
    | {
        "tax",
        "purchase",
        "sales_invoice",
        "income",
        "expenses",
    },
    "hrd": UMUM
    | {
        "employees",
        # Slip gaji tetap bernilai 9 pada matriks level, sehingga masuk
        # departemen ini pun belum membukanya — tetap perlu izin khusus.
        # Disebut di sini agar wilayahnya jelas, bukan agar terbuka.
        "salary_slip",
    },
    "engineering": UMUM
    | {
        "asset",
        "master_equipment",
        "purchase_order",
        "purchase_draft",
    },
}


def modules_for(departments: set[str]) -> set[str]:
    """
    Gabungan modul dari seluruh departemen yang dipegang seseorang.

    Bergabung, bukan beririsan: orang yang menangani dua wilayah melihat
    keduanya.
    """
    hasil: set[str] = set()
    for d in departments or ():
        hasil |= DEPARTMENT_MODULES.get(d, set())
    return hasil
