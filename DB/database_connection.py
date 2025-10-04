import sqlite3
from models import Patient, Provider, Appointment
from typing import List

patients_db: List[Patient] = []
providers_db: List[Provider] = []
appointments_db: List[Appointment] = []

class AppointmentAndPatientManager:
    def __init__(self, db_name="appointment_details_new.db"):
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
                provider_id TEXT NOT NULL,
                appointment_date TEXT NOT NULL,
                appointment_time TEXT NOT NULL,
                FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
                FOREIGN KEY (provider_id) REFERENCES providers(provider_id)
            )
        ''')

        # Create Provider table
        self.cursor.execute('''
                    CREATE TABLE IF NOT EXISTS providers (
                        provider_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        provider_name TEXT NOT NULL,
                        location TEXT NOT NULL,
                        speciality TEXT NOT NULL,
                        slots TEXT NOT NULL
                    )
                ''')

        self.conn.commit()

    def add_patient(self, first_name, last_name, gender, date_of_birth,
                        email, phone_number, address):
        try:
            self.cursor.execute("INSERT INTO patients (first_name, last_name, gender, date_of_birth, email, phone_number, address) VALUES (?, ?, ?, ?, ?, ?, ?)", (first_name, last_name, gender, date_of_birth,
                        email, phone_number, address))
            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.IntegrityError:
            return 0

    def get_all_patients(self):
        self.cursor.execute("SELECT * FROM patients p")
        rows = self.cursor.fetchall()
        patients_db = []

        for row in rows:
            patient = Patient(id=row[0], first_name=row[1], last_name=row[2], email=row[3], date_of_birth=row[4], gender=row[5], phone_number=row[6], address=row[7])
            patients_db.append(patient)

        return patients_db

    def get_all_providers(self):
        self.cursor.execute("SELECT * FROM providers p")
        rows = self.cursor.fetchall()
        providers_db = []

        for row in rows:
            providerName = "Dr. " + row[1]
            provider = Provider(id=row[0], provider_name=providerName, location=row[2], speciality=row[3], slots=row[4])
            providers_db.append(provider)

        return providers_db

    def get_provider_by_id(self, provider_id):
        self.cursor.execute("SELECT * FROM providers WHERE provider_id = ?", (provider_id,))
        row = self.cursor.fetchone()
        provider = Provider(id=row[0], provider_name=row[1], location=row[2], speciality=row[3], slots=row[4])
        return provider

    def get_provider_by_name(self, provider_name):
        self.cursor.execute("SELECT * FROM providers WHERE provider_name like ?", (provider_name,))
        row = self.cursor.fetchone()
        if row is None:
            return None
        provider = Provider(id=row[0], provider_name=row[1], location=row[2], speciality=row[3], slots=row[4])
        return provider

    def get_providers_by_location(self, location):
        self.cursor.execute("SELECT * FROM providers WHERE location like ?", (location,))
        rows = self.cursor.fetchall()

        providers_db = []
        for row in rows:
            provider = Provider(id=row[0], provider_name=row[1], location=row[2], speciality=row[3], slots=row[4])
            providers_db.append(provider)

        return providers_db

    def get_providers_by_speciality(self, speciality):
        self.cursor.execute("SELECT * FROM providers WHERE speciality like ?", (speciality,))
        rows = self.cursor.fetchall()

        providers_db = []

        for row in rows:
            provider = Provider(id=row[0], provider_name=row[1], location=row[2], speciality=row[3], slots=row[4])
            providers_db.append(provider)

        return providers_db

    def get_all_appointments(self):
        self.cursor.execute("SELECT * FROM appointments ap")
        rows = self.cursor.fetchall()
        appointments_db = []

        for row in rows:
            appointment = Appointment(id=row[0], patient_id=row[1], doctor_name=row[2], appointment_date=row[3], appointment_time=row[4])
            appointments_db.append(appointment)

        return appointments_db

    def get_appointments_by_patient_Name(self, patient_first_name, patient_last_name):
        patient = self.get_patient_by_name(patient_first_name, patient_last_name)
        if patient is None:
            return {
                "Message": f"No patient found with the name {patient_first_name} {patient_last_name}."
            }

        self.cursor.execute("SELECT * FROM appointments WHERE patient_id = ?", (patient.id,))
        rows = self.cursor.fetchall()
        if rows is None:
            return {
                "Message": f"No appointments found of patient {patient_first_name} {patient_last_name}."
            }

        appointments_db = []

        for row in rows:
            provider = self.get_provider_by_id(row[2]);
            appointment = Appointment(id=row[0], patient_name=patient_first_name , doctor_name=provider.provider_name, appointment_date=row[3],
                                      appointment_time=row[4])
            appointments_db.append(appointment)

        return appointments_db

    def get_patient_by_id(self, patient_id):
        self.cursor.execute("SELECT * FROM patients WHERE patient_id = ?", (patient_id))
        row = self.cursor.fetchone()
        patient = Patient(id=row[0], first_name=row[1], last_name=row[2], email=row[3], date_of_birth=row[4], gender=row[5], phone_number=row[6], address=row[7])
        return patient

    def get_patient_by_name(self, first_name, last_name):
        self.cursor.execute("SELECT * FROM patients WHERE first_name like ? AND last_name like ?", (first_name, last_name,))
        row = self.cursor.fetchone()
        if row is None:
            return None
        patient = Patient(id=row[0], first_name=row[1], last_name=row[2], email=row[3], date_of_birth=row[4], gender=row[5], phone_number=row[6], address=row[7])
        return patient

    def get_provider_by_id(self, provider_id):
        self.cursor.execute("SELECT * FROM providers WHERE provider_id = ?", (provider_id))
        row = self.cursor.fetchone()
        provider = Provider(id=row[0], provider_name=row[1], location=row[2], speciality=row[3], slots=row[4])
        return provider

    def verify_patient_by_phone_and_dob(self, patient_data):
        self.cursor.execute("SELECT * FROM patients WHERE first_name like ? AND last_name like ? AND phone_number = ? AND date_of_birth = ?", (patient_data.first_name, patient_data.last_name, patient_data.phone_number, patient_data.date_of_birth))
        row = self.cursor.fetchone()
        patient = Patient(id=row[0], first_name=row[1], last_name=row[2], email=row[3], date_of_birth=row[4], gender=row[5], phone_number=row[6], address=row[7])
        return patient

    def verify_patient_by_phone(self, patient_first_name, patient_last_name, patient_phone_no):
        self.cursor.execute("SELECT * FROM patients WHERE first_name like ? AND last_name like ? AND phone_number = ?", (patient_first_name, patient_last_name, patient_phone_no))
        row = self.cursor.fetchone()
        if row is None:
            return 0
        else:
            patient = Patient(id=row[0], first_name=row[1], last_name=row[2], email=row[3], date_of_birth=row[4], gender=row[5], phone_number=row[6], address=row[7])
            return patient.id

    def schedule_appointment(self, patient_id, provider_id, date, time):
        try:
            self.cursor.execute(
                "INSERT INTO appointments (patient_id, provider_id, appointment_date, appointment_time) VALUES (?, ?, ?, ?)",
                (patient_id, provider_id, date, time))
            self.conn.commit()
            return {"Message": f"Appointment scheduled for patient ID {patient_id} with doctor {provider_id} on {date} at {time}. The appointment id is {self.cursor.lastrowid}."}

        except sqlite3.Error as e:
            return {
                "Message": f"Error scheduling appointment: {e}"}


    def schedule_appointment_with_detail(self,req):
        try:
            patient_id = self.verify_patient_by_phone(req.first_name, req.last_name, req.phone_number)
            if patient_id is 0:
                patient_id = self.add_patient(req.first_name, req.last_name, req.gender, req.dob,
                                                 req.email, req.phone_number, req.address)

            self.cursor.execute(
                "INSERT INTO appointments (patient_id, provider_id, appointment_date, appointment_time) VALUES (?, ?, ?, ?)",
                (patient_id, req.provider_id, req.date, req.time))
            self.conn.commit()
            return {"Message": f"Appointment scheduled . The appointment id is {self.cursor.lastrowid}."}

        except sqlite3.Error as e:
            return {
                "Message": f"Error scheduling appointment: {e}"}

    def reschedule_appointment(self, provider_name, patient_first_name, patient_last_name, new_date, new_time):
        provider = self.get_provider_by_name(provider_name)
        if provider is None:
            return {
                "Message": f"No doctor found with the name {provider_name}."
            }

        patient = self.get_patient_by_name(patient_first_name, patient_last_name)
        if patient is None:
            return {
                "Message": f"No patient found with the name {patient_first_name} {patient_last_name}."
            }

        self.cursor.execute(
            "UPDATE appointments SET appointment_date = ?, appointment_time = ? WHERE patient_id = ? AND provider_id = ?",
            (new_date, new_time, patient.id, provider.id))

        self.conn.commit()
        if self.cursor.rowcount == 0:
            return {
                "Message": f"No appointment found for patient {patient_first_name} {patient_last_name} with doctor {provider_name}."
            }
        else:
            return {
                "Message": f"Appointment of patient {patient_first_name} {patient_last_name} with doctor {provider_name} updated to {new_date} at {new_time}"
            }

    def cancel_appointment(self, patient_first_name, patient_phone_number):
        self.cursor.execute(
            "SELECT * FROM patients WHERE first_name like ? AND phone_number = ?",
            (patient_first_name, patient_phone_number))
        row = self.cursor.fetchone()
        patient = Patient(id=row[0], first_name=row[1], last_name=row[2], email=row[3], date_of_birth=row[4],
                          gender=row[5], phone_number=row[6], address=row[7])
        if patient is None:
            return {
                "Message": f"No patient found with the name {patient_first_name} and phone no. {patient_phone_number}."
            }
        # Now check if appointment exists for this patient
        self.cursor.execute(
            "SELECT * FROM appointments WHERE patient_id = ?",
            (patient.id,))
        row = self.cursor.fetchone()
        if row is None:
            return {
                "Message": f"No appointments found for patient {patient_first_name} with dob {patient_dob}."
            }
        appointments_id = row[0]
        return self.cancel_appointment_by_id(appointments_id, patient_first_name)

    def cancel_appointment_by_id(self, appointment_id, patient_first_name):
        self.cursor.execute("DELETE FROM appointments WHERE appointment_id = ?", (appointment_id,))
        self.conn.commit()
        return {"Message": f"Appointment cancelled for patient {patient_first_name}."}

    def close_connection(self):
        self.conn.close()