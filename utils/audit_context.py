from contextvars import ContextVar

"""
Identitas pengguna untuk pencatatan jejak audit.

Alternatifnya adalah menambahkan parameter `user_id` pada setiap method
penulisan, tetapi 40 dari 66 method belum menerimanya — mengubah tanda
tangannya berarti ikut mengubah controller dan rute untuk masing-masing,
tiga lapis sekaligus, dengan risiko satu lapis tertinggal dan gagal diam-diam.

Dengan context variable, identitas disimpan sekali per permintaan HTTP dan
dibaca langsung oleh pencatat audit. Aman untuk async: tiap permintaan punya
salinan konteksnya sendiri, tidak saling menimpa antar pengguna.
"""

_current_user_id: ContextVar[int | None] = ContextVar(
    "audit_current_user_id", default=None
)
_current_user_name: ContextVar[str | None] = ContextVar(
    "audit_current_user_name", default=None
)
_current_ip: ContextVar[str | None] = ContextVar("audit_current_ip", default=None)


def set_current_user(
    user_id: int | None,
    user_name: str | None = None,
    ip: str | None = None,
) -> None:
    _current_user_id.set(user_id)
    _current_user_name.set(user_name)
    _current_ip.set(ip)


def get_current_user_id() -> int | None:
    return _current_user_id.get()


def get_current_user_name() -> str | None:
    return _current_user_name.get()


def get_current_ip() -> str | None:
    return _current_ip.get()


def clear_current_user() -> None:
    set_current_user(None, None, None)