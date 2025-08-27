import sqlite3
from models import Patient, Appointment
from typing import List

patients_db: List[Patient] = []
appointments_db: List[Appointment] = []

class AppointmentManager:
    def __init__(self, db_name="appointments_db.db"):
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self._create_tables()

    def _create_tables(self):
        # Create Appointments table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS appointments (
                appointment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_name TEXT NOT NULL,
                doctor_name TEXT NOT NULL,
                appointment_date TEXT NOT NULL,
                appointment_time TEXT NOT NULL
            )
        ''')

        self.conn.commit()

    def view_appointments(self, patient_name):
        updated_patient_name = f"%{patient_name}%"
        self.cursor.execute("SELECT * FROM appointments WHERE patient_name LIKE ?", (updated_patient_name,))
        rows = self.cursor.fetchall()
        appointments_db = []

        for row in rows:
            appointment = Appointment(id = row[0], patient_name=row[1], doctor_name=row[2], appointment_date=row[3], appointment_time=row[4])
            appointments_db.append(appointment)

        return appointments_db


    def schedule_appointment(self, patient_name, doctor_name, date, time):
        try:
            self.cursor.execute(
                "INSERT INTO appointments (patient_name, doctor_name, appointment_date, appointment_time) VALUES (?, ?, ?, ?)",
                (patient_name, doctor_name, date, time))
            self.conn.commit()
            return {"Message": f"Appointment scheduled for patient ID {patient_name} with doctor {doctor_name} on {date} at {time}."}

        except sqlite3.Error as e:
            return {
                "Message": f"Error scheduling appointment: {e}"}

    def reschedule_appointment(self, patient_name, doctor_name, new_date, new_time):
        self.cursor.execute(
            "UPDATE appointments SET appointment_date = ?, appointment_time = ? WHERE patient_name = ? AND doctor_name = ?",
            (new_date, new_time, patient_name, doctor_name))
        self.conn.commit()
        return {"Message": f"Appointment of patient {patient_name} with doctor {doctor_name} updated to {new_date} at {new_time}."}

    def cancel_appointment(self, request):
        self.cursor.execute("DELETE FROM appointments WHERE patient_name = ? AND doctor_name = ?", (request.patient_name, request.doctor_name))
        self.conn.commit()
        return {"Message": f"Appointment of patient {request.patient_name} with doctor {request.doctor_name} is cancelled."}

    def close_connection(self):
        self.conn.close()