import sqlite3
from models import Patient, Appointment
from typing import List

patients_db: List[Patient] = []
appointments_db: List[Appointment] = []

class AppointmentAndPatientManager:
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

        # Create Appointments table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS appointments (
                appointment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER,
                doctor_name TEXT NOT NULL,
                appointment_date TEXT NOT NULL,
                appointment_time TEXT NOT NULL,
                FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
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

    def get_all_appointments(self):
        self.cursor.execute("SELECT * FROM appointments ap")
        rows = self.cursor.fetchall()
        appointments_db = []

        for row in rows:
            appointment = Appointment(id=row[0], patient_id=row[1], doctor_name=row[2], appointment_date=row[3], appointment_time=row[4])
            appointments_db.append(appointment)

        return appointments_db


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

    def schedule_appointment(self, patient_id, doctor_name, date, time):
        try:
            self.cursor.execute(
                "INSERT INTO appointments (patient_id, doctor_name, appointment_date, appointment_time) VALUES (?, ?, ?, ?)",
                (patient_id, doctor_name, date, time))
            self.conn.commit()
            return {"Message": f"Appointment scheduled for patient ID {patient_id} with doctor {doctor_name} on {date} at {time}."}

        except sqlite3.Error as e:
            return {
                "Message": f"Error scheduling appointment: {e}"}

    def update_appointment_time(self, appointment_id, new_date, new_time):
        self.cursor.execute(
            "UPDATE appointments SET appointment_date = ?, appointment_time = ? WHERE appointment_id = ?",
            (new_date, new_time, appointment_id))
        self.conn.commit()
        return {"Message": f"Appointment ID {appointment_id} updated to {new_date} at {new_time}."}

    def cancel_appointment(self, appointment_id):
        self.cursor.execute("DELETE FROM appointments WHERE appointment_id = ?", (appointment_id,))
        self.conn.commit()
        return {"Message": f"Appointment ID {appointment_id} cancelled."}

    def close_connection(self):
        self.conn.close()