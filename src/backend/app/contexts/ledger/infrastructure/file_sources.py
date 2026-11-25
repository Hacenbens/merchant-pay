"""Read the challenge workbook (.xlsx) or a CSV into (row_number, canonical-key dict) pairs.

If the real workbook uses different headers, add them to HEADER_ALIASES; nothing else changes.
"""

import csv
from collections.abc import Iterator
from pathlib import Path

from openpyxl import load_workbook

from app.contexts.ledger.domain.row_parsing import REQUIRED_FIELDS
from app.shared.domain.enums import normalize_token

HEADER_ALIASES: dict[str, str] = {
    "transactionid": "transaction_id", "idtransaction": "transaction_id", "txnid": "transaction_id",
    "merchantid": "merchant_id", "idmarchand": "merchant_id", "idcommercant": "merchant_id",
    "datetime": "occurred_at", "date": "occurred_at", "dateheure": "occurred_at",
    "transactiondate": "occurred_at", "timestamp": "occurred_at", "transactiondatetime": "occurred_at",
    "amount": "amount", "amountdzd": "amount", "montant": "amount", "montantdzd": "amount",
    "channel": "channel", "paymentchannel": "channel", "canal": "channel",
    "canaldepaiement": "channel", "paymentmethod": "channel",
    "status": "status", "statut": "status", "transactionstatus": "status",
    "category": "category", "merchantcategory": "category", "categorie": "category",
    # optional, enriched data only. Deliberately NOT aliased from "customer id"-like headers.
    "customertoken": "customer_token",
}

Row = tuple[int, dict[str, object]]


def _header_map(headers: list[object]) -> dict[int, str]:
    mapping = {}
    for idx, h in enumerate(headers):
        canonical = HEADER_ALIASES.get(normalize_token(str(h or "")))
        if canonical and canonical not in mapping.values():
            mapping[idx] = canonical
    missing = set(REQUIRED_FIELDS) - set(mapping.values())
    if missing:
        raise ValueError(f"Missing columns {sorted(missing)}; found headers {headers}")
    return mapping


def read_xlsx(path: Path, sheet: str = "Transactions") -> Iterator[Row]:
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb[sheet] if sheet in wb.sheetnames else wb.worksheets[0]
    rows = ws.iter_rows(values_only=True)
    mapping = _header_map(list(next(rows)))
    for number, values in enumerate(rows, start=2):
        if all(v is None for v in values):
            continue
        yield number, {key: values[i] for i, key in mapping.items() if i < len(values)}


def read_csv(path: Path) -> Iterator[Row]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.reader(fh)
        mapping = _header_map(next(reader))
        for number, values in enumerate(reader, start=2):
            if not any(values):
                continue
            yield number, {key: values[i] for i, key in mapping.items() if i < len(values)}


def read_any(path: Path) -> Iterator[Row]:
    return read_csv(path) if path.suffix.lower() == ".csv" else read_xlsx(path)
