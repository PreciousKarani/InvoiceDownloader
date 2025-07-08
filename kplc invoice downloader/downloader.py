import os
import requests
import cx_Oracle
from pathlib import Path
from db_conn import DB_CONFIG


class InvoiceDownloader:
    def __init__(self, account_number: str, month: str, save_folder: str):
        self.account_number = account_number
        self.month = month
        self.save_folder = Path(save_folder)
        self.invoice_ids = []
        self.customer_name = ""
        self.token = self.generate_token()
        self.headers = {"Authorization": f"Bearer {self.token}"}
        os.makedirs(self.save_folder, exist_ok=True)

    def generate_token(self):
        basic_auth_bearertoken = "MElHZExfb3JPU1lzTEdjeHpiNkVnWkdIbGRJYTpfZmtVa3M3NVBaTVViUEF5ZE5SNTNTR1VIdVVh"
        url = 'https://selfservice.kplc.co.ke/api/token'
        headers = {
            "Authorization": f"Basic {basic_auth_bearertoken}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        data = {
            "grant_type": "client_credentials",
            "scope": "nuru_docs_private"
        }
        response = requests.post(url, headers=headers, data=data, verify=False)
        if response.status_code == 200:
            token = response.json().get("access_token")
            print("✅ Token acquired")
            return token
        else:
            raise Exception(f"Failed to get token: {response.status_code}, {response.text}")

    def fetch_invoice_ids(self):
        print(f"Querying DB for {self.account_number} in {self.month}")
        dsn = cx_Oracle.makedsn(
            DB_CONFIG["host"],
            DB_CONFIG["port"],
            service_name=DB_CONFIG["service_name"]
        )
        conn = cx_Oracle.connect(
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            dsn=dsn
        )
        cursor = conn.cursor()

        query = """
        SELECT FULL_NAME AS CUSTOMER_NAME, GPF.REFERENCE AS ACCOUNT_NUMBER, GN.ID_NOTICE
        FROM INCMS_ADMINIS.GCCB_NOTICE GN
            INNER JOIN INCMS_ADMINIS.GCCB_NOTICE_BILL GNB ON GN.ID_NOTICE = GNB.ID_NOTICE
            INNER JOIN INCMS_ADMINIS.GCCOM_BILL GB ON GNB.ID_BILL = GB.ID_BILL
            INNER JOIN INCMS_ADMINIS.GCCOM_BILLING_PERIOD GBP ON GB.ID_BILLING_PERIOD = GBP.ID_BILLING_PERIOD
            INNER JOIN INCMS_ADMINIS.GCCOM_PAYMENT_FORM GPF ON GB.ID_PAYMENT_FORM = GPF.ID_PAYMENT_FORM
            INNER JOIN INCMS_ADMINIS.GCCD_RELATIONSHIP GR ON GPF.ID_CUSTOMER = GR.ID_RELATIONSHIP
        WHERE GPF.REFERENCE = :account_number AND TO_CHAR(GBP.INITIAL_DATE, 'yyyymm') = :month
        """

        cursor.execute(query, account_number=self.account_number, month=self.month)
        rows = cursor.fetchall()

        if not rows:
            raise Exception(f"No invoices found for account {self.account_number} in {self.month}.")

        self.customer_name = rows[0][0]
        self.invoice_ids = [row[2] for row in rows]
        print(f"✅ Found {len(self.invoice_ids)} invoice(s) for {self.account_number}")

        cursor.close()
        conn.close()

    def download_invoices(self):
        if not self.invoice_ids:
            return [(f"❌ No invoices to download for account {self.account_number}", "red")]

        downloaded = 0
        skipped = 0
        errors = 0

        for invoice_id in self.invoice_ids:
            url = f"https://selfservice.kplc.co.ke/api/nuruDocuments/4/{invoice_id}/pdf"

            safe_name = "".join(c for c in self.customer_name if c.isalnum() or c in (' ', '_')).rstrip()
            safe_name = safe_name.replace(' ', '_')
            filename = f"{safe_name}_{self.account_number}_{invoice_id}.pdf"
            file_path = self.save_folder / filename

            if file_path.exists():
                print(f"File exists, skipping: {file_path}")
                skipped += 1
                continue

            try:
                response = requests.get(url, headers=self.headers, verify=False)
                if response.status_code == 422:
                    print(f" Invoice ID {invoice_id} not found.")
                    errors += 1
                    continue

                response.raise_for_status()

                with open(file_path, "wb") as f:
                    f.write(response.content)

                print(f"✅ Downloaded: {file_path}")
                downloaded += 1
            except Exception as e:
                print(f"❌ Error downloading {invoice_id}: {e}")
                errors += 1
                continue

        results = []
        if downloaded:
            results.append((f"✅ Downloaded for account {self.account_number} ({downloaded} invoice(s))", "green"))
        if skipped:
            results.append((f"Invoice Already Exists for account {self.account_number} ({skipped} invoice(s))", "orange"))
        if errors:
            results.append((f"❌ Failed downloads for account {self.account_number} ({errors})", "red"))

        return results or [(f" No files downloaded for account {self.account_number}", "gray")]
