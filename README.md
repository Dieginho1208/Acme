# Acme Logistics Suite

A desktop **inventory, dispatch, billing and accounts-receivable** system for a
wholesale distributor, built with **Python, Tkinter and SQLite**, with no
third-party runtime dependencies.

It covers the whole path of an order: goods are received into bin locations,
shipped to a customer on a delivery note, approved by a manager, invoiced at
the customer's price list, and collected through payments that accounting
reviews before they count.

> This is a portfolio edition of a production system I designed and built for
> a manufacturing and distribution group. Company data, names and
> infrastructure details were removed, and the catalog is generated mock data
> (consumer electronics). See [Confidentiality](#confidentiality).

![Dashboard](docs/screenshots/dashboard.png)

## Quick start

```bash
git clone https://github.com/<your-user>/acme-logistics-suite.git
cd acme-logistics-suite
python setup_mock_db.py      # creates inventory_mock.db with demo data
python main.py               # opens the application
```

`python main.py` also generates the database on its first run if it is
missing. You need Python 3.10 or newer with Tkinter (included in the official
Windows and macOS installers; on Debian/Ubuntu install `python3-tk`).

Demo accounts (password `demo` for all of them):

| Username     | Role                 | What they see                                              |
|--------------|----------------------|------------------------------------------------------------|
| `admin`      | Administrator        | Everything, plus users, settings and the audit log         |
| `manager`    | Operations manager   | Stock, delivery note approval, customers, reports, audit   |
| `warehouse`  | Warehouse clerk      | Stock: receive, transfer, cycle counts                     |
| `sales`      | Sales representative | Only **their own** customers, notes, balances and payments |
| `accountant` | Accountant           | Price lists, invoicing, payment review, Legacy ERP exports |

## Features

**Inventory**
- 100 items in 10 categories, stored in 3 warehouses with aisle/rack/shelf bins.
- Receipts, transfers between bins or warehouses, and cycle-count adjustments
  with a mandatory reason. Stock can never go negative.
- A stock ledger: every movement is recorded, and the stock snapshot always
  equals the sum of the ledger (checked by the test-suite).
- Low-stock highlighting against each item's reorder point.

**Delivery notes**
- Issuing a note takes the goods out of their bins immediately.
- A manager approves it for invoicing or returns it to sales with a reason;
  sales can fix and resubmit it. Voiding a note puts the stock back.

**Billing**
- Dated price lists (default, wholesale, education...) with full price history:
  a new price applies from its start date and older prices are kept.
- Invoices are drafted from approved notes at the price valid on the invoice
  date; the accountant can edit a price, and edited lines are flagged.
- Voiding an invoice (only without payments) makes its notes billable again.

**Accounts receivable**
- Sales reps record payments for their customers; they stay *pending* until
  accounting matches them with the bank and approves or rejects them.
- Balances by customer, aging buckets (current, 1-30, 31-60, 61-90, 90+),
  overdue highlighting and a statement of account with running balance.

**Reports and Legacy ERP bridge**
- CSV exports: inventory valuation, receivables aging, customer statements.
- A CSV bridge to the *Legacy ERP* the company is phasing out: an all-or-nothing
  item catalog import with a dry run, and a sales ledger export in the layout
  the legacy accounting module imports. A sample file is in `samples/`.

**Cross-cutting**
- Role-based permissions defined in one table (`acme/core/security.py`).
- Salted PBKDF2 password hashes.
- An audit log of every change. Nothing is ever deleted: records are voided or
  deactivated, always with a reason.
- Slow screens load in a background thread, so the window never freezes.

| | |
|---|---|
| ![Inventory](docs/screenshots/inventory.png) | ![Delivery notes](docs/screenshots/delivery_notes.png) |
| ![Invoice editor](docs/screenshots/invoice_editor.png) | ![Receivables](docs/screenshots/receivables.png) |
| ![Price lists](docs/screenshots/price_lists.png) | ![Sales rep view](docs/screenshots/sales_rep_view.png) |

## Architecture

The code is split into a model layer that knows nothing about the user
interface and a view layer that knows nothing about SQL.

```
acme/
├── core/                    MODEL: storage and business rules (no Tkinter)
│   ├── database.py          SQLite schema, per-thread connections, transactions
│   ├── security.py          roles, permission table, password hashing
│   ├── money.py             integer-cent arithmetic and formatting
│   ├── context.py           composition root: builds every service
│   └── services/
│       ├── inventory.py     items, bins, stock ledger
│       ├── dispatch.py      delivery note life cycle
│       ├── billing.py       price lists, invoice drafts, invoices
│       ├── receivables.py   payments, approvals, aging, statements
│       ├── customers.py     customer master data and visibility rules
│       ├── reports.py       dashboard figures and CSV exports
│       ├── legacy_erp.py    CSV bridge to the Legacy ERP
│       ├── auth.py          sign-in and user administration
│       └── settings.py      company settings and tax rate
└── ui/                      VIEW + CONTROLLERS (Tkinter/ttk)
    ├── app.py               sign-in screen, main window, navigation
    ├── theme.py             colors, fonts, ttk styles
    ├── widgets.py           DataTable, FormDialog, KPI tiles, background tasks
    └── pages/               one module per screen
setup_mock_db.py             demo data generator
main.py                      entry point
tests/                       unittest suite
```

Design decisions:

- **Services own the rules.** Every operation that changes data checks the
  caller's permission, validates its input, runs in a single transaction and
  writes to the audit log. Errors are raised as `BusinessRuleError` with a
  message the UI shows as-is.
- **Views are thin.** Pages call services through an `AppContext` and render
  the result. Swapping Tkinter for a web front-end would not touch `acme/core`.
- **Money is stored in integer cents** and the tax rate in basis points, so
  totals never suffer from floating-point rounding.
- **Injectable clock.** The database takes a clock function. Tests use it to
  move time forward (aging), and the mock data generator uses it to create
  four months of realistic history *through the real services*, so the demo
  data obeys exactly the same rules as the application.
- **Thread safety.** SQLite connections are per thread, and Tkinter is only
  touched from the main thread (`run_in_background` hands results back with
  `after()`).

## Mock data

`setup_mock_db.py` builds `inventory_mock.db` from a fixed random seed, so
every run produces the same data:

- 100 consumer-electronics items (SKUs, EAN-13 barcodes, costs, prices,
  reorder points) from fictional brands;
- 3 warehouses with 62 bin locations, 24 business customers, 3 price lists;
- about 120 days of activity ending today: receipts, transfers, cycle counts
  and roughly 200 each of delivery notes (in every status), invoices and
  payments, including overdue balances and payments waiting for review.

```bash
python setup_mock_db.py --days 60 --seed 7 --path demo.db
python main.py --db demo.db
```

## Development

```bash
pip install -r requirements.txt   # optional: linters only
flake8 .                          # PEP 8 + docstrings, configured in setup.cfg
python -m unittest -v             # 45 tests; the UI smoke test needs a display
```

The GitHub Actions workflow runs the linter and the full test-suite (including
a smoke test that opens every page for every role under a virtual display) on
Python 3.10 and 3.12.

## Confidentiality

This repository contains no data from the original deployment. Company and
product names, people, customers, server addresses, credentials, document
numbering and the product catalog were replaced: the company is
*Acme Logistics*, the system being replaced is *Legacy ERP*, every person and
customer is fictional, and the catalog is generated. Demo passwords are only
for the generated database.

## License

[MIT](LICENSE)
