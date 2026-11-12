#!/usr/bin/env python3
"""Create ``inventory_mock.db``: a realistic, fully fictional demo database.

The script builds the schema and fills it with:

* 100 electronics items across 10 categories (SKUs, barcodes, costs, prices,
  reorder points) stored in 3 warehouses with aisle/rack/shelf locations;
* 6 demo users, one per role (password ``demo`` for all of them);
* 3 price lists with price history, and 24 business customers;
* about four months of activity -- receipts, transfers, cycle-count
  adjustments, delivery notes in every status, invoices and payments --
  generated *through the real business services*, so every record obeys the
  same rules as the application.

All names, companies, brands, addresses and tax ids are invented. The data is
generated from a fixed random seed, so every run produces the same database.

Usage::

    python setup_mock_db.py                 # creates ./inventory_mock.db
    python setup_mock_db.py --path demo.db  # somewhere else
    python setup_mock_db.py --days 60       # shorter history
"""

import argparse
import datetime as dt
import random
import sys
from pathlib import Path

from acme.config import default_db_path
from acme.core.context import AppContext
from acme.core.errors import BusinessRuleError

DEMO_PASSWORD = "demo"

USERS = (
    ("admin", "Avery Collins", "admin"),
    ("manager", "Jordan Blake", "manager"),
    ("warehouse", "Sam Ortega", "warehouse"),
    ("sales", "Riley Chen", "sales"),
    ("sales2", "Morgan Patel", "sales"),
    ("accountant", "Casey Novak", "accountant"),
)

WAREHOUSES = (
    ("MAIN", "Main Distribution Center", ("A", "B", "C"), 4, 3),
    ("EAST", "East Fulfillment Hub", ("A", "B"), 3, 3),
    ("SHOP", "Downtown Showroom", ("S",), 4, 2),
)

# category -> SKU prefix and (name, brand, unit cost, unit price, reorder point)
CATALOG = {
    ("Computer Peripherals", "PER"): (
        ("Wireless Mouse", "Voltix", 9.80, 19.99, 40),
        ("Ergonomic Vertical Mouse", "Kestrel", 17.50, 34.99, 20),
        ("Mechanical Keyboard (Brown Switches)", "Corebit", 42.00, 89.99, 15),
        ("Low-Profile Wireless Keyboard", "Voltix", 21.00, 44.99, 20),
        ("Full HD Webcam 1080p", "Pixelon", 24.50, 49.99, 15),
        ("4K Streaming Webcam", "Pixelon", 61.00, 119.00, 8),
        ("Large Desk Mat 900 x 400 mm", "Halcyon", 6.20, 16.99, 25),
        ("Graphics Drawing Tablet", "Lumora", 38.00, 79.99, 6),
        ("USB Numeric Keypad", "Corebit", 7.40, 15.99, 15),
        ("Wireless Presenter Remote", "Kestrel", 11.30, 24.99, 10),
    ),
    ("Audio", "AUD"): (
        ("Noise-Cancelling Headphones", "Northwave", 72.00, 149.00, 10),
        ("True Wireless Earbuds", "Northwave", 28.00, 59.99, 25),
        ("USB Condenser Microphone", "Ardent", 33.00, 69.99, 10),
        ("Bluetooth Portable Speaker", "Tessera", 22.00, 45.99, 15),
        ("Soundbar 2.1 with Subwoofer", "Tessera", 88.00, 179.00, 5),
        ("Wired Office Headset with Mic", "Ardent", 14.50, 29.99, 20),
        ("Studio Monitor Headphones", "Northwave", 46.00, 94.99, 6),
        ("Desktop Speakers 2.0", "Tessera", 19.00, 39.99, 10),
        ("Headphone Stand with USB Hub", "Halcyon", 12.00, 27.99, 8),
        ("Microphone Boom Arm", "Ardent", 13.50, 29.99, 8),
    ),
    ("Networking", "NET"): (
        ("Dual-Band Wi-Fi 6 Router", "Quillon", 54.00, 109.00, 10),
        ("Mesh Wi-Fi System (3-Pack)", "Quillon", 129.00, 259.00, 4),
        ("8-Port Gigabit Switch", "Quillon", 18.00, 36.99, 12),
        ("24-Port Managed Switch", "Quillon", 119.00, 239.00, 3),
        ("USB Wi-Fi Adapter AC1300", "Voltix", 11.00, 23.99, 15),
        ("Powerline Adapter Kit", "Quillon", 32.00, 64.99, 6),
        ("Cat6 Patch Cable 2 m", "Corebit", 1.40, 4.99, 100),
        ("Cat6 Patch Cable 10 m", "Corebit", 3.90, 11.99, 50),
        ("Wi-Fi Range Extender", "Quillon", 17.00, 34.99, 10),
        ("PoE Injector 30 W", "Quillon", 9.50, 21.99, 8),
    ),
    ("Storage", "STO"): (
        ("Portable SSD 1 TB", "Lumora", 58.00, 109.00, 12),
        ("Portable SSD 2 TB", "Lumora", 96.00, 179.00, 6),
        ("NVMe SSD 1 TB (M.2 2280)", "Corebit", 49.00, 94.99, 10),
        ("External Hard Drive 4 TB", "Lumora", 67.00, 119.00, 8),
        ("USB 3.2 Flash Drive 64 GB", "Voltix", 4.10, 10.99, 60),
        ("USB 3.2 Flash Drive 256 GB", "Voltix", 13.00, 27.99, 30),
        ("microSD Card 128 GB", "Pixelon", 8.20, 17.99, 40),
        ("2-Bay NAS Enclosure", "Corebit", 148.00, 289.00, 3),
        ("SATA SSD 500 GB", "Corebit", 26.00, 49.99, 12),
        ("SD Card Reader USB-C", "Voltix", 5.60, 13.99, 20),
    ),
    ("Cables & Adapters", "CAB"): (
        ("USB-C to USB-C Cable 1 m", "Voltix", 2.30, 8.99, 80),
        ("USB-C to Lightning Cable 1 m", "Voltix", 3.10, 12.99, 60),
        ("HDMI 2.1 Cable 2 m", "Corebit", 3.80, 13.99, 50),
        ("DisplayPort 1.4 Cable 2 m", "Corebit", 4.20, 14.99, 30),
        ("USB-C to HDMI Adapter", "Kestrel", 6.50, 18.99, 30),
        ("USB-C 7-in-1 Hub", "Kestrel", 14.00, 34.99, 20),
        ("USB-A to USB-C Adapter (2-Pack)", "Voltix", 1.60, 6.99, 60),
        ("Universal Travel Adapter", "Halcyon", 8.90, 22.99, 15),
        ("Braided Micro-USB Cable 2 m", "Voltix", 1.90, 7.99, 40),
        ("Thunderbolt 4 Cable 0.8 m", "Corebit", 15.00, 34.99, 10),
    ),
    ("Power & Charging", "PWR"): (
        ("65 W GaN USB-C Charger", "Ardent", 15.50, 39.99, 25),
        ("20 W USB-C Wall Charger", "Ardent", 4.80, 14.99, 50),
        ("Power Bank 10,000 mAh", "Ardent", 10.50, 24.99, 30),
        ("Power Bank 20,000 mAh with PD", "Ardent", 19.00, 44.99, 15),
        ("3-in-1 Wireless Charging Stand", "Halcyon", 21.00, 49.99, 10),
        ("Surge Protector 8 Outlets", "Halcyon", 12.50, 29.99, 15),
        ("Line-Interactive UPS 1000 VA", "Ardent", 79.00, 149.00, 4),
        ("Car Charger Dual USB-C", "Ardent", 5.20, 14.99, 25),
        ("AA Rechargeable Batteries (8-Pack)", "Tessera", 7.30, 17.99, 30),
        ("Smart Plug (2-Pack)", "Halcyon", 9.00, 21.99, 20),
    ),
    ("Displays", "DSP"): (
        ("24-inch IPS Monitor 1080p", "Pixelon", 92.00, 159.00, 6),
        ("27-inch QHD Monitor 165 Hz", "Pixelon", 179.00, 299.00, 4),
        ("32-inch 4K UHD Monitor", "Pixelon", 248.00, 419.00, 3),
        ("Portable USB-C Monitor 15.6-inch", "Lumora", 89.00, 169.00, 4),
        ("Dual Monitor Desk Mount", "Halcyon", 31.00, 64.99, 6),
        ("Single Monitor Arm", "Halcyon", 19.00, 39.99, 8),
        ("Laptop Stand (Aluminum)", "Halcyon", 13.00, 29.99, 15),
        ("Screen Cleaning Kit", "Tessera", 2.40, 8.99, 40),
        ("Privacy Filter 24-inch", "Kestrel", 22.00, 49.99, 6),
        ("Full HD Mini Projector", "Lumora", 112.00, 219.00, 3),
    ),
    ("PC Components", "CMP"): (
        ("DDR4 RAM 16 GB (2 x 8 GB) 3200", "Corebit", 29.00, 54.99, 12),
        ("DDR5 RAM 32 GB (2 x 16 GB) 5600", "Corebit", 68.00, 119.00, 6),
        ("650 W 80+ Gold Power Supply", "Ardent", 52.00, 94.99, 5),
        ("Mid-Tower ATX Case", "Halcyon", 44.00, 84.99, 4),
        ("CPU Air Cooler 120 mm", "Kestrel", 17.00, 34.99, 8),
        ("120 mm Case Fan (3-Pack)", "Kestrel", 11.00, 24.99, 12),
        ("Thermal Paste 4 g", "Kestrel", 2.10, 7.99, 30),
        ("PCIe Wi-Fi 6E Card", "Quillon", 21.00, 42.99, 6),
        ("Anti-Static Wrist Strap", "Tessera", 1.20, 5.99, 20),
        ("Precision Screwdriver Kit (64-Piece)", "Tessera", 9.40, 24.99, 12),
    ),
    ("Smart Home", "SMH"): (
        ("Smart LED Bulb E26 (4-Pack)", "Lumora", 14.00, 32.99, 15),
        ("Indoor Wi-Fi Security Camera", "Pixelon", 18.50, 39.99, 12),
        ("Outdoor Security Camera 2K", "Pixelon", 41.00, 84.99, 6),
        ("Video Doorbell", "Pixelon", 47.00, 99.99, 5),
        ("Smart Thermostat", "Halcyon", 64.00, 129.00, 4),
        ("Door & Window Sensor (3-Pack)", "Halcyon", 12.00, 27.99, 10),
        ("Smart Home Hub", "Quillon", 33.00, 69.99, 5),
        ("Motion Sensor", "Halcyon", 7.80, 17.99, 12),
        ("Smart LED Light Strip 5 m", "Lumora", 11.50, 26.99, 15),
        ("Robot Vacuum (Wi-Fi)", "Tessera", 119.00, 229.00, 3),
    ),
    ("Mobile Accessories", "MOB"): (
        ("Phone Car Mount (Magnetic)", "Kestrel", 5.10, 15.99, 25),
        ("Tempered Glass Screen Protector", "Tessera", 0.90, 9.99, 100),
        ("Shockproof Phone Case", "Tessera", 2.60, 14.99, 60),
        ("Tablet Folio Case 11-inch", "Tessera", 7.20, 24.99, 15),
        ("Phone Tripod with Remote", "Kestrel", 8.40, 21.99, 15),
        ("Selfie Ring Light 10-inch", "Lumora", 9.90, 24.99, 10),
        ("Smartwatch Band (Silicone)", "Tessera", 1.80, 9.99, 40),
        ("Stylus Pen for Tablets", "Kestrel", 6.30, 19.99, 15),
        ("Fitness Tracker Band", "Northwave", 17.00, 39.99, 10),
        ("Wireless Charging Pad 15 W", "Halcyon", 6.90, 18.99, 25),
    ),
}

CUSTOMERS = (
    ("Brightline Retail Co.", "Cedar Falls"), ("Summit Office Supply", "Lakeview"),
    ("Northgate Electronics", "Riverton"), ("Bluebird Learning Center", "Maple Ridge"),
    ("Harbor Point Hotels", "Port Ellis"), ("Keystone Medical Group", "Fairmont"),
    ("Pinecrest Coworking", "Glenwood"), ("Redwood Logistics LLC", "Ashford"),
    ("Silverline Gaming Lounge", "Westbrook"), ("Oakmont Public Library", "Oakmont"),
    ("Granite State Realty", "Stonebridge"), ("Clearwater Dental", "Clearwater"),
    ("Metro Print & Copy", "Midtown"), ("Evergreen Insurance Partners", "Elmhurst"),
    ("Orchard Valley School District", "Orchard Valley"), ("Lighthouse Cafe Group", "Bayside"),
    ("Copperfield Engineering", "Copperfield"), ("Sunrise Fitness Studios", "Sunnyvale"),
    ("Tallgrass Veterinary Clinic", "Prairie View"), ("Union Street Law Office", "Union City"),
    ("Willow Creek Apartments", "Willow Creek"), ("Atlas Construction Co.", "Granite Bay"),
    ("Beacon Photography Studio", "Harborview"), ("Quarry Hill Tech Repair", "Quarry Hill"),
)

STREETS = ("Main St", "Oak Ave", "Market St", "Elm St", "Park Blvd", "Lake Rd", "Pine St",
           "Harbor Way", "Cedar Ln", "Hillside Dr")


class SimulatedClock:
    """A clock that the generator moves forward day by day."""

    def __init__(self, start: dt.datetime):
        self.current = start

    def __call__(self) -> dt.datetime:
        """Return the simulated "now"."""
        return self.current

    def set(self, day: dt.date, hour: int, minute: int = 0) -> None:
        """Jump to ``day`` at ``hour:minute``."""
        self.current = dt.datetime.combine(day, dt.time(hour, minute))


class MockDataBuilder:
    """Fill a fresh database with demo data using the business services."""

    def __init__(self, path: Path, days: int, seed: int):
        self.today = dt.date.today()
        self.start = self.today - dt.timedelta(days=days)
        self.days = days
        self.rng = random.Random(seed)
        self.clock = SimulatedClock(dt.datetime.combine(self.start, dt.time(8)))
        self.app = AppContext(path, clock=self.clock)
        self.users = {}
        self.items = []
        self.locations = {}
        self.customers = []
        self.lists = {}

    # ------------------------------------------------------------------ build steps
    def build(self) -> dict:
        """Run every step and return a summary of what was created."""
        self._create_users()
        self._create_warehouses()
        self._create_catalog()
        self._create_price_lists()
        self._create_customers()
        self._initial_stock()
        for offset in range(1, self.days + 1):
            self._simulate_day(self.start + dt.timedelta(days=offset))
        self._finishing_touches()
        db = self.app.db
        summary = {table: db.scalar(f"SELECT COUNT(*) FROM {table}", (), 0) for table in (
            "items", "customers", "stock_movements", "delivery_notes", "invoices", "payments")}
        self.app.close()
        return summary

    def _create_users(self) -> None:
        for username, full_name, role in USERS:
            self.app.auth.create_user(None, username, full_name, role, DEMO_PASSWORD)
        for user in self.app.auth.list_users():
            self.users[user["username"]] = self.app.auth.login(user["username"], DEMO_PASSWORD)

    def _create_warehouses(self) -> None:
        admin = self.users["admin"]
        for code, name, aisles, racks, shelves in WAREHOUSES:
            warehouse_id = self.app.inventory.create_warehouse(admin, code, name)
            ids = []
            for aisle in aisles:
                for rack in range(1, racks + 1):
                    for shelf in range(1, shelves + 1):
                        ids.append(self.app.inventory.create_location(
                            admin, warehouse_id, f"{aisle}{rack:02d}-S{shelf}",
                            f"Aisle {aisle}, rack {rack}, shelf {shelf}"))
            self.locations[code] = ids

    def _create_catalog(self) -> None:
        admin = self.users["admin"]
        for (category, prefix), products in CATALOG.items():
            category_id = self.app.inventory.category_id(category)
            for number, (name, brand, cost, price, reorder) in enumerate(products, start=1):
                sku = f"{prefix}-{1000 + number * 7}"
                barcode = self._ean13(f"0{self.rng.randint(10 ** 10, 10 ** 11 - 1)}")
                item_id = self.app.inventory.save_item(admin, {
                    "sku": sku, "name": name, "category_id": category_id, "brand": brand,
                    "barcode": barcode, "unit": "ea", "unit_cost": f"{cost:.2f}",
                    "unit_price": f"{price:.2f}", "reorder_point": reorder})
                self.items.append({"id": item_id, "sku": sku, "price": price,
                                   "reorder": reorder,
                                   "home": self.rng.choice(self.locations["MAIN"])})

    def _create_price_lists(self) -> None:
        accountant = self.users["accountant"]
        billing = self.app.billing
        self.lists = {
            "Standard": billing.create_price_list(accountant, "Standard", is_default=True),
            "Wholesale": billing.create_price_list(accountant, "Wholesale"),
            "Education & Nonprofit": billing.create_price_list(accountant,
                                                               "Education & Nonprofit"),
        }
        discounts = {"Standard": 1.00, "Wholesale": 0.88, "Education & Nonprofit": 0.92}
        for item in self.items:
            for name, factor in discounts.items():
                billing.set_price(accountant, self.lists[name], item["id"],
                                  f"{item['price'] * factor:.2f}", self.start)
        # A mid-period price change on a few items, so the price history is not empty.
        change_day = self.start + dt.timedelta(days=self.days // 2)
        for item in self.rng.sample(self.items, 12):
            factor = self.rng.choice((0.95, 1.05, 1.08))
            billing.set_price(accountant, self.lists["Standard"], item["id"],
                              f"{item['price'] * factor:.2f}", change_day)
            billing.set_price(accountant, self.lists["Wholesale"], item["id"],
                              f"{item['price'] * factor * 0.88:.2f}", change_day)

    def _create_customers(self) -> None:
        manager = self.users["manager"]
        reps = [self.users["sales"].id, self.users["sales2"].id]
        for number, (name, city) in enumerate(CUSTOMERS, start=1):
            if any(word in name for word in ("School", "Library", "Learning")):
                price_list = self.lists["Education & Nonprofit"]
            elif number % 4 == 0:
                price_list = self.lists["Wholesale"]
            else:
                price_list = None                          # uses the default list
            domain = "".join(ch for ch in name.lower() if ch.isalnum())[:18]
            customer_id = self.app.customers.save(manager, {
                "code": f"C{number:04d}", "name": name,
                "tax_id": f"TAX-{self.rng.randint(10, 99)}-{self.rng.randint(1000000, 9999999)}",
                "email": f"billing@{domain}.example", "phone": f"555-01{number:02d}",
                "address": f"{self.rng.randint(10, 999)} {self.rng.choice(STREETS)}, {city}",
                "sales_rep_id": reps[number % 2], "price_list_id": price_list,
                "credit_days": self.rng.choice((15, 30, 30, 30, 45, 60))})
            self.customers.append({"id": customer_id,
                                   "rep": "sales" if number % 2 == 0 else "sales2",
                                   "weight": self.rng.choice((1, 1, 2, 3))})

    def _initial_stock(self) -> None:
        clerk = self.users["warehouse"]
        for item in self.items:
            quantity = item["reorder"] * self.rng.randint(3, 6)
            self.app.inventory.receive(clerk, item["id"], item["home"], quantity,
                                       "OPENING", "Opening balance")
            if self.rng.random() < 0.35:            # some stock also in the other sites
                site = self.rng.choice(("EAST", "SHOP"))
                self.app.inventory.receive(clerk, item["id"],
                                           self.rng.choice(self.locations[site]),
                                           max(2, quantity // 4), "OPENING",
                                           "Opening balance")

    # ------------------------------------------------------------------ daily activity
    def _simulate_day(self, day: dt.date) -> None:
        if day.weekday() >= 5:                      # quiet weekends
            return
        rng, recent = self.rng, (self.today - day).days
        self.clock.set(day, 8, rng.randint(0, 50))
        self._restock(day)
        self.clock.set(day, 9, rng.randint(0, 59))
        for _ in range(rng.choice((1, 2, 2, 3, 3, 4))):
            self._new_delivery_note()
        self.clock.set(day, 15, rng.randint(0, 59))
        self._review_notes(keep_recent=recent < 2)
        if rng.random() < 0.15:
            self._move_stock()
        if day.weekday() in (1, 4) and recent > 1:   # invoicing runs Tue and Fri
            self.clock.set(day, 16, rng.randint(0, 30))
            self._invoice_approved(day)
        self.clock.set(day, 17, rng.randint(0, 30))
        self._collect_payments(day)

    def _restock(self, day: dt.date) -> None:
        clerk = self.users["warehouse"]
        for item in self.items:
            on_hand = self.app.inventory.on_hand(item["id"], item["home"])
            # Leave a few items low so the "low stock" alert has something to show.
            if on_hand <= item["reorder"] and (self.today - day).days > 6:
                quantity = item["reorder"] * self.rng.randint(3, 5)
                self.app.inventory.receive(clerk, item["id"], item["home"], quantity,
                                           f"PO-{self.rng.randint(20000, 29999)}",
                                           "Supplier delivery")

    def _new_delivery_note(self) -> None:
        customer = self.rng.choices(self.customers,
                                    weights=[c["weight"] for c in self.customers])[0]
        lines = []
        for item in self.rng.sample(self.items, self.rng.randint(1, 5)):
            on_hand = self.app.inventory.on_hand(item["id"], item["home"])
            quantity = min(on_hand, self.rng.randint(1, max(2, item["reorder"] // 2)))
            if quantity > 0:
                lines.append((item["id"], item["home"], quantity))
        if lines:
            remarks = self.rng.choice(("", "", "", "Deliver to loading dock",
                                       "Call before delivery", "Urgent"))
            self.app.dispatch.create_note(self.users[customer["rep"]], customer["id"], lines,
                                          remarks)

    def _review_notes(self, keep_recent: bool) -> None:
        manager = self.users["manager"]
        for note in self.app.dispatch.list_notes(manager, status="ISSUED"):
            if keep_recent and self.rng.random() < 0.8:
                continue                                    # leave some awaiting approval
            roll = self.rng.random()
            if roll < 0.06:
                self.app.dispatch.return_to_sales(
                    manager, note["id"], self.rng.choice((
                        "Quantity does not match the signed copy",
                        "Customer purchase order number missing",
                        "Wrong delivery address on the note")))
            elif roll < 0.09:
                self.app.dispatch.void(manager, note["id"], "Customer cancelled the order")
            else:
                self.app.dispatch.approve(manager, note["id"])
        for note in self.app.dispatch.list_notes(manager, status="RETURNED"):
            if self.rng.random() < 0.5:
                self.app.dispatch.resubmit(self._rep_for(note), note["id"],
                                           "Corrected and re-signed")

    def _move_stock(self) -> None:
        clerk = self.users["warehouse"]
        item = self.rng.choice(self.items)
        on_hand = self.app.inventory.on_hand(item["id"], item["home"])
        if self.rng.random() < 0.6 and on_hand > 6:
            self.app.inventory.transfer(clerk, item["id"], item["home"],
                                        self.rng.choice(self.locations["SHOP"]),
                                        self.rng.randint(1, 3), "Showroom display stock")
        elif on_hand > 3:
            self.app.inventory.adjust(clerk, item["id"], item["home"],
                                      on_hand - self.rng.randint(1, 2),
                                      "Cycle count: damaged packaging written off")

    def _invoice_approved(self, day: dt.date) -> None:
        accountant = self.users["accountant"]
        by_customer: dict = {}
        for note in self.app.billing.notes_ready_to_invoice():
            by_customer.setdefault(note["customer_id"], []).append(note["id"])
        for customer_id, note_ids in by_customer.items():
            draft = self.app.billing.build_draft(accountant, customer_id, note_ids, day)
            if self.rng.random() < 0.1:                     # negotiated discount on a line
                line = self.rng.choice(draft.lines)
                line.unit_price = int(line.unit_price * 0.95)
            self.app.billing.create_invoice(accountant, draft)

    def _collect_payments(self, day: dt.date) -> None:
        accountant = self.users["accountant"]
        for invoice in self.app.billing.list_invoices(accountant, status="OPEN"):
            issued = dt.date.fromisoformat(invoice["issue_date"])
            due = dt.date.fromisoformat(invoice["due_date"])
            age, open_amount = (day - issued).days, invoice["total"] - invoice["paid"]
            if age < 5 or open_amount <= 0:
                continue
            slow_payer = invoice["customer_id"] % 7 == 0     # some customers pay late
            chance = 0.02 if slow_payer else (0.12 if day <= due else 0.06)
            if self.rng.random() >= chance:
                continue
            recent = (self.today - day).days <= 4
            payer = self._rep_for(invoice) if recent else accountant
            amount = open_amount if self.rng.random() < 0.8 else open_amount // 2
            try:
                self.app.receivables.record_payment(
                    payer, invoice["id"], f"{amount / 100:.2f}",
                    self.rng.choice(("Bank transfer", "Bank transfer", "Card", "Check", "Wire")),
                    f"REF-{self.rng.randint(100000, 999999)}", day)
            except BusinessRuleError:
                continue                                   # already has a pending payment

    def _rep_for(self, invoice):
        customer = next(c for c in self.customers if c["id"] == invoice["customer_id"])
        return self.users[customer["rep"]]

    def _finishing_touches(self) -> None:
        """Make sure every interesting state exists for the demo."""
        self.clock.set(self.today, 8, 30)
        manager = self.users["manager"]
        accountant = self.users["accountant"]
        rejected = self.app.receivables.list_payments(accountant, status="PENDING")
        if len(rejected) > 2:
            self.app.receivables.reject_payment(accountant, rejected[-1]["id"],
                                                "Not found in the bank statement")
        if not self.app.dispatch.list_notes(manager, status="RETURNED"):
            self._new_delivery_note()
            newest = self.app.dispatch.list_notes(manager, status="ISSUED")[0]
            self.app.dispatch.return_to_sales(manager, newest["id"],
                                              "Customer purchase order number missing")
        if not self.app.dispatch.list_notes(manager, status="ISSUED"):
            self._new_delivery_note()
        self.clock.set(self.today, 9, 0)

    @staticmethod
    def _ean13(first12: str) -> str:
        """Append the EAN-13 check digit to a 12-digit string."""
        digits = [int(d) for d in first12[:12]]
        total = sum(d * (3 if i % 2 else 1) for i, d in enumerate(digits))
        return first12[:12] + str((10 - total % 10) % 10)


def main(argv=None) -> int:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--path", type=Path, default=default_db_path(),
                        help="database file to create (default: %(default)s)")
    parser.add_argument("--days", type=int, default=120,
                        help="days of simulated history (default: %(default)s)")
    parser.add_argument("--seed", type=int, default=42, help="random seed")
    parser.add_argument("--force", action="store_true",
                        help="overwrite the file without asking")
    args = parser.parse_args(argv)

    if args.path.exists():
        if not args.force and sys.stdin.isatty():
            answer = input(f"{args.path} exists. Replace it? [y/N] ").strip().lower()
            if answer not in ("y", "yes"):
                print("Nothing changed.")
                return 1
        for suffix in ("", "-wal", "-shm"):
            Path(f"{args.path}{suffix}").unlink(missing_ok=True)

    print(f"Creating {args.path} with {args.days} days of history...")
    summary = MockDataBuilder(args.path, args.days, args.seed).build()
    for table, count in summary.items():
        print(f"  {table:<16} {count:>6}")
    print("Done. Sign in with any of: " + ", ".join(u[0] for u in USERS)
          + f" (password: {DEMO_PASSWORD})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
