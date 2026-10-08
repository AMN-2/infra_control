"""A tiny in-memory stand-in for the parts of `frappe` the job engine touches.

Enough to run the engine end to end in pytest without a site: documents, `db.exists/get_value`,
`get_all`, `enqueue`, `publish_realtime`, `cache()` (a fake Redis), `conf`, roles.
"""

from __future__ import annotations

import itertools
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

SERIES = {
	"Infra Job": "JOB-",
	"Infra Audit Log": "AUD-",
	"Server": "SRV-",
	"Bench": "BENCH-",
	"Alert Rule": "RULE-",
}


class FakeRedis:
	def __init__(self) -> None:
		self.store: dict[str, str] = {}

	def set(self, name: str, value: str, *, nx: bool = False, ex: int | None = None) -> bool:
		if nx and name in self.store:
			return False
		self.store[name] = value
		return True

	def get(self, name: str) -> str | None:
		return self.store.get(name)

	def delete(self, *names: str) -> int:
		return sum(1 for n in names if self.store.pop(n, None) is not None)

	def eval(self, script: str, numkeys: int, *args: str) -> int:
		key, token = args[0], args[1]
		if self.store.get(key) == token:
			del self.store[key]
			return 1
		return 0


class _Response(dict):  # type: ignore[type-arg]
	"""frappe._dict-like: attribute access returns None for missing keys."""

	def __getattr__(self, item: str) -> Any:
		return self.get(item)


class FakeDoc:
	def __init__(self, frappe: FakeFrappe, data: dict[str, Any]) -> None:
		object.__setattr__(self, "_frappe", frappe)
		object.__setattr__(self, "_data", dict(data))
		object.__setattr__(self, "flags", SimpleNamespace(ignore_permissions=False))

	def __getattr__(self, item: str) -> Any:
		return self._data.get(item)

	def __setattr__(self, key: str, value: Any) -> None:
		self._data[key] = value

	def get(self, key: str, default: Any = None) -> Any:
		return self._data.get(key, default)

	def set(self, key: str, value: Any) -> None:
		self._data[key] = value

	def get_password(self, field: str) -> Any:
		return self._data.get(field)

	def is_new(self) -> bool:
		return self._data.get("name") is None

	def insert(self, ignore_permissions: bool = False) -> FakeDoc:
		dt = self._data["doctype"]
		if not self._data.get("name"):
			if dt == "Infra Job Step":
				self._data["name"] = f"{self._data['job']}-{self._data['step_index']}"
			else:
				self._data["name"] = f"{SERIES.get(dt, dt + '-')}{next(self._frappe.counter):05d}"
		self._data.setdefault("creation", self._frappe.now())
		self._frappe.store.setdefault(dt, {})[self._data["name"]] = self
		return self

	def save(self, ignore_permissions: bool = False) -> FakeDoc:
		return self.insert()

	def db_set(self, field: str | dict[str, Any], value: Any = None) -> None:
		if isinstance(field, dict):
			self._data.update(field)
		else:
			self._data[field] = value
		self._data["modified"] = self._frappe.now()

	def reload(self) -> None:
		pass

	def as_dict(self) -> dict[str, Any]:
		return dict(self._data)


class _Db:
	def __init__(self, frappe: FakeFrappe) -> None:
		self.f = frappe

	def exists(self, doctype: str, name: Any) -> Any:
		if isinstance(name, dict):
			return next(
				(
					n
					for n, d in self.f.store.get(doctype, {}).items()
					if all(d.get(k) == v for k, v in name.items())
				),
				None,
			)
		return name if name in self.f.store.get(doctype, {}) else None

	def get_value(self, doctype: str, filters: Any, fieldname: str = "name") -> Any:
		name = self.exists(doctype, filters)
		if not name:
			return None
		return self.f.store[doctype][name].get(fieldname)

	def get_single_value(self, doctype: str, field: str) -> Any:
		return self.f.singles.get(doctype, {}).get(field)

	def commit(self) -> None:
		self.f.commits += 1

	def count(self, doctype: str, filters: dict[str, Any] | None = None) -> int:
		return len(self.f._rows(doctype, filters))

	def rollback(self) -> None:
		self.f.rollbacks += 1


class FakeFrappe:
	def __init__(self, user: str = "admin@example.com", roles: tuple[str, ...] = ("Infra Admin",)) -> None:
		self.store: dict[str, dict[str, FakeDoc]] = {}
		self.singles: dict[str, dict[str, Any]] = {}
		self.counter = itertools.count(1)
		self.session = SimpleNamespace(user=user)
		self.roles: dict[str, tuple[str, ...]] = {user: roles}
		self.db = _Db(self)
		self.cache_client = FakeRedis()
		self.events: list[tuple[str, dict[str, Any]]] = []
		self.enqueued: list[dict[str, Any]] = []
		self.errors: list[str] = []
		self.conf: dict[str, Any] = {}
		self.rollbacks = 0
		self.local = SimpleNamespace(response=_Response({"docs": []}))
		self.clock = datetime(2026, 10, 7, 12, 0, 0, tzinfo=UTC).replace(tzinfo=None)
		self.commits = 0

	# --- time -------------------------------------------------------------------------
	def now(self) -> datetime:
		return self.clock

	# --- documents --------------------------------------------------------------------
	def add(self, doctype: str, **data: Any) -> FakeDoc:
		return FakeDoc(self, {"doctype": doctype, **data}).insert()

	def get_doc(self, doctype: str | dict[str, Any], name: Any = None) -> FakeDoc:
		if isinstance(doctype, dict):
			return FakeDoc(self, doctype)
		if isinstance(name, dict):
			name = self.db.exists(doctype, name)
		if name is None and doctype in self.singles:
			return FakeDoc(self, {"doctype": doctype, **self.singles[doctype]})
		try:
			return self.store[doctype][name]
		except KeyError:
			raise self.DoesNotExistError(f"{doctype} {name} not found") from None

	@staticmethod
	def _match(doc: FakeDoc, key: str, cond: Any) -> bool:
		value = doc.get(key)
		if isinstance(cond, list | tuple) and len(cond) == 2 and isinstance(cond[0], str):
			op, arg = cond
			if op == "in":
				return value in arg
			if op == "not in":
				return value not in arg
			if op == "!=":
				return value != arg
			if value is None:
				return False
			return {
				">": value > arg,
				">=": value >= arg,
				"<": value < arg,
				"<=": value <= arg,
				"=": value == arg,
				"like": str(arg).strip("%") in str(value),
			}[op]
		return value == cond

	def _rows(self, doctype: str, filters: dict[str, Any] | None) -> list[FakeDoc]:
		return [
			d
			for d in self.store.get(doctype, {}).values()
			if all(self._match(d, k, v) for k, v in (filters or {}).items())
		]

	def get_all(
		self,
		doctype: str,
		filters: dict[str, Any] | None = None,
		fields: list[str] | None = None,
		order_by: str = "",
		limit: int | None = None,
		pluck: str | None = None,
		**kw: Any,
	) -> list[Any]:
		rows = self._rows(doctype, filters)
		for clause in reversed([c.strip() for c in order_by.split(",") if c.strip()]):
			field, _, direction = clause.partition(" ")
			rows.sort(
				key=lambda d, f=field: (d.get(f) is None, d.get(f) if d.get(f) is not None else 0),
				reverse=direction.strip().lower() == "desc",
			)
		if pluck:
			out: list[Any] = [d.get(pluck) for d in rows]
		else:
			out = [{f: d.get(f) for f in (fields or ["name"])} for d in rows]
		return out[:limit] if limit else out

	def add_child(self, parent: FakeDoc, child_doctype: str, **data: Any) -> FakeDoc:
		siblings = [d for d in self.store.get(child_doctype, {}).values() if d.get("parent") == parent.name]
		return self.add(
			child_doctype, parent=parent.name, parenttype=parent.doctype, idx=len(siblings) + 1, **data
		)

	# --- services ---------------------------------------------------------------------
	def cache(self) -> FakeRedis:
		return self.cache_client

	def publish_realtime(self, event: str, message: dict[str, Any], **kw: Any) -> None:
		self.events.append((event, dict(message)))

	def enqueue(self, method: Any, **kw: Any) -> None:
		self.enqueued.append({"method": method, **kw})

	def get_roles(self, user: str | None = None) -> list[str]:
		return list(self.roles.get(user or self.session.user, ()))

	def log_error(self, title: str = "", message: str = "") -> None:
		self.errors.append(f"{title}: {message}")

	def get_traceback(self) -> str:
		return "traceback"

	class DoesNotExistError(Exception):
		pass

	def events_of(self, event: str) -> list[dict[str, Any]]:
		return [p for e, p in self.events if e == event]
