"""
Tidak ada bidang skema yang hanya menerima `None`.

`date: Optional[date] = None` di sebuah kelas membuat `date` bernilai `None`
untuk seluruh bidang SESUDAHNYA. `Optional[date]` di bawahnya lalu terbaca
`Optional[None]`, dan setiap tanggal ditolak 422 "Input should be None".
Itu yang membuat tender dengan batas penawaran tidak dapat disunting sama
sekali (22 Sep 2026). Uji ini menyapu SEMUA skema, bukan tender saja.
"""

import importlib
import inspect
import pkgutil
import types
import typing

import pytest
from pydantic import BaseModel

import schemas


def _hanya_none(a) -> bool:
    if a is type(None):
        return True
    if typing.get_origin(a) in (typing.Union, types.UnionType):
        return all(x is type(None) for x in typing.get_args(a))
    return False


def test_tidak_ada_bidang_yang_hanya_menerima_none():
    temuan, diperiksa = [], 0
    for m in pkgutil.iter_modules(schemas.__path__):
        mod = importlib.import_module(f"schemas.{m.name}")
        for nama, kelas in inspect.getmembers(mod, inspect.isclass):
            if not (issubclass(kelas, BaseModel) and kelas.__module__ == mod.__name__):
                continue
            for bidang, info in kelas.model_fields.items():
                diperiksa += 1
                if _hanya_none(info.annotation):
                    temuan.append(f"{m.name}.{nama}.{bidang}")
    assert diperiksa > 100, "pemeriksa tidak menemukan skema — salah tunjuk?"
    assert temuan == [], f"bidang yang hanya menerima None: {temuan}"


def test_tender_bisa_disunting_dengan_batas_penawaran():
    from schemas.tender_schema import TenderUpdate

    t = TenderUpdate(name="Ganti nama", date="2026-09-22", dueDate="2026-09-30")
    assert str(t.dueDate) == "2026-09-30"
