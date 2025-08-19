import sqlite3
from models import Patient
from typing import List

patients_db: List[Patient] = []

class AppointmentManager:
    def __init__(self, db_name="appointments.db"):
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self._create_tables()

    def _create_tables(self):
        # Create Patients table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS patients (
                patient_id INTEGER PRIMARY KEY AUTOINCREMENT,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                gender TEXT NOT NULL,
                date_of_birth TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                phone_number TEXT,
                address TEXT
            )
        ''')

        self.conn.commit()

    def add_patient(self, first_name, last_name, gender, date_of_birth,
                        email, phone_number, address):
        try:
            self.cursor.execute("INSERT INTO patients (first_name, last_name, gender, date_of_birth, email, phone_number, address) VALUES (?, ?, ?, ?, ?, ?, ?)", (first_name, last_name, gender, date_of_birth,
                        email, phone_number, address))
            self.conn.commit()
            print(f"Patient '{first_name}' added successfully.")
        except sqlite3.IntegrityError:
            print(f"Error: Patient with email id '{email}' already exists.")

    def get_all_patients(self):
        self.cursor.execute("SELECT * FROM patients p")
        rows = self.cursor.fetchall()
        patients_db = []

        for row in rows:
            patient = Patient(id=row[0], first_name=row[1], last_name=row[2], email=row[3], date_of_birth=row[4], gender=row[5], phone_number=row[6], address=row[7])
            patients_db.append(patient)

        return patients_db

    def get_patient_by_id(self, patient_id):
        self.cursor.execute("SELECT * FROM patients WHERE patient_id = ?", (patient_id))
        row = self.cursor.fetchone()
        patient = Patient(id=row[0], first_name=row[1], last_name=row[2], email=row[3], date_of_birth=row[4], gender=row[5], phone_number=row[6], address=row[7])
        return patient

    def verify_patient_by_phone_and_dob(self, patient_data):
        self.cursor.execute("SELECT * FROM patients WHERE first_name = ? AND last_name = ? AND phone_number = ? AND date_of_birth = ?", (patient_data.first_name, patient_data.last_name, patient_data.phone_number, patient_data.date_of_birth))
        row = self.cursor.fetchone()
        patient = Patient(id=row[0], first_name=row[1], last_name=row[2], email=row[3], date_of_birth=row[4], gender=row[5], phone_number=row[6], address=row[7])
        return patient



    def close_connection(self):
        self.conn.close()